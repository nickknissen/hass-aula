"""DataUpdateCoordinators for the Aula integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING

from aula import (
    AulaAuthenticationError,
    AulaConnectionError,
    AulaRateLimitError,
    AulaServerError,
    CalendarEvent,
    DailyOverview,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CALENDAR_POLL_INTERVAL, LOGGER, PRESENCE_POLL_INTERVAL

if TYPE_CHECKING:
    from aula import AulaApiClient, Profile
    from homeassistant.core import HomeAssistant

    from .data import AulaConfigEntry


class AulaPresenceCoordinator(
    DataUpdateCoordinator[dict[int, DailyOverview | None]],
):
    """Coordinator for fetching presence data for all children."""

    config_entry: AulaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        profile: Profile,
    ) -> None:
        """Initialize the presence coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name="Aula Presence",
            update_interval=timedelta(seconds=PRESENCE_POLL_INTERVAL),
        )
        self.client = client
        self.profile = profile

    async def _async_update_data(self) -> dict[int, DailyOverview | None]:
        """Fetch presence data for all children."""
        try:
            results = await asyncio.gather(
                *(self.client.get_daily_overview(child.id) for child in self.profile.children)
            )
            data: dict[int, DailyOverview | None] = {
                child.id: result
                for child, result in zip(self.profile.children, results)
            }
        except AulaAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain="hass_aula",
                translation_key="auth_failed",
            ) from err
        except (AulaConnectionError, AulaServerError, AulaRateLimitError) as err:
            msg = f"Error communicating with Aula API: {err}"
            raise UpdateFailed(msg) from err
        else:
            return data


class AulaCalendarCoordinator(
    DataUpdateCoordinator[dict[int, list[CalendarEvent]]],
):
    """Coordinator for fetching calendar events for all children."""

    config_entry: AulaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        profile: Profile,
    ) -> None:
        """Initialize the calendar coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name="Aula Calendar",
            update_interval=timedelta(seconds=CALENDAR_POLL_INTERVAL),
        )
        self.client = client
        self.profile = profile

    async def _async_update_data(self) -> dict[int, list[CalendarEvent]]:
        """Fetch calendar events for all children."""
        try:
            now = dt_util.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=30)

            all_child_ids = [child.id for child in self.profile.children]
            events = await self.client.get_calendar_events(
                institution_profile_ids=all_child_ids,
                start=start,
                end=end,
            )

            result: dict[int, list[CalendarEvent]] = {
                child.id: [] for child in self.profile.children
            }
            for event in events:
                if event.belongs_to in result:
                    result[event.belongs_to].append(event)
        except AulaAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain="hass_aula",
                translation_key="auth_failed",
            ) from err
        except (AulaConnectionError, AulaServerError, AulaRateLimitError) as err:
            msg = f"Error communicating with Aula API: {err}"
            raise UpdateFailed(msg) from err
        else:
            return result
