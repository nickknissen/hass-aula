"""Tests for Aula sensor platform."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from aula.models.presence import PresenceState
from homeassistant.core import HomeAssistant

from custom_components.aula.const import (
    CONF_MITID_USERNAME,
    CONF_TOKEN_DATA,
    DOMAIN,
)

from .conftest import (
    MOCK_TOKEN_DATA,
    MOCK_USERNAME,
    mock_daily_overview,
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


async def test_presence_status_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test presence status sensor reports correct state."""
    overview = mock_daily_overview(status=PresenceState.PRESENT)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = _create_config_entry(hass)
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

    entry = _create_config_entry(hass)
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

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_presence_status")
    assert state is not None
    assert state.state == "not_present"


async def test_check_in_time_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test check-in time sensor."""
    check_in = datetime(2024, 1, 15, 8, 30, tzinfo=UTC)
    overview = mock_daily_overview(check_in_time=check_in)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_check_in_time")
    assert state is not None
    assert state.state == check_in.isoformat()


async def test_check_out_time_sensor(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test check-out time sensor."""
    check_out = datetime(2024, 1, 15, 15, 0, tzinfo=UTC)
    overview = mock_daily_overview(check_out_time=check_out)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_check_out_time")
    assert state is not None
    assert state.state == check_out.isoformat()


async def test_sensor_unavailable_when_no_overview(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test sensors show unavailable when overview is None."""
    mock_aula_client.get_daily_overview = AsyncMock(return_value=None)

    entry = _create_config_entry(hass)
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

        entry = _create_config_entry(hass)
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
