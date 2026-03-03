"""DataUpdateCoordinators for the Aula integration."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
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
from aula.models import MUTask, MUWeeklyPerson, Notification
from aula.models.meebook_weekplan import MeebookTask
from aula.models.mu_weekly_letter import MUWeeklyLetter
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CALENDAR_POLL_INTERVAL,
    DOMAIN,
    EASYIQ_POLL_INTERVAL,
    EVENT_NOTIFICATION,
    HUSKELISTEN_POLL_INTERVAL,
    LIBRARY_POLL_INTERVAL,
    LOGGER,
    MEEBOOK_POLL_INTERVAL,
    MU_TASKS_POLL_INTERVAL,
    MU_UGEPLAN_POLL_INTERVAL,
    NOTIFICATIONS_POLL_INTERVAL,
    PRESENCE_POLL_INTERVAL,
    WIDGET_BIBLIOTEKET,
    WIDGET_EASYIQ_WEEKPLAN,
    WIDGET_MIN_UDDANNELSE,
)
from .data import EasyIQChildData, HuskelistenChildData, LibraryChildData, WidgetContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from aula import AulaApiClient, Child, Profile
    from homeassistant.core import HomeAssistant

    from .data import AulaConfigEntry
    from .token_manager import AulaTokenManager


@asynccontextmanager
async def _aula_api_errors(
    token_manager: AulaTokenManager | None = None,
) -> AsyncIterator[None]:
    """Translate Aula API errors to Home Assistant exceptions."""
    try:
        yield
    except AulaAuthenticationError as err:
        if token_manager is not None:
            try:
                await token_manager.async_refresh_and_rebuild_client()
                msg = "Session refreshed, retrying"
                raise UpdateFailed(msg) from err
            except AulaAuthenticationError:
                pass
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from err
    except (AulaConnectionError, AulaServerError, AulaRateLimitError) as err:
        msg = f"Error communicating with Aula API: {err}"
        raise UpdateFailed(msg) from err


def _get_child_widget_id(child: Child) -> str:
    """Get the widget user ID for a child from its raw data."""
    # TODO(aula-package): Child does not expose userId as a public field.  # noqa: TD003, FIX002, E501
    # Add Child.user_id to the aula package, then replace this _raw access.
    raw = child._raw  # noqa: SLF001
    if raw:
        return str(raw["userId"])
    return str(child.id)


def _get_child_institution_code(child: Child) -> str:
    """Get the institution code for a child from its raw data."""
    # TODO(aula-package): Child does not expose institutionCode as a public field.  # noqa: TD003, FIX002, E501
    # Add Child.institution_code to the aula package, then replace this _raw access.
    raw = child._raw  # noqa: SLF001
    if raw:
        return raw.get("institutionProfile", {}).get("institutionCode", "")
    return ""


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
        token_manager: AulaTokenManager,
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
        self.token_manager = token_manager

    async def _async_update_data(self) -> dict[int, DailyOverview | None]:
        """Fetch presence data for all children."""
        async with _aula_api_errors(self.token_manager):
            results = await asyncio.gather(
                *(
                    self.client.get_daily_overview(child.id)
                    for child in self.profile.children
                )
            )
            return {
                child.id: result
                for child, result in zip(self.profile.children, results, strict=False)
            }


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
        token_manager: AulaTokenManager,
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
        self.token_manager = token_manager

    async def _async_update_data(self) -> dict[int, list[CalendarEvent]]:
        """Fetch calendar events for all children."""
        async with _aula_api_errors(self.token_manager):
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
            return result


class AulaNotificationsCoordinator(
    DataUpdateCoordinator[list[Notification]],
):
    """Coordinator for fetching notifications for the active profile."""

    config_entry: AulaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        token_manager: AulaTokenManager,
    ) -> None:
        """Initialize the notifications coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name="Aula Notifications",
            update_interval=timedelta(seconds=NOTIFICATIONS_POLL_INTERVAL),
        )
        self.client = client
        self.token_manager = token_manager
        self._known_ids: set[str] | None = None

    async def _async_update_data(self) -> list[Notification]:
        """Fetch notifications for the active profile."""
        async with _aula_api_errors(self.token_manager):
            notifications = await self.client.get_notifications_for_active_profile(
                limit=50
            )

        new_ids = {n.id for n in notifications}
        if self._known_ids is None:
            # First fetch — populate without firing events
            self._known_ids = new_ids
        else:
            for n in notifications:
                if n.id not in self._known_ids:
                    self.hass.bus.async_fire(
                        EVENT_NOTIFICATION,
                        {
                            "notification_id": n.id,
                            "title": n.title,
                            "module": n.module,
                            "event_type": n.event_type,
                            "related_child_name": n.related_child_name,
                            "created_at": n.created_at,
                            "is_read": n.is_read,
                        },
                    )
            self._known_ids = new_ids

        return notifications


