"""Token refresh manager for the Aula integration."""

from __future__ import annotations

import asyncio
import ssl
import time
from typing import TYPE_CHECKING, Any

import httpx
from aula import AulaAuthenticationError, create_client
from aula.auth.exceptions import MitIDAuthError
from aula.auth.mitid_client import MitIDAuthClient
from aula.http_httpx import HttpxHttpClient

from .const import CONF_TOKEN_DATA, LOGGER

if TYPE_CHECKING:
    from aula import AulaApiClient
    from homeassistant.core import HomeAssistant

    from .data import AulaConfigEntry

_NO_REFRESH_TOKEN_MSG = "No refresh token available"  # noqa: S105


class AulaTokenManager:
    """Manages token refresh for the Aula integration."""

    def __init__(self, hass: HomeAssistant, entry: AulaConfigEntry) -> None:
        """Initialize the token manager."""
        self._hass = hass
        self._entry = entry
        self._lock = asyncio.Lock()

    async def async_refresh_token(self) -> tuple[AulaApiClient, dict[str, Any]]:
        """Refresh token and return a new client for setup-time use."""
        async with self._lock:
            token_data = self._entry.data[CONF_TOKEN_DATA]
            refresh_token = token_data.get("tokens", {}).get("refresh_token")
            if not refresh_token:
                raise AulaAuthenticationError(_NO_REFRESH_TOKEN_MSG, 0)

            new_token_data = await self._async_do_refresh(token_data, refresh_token)
            self._async_persist_token_data(new_token_data)
            client = await self._async_create_client(new_token_data)
            return client, new_token_data

    async def async_refresh_and_rebuild_client(self) -> AulaApiClient:
        """Refresh token, rebuild client, and update all coordinators."""
        async with self._lock:
            token_data = self._entry.data[CONF_TOKEN_DATA]
            expires_at = token_data.get("tokens", {}).get("expires_at")

            # Early exit: another waiter already refreshed
            if expires_at is not None and time.time() < expires_at:
                return self._entry.runtime_data.client

            refresh_token = token_data.get("tokens", {}).get("refresh_token")
            if not refresh_token:
                raise AulaAuthenticationError(_NO_REFRESH_TOKEN_MSG, 0)

            new_token_data = await self._async_do_refresh(token_data, refresh_token)
            self._async_persist_token_data(new_token_data)

            new_client = await self._async_create_client(new_token_data)

            old_client = self._entry.runtime_data.client
            self._entry.runtime_data.client = new_client
            self._update_coordinator_clients(new_client)

            await old_client.close()

            return new_client

    async def _async_do_refresh(
        self, token_data: dict[str, Any], refresh_token: str
    ) -> dict[str, Any]:
        """Perform the actual token refresh via MitIDAuthClient."""
        ssl_context = await self._hass.async_add_executor_job(
            ssl.create_default_context,
        )
        httpx_client = httpx.AsyncClient(
            verify=ssl_context,
            follow_redirects=False,
            timeout=30,
        )
        try:
            auth_client = MitIDAuthClient(
                mitid_username="",
                httpx_client=httpx_client,
            )
            new_tokens = await auth_client.refresh_access_token(refresh_token)
        except MitIDAuthError as err:
            msg = f"Token refresh failed: {err}"
            raise AulaAuthenticationError(msg, 0) from err
        finally:
            await httpx_client.aclose()

        username = token_data.get("username", "")
        cookies = token_data.get("cookies", {})
        return {
            "timestamp": time.time(),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "username": username,
            "tokens": new_tokens,
            "cookies": cookies,
        }

    async def _async_create_client(self, token_data: dict[str, Any]) -> AulaApiClient:
        """Create a new AulaApiClient from token data."""
        cookies = token_data.get("cookies", {})
        http_client = await self._hass.async_add_executor_job(HttpxHttpClient, cookies)
        try:
            return await create_client(token_data, http_client=http_client)
        except Exception:
            await http_client.close()
            raise

    def _async_persist_token_data(self, new_token_data: dict[str, Any]) -> None:
        """Persist updated token data to the config entry."""
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_TOKEN_DATA: new_token_data},
        )

    def _update_coordinator_clients(self, new_client: AulaApiClient) -> None:
        """Update the client reference on all coordinators."""
        for coord in self._entry.runtime_data.all_coordinators:
            coord.client = new_client
        LOGGER.debug("Updated all coordinator clients after token refresh")
