"""Tests for the Aula actions."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from aula import ActivityType, AulaAuthenticationError, AulaConnectionError
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.util import dt as dt_util

from custom_components.hass_aula import services
from custom_components.hass_aula.const import DOMAIN, SERVICE_UPDATE_PRESENCE

from .conftest import make_config_entry, mock_child, mock_profile

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def _setup_integration(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    children: list[MagicMock] | None = None,
) -> MockConfigEntry:
    """Set up the integration and return the config entry."""
    if children is not None:
        mock_aula_client.get_profile.return_value = mock_profile(children)
    entry = make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _device_id(hass: HomeAssistant, child_id: int) -> str:
    """Return the registry device ID for a child."""
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, str(child_id))},
    )
    assert device is not None
    return device.id


async def _call(hass: HomeAssistant, **data: Any) -> None:
    """Call update_presence with the given data."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_PRESENCE,
        data,
        blocking=True,
    )


async def test_service_registered(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """The action is registered."""
    await _setup_integration(hass, mock_aula_client)
    assert hass.services.has_service(DOMAIN, SERVICE_UPDATE_PRESENCE)


async def test_service_description_loads(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """services.yaml describes every field the action accepts."""
    await _setup_integration(hass, mock_aula_client)
    descriptions = await async_get_all_descriptions(hass)

    description = descriptions[DOMAIN][SERVICE_UPDATE_PRESENCE]
    assert set(description["fields"]) == {
        "entry_time",
        "exit_time",
        "date",
        "activity_type",
        "exit_with",
        "comment",
        "repeat",
        "expires_at",
    }
    assert "target" in description


def test_services_yaml_target_has_no_device_filter() -> None:
    """Hassfest rejects device filters on target; catch that before CI does."""
    path = Path(services.__file__).parent / "services.yaml"
    definitions = yaml.safe_load(path.read_text(encoding="utf-8"))

    for name, definition in definitions.items():
        target = definition.get("target")
        if target is not None:
            assert "device" not in target, (
                f"{name}: use a device selector field, not a target device filter"
            )


async def test_update_presence_by_device(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A device target updates that child with the given times."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    await _call(
        hass,
        **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
        entry_time="08:00:00",
        exit_time="15:30:00",
        date="2026-08-11",
        exit_with="Nick Nissen (Far)",
        comment="Går til fodbold",
    )

    mock_aula_client.update_presence_template.assert_awaited_once_with(
        institution_profile_id=1,
        by_date=date(2026, 8, 11),
        entry_time="08:00",
        exit_time="15:30",
        activity_type=ActivityType.PICKED_UP_BY,
        exit_with="Nick Nissen (Far)",
        comment="Går til fodbold",
        template_id=None,
        repeat_pattern="Never",
        expires_at=None,
    )


async def test_update_presence_defaults_to_today(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Omitting the date targets today."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    await _call(
        hass,
        **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
        entry_time="08:00:00",
        exit_time="15:30:00",
        activity_type="self_decider",
    )

    kwargs = mock_aula_client.update_presence_template.await_args.kwargs
    assert kwargs["by_date"] == dt_util.now().date()
    assert kwargs["activity_type"] is ActivityType.SELF_DECIDER


async def test_update_presence_reuses_existing_template_id(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """An existing template for the date is updated instead of duplicated."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    day = MagicMock()
    day.id = 987
    day.by_date = "2026-08-11T00:00:00"
    profile = MagicMock()
    profile.id = 1
    week_template = MagicMock()
    week_template.institution_profile = profile
    week_template.day_templates = [day]
    mock_aula_client.get_presence_templates = AsyncMock(return_value=[week_template])

    await _call(
        hass,
        **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
        entry_time="08:00:00",
        exit_time="15:30:00",
        date="2026-08-11",
        exit_with="Mor",
    )

    kwargs = mock_aula_client.update_presence_template.await_args.kwargs
    assert kwargs["template_id"] == 987


async def test_update_presence_multiple_children(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Two device targets produce one call per child."""
    children = [mock_child(1, "Emilie"), mock_child(2, "Karla")]
    await _setup_integration(hass, mock_aula_client, children)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    await _call(
        hass,
        **{ATTR_DEVICE_ID: [_device_id(hass, 1), _device_id(hass, 2)]},
        entry_time="08:00:00",
        exit_time="15:30:00",
        exit_with="Far",
    )

    assert mock_aula_client.update_presence_template.await_count == 2
    updated = {
        call.kwargs["institution_profile_id"]
        for call in mock_aula_client.update_presence_template.await_args_list
    }
    assert updated == {1, 2}


async def test_update_presence_by_entity(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """An entity target resolves to that entity's child device."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    await _call(
        hass,
        **{ATTR_ENTITY_ID: ["sensor.test_child_presence_status"]},
        entry_time="08:00:00",
        exit_time="15:30:00",
        exit_with="Far",
    )

    kwargs = mock_aula_client.update_presence_template.await_args.kwargs
    assert kwargs["institution_profile_id"] == 1


async def test_update_presence_refreshes_presence_coordinator(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """The presence coordinator refreshes after a successful update."""
    entry = await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)
    before = mock_aula_client.get_daily_overview.await_count

    await _call(
        hass,
        **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
        entry_time="08:00:00",
        exit_time="15:30:00",
        exit_with="Far",
    )
    await hass.async_block_till_done()

    assert entry.runtime_data.presence_coordinator.last_update_success
    assert mock_aula_client.get_daily_overview.await_count > before


async def test_exit_with_required_for_pickup(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """picked_up_by without exit_with is rejected."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
            entry_time="08:00:00",
            exit_time="15:30:00",
        )

    mock_aula_client.update_presence_template.assert_not_awaited()


async def test_exit_with_not_required_for_self_decider(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """self_decider does not need a pickup person."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    await _call(
        hass,
        **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
        entry_time="08:00:00",
        exit_time="15:30:00",
        activity_type="self_decider",
    )

    mock_aula_client.update_presence_template.assert_awaited_once()


async def test_invalid_time_range(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """An exit time at or before the entry time is rejected."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
            entry_time="15:30:00",
            exit_time="08:00:00",
            exit_with="Far",
        )

    mock_aula_client.update_presence_template.assert_not_awaited()


async def test_no_target(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A call with no target is rejected."""
    await _setup_integration(hass, mock_aula_client)

    with pytest.raises(ServiceValidationError):
        await _call(hass, entry_time="08:00:00", exit_time="15:30:00", exit_with="Far")


async def test_unknown_device(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A device that is not an Aula child is rejected."""
    await _setup_integration(hass, mock_aula_client)

    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            **{ATTR_DEVICE_ID: ["does-not-exist"]},
            entry_time="08:00:00",
            exit_time="15:30:00",
            exit_with="Far",
        )


async def test_account_device_is_not_a_valid_target(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """The profile-level device cannot be targeted."""
    await _setup_integration(hass, mock_aula_client)
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "profile_42")},
    )
    assert device is not None

    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            **{ATTR_DEVICE_ID: [device.id]},
            entry_time="08:00:00",
            exit_time="15:30:00",
            exit_with="Far",
        )