class _AulaWidgetCoordinator(DataUpdateCoordinator):
    """Shared base for all widget coordinators."""

    config_entry: AulaConfigEntry

    def __init__(  # noqa: PLR0913
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        profile: Profile,
        widget_context: WidgetContext,
        token_manager: AulaTokenManager,
        *,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the widget coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=name,
            update_interval=update_interval,
        )
        self.client = client
        self.profile = profile
        self.widget_context = widget_context
        self.token_manager = token_manager
        # Pre-build name lookup for child matching
        self._child_by_name: dict[str, Child] = {
            child.name: child for child in profile.children
        }

    def _match_child(self, name: str) -> Child | None:
        """Match a name string to a child, with partial-match fallback."""
        child = self._child_by_name.get(name)
        if child:
            return child
        # Fallback: partial match
        for child_name, child in self._child_by_name.items():
            if child_name in name or name in child_name:
                return child
        return None


class AulaLibraryCoordinator(
    _AulaWidgetCoordinator,
    DataUpdateCoordinator[dict[int, LibraryChildData]],
):
    """Coordinator for fetching library loan data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        profile: Profile,
        widget_context: WidgetContext,
        token_manager: AulaTokenManager,
    ) -> None:
        """Initialize the library coordinator."""
        super().__init__(
            hass,
            client,
            profile,
            widget_context,
            token_manager,
            name="Aula Library",
            update_interval=timedelta(seconds=LIBRARY_POLL_INTERVAL),
        )

    async def _async_update_data(self) -> dict[int, LibraryChildData]:
        """Fetch library status and distribute to children."""
        async with _aula_api_errors(self.token_manager):
            status = await self.client.widgets.get_library_status(
                widget_id=WIDGET_BIBLIOTEKET,
                children=self.widget_context.child_filter,
                institutions=self.widget_context.institution_filter,
                session_uuid=self.widget_context.session_uuid,
            )

        result: dict[int, LibraryChildData] = {
            child.id: LibraryChildData() for child in self.profile.children
        }

        for loan in status.loans:
            child = self._match_child(loan.patron_display_name)
            if child and child.id in result:
                result[child.id].loans.append(loan)

        for loan in status.longterm_loans:
            child = self._match_child(loan.patron_display_name)
            if child and child.id in result:
                result[child.id].longterm_loans.append(loan)

        # Reservations don't have patron info, assign to all children
        for child_data in result.values():
            child_data.reservations = status.reservations

        return result


class AulaMUTasksCoordinator(
    _AulaWidgetCoordinator,
    DataUpdateCoordinator[dict[int, list[MUTask]]],
):
    """Coordinator for fetching Min Uddannelse tasks."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        profile: Profile,
        widget_context: WidgetContext,
        token_manager: AulaTokenManager,
    ) -> None:
        """Initialize the MU tasks coordinator."""
        super().__init__(
            hass,
            client,
            profile,
            widget_context,
            token_manager,
            name="Aula MU Tasks",
            update_interval=timedelta(seconds=MU_TASKS_POLL_INTERVAL),
        )

    async def _async_update_data(self) -> dict[int, list[MUTask]]:
        """Fetch MU tasks and distribute to children."""
        week = dt_util.now().strftime("%G-W%V")
        async with _aula_api_errors(self.token_manager):
            tasks = await self.client.widgets.get_mu_tasks(
                widget_id=WIDGET_MIN_UDDANNELSE,
                child_filter=self.widget_context.child_filter,
                institution_filter=self.widget_context.institution_filter,
                week=week,
                session_uuid=self.widget_context.session_uuid,
            )

        result: dict[int, list[MUTask]] = {
            child.id: [] for child in self.profile.children
        }

        for task in tasks:
            child = self._match_child(task.student_name)
            if child and child.id in result:
                result[child.id].append(task)

        return result


