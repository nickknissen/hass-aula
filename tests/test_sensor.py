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
    WIDGET_MIN_UDDANNELSE,
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

    entry = make_widget_config_entry(widgets=[WIDGET_MIN_UDDANNELSE])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_tasks")
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

    state = hass.states.get("sensor.test_child_tasks")
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
