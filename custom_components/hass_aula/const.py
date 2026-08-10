"""Constants for the Aula integration."""

from __future__ import annotations

from logging import Logger, getLogger

from aula import ActivityType
from aula.const import (
    WIDGET_BIBLIOTEKET,
    WIDGET_EASYIQ,
    WIDGET_EASYIQ_HOMEWORK,
    WIDGET_EASYIQ_WEEKPLAN,
    WIDGET_HUSKELISTEN,
    WIDGET_MEEBOOK,
    WIDGET_MIN_UDDANNELSE_TASKS,
    WIDGET_MIN_UDDANNELSE_UGEPLAN,
)
from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "hass_aula"

EVENT_NOTIFICATION = "hass_aula_notification"

CONF_MITID_USERNAME = "mitid_username"
CONF_TOKEN_DATA = "token_data"  # noqa: S105
CONF_WIDGETS = "widgets"

SERVICE_UPDATE_PRESENCE = "update_presence"

ATTR_ACTIVITY_TYPE = "activity_type"
ATTR_COMMENT = "comment"
ATTR_DATE = "date"
ATTR_ENTRY_TIME = "entry_time"
ATTR_EXIT_TIME = "exit_time"
ATTR_EXIT_WITH = "exit_with"
ATTR_EXPIRES_AT = "expires_at"
ATTR_REPEAT = "repeat"

ACTIVITY_TYPE_PICKED_UP_BY = "picked_up_by"

# Maps the action's option slugs to the aula package's ActivityType members.
# Whether a type needs exit_with comes from ActivityType.requires_exit_with.
ACTIVITY_TYPES: dict[str, ActivityType] = {
    ACTIVITY_TYPE_PICKED_UP_BY: ActivityType.PICKED_UP_BY,
    "self_decider": ActivityType.SELF_DECIDER,
    "send_home": ActivityType.SEND_HOME,
    "go_home_with": ActivityType.GO_HOME_WITH,
    "drop_off_time": ActivityType.DROP_OFF_TIME,
}

REPEAT_NEVER = "never"

# Maps the action's snake_case options to the aula package's repeat_pattern values.
REPEAT_PATTERNS: dict[str, str] = {
    REPEAT_NEVER: "Never",
    "weekly": "Weekly",
    "every_2_weeks": "Every2Weeks",
}

PRESENCE_POLL_INTERVAL = 300  # 5 minutes
NOTIFICATIONS_POLL_INTERVAL = 300  # 5 minutes
CALENDAR_POLL_INTERVAL = 3600  # 60 minutes
MESSAGES_POLL_INTERVAL = 1800  # 30 minutes

# Widget poll intervals (seconds)
LIBRARY_POLL_INTERVAL = 3600  # 60 minutes
MU_TASKS_POLL_INTERVAL = 1800  # 30 minutes
MU_UGEPLAN_POLL_INTERVAL = 1800  # 30 minutes
EASYIQ_POLL_INTERVAL = 1800  # 30 minutes
MEEBOOK_POLL_INTERVAL = 3600  # 60 minutes
HUSKELISTEN_POLL_INTERVAL = 1800  # 30 minutes

# Latest-messages sensor shaping
MAX_MESSAGE_ITEMS = 5
MAX_PREVIEW_CHARS = 200

SUPPORTED_WIDGETS: frozenset[str] = frozenset(
    {
        WIDGET_BIBLIOTEKET,
        WIDGET_EASYIQ,
        WIDGET_EASYIQ_HOMEWORK,
        WIDGET_EASYIQ_WEEKPLAN,
        WIDGET_HUSKELISTEN,
        WIDGET_MEEBOOK,
        WIDGET_MIN_UDDANNELSE_TASKS,
        WIDGET_MIN_UDDANNELSE_UGEPLAN,
    }
)

PARALLEL_UPDATES = 1

PLATFORMS: list[Platform] = [
    Platform.CALENDAR,
    Platform.SENSOR,
]
