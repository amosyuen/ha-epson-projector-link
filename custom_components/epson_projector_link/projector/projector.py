"""TCP connection of Epson projector module."""

import asyncio
import binascii
from collections import deque
import inspect
import logging

import async_timeout
from homeassistant.const import STATE_UNKNOWN

from .const import AUTO_IRIS_MODE_CODE_MAP
from .const import COLOR_MODE_CODE_MAP
from .const import ESCVPNETNAME
from .const import ESCVPNET_CONNECT_COMMAND
from .const import IMEVENT
from .const import IMEVENT_ALARM_BIT_MAP
from .const import IMEVENT_STATUS_CODE_ABNORMAL
from .const import IMEVENT_STATUS_CODE_TO_POWER_MAP
from .const import IMEVENT_WARNING_BIT_MAP
from .const import OFF
from .const import ON
from .const import POWER_CODE_MAP
from .const import POWER_CONSUMPTION_MODE_CODE_MAP
from .const import PROPERTY_AUTO_IRIS_MODE
from .const import PROPERTY_BRIGHTNESS
from .const import PROPERTY_COLOR_MODE
from .const import PROPERTY_ERR
from .const import PROPERTY_ERR_CODE_MAP
from .const import PROPERTY_LAMP_HOURS
from .const import PROPERTY_MUTE
from .const import PROPERTY_POWER
from .const import PROPERTY_POWER_CONSUMPTION_MODE
from .const import PROPERTY_SOURCE
from .const import PROPERTY_SOURCE_LIST
from .const import PROPERTY_VOLUME
from .const import RESPONSE_ERROR
from .const import SOURCE_CODE_MAP
from .const import STATE_COOLDOWN
from .const import STATE_OFF
from .const import STATE_ON
from .const import STATE_WARMUP
from .const import STATUS_CODE_MAP
from .const import STATUS_OK
from .const import TCP_PORT
from .const import TIMEOUT_CONNECT
from .const import TIMEOUT_POWER_ON_OFF
from .const import TIMEOUT_REQUEST
from .exceptions import ProjectorErrorResponse

_LOGGER = logging.getLogger(__name__)


def hex_string_to_int(string):
    return int(string, 16)


def _get_source_name(code):
    source_name = SOURCE_CODE_MAP.get(code)
    return code if source_name is None else source_name


