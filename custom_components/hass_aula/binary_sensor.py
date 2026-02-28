"""Binary sensor platform for the Aula integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aula.models.presence import PresenceState
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import PARALLEL_UPDATES as PARALLEL_UPDATES  # noqa: PLC0414
from .entity import AulaEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AulaPresenceCoordinator
    from .data import AulaConfigEntry

PRESENT_STATES: frozenset[PresenceState] = frozenset(
    {
        PresenceState.PRESENT,
        PresenceState.FIELDTRIP,
        PresenceState.SLEEPING,
        PresenceState.SPARE_TIME_ACTIVITY,
        PresenceState.PHYSICAL_PLACEMENT,
    }
)

BINARY_SENSOR_DESCRIPTION = BinarySensorEntityDescription(
    key="is_present",
    device_class=BinarySensorDeviceClass.PRESENCE,
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AulaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aula presence binary sensors."""
    coordinator = entry.runtime_data.presence_coordinator
    profile = entry.runtime_data.profile

    async_add_entities(
        AulaPresenceBinarySensor(coordinator=coordinator, child=child)
        for child in profile.children
    )


class AulaPresenceBinarySensor(AulaEntity, BinarySensorEntity):
    """Representation of an Aula presence binary sensor."""

    entity_description = BINARY_SENSOR_DESCRIPTION

    def __init__(
        self,
        coordinator: AulaPresenceCoordinator,
        child: Any,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{child.id}_{BINARY_SENSOR_DESCRIPTION.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the child is present."""
        overview = self.coordinator.data.get(self._child.id)
        if overview is None:
            return None
        return overview.status in PRESENT_STATES
