"""Tests for Aula calendar platform."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

from aula import ActivityType, HttpRequestError
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.hass_aula.calendar import _convert_event

from .conftest import (
    make_config_entry,
    mock_calendar_event,
    mock_child,
    mock_day_template,
    mock_presence_week,
    mock_profile,
)

PRESENCE_PLAN = "calendar.test_child_presence_plan"


async def test_calendar_get_events_reads_this_childs_calendar(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test a range read shows the child's calendar as aula assembles it."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # aula has already put the booked slot in place of the booking period.
    booked_slot = mock_calendar_event(
        event_id=42,
        title="Skole-hjem-samtale",
        start=datetime(2024, 1, 16, 15, 20, tzinfo=UTC),
        end=datetime(2024, 1, 16, 15, 40, tzinfo=UTC),
        event_type="school_home_meeting",
    )
    mock_aula_client.get_calendar_events_by_child = AsyncMock(
        return_value={1: [booked_slot]}
    )
    start = datetime(2024, 1, 15, tzinfo=UTC)
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": "calendar.test_child_school_calendar",
            "start_date_time": start,
            "end_date_time": start + timedelta(days=7),
        },
        blocking=True,
        return_response=True,
    )

    events = response["calendar.test_child_school_calendar"]["events"]
    assert [
        (
            e["summary"],
            datetime.fromisoformat(e["start"]),
            datetime.fromisoformat(e["end"]),
        )
        for e in events
    ] == [
        (
            "Skole-hjem-samtale",
            datetime(2024, 1, 16, 15, 20, tzinfo=UTC),
            datetime(2024, 1, 16, 15, 40, tzinfo=UTC),
        )
    ]
    child_ids, range_start, range_end = (
        mock_aula_client.get_calendar_events_by_child.await_args.args
    )
    assert child_ids == [1]
    assert (range_start, range_end) == (start, start + timedelta(days=7))


async def test_calendar_entity_created(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test calendar entity is created."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.test_child_school_calendar")
    assert state is not None


async def test_calendar_with_events(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test calendar with events."""
    event = mock_calendar_event(
        title="Math Class",
        teacher_name="Mr. Smith",
        belongs_to=1,
    )
    mock_aula_client.get_calendar_events_by_child = AsyncMock(return_value={1: [event]})

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.test_child_school_calendar")
    assert state is not None


async def test_calendar_shared_lesson_is_on_for_both_twins(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a lesson twins share is the current event on both calendars."""
    freezer.move_to("2024-01-15T09:30:00+00:00")
    mock_aula_client.get_profile = AsyncMock(
        return_value=mock_profile([mock_child(1), mock_child(2, name="Second Child")])
    )
    shared = mock_calendar_event(title="Dansk", profiles=[1, 2])
    mock_aula_client.get_calendar_events_by_child = AsyncMock(
        return_value={1: [shared], 2: [shared]}
    )

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in (
        "calendar.test_child_school_calendar",
        "calendar.second_child_school_calendar",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert (state.state, state.attributes["message"]) == ("on", "Dansk")


async def test_calendar_empty(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test calendar with no events."""
    mock_aula_client.get_calendar_events_by_child = AsyncMock(return_value={1: []})

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.test_child_school_calendar")
    assert state is not None
    assert state.state == "off"


async def test_calendar_event_with_substitute(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test calendar event with substitute teacher."""
    event = mock_calendar_event(
        title="English Class",
        teacher_name="Mrs. Jones",
        has_substitute=True,
        substitute_name="Mr. Brown",
        belongs_to=1,
    )
    mock_aula_client.get_calendar_events_by_child = AsyncMock(return_value={1: [event]})

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.test_child_school_calendar")
    assert state is not None


async def test_calendar_event_with_location(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test calendar event with location."""
    event = mock_calendar_event(
        title="Gym Class",
        location="Sports Hall",
        belongs_to=1,
    )
    mock_aula_client.get_calendar_events_by_child = AsyncMock(return_value={1: [event]})

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.test_child_school_calendar")
    assert state is not None


async def test_calendar_get_events_api_error(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test a failed range fetch shows an empty range, not an error."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_aula_client.get_calendar_events_by_child = AsyncMock(
        side_effect=HttpRequestError("Aula rejected method (status code 1)", 200)
    )
    start = dt_util.now()
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": "calendar.test_child_school_calendar",
            "start_date_time": start,
            "end_date_time": start + timedelta(days=7),
        },
        blocking=True,
        return_response=True,
    )

    assert response == {"calendar.test_child_school_calendar": {"events": []}}


def test_convert_event_names_every_teacher() -> None:
    """A co-taught lesson names all its adults, not just the first."""
    event = mock_calendar_event(
        teacher_name="Laerer 1",
        teacher_names=["Laerer 1", "Laerer 2"],
    )

    assert "Teachers: Laerer 1, Laerer 2" in _convert_event(event).description


def test_convert_event_uses_singular_label_for_one_teacher() -> None:
    """A lesson with one adult still reads naturally."""
    event = mock_calendar_event(teacher_name="Mr. Smith")

    assert "Teacher: Mr. Smith" in _convert_event(event).description


def test_convert_event_falls_back_to_the_singular_field() -> None:
    """An event carrying no name list still names its teacher."""
    event = mock_calendar_event(teacher_name="Mr. Smith", teacher_names=[])

    assert "Teacher: Mr. Smith" in _convert_event(event).description


