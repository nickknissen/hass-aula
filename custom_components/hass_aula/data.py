"""Custom types for the Aula integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from aula import AulaApiClient, Profile
    from aula.models import Appointment, EasyIQHomework, LibraryLoan
    from aula.models.momo_huskeliste import AssignmentReminder, TeamReminder
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from .coordinator import (
        AulaCalendarCoordinator,
        AulaEasyIQCoordinator,
        AulaHuskelistenCoordinator,
        AulaLibraryCoordinator,
        AulaMeebookCoordinator,
        AulaMUTasksCoordinator,
        AulaNotificationsCoordinator,
        AulaPresenceCoordinator,
    )
    from .token_manager import AulaTokenManager

type AulaConfigEntry = ConfigEntry[AulaRuntimeData]


@dataclass
class WidgetContext:
    """Context needed by widget API calls."""

    child_filter: list[str]
    institution_filter: list[str]
    session_uuid: str


@dataclass
class LibraryChildData:
    """Library data for a single child."""

    loans: list[LibraryLoan] = field(default_factory=list)
    longterm_loans: list[LibraryLoan] = field(default_factory=list)
    reservations: list[dict] = field(default_factory=list)


@dataclass
class EasyIQChildData:
    """EasyIQ data for a single child."""

    weekplan: list[Appointment] = field(default_factory=list)
    homework: list[EasyIQHomework] = field(default_factory=list)


@dataclass
class HuskelistenChildData:
    """Huskelisten data for a single child."""

    team_reminders: list[TeamReminder] = field(default_factory=list)
    assignment_reminders: list[AssignmentReminder] = field(default_factory=list)


@dataclass
class AulaRuntimeData:
    """Runtime data for the Aula integration."""

    client: AulaApiClient
    token_manager: AulaTokenManager
    profile: Profile
    presence_coordinator: AulaPresenceCoordinator
    calendar_coordinator: AulaCalendarCoordinator
    notifications_coordinator: AulaNotificationsCoordinator
    library_coordinator: AulaLibraryCoordinator | None = None
    mu_tasks_coordinator: AulaMUTasksCoordinator | None = None
    easyiq_coordinator: AulaEasyIQCoordinator | None = None
    meebook_coordinator: AulaMeebookCoordinator | None = None
    huskelisten_coordinator: AulaHuskelistenCoordinator | None = None

    @property
    def all_coordinators(self) -> Iterator[DataUpdateCoordinator]:
        """Yield all active coordinators."""
        for coord in (
            self.presence_coordinator,
            self.calendar_coordinator,
            self.notifications_coordinator,
            self.library_coordinator,
            self.mu_tasks_coordinator,
            self.easyiq_coordinator,
            self.meebook_coordinator,
            self.huskelisten_coordinator,
        ):
            if coord is not None:
                yield coord
