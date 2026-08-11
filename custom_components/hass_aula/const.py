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

CONF_AUTH_METHOD = "auth_method"
CONF_MITID_PASSWORD = "mitid_password"  # noqa: S105
CONF_MITID_USERNAME = "mitid_username"
CONF_TOKEN_CODE = "token_code"  # noqa: S105
CONF_TOKEN_DATA = "token_data"  # noqa: S105
CONF_WIDGETS = "widgets"

# MitID authenticators this integration can drive. "app" approves the login in
# the MitID app; "token" reads a one-time code off a MitID kodeviser (code
# display), which users without a smartphone rely on.
AUTH_METHOD_APP = "app"
AUTH_METHOD_TOKEN = "token"  # noqa: S105
AUTH_METHODS = [AUTH_METHOD_APP, AUTH_METHOD_TOKEN]
TOKEN_CODE_LENGTH = 6

SERVICE_UPDATE_PRESENCE = "update_presence"
SERVICE_GET_THREAD_MESSAGES = "get_thread_messages"

ATTR_ACTIVITY_TYPE = "activity_type"
ATTR_COMMENT = "comment"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_DATE = "date"
ATTR_ENTRY_TIME = "entry_time"
ATTR_EXIT_TIME = "exit_time"
ATTR_EXIT_WITH = "exit_with"
ATTR_EXPIRES_AT = "expires_at"
ATTR_LIMIT = "limit"
ATTR_REPEAT = "repeat"
ATTR_THREAD_ID = "thread_id"

# Aula's own message list pages at 10; 50 is a generous ceiling for one thread.
MAX_THREAD_MESSAGES = 50
DEFAULT_THREAD_MESSAGES = 5

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
