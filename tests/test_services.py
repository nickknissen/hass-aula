"""Tests for the Aula actions."""

from __future__ import annotations

import inspect
import json
import os
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import probatio
import pytest
import yaml
from aula import (
    ActivityType,
    Attachment,
    AttachmentDocument,
    AttachmentFile,
    AttachmentLink,
    AttachmentMedia,
    AulaApiClient,
    AulaAuthenticationError,
    AulaConnectionError,
    DownloadTooLargeError,
    HttpRequestError,
)
from aula.api_client import ThreadScanLimitError
from homeassistant.components import media_source
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import Context
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.hass_aula import services
from custom_components.hass_aula.const import (
    DOMAIN,
    SERVICE_CLEAR_ATTACHMENTS,
    SERVICE_DOWNLOAD_ATTACHMENT,
    SERVICE_GET_THREAD_MESSAGES,
    SERVICE_MARK_THREAD_READ,
    SERVICE_UPDATE_PRESENCE,
)

from .conftest import make_config_entry, mock_child, mock_message, mock_profile

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry, MockUser


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
    [device] = dr.async_get(hass).async_get_devices(
        identifiers={(DOMAIN, str(child_id))},
    )
    return device.id


async def _call(hass: HomeAssistant, **data: Any) -> None:
    """Call update_presence with the given data."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_PRESENCE,
        data,
        blocking=True,
    )


def _assert_fits_installed_aula(update_presence_template: AsyncMock) -> None:
    """
    Check the call against the installed aula's real signature.

    The client mock accepts any keyword, so without this a keyword the pinned
    aula lacks would pass here and raise TypeError in Home Assistant.
    """
    inspect.signature(AulaApiClient.update_presence_template).bind(
        None, **update_presence_template.await_args.kwargs
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
        "self_decider_end_time",
        "exit_with",
        "comment",
        "repeat",
        "expires_at",
    }
    assert "target" in description


def test_services_yaml_matches_hassfest_rules() -> None:
    """
    Mirror the hassfest rules that services.yaml keeps tripping over.

    Custom integrations may only use these top-level keys, and a device filter
    on target is rejected outright. Both fail in CI otherwise.
    """
    allowed = {"fields", "target", "name", "description"}
    path = Path(services.__file__).parent / "services.yaml"
    definitions = yaml.safe_load(path.read_text(encoding="utf-8"))

    for name, definition in definitions.items():
        extra = set(definition) - allowed
        assert not extra, f"{name}: hassfest rejects top-level key(s) {sorted(extra)}"

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
        self_decider_end_time=None,
    )
    _assert_fits_installed_aula(mock_aula_client.update_presence_template)


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


async def test_self_decider_leaves_within_a_window(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A self-decider may leave from exit_time until self_decider_end_time."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    await _call(
        hass,
        **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
        entry_time="08:00:00",
        exit_time="14:00:00",
        activity_type="self_decider",
        self_decider_end_time="16:00:00",
    )

    kwargs = mock_aula_client.update_presence_template.await_args.kwargs
    assert kwargs["activity_type"] == ActivityType.SELF_DECIDER
    assert kwargs["exit_time"] == "14:00"
    assert kwargs["self_decider_end_time"] == "16:00"
    _assert_fits_installed_aula(mock_aula_client.update_presence_template)


async def test_self_decider_end_time_needs_self_decider(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Any other activity type has no window, so the end time is refused."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass,
            **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
            entry_time="08:00:00",
            exit_time="14:00:00",
            exit_with="Far",
            self_decider_end_time="16:00:00",
        )

    assert err.value.translation_key == "self_decider_end_time_not_allowed"
    mock_aula_client.update_presence_template.assert_not_awaited()


async def test_self_decider_window_must_end_after_it_starts(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """An end time at or before exit_time is refused."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(return_value=True)

    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass,
            **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
            entry_time="08:00:00",
            exit_time="16:00:00",
            activity_type="self_decider",
            self_decider_end_time="14:00:00",
        )

    assert err.value.translation_key == "invalid_self_decider_window"
    mock_aula_client.update_presence_template.assert_not_awaited()


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
    entry = await _setup_integration(hass, mock_aula_client)
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, "profile_42"), entry.entry_id
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


