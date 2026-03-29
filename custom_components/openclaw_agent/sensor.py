"""Sensors for OpenClaw Agent integration."""

import logging
from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_AGENT_NAME
from .api_client import OpenClawAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OpenClaw sensors from a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    agent_name = entry.data.get(CONF_AGENT_NAME, "Jarvis")

    sensors = [
        OpenClawStatusSensor(api, entry, agent_name),
        OpenClawModelSensor(api, entry, agent_name),
        OpenClawUptimeSensor(api, entry, agent_name),
        OpenClawLastMessageSensor(api, entry, agent_name),
    ]
    async_add_entities(sensors, update_before_add=True)


class OpenClawBaseSensor(SensorEntity):
    """Base sensor for OpenClaw."""

    def __init__(self, api: OpenClawAPI, entry: ConfigEntry, agent_name: str) -> None:
        """Initialize."""
        self._api = api
        self._entry = entry
        self._agent_name = agent_name
        self._attr_unique_id = f"{entry.entry_id}_{self._sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"OpenClaw ({agent_name})",
            "manufacturer": "OpenClaw",
            "model": "Gateway",
            "sw_version": "1.0.0",
        }

    @property
    def _sensor_type(self) -> str:
        raise NotImplementedError

    @property
    def name(self) -> str:
        return f"OpenClaw {self._sensor_type.replace('_', ' ').title()}"


class OpenClawStatusSensor(OpenClawBaseSensor):
    """Gateway connection status."""

    _sensor_type = "status"
    _attr_icon = "mdi:robot-happy"

    async def async_update(self) -> None:
        data = await self._api.health_check()
        self._attr_native_value = "online" if data else "offline"


class OpenClawModelSensor(OpenClawBaseSensor):
    """Current model info."""

    _sensor_type = "model"
    _attr_icon = "mdi:brain"

    async def async_update(self) -> None:
        data = await self._api.get_status()
        if data:
            self._attr_native_value = data.get("model", "unknown")
            self._attr_extra_state_attributes = {
                "provider": data.get("provider", "unknown"),
                "fallbacks": data.get("fallbacks", []),
            }
        else:
            self._attr_native_value = STATE_UNAVAILABLE


class OpenClawUptimeSensor(OpenClawBaseSensor):
    """Gateway uptime."""

    _sensor_type = "uptime"
    _attr_icon = "mdi:clock-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "minutes"

    async def async_update(self) -> None:
        data = await self._api.get_status()
        if data and "uptime" in data:
            self._attr_native_value = data["uptime"]
        else:
            self._attr_native_value = STATE_UNAVAILABLE


class OpenClawLastMessageSensor(OpenClawBaseSensor):
    """Last message processed."""

    _sensor_type = "last_message"
    _attr_icon = "mdi:message-text"

    def __init__(self, api, entry, agent_name):
        super().__init__(api, entry, agent_name)
        self._last_user = None
        self._last_response = None
        self._last_time = None

    @property
    def native_value(self) -> str | None:
        return self._last_response[:100] if self._last_response else None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "user_message": self._last_user,
            "full_response": self._last_response,
            "timestamp": self._last_time,
        }

    async def async_update(self) -> None:
        # Listen to events
        @callback
        def _on_message(event):
            self._last_user = event.data.get("user_message")
            self._last_response = event.data.get("response")
            self._last_time = datetime.now().isoformat()
            self.async_write_ha_state()

        self.hass.bus.async_listen(f"{DOMAIN}_message_received", _on_message)
