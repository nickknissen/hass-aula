"""Sensor platform for the Aula integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import PARALLEL_UPDATES as PARALLEL_UPDATES  # noqa: PLC0414
from .entity import AulaEntity

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from aula import DailyOverview

    from .coordinator import AulaPresenceCoordinator
    from .data import AulaConfigEntry


@dataclass(frozen=True, kw_only=True)
class AulaPresenceSensorDescription(SensorEntityDescription):
    """Describe an Aula presence sensor."""

    value_fn: Callable[[DailyOverview | None], Any]


PRESENCE_SENSOR_DESCRIPTIONS: tuple[AulaPresenceSensorDescription, ...] = (
    AulaPresenceSensorDescription(
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
        value_fn=lambda overview: overview.status.name.lower() if overview else None,
    ),
    AulaPresenceSensorDescription(
        key="check_in_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda overview: overview.check_in_time if overview else None,
    ),
    AulaPresenceSensorDescription(
        key="check_out_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda overview: overview.check_out_time if overview else None,
    ),
    AulaPresenceSensorDescription(
        key="entry_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda overview: overview.entry_time if overview else None,
    ),
    AulaPresenceSensorDescription(
        key="exit_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda overview: overview.exit_time if overview else None,
    ),
    AulaPresenceSensorDescription(
        key="location",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda overview: overview.location if overview else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AulaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aula presence sensors."""
    coordinator = entry.runtime_data.presence_coordinator
    profile = entry.runtime_data.profile

    entities: list[AulaPresenceSensor] = []
    for child in profile.children:
        entities.extend(
            AulaPresenceSensor(
                coordinator=coordinator,
                child=child,
                description=description,
            )
            for description in PRESENCE_SENSOR_DESCRIPTIONS
        )

    async_add_entities(entities)


class AulaPresenceSensor(AulaEntity, SensorEntity):
    """Representation of an Aula presence sensor."""

    entity_description: AulaPresenceSensorDescription

    def __init__(
        self,
        coordinator: AulaPresenceCoordinator,
        child: Any,
        description: AulaPresenceSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, child)
        self.entity_description = description
        self._attr_unique_id = f"{child.id}_{description.key}"

    @property
    def native_value(self) -> str | datetime | None:
        """Return the state of the sensor."""
        overview = self.coordinator.data.get(self._child.id)
        return self.entity_description.value_fn(overview)
