"""Tests for Aula coordinators."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aula import (
    AulaAuthenticationError,
    AulaConnectionError,
    AulaRateLimitError,
    AulaServerError,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.aula.const import (
    CONF_MITID_USERNAME,
    CONF_TOKEN_DATA,
    DOMAIN,
)
from custom_components.aula.coordinator import (
    AulaCalendarCoordinator,
    AulaPresenceCoordinator,
)

from .conftest import (
    MOCK_TOKEN_DATA,
    MOCK_USERNAME,
    mock_calendar_event,
    mock_daily_overview,
    mock_profile,
)


def _create_config_entry(hass: HomeAssistant):
    """Create a config entry and add it to HA."""
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_MITID_USERNAME: MOCK_USERNAME,
            CONF_TOKEN_DATA: MOCK_TOKEN_DATA,
        },
        source="user",
        unique_id="test_user",
    )
    entry.add_to_hass(hass)
    return entry


async def test_presence_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test presence coordinator fetches data for all children."""
    client = AsyncMock()
    overview = mock_daily_overview()
    client.get_daily_overview = AsyncMock(return_value=overview)

    profile = mock_profile()
    coordinator = AulaPresenceCoordinator(hass, client, profile)

    entry = _create_config_entry(hass)
    coordinator.config_entry = entry

    data = await coordinator._async_update_data()

    assert 1 in data
    assert data[1] is overview
    client.get_daily_overview.assert_called_once_with(1)


async def test_presence_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test presence coordinator raises ConfigEntryAuthFailed on auth error."""
    client = AsyncMock()
    client.get_daily_overview = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )

    profile = mock_profile()
    coordinator = AulaPresenceCoordinator(hass, client, profile)

    entry = _create_config_entry(hass)
    coordinator.config_entry = entry

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_presence_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test presence coordinator raises UpdateFailed on connection error."""
    client = AsyncMock()
    client.get_daily_overview = AsyncMock(
        side_effect=AulaConnectionError("Connection failed", 0)
    )

    profile = mock_profile()
    coordinator = AulaPresenceCoordinator(hass, client, profile)

    entry = _create_config_entry(hass)
    coordinator.config_entry = entry

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_presence_coordinator_server_error(hass: HomeAssistant) -> None:
    """Test presence coordinator raises UpdateFailed on server error."""
    client = AsyncMock()
    client.get_daily_overview = AsyncMock(
        side_effect=AulaServerError("Server error", 500)
    )

    profile = mock_profile()
    coordinator = AulaPresenceCoordinator(hass, client, profile)

    entry = _create_config_entry(hass)
    coordinator.config_entry = entry

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_presence_coordinator_rate_limit_error(hass: HomeAssistant) -> None:
    """Test presence coordinator raises UpdateFailed on rate limit error."""
    client = AsyncMock()
    client.get_daily_overview = AsyncMock(
        side_effect=AulaRateLimitError("Rate limited", 429)
    )

    profile = mock_profile()
    coordinator = AulaPresenceCoordinator(hass, client, profile)

    entry = _create_config_entry(hass)
    coordinator.config_entry = entry

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_calendar_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test calendar coordinator fetches events for all children."""
    client = AsyncMock()
    event = mock_calendar_event(belongs_to=1)
    client.get_calendar_events = AsyncMock(return_value=[event])

    profile = mock_profile()
    coordinator = AulaCalendarCoordinator(hass, client, profile)

    entry = _create_config_entry(hass)
    coordinator.config_entry = entry

    data = await coordinator._async_update_data()

    assert 1 in data
    assert len(data[1]) == 1
    assert data[1][0] is event


async def test_calendar_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test calendar coordinator raises ConfigEntryAuthFailed on auth error."""
    client = AsyncMock()
    client.get_calendar_events = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )

    profile = mock_profile()
    coordinator = AulaCalendarCoordinator(hass, client, profile)

    entry = _create_config_entry(hass)
    coordinator.config_entry = entry

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_calendar_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test calendar coordinator raises UpdateFailed on connection error."""
    client = AsyncMock()
    client.get_calendar_events = AsyncMock(
        side_effect=AulaConnectionError("Connection failed", 0)
    )

    profile = mock_profile()
    coordinator = AulaCalendarCoordinator(hass, client, profile)

    entry = _create_config_entry(hass)
    coordinator.config_entry = entry

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
