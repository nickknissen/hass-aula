"""Calendar platform for the Aula integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from aula import (
    AulaAuthenticationError,
    AulaConnectionError,
    AulaRateLimitError,
    AulaServerError,
)
from aula import CalendarEvent as AulaCalendarEvent
from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from .const import PARALLEL_UPDATES as PARALLEL_UPDATES  # noqa: PLC0414
from .entity import AulaEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AulaCalendarCoordinator
    from .data import AulaConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AulaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aula calendar entities."""
    coordinator = entry.runtime_data.calendar_coordinator
    profile = entry.runtime_data.profile

    async_add_entities(
        AulaCalendarEntity(coordinator=coordinator, child=child)
        for child in profile.children
    )


def _convert_event(event: AulaCalendarEvent) -> CalendarEvent:
    """Convert an Aula calendar event to a HA calendar event."""
    description_parts: list[str] = []
    if event.teacher_name:
        description_parts.append(f"Teacher: {event.teacher_name}")
    if event.has_substitute and event.substitute_name:
        description_parts.append(f"Substitute: {event.substitute_name}")
    if event.location:
        description_parts.append(f"Location: {event.location}")

    return CalendarEvent(
        summary=event.title,
        start=event.start_datetime,
        end=event.end_datetime,
        description="\n".join(description_parts) if description_parts else None,
        location=event.location,
    )


class AulaCalendarEntity(AulaEntity, CalendarEntity):
    """Representation of an Aula school calendar."""

    _attr_translation_key = "school_calendar"

    def __init__(
        self,
        coordinator: AulaCalendarCoordinator,
        child: Any,
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
        now = datetime.now().astimezone()
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
            events = await self.coordinator.client.get_calendar_events(
                institution_profile_ids=[self._child.id],
                start=start_date,
                end=end_date,
            )
        except (
            AulaAuthenticationError,
            AulaConnectionError,
            AulaServerError,
            AulaRateLimitError,
        ):
            return []

        return [_convert_event(event) for event in events]
