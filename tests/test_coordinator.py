"""Tests for Aula coordinators."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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

from custom_components.hass_aula.coordinator import (
    AulaCalendarCoordinator,
    AulaEasyIQCoordinator,
    AulaHuskelistenCoordinator,
    AulaLibraryCoordinator,
    AulaMeebookCoordinator,
    AulaMUTasksCoordinator,
    AulaMUUgeplanCoordinator,
    AulaPresenceCoordinator,
)
from custom_components.hass_aula.data import (
    WidgetContext,
)

from .conftest import (
    mock_appointment,
    mock_calendar_event,
    mock_daily_overview,
    mock_easyiq_homework,
    mock_library_loan,
    mock_library_status,
    mock_meebook_student_plan,
    mock_mu_task,
    mock_mu_weekly_letter,
    mock_mu_weekly_person,
    mock_profile,
    mock_team_reminder,
    mock_user_reminders,
)


def _create_config_entry():
    """Create a mock config entry for coordinator tests."""
    return MagicMock()


def _create_widget_context() -> WidgetContext:
    """Create a test widget context."""
    return WidgetContext(
        child_filter=["1000"],
        institution_filter=["inst_1"],
        session_uuid="session_123",
    )


def _create_token_manager() -> AsyncMock:
    """Create a mock token manager for coordinator tests."""
    tm = AsyncMock()
    tm.async_refresh_and_rebuild_client = AsyncMock()
    return tm


# --- Presence Coordinator Tests ---


async def test_presence_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test presence coordinator fetches data for all children."""
    client = AsyncMock()
    overview = mock_daily_overview()
    client.get_daily_overview = AsyncMock(return_value=overview)
    client.get_presence_templates = AsyncMock(return_value=[])

    profile = mock_profile()
    tm = _create_token_manager()
    coordinator = AulaPresenceCoordinator(hass, client, profile, tm)

    entry = _create_config_entry()
    coordinator.config_entry = entry

    data = await coordinator._async_update_data()

    assert 1 in data
    assert data[1].overview is overview
    assert data[1].self_decider_start is None
    assert data[1].self_decider_end is None
    client.get_daily_overview.assert_called_once_with(1)


async def test_presence_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test presence coordinator raises ConfigEntryAuthFailed on auth error."""
    client = AsyncMock()
    client.get_daily_overview = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )
    client.get_presence_templates = AsyncMock(return_value=[])

    profile = mock_profile()
    tm = _create_token_manager()
    tm.async_refresh_and_rebuild_client = AsyncMock(
        side_effect=AulaAuthenticationError("Refresh failed", 0)
    )
    coordinator = AulaPresenceCoordinator(hass, client, profile, tm)

    entry = _create_config_entry()
    coordinator.config_entry = entry

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_presence_coordinator_auth_error_refresh_succeeds(
    hass: HomeAssistant,
) -> None:
    """Test presence coordinator raises UpdateFailed after successful refresh."""
    client = AsyncMock()
    client.get_daily_overview = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )
    client.get_presence_templates = AsyncMock(return_value=[])

    profile = mock_profile()
    tm = _create_token_manager()
    coordinator = AulaPresenceCoordinator(hass, client, profile, tm)

    entry = _create_config_entry()
    coordinator.config_entry = entry

    with pytest.raises(UpdateFailed, match="Session refreshed"):
        await coordinator._async_update_data()


async def test_presence_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test presence coordinator raises UpdateFailed on connection error."""
    client = AsyncMock()
    client.get_daily_overview = AsyncMock(
        side_effect=AulaConnectionError("Connection failed", 0)
    )
    client.get_presence_templates = AsyncMock(return_value=[])

    profile = mock_profile()
    tm = _create_token_manager()
    coordinator = AulaPresenceCoordinator(hass, client, profile, tm)

    entry = _create_config_entry()
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
    tm = _create_token_manager()
    coordinator = AulaPresenceCoordinator(hass, client, profile, tm)

    entry = _create_config_entry()
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
    tm = _create_token_manager()
    coordinator = AulaPresenceCoordinator(hass, client, profile, tm)

    entry = _create_config_entry()
    coordinator.config_entry = entry

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# --- Calendar Coordinator Tests ---


