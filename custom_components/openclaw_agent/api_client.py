"""OpenClaw gateway API client for Home Assistant."""

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


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
            connector = aiohttp.TCPConnector(ssl=self._verify_ssl if self._use_ssl else False)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self) -> None:
        """Close the session."""
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
                _LOGGER.error("API request failed: %s %s -> %s", method, url, resp.status)
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
        """Get gateway status via models endpoint."""
        data = await self._request("GET", "/v1/models")
        if data:
            return {"model": "unknown", "provider": "unknown", "raw": data}
        return None

    # ── Chat / Completions (OpenAI-compatible) ───────────────────

    async def send_message(
        self,
        message: str,
        session_id: str = "default",
        model: str | None = None,
        agent_id: str = "main",
    ) -> dict[str, Any] | None:
        """Send a message via the OpenAI-compatible chat completions endpoint."""
        payload: dict[str, Any] = {
            "model": model or "default",
            "messages": [
                {"role": "user", "content": message},
            ],
            "stream": False,
            "metadata": {
                "sessionKey": f"ha:{session_id}",
                "agentId": agent_id,
            },
        }
        return await self._request(
            "POST", "/v1/chat/completions", json=payload
        )

    # ── WebSocket (for real-time events) ─────────────────────────

    async def create_websocket(self, on_message, on_disconnect=None):
        """Create a WebSocket connection to the gateway."""
        scheme = "wss" if self._use_ssl else "ws"
        url = f"{scheme}://{self._host}:{self._port}/__openclaw__/ws"

        ssl_ctx = None
        if self._use_ssl:
            import ssl
            ssl_ctx = ssl.create_default_context()
            if not self._verify_ssl:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

        try:
            session = await self._get_session()
            ws = await session.ws_connect(url, headers=self.headers, ssl=ssl_ctx)

            async def listen():
                try:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await on_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            _LOGGER.error("WebSocket error: %s", ws.exception())
                            break
                finally:
                    if on_disconnect:
                        await on_disconnect()

            asyncio.create_task(listen())
            return ws
        except Exception:
            _LOGGER.exception("Failed to create WebSocket")
            return None
