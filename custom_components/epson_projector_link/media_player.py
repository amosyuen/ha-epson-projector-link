"""Support for Epson projector."""
import asyncio
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.media_player import DEVICE_CLASS_TV
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_PLATFORM
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import SUPPORT_SELECT_SOURCE
from homeassistant.components.media_player.const import SUPPORT_TURN_OFF
from homeassistant.components.media_player.const import SUPPORT_TURN_ON
from homeassistant.components.media_player.const import SUPPORT_VOLUME_SET
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.event import async_track_time_interval

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
from .const import SERVICE_SET_BRIGHTNESS
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
from .projector.const import PROPERTY_MUTE
from .projector.const import PROPERTY_POWER
from .projector.const import PROPERTY_POWER_CONSUMPTION_MODE
from .projector.const import PROPERTY_SOURCE
from .projector.const import PROPERTY_SOURCE_LIST
from .projector.const import PROPERTY_VOLUME
from .projector.const import SOURCE_CODE_INVERTED_MAP

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


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload Epson Projector Home Cinema entry."""
    _LOGGER.debug("async_unload_entry: entry_id=%s", config_entry.entry_id)
    registry = async_get_entity_registry(hass)
    entity_id = registry.async_get_entity_id(
        MEDIA_PLAYER_PLATFORM, DOMAIN, config_entry.entry_id
    )
    projector_entity = registry.async_get(entity_id)
    projector_entity.unload()

    return True


PROPERTY_TO_FEATURE_MAP = {
    PROPERTY_SOURCE: SUPPORT_SELECT_SOURCE,
    PROPERTY_VOLUME: SUPPORT_VOLUME_SET,
}


def _get_supported_features(properties):
    features = (
        SUPPORT_TURN_OFF
        | SUPPORT_TURN_ON
        # Technically supported, but disabled since it just proxies to the playing device
        # | SUPPORT_PAUSE
        # | SUPPORT_PLAY
        # | SUPPORT_STOP
        # | SUPPORT_NEXT_TRACK
        # | SUPPORT_PREVIOUS_TRACK
        # | SUPPORT_VOLUME_MUTE
        # | SUPPORT_VOLUME_STEP  # Some projectors can step volume even if they can't read volume
    )

    for prop in properties:
        additional_features = PROPERTY_TO_FEATURE_MAP.get(prop)
        if additional_features is not None:
            features |= additional_features

    return features


def _to_hex(integer):
    return "%0.2X" % integer


class EpsonProjectorMediaPlayer(MediaPlayerEntity):
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
        self._attr_device_class = DEVICE_CLASS_TV
        self._attr_extra_state_attributes = {}
        self._attr_should_poll = False  # We do our own polling based on config setting
        self._attr_source_list = None
        self._attr_state = None
        self._attr_supported_features = _get_supported_features(poll_properties)

        projector.set_callback(self._callback)

        unregister_callbacks = []
        if scan_interval_power is not None:

            async def get_power_update(now):
                _LOGGER.debug("get_power_update:")
                return await self.async_get_power()

            unregister_callbacks.append(
                async_track_time_interval(
                    hass,
                    # self.async_get_power,
                    get_power_update,
                    scan_interval_power,
                )
            )

        if scan_interval_properties is not None and len(poll_properties) > 0:

            def update_attributes(now):
                _LOGGER.debug("update_attributes:")
                return self.update_additional_attributes()

            unregister_callbacks.append(
                async_track_time_interval(
                    hass,
                    # self.update_additional_attributes,
                    update_attributes,
                    scan_interval_properties,
                )
            )
        self._unregister_callbacks = unregister_callbacks

    def unload(self):
        """Unload projector entity."""
        for callback in self._unregister_callbacks:
            callback()
        self._unregister_callbacks.clear()

    async def async_update(self):
        """Update state."""
        _LOGGER.debug("async_update: unique_id=%s", self._config_entry.unique_id)
        await self.async_get_power()

    # now param is to allow callback to work
    async def async_get_power(self, now=None):
        try:
            self._attr_state = await self._projector.get_property(PROPERTY_POWER)
            return self._attr_state
        except asyncio.TimeoutError:
            async_call_later(
                self.hass, POWER_TIMEOUT_RETRY_INTERVAL, self.async_get_power
            )
        except Exception as err:
            _LOGGER.debug("async_get_power: Error getting power error=%s", err)
            self._attr_available = False
            raise

    # now param is to allow callback to work
    def update_additional_attributes(self, now=None):
        """Poll additional attributes"""
        if PROPERTY_SOURCE in self._poll_properties:
            self.hass.create_task(self.async_try_get_property(PROPERTY_SOURCE_LIST))

        if self._attr_state == STATE_ON:
            for prop in self._poll_properties:
                self.hass.create_task(self.async_try_get_property(prop))

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
        selected_source = SOURCE_CODE_INVERTED_MAP[source]
        await self._projector.set_property(PROPERTY_SOURCE, selected_source)

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
