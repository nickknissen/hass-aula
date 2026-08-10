"""Actions for the Aula integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
from aula import (
    AulaAuthenticationError,
    AulaConnectionError,
    AulaRateLimitError,
    AulaServerError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (
    ACTIVITY_TYPE_PICKED_UP_BY,
    ACTIVITY_TYPES,
    ATTR_ACTIVITY_TYPE,
    ATTR_COMMENT,
    ATTR_DATE,
    ATTR_ENTRY_TIME,
    ATTR_EXIT_TIME,
    ATTR_EXIT_WITH,
    ATTR_EXPIRES_AT,
    ATTR_REPEAT,
    DOMAIN,
    LOGGER,
    REPEAT_NEVER,
    REPEAT_PATTERNS,
    SERVICE_UPDATE_PRESENCE,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from datetime import date, datetime, time

    from aula import ActivityType, AulaApiClient
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.device_registry import DeviceEntry

    from .data import AulaConfigEntry

UPDATE_PRESENCE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_AREA_ID, default=list): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_DEVICE_ID, default=list): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(ATTR_ENTITY_ID, default=list): cv.entity_ids,
        vol.Required(ATTR_ENTRY_TIME): cv.time,
        vol.Required(ATTR_EXIT_TIME): cv.time,
        vol.Optional(ATTR_DATE): cv.date,
        vol.Optional(ATTR_ACTIVITY_TYPE, default=ACTIVITY_TYPE_PICKED_UP_BY): vol.In(
            ACTIVITY_TYPES
        ),
        vol.Optional(ATTR_EXIT_WITH): cv.string,
        vol.Optional(ATTR_COMMENT): cv.string,
        vol.Optional(ATTR_REPEAT, default=REPEAT_NEVER): vol.In(REPEAT_PATTERNS),
        vol.Optional(ATTR_EXPIRES_AT): cv.datetime,
    }
)


@dataclass(frozen=True, kw_only=True)
class _PresenceUpdate:
    """A validated update_presence payload, ready for the aula package."""

    by_date: date
    entry_time: str
    exit_time: str
    activity_type: ActivityType
    exit_with: str | None
    comment: str | None
    repeat_pattern: str
    expires_at: str | None


@callback
def _child_id_from_device(device: DeviceEntry) -> int | None:
    """
    Return the child's institution profile ID for an Aula child device.

    Child devices are identified by ``(DOMAIN, "<child.id>")``; the account
    device uses ``(DOMAIN, "profile_<id>")`` and yields None.
    """
    for domain, identifier in device.identifiers:
        if domain == DOMAIN and identifier.isdigit():
            return int(identifier)
    return None


@callback
def _async_invalid_target(target: str) -> ServiceValidationError:
    """Build the error raised for a target that is not an Aula child."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_target",
        translation_placeholders={"target": target},
    )


@callback
def _async_resolve_device_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Expand the action's target into a set of device IDs."""
    device_ids: set[str] = set(call.data[ATTR_DEVICE_ID])

    entity_reg = er.async_get(hass)
    for entity_id in call.data[ATTR_ENTITY_ID]:
        entity_entry = entity_reg.async_get(entity_id)
        if entity_entry is None or entity_entry.device_id is None:
            raise _async_invalid_target(entity_id)
        device_ids.add(entity_entry.device_id)

    # Areas may hold unrelated devices, so filter rather than reject.
    device_reg = dr.async_get(hass)
    for area_id in call.data[ATTR_AREA_ID]:
        device_ids.update(
            device.id
            for device in dr.async_entries_for_area(device_reg, area_id)
            if _child_id_from_device(device) is not None
        )

    return device_ids


@callback
def _async_entry_for_device(
    hass: HomeAssistant, device: DeviceEntry
) -> AulaConfigEntry:
    """Return the loaded Aula config entry that owns a device."""
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            continue
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"target": entry.title},
            )
        return cast("AulaConfigEntry", entry)

    raise _async_invalid_target(device.name or device.id)


@callback
def _async_resolve_targets(
    hass: HomeAssistant, call: ServiceCall
) -> list[tuple[AulaConfigEntry, list[int]]]:
    """Resolve the action's target into children grouped by config entry."""
    device_reg = dr.async_get(hass)
    grouped: dict[str, tuple[AulaConfigEntry, list[int]]] = {}

    for device_id in _async_resolve_device_ids(hass, call):
        device = device_reg.async_get(device_id)
        child_id = _child_id_from_device(device) if device is not None else None
        if device is None or child_id is None:
            raise _async_invalid_target(device_id)

        entry = _async_entry_for_device(hass, device)
        _, child_ids = grouped.setdefault(entry.entry_id, (entry, []))
        if child_id not in child_ids:
            child_ids.append(child_id)

    if not grouped:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_target",
        )

    return list(grouped.values())


