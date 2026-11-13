"""Support for Epson projector."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import ATTR_INPUT_SOURCE_LIST
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
import voluptuous as vol

from .const import CONF_POLL_PROPERTIES
from .const import CONF_PROPERTIES_SCAN_INTERVAL
from .const import DOMAIN
from .const import POWER_TIMEOUT_RETRY_INTERVAL
from .const import PROPERTY_TO_ATTRIBUTE_NAME_MAP
from .const import SERVICE_LOAD_LENS_MEMORY
from .const import SERVICE_LOAD_PICTURE_MEMORY
from .const import SERVICE_SELECT_AUTO_IRIS_MODE
from .const import SERVICE_SELECT_COLOR_MODE
from .const import SERVICE_SELECT_POWER_CONSUMPTION_MODE
from .const import SERVICE_SEND_COMMAND
from .const import SERVICE_SET_BRIGHTNESS
from .const import STATE_ERROR
from .projector.const import AUTO_IRIS_MODE_CODE_INVERTED_MAP
from .projector.const import COLOR_MODE_CODE_INVERTED_MAP
from .projector.const import COMMAND_LOAD_LENS_MEMORY
from .projector.const import COMMAND_LOAD_PICTURE_MEMORY
from .projector.const import COMMAND_MEDIA_MUTE
from .projector.const import COMMAND_MEDIA_NEXT
from .projector.const import COMMAND_MEDIA_PAUSE
from .projector.const import COMMAND_MEDIA_PLAY
from .projector.const import COMMAND_MEDIA_PREVIOUS
from .projector.const import COMMAND_MEDIA_STOP
from .projector.const import COMMAND_MEDIA_VOL_DOWN
from .projector.const import COMMAND_MEDIA_VOL_UP
from .projector.const import OFF
from .projector.const import ON
from .projector.const import POWER_CONSUMPTION_MODE_CODE_INVERTED_MAP
from .projector.const import PROPERTY_AUTO_IRIS_MODE
from .projector.const import PROPERTY_BRIGHTNESS
from .projector.const import PROPERTY_COLOR_MODE
from .projector.const import PROPERTY_ERR
from .projector.const import PROPERTY_MUTE
from .projector.const import PROPERTY_POWER
from .projector.const import PROPERTY_POWER_CONSUMPTION_MODE
from .projector.const import PROPERTY_SOURCE
from .projector.const import PROPERTY_SOURCE_LIST
from .projector.const import PROPERTY_VOLUME
from .projector.const import SOURCE_CODE_INVERTED_MAP
from .projector.const import STATE_COOLDOWN
from .projector.const import STATE_WARMUP

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up the Epson projector from a config entry."""
    _LOGGER.debug("async_setup_entry: entry_id=%s", config_entry.entry_id)
    entry_id = config_entry.entry_id
    projector = hass.data[DOMAIN][entry_id]
    scan_interval_power = _to_time_delta_seconds(config_entry.data[CONF_SCAN_INTERVAL])
    scan_interval_properties = _to_time_delta_seconds(
        config_entry.data[CONF_PROPERTIES_SCAN_INTERVAL]
    )
    projector_entity = EpsonProjectorMediaPlayer(
        hass=hass,
        config_entry=config_entry,
        projector=projector,
        poll_properties=config_entry.data[CONF_POLL_PROPERTIES],
        scan_interval_power=scan_interval_power,
        scan_interval_properties=scan_interval_properties,
    )
    async_add_entities([projector_entity], True)

    _setup_services()