def _parse_source_list(response):
    parts = response.split(" ")
    if len(parts) % 2 == 1:
        _LOGGER.error(
            "_parse_source_list: Source list response has odd number of values. response=%s",
            response,
        )
    sources = []
    for i in range(len(parts) // 2):
        code = parts[2 * i]
        source_name = SOURCE_CODE_MAP.get(code)
        sources.append(code if source_name is None else source_name)
    return sources


POWER_PARSER = POWER_CODE_MAP.get
PROPERTY_PARSER_MAP = {
    PROPERTY_AUTO_IRIS_MODE: AUTO_IRIS_MODE_CODE_MAP.get,
    PROPERTY_COLOR_MODE: COLOR_MODE_CODE_MAP.get,
    PROPERTY_ERR: PROPERTY_ERR_CODE_MAP.get,
    PROPERTY_LAMP_HOURS: int,
    PROPERTY_BRIGHTNESS: int,
    PROPERTY_MUTE: lambda v: v == ON,
    PROPERTY_POWER: POWER_PARSER,
    PROPERTY_POWER_CONSUMPTION_MODE: POWER_CONSUMPTION_MODE_CODE_MAP.get,
    PROPERTY_SOURCE: _get_source_name,
    PROPERTY_SOURCE_LIST: _parse_source_list,
    PROPERTY_VOLUME: int,
}


class Projector:
    """
    Epson Projector Home Cinema that connects using a TCP socket.
    """

    def __init__(self, host, port=TCP_PORT):
        """
        :param str host:            IP address of Projector
        :param int port:            Port to connect to
        """
        self._host = host
        self._port = port
        self._is_open = False
        self._has_errors = False
        self._serial = None
        self._callback = None
        self._power_state = None
        self._power_on_off_future = None
        self._request_queue = deque()
        self._tasks = set()

        self._reader = None
        self._writer = None

    def set_callback(self, callback):
        self._callback = callback

    async def connect(self):
        """Async init to open connection with projector."""
        _LOGGER.debug("connect")
        response = None
        try:
            with async_timeout.timeout(TIMEOUT_CONNECT):
                reader, writer = await asyncio.open_connection(
                    host=self._host, port=self._port
                )
                writer.write(ESCVPNET_CONNECT_COMMAND.encode())
                response = await reader.read(16)
        except asyncio.TimeoutError:
            _LOGGER.exception("connect: Opening connection timed out")
            raise
        except ConnectionRefusedError:
            _LOGGER.exception("connect: Connection refused")
            raise

        _LOGGER.debug(
            "connect: response=%s bytes=%s len=%d",
            response.decode().encode("unicode_escape"),
            binascii.hexlify(response),
            len(response),
        )
        if len(response) < 16 or response[0:10].decode() != ESCVPNETNAME:
            raise Exception("Unsupported connect response format.")

        # message format https://support.atlona.com/hc/en-us/articles/360048888054-IP-Control-of-Epson-Projectors
        # byte 10 is the version
        # byte 11 is the type (TYPE_CONNECT)
        # bytes 12 and 13 are the seq no of the message
        status_code = response[14]
        status = STATUS_CODE_MAP.get(status_code, status_code)
        header_count = response[15]
        _LOGGER.debug(
            "connect: status=%s, header_count=%d",
            status,
            header_count,
        )
        if status_code != STATUS_OK:
            raise Exception(f"Connect response returned error status={status}")

        self._is_open = True
        self._reader = reader
        self._writer = writer
        self._create_task(self._listen())
        _LOGGER.info("connect: Connection opened")
        return

    def close(self):
        if self._is_open:
            # Must set _is_open to false before closing to prevent re-connect try in _listen()
            self._is_open = False
            self._writer.close()

            for request in self._request_queue:
                request.future.cancel("Connection closed")
            self._request_queue.clear()

    async def get_property(self, prop):
        """Get property state from device."""
        if not prop:
            return
        return await self._send_request(Request(f"{prop}?"))

    async def set_property(self, prop, value):
        """Set property. Returns the set prop value."""
        if not prop or not value:
            return
        return await self._send_request(Request(f"{prop} {value}", value))

    async def send_command(self, command, arg=None):
        """Send command."""
        if not command:
            return
        if arg is not None:
            command = f"{command} {arg}"
        return await self._send_request(Request(command))

    async def _send_request(self, request):
        """Send TCP request."""
        _LOGGER.debug('_send_request: command="%s"', request.command)

        if self._is_open is False:
            await self.connect()

        for r in self._request_queue:
            if r.command == request.command:
                _LOGGER.debug(
                    '_send_request: command="%s" waiting on previous duplicate command',
                    request.command,
                )
                return await r.future

        self._request_queue.append(request)

        if len(self._request_queue) > 1:
            _LOGGER.debug(
                '_send_request: command="%s" waiting for %d queued futures',
                request.command,
                len(self._request_queue) - 1,
            )
            # Wait for previous request to finish, ignoring result
            try:
                await self._request_queue[-2].future
            except Exception:
                pass

        # Wait if the projector is cooling down or warming up
        if self._power_state == STATE_COOLDOWN or self._power_state == STATE_WARMUP:
            if (
                self._power_on_off_future is not None
                and not self._power_on_off_future.done()
            ):
                try:
                    _LOGGER.debug(
                        '_send_request: command="%s" waiting for power state change future',
                        request.command,
                    )
                    with async_timeout.timeout(TIMEOUT_POWER_ON_OFF):
                        await self._power_on_off_future
                except asyncio.TimeoutError as err:
                    _LOGGER.warning(
                        '_send_request: command="%s" timeout waiting for _power_on_off_future',
                        request.command,
                    )
                    if (
                        self._power_on_off_future is not None
                        and not self._power_on_off_future.done()
                    ):
                        self._power_on_off_future.set_exception(err)
                except Exception:
                    pass

        try:
            is_power_request = request.command.startswith(PROPERTY_POWER + " ")
            if is_power_request:
                self._power_on_off_future = request.future
            _LOGGER.debug(
                '_send_request: command="%s" sending request',
                request.command,
            )
            with async_timeout.timeout(
                TIMEOUT_POWER_ON_OFF if is_power_request else TIMEOUT_REQUEST
            ):
                self._writer.write(f"{request.command}\r".encode())
                return await request.future
        except Exception as err:
            _LOGGER.exception(
                '_send_request: command="%s" error=%s',
                request.command,
                err,
            )
            if not request.future.done():
                request.future.set_exception(err)
            raise
        finally:
            if request in self._request_queue:
                self._request_queue.remove(request)

    async def _listen(self):
        _LOGGER.debug("_listen: Listening to connection")

        while self._is_open:
            try:
                response_bytes = await self._reader.readuntil(b":")
            except Exception:
                break
            if len(response_bytes) == 0:
                _LOGGER.info("_listen: End of file")
                break

            response = response_bytes.decode()
            _LOGGER.debug(
                "_listen: response=%s bytes=%s len=%d",
                response.encode("unicode_escape"),
                binascii.hexlify(response_bytes),
                len(response),
            )

            # Always ends with colon, strip it off
            # Also strip off trailing carriage return if it exists
            if len(response) >= 2 and response[-2] == "\r":
                response = response[0:-2]
            else:
                response = response[0:-1]

            if len(response) == 0:
                self._handle_ack()
                continue

            if response == RESPONSE_ERROR:
                self._handle_err()
                continue

            key_value_separator_index = response.find("=")
            if key_value_separator_index != -1:
                prop = response[0:key_value_separator_index]
                value = response[key_value_separator_index + 1 :]
                if prop == IMEVENT:
                    await self._handle_imevent(value)
                    continue

                # Response from projector
                self._handle_property(prop, value)
                continue

            _LOGGER.warning("_listen: Unhandled response %s", response)

        _LOGGER.info("_listen: Connection ended")

        # Try to-reopen connection, if it was not an explicit close.
        # Explicit close will set _is_open to False.
        if self._is_open:
            self._is_open = False
            self._create_task(self.connect())

    def _handle_ack(self):
        request = self._pop_request()
        command = request.command if request else STATE_UNKNOWN
        _LOGGER.debug('_handle_ack: Received ACK response for command="%s"', command)
        if request:
            # Set state to warmup / cooldown so we will delay requests until power state changes
            if (self._power_state == STATE_OFF) and command == f"{PROPERTY_POWER} {ON}":
                if self._power_on_off_future is None:
                    _LOGGER.debug(
                        "_update_property: Creating _power_on_off_future for warmup"
                    )
                    self._power_on_off_future = asyncio.Future()
                self._update_property(PROPERTY_POWER, STATE_WARMUP)
            elif self._power_state == STATE_ON and command == f"{PROPERTY_POWER} {OFF}":
                if self._power_on_off_future is None:
                    _LOGGER.debug(
                        "_update_property: Creating _power_on_off_future for cooldown"
                    )
                    self._power_on_off_future = asyncio.Future()
                self._update_property(PROPERTY_POWER, STATE_COOLDOWN)

            if not request.future.done():
                request.future.set_result(request.new_property_value)

    def _handle_err(self):
        request = self._pop_request()
        command = request.command if request else STATE_UNKNOWN
        error_message = f'Received error response for command="{command}"'
        _LOGGER.warning("_handle_err: %s", error_message)
        if request and not request.future.done():
            request.future.set_exception(ProjectorErrorResponse(error_message))

    async def _handle_imevent(self, value):
        # Event from projector
        parts = value.split(" ")
        _LOGGER.debug('_handle_imevent: imevent value="%s"', value)

        if len(parts) < 2:
            _LOGGER.warning("_handle_imevent: Value unexpectedly only has 2 parts.")

        if len(parts) >= 3:
            warning_bitmask = hex_string_to_int(parts[2])
            for bit, warning in IMEVENT_WARNING_BIT_MAP.items():
                if (warning_bitmask & (1 << bit)) > 0:
                    _LOGGER.warning('_handle_imevent: imevent warning="%s"', warning)

        power_code = hex_string_to_int(parts[1])
        if power_code == IMEVENT_STATUS_CODE_ABNORMAL:
            if len(parts) < 4:
                _LOGGER.warning(
                    "_handle_imevent: Value unexpectedly has less than 4 parts."
                )
                return
            _LOGGER.error(
                "_handle_imevent: imevent abnormal power code. Alarm Bitmask=%s",
                parts[3],
            )
            alarm_bitmask = hex_string_to_int(parts[3])
            errors = []
            for bit, alarm in IMEVENT_ALARM_BIT_MAP.items():
                if (alarm_bitmask & (1 << bit)) > 0:
                    _LOGGER.error('_handle_imevent: imevent alarm="%s"', alarm)
                    errors.append(alarm)
            if len(errors) > 0:
                self._has_errors = True
                self._update_property(PROPERTY_ERR, ", ".join(errors))
        else:
            power = IMEVENT_STATUS_CODE_TO_POWER_MAP.get(power_code)
            if power is None:
                _LOGGER.warning(
                    '_handle_imevent: unsupported power_code="%s"', power_code
                )
            else:
                self._update_property(PROPERTY_POWER, power)

    def _handle_property(self, prop, value):
        _LOGGER.debug('_handle_property: prop=%s value="%s"', prop, value)
        request = self._pop_request()
        parser = PROPERTY_PARSER_MAP.get(prop)
        if parser is not None:
            try:
                parsed_value = parser(value)
                if parsed_value is None:
                    value = STATE_UNKNOWN
                    _LOGGER.error(
                        '_handle_property: prop=%s has unknown value="%s"',
                        prop,
                        value,
                    )
                value = parsed_value
            except Exception as err:
                _LOGGER.error(
                    '_handle_property: Error parsing prop=%s, value="%s", %s',
                    prop,
                    value,
                    err,
                )
                if request and not request.future.done():
                    request.future.set_exception(err)
        if request and not request.future.done():
            request.future.set_result(value)
        self._update_property(prop, value)

    def _update_property(self, prop, value):
        _LOGGER.debug("_update_property: prop=%s, value=%s", prop, value)
        if prop == PROPERTY_POWER:
            # Sometimes power response for cooldown / warmup is a little late.
            # Ignore if the value is already on/off
            if (self._power_state == STATE_OFF and value == STATE_COOLDOWN) or (
                self._power_state == STATE_ON and value == STATE_WARMUP
            ):
                return

            self._power_state = value
            if value == STATE_OFF or value == STATE_ON:
                if (
                    self._power_on_off_future is not None
                    and not self._power_on_off_future.done()
                ):
                    _LOGGER.debug("_update_property: Resolving _power_on_off_future")
                    self._power_on_off_future.set_result(value)
                self._power_on_off_future = None
                if self._has_errors:
                    self._has_errors = False
                    self._update_property(PROPERTY_ERR, None)
        if self._callback:
            self._create_task(self._create_callback_task(self._callback, prop, value))

    # Callback may not be async, so should wrap it in async function
    async def _create_callback_task(self, callback, prop, value):
        value = callback(prop, value)
        if inspect.iscoroutine(value):
            await value

    def _create_task(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _pop_request(self):
        if len(self._request_queue) > 0:
            return self._request_queue.popleft()

        _LOGGER.error("_pop_request: Request queue is unexpectedly empty")
        return None


class Request:
    """
    Request for projector
    """

    def __init__(self, command, new_property_value=None):
        self.command = command
        self.new_property_value = new_property_value
        self.future = asyncio.Future()
