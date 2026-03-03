"""Sensor platform for the Aula integration."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from .const import PARALLEL_UPDATES as PARALLEL_UPDATES  # noqa: PLC0414
from .entity import AulaAccountEntity, AulaEntity

if TYPE_CHECKING:
    from aula import Child, DailyOverview, Profile
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import (
        AulaEasyIQCoordinator,
        AulaHuskelistenCoordinator,
        AulaLibraryCoordinator,
        AulaMeebookCoordinator,
        AulaMUTasksCoordinator,
        AulaNotificationsCoordinator,
        AulaPresenceCoordinator,
    )
    from .data import (
        AulaConfigEntry,
        EasyIQChildData,
        HuskelistenChildData,
        LibraryChildData,
    )

MAX_ATTRIBUTE_ITEMS = 20

PRESENCE_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="presence_status",
    translation_key="presence_status",
    device_class=SensorDeviceClass.ENUM,
    options=[
        "not_present",
        "sick",
        "reported_absent",
        "present",
        "fieldtrip",
        "sleeping",
        "spare_time_activity",
        "physical_placement",
        "checked_out",
    ],
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AulaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aula sensors."""
    runtime = entry.runtime_data
    profile = runtime.profile

    entities: list[SensorEntity] = [
        AulaPresenceSensor(coordinator=runtime.presence_coordinator, child=child)
        for child in profile.children
    ]
    entities.append(
        AulaNotificationsSensor(
            coordinator=runtime.notifications_coordinator, profile=profile
        )
    )

    # Widget sensors — only created if the coordinator exists
    if runtime.library_coordinator:
        entities.extend(
            AulaLibraryLoansSensor(coordinator=runtime.library_coordinator, child=child)
            for child in profile.children
        )

    if runtime.mu_tasks_coordinator:
        entities.extend(
            AulaMUTasksSensor(coordinator=runtime.mu_tasks_coordinator, child=child)
            for child in profile.children
        )

    if runtime.easyiq_coordinator:
        for child in profile.children:
            entities.extend(
                [
                    AulaEasyIQWeekplanSensor(
                        coordinator=runtime.easyiq_coordinator, child=child
                    ),
                    AulaEasyIQHomeworkSensor(
                        coordinator=runtime.easyiq_coordinator, child=child
                    ),
                ]
            )

    if runtime.meebook_coordinator:
        entities.extend(
            AulaMeebookWeekplanSensor(
                coordinator=runtime.meebook_coordinator, child=child
            )
            for child in profile.children
        )

    if runtime.huskelisten_coordinator:
        entities.extend(
            AulaHuskelistenSensor(
                coordinator=runtime.huskelisten_coordinator, child=child
            )
            for child in profile.children
        )

    async_add_entities(entities)