def _setup_services():
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_LOAD_LENS_MEMORY,
        {
            vol.Required("lens_memory_id"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=10)
            )
        },
        SERVICE_LOAD_LENS_MEMORY,
    )
    platform.async_register_entity_service(
        SERVICE_LOAD_PICTURE_MEMORY,
        {
            vol.Required("picture_memory_id"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=10)
            )
        },
        SERVICE_LOAD_PICTURE_MEMORY,
    )
    platform.async_register_entity_service(
        SERVICE_SELECT_AUTO_IRIS_MODE,
        {
            vol.Required(
                PROPERTY_TO_ATTRIBUTE_NAME_MAP[PROPERTY_AUTO_IRIS_MODE]
            ): vol.All(cv.string, vol.Any(*AUTO_IRIS_MODE_CODE_INVERTED_MAP.keys()))
        },
        SERVICE_SELECT_AUTO_IRIS_MODE,
    )
    platform.async_register_entity_service(
        SERVICE_SELECT_COLOR_MODE,
        {
            vol.Required(PROPERTY_TO_ATTRIBUTE_NAME_MAP[PROPERTY_COLOR_MODE]): vol.All(
                cv.string, vol.Any(*COLOR_MODE_CODE_INVERTED_MAP.keys())
            )
        },
        SERVICE_SELECT_COLOR_MODE,
    )
    platform.async_register_entity_service(
        SERVICE_SELECT_POWER_CONSUMPTION_MODE,
        {
            vol.Required(
                PROPERTY_TO_ATTRIBUTE_NAME_MAP[PROPERTY_POWER_CONSUMPTION_MODE]
            ): vol.All(
                cv.string, vol.Any(*POWER_CONSUMPTION_MODE_CODE_INVERTED_MAP.keys())
            )
        },
        SERVICE_SELECT_POWER_CONSUMPTION_MODE,
    )
    platform.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {vol.Required("command"): str},
        SERVICE_SEND_COMMAND,
    )
    platform.async_register_entity_service(
        SERVICE_SET_BRIGHTNESS,
        {
            vol.Required(PROPERTY_TO_ATTRIBUTE_NAME_MAP[PROPERTY_BRIGHTNESS]): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        SERVICE_SET_BRIGHTNESS,
    )


def _to_time_delta_seconds(scan_interval):
    return (
        timedelta(seconds=scan_interval)
        if isinstance(scan_interval, int)
        else scan_interval
    )


PROPERTY_TO_FEATURE_MAP = {
    PROPERTY_SOURCE: MediaPlayerEntityFeature.SELECT_SOURCE,
    PROPERTY_VOLUME: MediaPlayerEntityFeature.VOLUME_SET,
}


def _get_supported_features(properties):
    features = (
        MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.TURN_ON
        # Technically supported, but disabled since it just proxies to the playing device
        # | MediaPlayerEntityFeature.PAUSE
        # | MediaPlayerEntityFeature.PLAY
        # | MediaPlayerEntityFeature.STOP
        # | MediaPlayerEntityFeature.NEXT_TRACK
        # | MediaPlayerEntityFeature.PREVIOUS_TRACK
        # | MediaPlayerEntityFeature.VOLUME_MUTE
        # | MediaPlayerEntityFeature.VOLUME_STEP  # Some projectors can step volume even if they can't read volume
    )

    for prop in properties:
        additional_features = PROPERTY_TO_FEATURE_MAP.get(prop)
        if additional_features is not None:
            features |= additional_features

    return features


def _to_hex(integer):
    return "%0.2X" % integer


class EpsonProjectorMediaPlayer(MediaPlayerEntity, RestoreEntity):
    """Representation of Epson Projector Home Cinema Device."""

    def __init__(
        self,
        hass,
        config_entry,
        projector,
        poll_properties,
        scan_interval_power,
        scan_interval_properties,
    ):
        """Initialize projector entity."""
        _LOGGER.debug("__init__: unique_id=%s", config_entry.unique_id)
        self._config_entry = config_entry
        self._projector = projector
        self._poll_properties = poll_properties

        self._attr_available = False
        self._attr_device_class = MediaPlayerDeviceClass.TV
        self._attr_extra_state_attributes = {
            PROPERTY_TO_ATTRIBUTE_NAME_MAP[PROPERTY_ERR]: None
        }
        self._attr_should_poll = False  # We do our own polling based on config setting
        self._attr_source_list = None
        self._attr_state = None
        self._attr_supported_features = _get_supported_features(poll_properties)
        self._attr_translation_key = "projector"

        self._scan_interval_power = scan_interval_power
        self._scan_interval_properties = scan_interval_properties
        self._unsub_power_retry = None

        projector.set_callback(self._callback)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Start polling only once the entity is added, and let Home Assistant
        # cancel the timers when the entity is removed (e.g. on reload).
        if self._scan_interval_power is not None:
            self.async_on_remove(
                async_track_time_interval(
                    self.hass,
                    self._async_get_power_callback,
                    self._scan_interval_power,
                )
            )

        if (
            self._scan_interval_properties is not None
            and len(self._poll_properties) > 0
        ):
            self.async_on_remove(
                async_track_time_interval(
                    self.hass,
                    self._update_additional_attributes_callback,
                    self._scan_interval_properties,
                )
            )

        # Restore old state
        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._attr_source_list = old_state.attributes.get(ATTR_INPUT_SOURCE_LIST)

            for attribute in PROPERTY_TO_ATTRIBUTE_NAME_MAP.values():
                value = old_state.attributes.get(attribute)
                if value is not None:
                    self._attr_extra_state_attributes[attribute] = value
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Cancel a pending power retry when the entity is removed."""
        self._cancel_power_retry()
        await super().async_will_remove_from_hass()

    async def async_update(self):
        """Update state."""
        _LOGGER.debug("async_update: unique_id=%s", self._config_entry.unique_id)
        await self.async_get_power()

    async def _async_get_power_callback(self, now=None):
        try:
            await self.async_get_power()
        except Exception:
            # Already logged in async_get_power. The projector is often
            # unreachable (e.g. no mains power), so do not raise from the timer.
            pass

    async def async_get_power(self):
        try:
            self._attr_state = await self._projector.get_property(PROPERTY_POWER)
            return self._attr_state
        except asyncio.TimeoutError:
            self._cancel_power_retry()
            self._unsub_power_retry = async_call_later(
                self.hass, POWER_TIMEOUT_RETRY_INTERVAL, self._async_power_retry
            )
        except Exception as err:
            _LOGGER.debug("async_get_power: Error getting power error=%s", err)
            self._attr_available = False
            raise

    async def _async_power_retry(self, now):
        self._unsub_power_retry = None
        await self._async_get_power_callback()

    def _cancel_power_retry(self):
        if self._unsub_power_retry is not None:
            self._unsub_power_retry()
            self._unsub_power_retry = None

    @callback
    def _update_additional_attributes_callback(self, now):
        self.update_additional_attributes()

    def update_additional_attributes(self):
        """Poll additional attributes"""
        if PROPERTY_SOURCE in self._poll_properties and self._attr_source_list is None:
            self.hass.async_create_task(
                self.async_try_get_property(PROPERTY_SOURCE_LIST)
            )

        if self._attr_state == STATE_ON:
            for prop in self._poll_properties:
                # Avoid double pulling the source list
                if prop != PROPERTY_SOURCE:
                    self.hass.async_create_task(self.async_try_get_property(prop))

    async def async_try_get_property(self, prop):
        try:
            return await self._projector.get_property(prop)
        except Exception as err:
            _LOGGER.warning(
                "async_try_get_property: unique_id=%s: Error getting property=%s. Projector may not support it: %s",
                self._config_entry.unique_id,
                prop,
                err,
            )

    @property
    def device_info(self):
        """Get attributes about the device."""
        if not self._attr_unique_id:
            return None
        return {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "manufacturer": "Epson",
            "name": "Epson Projector Home Cinema",
            "model": "Epson",
            "via_hub": (DOMAIN, self._attr_unique_id),
        }

    @property
    def name(self):
        """Get name for the entity."""
        return self._config_entry.title

    @property
    def unique_id(self):
        """Get unique ID for the entity."""
        return self._config_entry.unique_id

    async def async_turn_on(self):
        await self._projector.set_property(PROPERTY_POWER, ON)

    async def async_turn_off(self):
        await self._projector.set_property(PROPERTY_POWER, OFF)

    async def async_select_source(self, source):
        source_code = SOURCE_CODE_INVERTED_MAP.get(source)
        if source_code is None:
            source_code = source
        await self._projector.set_property(PROPERTY_SOURCE, source_code)

    async def async_set_volume_level(self, volume):
        await self._projector.set_property(PROPERTY_VOLUME, int(volume * 100))

    async def async_mute_volume(self, mute):
        if (
            PROPERTY_TO_ATTRIBUTE_NAME_MAP[PROPERTY_MUTE]
            in self._attr_extra_state_attributes
        ):
            # Projector supports mute state
            await self._projector.set_property(PROPERTY_MUTE, ON if mute else OFF)
        else:
            # In this case we don't know the current mute state so this is a toggle
            await self._projector.send_command(COMMAND_MEDIA_MUTE)

    async def async_volume_up(self):
        await self._projector.send_command(COMMAND_MEDIA_VOL_UP)

    async def async_volume_down(self):
        await self._projector.send_command(COMMAND_MEDIA_VOL_DOWN)

    async def async_media_pause(self):
        await self._projector.send_command(COMMAND_MEDIA_PAUSE)

    async def async_media_play(self):
        await self._projector.send_command(COMMAND_MEDIA_PLAY)

    async def async_media_stop(self):
        await self._projector.send_command(COMMAND_MEDIA_STOP)

    async def async_media_next_track(self):
        await self._projector.send_command(COMMAND_MEDIA_NEXT)

    async def async_media_previous_track(self):
        await self._projector.send_command(COMMAND_MEDIA_PREVIOUS)

    #
    # Custom Services
    #

    async def load_lens_memory(self, lens_memory_id):
        await self._projector.send_command(
            COMMAND_LOAD_LENS_MEMORY, _to_hex(lens_memory_id)
        )

    async def load_picture_memory(self, picture_memory_id):
        await self._projector.send_command(
            # 02 is for MEMORY Type
            COMMAND_LOAD_PICTURE_MEMORY,
            f"02 {_to_hex(picture_memory_id)}",
        )

    async def select_auto_iris_mode(self, auto_iris_mode):
        await self._projector.set_property(
            PROPERTY_AUTO_IRIS_MODE, AUTO_IRIS_MODE_CODE_INVERTED_MAP[auto_iris_mode]
        )

    async def select_color_mode(self, color_mode):
        await self._projector.set_property(
            PROPERTY_COLOR_MODE, COLOR_MODE_CODE_INVERTED_MAP[color_mode]
        )

    async def select_power_consumption_mode(self, power_consumption_mode):
        await self._projector.set_property(
            PROPERTY_POWER_CONSUMPTION_MODE,
            POWER_CONSUMPTION_MODE_CODE_INVERTED_MAP[power_consumption_mode],
        )

    async def set_brightness(self, brightness):
        await self._projector.set_property(PROPERTY_BRIGHTNESS, brightness)

    async def send_command(self, command):
        await self._projector.send_command(command)

    def _callback(self, prop, value):
        if prop == PROPERTY_POWER:
            return self._update_power(value)
        if prop == PROPERTY_SOURCE_LIST:
            self._attr_source_list = value
            return

        attribute_name = PROPERTY_TO_ATTRIBUTE_NAME_MAP.get(prop)
        if attribute_name is None:
            _LOGGER.warning(
                "_callback: unique_id=%s: Unsupported prop=%s value=%s",
                self._config_entry.unique_id,
                prop,
                value,
            )
            return

        _LOGGER.debug(
            "_callback: unique_id=%s: attr=%s, value=%s",
            self._config_entry.unique_id,
            attribute_name,
            value,
        )
        self._attr_extra_state_attributes[attribute_name] = value
        if prop == PROPERTY_ERR and (
            self._attr_state is STATE_WARMUP or self._attr_state is STATE_COOLDOWN
        ):
            self._attr_state = STATE_ERROR
        self._update_ha()

    def _update_power(self, value):
        prev_state = self._attr_state
        prev_available = self._attr_available
        self._attr_state = value
        self._attr_available = True
        _LOGGER.debug(
            "_update_power: unique_id=%s: value=%s, available=%s",
            self._config_entry.unique_id,
            self._attr_state,
            self._attr_available,
        )

        if self._attr_state == STATE_ON and (
            prev_state != STATE_ON or not prev_available
        ):
            self.update_additional_attributes()
        self._update_ha()

    def _update_ha(self):
        # Only update if we already set the entity id
        if self.entity_id is not None:
            self.async_schedule_update_ha_state()
