"""The Aula integration for Home Assistant."""

from __future__ import annotations

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

from .const import CONF_TOKEN_DATA, DOMAIN, LOGGER, PLATFORMS
from .coordinator import AulaCalendarCoordinator, AulaPresenceCoordinator
from .data import AulaRuntimeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import AulaConfigEntry


def _create_http_client(cookies: dict) -> HttpxHttpClient:
    """
    Create HTTP client in a thread.

    Avoids blocking SSL cert loading on the event loop.
    """
    return HttpxHttpClient(cookies=cookies)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AulaConfigEntry,
) -> bool:
    """Set up Aula from a config entry."""
    token_data = entry.data[CONF_TOKEN_DATA]
    cookies = token_data.get("cookies", {})

    try:
        http_client = await hass.async_add_executor_job(_create_http_client, cookies)
        client = await create_client(token_data, http_client=http_client)
    except AulaAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from err
    except (AulaConnectionError, AulaServerError, AulaRateLimitError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
        ) from err

    try:
        profile = await client.get_profile()
    except AulaAuthenticationError as err:
        await client.close()
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from err
    except (AulaConnectionError, AulaServerError, AulaRateLimitError) as err:
        await client.close()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
        ) from err

    presence_coordinator = AulaPresenceCoordinator(hass, client, profile)
    calendar_coordinator = AulaCalendarCoordinator(hass, client, profile)

    await presence_coordinator.async_config_entry_first_refresh()
    await calendar_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AulaRuntimeData(
        client=client,
        profile=profile,
        presence_coordinator=presence_coordinator,
        calendar_coordinator=calendar_coordinator,
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
    current_child_ids = {(DOMAIN, str(child.id)) for child in profile.children}

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if not device_entry.identifiers & current_child_ids:
            LOGGER.info(
                "Removing stale device %s (%s)",
                device_entry.name,
                device_entry.id,
            )
            device_registry.async_remove_device(device_entry.id)
