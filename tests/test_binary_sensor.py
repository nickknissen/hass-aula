"""Tests for Aula binary sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from aula.models.presence import PresenceState
from homeassistant.core import HomeAssistant

from custom_components.aula.const import (
    CONF_MITID_USERNAME,
    CONF_TOKEN_DATA,
    DOMAIN,
)

from .conftest import MOCK_TOKEN_DATA, MOCK_USERNAME, mock_daily_overview


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


async def test_binary_sensor_present(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test binary sensor is on when child is present."""
    overview = mock_daily_overview(status=PresenceState.PRESENT)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_child_present")
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_not_present(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test binary sensor is off when child is not present."""
    overview = mock_daily_overview(status=PresenceState.NOT_PRESENT)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_child_present")
    assert state is not None
    assert state.state == "off"


async def test_binary_sensor_sick(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test binary sensor is off when child is sick."""
    overview = mock_daily_overview(status=PresenceState.SICK)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_child_present")
    assert state is not None
    assert state.state == "off"


async def test_binary_sensor_fieldtrip(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test binary sensor is on when child is on fieldtrip."""
    overview = mock_daily_overview(status=PresenceState.FIELDTRIP)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_child_present")
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_sleeping(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test binary sensor is on when child is sleeping."""
    overview = mock_daily_overview(status=PresenceState.SLEEPING)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_child_present")
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_checked_out(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test binary sensor is off when child has checked out."""
    overview = mock_daily_overview(status=PresenceState.CHECKED_OUT)
    mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_child_present")
    assert state is not None
    assert state.state == "off"


async def test_binary_sensor_unavailable(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test binary sensor when overview is None."""
    mock_aula_client.get_daily_overview = AsyncMock(return_value=None)

    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_child_present")
    assert state is not None
    # When overview is None, is_on returns None which shows as unknown
    assert state.state == "unknown"


async def test_binary_sensor_all_present_states(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test all states that should show as present."""
    present_states = [
        PresenceState.PRESENT,
        PresenceState.FIELDTRIP,
        PresenceState.SLEEPING,
        PresenceState.SPARE_TIME_ACTIVITY,
        PresenceState.PHYSICAL_PLACEMENT,
    ]

    for presence_state in present_states:
        overview = mock_daily_overview(status=presence_state)
        mock_aula_client.get_daily_overview = AsyncMock(return_value=overview)

        entry = _create_config_entry(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.test_child_present")
        assert state is not None
        assert state.state == "on", f"Expected on for {presence_state}"

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
