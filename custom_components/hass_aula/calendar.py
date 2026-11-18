"""Calendar platform for the Aula integration."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from aula import ActivityType, HttpRequestError
from aula import CalendarEvent as AulaCalendarEvent
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from .const import ACTIVITY_TYPES, DOMAIN
from .const import PARALLEL_UPDATES as PARALLEL_UPDATES  # noqa: PLC0414
from .coordinator import (
    AulaCalendarCoordinator,
    AulaPresenceCoordinator,
    day_templates_by_child,
)
from .entity import AulaEntity

if TYPE_CHECKING:
    from collections.abc import Mapping

    from aula import Child
    from aula.models.presence_template import DayTemplate
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import AulaConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AulaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aula calendar entities."""
    runtime = entry.runtime_data
    children = runtime.profile.children
    activity_labels = await _async_activity_labels(hass)

    async_add_entities(
        [
            *(
                AulaCalendarEntity(
                    coordinator=runtime.calendar_coordinator, child=child
                )
                for child in children
            ),
            *(
                AulaPresencePlanCalendar(
                    coordinator=runtime.presence_coordinator,
                    child=child,
                    activity_labels=activity_labels,
                )
                for child in children
            ),
        ]
    )


async def _async_activity_labels(hass: HomeAssistant) -> dict[ActivityType, str]:
    """Name each activity type as the update_presence action does, in HA's language."""
    translations = await async_get_translations(
        hass, hass.config.language, "selector", {DOMAIN}
    )
    prefix = f"component.{DOMAIN}.selector.activity_type.options"
    return {
        activity: translations.get(f"{prefix}.{option}", activity.display_name)
        for option, activity in ACTIVITY_TYPES.items()
    }


def _planned_time(value: str | None, *, is_placeholder: bool) -> time | None:
    """Return a planned time, or None when Aula only filled in a placeholder."""
    if is_placeholder or not value:
        return None
    return dt_util.parse_time(value)


def _start_of_this_week() -> date:
    today = dt_util.now().date()
    return today - timedelta(days=today.weekday())


def _plan_event(
    day: DayTemplate, activity_labels: Mapping[ActivityType, str]
) -> CalendarEvent | None:
    """Turn a planned day into an event, or None when the day holds no plan."""
    if day.is_on_vacation or not day.by_date:
        return None
    try:
        activity = ActivityType(day.activity_type)
    except ValueError:
        return None

    title = activity_labels[activity]
    if activity.requires_exit_with and day.exit_with:
        title = f"{title} {day.exit_with}"
    entry = _planned_time(day.entry_time, is_placeholder=day.is_default_entry_time)
    leave = _planned_time(day.exit_time, is_placeholder=day.is_default_exit_time)
    if activity is ActivityType.SELF_DECIDER:
        window_start = _planned_time(
            day.self_decider_start_time, is_placeholder=day.is_default_exit_time
        )
        window_end = _planned_time(
            day.self_decider_end_time, is_placeholder=day.is_default_exit_time
        )
        if window_start and window_end and window_start < window_end:
            title = f"{title} {window_start:%H:%M}-{window_end:%H:%M}"
        leave = window_end or leave

    on = date.fromisoformat(day.by_date)
    if entry and leave and entry < leave:
        time_zone = dt_util.get_default_time_zone()
        start: date | datetime = datetime.combine(on, entry, tzinfo=time_zone)
        end: date | datetime = datetime.combine(on, leave, tzinfo=time_zone)
    elif entry or leave:
        start, end = on, on + timedelta(days=1)
    else:
        return None

    return CalendarEvent(
        summary=title, start=start, end=end, description=day.comment or None
    )


def _names(names: list[str], fallback: str | None) -> list[str]:
    """Return the full name list, falling back to the single-name field."""
    if names:
        return names
    return [fallback] if fallback else []


def _convert_event(event: AulaCalendarEvent) -> CalendarEvent:
    """Convert an Aula calendar event to a HA calendar event."""
    description_parts: list[str] = []
    # A lesson often has more than one adult attached; aula merges the rows
    # Aula sends per adult and lists them all here, so name every one of them
    # rather than only whoever happened to come first.
    teachers = _names(event.teacher_names, event.teacher_name)
    if teachers:
        label = "Teachers" if len(teachers) > 1 else "Teacher"
        description_parts.append(f"{label}: {', '.join(teachers)}")
    if event.has_substitute:
        substitutes = _names(event.substitute_names, event.substitute_name)
        if substitutes:
            label = "Substitutes" if len(substitutes) > 1 else "Substitute"
            description_parts.append(f"{label}: {', '.join(substitutes)}")
    if event.location:
        description_parts.append(f"Location: {event.location}")

    return CalendarEvent(
        summary=event.title,
        start=event.start_datetime,
        end=event.end_datetime,
        description="\n".join(description_parts) if description_parts else None,
        location=event.location,
    )


class AulaCalendarEntity(AulaEntity[AulaCalendarCoordinator], CalendarEntity):
    """Representation of an Aula school calendar."""

    _attr_translation_key = "school_calendar"

    def __init__(
        self,
        coordinator: AulaCalendarCoordinator,
        child: Child,
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{child.id}_school_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        events = self.coordinator.data.get(self._child.id, [])
        if not events:
            return None
        now = dt_util.now()
        upcoming = [e for e in events if e.end_datetime > now]
        if not upcoming:
            return None
        upcoming.sort(key=lambda e: e.start_datetime)
        return _convert_event(upcoming[0])

    async def async_get_events(
        self,
        hass: HomeAssistant,  # noqa: ARG002
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a date range."""
        try:
            calendars = await self.coordinator.client.get_calendar_events_by_child(
                [self._child.id], start_date, end_date
            )
        except HttpRequestError:
            return []

        return [_convert_event(event) for event in calendars.get(self._child.id, [])]


class AulaPresencePlanCalendar(AulaEntity[AulaPresenceCoordinator], CalendarEntity):
    """A child's planned drop-off and pick-up, one event per planned day."""

    _attr_translation_key = "presence_plan"

    def __init__(
        self,
        coordinator: AulaPresenceCoordinator,
        child: Child,
        activity_labels: Mapping[ActivityType, str],
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator, child)
        self._activity_labels = activity_labels
        self._attr_unique_id = f"{child.id}_presence_plan"

    def _events(self, days: list[DayTemplate]) -> list[CalendarEvent]:
        events = (_plan_event(day, self._activity_labels) for day in days)
        return sorted(filter(None, events), key=lambda e: e.start_datetime_local)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next planned day."""
        child_data = self.coordinator.data.get(self._child.id)
        if child_data is None:
            return None
        now = dt_util.now()
        return next(
            (
                e
                for e in self._events(child_data.planned_days)
                if e.end_datetime_local > now
            ),
            None,
        )

    async def async_get_events(
        self,
        hass: HomeAssistant,  # noqa: ARG002
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return the planned days within a date range."""
        # Aula refuses the whole request when it reaches back before this week.
        from_date = max(start_date.date(), _start_of_this_week())
        if end_date.date() < from_date:
            return []
        try:
            templates = await self.coordinator.client.get_presence_templates(
                institution_profile_ids=[self._child.id],
                from_date=from_date,
                to_date=end_date.date(),
            )
        except HttpRequestError:
            return []

        days = day_templates_by_child(templates).get(self._child.id, [])
        return [
            e
            for e in self._events(days)
            if e.start_datetime_local < end_date and e.end_datetime_local > start_date
        ]
