"""Conversation agent for Home Assistant Assist."""

import logging
from typing import Any

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AbstractConversationAgent,
    ConversationInput,
    ConversationResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .api_client import OpenClawAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OpenClawConversationAgent(AbstractConversationAgent):
    """Conversation agent that proxies to OpenClaw."""

    def __init__(self, hass: HomeAssistant, api: OpenClawAPI) -> None:
        """Initialize the agent."""
        self.hass = hass
        self._api = api
        self._supported_languages = ["*"]  # OpenClaw handles language detection

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return self._supported_languages

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a conversation turn via OpenClaw."""
        try:
            # Build context with exposed HA entities
            context_text = await self._build_context()

            message = user_input.text
            if context_text:
                message = f"[HA Context]\n{context_text}\n\n{message}"

            response = await self._api.send_message(
                message=message,
                session_id=f"ha-{user_input.conversation_id}",
            )

            if response and "choices" in response:
                reply = response["choices"][0]["message"]["content"]
            else:
                reply = "Sorry, I couldn't reach the OpenClaw gateway."

            # Fire event for automations
            self.hass.bus.async_fire(
                f"{DOMAIN}_message_received",
                {
                    "user_message": user_input.text,
                    "response": reply,
                    "conversation_id": user_input.conversation_id,
                },
            )

            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(reply)

            return ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )

        except Exception:
            _LOGGER.exception("Error processing conversation")
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(
                "An error occurred while processing your request."
            )
            return ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )

    async def _build_context(self) -> str:
        """Build a text context of exposed HA entities for the agent."""
        context_lines = []
        try:
            states = self.hass.states.async_all()
            for state in states:
                # Include entity_id and state for context
                attributes_str = ""
                if state.attributes.get("friendly_name"):
                    attributes_str = f" ({state.attributes['friendly_name']})"
                context_lines.append(f"- {state.entity_id}: {state.state}{attributes_str}")
        except Exception:
            pass

        if context_lines:
            return "Home Assistant Entities:\n" + "\n".join(context_lines[:200])
        return ""
