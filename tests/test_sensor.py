"""Tests for Aula sensor platform."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from aula.models.presence import PresenceState
from homeassistant.core import HomeAssistant

from custom_components.hass_aula.const import (
    WIDGET_BIBLIOTEKET,
    WIDGET_EASYIQ,
    WIDGET_HUSKELISTEN,
    WIDGET_MEEBOOK,
    WIDGET_MIN_UDDANNELSE_TASKS,
    WIDGET_MIN_UDDANNELSE_UGEPLAN,
)

from .conftest import (
    make_config_entry,
    make_widget_config_entry,
    mock_appointment,
    mock_assignment_reminder,
    mock_daily_overview,
    mock_easyiq_homework,
    mock_library_loan,
    mock_library_status,
    mock_meebook_student_plan,
    mock_mu_task,
    mock_mu_weekly_letter,
    mock_mu_weekly_person,
    mock_team_reminder,
    mock_user_reminders,
)


async def test_presence_status_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test presence status sensor reports correct state."""
    overview = mock_daily_overview(status=PresenceState.PRESENT)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_presence_status")
    assert state is not None
    assert state.state == "present"


async def test_presence_status_sick(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test presence status sensor when child is sick."""
    overview = mock_daily_overview(status=PresenceState.SICK)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_presence_status")
    assert state is not None
    assert state.state == "sick"


async def test_presence_status_not_present(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test presence status sensor when child is not present."""
    overview = mock_daily_overview(status=PresenceState.NOT_PRESENT)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_presence_status")
    assert state is not None
    assert state.state == "not_present"


async def test_presence_sensor_attributes(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test that check-in/out times and location are exposed as attributes."""
    check_in = datetime(2024, 1, 15, 8, 30, tzinfo=UTC)
    check_out = datetime(2024, 1, 15, 15, 0, tzinfo=UTC)
    entry_time = datetime(2024, 1, 15, 8, 25, tzinfo=UTC)
    exit_time = datetime(2024, 1, 15, 15, 5, tzinfo=UTC)
    overview = mock_daily_overview(
        check_in_time=check_in,
        check_out_time=check_out,
        entry_time=entry_time,
        exit_time=exit_time,
        location="Room 1",
    )
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_presence_status")
    assert state is not None
    assert state.attributes["check_in_time"] == check_in
    assert state.attributes["check_out_time"] == check_out
    assert state.attributes["entry_time"] == entry_time
    assert state.attributes["exit_time"] == exit_time
    assert state.attributes["location"] == "Room 1"


async def test_sensor_unavailable_when_no_overview(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test sensors show unavailable when overview is None."""
    mock_aula_client.get_daily_overview = AsyncMock(return_value=None)

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_presence_status")
    assert state is not None
    assert state.state == "unknown"


async def test_all_presence_states(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test that all presence states are correctly reported."""
    expected_states = {
        PresenceState.NOT_PRESENT: "not_present",
        PresenceState.SICK: "sick",
        PresenceState.REPORTED_ABSENT: "reported_absent",
        PresenceState.PRESENT: "present",
        PresenceState.FIELDTRIP: "fieldtrip",
        PresenceState.SLEEPING: "sleeping",
        PresenceState.SPARE_TIME_ACTIVITY: "spare_time_activity",
        PresenceState.PHYSICAL_PLACEMENT: "physical_placement",
        PresenceState.CHECKED_OUT: "checked_out",
    }

    for presence_state, expected_value in expected_states.items():
        overview = mock_daily_overview(status=presence_state)
        mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

        entry = make_config_entry()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test_child_presence_status")
        assert state is not None
        assert state.state == expected_value, (
            f"Expected {expected_value} for {presence_state}"
        )

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


# --- Notification Sensor Tests ---


async def test_notifications_sensor_counts_all(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test that notifications sensor counts all notifications."""
    from .conftest import mock_notification

    n1 = mock_notification(notification_id="1")
    n2 = mock_notification(notification_id="2")
    n3 = mock_notification(notification_id="3")
    mock_aula_client.get_notifications_for_active_profile = AsyncMock(
        return_value=[n1, n2, n3]
    )

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_parent_unread_notifications")
    assert state is not None
    assert state.state == "3"


async def test_child_notifications_per_child(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test per-child notification sensors filter by institution_profile_id."""
    from .conftest import mock_child, mock_notification, mock_profile

    child_a = mock_child(child_id=1, name="Child A")
    child_b = mock_child(child_id=2, name="Child B")
    profile = mock_profile(children=[child_a, child_b])
    mock_aula_client.get_profile = AsyncMock(return_value=profile)

    notifications = [
        mock_notification(
            notification_id="1",
            title="Msg A1",
            event_type="new_message",
            institution_profile_id=1,
        ),
        mock_notification(
            notification_id="2",
            title="Msg A2",
            event_type="new_post",
            institution_profile_id=1,
        ),
        mock_notification(
            notification_id="3",
            title="Msg B1",
            event_type="new_message",
            institution_profile_id=2,
        ),
        mock_notification(
            notification_id="4",
            title="No child",
            event_type="new_message",
            institution_profile_id=None,
        ),
    ]
    mock_aula_client.get_notifications_for_active_profile = AsyncMock(
        return_value=notifications
    )

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Child A: 2 notifications (ids 1, 2)
    state_a = hass.states.get("sensor.child_a_unread_notifications")
    assert state_a is not None
    assert state_a.state == "2"
    assert state_a.attributes["by_type"] == {"new_message": 1, "new_post": 1}
    assert len(state_a.attributes["recent"]) == 2

    # Child B: 1 notification (id 3)
    state_b = hass.states.get("sensor.child_b_unread_notifications")
    assert state_b is not None
    assert state_b.state == "1"
    assert state_b.attributes["by_type"] == {"new_message": 1}

    # Profile total counts all notifications including institution_profile_id=None
    state_total = hass.states.get("sensor.test_parent_unread_notifications")
    assert state_total is not None
    assert state_total.state == "4"


# --- Library Sensor Tests ---


async def test_library_loans_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test library loans sensor shows correct count and attributes."""
    loan1 = mock_library_loan(
        loan_id=1, title="Book A", patron_display_name="Test Child"
    )
    loan2 = mock_library_loan(
        loan_id=2, title="Book B", patron_display_name="Test Child"
    )
    status = mock_library_status(loans=[loan1], longterm_loans=[loan2])
    mock_aula_client.widgets.get_library_status = AsyncMock(return_value=status)

    entry = make_widget_config_entry(widgets=[WIDGET_BIBLIOTEKET])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_library_loans")
    assert state is not None
    assert state.state == "2"
    assert len(state.attributes["loans"]) == 2
    assert state.attributes["loans"][0]["title"] == "Book A"


async def test_library_sensor_not_created_when_widget_disabled(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test library sensor is not created when widget is not enabled."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_library_loans")
    assert state is None


async def test_library_sensor_empty_data(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test library sensor with no loans."""
    status = mock_library_status()
    mock_aula_client.widgets.get_library_status = AsyncMock(return_value=status)

    entry = make_widget_config_entry(widgets=[WIDGET_BIBLIOTEKET])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_library_loans")
    assert state is not None
    assert state.state == "0"


# --- MU Tasks Sensor Tests ---


async def test_mu_tasks_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test MU tasks sensor shows incomplete task count."""
    task1 = mock_mu_task(task_id="1", is_completed=False, student_name="Test Child")
    task2 = mock_mu_task(task_id="2", is_completed=True, student_name="Test Child")
    mock_aula_client.widgets.get_mu_tasks = AsyncMock(return_value=[task1, task2])

    entry = make_widget_config_entry(widgets=[WIDGET_MIN_UDDANNELSE_TASKS])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_mu_tasks")
    assert state is not None
    assert state.state == "1"  # only incomplete tasks
    assert len(state.attributes["tasks"]) == 2


async def test_mu_tasks_sensor_not_created_when_disabled(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test MU tasks sensor is not created when widget is disabled."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_mu_tasks")
    assert state is None


# --- EasyIQ Sensor Tests ---


async def test_easyiq_weekplan_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test EasyIQ weekplan sensor shows appointment count."""
    appt = mock_appointment()
    mock_aula_client.widgets.get_easyiq_weekplan = AsyncMock(return_value=[appt])
    mock_aula_client.widgets.get_easyiq_homework = AsyncMock(return_value=[])

    entry = make_widget_config_entry(widgets=[WIDGET_EASYIQ])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_weekplan")
    assert state is not None
    assert state.state == "1"
    assert len(state.attributes["appointments"]) == 1
    assert state.attributes["appointments"][0]["title"] == "Science Class"


async def test_easyiq_homework_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test EasyIQ homework sensor shows incomplete homework count."""
    hw1 = mock_easyiq_homework(hw_id="1", is_completed=False)
    hw2 = mock_easyiq_homework(hw_id="2", is_completed=True)
    mock_aula_client.widgets.get_easyiq_weekplan = AsyncMock(return_value=[])
    mock_aula_client.widgets.get_easyiq_homework = AsyncMock(return_value=[hw1, hw2])

    entry = make_widget_config_entry(widgets=[WIDGET_EASYIQ])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_homework")
    assert state is not None
    assert state.state == "1"  # only incomplete
    assert len(state.attributes["homework"]) == 2


async def test_easyiq_sensors_not_created_when_disabled(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test EasyIQ sensors are not created when widget is disabled."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_child_weekplan") is None
    assert hass.states.get("sensor.test_child_homework") is None


# --- Meebook Sensor Tests ---


async def test_meebook_weekplan_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test Meebook weekplan sensor shows task count."""
    plan = mock_meebook_student_plan(name="Test Child")
    mock_aula_client.widgets.get_meebook_weekplan = AsyncMock(return_value=[plan])

    entry = make_widget_config_entry(widgets=[WIDGET_MEEBOOK])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_meebook_weekplan")
    assert state is not None
    assert state.state == "1"
    assert len(state.attributes["tasks"]) == 1
    assert state.attributes["tasks"][0]["title"] == "Weekly Activity"


async def test_meebook_sensor_not_created_when_disabled(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test Meebook sensor is not created when widget is disabled."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_child_meebook_weekplan") is None


# --- Huskelisten Sensor Tests ---


async def test_huskelisten_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test Huskelisten sensor shows reminder count."""
    team_r = mock_team_reminder()
    assign_r = mock_assignment_reminder()
    ur = mock_user_reminders(
        user_name="Test Child",
        team_reminders=[team_r],
        assignment_reminders=[assign_r],
    )
    mock_aula_client.widgets.get_momo_reminders = AsyncMock(return_value=[ur])

    entry = make_widget_config_entry(widgets=[WIDGET_HUSKELISTEN])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_reminders")
    assert state is not None
    assert state.state == "2"
    assert len(state.attributes["reminders"]) == 2
    assert state.attributes["reminders"][0]["text"] == "Remember to bring gym clothes"
    assert state.attributes["reminders"][1]["text"] == "Complete worksheet"


async def test_huskelisten_sensor_not_created_when_disabled(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test Huskelisten sensor is not created when widget is disabled."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_child_reminders") is None


async def test_huskelisten_sensor_empty(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test Huskelisten sensor with no reminders."""
    mock_aula_client.widgets.get_momo_reminders = AsyncMock(return_value=[])

    entry = make_widget_config_entry(widgets=[WIDGET_HUSKELISTEN])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_reminders")
    assert state is not None
    assert state.state == "0"


# --- MU Weekly Notes Sensor Tests ---


async def test_mu_weekly_notes_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test MU weekly notes sensor shows note count and attributes."""
    letter1 = mock_mu_weekly_letter(group_name="3A", week_number=5)
    letter2 = mock_mu_weekly_letter(group_id=2, group_name="3B", week_number=5)
    next_letter = mock_mu_weekly_letter(group_name="3A", week_number=6)
    person = mock_mu_weekly_person(name="Test Child", letters=[letter1, letter2])
    next_person = mock_mu_weekly_person(name="Test Child", letters=[next_letter])
    mock_aula_client.widgets.get_ugeplan = AsyncMock(
        side_effect=[[person], [next_person]]
    )

    entry = make_widget_config_entry(widgets=[WIDGET_MIN_UDDANNELSE_UGEPLAN])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_weekly_notes")
    assert state is not None
    assert state.state == "2"
    assert len(state.attributes["notes"]) == 2
    assert state.attributes["notes"][0] == "<p>Weekly update</p>"
    assert len(state.attributes["next_week_notes"]) == 1
    assert state.attributes["next_week_notes"][0] == "<p>Weekly update</p>"


async def test_mu_weekly_notes_sensor_not_created_when_disabled(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test MU weekly notes sensor is not created when feature is disabled."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_weekly_notes")
    assert state is None


async def test_mu_weekly_notes_sensor_empty(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test MU weekly notes sensor with no notes."""
    mock_aula_client.widgets.get_ugeplan = AsyncMock(side_effect=[[], []])

    entry = make_widget_config_entry(widgets=[WIDGET_MIN_UDDANNELSE_UGEPLAN])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_weekly_notes")
    assert state is not None
    assert state.state == "0"