async def test_api_error_envelope_raises(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """An error code in a 200 response surfaces as a HomeAssistantError."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.update_presence_template = AsyncMock(
        side_effect=HttpRequestError("Aula rejected method (status code 1)", 200)
    )

    with pytest.raises(HomeAssistantError):
        await _call(
            hass,
            **{ATTR_DEVICE_ID: [_device_id(hass, 1)]},
            entry_time="08:00:00",
            exit_time="15:30:00",
            exit_with="Far",
        )


async def test_get_thread_messages_returns_full_content(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """The action returns content, sender and send time for each message."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = AsyncMock(
        return_value=[
            mock_message(
                message_id="9",
                content="Kære forældre",
                sender="Anne Jensen",
                send_date="2026-11-10T07:15:00+00:00",
            )
        ]
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_THREAD_MESSAGES,
        {"thread_id": "42"},
        blocking=True,
        return_response=True,
    )

    mock_aula_client.get_messages_for_thread.assert_awaited_once_with("42", limit=5)
    assert response == {
        "thread_id": "42",
        "messages": [
            {
                "id": "9",
                "content": "Kære forældre",
                "content_markdown": "Kære forældre",
                "sender": "Anne Jensen",
                "sent_at": "2026-11-10T07:15:00+00:00",
                "attachments": [],
            }
        ],
    }


