"""OpenClaw Agent integration for Home Assistant."""

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api_client import OpenClawAPI
from .config_editor import ConfigEditor
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the OpenClaw Agent component (YAML path)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenClaw Agent from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = OpenClawAPI(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        token=entry.data[CONF_TOKEN],
        use_ssl=entry.data.get(CONF_USE_SSL, False),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
    )

    config_editor = ConfigEditor(str(hass.config.config_dir))

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "config_editor": config_editor,
    }

    # Set up services
    await async_setup_services(hass, api, config_editor)

    # Set up platforms (sensors)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register conversation agent
    from .agent import OpenClawConversationAgent

    agent = OpenClawConversationAgent(hass, api)
    conversation.async_set_agent(hass, entry, agent)
    _LOGGER.info("OpenClaw conversation agent registered")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["api"].close()

    return unload_ok


# Need this import at the bottom to avoid circular import at module level
from homeassistant.components import conversation
