"""The epson integration."""

import asyncio
import logging

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .projector import Projector

PLATFORMS = [MEDIA_PLAYER_PLATFORM]

_LOGGER = logging.getLogger(__name__)


def create_projector(data):
    return Projector(
        host=data[CONF_HOST],
    )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up epson from a config entry."""
    projector = create_projector(config_entry.data)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = projector

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update options."""
    if config_entry.data == config_entry.options:
        _LOGGER.debug(
            "update_listener: No changes in options for %s", config_entry.entry_id
        )
        return

    _LOGGER.debug(
        "update_listener: Updating options and reloading %s", config_entry.entry_id
    )
    hass.config_entries.async_update_entry(
        entry=config_entry,
        data=config_entry.options.copy(),
    )
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unloaded
