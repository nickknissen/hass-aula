"""Tests for Aula calendar platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from aula import HttpRequestError
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.hass_aula.calendar import _convert_event

from .conftest import make_config_entry, mock_calendar_event


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
    mock_aula_client.get_calendar_events = AsyncMock(return_value=[event])

    entry = make_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.test_child_school_calendar")
    assert state is not None


async def test_calendar_empty(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test calendar with no events."""
    mock_aula_client.get_calendar_events = AsyncMock(return_value=[])

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
    mock_aula_client.get_calendar_events = AsyncMock(return_value=[event])

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
    mock_aula_client.get_calendar_events = AsyncMock(return_value=[event])

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

    mock_aula_client.get_calendar_events = AsyncMock(
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