async def test_entry_not_loaded(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Targeting a child of an unloaded entry is a user error."""
    entry = await _setup_integration(hass, mock_aula_client)
    device_id = _device_id(hass, 1)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            **{ATTR_DEVICE_ID: [device_id]},
            entry_time="08:00:00",
            exit_time="15:30:00",
            exit_with="Far",
        )


async def test_auth_error_refreshes_and_retries(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """An auth failure triggers a session refresh and one retry."""
    entry = await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(
        side_effect=[AulaAuthenticationError("expired", 401), True]
    )
    refresh = AsyncMock(return_value=mock_aula_client)
    entry.runtime_data.token_manager.async_refresh_and_rebuild_client = refresh

    await _call(
        hass,
        **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
        entry_time="08:00:00",
        exit_time="15:30:00",
        exit_with="Far",
    )

    refresh.assert_awaited_once()
    assert mock_aula_client.update_presence_template.await_count == 2


async def test_auth_error_after_refresh_raises(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A second auth failure surfaces as a HomeAssistantError."""
    entry = await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(
        side_effect=AulaAuthenticationError("expired", 401)
    )
    entry.runtime_data.token_manager.async_refresh_and_rebuild_client = AsyncMock(
        return_value=mock_aula_client
    )

    with pytest.raises(HomeAssistantError):
        await _call(
            hass,
            **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
            entry_time="08:00:00",
            exit_time="15:30:00",
            exit_with="Far",
        )


async def test_connection_error_raises(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A connection failure surfaces as a HomeAssistantError."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(
        side_effect=AulaConnectionError("boom", 500)
    )

    with pytest.raises(HomeAssistantError):
        await _call(
            hass,
            **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
            entry_time="08:00:00",
            exit_time="15:30:00",
            exit_with="Far",
        )
