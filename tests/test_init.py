"""Tests for Aula integration setup and teardown."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aula import AulaAuthenticationError, AulaConnectionError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.hass_aula.const import DOMAIN

from .conftest import make_config_entry, mock_child, mock_profile


def _make_refreshed_client() -> AsyncMock:
    """Create a mock client as returned by token refresh."""
    client = AsyncMock()
    client.get_profile = AsyncMock(return_value=mock_profile())
    client.get_daily_overview = AsyncMock(return_value=None)
    client.get_calendar_events = AsyncMock(return_value=[])
    client.get_notifications_for_active_profile = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


async def test_setup_entry(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test successful setup of a config entry."""
    entry = make_config_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    assert entry.runtime_data.client is mock_aula_client


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
) -> None:
    """Test setup fails with auth error when refresh also fails."""
    with (
        patch(
            "custom_components.hass_aula.create_client",
            side_effect=AulaAuthenticationError("Auth failed", 401),
        ),
        patch(
            "custom_components.hass_aula.AulaTokenManager.async_refresh_token",
            side_effect=AulaAuthenticationError("Refresh failed", 0),
        ),
    ):
        entry = make_config_entry()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_auth_error_refresh_succeeds(
    hass: HomeAssistant,
) -> None:
    """Test setup recovers when create_client fails but refresh succeeds."""
    refreshed_client = _make_refreshed_client()

    with (
        patch(
            "custom_components.hass_aula.create_client",
            side_effect=AulaAuthenticationError("Auth failed", 401),
        ),
        patch(
            "custom_components.hass_aula.AulaTokenManager.async_refresh_token",
            return_value=(refreshed_client, {"tokens": {}}),
        ),
    ):
        entry = make_config_entry()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.client is refreshed_client


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test setup retries with connection error."""
    with patch(
        "custom_components.hass_aula.create_client",
        side_effect=AulaConnectionError("Connection failed", 0),
    ):
        entry = make_config_entry()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_profile_auth_error(
    hass: HomeAssistant,
) -> None:
    """Test setup fails when get_profile raises auth error and refresh fails."""
    with (
        patch("custom_components.hass_aula.create_client") as mock_create,
        patch(
            "custom_components.hass_aula.AulaTokenManager.async_refresh_token",
            side_effect=AulaAuthenticationError("Refresh failed", 0),
        ),
    ):
        client = AsyncMock()
        client.get_profile = AsyncMock(
            side_effect=AulaAuthenticationError("Auth failed", 401)
        )
        client.close = AsyncMock()
        mock_create.return_value = client

        entry = make_config_entry()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_ERROR
        client.close.assert_called_once()


async def test_setup_entry_profile_auth_error_refresh_succeeds(
    hass: HomeAssistant,
) -> None:
    """Test setup recovers when get_profile fails but refresh succeeds."""
    refreshed_client = _make_refreshed_client()

    with (
        patch("custom_components.hass_aula.create_client") as mock_create,
        patch(
            "custom_components.hass_aula.AulaTokenManager.async_refresh_token",
            return_value=(refreshed_client, {"tokens": {}}),
        ),
    ):
        client = AsyncMock()
        client.get_profile = AsyncMock(
            side_effect=AulaAuthenticationError("Auth failed", 401)
        )
        client.close = AsyncMock()
        mock_create.return_value = client

        entry = make_config_entry()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.client is refreshed_client
        client.close.assert_called_once()


async def test_setup_entry_profile_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test setup retries when get_profile raises connection error."""
    with patch("custom_components.hass_aula.create_client") as mock_create:
        client = AsyncMock()
        client.get_profile = AsyncMock(
            side_effect=AulaConnectionError("Connection failed", 0)
        )
        client.close = AsyncMock()
        mock_create.return_value = client

        entry = make_config_entry()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_RETRY
        client.close.assert_called_once()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test successful unload of a config entry."""
    entry = make_config_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_aula_client.close.assert_called_once()


async def test_stale_device_removal(
    hass: HomeAssistant,
) -> None:
    """Test that devices for removed children are cleaned up."""
    child1 = mock_child(child_id=1, name="Child 1")
    child2 = mock_child(child_id=2, name="Child 2")
    profile_with_two = mock_profile(children=[child1, child2])

    with patch("custom_components.hass_aula.create_client") as mock_create:
        client = AsyncMock()
        client.get_profile = AsyncMock(return_value=profile_with_two)
        client.get_daily_overview = AsyncMock(return_value=None)
        client.get_calendar_events = AsyncMock(return_value=[])
        client.get_notifications_for_active_profile = AsyncMock(return_value=[])
        client.close = AsyncMock()
        mock_create.return_value = client

        entry = make_config_entry()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        # Now reload with only one child
        profile_with_one = mock_profile(children=[child1])
        client.get_profile = AsyncMock(return_value=profile_with_one)

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify second child device was removed
        device_registry = dr.async_get(hass)
        devices = [
            d
            for d in device_registry.devices.values()
            if (DOMAIN, "2") in d.identifiers
        ]
        assert len(devices) == 0
