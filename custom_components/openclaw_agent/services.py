"""Home Assistant service registrations and handlers for OpenClaw Agent."""

import logging
from typing import Any

import voluptuous as vol
import yaml

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .api_client import OpenClawAPI
from .config_editor import ConfigEditor
from .const import (
    DOMAIN,
    ATTR_MESSAGE,
    ATTR_SESSION_ID,
    ATTR_MODEL,
    ATTR_RESPONSE,
    SERVICE_SEND_MESSAGE,
    SERVICE_CLEAR_HISTORY,
    SERVICE_RESTART_HA,
    SERVICE_EDIT_CONFIG,
    SERVICE_RELOAD_INTEGRATION,
    SERVICE_RUN_COMMAND,
    SERVICE_BACKUP_CONFIG,
    SERVICE_CHECK_CONFIG,
    EVENT_MESSAGE_RECEIVED,
    EVENT_COMMAND_RESULT,
)

_LOGGER = logging.getLogger(__name__)

# ── Schemas ──────────────────────────────────────────────────────

SEND_MESSAGE_SCHEMA = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_SESSION_ID, default="default"): cv.string,
    vol.Optional(ATTR_MODEL): cv.string,
})

EDIT_CONFIG_SCHEMA = vol.Schema({
    vol.Required("filename", default="configuration.yaml"): cv.string,
    vol.Required("content"): cv.string,
    vol.Optional("section"): cv.string,
    vol.Optional("backup", default=True): cv.boolean,
})

RELOAD_SCHEMA = vol.Schema({
    vol.Required("integration"): cv.string,
})

RUN_COMMAND_SCHEMA = vol.Schema({
    vol.Required("command"): cv.string,
    vol.Optional("timeout", default=30): cv.positive_int,
})

BACKUP_SCHEMA = vol.Schema({
    vol.Optional("filename"): cv.string,
})

CHECK_CONFIG_SCHEMA = vol.Schema({})

CLEAR_HISTORY_SCHEMA = vol.Schema({
    vol.Optional(ATTR_SESSION_ID, default="default"): cv.string,
})


async def async_setup_services(
    hass: HomeAssistant,
    api: OpenClawAPI,
    config_editor: ConfigEditor,
) -> None:
    """Register all OpenClaw Agent services."""

    # ── openclaw_agent.send_message ──────────────────────────────

    async def _handle_send_message(call: ServiceCall) -> None:
        message = call.data[ATTR_MESSAGE]
        session_id = call.data.get(ATTR_SESSION_ID, "default")
        model = call.data.get(ATTR_MODEL)

        response = await api.send_message(message, session_id, model)
        if response and "choices" in response:
            reply = response["choices"][0]["message"]["content"]
            hass.bus.async_fire(
                EVENT_MESSAGE_RECEIVED,
                {"user_message": message, "response": reply, "session_id": session_id},
            )
            call.data[ATTR_RESPONSE] = reply

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_MESSAGE, _handle_send_message, SEND_MESSAGE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    # ── openclaw_agent.clear_history ─────────────────────────────

    async def _handle_clear_history(call: ServiceCall) -> None:
        session_id = call.data.get(ATTR_SESSION_ID, "default")
        _LOGGER.info("Clearing history for session: %s", session_id)

    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_HISTORY, _handle_clear_history, CLEAR_HISTORY_SCHEMA,
    )

    # ── openclaw_agent.restart_homeassistant ─────────────────────

    async def _handle_restart_ha(call: ServiceCall) -> None:
        _LOGGER.warning("Restarting Home Assistant via OpenClaw Agent")
        await hass.services.async_call("homeassistant", "restart")

    hass.services.async_register(
        DOMAIN, SERVICE_RESTART_HA, _handle_restart_ha,
    )

    # ── openclaw_agent.edit_configuration ────────────────────────

    async def _handle_edit_config(call: ServiceCall) -> dict[str, Any]:
        filename = call.data.get("filename", "configuration.yaml")
        content = call.data["content"]
        section = call.data.get("section")
        backup = call.data.get("backup", True)

        try:
            if section:
                # Patch a specific section
                success = await config_editor.patch_file(filename, section, content)
            else:
                # Write entire file
                success = await config_editor.write_file(filename, content, backup)

            return {"success": success, "filename": filename}
        except Exception as e:
            _LOGGER.exception("Failed to edit config")
            return {"success": False, "error": str(e)}

    hass.services.async_register(
        DOMAIN, SERVICE_EDIT_CONFIG, _handle_edit_config, EDIT_CONFIG_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    # ── openclaw_agent.reload_integration ────────────────────────

    async def _handle_reload_integration(call: ServiceCall) -> None:
        integration = call.data["integration"]
        _LOGGER.info("Reloading integration: %s", integration)
        await hass.services.async_call("homeassistant", "reload_config_entry",
                                       {"integration": integration})

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD_INTEGRATION, _handle_reload_integration, RELOAD_SCHEMA,
    )

    # ── openclaw_agent.run_command ───────────────────────────────

    async def _handle_run_command(call: ServiceCall) -> dict[str, Any]:
        import asyncio
        command = call.data["command"]
        timeout = call.data.get("timeout", 30)

        _LOGGER.info("Running command: %s", command)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            result = {
                "return_code": proc.returncode,
                "stdout": stdout.decode()[:5000],
                "stderr": stderr.decode()[:5000],
                "success": proc.returncode == 0,
            }

            hass.bus.async_fire(EVENT_COMMAND_RESULT, {
                "command": command,
                "return_code": proc.returncode,
                "success": proc.returncode == 0,
            })

            return result
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    hass.services.async_register(
        DOMAIN, SERVICE_RUN_COMMAND, _handle_run_command, RUN_COMMAND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    # ── openclaw_agent.backup_configuration ──────────────────────

    async def _handle_backup_config(call: ServiceCall) -> dict[str, Any]:
        filename = call.data.get("filename")
        try:
            if filename:
                path = await config_editor.backup_file(filename)
            else:
                path = await config_editor.backup_all()
            return {"success": True, "backup_path": path}
        except Exception as e:
            _LOGGER.exception("Backup failed")
            return {"success": False, "error": str(e)}

    hass.services.async_register(
        DOMAIN, SERVICE_BACKUP_CONFIG, _handle_backup_config, BACKUP_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    # ── openclaw_agent.check_configuration ───────────────────────

    async def _handle_check_config(call: ServiceCall) -> dict[str, Any]:
        try:
            result = await config_editor.check_config()
            return {
                "valid": result["valid"],
                "output": result["output"][:5000],
                "errors": result["errors"][:5000],
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    hass.services.async_register(
        DOMAIN, SERVICE_CHECK_CONFIG, _handle_check_config, CHECK_CONFIG_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    _LOGGER.info("OpenClaw Agent services registered")
