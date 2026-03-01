"""Sensor platform for the Aula integration."""

from __future__ import annotations

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

    from .coordinator import AulaNotificationsCoordinator, AulaPresenceCoordinator
    from .data import AulaConfigEntry


PRESENCE_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="presence_status",
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
    presence_coordinator = entry.runtime_data.presence_coordinator
    notifications_coordinator = entry.runtime_data.notifications_coordinator
    profile = entry.runtime_data.profile

    entities: list[SensorEntity] = [
        AulaPresenceSensor(coordinator=presence_coordinator, child=child)
        for child in profile.children
    ]
    entities.append(
        AulaNotificationsSensor(coordinator=notifications_coordinator, profile=profile)
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