def _build_update(call: ServiceCall) -> _PresenceUpdate:
    """Validate the call data and convert it to aula package arguments."""
    entry_time: time = call.data[ATTR_ENTRY_TIME]
    exit_time: time = call.data[ATTR_EXIT_TIME]
    if entry_time >= exit_time:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_time_range",
            translation_placeholders={
                "entry_time": entry_time.strftime("%H:%M"),
                "exit_time": exit_time.strftime("%H:%M"),
            },
        )

    activity_type = ACTIVITY_TYPES[call.data[ATTR_ACTIVITY_TYPE]]
    exit_with: str | None = call.data.get(ATTR_EXIT_WITH)
    if activity_type.requires_exit_with and not exit_with:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="exit_with_required",
            translation_placeholders={"activity_type": activity_type.display_name},
        )

    expires_at: datetime | None = call.data.get(ATTR_EXPIRES_AT)
    return _PresenceUpdate(
        by_date=call.data.get(ATTR_DATE) or dt_util.now().date(),
        entry_time=entry_time.strftime("%H:%M"),
        exit_time=exit_time.strftime("%H:%M"),
        activity_type=activity_type,
        exit_with=exit_with,
        comment=call.data.get(ATTR_COMMENT),
        repeat_pattern=REPEAT_PATTERNS[call.data[ATTR_REPEAT]],
        expires_at=expires_at.isoformat() if expires_at is not None else None,
    )


async def _async_call_aula[T](
    entry: AulaConfigEntry,
    operation: Callable[[AulaApiClient], Coroutine[Any, Any, T]],
) -> T:
    """Run an Aula API operation, refreshing the session once on auth failure."""
    runtime = entry.runtime_data
    try:
        try:
            return await operation(runtime.client)
        except AulaAuthenticationError:
            LOGGER.debug("Aula rejected the action, refreshing session and retrying")
            client = await runtime.token_manager.async_refresh_and_rebuild_client()
            return await operation(client)
    except AulaAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from err
    except (AulaConnectionError, AulaServerError, AulaRateLimitError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="action_failed",
            translation_placeholders={"error": str(err)},
        ) from err


async def _async_template_ids(
    client: AulaApiClient,
    child_ids: list[int],
    by_date: date,
) -> dict[int, int]:
    """
    Map child ID to the existing day-template ID for a date, when there is one.

    Passing the existing ID makes Aula update that template instead of adding
    another one for the same day.
    """
    templates = await client.get_presence_templates(
        institution_profile_ids=child_ids,
        from_date=by_date,
        to_date=by_date,
    )

    target = by_date.isoformat()
    result: dict[int, int] = {}
    for week_template in templates:
        profile = week_template.institution_profile
        if profile is None or profile.id is None:
            continue
        for day in week_template.day_templates:
            if day.id is not None and day.by_date and day.by_date[:10] == target:
                result[profile.id] = day.id

    return result


async def _async_apply(
    entry: AulaConfigEntry,
    child_ids: list[int],
    update: _PresenceUpdate,
) -> None:
    """Write one presence update to every targeted child of a config entry."""

    async def operation(client: AulaApiClient) -> None:
        # Re-resolved on retry, so replaying the whole operation stays idempotent.
        template_ids = await _async_template_ids(client, child_ids, update.by_date)
        results = await asyncio.gather(
            *(
                client.update_presence_template(
                    institution_profile_id=child_id,
                    by_date=update.by_date,
                    entry_time=update.entry_time,
                    exit_time=update.exit_time,
                    activity_type=update.activity_type,
                    exit_with=update.exit_with,
                    comment=update.comment,
                    template_id=template_ids.get(child_id),
                    repeat_pattern=update.repeat_pattern,
                    expires_at=update.expires_at,
                )
                for child_id in child_ids
            ),
            return_exceptions=True,
        )

        failure: BaseException | None = None
        for child_id, result in zip(child_ids, results, strict=True):
            if isinstance(result, BaseException):
                LOGGER.error(
                    "Failed to update presence for child %s on %s: %s",
                    child_id,
                    update.by_date,
                    result,
                )
                failure = failure or result
            else:
                LOGGER.debug(
                    "Updated presence template for child %s on %s",
                    child_id,
                    update.by_date,
                )
        if failure is not None:
            raise failure

    await _async_call_aula(entry, operation)
    await entry.runtime_data.presence_coordinator.async_request_refresh()


async def _async_update_presence(call: ServiceCall) -> None:
    """Handle the update_presence action."""
    update = _build_update(call)
    for entry, child_ids in _async_resolve_targets(call.hass, call):
        await _async_apply(entry, child_ids, update)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Aula actions."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_PRESENCE,
        _async_update_presence,
        schema=UPDATE_PRESENCE_SCHEMA,
    )
