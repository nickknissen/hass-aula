# hass-aula — Product Spec

Home Assistant custom integration for [Aula](https://aula.dk), the Danish
school and daycare communication platform. Wraps the
[`aula`](https://pypi.org/project/aula/) Python library (v0.1.1+).

---

## 1. Problem

Danish parents use Aula daily to check whether their child has arrived at
school/daycare, read messages from teachers, track homework, and keep up with
the school calendar. All of this lives behind a web portal that requires MitID
(Denmark's national identity) to log in.

There is no way to surface this information in a smart-home dashboard, build
automations around school events, or get push notifications when a child checks
in — unless you build a custom integration.

## 2. Users

Parents (guardians) in Denmark whose children attend institutions using Aula.
Typical household has 1–3 children across 1–2 institutions (e.g. a daycare and
a school).

## 3. Goals

- **At-a-glance status**: Is my child at school right now? When did they arrive?
- **Calendar in HA**: See the school schedule alongside the family calendar.
- **Message awareness**: Know when new messages arrive without opening Aula.
- **Homework tracking**: Surface upcoming tasks on the family dashboard.
- **Automation hooks**: Trigger actions on presence changes, new messages, or
  upcoming events (e.g. "notify me when my child checks in at daycare").

## 4. Non-Goals (for now)

- **Write operations**: No sending messages, marking tasks complete, or
  reporting absence. The `aula` library is read-only and so is this integration.
- **Gallery / media browsing**: The library supports downloading gallery images,
  but surfacing them as an HA media source is out of scope for the MVP.
- **Multiple guardian roles**: The integration assumes a `guardian` role. Teacher
  or employee roles are not supported.

---

## 5. Authentication

### The MitID challenge

Aula authenticates through Denmark's MitID system. This is an interactive
multi-step flow:

1. User provides their MitID username.
2. The Aula login redirects through a SAML broker to MitID.
3. MitID presents **two QR codes** that the user scans with the MitID app.
4. After app approval, an OAuth 2.0 code exchange yields access + refresh tokens.

This cannot be reduced to a username/password form. The integration must handle
the interactive QR-code step during setup.

### Token lifecycle

The `aula` library's `authenticate_and_create_client()` function manages the
full lifecycle:

| Scenario | Behavior |
|----------|----------|
| First setup | Full MitID flow with QR codes |
| Tokens cached and valid | Reuse immediately — no user interaction |
| Access token expired, refresh token valid | Silent refresh — no user interaction |
| Refresh token expired | Re-trigger full MitID flow (reauth) |

Tokens include: `access_token`, `refresh_token`, `expires_at`, plus HTTP
cookies required for the Aula session.

### Config flow design

| Step | What the user sees |
|------|--------------------|
| **`user`** | Text field: MitID username |
| **`qr_code`** | Two QR codes rendered as images. User scans with MitID app and approves. The flow blocks until MitID completes or times out. |
| **`reauth_confirm`** | Shown when tokens fully expire. Same flow as initial setup. |

**Token storage**: Tokens and cookies are persisted in the config entry's `data`
dict (encrypted at rest by HA). A custom `TokenStorage` subclass bridges the
`aula` library's storage protocol to `hass.config_entries.async_update_entry()`.

**QR code rendering**: The `aula` library provides two `qrcode.QRCode` objects
via the `on_qr_codes` callback. The config flow renders these as base64-encoded
PNG data URIs in a markdown description placeholder. This is a static image —
the QR codes don't change once generated.

---

## 6. Entities

### Device model

Each **child** is represented as a Home Assistant **device**:

| Field | Value |
|-------|-------|
| Identifiers | `{(DOMAIN, child.id)}` |
| Name | Child's display name |
| Manufacturer | `Aula` |
| Model | Institution name (e.g. "Skovbørnehaven") |

All per-child entities are grouped under the child's device.

### 6.1 Presence sensor (per child)

Shows the child's current presence status at school/daycare.

| | |
|-|-|
| **Platform** | `sensor` |
| **Unique ID** | `aula_{child.id}_presence` |
| **Name** | `{child.name} Presence` |
| **State** | One of: `Not present`, `Sick`, `Reported absent`, `Present`, `Field trip`, `Sleeping`, `Spare time activity`, `Physical placement`, `Checked out` |
| **Icon** | `mdi:school` |

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `status_code` | int | Raw `PresenceState` enum value (0–8) |
| `location` | str \| None | Current location text |
| `check_in_time` | str \| None | Actual check-in time today |
| `check_out_time` | str \| None | Actual check-out time today |
| `entry_time` | str \| None | Planned/expected entry time |
| `exit_time` | str \| None | Planned/expected exit time |
| `exit_with` | str \| None | Name of person picking up the child |
| `comment` | str \| None | Staff comment for the day |
| `institution` | str \| None | Institution name |
| `main_group` | str \| None | Class or group name (e.g. "3.A") |

**Data source**: `AulaApiClient.get_daily_overview(child_id=child.id)`

### 6.2 At-school binary sensor (per child)

Simplified yes/no: is the child physically at the institution?

| | |
|-|-|
| **Platform** | `binary_sensor` |
| **Unique ID** | `aula_{child.id}_at_school` |
| **Name** | `{child.name} At School` |
| **Device class** | `presence` |
| **State** | `on` if presence status is `Present`, `Field trip`, `Sleeping`, or `Spare time activity`. `off` otherwise. |

This is the primary entity for automations ("notify me when my child arrives").

### 6.3 School calendar (per child)

Native HA calendar entity showing the child's school schedule.

| | |
|-|-|
| **Platform** | `calendar` |
| **Unique ID** | `aula_{child.id}_calendar` |
| **Name** | `{child.name} School Calendar` |

**Event mapping:**

| HA CalendarEvent field | Source |
|------------------------|--------|
| `summary` | `event.title` |
| `start` | `event.start_datetime` |
| `end` | `event.end_datetime` |
| `location` | `event.location` |
| `description` | `"Teacher: {teacher_name}"` and/or `"Substitute: {substitute_name}"` if applicable |

The calendar entity implements `async_get_events()` for the HA calendar panel,
fetching events for the requested date range on demand.

**Data source**: `AulaApiClient.get_calendar_events(institution_profile_ids, start, end)`

### 6.4 Unread messages sensor (per account)

| | |
|-|-|
| **Platform** | `sensor` |
| **Unique ID** | `aula_{profile.profile_id}_messages` |
| **Name** | `Aula Messages` |
| **State** | Number of message threads (int) |
| **State class** | `measurement` |
| **Icon** | `mdi:email` |

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `threads` | list[dict] | Up to 10 most recent threads: `{subject, thread_id}` |

**Data source**: `AulaApiClient.get_message_threads()`

### 6.5 Latest post sensor (per account)

| | |
|-|-|
| **Platform** | `sensor` |
| **Unique ID** | `aula_{profile.profile_id}_latest_post` |
| **Name** | `Aula Latest Post` |
| **State** | Title of the most recent post (truncated to 255 chars) |
| **Icon** | `mdi:bulletin-board` |

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `content` | str | Plain-text body (truncated to 1024 chars) |
| `author` | str | Post owner's full name |
| `timestamp` | datetime \| None | Publish timestamp |
| `is_important` | bool | Whether the post is flagged as important |
| `comment_count` | int | Number of comments |

**Data source**: `AulaApiClient.get_posts(institution_profile_ids, limit=1)`

### 6.6 Homework todo list (per child)

Read-only todo list showing Min Uddannelse tasks for the current week.

| | |
|-|-|
| **Platform** | `todo` |
| **Unique ID** | `aula_{child.id}_homework` |
| **Name** | `{child.name} Homework` |

**Item mapping:**

| TodoItem field | Source |
|----------------|--------|
| `uid` | `task.id` |
| `summary` | `task.title` |
| `due` | `task.due_date` |
| `status` | `completed` if `task.is_completed`, else `needs_action` |
| `description` | Course name and class/subject info |

This entity is **read-only** — `TodoListEntity.supported_features` does not
include create/update/delete.

**Data source**: `AulaApiClient.get_mu_tasks(widget_id, child_filter, institution_filter, week, session_uuid)`

> **Note**: Widget API calls require a `session_uuid` obtained from
> `get_profile_context()` and a per-widget bearer token obtained internally by
> the library. This is handled transparently by the coordinator.

---

## 7. Data Coordinators

Each data source gets its own `DataUpdateCoordinator` to allow independent
polling intervals and error isolation.

| Coordinator | Interval | Feeds entities | API methods called |
|-------------|----------|----------------|-------------------|
| **Presence** | 5 min | Presence sensor, At-school binary sensor | `get_daily_overview()` per child |
| **Calendar** | 30 min | School calendar | `get_calendar_events()` (14-day rolling window) |
| **Messages** | 15 min | Unread messages sensor | `get_message_threads()` |
| **Posts** | 30 min | Latest post sensor | `get_posts(limit=10)` |
| **Tasks** | 60 min | Homework todo list | `get_mu_tasks()` per child (current week) |

All coordinators share a single `AulaApiClient` instance.

**Error handling:**

| Error | Coordinator behavior |
|-------|---------------------|
| `HttpRequestError` (network/server) | Raise `UpdateFailed` — HA retries next interval |
| HTTP 401/403 | Raise `ConfigEntryAuthFailed` — HA shows reauth prompt |
| Token refresh fails | Raise `ConfigEntryAuthFailed` |
| No data for child | Return `None` — entity becomes `unavailable` |

---

## 8. Integration Setup Flow

When a config entry loads:

1. **Restore tokens** from config entry data.
2. **Create client**: Call `authenticate_and_create_client()` with stored tokens.
   If tokens are valid, this returns immediately with no user interaction. If
   refresh is needed, it happens silently.
3. **Fetch profile**: `client.get_profile()` → get children list and all
   institution profile IDs.
4. **Fetch profile context**: `client.get_profile_context()` → get
   `session_uuid` needed for widget APIs.
5. **Store runtime data** in `hass.data[DOMAIN][entry_id]`: the client, profile,
   children list, session UUID.
6. **Create coordinators** and trigger initial refresh.
7. **Forward** to entity platforms.

### Unload

On entry unload: cancel all coordinator timers, close the `AulaApiClient`
(which closes the underlying HTTP client).

---

## 9. Configuration Options

Configurable via the HA options flow after setup:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `scan_interval_presence` | int | 5 | Presence polling interval (minutes) |
| `scan_interval_calendar` | int | 30 | Calendar polling interval (minutes) |
| `scan_interval_messages` | int | 15 | Messages polling interval (minutes) |
| `calendar_days_ahead` | int | 14 | Days ahead to fetch calendar events |

---

## 10. File Structure

```
custom_components/aula/
├── __init__.py          # async_setup_entry, async_unload_entry
├── config_flow.py       # ConfigFlow (user + qr_code steps), OptionsFlow
├── const.py             # DOMAIN, logger, default intervals
├── coordinator.py       # All DataUpdateCoordinator subclasses
├── entity.py            # AulaEntity base class (device info)
├── sensor.py            # PresenceSensor, MessagesSensor, LatestPostSensor
├── binary_sensor.py     # AtSchoolBinarySensor
├── calendar.py          # SchoolCalendar
├── todo.py              # HomeworkTodoList
├── manifest.json
├── strings.json
└── translations/
    ├── en.json
    └── da.json
```

### manifest.json

```json
{
  "domain": "aula",
  "name": "Aula",
  "codeowners": ["@nickknissen"],
  "config_flow": true,
  "documentation": "https://github.com/nickknissen/hass-aula",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/nickknissen/hass-aula/issues",
  "requirements": ["aula>=0.1.1"],
  "version": "0.1.0"
}
```

---

## 11. Phasing

### Phase 1 — MVP

- Config flow: MitID username → QR code display → token persistence
- Reauth flow when tokens expire
- Presence sensor + at-school binary sensor (per child)
- School calendar entity (per child)
- Messages sensor (per account)
- Danish and English translations

### Phase 2

- Homework todo list (per child, Min Uddannelse)
- Latest post sensor (per account)
- Options flow for polling intervals
- Diagnostics support (`async_get_config_entry_diagnostics`)

### Phase 3 — Future

- Library loans sensor (books due, from Cicero)
- EasyIQ / Meebook weekly plan entities
- MoMo course tracking
- Event entity for message/post notifications
- Gallery as HA media source

---

## 12. Key Technical Considerations

### httpx in Home Assistant

The `aula` library uses `httpx` internally (via `HttpxHttpClient`). HA
convention is `aiohttp`. Two options:

1. **Use httpx directly** (recommended for MVP): The library bundles it. Works
   fine — httpx is async and well-maintained. List it as a requirement.
2. **Write an aiohttp adapter**: The library's `HttpClient` is a protocol, so
   we could implement it with `aiohttp.ClientSession`. However, the auth flow
   (`MitIDAuthClient`) uses `httpx` internally and does not go through the
   `HttpClient` protocol — so we can't fully eliminate the httpx dependency.

**Decision**: Use httpx for MVP. Revisit if HA core raises concerns.

### ID semantics

The `aula` library has overlapping ID concepts:

| Field | What it is | Where it's used |
|-------|-----------|-----------------|
| `child.id` | Child's institution profile ID | `get_daily_overview(child_id=...)` |
| `child.profile_id` | Child's user profile ID | Device identifier |
| `profile.institution_profile_ids` | All institution profile IDs (parent + children) | `get_calendar_events(...)`, `get_posts(...)` |

The coordinator must use the right ID for each API call.

### Widget API calls

Some endpoints (Min Uddannelse tasks, library, Meebook, EasyIQ) are third-party
widget integrations that require:

1. A `session_uuid` from `get_profile_context()["data"]["userId"]`
2. A per-widget bearer token fetched internally by `_get_bearer_token(widget_id)`
3. Child/institution filters as string lists (not ints)

The tasks coordinator must fetch the profile context to obtain the session UUID,
then pass the correct widget ID, child filters, and institution filters. The
bearer token is handled internally by the `AulaApiClient`.

### Rate limiting

Aula's API rate limits are undocumented. The default polling intervals (5–60
minutes) are conservative. If users report being rate-limited, the options flow
allows increasing intervals.

### Multi-account support

Multiple config entries (multiple MitID users) are supported. Each entry gets
its own `AulaApiClient`, token storage, and set of coordinators. No shared
global state.

---

## 13. Testing Strategy

| Layer | Approach |
|-------|----------|
| **Config flow** | Mock `authenticate_and_create_client()`. Test: successful setup, auth timeout, reauth trigger. |
| **Coordinators** | Mock `AulaApiClient` methods with fixture data. Test: successful update, `UpdateFailed` on network error, `ConfigEntryAuthFailed` on 401. |
| **Entities** | Feed coordinators with known data. Verify: entity states, attributes, unique IDs, device info. |
| **Integration** | Use `pytest-homeassistant-custom-component`. Test: full setup/unload cycle, platform forwarding. |

Test fixtures will use the `_raw` dicts preserved on all `aula` data models to
create realistic mock data.

---

## 14. Open Questions

1. **QR code UX in config flow**: HA config flows can show images via markdown
   in `description_placeholders`, but the experience of scanning two QR codes
   during setup is unusual. Should we also show the MitID OTP code as a text
   fallback for users who prefer that?

2. **Token expiry horizon**: How long do Aula refresh tokens remain valid? If
   they expire after hours (not days), the reauth prompt may fire frequently for
   users who restart HA. Needs real-world testing.

3. **Calendar `async_get_events` vs coordinator**: Should the calendar entity
   serve events purely from the coordinator's cached data, or should it make
   live API calls in `async_get_events()` for the requested range? Live calls
   are more accurate but increase API load when the user scrolls the calendar.