class AulaPresenceSensor(AulaEntity, SensorEntity):
    """Representation of an Aula presence sensor."""

    entity_description = PRESENCE_SENSOR_DESCRIPTION

    def __init__(
        self,
        coordinator: AulaPresenceCoordinator,
        child: Child,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{child.id}_presence_status"

    @property
    def _overview(self) -> DailyOverview | None:
        return self.coordinator.data.get(self._child.id)

    @property
    def native_value(self) -> str | None:
        """Return the presence status."""
        overview = self._overview
        return overview.status.name.lower() if overview else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return time and location details as attributes."""
        overview = self._overview
        if not overview:
            return {}
        return {
            "check_in_time": overview.check_in_time,
            "check_out_time": overview.check_out_time,
            "entry_time": overview.entry_time,
            "exit_time": overview.exit_time,
            "location": overview.location,
        }


class AulaNotificationsSensor(AulaAccountEntity, SensorEntity):
    """Sensor showing unread notification count for the active profile."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "unread_notifications"

    def __init__(
        self,
        coordinator: AulaNotificationsCoordinator,
        profile: Profile,
    ) -> None:
        """Initialize the notifications sensor."""
        super().__init__(coordinator, profile)
        self._attr_unique_id = f"{profile.profile_id}_unread_notifications"

    @property
    def native_value(self) -> int:
        """Return the number of unread notifications."""
        notifications = self.coordinator.data or []
        return sum(1 for n in notifications if n.is_read is False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return total count and recent notification titles."""
        notifications = self.coordinator.data or []
        return {
            "total": len(notifications),
            "recent": [n.title for n in notifications[:5]],
        }


class AulaLibraryLoansSensor(AulaEntity, SensorEntity):
    """Sensor showing library loan count for a child."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_translation_key = "library_loans"

    def __init__(
        self,
        coordinator: AulaLibraryCoordinator,
        child: Child,
    ) -> None:
        """Initialize the library loans sensor."""
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{child.id}_library_loans"

    @property
    def _child_data(self) -> LibraryChildData | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._child.id)

    @property
    def native_value(self) -> int:
        """Return the number of active loans."""
        data = self._child_data
        if not data:
            return 0
        return len(data.loans) + len(data.longterm_loans)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return loan details."""
        data = self._child_data
        if not data:
            return {}
        return {
            "loans": [
                {
                    "title": loan.title,
                    "author": loan.author,
                    "due_date": loan.due_date,
                }
                for loan in itertools.islice(
                    itertools.chain(data.loans, data.longterm_loans),
                    MAX_ATTRIBUTE_ITEMS,
                )
            ],
            "reservations_count": len(data.reservations),
        }


class AulaMUTasksSensor(AulaEntity, SensorEntity):
    """Sensor showing Min Uddannelse task count for a child."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "mu_tasks"

    def __init__(
        self,
        coordinator: AulaMUTasksCoordinator,
        child: Child,
    ) -> None:
        """Initialize the MU tasks sensor."""
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{child.id}_mu_tasks"

    @property
    def _tasks(self) -> list:
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get(self._child.id, [])

    @property
    def native_value(self) -> int:
        """Return the number of incomplete tasks."""
        return sum(1 for t in self._tasks if not t.is_completed)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return task details."""
        tasks = self._tasks
        if not tasks:
            return {}
        return {
            "tasks": [
                {
                    "title": t.title,
                    "due_date": str(t.due_date) if t.due_date else None,
                    "subject": t.classes[0].name if t.classes else None,
                    "is_completed": t.is_completed,
                }
                for t in tasks[:MAX_ATTRIBUTE_ITEMS]
            ],
        }


class AulaEasyIQWeekplanSensor(AulaEntity, SensorEntity):
    """Sensor showing EasyIQ weekplan appointment count for a child."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "easyiq_weekplan"

    def __init__(
        self,
        coordinator: AulaEasyIQCoordinator,
        child: Child,
    ) -> None:
        """Initialize the EasyIQ weekplan sensor."""
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{child.id}_easyiq_weekplan"

    @property
    def _child_data(self) -> EasyIQChildData | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._child.id)

    @property
    def native_value(self) -> int:
        """Return the number of appointments."""
        data = self._child_data
        if not data:
            return 0
        return len(data.weekplan)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return appointment details."""
        data = self._child_data
        if not data or not data.weekplan:
            return {}
        return {
            "appointments": [
                {
                    "title": a.title,
                    "start": a.start,
                    "end": a.end,
                }
                for a in data.weekplan[:MAX_ATTRIBUTE_ITEMS]
            ],
        }


class AulaEasyIQHomeworkSensor(AulaEntity, SensorEntity):
    """Sensor showing EasyIQ homework count for a child."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "easyiq_homework"

    def __init__(
        self,
        coordinator: AulaEasyIQCoordinator,
        child: Child,
    ) -> None:
        """Initialize the EasyIQ homework sensor."""
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{child.id}_easyiq_homework"

    @property
    def _child_data(self) -> EasyIQChildData | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._child.id)

    @property
    def native_value(self) -> int:
        """Return the number of incomplete homework items."""
        data = self._child_data
        if not data:
            return 0
        return sum(1 for h in data.homework if not h.is_completed)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return homework details."""
        data = self._child_data
        if not data or not data.homework:
            return {}
        return {
            "homework": [
                {
                    "title": h.title,
                    "subject": h.subject,
                    "due_date": h.due_date,
                    "is_completed": h.is_completed,
                }
                for h in data.homework[:MAX_ATTRIBUTE_ITEMS]
            ],
        }


class AulaMeebookWeekplanSensor(AulaEntity, SensorEntity):
    """Sensor showing Meebook weekplan task count for a child."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "meebook_weekplan"

    def __init__(
        self,
        coordinator: AulaMeebookCoordinator,
        child: Child,
    ) -> None:
        """Initialize the Meebook weekplan sensor."""
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{child.id}_meebook_weekplan"

    @property
    def _tasks(self) -> list:
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get(self._child.id, [])

    @property
    def native_value(self) -> int:
        """Return the number of tasks this week."""
        return len(self._tasks)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return task details."""
        tasks = self._tasks
        if not tasks:
            return {}
        return {
            "tasks": [
                {
                    "title": t.title,
                    "type": t.type,
                    "content": t.content,
                }
                for t in tasks[:MAX_ATTRIBUTE_ITEMS]
            ],
        }


class AulaHuskelistenSensor(AulaEntity, SensorEntity):
    """Sensor showing Huskelisten reminder count for a child."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "huskelisten_reminders"

    def __init__(
        self,
        coordinator: AulaHuskelistenCoordinator,
        child: Child,
    ) -> None:
        """Initialize the Huskelisten sensor."""
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{child.id}_huskelisten_reminders"

    @property
    def _child_data(self) -> HuskelistenChildData | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._child.id)

    @property
    def native_value(self) -> int:
        """Return the total number of reminders."""
        data = self._child_data
        if not data:
            return 0
        return len(data.team_reminders) + len(data.assignment_reminders)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return reminder details."""
        data = self._child_data
        if not data:
            return {}
        team_items = (
            {
                "text": r.reminder_text,
                "due_date": r.due_date,
                "subject": r.subject_name,
                "team": r.team_name,
            }
            for r in data.team_reminders
        )
        assignment_items = (
            {
                "text": r.assignment_text,
                "due_date": r.due_date,
                "team": ", ".join(r.team_names) if r.team_names else None,
            }
            for r in data.assignment_reminders
        )
        return {
            "reminders": list(
                itertools.islice(
                    itertools.chain(team_items, assignment_items), MAX_ATTRIBUTE_ITEMS
                )
            )
        }
