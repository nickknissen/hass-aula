"""Shared fixtures for Aula integration tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aula import CalendarEvent, DailyOverview, Profile
from aula.models import Appointment, EasyIQHomework, LibraryLoan, MUTask
from aula.models.child import Child
from aula.models.library import LibraryStatus
from aula.models.meebook_weekplan import MeebookDayPlan, MeebookStudentPlan, MeebookTask
from aula.models.momo_huskeliste import AssignmentReminder, TeamReminder, UserReminders
from aula.models.mu_task import MUTaskClass
from aula.models.mu_weekly_letter import (
    MUWeeklyInstitution,
    MUWeeklyLetter,
    MUWeeklyPerson,
)
from aula.models.notification import Notification
from aula.models.presence import PresenceState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_aula.const import (
    CONF_MITID_USERNAME,
    CONF_TOKEN_DATA,
    CONF_WIDGETS,
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


def make_config_entry(**kwargs: Any) -> MockConfigEntry:
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


def make_widget_config_entry(widgets: list[str], **kwargs: Any) -> MockConfigEntry:
    """Create a MockConfigEntry with widgets enabled."""
    data = {
        CONF_MITID_USERNAME: MOCK_USERNAME,
        CONF_TOKEN_DATA: MOCK_TOKEN_DATA,
        CONF_WIDGETS: widgets,
    }
    return make_config_entry(data=data, **kwargs)


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
    child._raw = {
        "id": child_id,
        "userId": str(child_id * 1000),
        "profileId": profile_id,
        "name": name,
        "institutionProfile": {
            "institutionName": institution_name,
            "institutionCode": f"inst_{child_id}",
        },
    }
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
    institution_profile_id: int | None = None,
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
    notification.institution_profile_id = institution_profile_id
    return notification


def mock_library_loan(
    loan_id: int = 1,
    title: str = "Test Book",
    author: str = "Test Author",
    patron_display_name: str = "Test Child",
    due_date: str = "2024-02-01",
) -> MagicMock:
    """Create a mock LibraryLoan object."""
    loan = MagicMock(spec=LibraryLoan)
    loan.id = loan_id
    loan.title = title
    loan.author = author
    loan.patron_display_name = patron_display_name
    loan.due_date = due_date
    loan.number_of_loans = 1
    loan.cover_image_url = ""
    return loan


def mock_library_status(
    loans: list | None = None,
    longterm_loans: list | None = None,
    reservations: list | None = None,
) -> MagicMock:
    """Create a mock LibraryStatus object."""
    status = MagicMock(spec=LibraryStatus)
    status.loans = loans or []
    status.longterm_loans = longterm_loans or []
    status.reservations = reservations or []
    status.branch_ids = []
    return status


def mock_mu_task(
    task_id: str = "1",
    title: str = "Math Homework",
    student_name: str = "Test Child",
    is_completed: bool = False,
    due_date: datetime | None = None,
) -> MagicMock:
    """Create a mock MUTask object."""
    task = MagicMock(spec=MUTask)
    task.id = task_id
    task.title = title
    task.task_type = "assignment"
    task.due_date = due_date or datetime(2024, 2, 1, tzinfo=UTC)
    task.weekday = "Monday"
    task.week_number = 5
    task.is_completed = is_completed
    task.student_name = student_name
    task.unilogin = "test_uni"
    task.url = "https://example.com"
    mock_class = MagicMock(spec=MUTaskClass)
    mock_class.name = "Math"
    task.classes = [mock_class]
    task.course = None
    return task


def mock_appointment(
    appointment_id: str = "1",
    title: str = "Science Class",
    start: str = "2024-01-15T09:00:00",
    end: str = "2024-01-15T10:00:00",
) -> MagicMock:
    """Create a mock Appointment object."""
    appt = MagicMock(spec=Appointment)
    appt.appointment_id = appointment_id
    appt.title = title
    appt.start = start
    appt.end = end
    appt.description = ""
    appt.item_type = None
    return appt


def mock_easyiq_homework(
    hw_id: str = "1",
    title: str = "Read Chapter 5",
    subject: str = "English",
    due_date: str = "2024-02-01",
    is_completed: bool = False,
) -> MagicMock:
    """Create a mock EasyIQHomework object."""
    hw = MagicMock(spec=EasyIQHomework)
    hw.id = hw_id
    hw.title = title
    hw.description = ""
    hw.due_date = due_date
    hw.subject = subject
    hw.is_completed = is_completed
    return hw


def mock_meebook_task(
    task_id: int = 1,
    title: str = "Weekly Activity",
    task_type: str = "activity",
    content: str = "Do the activity",
) -> MagicMock:
    """Create a mock MeebookTask object."""
    task = MagicMock(spec=MeebookTask)
    task.id = task_id
    task.type = task_type
    task.title = title
    task.content = content
    task.pill = ""
    task.link_text = ""
    return task


def mock_meebook_student_plan(
    name: str = "Test Child",
    tasks: list | None = None,
) -> MagicMock:
    """Create a mock MeebookStudentPlan with a single day."""
    plan = MagicMock(spec=MeebookStudentPlan)
    plan.name = name
    plan.unilogin = "test_uni"
    day = MagicMock(spec=MeebookDayPlan)
    day.date = "2024-01-15"
    day.tasks = tasks or [mock_meebook_task()]
    plan.week_plan = [day]
    return plan


def mock_team_reminder(
    reminder_id: int = 1,
    reminder_text: str = "Remember to bring gym clothes",
    due_date: str = "2024-02-01",
    team_name: str = "3A",
    subject_name: str = "Gym",
) -> MagicMock:
    """Create a mock TeamReminder object."""
    r = MagicMock(spec=TeamReminder)
    r.id = reminder_id
    r.institution_name = "Test School"
    r.institution_id = 1
    r.due_date = due_date
    r.team_id = 1
    r.team_name = team_name
    r.reminder_text = reminder_text
    r.created_by = "Teacher"
    r.last_edit_by = "Teacher"
    r.subject_name = subject_name
    return r


def mock_assignment_reminder(
    reminder_id: int = 1,
    assignment_text: str = "Complete worksheet",
    due_date: str = "2024-02-01",
    team_names: list[str] | None = None,
) -> MagicMock:
    """Create a mock AssignmentReminder object."""
    r = MagicMock(spec=AssignmentReminder)
    r.id = reminder_id
    r.institution_name = "Test School"
    r.institution_id = 1
    r.due_date = due_date
    r.course_id = 1
    r.team_names = team_names or ["3A"]
    r.team_ids = [1]
    r.assignment_id = 1
    r.assignment_text = assignment_text
    return r


def mock_user_reminders(
    user_name: str = "Test Child",
    team_reminders: list | None = None,
    assignment_reminders: list | None = None,
) -> MagicMock:
    """Create a mock UserReminders object."""
    ur = MagicMock(spec=UserReminders)
    ur.user_id = 1
    ur.user_name = user_name
    ur.team_reminders = team_reminders or []
    ur.assignment_reminders = assignment_reminders or []
    return ur


def mock_mu_weekly_letter(
    group_id: int = 1,
    group_name: str = "3A",
    content_html: str = "<p>Weekly update</p>",
    week_number: int = 5,
    sort_order: int = 0,
) -> MagicMock:
    """Create a mock MUWeeklyLetter object."""
    letter = MagicMock(spec=MUWeeklyLetter)
    letter.group_id = group_id
    letter.group_name = group_name
    letter.content_html = content_html
    letter.week_number = week_number
    letter.sort_order = sort_order
    return letter


def mock_mu_weekly_person(
    name: str = "Test Child",
    person_id: int = 1,
    letters: list | None = None,
    institution_name: str = "Test School",
    institution_code: int = 1,
) -> MagicMock:
    """Create a mock MUWeeklyPerson with a single institution."""
    person = MagicMock(spec=MUWeeklyPerson)
    person.name = name
    person.id = person_id
    person.unilogin = "test_uni"
    inst = MagicMock(spec=MUWeeklyInstitution)
    inst.name = institution_name
    inst.code = institution_code
    inst.letters = letters or [mock_mu_weekly_letter()]
    person.institutions = [inst]
    return person


def _setup_widget_mocks(client: AsyncMock) -> None:
    """Set up widget-related mock methods on a client."""
    client.get_profile_context = AsyncMock(
        return_value={"data": {"userId": "session_123"}}
    )
    client.widgets = MagicMock()
    client.widgets.get_library_status = AsyncMock(return_value=mock_library_status())
    client.widgets.get_mu_tasks = AsyncMock(return_value=[])
    client.widgets.get_ugeplan = AsyncMock(return_value=[])
    client.widgets.get_easyiq_weekplan = AsyncMock(return_value=[])
    client.widgets.get_easyiq_homework = AsyncMock(return_value=[])
    client.widgets.get_meebook_weekplan = AsyncMock(return_value=[])
    client.widgets.get_momo_reminders = AsyncMock(return_value=[])


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
        _setup_widget_mocks(client)
        mock_create.return_value = client
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return make_config_entry()


@pytest.fixture
def mock_token_manager() -> AsyncMock:
    """Create a mock AulaTokenManager."""
    tm = AsyncMock()
    tm.async_refresh_token = AsyncMock()
    tm.async_refresh_and_rebuild_client = AsyncMock()
    return tm


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.hass_aula.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