def test_convert_event_names_every_substitute() -> None:
    """Substitutes are listed in full too."""
    event = mock_calendar_event(
        teacher_name="Mrs. Jones",
        has_substitute=True,
        substitute_name="Mr. Brown",
        substitute_names=["Mr. Brown", "Ms. Green"],
    )

    assert "Substitutes: Mr. Brown, Ms. Green" in _convert_event(event).description


def test_convert_event_omits_substitutes_when_not_flagged() -> None:
    """Names left over on a lesson with no substitute are not shown."""
    event = mock_calendar_event(
        teacher_name="Mrs. Jones",
        has_substitute=False,
        substitute_names=["Mr. Brown"],
    )

    assert "Substitute" not in _convert_event(event).description


def test_convert_event_without_any_teacher_has_no_description() -> None:
    """An event with nothing to describe gets no description at all."""
    event = mock_calendar_event(teacher_name=None, location=None)

    assert _convert_event(event).description is None


async def _setup(hass: HomeAssistant) -> None:
    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _get_presence_plan(
    hass: HomeAssistant,
    start: datetime,
    end: datetime,
    entity_id: str = PRESENCE_PLAN,
) -> list[dict[str, Any]]:
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": entity_id, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    events: list[dict[str, Any]] = response[entity_id]["events"]
    return events


async def test_presence_plan_shows_each_planned_day(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A planned day runs from drop-off to pick-up, titled with how the child leaves."""
    await _setup(hass)
    week = [
        mock_day_template(
            "2024-01-15",
            ActivityType.PICKED_UP_BY,
            exit_with="Værge Et (Far)",
            comment="Har gymnastiktøj med",
        ),
        mock_day_template(
            "2024-01-16",
            ActivityType.SELF_DECIDER,
            exit_time="14:00:00",
            self_decider_start_time="14:00:00",
            self_decider_end_time="15:30:00",
        ),
        # A weekday nobody planned.
        mock_day_template(
            "2024-01-17",
            entry_time=None,
            exit_time=None,
            is_default_entry_time=True,
            is_default_exit_time=True,
        ),
        # Only the drop-off is planned; the pick-up is Aula's placeholder.
        mock_day_template(
            "2024-01-18",
            ActivityType.SEND_HOME,
            exit_time="23:59:00",
            is_default_exit_time=True,
        ),
        mock_day_template(
            "2024-01-19", exit_with="Værge Et (Far)", is_on_vacation=True
        ),
    ]
    mock_aula_client.get_presence_templates = AsyncMock(
        return_value=[mock_presence_week(1, week)]
    )
    tz = dt_util.get_default_time_zone()
    start = datetime(2024, 1, 15, tzinfo=tz)

    events = await _get_presence_plan(hass, start, start + timedelta(days=7))

    assert [
        (e["summary"], e["start"], e["end"], e.get("description")) for e in events
    ] == [
        (
            "Collected by Værge Et (Far)",
            datetime(2024, 1, 15, 8, 0, tzinfo=tz).isoformat(),
            datetime(2024, 1, 15, 15, 30, tzinfo=tz).isoformat(),
            "Har gymnastiktøj med",
        ),
        (
            "Allowed to leave alone 14:00-15:30",
            datetime(2024, 1, 16, 8, 0, tzinfo=tz).isoformat(),
            datetime(2024, 1, 16, 15, 30, tzinfo=tz).isoformat(),
            None,
        ),
        ("Sent home", "2024-01-18", "2024-01-19", None),
    ]
    mock_aula_client.get_presence_templates.assert_awaited_with(
        institution_profile_ids=[1],
        from_date=date(2024, 1, 15),
        to_date=date(2024, 1, 22),
    )


async def test_presence_plan_titles_follow_the_home_assistant_language(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Titles use the activity names the update_presence action shows."""
    hass.config.language = "da"
    mock_aula_client.get_presence_templates = AsyncMock(
        return_value=[
            mock_presence_week(1, [mock_day_template(exit_with="Værge Et (Far)")])
        ]
    )
    await _setup(hass)
    start = datetime(2024, 1, 15, tzinfo=dt_util.get_default_time_zone())

    events = await _get_presence_plan(
        hass, start, start + timedelta(days=1), "calendar.test_child_komme_ga_plan"
    )

    assert [e["summary"] for e in events] == ["Hentes af Værge Et (Far)"]


async def test_presence_plan_is_on_while_the_child_is_planned_in(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The calendar is on from drop-off to pick-up, with the day's title."""
    freezer.move_to(datetime(2024, 1, 15, 9, 0, tzinfo=dt_util.get_default_time_zone()))
    mock_aula_client.get_presence_templates = AsyncMock(
        return_value=[
            mock_presence_week(
                1,
                [
                    mock_day_template("2024-01-15", exit_with="Værge Et (Far)"),
                    mock_day_template("2024-01-16", ActivityType.SEND_HOME),
                ],
            )
        ]
    )
    await _setup(hass)

    state = hass.states.get(PRESENCE_PLAN)
    assert state is not None
    assert (state.state, state.attributes["message"]) == (
        "on",
        "Collected by Værge Et (Far)",
    )


async def test_presence_plan_get_events_api_error(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A failed range fetch shows an empty range, not an error."""
    await _setup(hass)
    mock_aula_client.get_presence_templates = AsyncMock(
        side_effect=HttpRequestError("Aula rejected method (status code 1)", 200)
    )
    start = dt_util.now()

    assert await _get_presence_plan(hass, start, start + timedelta(days=7)) == []
