"""Adds config flow for Epson Projector Link."""

import asyncio
import logging

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.const import STATE_ON
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from . import create_projector
from .const import CONF_POLL_PROPERTIES
from .const import CONF_PROPERTIES_SCAN_INTERVAL
from .const import DEFAULT_POWER_SCAN_INTERVAL
from .const import DEFAULT_PROPERTIES_SCAN_INTERVAL
from .const import DOMAIN
from .const import PROPERTY_TO_ATTRIBUTE_NAME_MAP
from .projector.const import PROPERTY_POWER
from .projector.const import PROPERTY_SERIAL_NUMBER
from .projector.exceptions import ProjectorErrorResponse

_LOGGER = logging.getLogger(__name__)


def _snake_to_title_words(string):
    return " ".join(word.title() for word in string.split("_"))


PROPERTY_SELECT_OPTIONS = {
    k: _snake_to_title_words(v) for k, v in PROPERTY_TO_ATTRIBUTE_NAME_MAP.items()
}


def _create_options_schema(user_input, is_config):
    if user_input is None:
        user_input = {}

    schema = {}
    if is_config:
        schema.update(
            {
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, DOMAIN)): str,
            }
        )

    schema.update(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=user_input.get(CONF_SCAN_INTERVAL, DEFAULT_POWER_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),
            vol.Optional(
                CONF_PROPERTIES_SCAN_INTERVAL,
                default=user_input.get(
                    CONF_PROPERTIES_SCAN_INTERVAL, DEFAULT_PROPERTIES_SCAN_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                CONF_POLL_PROPERTIES, default=user_input.get(CONF_POLL_PROPERTIES, [])
            ): cv.multi_select(PROPERTY_SELECT_OPTIONS),
        }
    )
    return vol.Schema(schema)


async def _async_get_property(projector, property, errors={}):
    try:
        return await projector.get_property(property)
    except ProjectorErrorResponse as e:
        attribute_name = PROPERTY_TO_ATTRIBUTE_NAME_MAP[property]
        if attribute_name:
            errors["base"] = f"property_error_{attribute_name}"
        else:
            # This shouldn't happen unless projector in some error state
            _LOGGER.exception("_async_get_property: Unsupported property: %s", e)
            errors["base"] = "cannot_connect"
    except asyncio.TimeoutError:
        errors["base"] = "cannot_find_projector"
    except Exception as e:
        _LOGGER.exception("_async_get_property: Unable to connect error: %s", e)
        errors["base"] = "cannot_connect"


async def _async_validate_additional_properties(projector, properties, errors={}):
    if len(properties) == 0:
        return

    state = await _async_get_property(projector, PROPERTY_POWER, errors)
    if len(errors) > 0:
        return

    if state != STATE_ON:
        errors["base"] = "projector_off"
        return

    for property in properties:
        await _async_get_property(projector, property, errors)
        if len(errors) > 0:
            return


class EpsonProjectorLinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for epson_projector_link."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            projector = create_projector(user_input)

            # Abort if existing project with same serial number
            serial_no = await _async_get_property(
                projector, PROPERTY_SERIAL_NUMBER, errors
            )
            if len(errors) == 0:
                await self.async_set_unique_id(serial_no)
                self._abort_if_unique_id_configured()

                if len(errors) == 0:
                    # Validate additional properties
                    await _async_validate_additional_properties(
                        projector, user_input.get(CONF_POLL_PROPERTIES), errors
                    )

                    if len(errors) == 0:
                        return self.async_create_entry(
                            title=user_input.pop(CONF_NAME), data=user_input
                        )

        return self.async_show_form(
            step_id="user",
            data_schema=_create_options_schema(user_input, is_config=True),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EpsonProjectorLinkOptionsFlowHandler(config_entry)


class EpsonProjectorLinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for epson_projector_link."""

    def __init__(self, config_entry):
        """Initialize."""
        self._original_data = dict(config_entry.data)
        self._data = dict(config_entry.data)

    async def async_step_init(self, user_input=None):
        """Manage Options."""
        errors = {}
        if user_input is not None:
            self._data.update(user_input)

            # Validate additional properties
            old_properties = self._original_data.get(CONF_POLL_PROPERTIES)
            new_properties = self._data.get(CONF_POLL_PROPERTIES)
            if new_properties != old_properties:
                projector = create_projector(self._data)
                await _async_validate_additional_properties(
                    projector, user_input.get(CONF_POLL_PROPERTIES), errors
                )

            if len(errors) == 0:
                return self.async_create_entry(title="", data=self._data)

        return self.async_show_form(
            step_id="init",
            data_schema=_create_options_schema(self._data, is_config=False),
            errors=errors,
        )
