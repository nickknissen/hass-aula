"""Custom types for the Aula integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aula import AulaApiClient, Profile
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import AulaCalendarCoordinator, AulaPresenceCoordinator

type AulaConfigEntry = ConfigEntry[AulaRuntimeData]


@dataclass
class AulaRuntimeData:
    """Runtime data for the Aula integration."""

    client: AulaApiClient
    profile: Profile
    presence_coordinator: AulaPresenceCoordinator
    calendar_coordinator: AulaCalendarCoordinator