async def test_calendar_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test calendar coordinator fetches events for all children."""
    client = AsyncMock()
    event = mock_calendar_event(belongs_to=1)
    client.get_calendar_events = AsyncMock(return_value=[event])

    profile = mock_profile()
    tm = _create_token_manager()
    coordinator = AulaCalendarCoordinator(hass, client, profile, tm)

    entry = _create_config_entry()
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
    tm = _create_token_manager()
    tm.async_refresh_and_rebuild_client = AsyncMock(
        side_effect=AulaAuthenticationError("Refresh failed", 0)
    )
    coordinator = AulaCalendarCoordinator(hass, client, profile, tm)

    entry = _create_config_entry()
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
    tm = _create_token_manager()
    coordinator = AulaCalendarCoordinator(hass, client, profile, tm)

    entry = _create_config_entry()
    coordinator.config_entry = entry

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# --- Library Coordinator Tests ---


async def test_library_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test library coordinator fetches and distributes loans to children."""
    client = AsyncMock()
    loan = mock_library_loan(patron_display_name="Test Child")
    longterm = mock_library_loan(
        loan_id=2, title="Long Book", patron_display_name="Test Child"
    )
    status = mock_library_status(
        loans=[loan], longterm_loans=[longterm], reservations=[{"id": 1}]
    )
    client.widgets = MagicMock()
    client.widgets.get_library_status = AsyncMock(return_value=status)

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaLibraryCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    data = await coordinator._async_update_data()

    assert 1 in data
    assert len(data[1].loans) == 1
    assert data[1].loans[0] is loan
    assert len(data[1].longterm_loans) == 1
    assert data[1].longterm_loans[0] is longterm
    assert len(data[1].reservations) == 1


async def test_library_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test library coordinator raises ConfigEntryAuthFailed on auth error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_library_status = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    tm.async_refresh_and_rebuild_client = AsyncMock(
        side_effect=AulaAuthenticationError("Refresh failed", 0)
    )
    coordinator = AulaLibraryCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_library_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test library coordinator raises UpdateFailed on connection error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_library_status = AsyncMock(
        side_effect=AulaConnectionError("Connection failed", 0)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaLibraryCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_library_coordinator_multi_child(hass: HomeAssistant) -> None:
    """Test library coordinator distributes loans to correct children."""
    from .conftest import mock_child

    child1 = mock_child(child_id=1, name="Alice")
    child2 = mock_child(child_id=2, name="Bob")
    profile = mock_profile(children=[child1, child2])

    loan_alice = mock_library_loan(loan_id=1, patron_display_name="Alice")
    loan_bob = mock_library_loan(loan_id=2, patron_display_name="Bob")
    status = mock_library_status(loans=[loan_alice, loan_bob])

    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_library_status = AsyncMock(return_value=status)

    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaLibraryCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    data = await coordinator._async_update_data()

    assert len(data[1].loans) == 1
    assert data[1].loans[0] is loan_alice
    assert len(data[2].loans) == 1
    assert data[2].loans[0] is loan_bob


# --- MU Tasks Coordinator Tests ---


async def test_mu_tasks_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test MU tasks coordinator fetches and distributes tasks."""
    client = AsyncMock()
    task = mock_mu_task(student_name="Test Child")
    client.widgets = MagicMock()
    client.widgets.get_mu_tasks = AsyncMock(return_value=[task])

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaMUTasksCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    data = await coordinator._async_update_data()

    assert 1 in data
    assert len(data[1]) == 1
    assert data[1][0] is task


async def test_mu_tasks_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test MU tasks coordinator raises ConfigEntryAuthFailed on auth error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_mu_tasks = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    tm.async_refresh_and_rebuild_client = AsyncMock(
        side_effect=AulaAuthenticationError("Refresh failed", 0)
    )
    coordinator = AulaMUTasksCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_mu_tasks_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test MU tasks coordinator raises UpdateFailed on connection error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_mu_tasks = AsyncMock(
        side_effect=AulaConnectionError("Connection failed", 0)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaMUTasksCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# --- EasyIQ Coordinator Tests ---


async def test_easyiq_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test EasyIQ coordinator fetches weekplan and homework per child."""
    client = AsyncMock()
    appt = mock_appointment()
    hw = mock_easyiq_homework()
    client.widgets = MagicMock()
    client.widgets.get_easyiq_weekplan = AsyncMock(return_value=[appt])
    client.widgets.get_easyiq_homework = AsyncMock(return_value=[hw])

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaEasyIQCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    data = await coordinator._async_update_data()

    assert 1 in data
    assert len(data[1].weekplan) == 1
    assert data[1].weekplan[0] is appt
    assert len(data[1].homework) == 1
    assert data[1].homework[0] is hw


async def test_easyiq_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test EasyIQ coordinator raises ConfigEntryAuthFailed on auth error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_easyiq_weekplan = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )
    client.widgets.get_easyiq_homework = AsyncMock(return_value=[])

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    tm.async_refresh_and_rebuild_client = AsyncMock(
        side_effect=AulaAuthenticationError("Refresh failed", 0)
    )
    coordinator = AulaEasyIQCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_easyiq_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test EasyIQ coordinator raises UpdateFailed on connection error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_easyiq_weekplan = AsyncMock(
        side_effect=AulaConnectionError("Connection failed", 0)
    )
    client.widgets.get_easyiq_homework = AsyncMock(return_value=[])

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaEasyIQCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# --- Meebook Coordinator Tests ---


