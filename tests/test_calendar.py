"""Tests for Aula calendar platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from custom_components.hass_aula.const import (
    CONF_MITID_USERNAME,
    CONF_TOKEN_DATA,
    DOMAIN,
)

from .conftest import MOCK_TOKEN_DATA, MOCK_USERNAME, mock_calendar_event


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


async def test_calendar_entity_created(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test calendar entity is created."""
    entry = _create_config_entry(hass)
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

    entry = _create_config_entry(hass)
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

    entry = _create_config_entry(hass)
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

    entry = _create_config_entry(hass)
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

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.test_child_school_calendar")
    assert state is not None