class AulaMUUgeplanCoordinator(
    _AulaWidgetCoordinator,
    DataUpdateCoordinator[dict[int, list[MUWeeklyLetter]]],
):
    """Coordinator for fetching Min Uddannelse weekly notes (ugenoter)."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        profile: Profile,
        widget_context: WidgetContext,
        token_manager: AulaTokenManager,
    ) -> None:
        """Initialize the MU ugeplan coordinator."""
        super().__init__(
            hass,
            client,
            profile,
            widget_context,
            token_manager,
            name="Aula MU Ugeplan",
            update_interval=timedelta(seconds=MU_UGEPLAN_POLL_INTERVAL),
        )

    async def _async_update_data(self) -> dict[int, list[MUWeeklyLetter]]:
        """Fetch MU weekly notes and distribute to children."""
        week = dt_util.now().strftime("%G-W%V")
        async with _aula_api_errors(self.token_manager):
            persons: list[MUWeeklyPerson] = await self.client.widgets.get_ugeplan(
                widget_id=WIDGET_MIN_UDDANNELSE,
                child_filter=self.widget_context.child_filter,
                institution_filter=self.widget_context.institution_filter,
                week=week,
                session_uuid=self.widget_context.session_uuid,
            )

        result: dict[int, list[MUWeeklyLetter]] = {
            child.id: [] for child in self.profile.children
        }

        for person in persons:
            child = self._match_child(person.name)
            if child and child.id in result:
                for institution in person.institutions:
                    result[child.id].extend(institution.letters)

        return result


class AulaEasyIQCoordinator(
    _AulaWidgetCoordinator,
    DataUpdateCoordinator[dict[int, EasyIQChildData]],
):
    """Coordinator for fetching EasyIQ weekplan and homework."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        profile: Profile,
        widget_context: WidgetContext,
        token_manager: AulaTokenManager,
    ) -> None:
        """Initialize the EasyIQ coordinator."""
        super().__init__(
            hass,
            client,
            profile,
            widget_context,
            token_manager,
            name="Aula EasyIQ",
            update_interval=timedelta(seconds=EASYIQ_POLL_INTERVAL),
        )

    async def _async_update_data(self) -> dict[int, EasyIQChildData]:
        """Fetch EasyIQ weekplan and homework per child."""
        week = dt_util.now().strftime("%G-W%V")

        async def _fetch_child(child: Child) -> tuple[int, EasyIQChildData]:
            child_id_str = _get_child_widget_id(child)
            inst_code = _get_child_institution_code(child)
            if not inst_code and self.widget_context.institution_filter:
                inst_code = self.widget_context.institution_filter[0]
            inst_filter = [inst_code]

            weekplan, homework = await asyncio.gather(
                self.client.widgets.get_easyiq_weekplan(
                    week=week,
                    session_uuid=self.widget_context.session_uuid,
                    institution_filter=inst_filter,
                    child_id=child_id_str,
                    widget_id=WIDGET_EASYIQ_WEEKPLAN,
                ),
                self.client.widgets.get_easyiq_homework(
                    week=week,
                    session_uuid=self.widget_context.session_uuid,
                    institution_filter=inst_filter,
                    child_id=child_id_str,
                ),
            )
            return child.id, EasyIQChildData(weekplan=weekplan, homework=homework)

        async with _aula_api_errors(self.token_manager):
            results = await asyncio.gather(
                *(_fetch_child(child) for child in self.profile.children)
            )

        return dict(results)


class AulaMeebookCoordinator(
    _AulaWidgetCoordinator,
    DataUpdateCoordinator[dict[int, list[MeebookTask]]],
):
    """Coordinator for fetching Meebook weekplan data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        profile: Profile,
        widget_context: WidgetContext,
        token_manager: AulaTokenManager,
    ) -> None:
        """Initialize the Meebook coordinator."""
        super().__init__(
            hass,
            client,
            profile,
            widget_context,
            token_manager,
            name="Aula Meebook",
            update_interval=timedelta(seconds=MEEBOOK_POLL_INTERVAL),
        )

    async def _async_update_data(self) -> dict[int, list[MeebookTask]]:
        """Fetch Meebook weekplan and distribute tasks to children."""
        week = dt_util.now().strftime("%G-W%V")
        async with _aula_api_errors(self.token_manager):
            student_plans = await self.client.widgets.get_meebook_weekplan(
                child_filter=self.widget_context.child_filter,
                institution_filter=self.widget_context.institution_filter,
                week=week,
                session_uuid=self.widget_context.session_uuid,
            )

        result: dict[int, list[MeebookTask]] = {
            child.id: [] for child in self.profile.children
        }

        for plan in student_plans:
            child = self._match_child(plan.name)
            if child and child.id in result:
                for day_plan in plan.week_plan:
                    result[child.id].extend(day_plan.tasks)

        return result


class AulaHuskelistenCoordinator(
    _AulaWidgetCoordinator,
    DataUpdateCoordinator[dict[int, HuskelistenChildData]],
):
    """Coordinator for fetching Huskelisten reminders."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AulaApiClient,
        profile: Profile,
        widget_context: WidgetContext,
        token_manager: AulaTokenManager,
    ) -> None:
        """Initialize the Huskelisten coordinator."""
        super().__init__(
            hass,
            client,
            profile,
            widget_context,
            token_manager,
            name="Aula Huskelisten",
            update_interval=timedelta(seconds=HUSKELISTEN_POLL_INTERVAL),
        )

    async def _async_update_data(self) -> dict[int, HuskelistenChildData]:
        """Fetch Huskelisten reminders and distribute to children."""
        now = dt_util.now()
        from_date = now.strftime("%Y-%m-%d")
        due_no_later_than = (now + timedelta(days=30)).strftime("%Y-%m-%d")

        async with _aula_api_errors(self.token_manager):
            user_reminders_list = await self.client.widgets.get_momo_reminders(
                children=self.widget_context.child_filter,
                institutions=self.widget_context.institution_filter,
                session_uuid=self.widget_context.session_uuid,
                from_date=from_date,
                due_no_later_than=due_no_later_than,
            )

        result: dict[int, HuskelistenChildData] = {
            child.id: HuskelistenChildData() for child in self.profile.children
        }

        for user_reminders in user_reminders_list:
            child = self._match_child(user_reminders.user_name)
            if child and child.id in result:
                result[child.id].team_reminders.extend(user_reminders.team_reminders)
                result[child.id].assignment_reminders.extend(
                    user_reminders.assignment_reminders
                )

        return result
