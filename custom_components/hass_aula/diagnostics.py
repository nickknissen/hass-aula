"""Diagnostics support for the Aula integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import AulaConfigEntry

REDACTED = "**REDACTED**"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AulaConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data

    children_data = [
        {
            "id": child.id,
            "name": REDACTED,
            "institution_name": child.institution_name,
        }
        for child in runtime_data.profile.children
    ]

    presence_data: dict[str, Any] = {}
    for child_id, overview in runtime_data.presence_coordinator.data.items():
        if overview is None:
            presence_data[str(child_id)] = None
        else:
            presence_data[str(child_id)] = {
                "status": overview.status.name,
                "location": overview.location,
                "check_in_time": str(overview.check_in_time)
                if overview.check_in_time
                else None,
                "check_out_time": str(overview.check_out_time)
                if overview.check_out_time
                else None,
            }

    calendar_data: dict[str, int] = {}
    for child_id, events in runtime_data.calendar_coordinator.data.items():
        calendar_data[str(child_id)] = len(events)

    result: dict[str, Any] = {
        "profile": {
            "profile_id": runtime_data.profile.profile_id,
            "display_name": REDACTED,
            "children_count": len(runtime_data.profile.children),
            "children": children_data,
        },
        "presence": presence_data,
        "calendar_event_counts": calendar_data,
    }

    # Widget data summaries
    widgets: dict[str, Any] = {}

    if runtime_data.library_coordinator and runtime_data.library_coordinator.data:
        widgets["library"] = {
            str(child_id): len(data.loans) + len(data.longterm_loans)
            for child_id, data in runtime_data.library_coordinator.data.items()
        }

    if runtime_data.mu_tasks_coordinator and runtime_data.mu_tasks_coordinator.data:
        widgets["mu_tasks"] = {
            str(child_id): len(tasks)
            for child_id, tasks in runtime_data.mu_tasks_coordinator.data.items()
        }

    if runtime_data.easyiq_coordinator and runtime_data.easyiq_coordinator.data:
        widgets["easyiq"] = {
            str(child_id): {
                "weekplan": len(data.weekplan),
                "homework": len(data.homework),
            }
            for child_id, data in runtime_data.easyiq_coordinator.data.items()
        }

    if runtime_data.meebook_coordinator and runtime_data.meebook_coordinator.data:
        widgets["meebook"] = {
            str(child_id): len(tasks)
            for child_id, tasks in runtime_data.meebook_coordinator.data.items()
        }

    if (
        runtime_data.huskelisten_coordinator
        and runtime_data.huskelisten_coordinator.data
    ):
        widgets["huskelisten"] = {
            str(child_id): len(data.team_reminders) + len(data.assignment_reminders)
            for child_id, data in runtime_data.huskelisten_coordinator.data.items()
        }

    if widgets:
        result["widgets"] = widgets

    return result
