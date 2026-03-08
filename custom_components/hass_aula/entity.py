"""Base entity for the Aula integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import AulaNotificationsCoordinator

if TYPE_CHECKING:
    from aula import Child, Profile


class AulaEntity[CoordT: DataUpdateCoordinator[Any]](
    CoordinatorEntity[CoordT],
):
    """Base class for Aula entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CoordT,
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


class AulaAccountEntity(CoordinatorEntity[AulaNotificationsCoordinator]):
    """Base class for profile-level Aula entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AulaNotificationsCoordinator,
        profile: Profile,
    ) -> None:
        """Initialize the account entity."""
        super().__init__(coordinator)
        self._profile = profile
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"profile_{profile.profile_id}")},
            name=profile.display_name,
            manufacturer="Aula",
            entry_type=DeviceEntryType.SERVICE,
        )
