"""The Aula integration for Home Assistant."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aula import (
    AulaAuthenticationError,
    AulaConnectionError,
    AulaRateLimitError,
    AulaServerError,
    create_client,
)
from aula.http_httpx import HttpxHttpClient
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_TOKEN_DATA,
    CONF_WIDGETS,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    WIDGET_BIBLIOTEKET,
    WIDGET_EASYIQ,
    WIDGET_EASYIQ_HOMEWORK,
    WIDGET_EASYIQ_WEEKPLAN,
    WIDGET_HUSKELISTEN,
    WIDGET_MEEBOOK,
    WIDGET_MIN_UDDANNELSE_TASKS,
    WIDGET_MIN_UDDANNELSE_UGEPLAN,
)
from .coordinator import (
    AulaCalendarCoordinator,
    AulaEasyIQCoordinator,
    AulaHuskelistenCoordinator,
    AulaLibraryCoordinator,
    AulaMeebookCoordinator,
    AulaMUTasksCoordinator,
    AulaMUUgeplanCoordinator,
    AulaNotificationsCoordinator,
    AulaPresenceCoordinator,
    _get_child_institution_code,
    _get_child_widget_id,
)
from .data import AulaRuntimeData, WidgetContext
from .token_manager import AulaTokenManager

if TYPE_CHECKING:
    from aula import AulaApiClient, Profile
    from homeassistant.core import HomeAssistant

    from .data import AulaConfigEntry

# All widget/feature IDs that require building a widget context.
_ALL_WIDGET_IDS = (
    WIDGET_BIBLIOTEKET,
    WIDGET_MIN_UDDANNELSE_TASKS,
    WIDGET_MIN_UDDANNELSE_UGEPLAN,
    WIDGET_EASYIQ,
    WIDGET_EASYIQ_WEEKPLAN,
    WIDGET_EASYIQ_HOMEWORK,
    WIDGET_MEEBOOK,
    WIDGET_HUSKELISTEN,
)


@dataclass
class _WidgetCoordinators:
    """Container for optional widget coordinators."""

    library: AulaLibraryCoordinator | None = None
    mu_tasks: AulaMUTasksCoordinator | None = None
    mu_ugeplan: AulaMUUgeplanCoordinator | None = None
    easyiq: AulaEasyIQCoordinator | None = None
    meebook: AulaMeebookCoordinator | None = None
    huskelisten: AulaHuskelistenCoordinator | None = None


def is_widget_enabled(entry: AulaConfigEntry, widget_id: str) -> bool:
    """Return True if the given widget ID is selected in the config entry."""
    return widget_id in entry.data.get(CONF_WIDGETS, [])


def _create_http_client(cookies: dict[str, str]) -> HttpxHttpClient:
    """Create HTTP client in a thread to avoid blocking SSL cert loading."""
    return HttpxHttpClient(cookies=cookies)


async def _build_widget_context(
    client: AulaApiClient, profile: Profile
) -> WidgetContext:
    """Build the widget context from profile data."""
    profile_context = await client.get_profile_context()
    session_uuid = str(profile_context["data"]["userId"])

    child_filter: list[str] = []
    institution_codes: set[str] = set()

    for child in profile.children:
        child_filter.append(_get_child_widget_id(child))
        inst_code = _get_child_institution_code(child)
        if inst_code:
            institution_codes.add(inst_code)

    return WidgetContext(
        child_filter=child_filter,
        institution_filter=sorted(institution_codes),
        session_uuid=session_uuid,
    )


async def _try_build_widget_context(
    entry: AulaConfigEntry,
    client: AulaApiClient,
    profile: Profile,
) -> WidgetContext | None:
    """Build widget context if any widget is enabled, else return None."""
    if not any(is_widget_enabled(entry, w) for w in _ALL_WIDGET_IDS):
        return None

    try:
        return await _build_widget_context(client, profile)
    except (
        AulaAuthenticationError,
        AulaConnectionError,
        AulaServerError,
        AulaRateLimitError,
    ) as err:
        LOGGER.warning("Failed to build widget context, skipping widgets: %s", err)
        return None


def _create_widget_coordinators(  # noqa: PLR0913
    hass: HomeAssistant,
    entry: AulaConfigEntry,
    client: AulaApiClient,
    profile: Profile,
    widget_context: WidgetContext,
    token_manager: AulaTokenManager,
) -> _WidgetCoordinators:
    """Create widget coordinators for enabled widgets."""
    wc = _WidgetCoordinators()

    if is_widget_enabled(entry, WIDGET_BIBLIOTEKET):
        wc.library = AulaLibraryCoordinator(
            hass, client, profile, widget_context, token_manager
        )

    if is_widget_enabled(entry, WIDGET_MIN_UDDANNELSE_TASKS):
        wc.mu_tasks = AulaMUTasksCoordinator(
            hass, client, profile, widget_context, token_manager
        )

    if is_widget_enabled(entry, WIDGET_MIN_UDDANNELSE_UGEPLAN):
        wc.mu_ugeplan = AulaMUUgeplanCoordinator(
            hass, client, profile, widget_context, token_manager
        )

    if (
        is_widget_enabled(entry, WIDGET_EASYIQ)
        or is_widget_enabled(entry, WIDGET_EASYIQ_WEEKPLAN)
        or is_widget_enabled(entry, WIDGET_EASYIQ_HOMEWORK)
    ):
        wc.easyiq = AulaEasyIQCoordinator(
            hass, client, profile, widget_context, token_manager
        )

    if is_widget_enabled(entry, WIDGET_MEEBOOK):
        wc.meebook = AulaMeebookCoordinator(
            hass, client, profile, widget_context, token_manager
        )

    if is_widget_enabled(entry, WIDGET_HUSKELISTEN):
        wc.huskelisten = AulaHuskelistenCoordinator(
            hass, client, profile, widget_context, token_manager
        )

    return wc


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AulaConfigEntry,
) -> bool:
    """Set up Aula from a config entry."""
    token_manager = AulaTokenManager(hass, entry)
    token_data = entry.data[CONF_TOKEN_DATA]
    cookies = token_data.get("cookies", {})

    http_client = await hass.async_add_executor_job(_create_http_client, cookies)
    try:
        client = await create_client(token_data, http_client=http_client)
    except AulaAuthenticationError:
        await http_client.close()
        try:
            client, _new_token_data = await token_manager.async_refresh_token()
        except AulaAuthenticationError as refresh_err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from refresh_err
    except (AulaConnectionError, AulaServerError, AulaRateLimitError) as err:
        await http_client.close()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
        ) from err

    try:
        profile = await client.get_profile()
    except AulaAuthenticationError:
        await client.close()
        try:
            client, _new_token_data = await token_manager.async_refresh_token()
            profile = await client.get_profile()
        except AulaAuthenticationError as refresh_err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from refresh_err
        except (AulaConnectionError, AulaServerError, AulaRateLimitError) as err:
            await client.close()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
            ) from err
    except (AulaConnectionError, AulaServerError, AulaRateLimitError) as err:
        await client.close()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
        ) from err

    presence_coordinator = AulaPresenceCoordinator(hass, client, profile, token_manager)
    calendar_coordinator = AulaCalendarCoordinator(hass, client, profile, token_manager)
    notifications_coordinator = AulaNotificationsCoordinator(
        hass, client, token_manager
    )

    # Create widget coordinators if any widgets are enabled
    wc = _WidgetCoordinators()
    widget_context = await _try_build_widget_context(entry, client, profile)
    if widget_context:
        wc = _create_widget_coordinators(
            hass, entry, client, profile, widget_context, token_manager
        )

    # First refresh all coordinators in parallel
    first_refreshes = [
        presence_coordinator.async_config_entry_first_refresh(),
        calendar_coordinator.async_config_entry_first_refresh(),
        notifications_coordinator.async_config_entry_first_refresh(),
    ]
    first_refreshes.extend(
        coord.async_config_entry_first_refresh()
        for coord in (
            wc.library,
            wc.mu_tasks,
            wc.mu_ugeplan,
            wc.easyiq,
            wc.meebook,
            wc.huskelisten,
        )
        if coord
    )

    await asyncio.gather(*first_refreshes)

    entry.runtime_data = AulaRuntimeData(
        client=client,
        token_manager=token_manager,
        profile=profile,
        presence_coordinator=presence_coordinator,
        calendar_coordinator=calendar_coordinator,
        notifications_coordinator=notifications_coordinator,
        library_coordinator=wc.library,
        mu_tasks_coordinator=wc.mu_tasks,
        mu_ugeplan_coordinator=wc.mu_ugeplan,
        easyiq_coordinator=wc.easyiq,
        meebook_coordinator=wc.meebook,
        huskelisten_coordinator=wc.huskelisten,
    )

    _async_remove_stale_devices(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: AulaConfigEntry,
) -> bool:
    """Unload an Aula config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok


def _async_remove_stale_devices(
    hass: HomeAssistant,
    entry: AulaConfigEntry,
) -> None:
    """Remove devices for children no longer in the profile."""
    device_registry = dr.async_get(hass)
    profile = entry.runtime_data.profile
    current_ids = {(DOMAIN, str(child.id)) for child in profile.children}
    current_ids.add((DOMAIN, f"profile_{profile.profile_id}"))

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if not device_entry.identifiers & current_ids:
            LOGGER.info(
                "Removing stale device %s (%s)",
                device_entry.name,
                device_entry.id,
            )
            device_registry.async_remove_device(device_entry.id)
