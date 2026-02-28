"""Constants for the Aula integration."""

from __future__ import annotations

from logging import Logger, getLogger

from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "hass_aula"

CONF_MITID_USERNAME = "mitid_username"
CONF_TOKEN_DATA = "token_data"  # noqa: S105

PRESENCE_POLL_INTERVAL = 300  # 5 minutes
CALENDAR_POLL_INTERVAL = 3600  # 60 minutes

PARALLEL_UPDATES = 1

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.SENSOR,
]