async def test_get_thread_messages_missing_sender_and_send_time_are_null(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A message without a sender or send time still comes back, with nulls."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = AsyncMock(
        return_value=[mock_message(sender=None, send_date=None)]
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_THREAD_MESSAGES,
        {"thread_id": "42"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    [message] = response["messages"]
    assert message["sender"] is None
    assert message["sent_at"] is None


async def test_get_thread_messages_lists_attachments_by_type(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Each attachment says which variant it is, and a secure document has no URL."""
    await _setup_integration(hass, mock_aula_client)
    attachments = [
        Attachment(
            id=1,
            name="plan.pdf",
            created=datetime(2026, 11, 10, 7, 14, tzinfo=UTC),
            file=AttachmentFile(id=11, url="https://example.com/plan.pdf"),
        ),
        Attachment(
            id=2,
            name="theme-day.jpg",
            media=AttachmentMedia(title="Theme day", media_type="image"),
            file=AttachmentFile(id=12, url="https://example.com/theme-day.jpg"),
        ),
        Attachment(
            id=3,
            name="Invitation",
            link=AttachmentLink(service="onedrive", url="https://example.com/inv"),
        ),
        Attachment(
            id=4,
            name="Secure note",
            document=AttachmentDocument(id=44, title="Secure note"),
        ),
        Attachment(id=5, name="Unknown"),
    ]
    mock_aula_client.get_messages_for_thread = AsyncMock(
        return_value=[mock_message(has_attachments=True, attachments=attachments)]
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_THREAD_MESSAGES,
        {"thread_id": "42"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    [message] = response["messages"]
    assert message["attachments"] == [
        {
            "id": 1,
            "name": "plan.pdf",
            "type": "file",
            "url": "https://example.com/plan.pdf",
            "created": "2026-11-10T07:14:00+00:00",
        },
        {
            "id": 2,
            "name": "theme-day.jpg",
            "type": "media",
            "url": "https://example.com/theme-day.jpg",
            "created": None,
        },
        {
            "id": 3,
            "name": "Invitation",
            "type": "link",
            "url": "https://example.com/inv",
            "created": None,
        },
        {
            "id": 4,
            "name": "Secure note",
            "type": "document",
            "url": None,
            "created": None,
        },
        {"id": 5, "name": "Unknown", "type": None, "url": None, "created": None},
    ]


async def test_get_thread_messages_response_is_plain_json(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Datetimes and attachments go out as plain JSON types."""
    await _setup_integration(hass, mock_aula_client)
    attachment = Attachment(
        id=1,
        name="plan.pdf",
        created=datetime(2026, 11, 10, 7, 14, tzinfo=UTC),
        file=AttachmentFile(id=11, url="https://example.com/plan.pdf"),
    )
    mock_aula_client.get_messages_for_thread = AsyncMock(
        return_value=[mock_message(has_attachments=True, attachments=[attachment])]
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_THREAD_MESSAGES,
        {"thread_id": "42"},
        blocking=True,
        return_response=True,
    )

    assert json.loads(json.dumps(response)) == response


async def test_get_thread_messages_honours_limit(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """An explicit limit is passed through to the client."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = AsyncMock(return_value=[])

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_THREAD_MESSAGES,
        {"thread_id": "42", "limit": 25},
        blocking=True,
        return_response=True,
    )

    mock_aula_client.get_messages_for_thread.assert_awaited_once_with("42", limit=25)


@pytest.mark.parametrize("limit", [0, 51])
async def test_get_thread_messages_rejects_out_of_range_limit(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    limit: int,
) -> None:
    """A limit outside 1-50 is rejected by the schema."""
    await _setup_integration(hass, mock_aula_client)

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_THREAD_MESSAGES,
            {"thread_id": "42", "limit": limit},
            blocking=True,
            return_response=True,
        )


async def test_get_thread_messages_does_not_fetch_thread_list(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Reading a thread costs one request, not a thread-list lookup as well."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = AsyncMock(return_value=[])
    before = mock_aula_client.get_message_threads.await_count

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_THREAD_MESSAGES,
        {"thread_id": "42"},
        blocking=True,
        return_response=True,
    )

    assert mock_aula_client.get_message_threads.await_count == before


async def test_get_thread_messages_explicit_config_entry(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """An explicit config_entry_id selects the account."""
    entry = await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = AsyncMock(return_value=[])

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_THREAD_MESSAGES,
        {"thread_id": "42", "config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )

    mock_aula_client.get_messages_for_thread.assert_awaited_once()


async def test_get_thread_messages_unknown_config_entry(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """An unknown config_entry_id is a user error."""
    await _setup_integration(hass, mock_aula_client)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_THREAD_MESSAGES,
            {"thread_id": "42", "config_entry_id": "nope"},
            blocking=True,
            return_response=True,
        )


async def test_get_thread_messages_no_loaded_account(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """With the only account unloaded the action reports that, not entries[0]."""
    entry = await _setup_integration(hass, mock_aula_client)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_THREAD_MESSAGES,
            {"thread_id": "42"},
            blocking=True,
            return_response=True,
        )


async def test_get_thread_messages_ambiguous_account(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Two loaded accounts require an explicit config_entry_id."""
    await _setup_integration(hass, mock_aula_client)
    second = make_config_entry(unique_id="second_user")
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_THREAD_MESSAGES,
            {"thread_id": "42"},
            blocking=True,
            return_response=True,
        )


async def test_get_thread_messages_auth_error_refreshes_and_retries(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Reads share the presence action's refresh-and-retry behaviour."""
    entry = await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = AsyncMock(
        side_effect=[AulaAuthenticationError("expired", 401), []]
    )
    refresh = AsyncMock(return_value=mock_aula_client)
    entry.runtime_data.token_manager.async_refresh_and_rebuild_client = refresh

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_THREAD_MESSAGES,
        {"thread_id": "42"},
        blocking=True,
        return_response=True,
    )

    refresh.assert_awaited_once()
    assert mock_aula_client.get_messages_for_thread.await_count == 2


async def test_get_thread_messages_connection_error_raises(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A connection failure surfaces as a HomeAssistantError."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = AsyncMock(
        side_effect=AulaConnectionError("boom", 500)
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_THREAD_MESSAGES,
            {"thread_id": "42"},
            blocking=True,
            return_response=True,
        )


async def test_mark_thread_read_marks_and_refreshes(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """The action marks the thread and refreshes the unread count."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.mark_thread_read = AsyncMock(return_value=True)
    threads_fetched = mock_aula_client.get_message_threads.await_count

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_MARK_THREAD_READ,
        {"thread_id": "42"},
        blocking=True,
        return_response=True,
    )

    mock_aula_client.mark_thread_read.assert_awaited_once_with("42")
    assert response == {"thread_id": "42", "marked": True}
    assert mock_aula_client.get_message_threads.await_count > threads_fetched


async def test_mark_thread_read_without_response(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """The action can be called without asking for a response."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.mark_thread_read = AsyncMock(return_value=False)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_MARK_THREAD_READ,
        {"thread_id": "42"},
        blocking=True,
    )

    mock_aula_client.mark_thread_read.assert_awaited_once_with("42")


async def test_mark_thread_read_refuses_shared_inbox(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """A thread outside the guardian's own mailbox is a user error."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.mark_thread_read = AsyncMock(
        side_effect=ValueError("thread is not in the guardian's own mailbox")
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MARK_THREAD_READ,
            {"thread_id": "42"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "thread_not_in_own_mailbox"


@pytest.mark.parametrize(
    "error",
    [
        ThreadScanLimitError("no message in the first 50 pages"),
        HttpRequestError("Aula did not confirm the read marker", 200),
    ],
)
async def test_mark_thread_read_failure_raises(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    error: Exception,
) -> None:
    """A thread aula could not mark surfaces as a HomeAssistantError."""
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.mark_thread_read = AsyncMock(side_effect=error)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MARK_THREAD_READ,
            {"thread_id": "42"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "action_failed"


async def _download(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    """Call download_attachment and return its response."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_DOWNLOAD_ATTACHMENT,
        data,
        blocking=True,
        return_response=True,
    )
    assert response is not None
    return dict(response)


def _thread_with(*attachments: Attachment) -> AsyncMock:
    """Return a get_messages_for_thread mock whose newest message has attachments."""
    return AsyncMock(
        return_value=[mock_message(has_attachments=True, attachments=list(attachments))]
    )


async def test_download_attachment_saves_file_in_media_folder(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """The file lands in an aula folder in the media folder, named after its id."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(
            id=123,
            name="Ugeplan uge 47.pdf",
            file=AttachmentFile(id=11, url="https://example.com/plan.pdf"),
        )
    )
    mock_aula_client.download_file = AsyncMock(return_value=b"%PDF-1.7")

    response = await _download(hass, thread_id="42", attachment_id=123)

    saved = tmp_path / "aula" / "123_ugeplan_uge_47.pdf"
    assert response == {
        "path": str(saved),
        "media_content_id": (
            "media-source://media_source/local/aula/123_ugeplan_uge_47.pdf"
        ),
        "content_type": "application/pdf",
    }
    assert saved.read_bytes() == b"%PDF-1.7"
    mock_aula_client.get_messages_for_thread.assert_awaited_once_with("42", limit=5)
    mock_aula_client.download_file.assert_awaited_once_with(
        "https://example.com/plan.pdf", max_bytes=25 * 1024 * 1024
    )
    inspect.signature(AulaApiClient.download_file).bind(
        None,
        *mock_aula_client.download_file.await_args.args,
        **mock_aula_client.download_file.await_args.kwargs,
    )


async def test_download_attachment_media_content_id_resolves_to_saved_file(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """The returned id opens the saved file, also when no media folder is "local"."""
    school_dir = tmp_path / "school"
    hass.config.media_dirs = {
        "school": str(school_dir),
        "recordings": str(tmp_path / "recordings"),
    }
    await _setup_integration(hass, mock_aula_client)
    assert await async_setup_component(hass, "media_source", {})
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(
            id=123,
            name="Ugeplan uge 47.pdf",
            file=AttachmentFile(id=11, url="https://example.com/plan.pdf"),
        )
    )
    mock_aula_client.download_file = AsyncMock(return_value=b"%PDF-1.7")

    response = await _download(hass, thread_id="42", attachment_id=123)

    media = await media_source.async_resolve_media(
        hass, response["media_content_id"], None
    )
    assert media.path == school_dir / "aula" / "123_ugeplan_uge_47.pdf"
    assert media.mime_type == "application/pdf"


@pytest.mark.parametrize(
    ("name", "file_name"),
    [
        ("Høstfest på skolen.JPG", "123_hostfest_pa_skolen.jpg"),
        ("Plan~1..final.pdf", "123_plan_1_final.pdf"),
        ("Plan.pd~f", "123_plan.pd_f"),
        ("../../secret.pdf", "123_secret.pdf"),
        ("Invitation", "123_invitation"),
        ("", "123_unknown"),
        (f"{'a' * 150}.pdf", f"123_{'a' * 100}.pdf"),
    ],
)
async def test_download_attachment_cleans_the_file_name(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
    name: str,
    file_name: str,
) -> None:
    """The name is cleaned so the media source, and so ai_task, can open it."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    assert await async_setup_component(hass, "media_source", {})
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(
            id=123,
            name=name,
            file=AttachmentFile(id=11, url="https://example.com/file"),
        )
    )
    mock_aula_client.download_file = AsyncMock(return_value=b"content")

    response = await _download(hass, thread_id="42", attachment_id=123)

    assert Path(response["path"]) == tmp_path / "aula" / file_name
    assert (tmp_path / "aula" / file_name).read_bytes() == b"content"
    if response["content_type"] is not None:
        media = await media_source.async_resolve_media(
            hass, response["media_content_id"], None
        )
        assert media.path == tmp_path / "aula" / file_name


@pytest.mark.parametrize(
    "attachment",
    [
        Attachment(
            id=123,
            name="Invitation",
            link=AttachmentLink(service="onedrive", url="https://example.com/inv"),
        ),
        Attachment(
            id=123,
            name="Secure note",
            document=AttachmentDocument(id=44, title="Secure note"),
        ),
        Attachment(id=123, name="Unknown"),
    ],
    ids=["link", "document", "no_type"],
)
async def test_download_attachment_refuses_what_aula_does_not_store(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
    attachment: Attachment,
) -> None:
    """Cloud links, secure documents and unknown kinds fail before any download."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = _thread_with(attachment)
    mock_aula_client.download_file = AsyncMock(return_value=b"content")

    with pytest.raises(ServiceValidationError) as exc_info:
        await _download(hass, thread_id="42", attachment_id=123)

    assert exc_info.value.translation_key == "attachment_not_downloadable"
    mock_aula_client.download_file.assert_not_awaited()
    assert not (tmp_path / "aula").exists()


async def test_download_attachment_saves_a_gallery_item(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """A gallery image is stored in Aula, so it downloads like a file."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(
            id=124,
            name="Theme day.jpg",
            media=AttachmentMedia(title="Theme day", media_type="image"),
            file=AttachmentFile(id=12, url="https://example.com/theme-day.jpg"),
        )
    )
    mock_aula_client.download_file = AsyncMock(return_value=b"\xff\xd8")

    response = await _download(hass, thread_id="42", attachment_id=124)

    assert response["content_type"] == "image/jpeg"
    assert (tmp_path / "aula" / "124_theme_day.jpg").read_bytes() == b"\xff\xd8"
    mock_aula_client.download_file.assert_awaited_once_with(
        "https://example.com/theme-day.jpg", max_bytes=25 * 1024 * 1024
    )


async def test_download_attachment_not_in_newest_messages(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """An id that is not in the newest five messages fails with a clear error."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(
            id=123,
            name="plan.pdf",
            file=AttachmentFile(id=11, url="https://example.com/plan.pdf"),
        )
    )
    mock_aula_client.download_file = AsyncMock(return_value=b"content")

    with pytest.raises(ServiceValidationError) as exc_info:
        await _download(hass, thread_id="42", attachment_id=999)

    assert exc_info.value.translation_key == "attachment_not_found"
    assert exc_info.value.translation_placeholders == {
        "attachment_id": "999",
        "thread_id": "42",
    }
    mock_aula_client.download_file.assert_not_awaited()


async def test_download_attachment_too_large(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """A file over the limit fails as a validation error and nothing is saved."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(
            id=123,
            name="video.mp4",
            file=AttachmentFile(id=11, url="https://example.com/video.mp4"),
        )
    )
    mock_aula_client.download_file = AsyncMock(
        side_effect=DownloadTooLargeError(
            "Download from example.com is larger than 26214400 bytes",
            max_bytes=26214400,
        )
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _download(hass, thread_id="42", attachment_id=123)

    assert exc_info.value.translation_key == "attachment_too_large"
    assert exc_info.value.translation_placeholders == {
        "name": "video.mp4",
        "max_mb": "25",
    }
    assert not (tmp_path / "aula").exists()


async def test_download_attachment_refused_by_the_file_server(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """A refused download names the status, never the signed URL."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    url = "https://example.com/plan.pdf?signature=secret"
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(id=123, name="plan.pdf", file=AttachmentFile(id=11, url=url))
    )
    request = httpx.Request("GET", url)
    mock_aula_client.download_file = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            f"Client error '403 Forbidden' for url '{url}'",
            request=request,
            response=httpx.Response(403, request=request),
        )
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _download(hass, thread_id="42", attachment_id=123)

    assert not isinstance(exc_info.value, ServiceValidationError)
    assert exc_info.value.translation_key == "attachment_download_failed"
    assert exc_info.value.translation_placeholders == {
        "name": "plan.pdf",
        "status": "403",
    }
    assert not (tmp_path / "aula").exists()


@pytest.mark.parametrize("blocked", ["media_folder_is_a_file", "name_is_a_folder"])
async def test_download_attachment_save_fails(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
    blocked: str,
) -> None:
    """A file that cannot be written fails with the path it was meant for."""
    media_dir = tmp_path / "media"
    target = media_dir / "aula" / "123_plan.pdf"
    if blocked == "media_folder_is_a_file":
        media_dir.write_text("not a folder")
    else:
        (target / "taken").mkdir(parents=True)
    hass.config.media_dirs = {"local": str(media_dir)}
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(
            id=123,
            name="plan.pdf",
            file=AttachmentFile(id=11, url="https://example.com/plan.pdf"),
        )
    )
    mock_aula_client.download_file = AsyncMock(return_value=b"%PDF-1.7")

    with pytest.raises(HomeAssistantError) as exc_info:
        await _download(hass, thread_id="42", attachment_id=123)

    assert not isinstance(exc_info.value, ServiceValidationError)
    assert exc_info.value.translation_key == "attachment_save_failed"
    assert exc_info.value.translation_placeholders is not None
    assert exc_info.value.translation_placeholders["path"] == str(target)


async def test_download_attachment_without_media_folder(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
) -> None:
    """Without a media folder there is nowhere to save, so nothing is downloaded."""
    hass.config.media_dirs = {}
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.download_file = AsyncMock(return_value=b"content")

    with pytest.raises(HomeAssistantError) as exc_info:
        await _download(hass, thread_id="42", attachment_id=123)

    assert exc_info.value.translation_key == "no_media_folder"
    mock_aula_client.download_file.assert_not_awaited()


async def test_download_attachment_again_replaces_the_copy(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """Downloading the same attachment twice keeps one file, the newest."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(
            id=123,
            name="plan.pdf",
            file=AttachmentFile(id=11, url="https://example.com/plan.pdf"),
        )
    )
    mock_aula_client.download_file = AsyncMock(side_effect=[b"first", b"second"])

    await _download(hass, thread_id="42", attachment_id=123)
    await _download(hass, thread_id="42", attachment_id=123)

    assert [p.name for p in (tmp_path / "aula").iterdir()] == ["123_plan.pdf"]
    assert (tmp_path / "aula" / "123_plan.pdf").read_bytes() == b"second"


