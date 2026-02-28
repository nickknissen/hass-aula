"""Base entity for the Aula integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AulaCalendarCoordinator, AulaPresenceCoordinator

if TYPE_CHECKING:
    from aula import Child


class AulaEntity(
    CoordinatorEntity[AulaPresenceCoordinator | AulaCalendarCoordinator],
):
    """Base class for Aula entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AulaPresenceCoordinator | AulaCalendarCoordinator,
        child: Child,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._child = child
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(child.id))},
            name=child.name,
            manufacturer="Aula",
            model=child.institution_name,
            entry_type=DeviceEntryType.SERVICE,
        )
