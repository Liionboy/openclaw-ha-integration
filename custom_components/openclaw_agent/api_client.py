"""OpenClaw gateway API client for Home Assistant."""

import asyncio
import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Counter for unique WebSocket message IDs
_ws_msg_id = 0


class OpenClawAPI:
    """Client for the OpenClaw gateway HTTP/WebSocket API."""

    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the API client."""
        self._host = host
        self._port = port
        self._token = token
        self._use_ssl = use_ssl
        self._verify_ssl = verify_ssl
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_responses: dict[str, asyncio.Future] = {}
        self._ws_listen_task: asyncio.Task | None = None

    @property
    def base_url(self) -> str:
        """Return the base URL for the gateway."""
        scheme = "https" if self._use_ssl else "http"
        return f"{scheme}://{self._host}:{self._port}"

    @property
    def headers(self) -> dict[str, str]:
        """Return common headers."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                ssl=self._verify_ssl if self._use_ssl else False
            )
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self) -> None:
        """Close all connections."""
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._ws_listen_task and not self._ws_listen_task.done():
            self._ws_listen_task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        """Make an HTTP request to the gateway."""
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        try:
            async with session.request(
                method, url, headers=self.headers, **kwargs
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                _LOGGER.error(
                    "API request failed: %s %s -> %s", method, url, resp.status
                )
                text = await resp.text()
                _LOGGER.error("Response: %s", text)
                return None
        except Exception:
            _LOGGER.exception("API request error: %s %s", method, url)
            return None

    # ── Health & Status ──────────────────────────────────────────

    async def health_check(self) -> dict[str, Any] | None:
        """Check gateway health."""
        return await self._request("GET", "/health")

    async def get_status(self) -> dict[str, Any] | None:
        """Get gateway status from health endpoint."""
        data = await self._request("GET", "/health")
        if data and data.get("ok"):
            return {"status": data.get("status", "live")}
        return None

    # ── WebSocket Connection ─────────────────────────────────────

    async def _ensure_ws(self) -> aiohttp.ClientWebSocketResponse:
        """Ensure we have an active WebSocket connection."""
        if self._ws is not None and not self._ws.closed:
            return self._ws

        scheme = "wss" if self._use_ssl else "ws"
        url = f"{scheme}://{self._host}:{self._port}/__openclaw__/ws"

        ssl_ctx = None
        if self._use_ssl:
            import ssl as ssl_module
            ssl_ctx = ssl_module.create_default_context()
            if not self._verify_ssl:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl_module.CERT_NONE

        session = await self._get_session()
        self._ws = await session.ws_connect(url, headers=self.headers, ssl=ssl_ctx)

        # Start listener task
        self._ws_listen_task = asyncio.create_task(self._ws_listener())

        _LOGGER.info("WebSocket connected to %s", url)
        return self._ws

    async def _ws_listener(self) -> None:
        """Listen for WebSocket responses and resolve futures."""
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        msg_id = data.get("id")
                        if msg_id and msg_id in self._ws_responses:
                            future = self._ws_responses.pop(msg_id)
                            if not future.done():
                                future.set_result(data)
                        else:
                            _LOGGER.debug("WS message (no pending): %s", str(data)[:200])
                    except json.JSONDecodeError:
                        _LOGGER.debug("WS non-JSON: %s", msg.data[:200])
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", self._ws.exception())
                    break
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING):
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            _LOGGER.exception("WebSocket listener error")
        finally:
            self._ws = None
            # Resolve any pending futures with error
            for msg_id, future in self._ws_responses.items():
                if not future.done():
                    future.set_result({"error": "websocket_disconnected"})
            self._ws_responses.clear()

    async def _ws_send_and_wait(
        self, payload: dict, timeout: float = 60
    ) -> dict[str, Any]:
        """Send a message over WebSocket and wait for response."""
        global _ws_msg_id
        _ws_msg_id += 1
        msg_id = f"ha_{_ws_msg_id}"
        payload["id"] = msg_id

        ws = await self._ensure_ws()

        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._ws_responses[msg_id] = future

        await ws.send_json(payload)

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._ws_responses.pop(msg_id, None)
            return {"error": "timeout", "message": "No response from gateway"}
        except Exception as e:
            self._ws_responses.pop(msg_id, None)
            return {"error": str(e)}

    # ── Chat (via WebSocket) ─────────────────────────────────────

    async def send_message(
        self,
        message: str,
        session_id: str = "default",
        model: str | None = None,
        agent_id: str = "main",
    ) -> dict[str, Any]:
        """Send a message to the agent via WebSocket."""
        payload = {
            "type": "agent.chat",
            "data": {
                "message": message,
                "sessionKey": f"ha:{session_id}",
                "agentId": agent_id,
            },
        }
        if model:
            payload["data"]["model"] = model

        try:
            result = await self._ws_send_and_wait(payload, timeout=120)
        except Exception as e:
            _LOGGER.error("WebSocket send_message failed: %s", e)
            return {"error": str(e)}

        if "error" in result:
            _LOGGER.error("Agent chat error: %s", result["error"])
            return result

        # Normalize response format
        if "choices" in result:
            return result
        if "data" in result and "response" in result["data"]:
            return {"choices": [{"message": {"content": result["data"]["response"]}}]}
        if "data" in result and "message" in result["data"]:
            return {"choices": [{"message": {"content": result["data"]["message"]}}]}

        # Return raw if format unknown
        _LOGGER.warning("Unknown WS response format: %s", str(result)[:300])
        return result
