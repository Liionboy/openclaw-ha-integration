"""Config flow for OpenClaw Agent integration."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .api_client import OpenClawAPI
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
    CONF_AGENT_NAME,
    DEFAULT_PORT,
    DEFAULT_AGENT_NAME,
)

_LOGGER = logging.getLogger(__name__)


class OpenClawConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenClaw Agent."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step — manual configuration."""
        errors = {}

        if user_input is not None:
            # Validate connection
            api = OpenClawAPI(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
                token=user_input[CONF_TOKEN],
                use_ssl=user_input.get(CONF_USE_SSL, False),
                verify_ssl=user_input.get(CONF_VERIFY_SSL, True),
            )

            health = await api.health_check()
            await api.close()

            if health:
                return self.async_create_entry(
                    title=f"OpenClaw ({user_input.get(CONF_AGENT_NAME, DEFAULT_AGENT_NAME)})",
                    data=user_input,
                )
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Required(CONF_TOKEN): str,
                vol.Optional(CONF_USE_SSL, default=False): cv.boolean,
                vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
                vol.Optional(CONF_AGENT_NAME, default=DEFAULT_AGENT_NAME): str,
            }),
            errors=errors,
        )
