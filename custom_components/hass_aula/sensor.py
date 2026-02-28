"""Sensor platform for the Aula integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)

from .const import PARALLEL_UPDATES as PARALLEL_UPDATES  # noqa: PLC0414
from .entity import AulaEntity

if TYPE_CHECKING:
    from aula import DailyOverview

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AulaPresenceCoordinator
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
    """Set up Aula presence sensors."""
    coordinator = entry.runtime_data.presence_coordinator
    profile = entry.runtime_data.profile

    async_add_entities(
        AulaPresenceSensor(coordinator=coordinator, child=child)
        for child in profile.children
    )


class AulaPresenceSensor(AulaEntity, SensorEntity):
    """Representation of an Aula presence sensor."""

    entity_description = PRESENCE_SENSOR_DESCRIPTION

    def __init__(
        self,
        coordinator: AulaPresenceCoordinator,
        child: Any,
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
