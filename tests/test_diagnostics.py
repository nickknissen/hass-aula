"""Tests for Aula diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from custom_components.aula.const import (
    CONF_MITID_USERNAME,
    CONF_TOKEN_DATA,
    DOMAIN,
)
from custom_components.aula.diagnostics import async_get_config_entry_diagnostics

from .conftest import MOCK_TOKEN_DATA, MOCK_USERNAME


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


async def test_diagnostics_redacts_pii(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test that diagnostics redacts PII."""
    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["profile"]["display_name"] == "**REDACTED**"
    assert result["profile"]["children"][0]["name"] == "**REDACTED**"
    assert result["profile"]["children_count"] == 1


async def test_diagnostics_structure(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test diagnostics output structure."""
    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert "profile" in result
    assert "presence" in result
    assert "calendar_event_counts" in result
    assert "profile_id" in result["profile"]
    assert "children" in result["profile"]


async def test_diagnostics_presence_data(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test diagnostics includes presence data."""
    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert "1" in result["presence"]
    presence = result["presence"]["1"]
    assert "status" in presence
    assert "check_in_time" in presence


async def test_diagnostics_calendar_counts(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Test diagnostics includes calendar event counts."""
    entry = _create_config_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert "1" in result["calendar_event_counts"]
    assert isinstance(result["calendar_event_counts"]["1"], int)