async def test_download_attachment_unknown_type_is_null(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """A name with no known type gives a null content_type, not a guess."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    mock_aula_client.get_messages_for_thread = _thread_with(
        Attachment(
            id=123,
            name="Invitation",
            file=AttachmentFile(id=11, url="https://example.com/invitation"),
        )
    )
    mock_aula_client.download_file = AsyncMock(return_value=b"content")

    response = await _download(hass, thread_id="42", attachment_id=123)

    assert response["content_type"] is None


async def _clear(hass: HomeAssistant, **data: Any) -> None:
    """Call clear_attachments with the given data."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_ATTACHMENTS,
        data,
        blocking=True,
    )


async def test_clear_attachments_removes_saved_files(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """Every saved attachment goes, and other media stays."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    folder = tmp_path / "aula"
    folder.mkdir()
    (folder / "123_plan.pdf").write_bytes(b"pdf")
    (folder / "124_theme_day.jpg").write_bytes(b"jpg")
    (tmp_path / "holiday.jpg").write_bytes(b"jpg")

    await _clear(hass)

    assert list(folder.iterdir()) == []
    assert (tmp_path / "holiday.jpg").exists()


async def test_clear_attachments_older_than_days(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """With days set, only files saved before that many days ago go."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    folder = tmp_path / "aula"
    folder.mkdir()
    now = time.time()
    for name, age_days in (("123_old.pdf", 40), ("124_recent.pdf", 5)):
        path = folder / name
        path.write_bytes(b"pdf")
        saved_at = now - age_days * 86400
        os.utime(path, (saved_at, saved_at))

    await _clear(hass, days=30)

    assert [path.name for path in folder.iterdir()] == ["124_recent.pdf"]


async def test_clear_attachments_before_anything_was_saved(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """Clearing with no attachment folder yet is not an error."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)

    await _clear(hass)

    assert not (tmp_path / "aula").exists()


async def test_clear_attachments_is_admin_only(
    hass: HomeAssistant,
    mock_aula_client: AsyncMock,
    hass_read_only_user: MockUser,
    tmp_path: Path,
) -> None:
    """A user who is not an administrator cannot delete saved attachments."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    await _setup_integration(hass, mock_aula_client)
    (tmp_path / "aula").mkdir()
    (tmp_path / "aula" / "123_plan.pdf").write_bytes(b"pdf")

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_ATTACHMENTS,
            {},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert (tmp_path / "aula" / "123_plan.pdf").exists()
