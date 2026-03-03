"""Tests for the AulaTokenManager."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aula import AulaAuthenticationError
from aula.auth.exceptions import OAuthError
from homeassistant.core import HomeAssistant

from custom_components.hass_aula.const import CONF_TOKEN_DATA
from custom_components.hass_aula.token_manager import AulaTokenManager

from .conftest import MOCK_TOKEN_DATA


def _make_entry(hass: HomeAssistant) -> MagicMock:
    """Create a mock config entry with token data."""
    entry = MagicMock()
    entry.data = {CONF_TOKEN_DATA: MOCK_TOKEN_DATA}
    entry.entry_id = "test_entry_id"

    # Mock hass.config_entries.async_update_entry
    hass.config_entries = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    return entry


def _make_refreshed_tokens() -> dict:
    """Create mock refreshed token response."""
    return {
        "token_type": "Bearer",
        "expires_in": 3600,
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_at": time.time() + 3600,
    }


async def test_async_refresh_token_success(hass: HomeAssistant) -> None:
    """Test successful token refresh returns new client and token data."""
    entry = _make_entry(hass)
    tm = AulaTokenManager(hass, entry)
    new_tokens = _make_refreshed_tokens()

    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.hass_aula.token_manager.MitIDAuthClient"
        ) as mock_auth_cls,
        patch("custom_components.hass_aula.token_manager.ssl.create_default_context"),
        patch(
            "custom_components.hass_aula.token_manager.httpx.AsyncClient"
        ) as mock_httpx,
        patch(
            "custom_components.hass_aula.token_manager.create_client",
            return_value=mock_client,
        ) as mock_create,
        patch("custom_components.hass_aula.token_manager.HttpxHttpClient"),
    ):
        mock_httpx_inst = AsyncMock()
        mock_httpx.return_value = mock_httpx_inst

        mock_auth = MagicMock()
        mock_auth.refresh_access_token = AsyncMock(return_value=new_tokens)
        mock_auth_cls.return_value = mock_auth

        client, token_data = await tm.async_refresh_token()

        assert client is mock_client
        assert token_data["tokens"] is new_tokens
        mock_auth.refresh_access_token.assert_called_once_with("mock_refresh_token")
        mock_create.assert_called_once()
        hass.config_entries.async_update_entry.assert_called_once()
        mock_httpx_inst.aclose.assert_called_once()


async def test_async_refresh_token_no_refresh_token(hass: HomeAssistant) -> None:
    """Test refresh raises when no refresh_token is available."""
    entry = _make_entry(hass)
    # Remove refresh_token from token data
    token_data_no_refresh = {
        **MOCK_TOKEN_DATA,
        "tokens": {
            "token_type": "Bearer",
            "access_token": "mock_access_token",
        },
    }
    entry.data = {CONF_TOKEN_DATA: token_data_no_refresh}
    tm = AulaTokenManager(hass, entry)

    with pytest.raises(AulaAuthenticationError, match="No refresh token"):
        await tm.async_refresh_token()


async def test_async_refresh_token_oauth_error(hass: HomeAssistant) -> None:
    """Test refresh raises AulaAuthenticationError on OAuthError."""
    entry = _make_entry(hass)
    tm = AulaTokenManager(hass, entry)

    with (
        patch(
            "custom_components.hass_aula.token_manager.MitIDAuthClient"
        ) as mock_auth_cls,
        patch("custom_components.hass_aula.token_manager.ssl.create_default_context"),
        patch(
            "custom_components.hass_aula.token_manager.httpx.AsyncClient"
        ) as mock_httpx,
    ):
        mock_httpx_inst = AsyncMock()
        mock_httpx.return_value = mock_httpx_inst

        mock_auth = MagicMock()
        mock_auth.refresh_access_token = AsyncMock(
            side_effect=OAuthError("Token expired")
        )
        mock_auth_cls.return_value = mock_auth

        with pytest.raises(AulaAuthenticationError, match="Token refresh failed"):
            await tm.async_refresh_token()

        mock_httpx_inst.aclose.assert_called_once()


async def test_async_refresh_and_rebuild_client(hass: HomeAssistant) -> None:
    """Test runtime refresh rebuilds client and updates coordinators."""
    entry = _make_entry(hass)

    # Set up runtime_data with coordinators
    old_client = AsyncMock()
    new_client = AsyncMock()

    presence_coord = MagicMock()
    calendar_coord = MagicMock()
    notifications_coord = MagicMock()
    all_coords = [presence_coord, calendar_coord, notifications_coord]
    runtime_data = MagicMock()
    runtime_data.client = old_client
    runtime_data.all_coordinators = all_coords
    entry.runtime_data = runtime_data

    # Ensure expires_at is in the past
    entry.data[CONF_TOKEN_DATA]["tokens"]["expires_at"] = time.time() - 100

    tm = AulaTokenManager(hass, entry)
    new_tokens = _make_refreshed_tokens()

    with (
        patch(
            "custom_components.hass_aula.token_manager.MitIDAuthClient"
        ) as mock_auth_cls,
        patch("custom_components.hass_aula.token_manager.ssl.create_default_context"),
        patch(
            "custom_components.hass_aula.token_manager.httpx.AsyncClient"
        ) as mock_httpx,
        patch(
            "custom_components.hass_aula.token_manager.create_client",
            return_value=new_client,
        ),
        patch("custom_components.hass_aula.token_manager.HttpxHttpClient"),
    ):
        mock_httpx.return_value = AsyncMock()
        mock_auth = MagicMock()
        mock_auth.refresh_access_token = AsyncMock(return_value=new_tokens)
        mock_auth_cls.return_value = mock_auth

        result = await tm.async_refresh_and_rebuild_client()

    assert result is new_client
    assert runtime_data.client is new_client
    for coord in all_coords:
        assert coord.client is new_client
    old_client.close.assert_called_once()


async def test_async_refresh_and_rebuild_client_early_exit(
    hass: HomeAssistant,
) -> None:
    """Test runtime refresh exits early if another waiter already refreshed."""
    entry = _make_entry(hass)

    existing_client = AsyncMock()
    runtime_data = MagicMock()
    runtime_data.client = existing_client
    entry.runtime_data = runtime_data

    # expires_at is in the future — another caller already refreshed
    entry.data[CONF_TOKEN_DATA]["tokens"]["expires_at"] = time.time() + 3600

    tm = AulaTokenManager(hass, entry)
    result = await tm.async_refresh_and_rebuild_client()

    assert result is existing_client


async def test_concurrent_refresh_only_one_call(hass: HomeAssistant) -> None:
    """Test concurrent refresh calls result in only one actual refresh."""
    entry = _make_entry(hass)
    entry.data = {
        CONF_TOKEN_DATA: {
            **MOCK_TOKEN_DATA,
            "tokens": {
                **MOCK_TOKEN_DATA["tokens"],
                "expires_at": time.time() - 100,
            },
        }
    }

    old_client = AsyncMock()
    new_client = AsyncMock()
    runtime_data = MagicMock()
    runtime_data.client = old_client
    runtime_data.all_coordinators = [MagicMock(), MagicMock(), MagicMock()]
    entry.runtime_data = runtime_data

    # Make async_update_entry actually update entry.data so the early-exit check works
    def fake_update(_entry: MagicMock, **kwargs: Any) -> None:
        if "data" in kwargs:
            _entry.data = kwargs["data"]

    hass.config_entries.async_update_entry = MagicMock(side_effect=fake_update)

    tm = AulaTokenManager(hass, entry)
    new_tokens = _make_refreshed_tokens()
    call_count = 0

    original_do_refresh = tm._async_do_refresh

    async def counting_refresh(token_data: dict, refresh_token: str) -> dict:
        nonlocal call_count
        call_count += 1
        return await original_do_refresh(token_data, refresh_token)

    with (
        patch(
            "custom_components.hass_aula.token_manager.MitIDAuthClient"
        ) as mock_auth_cls,
        patch("custom_components.hass_aula.token_manager.ssl.create_default_context"),
        patch(
            "custom_components.hass_aula.token_manager.httpx.AsyncClient"
        ) as mock_httpx,
        patch(
            "custom_components.hass_aula.token_manager.create_client",
            return_value=new_client,
        ),
        patch("custom_components.hass_aula.token_manager.HttpxHttpClient"),
        patch.object(tm, "_async_do_refresh", side_effect=counting_refresh),
    ):
        mock_httpx.return_value = AsyncMock()
        mock_auth = MagicMock()
        mock_auth.refresh_access_token = AsyncMock(return_value=new_tokens)
        mock_auth_cls.return_value = mock_auth

        results = await asyncio.gather(
            tm.async_refresh_and_rebuild_client(),
            tm.async_refresh_and_rebuild_client(),
        )

    # First call does the refresh, second gets early exit
    assert call_count == 1
    # Both return a valid client
    assert all(r is not None for r in results)
