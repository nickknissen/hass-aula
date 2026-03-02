"""Shared fixtures for Aula integration tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aula import CalendarEvent, DailyOverview, Profile
from aula.models import Notification
from aula.models.child import Child
from aula.models.presence import PresenceState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_aula.const import (
    CONF_MITID_USERNAME,
    CONF_TOKEN_DATA,
    DOMAIN,
)

MOCK_USERNAME = "test_user"
MOCK_TOKEN_DATA = {
    "timestamp": 1700000000.0,
    "created_at": "2024-01-01 00:00:00",
    "username": MOCK_USERNAME,
    "tokens": {
        "token_type": "Bearer",
        "expires_in": 3600,
        "access_token": "mock_access_token",
        "refresh_token": "mock_refresh_token",
        "expires_at": 1700003600.0,
    },
    "cookies": {},
}


@pytest.fixture(autouse=True)
def enable_custom_integrations(hass: HomeAssistant) -> None:
    """Enable custom integrations for all tests."""
    from homeassistant import loader

    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)


def make_config_entry(**kwargs) -> MockConfigEntry:
    """Create a MockConfigEntry with default Aula test data."""
    defaults = {
        "domain": DOMAIN,
        "data": {
            CONF_MITID_USERNAME: MOCK_USERNAME,
            CONF_TOKEN_DATA: MOCK_TOKEN_DATA,
        },
        "unique_id": "test_user",
    }
    defaults.update(kwargs)
    return MockConfigEntry(**defaults)


def mock_child(
    child_id: int = 1,
    name: str = "Test Child",
    institution_name: str = "Test School",
    profile_id: int = 100,
) -> MagicMock:
    """Create a mock Child object."""
    child = MagicMock(spec=Child)
    child.id = child_id
    child.name = name
    child.institution_name = institution_name
    child.profile_id = profile_id
    child.profile_picture = ""
    return child


def mock_profile(children: list[MagicMock] | None = None) -> MagicMock:
    """Create a mock Profile object."""
    profile = MagicMock(spec=Profile)
    profile.profile_id = 42
    profile.display_name = "Test Parent"
    profile.children = children or [mock_child()]
    profile.institution_profile_ids = [1]
    return profile


def mock_daily_overview(
    status: PresenceState = PresenceState.PRESENT,
    check_in_time: datetime | None = None,
    check_out_time: datetime | None = None,
    entry_time: datetime | None = None,
    exit_time: datetime | None = None,
    location: str | None = None,
) -> MagicMock:
    """Create a mock DailyOverview object."""
    overview = MagicMock(spec=DailyOverview)
    overview.status = status
    overview.check_in_time = check_in_time or datetime(2024, 1, 15, 8, 0, tzinfo=UTC)
    overview.check_out_time = check_out_time
    overview.entry_time = entry_time
    overview.exit_time = exit_time
    overview.location = location
    return overview


def mock_calendar_event(
    event_id: int = 1,
    title: str = "Math Class",
    start: datetime | None = None,
    end: datetime | None = None,
    teacher_name: str | None = "Mr. Smith",
    has_substitute: bool = False,
    substitute_name: str | None = None,
    location: str | None = None,
    belongs_to: int = 1,
) -> MagicMock:
    """Create a mock CalendarEvent object."""
    event = MagicMock(spec=CalendarEvent)
    event.id = event_id
    event.title = title
    event.start_datetime = start or datetime(2024, 1, 15, 9, 0, tzinfo=UTC)
    event.end_datetime = end or datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
    event.teacher_name = teacher_name
    event.has_substitute = has_substitute
    event.substitute_name = substitute_name
    event.location = location
    event.belongs_to = belongs_to
    return event


def mock_notification(
    notification_id: str = "1",
    title: str = "Test",
    module: str | None = "messaging",
    event_type: str | None = None,
    related_child_name: str | None = None,
    created_at: str | None = None,
    is_read: bool = False,
) -> MagicMock:
    """Create a mock Notification object."""
    notification = MagicMock(spec=Notification)
    notification.id = notification_id
    notification.title = title
    notification.module = module
    notification.event_type = event_type
    notification.related_child_name = related_child_name
    notification.created_at = created_at
    notification.is_read = is_read
    return notification


@pytest.fixture
def mock_aula_client() -> Generator[AsyncMock]:
    """Create a mock AulaApiClient."""
    with patch(
        "custom_components.hass_aula.create_client",
    ) as mock_create:
        client = AsyncMock()
        client.get_profile = AsyncMock(return_value=mock_profile())
        client.get_daily_overview = AsyncMock(return_value=mock_daily_overview())
        client.get_calendar_events = AsyncMock(return_value=[mock_calendar_event()])
        client.get_notifications_for_active_profile = AsyncMock(
            return_value=[mock_notification()]
        )
        client.is_logged_in = AsyncMock(return_value=True)
        client.close = AsyncMock()
        mock_create.return_value = client
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return make_config_entry()


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.hass_aula.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
