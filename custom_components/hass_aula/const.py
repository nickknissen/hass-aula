"""Constants for the Aula integration."""

from __future__ import annotations

from logging import Logger, getLogger

from aula.const import (
    WIDGET_BIBLIOTEKET as WIDGET_BIBLIOTEKET,  # noqa: PLC0414
)
from aula.const import (
    WIDGET_EASYIQ as WIDGET_EASYIQ,  # noqa: PLC0414
)
from aula.const import (
    WIDGET_EASYIQ_HOMEWORK as WIDGET_EASYIQ_HOMEWORK,  # noqa: PLC0414
)
from aula.const import (
    WIDGET_EASYIQ_WEEKPLAN as WIDGET_EASYIQ_WEEKPLAN,  # noqa: PLC0414
)
from aula.const import (
    WIDGET_HUSKELISTEN as WIDGET_HUSKELISTEN,  # noqa: PLC0414
)
from aula.const import (
    WIDGET_MEEBOOK as WIDGET_MEEBOOK,  # noqa: PLC0414
)
from aula.const import (
    WIDGET_MIN_UDDANNELSE as WIDGET_MIN_UDDANNELSE,  # noqa: PLC0414
)
from aula.const import (
    WIDGET_MIN_UDDANNELSE_UGEPLAN as WIDGET_MIN_UDDANNELSE_UGEPLAN,  # noqa: PLC0414
)
from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "hass_aula"

EVENT_NOTIFICATION = "hass_aula_notification"

CONF_MITID_USERNAME = "mitid_username"
CONF_TOKEN_DATA = "token_data"  # noqa: S105
CONF_WIDGETS = "widgets"

PRESENCE_POLL_INTERVAL = 300  # 5 minutes
NOTIFICATIONS_POLL_INTERVAL = 300  # 5 minutes
CALENDAR_POLL_INTERVAL = 3600  # 60 minutes

# Widget poll intervals (seconds)
LIBRARY_POLL_INTERVAL = 3600  # 60 minutes
MU_TASKS_POLL_INTERVAL = 1800  # 30 minutes
MU_UGEPLAN_POLL_INTERVAL = 1800  # 30 minutes
EASYIQ_POLL_INTERVAL = 1800  # 30 minutes
MEEBOOK_POLL_INTERVAL = 3600  # 60 minutes
HUSKELISTEN_POLL_INTERVAL = 1800  # 30 minutes

SUPPORTED_WIDGETS: frozenset[str] = frozenset(
    {
        WIDGET_BIBLIOTEKET,
        WIDGET_EASYIQ,
        WIDGET_EASYIQ_HOMEWORK,
        WIDGET_EASYIQ_WEEKPLAN,
        WIDGET_HUSKELISTEN,
        WIDGET_MEEBOOK,
    }
)

# Virtual feature IDs for widgets that expose multiple sub-features.
FEATURE_MU_TASKS = "mu_tasks"
FEATURE_MU_UGEPLAN = "mu_ugeplan"

# Widgets with sub-features: maps real widget ID → list of (feature_id, label).
WIDGET_FEATURES: dict[str, list[tuple[str, str]]] = {
    WIDGET_MIN_UDDANNELSE: [
        (FEATURE_MU_TASKS, "Opgaver"),
        (FEATURE_MU_UGEPLAN, "Ugenoter"),
    ],
    WIDGET_MIN_UDDANNELSE_UGEPLAN: [
        (FEATURE_MU_UGEPLAN, "Ugenoter"),
    ],
}

PARALLEL_UPDATES = 1

PLATFORMS: list[Platform] = [
    Platform.CALENDAR,
    Platform.SENSOR,
]
