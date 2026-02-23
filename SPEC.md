# hass-aula: Home Assistant Integration for Aula.dk

## Product Spec

### Overview

A Home Assistant custom integration for **Aula** — the Danish school communication
platform (aula.dk). This integration wraps the
[`aula`](https://pypi.org/project/aula/) Python library (v0.1.1+) to surface
school-related data — child presence, calendar events, messages, posts, homework
tasks, and library loans — as native Home Assistant entities.

**Domain:** `aula`
**IoT class:** `cloud_polling`
**Minimum HA version:** 2025.2.4
**HACS compatible:** Yes

---

### Target Users

Parents (guardians) in Denmark whose children attend schools using Aula. The
integration lets them:

- See at a glance whether their child has arrived at school
- Get upcoming school events in the HA calendar
- Track unread messages and new posts
- Monitor homework tasks and library book due dates
- Build automations around school events (e.g., notify when child checks in)

---

## Authentication

### The MitID Challenge

Aula authenticates via Denmark's national **MitID** identity system. This is an
interactive flow requiring QR-code scanning or app approval — it cannot be reduced
to a simple username/password form.

### Strategy: Two-Phase Setup

#### Phase 1 — Initial Token Acquisition (Config Flow)

1. User enters their **MitID username** in the HA config flow.
2. The integration calls `authenticate_and_create_client()` from the `aula`
   library, providing a custom `TokenStorage` backend.
3. The config flow transitions to a **QR code step** that displays the MitID QR
   codes via the `on_qr_codes` callback. The user scans with their MitID app.
4. On successful authentication, the integration receives an access token,
   refresh token, and session cookies.
5. Tokens are persisted using a Home Assistant–native `TokenStorage`
   implementation backed by `hass.data` + config entry storage (not the
   filesystem).

#### Phase 2 — Ongoing Token Refresh

- The `aula` library supports **token refresh** via
  `MitIDAuthClient.refresh_access_token()`.
- The coordinator attempts a silent token refresh before each data poll.
- If the refresh token itself has expired (long inactivity), the integration
  raises `ConfigEntryAuthFailed`, prompting the user to re-authenticate through
  the config flow reauth step.

### Config Flow Steps

| Step              | Fields                     | Description                                            |
|-------------------|----------------------------|--------------------------------------------------------|
| `user`            | `mitid_username`           | MitID username input                                   |
| `qr_code`         | *(display only)*           | Shows QR codes for MitID app approval                  |
| `reauth_confirm`  | `mitid_username`           | Re-authentication when tokens fully expire              |

### Token Storage Implementation

```python
class HATokenStorage(TokenStorage):
    """Store Aula tokens in HA config entry data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None: ...

    async def load(self) -> dict[str, Any] | None:
        # Read from entry.data["tokens"]

    async def save(self, data: dict[str, Any]) -> None:
        # Write to entry.data["tokens"] via
        # hass.config_entries.async_update_entry()
```

---

## Architecture

### Integration Data Flow

```
MitID Auth ──► aula library ──► AulaApiClient
                                     │
                     ┌───────────────┼───────────────┐
                     ▼               ▼               ▼
              AulaPresence     AulaCalendar     AulaMessages
              Coordinator      Coordinator      Coordinator
                     │               │               │
                     ▼               ▼               ▼
               sensor.*       calendar.*        sensor.*
             binary_sensor.*                    todo.*
```

### HTTP Client Adapter

The `aula` library defines an `HttpClient` protocol. The integration provides an
**aiohttp-based implementation** that reuses Home Assistant's
`async_get_clientsession()`, ensuring proper connection pooling and SSL handling.

```python
class AiohttpAulaClient(HttpClient):
    """Adapts HA's aiohttp session to the aula HttpClient protocol."""

    def __init__(self, session: aiohttp.ClientSession) -> None: ...

    async def request(self, method, url, *, headers, params, json) -> HttpResponse: ...
    async def download_bytes(self, url: str) -> bytes: ...
    def get_cookie(self, name: str) -> str | None: ...
    async def close(self) -> None: ...
```

> **Note:** The `aula` library ships with `HttpxHttpClient` (httpx-based). For the
> initial release we can use the bundled httpx client directly rather than writing
> an aiohttp adapter. The aiohttp adapter is a future optimization to align with
> HA best practices. The `HttpClient` protocol makes this swap transparent.

### Data Coordinators

| Coordinator          | Update Interval | API Calls                                            |
|----------------------|-----------------|------------------------------------------------------|
| `AulaPresenceCoordinator`  | 5 minutes   | `get_daily_overview()` per child                    |
| `AulaCalendarCoordinator`  | 30 minutes  | `get_calendar_events()` (rolling 14-day window)      |
| `AulaMessagesCoordinator`  | 15 minutes  | `get_message_threads()`                              |
| `AulaPostsCoordinator`     | 30 minutes  | `get_posts()`                                        |
| `AulaTasksCoordinator`     | 60 minutes  | `get_mu_tasks()` (current week)                      |

Each coordinator extends `DataUpdateCoordinator` and shares a single
`AulaApiClient` instance stored in `hass.data[DOMAIN][entry.entry_id]`.

All coordinators handle:
- `HttpRequestError` → `UpdateFailed`
- Auth failures → `ConfigEntryAuthFailed` (triggers reauth flow)

### Integration Setup (`__init__.py`)

```python
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.TODO,
]

async def async_setup_entry(hass, entry):
    # 1. Create token storage backed by config entry
    # 2. Authenticate / refresh tokens via aula library
    # 3. Fetch profile + children list
    # 4. Create shared AulaApiClient
    # 5. Create coordinators, trigger first refresh
    # 6. Forward entry setup to platforms
```

---

## Entities

### Per-Child Entities

Each child in the profile generates the following entities. The entity unique ID
is `aula_{child_id}_{entity_type}`.

#### 1. Presence Sensor

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Platform**    | `sensor`                                       |
| **Name**        | `{child_name} Presence`                        |
| **Device class**| —                                              |
| **State**       | `PresenceState` display name (e.g., "Present", "Sick", "Not present") |
| **Attributes**  |                                                |
|                 | `location` — current location string           |
|                 | `check_in_time` — today's check-in time        |
|                 | `check_out_time` — today's check-out time      |
|                 | `entry_time` — planned entry time              |
|                 | `exit_time` — planned exit time                |
|                 | `exit_with` — who the child leaves with        |
|                 | `comment` — daily comment                      |
|                 | `institution` — institution name               |
|                 | `main_group` — class/group name                |
| **Icon**        | `mdi:school`                                   |

#### 2. Present at School Binary Sensor

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Platform**    | `binary_sensor`                                |
| **Name**        | `{child_name} At School`                       |
| **Device class**| `presence`                                     |
| **State**       | `on` when `PresenceState` is `PRESENT`, `FIELDTRIP`, `SPARE_TIME_ACTIVITY`, or `SLEEPING`; `off` otherwise |
| **Attributes**  | Same as presence sensor                        |
| **Icon**        | `mdi:school`                                   |

#### 3. Calendar

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Platform**    | `calendar`                                     |
| **Name**        | `{child_name} School Calendar`                 |
| **Events**      | From `get_calendar_events()` with 14-day lookahead |
| **Event fields**|                                                |
|                 | `summary` → `event.title`                     |
|                 | `start` → `event.start_datetime`               |
|                 | `end` → `event.end_datetime`                   |
|                 | `location` → `event.location`                  |
|                 | `description` → teacher/substitute info         |

#### 4. Homework Tasks (Todo List)

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Platform**    | `todo`                                         |
| **Name**        | `{child_name} Homework`                        |
| **Items**       | From `get_mu_tasks()` for current week         |
| **Item fields** |                                                |
|                 | `summary` → `task.title`                       |
|                 | `due` → `task.due_date`                        |
|                 | `status` → mapped from `task.is_completed`     |
|                 | `description` → course name + classes          |
| **Note**        | Read-only; tasks cannot be completed from HA   |

### Per-Account Entities

These entities are created once per config entry (Aula account).

#### 5. Unread Messages Sensor

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Platform**    | `sensor`                                       |
| **Name**        | `Aula Unread Messages`                         |
| **Device class**| —                                              |
| **State class** | `measurement`                                  |
| **State**       | Count of message threads (int)                 |
| **Attributes**  |                                                |
|                 | `threads` — list of `{subject, thread_id}`     |
| **Icon**        | `mdi:email`                                    |

#### 6. Latest Post Sensor

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Platform**    | `sensor`                                       |
| **Name**        | `Aula Latest Post`                             |
| **State**       | Title of the most recent post                  |
| **Attributes**  |                                                |
|                 | `content` — plain text body (truncated)        |
|                 | `author` — post owner display name             |
|                 | `timestamp` — publish timestamp                |
|                 | `is_important` — boolean                       |
|                 | `comment_count` — number of comments           |
| **Icon**        | `mdi:bulletin-board`                           |

### Device Registry

Each **child** is registered as a HA **device**:

| Property         | Value                                         |
|------------------|-----------------------------------------------|
| `identifiers`    | `{(DOMAIN, child_id)}`                        |
| `name`           | Child's name                                  |
| `manufacturer`   | `Aula`                                        |
| `model`          | Institution name                              |
| `sw_version`     | `aula` library version                        |

---

## Configuration Options (Options Flow)

After initial setup, users can configure:

| Option                  | Type    | Default | Description                              |
|-------------------------|---------|---------|------------------------------------------|
| `update_interval_presence` | int  | 5       | Presence polling interval (minutes)      |
| `update_interval_calendar` | int  | 30      | Calendar polling interval (minutes)      |
| `update_interval_messages` | int  | 15      | Messages polling interval (minutes)      |
| `calendar_lookahead_days`  | int  | 14      | Days ahead to fetch calendar events      |

---

## Error Handling

| Scenario                        | Behavior                                           |
|---------------------------------|----------------------------------------------------|
| Network error during poll       | `UpdateFailed` — HA retries on next interval       |
| HTTP 401/403 from Aula API      | `ConfigEntryAuthFailed` — triggers reauth flow     |
| Token refresh fails             | `ConfigEntryAuthFailed` — triggers reauth flow     |
| MitID auth timeout/cancelled    | Config flow shows error, user can retry            |
| Child not found in daily overview | Entity state becomes `unavailable`               |

---

## File Structure

```
custom_components/aula/
├── __init__.py              # Entry setup, platforms, shared client
├── api.py                   # AiohttpAulaClient adapter (HttpClient impl)
├── auth.py                  # HATokenStorage, auth helpers
├── config_flow.py           # ConfigFlow with MitID QR step + options flow
├── const.py                 # DOMAIN, PLATFORMS, defaults, logger
├── coordinator.py           # DataUpdateCoordinators (presence, calendar, etc.)
├── data.py                  # AulaData runtime dataclass
├── entity.py                # AulaEntity base class (device info mixin)
├── sensor.py                # Presence sensor, unread messages, latest post
├── binary_sensor.py         # At-school binary sensor
├── calendar.py              # School calendar entity
├── todo.py                  # Homework tasks todo list
├── manifest.json            # Integration manifest
├── strings.json             # English strings (used for translations)
└── translations/
    ├── en.json              # English
    └── da.json              # Danish
```

### manifest.json

```json
{
  "domain": "aula",
  "name": "Aula",
  "codeowners": ["@nickknissen"],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/nickknissen/hass-aula",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/nickknissen/hass-aula/issues",
  "requirements": ["aula>=0.1.1"],
  "version": "0.1.0"
}
```

---

## Scope & Phasing

### Phase 1 — MVP

- Config flow with MitID authentication (username + QR code step)
- Token persistence and silent refresh
- Per-child presence sensor + binary sensor
- Per-child school calendar
- Unread messages sensor
- Danish + English translations

### Phase 2

- Homework tasks as todo entities (`get_mu_tasks()`)
- Latest post sensor
- Options flow for polling intervals
- Meebook/EasyIQ weekly plan support

### Phase 3 — Future

- Library loans sensor (books due)
- Gallery image download as HA media source
- Message notification events (HA event entity)
- Weekly letter sensors
- aiohttp adapter (replace httpx with HA's shared session)

---

## Dependencies

| Package | Version | Purpose                          |
|---------|---------|----------------------------------|
| `aula`  | >=0.1.1 | Core Aula API client             |

The `aula` package transitively depends on: `httpx`, `beautifulsoup4`,
`html2text`, `pycryptodome`, `qrcode`.

---

## Testing Strategy

- **Unit tests:** Mock `AulaApiClient` methods, verify entity states and
  attributes from known API response fixtures.
- **Config flow tests:** Mock `authenticate_and_create_client()`, test
  happy-path setup, auth failure, and reauth flow.
- **Coordinator tests:** Mock API calls, verify `UpdateFailed` and
  `ConfigEntryAuthFailed` are raised correctly.
- **Integration tests:** Use HA's `pytest-homeassistant-custom-component`
  framework.

---

## Open Questions

1. **QR code display in config flow:** HA config flows support showing images
   via `description_placeholders` or markdown, but rendering a live-updating QR
   code is non-trivial. Options:
   - Render QR as a base64 data URI in markdown description
   - Use a separate companion page / persistent notification
   - Display the OTP code as text fallback

2. **httpx vs aiohttp:** The `aula` library uses httpx internally (via
   `HttpxHttpClient`). HA convention is aiohttp. For MVP, using httpx directly
   is acceptable since the library's `HttpClient` protocol allows swapping
   later. Consider whether to add `httpx` as an explicit requirement or rely on
   the transitive dependency from `aula`.

3. **Multi-account support:** The integration should support multiple config
   entries (multiple Aula accounts / MitID users). Each entry gets its own
   `AulaApiClient` and set of coordinators. Verify there are no singleton
   conflicts.

4. **Rate limiting:** Aula's API rate limits are undocumented. Conservative
   default polling intervals protect against this, but may need adjustment based
   on user reports.