async def test_meebook_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test Meebook coordinator fetches and flattens tasks."""
    client = AsyncMock()
    plan = mock_meebook_student_plan(name="Test Child")
    client.widgets = MagicMock()
    client.widgets.get_meebook_weekplan = AsyncMock(return_value=[plan])

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaMeebookCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    data = await coordinator._async_update_data()

    assert 1 in data
    assert len(data[1]) == 1  # one task from the single day plan


async def test_meebook_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test Meebook coordinator raises ConfigEntryAuthFailed on auth error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_meebook_weekplan = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    tm.async_refresh_and_rebuild_client = AsyncMock(
        side_effect=AulaAuthenticationError("Refresh failed", 0)
    )
    coordinator = AulaMeebookCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_meebook_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test Meebook coordinator raises UpdateFailed on connection error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_meebook_weekplan = AsyncMock(
        side_effect=AulaConnectionError("Connection failed", 0)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaMeebookCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# --- Huskelisten Coordinator Tests ---


async def test_huskelisten_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test Huskelisten coordinator fetches and distributes reminders."""
    client = AsyncMock()
    team_r = mock_team_reminder()
    ur = mock_user_reminders(user_name="Test Child", team_reminders=[team_r])
    client.widgets = MagicMock()
    client.widgets.get_momo_reminders = AsyncMock(return_value=[ur])

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaHuskelistenCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    data = await coordinator._async_update_data()

    assert 1 in data
    assert len(data[1].team_reminders) == 1
    assert data[1].team_reminders[0] is team_r


async def test_huskelisten_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test Huskelisten coordinator raises ConfigEntryAuthFailed on auth error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_momo_reminders = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    tm.async_refresh_and_rebuild_client = AsyncMock(
        side_effect=AulaAuthenticationError("Refresh failed", 0)
    )
    coordinator = AulaHuskelistenCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_huskelisten_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test Huskelisten coordinator raises UpdateFailed on connection error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_momo_reminders = AsyncMock(
        side_effect=AulaConnectionError("Connection failed", 0)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaHuskelistenCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# --- MU Ugeplan Coordinator Tests ---


async def test_mu_ugeplan_coordinator_fetch(hass: HomeAssistant) -> None:
    """Test MU ugeplan coordinator fetches and distributes weekly notes."""
    client = AsyncMock()
    person = mock_mu_weekly_person(name="Test Child")
    next_person = mock_mu_weekly_person(
        name="Test Child",
        letters=[mock_mu_weekly_letter(group_name="3A", week_number=6)],
    )
    client.widgets = MagicMock()
    client.widgets.get_ugeplan = AsyncMock(side_effect=[[person], [next_person]])

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaMUUgeplanCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    data = await coordinator._async_update_data()

    assert 1 in data.current
    assert len(data.current[1]) == 1
    assert data.current[1][0].group_name == "3A"
    assert 1 in data.next_week
    assert len(data.next_week[1]) == 1
    assert data.next_week[1][0].week_number == 6


async def test_mu_ugeplan_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test MU ugeplan coordinator raises ConfigEntryAuthFailed on auth error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_ugeplan = AsyncMock(
        side_effect=AulaAuthenticationError("Auth failed", 401)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    tm.async_refresh_and_rebuild_client = AsyncMock(
        side_effect=AulaAuthenticationError("Refresh failed", 0)
    )
    coordinator = AulaMUUgeplanCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_mu_ugeplan_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test MU ugeplan coordinator raises UpdateFailed on connection error."""
    client = AsyncMock()
    client.widgets = MagicMock()
    client.widgets.get_ugeplan = AsyncMock(
        side_effect=AulaConnectionError("Connection failed", 0)
    )

    profile = mock_profile()
    ctx = _create_widget_context()
    tm = _create_token_manager()
    coordinator = AulaMUUgeplanCoordinator(hass, client, profile, ctx, tm)
    coordinator.config_entry = _create_config_entry()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
