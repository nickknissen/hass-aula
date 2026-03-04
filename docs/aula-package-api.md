# Aula Python Package API Reference

> **Package:** `aula==0.6.1`
> **Source:** `../aula` (relative to this repo)
> **Last updated:** 2026-03-03

---

## Table of Contents

- [AulaApiClient](#aulaapiclient)
- [AulaWidgetsClient](#aulawidgetsclient)
- [Data Models](#data-models)
- [Enums](#enums)
- [Exceptions](#exceptions)
- [Constants](#constants)
- [HTTP Layer](#http-layer)
- [Authentication](#authentication)
- [Token Storage](#token-storage)
- [Common Patterns](#common-patterns)

---

## AulaApiClient

**Module:** `aula.api_client`

Async client for Aula API endpoints. Transport-agnostic: accepts any `HttpClient` implementation. Authentication uses `access_token` as a query parameter during `init()` to establish a server-side session, then relies on session cookies for all subsequent requests.

### Constructor

```python
AulaApiClient(
    http_client: HttpClient,
    access_token: str | None = None,
    csrf_token: str | None = None,
) -> None
```

### Session Management

| Method | Signature | Description |
|--------|-----------|-------------|
| `init` | `async init() -> None` | Discover current API version and establish guardian role |
| `is_logged_in` | `async is_logged_in() -> bool` | Check if session is still authenticated |
| `close` | `async close() -> None` | Close the HTTP client |

Supports `async with` context manager.

### Profile & Context

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_profile` | `async get_profile() -> Profile` | Fetch authenticated user's profile with children |
| `get_profile_context` | `async get_profile_context() -> dict[str, Any]` | Fetch profile context for current guardian session |

### Widgets

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_widgets` | `async get_widgets() -> list[WidgetConfiguration]` | Return widget configurations available for the current user |

### Daily Overview & Presence

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_daily_overview` | `async get_daily_overview(child_id: int) -> DailyOverview \| None` | Fetch daily overview for a specific child |
| `get_presence_templates` | `async get_presence_templates(institution_profile_ids: list[int], from_date: date, to_date: date) -> list[PresenceWeekTemplate]` | Fetch presence week templates for given profiles and date range |

### Notifications

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_notifications_for_active_profile` | `async get_notifications_for_active_profile(*, children_ids: list[int] \| None = None, institution_codes: list[str] \| None = None, offset: int = 0, limit: int = 50, module: str \| None = None) -> list[Notification]` | Fetch notifications for active profile |

### Messaging

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_message_threads` | `async get_message_threads(filter_on: str \| None = None) -> list[MessageThread]` | Fetch first page of message threads, sorted by date descending |
| `get_messages_for_thread` | `async get_messages_for_thread(thread_id: str, limit: int = 5) -> list[Message]` | Fetch latest messages for a specific thread |
| `search_messages` | `async search_messages(institution_profile_ids: list[int], institution_codes: list[str], *, text: str = "", from_date: date \| None = None, to_date: date \| None = None, has_attachments: bool \| None = None, limit: int = 100) -> list[Message]` | Search messages with server-side filtering and automatic pagination |
| `get_all_message_threads` | `async get_all_message_threads(cutoff_date: date) -> list[dict]` | Paginate threads until older than cutoff_date |
| `get_all_messages_for_thread` | `async get_all_messages_for_thread(thread_id: str) -> list[dict]` | Paginate all messages for a thread |

### Calendar

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_calendar_events` | `async get_calendar_events(institution_profile_ids: list[int], start: datetime, end: datetime) -> list[CalendarEvent]` | Fetch calendar events for given profiles and date range |

### Posts

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_posts` | `async get_posts(institution_profile_ids: list[int], page: int = 1, limit: int = 10) -> list[Post]` | Fetch posts from Aula |

### Gallery

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_gallery_albums` | `async get_gallery_albums(institution_profile_ids: list[int], limit: int = 1000) -> list[dict]` | Fetch gallery albums as raw dicts |
| `get_album_pictures` | `async get_album_pictures(institution_profile_ids: list[int], album_id: int, limit: int = 1000) -> list[dict]` | Fetch pictures for a specific album as raw dicts |

### File Downloads

| Method | Signature | Description |
|--------|-----------|-------------|
| `download_file` | `async download_file(url: str) -> bytes` | Download a file as raw bytes |

### Deprecated Widget Methods

These delegate to `self.widgets.*` and will be removed in a future version:

| Method | Delegates to |
|--------|-------------|
| `get_mu_tasks(...)` | `self.widgets.get_mu_tasks` |
| `get_ugeplan(...)` | `self.widgets.get_ugeplan` |
| `get_easyiq_weekplan(...)` | `self.widgets.get_easyiq_weekplan` |
| `get_meebook_weekplan(...)` | `self.widgets.get_meebook_weekplan` |
| `get_momo_courses(...)` | `self.widgets.get_momo_courses` |
| `get_library_status(...)` | `self.widgets.get_library_status` |

### Attributes

| Attribute | Type | Notes |
|-----------|------|-------|
| `api_url` | `str` | Base API URL with version (e.g. `https://api.aula.dk/api/v17`) |
| `widgets` | `AulaWidgetsClient` | Widget-specific API client |

---

## AulaWidgetsClient

**Module:** `aula.widgets.client`

Widget provider API client for third-party Aula integrations. Constructed internally by `AulaApiClient`.

```python
AulaWidgetsClient(api_client: _WidgetRequestClient) -> None
```

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_mu_tasks` | `async get_mu_tasks(widget_id: str, child_filter: list[str], institution_filter: list[str], week: str, session_uuid: str) -> list[MUTask]` | Fetch Min Uddannelse tasks for a given week |
| `get_ugeplan` | `async get_ugeplan(widget_id: str, child_filter: list[str], institution_filter: list[str], week: str, session_uuid: str) -> list[MUWeeklyPerson]` | Fetch Min Uddannelse weekly plans (ugebreve) |
| `get_easyiq_weekplan` | `async get_easyiq_weekplan(week: str, session_uuid: str, institution_filter: list[str], child_id: str, widget_id: str = WIDGET_EASYIQ) -> list[Appointment]` | Fetch EasyIQ weekly plan appointments |
| `get_easyiq_homework` | `async get_easyiq_homework(week: str, session_uuid: str, institution_filter: list[str], child_id: str) -> list[EasyIQHomework]` | Fetch EasyIQ homework assignments |
| `get_meebook_weekplan` | `async get_meebook_weekplan(child_filter: list[str], institution_filter: list[str], week: str, session_uuid: str) -> list[MeebookStudentPlan]` | Fetch Meebook weekly plan |
| `get_momo_courses` | `async get_momo_courses(children: list[str], institutions: list[str], session_uuid: str) -> list[MomoUserCourses]` | Fetch MoMo courses (widget v1.3) |
| `get_momo_reminders` | `async get_momo_reminders(children: list[str], institutions: list[str], session_uuid: str, from_date: str, due_no_later_than: str) -> list[UserReminders]` | Fetch MoMo reminders (widget v1.10) |
| `get_library_status` | `async get_library_status(widget_id: str, children: list[str], institutions: list[str], session_uuid: str) -> LibraryStatus` | Fetch library status from Cicero (widget v1.6) |

---

## Data Models

**Module:** `aula.models`

All models inherit from `AulaDataClass` (provides `__iter__` for serialization). Every model has an optional `_raw: dict | None` field (excluded from repr) that stores the original API response dict. Most models have a `from_dict(data: dict) -> Self` class method.

### Profile

```python
@dataclass
class Profile(AulaDataClass):
    profile_id: int
    display_name: str
    children: list[Child] = []
    institution_profile_ids: list[int] = []
```

### Child

```python
@dataclass
class Child(AulaDataClass):
    id: int               # Institution profile ID — used for API calls
    profile_id: int       # User's profile ID — displayed to users
    name: str
    institution_name: str
    profile_picture: str
```

### DailyOverview

```python
@dataclass
class DailyOverview(AulaDataClass):
    id: int | None = None
    institution_profile: InstitutionProfile | None = None
    main_group: MainGroup | None = None
    status: PresenceState | None = None
    location: str | None = None
    sleep_intervals: list[SleepInterval] = []     # SleepInterval = dict[str, str]
    check_in_time: str | None = None
    check_out_time: str | None = None
    entry_time: str | None = None
    exit_time: str | None = None
    exit_with: str | None = None
    comment: str | None = None
```

### InstitutionProfile

```python
@dataclass
class InstitutionProfile(AulaDataClass):
    profile_id: int | None = None      # Matches Child.profile_id
    id: int | None = None              # Matches Child.id
    institution_code: str | None = None
    institution_name: str | None = None
    role: str | None = None
    name: str | None = None
    profile_picture: ProfilePicture | None = None
    short_name: str | None = None
    institution_role: str | None = None
    metadata: str | None = None
```

### MainGroup

```python
@dataclass
class MainGroup(AulaDataClass):
    id: int | None = None
    name: str | None = None
    short_name: str | None = None
    institution_code: str | None = None
    institution_name: str | None = None
    uni_group_type: str | None = None
```

### CalendarEvent

```python
@dataclass
class CalendarEvent(AulaDataClass):
    id: int
    title: str
    start_datetime: datetime
    end_datetime: datetime
    teacher_name: str | None
    has_substitute: bool
    substitute_name: str | None
    location: str | None
    belongs_to: int | None
```

### Message

```python
@dataclass
class Message(AulaDataClass):
    id: str
    content_html: str
    # Properties:
    # content: str          — plain text stripped from HTML
    # content_markdown: str — HTML converted to Markdown
```

### MessageThread

```python
@dataclass
class MessageThread(AulaDataClass):
    thread_id: str
    subject: str
```

### Notification

```python
@dataclass
class Notification(AulaDataClass):
    id: str
    title: str
    module: str | None = None
    event_type: str | None = None
    notification_type: str | None = None
    institution_code: str | None = None
    created_at: str | None = None
    expires_at: str | None = None
    related_child_name: str | None = None
    post_id: int | None = None
    album_id: int | None = None
    media_id: int | None = None
    institution_profile_id: int | None = None
```

### Post

```python
@dataclass
class Post(AulaDataClass):
    id: int
    title: str
    content_html: str
    timestamp: datetime | None
    owner: ProfileReference
    allow_comments: bool
    shared_with_groups: list[dict]
    publish_at: datetime | None
    is_published: bool
    expire_at: datetime | None
    is_expired: bool
    is_important: bool
    important_from: datetime | None
    important_to: datetime | None
    attachments: list[dict]
    comment_count: int
    can_current_user_delete: bool
    can_current_user_comment: bool
    edited_at: datetime | None = None
    # Properties:
    # content: str          — plain text stripped from HTML
    # content_markdown: str — HTML converted to Markdown
```

### ProfileReference

```python
@dataclass
class ProfileReference(AulaDataClass):
    id: int
    profile_id: int
    first_name: str
    last_name: str
    full_name: str
    short_name: str
    role: str
    institution_name: str
    profile_picture: dict | None = None
```

### WidgetConfiguration

```python
@dataclass
class WidgetConfiguration(AulaDataClass):
    widget_id: str
    name: str
    widget_supplier: str
    widget_type: str
    placement: str
    is_secure: bool
    can_access_on_mobile: bool
    aggregated_display_mode: str
```

### Appointment (EasyIQ)

```python
@dataclass
class Appointment(AulaDataClass):
    appointment_id: str
    title: str
    start: str = ""
    end: str = ""
    description: str = ""
    item_type: int | None = None
```

### EasyIQHomework

```python
@dataclass
class EasyIQHomework(AulaDataClass):
    id: str
    title: str
    description: str = ""
    due_date: str = ""
    subject: str = ""
    is_completed: bool = False
```

### MUTask

```python
@dataclass
class MUTask(AulaDataClass):
    id: str
    title: str
    task_type: str
    due_date: datetime | None
    weekday: str
    week_number: int
    is_completed: bool
    student_name: str
    unilogin: str
    url: str
    classes: list[MUTaskClass] = []
    course: MUTaskCourse | None = None
    student_count: int | None = None
    completed_count: int | None = None
    placement: str | None = None
    placement_time: str | None = None
```

### MUTaskClass

```python
@dataclass
class MUTaskClass(AulaDataClass):
    id: int
    name: str
    subject_id: int
    subject_name: str
```

### MUTaskCourse

```python
@dataclass
class MUTaskCourse(AulaDataClass):
    id: str
    name: str
    icon: str
    yearly_plan_id: str
    color: str | None
    url: str | None
```

### MUWeeklyPerson / MUWeeklyInstitution / MUWeeklyLetter

```python
@dataclass
class MUWeeklyPerson(AulaDataClass):
    name: str
    id: int
    unilogin: str
    institutions: list[MUWeeklyInstitution] = []

@dataclass
class MUWeeklyInstitution(AulaDataClass):
    name: str
    code: int
    letters: list[MUWeeklyLetter] = []

@dataclass
class MUWeeklyLetter(AulaDataClass):
    group_id: int
    group_name: str
    content_html: str
    week_number: int
    sort_order: int
```

### MeebookStudentPlan / MeebookDayPlan / MeebookTask

```python
@dataclass
class MeebookStudentPlan(AulaDataClass):
    name: str
    unilogin: str
    week_plan: list[MeebookDayPlan] = []

@dataclass
class MeebookDayPlan(AulaDataClass):
    date: str
    tasks: list[MeebookTask] = []

@dataclass
class MeebookTask(AulaDataClass):
    id: int
    type: str
    title: str
    content: str
    pill: str
    link_text: str
```

### MomoUserCourses / MomoCourse

```python
@dataclass
class MomoUserCourses(AulaDataClass):
    user_id: str
    name: str
    courses: list[MomoCourse] = []

@dataclass
class MomoCourse(AulaDataClass):
    id: str
    title: str
    institution_id: str
    image: str | None
```

### UserReminders / TeamReminder / AssignmentReminder

```python
@dataclass
class UserReminders(AulaDataClass):
    user_id: int
    user_name: str
    team_reminders: list[TeamReminder] = []
    assignment_reminders: list[AssignmentReminder] = []

@dataclass
class TeamReminder(AulaDataClass):
    id: int
    institution_name: str
    institution_id: int
    due_date: str
    team_id: int
    team_name: str
    reminder_text: str
    created_by: str
    last_edit_by: str
    subject_name: str

@dataclass
class AssignmentReminder(AulaDataClass):
    id: int
    institution_name: str
    institution_id: int
    due_date: str
    course_id: int
    team_names: list[str]
    team_ids: list[int]
    assignment_id: int
    assignment_text: str
```

### LibraryStatus / LibraryLoan

```python
@dataclass
class LibraryStatus(AulaDataClass):
    loans: list[LibraryLoan] = []
    longterm_loans: list[LibraryLoan] = []
    reservations: list[dict] = []
    branch_ids: list[str] = []

@dataclass
class LibraryLoan(AulaDataClass):
    id: int
    title: str
    author: str
    patron_display_name: str
    due_date: str
    number_of_loans: int
    cover_image_url: str = ""
```

### Presence Templates

```python
@dataclass
class PresenceWeekTemplate(AulaDataClass):
    institution_profile: InstitutionProfile | None = None
    day_templates: list[DayTemplate] = []

@dataclass
class DayTemplate(AulaDataClass):
    id: int | None = None
    day_of_week: int | None = None
    by_date: str | None = None
    repeat_pattern: str | None = None
    repeat_from_date: str | None = None
    repeat_to_date: str | None = None
    is_on_vacation: bool = False
    activity_type: int | None = None
    entry_time: str | None = None
    exit_time: str | None = None
    exit_with: str | None = None
    comment: str | None = None
    spare_time_activity: SpareTimeActivity | None = None

@dataclass
class SpareTimeActivity(AulaDataClass):
    start_time: str | None = None
    end_time: str | None = None
    comment: str | None = None
```

### ProfilePicture

```python
@dataclass
class ProfilePicture(AulaDataClass):
    url: str | None = None
```

---

## Enums

### PresenceState

**Module:** `aula.models.presence`

| Value | Int | English | Danish |
|-------|-----|---------|--------|
| `NOT_PRESENT` | 0 | Not Present | Ikke kommet |
| `SICK` | 1 | Sick | Syg |
| `REPORTED_ABSENT` | 2 | Reported Absent | Ferie/fri |
| `PRESENT` | 3 | Present | Til stede |
| `FIELDTRIP` | 4 | Field Trip | På tur |
| `SLEEPING` | 5 | Sleeping | Sover |
| `SPARE_TIME_ACTIVITY` | 6 | Spare Time Activity | Til aktivitet |
| `PHYSICAL_PLACEMENT` | 7 | Physical Placement | Fysisk placering |
| `CHECKED_OUT` | 8 | Checked Out | Gået |

**Properties:** `display_name: str`, `danish_name: str`
**Class method:** `get_display_name(value: int) -> str`

---

## Exceptions

### HTTP Exceptions (`aula.http`)

```
HttpRequestError                 — Base; any non-2xx response
├── AulaAuthenticationError      — 401/403
├── AulaRateLimitError           — 429
├── AulaServerError              — 5xx
├── AulaNotFoundError            — 404
└── AulaConnectionError          — Network errors (status_code=0)
```

All store `status_code: int` as an attribute.

### Auth Exceptions (`aula.auth.exceptions`)

```
MitIDAuthError                   — Base for MitID auth failures
├── MitIDError                   — MitID protocol errors
├── NetworkError                 — Network failures during auth
├── SAMLError                    — SAML protocol errors
├── OAuthError                   — OAuth flow failures
├── TokenInvalidError            — TOTP code rejected
└── PasswordInvalidError         — MitID password rejected
```

---

## Constants

**Module:** `aula.const`

### API URLs

```python
API_URL = "https://www.aula.dk/api/v"
API_VERSION = "23"
MIN_UDDANNELSE_API = "https://api.minuddannelse.net/aula"
SYSTEMATIC_API = "https://systematic-momo.dk/api/aula"
EASYIQ_API = "https://api.easyiqcloud.dk/api/aula"
MEEBOOK_API = "https://app.meebook.com/aulaapi"
CICERO_API = "https://surf.cicero-suite.com/portal-api/rest/aula"
```

### Widget IDs

```python
WIDGET_EASYIQ = "0001"
WIDGET_EASYIQ_WEEKPLAN = "0128"
WIDGET_EASYIQ_HOMEWORK = "0142"
WIDGET_BIBLIOTEKET = "0019"
WIDGET_MIN_UDDANNELSE_UGEPLAN = "0029"
WIDGET_MIN_UDDANNELSE = "0030"
WIDGET_MEEBOOK = "0004"
WIDGET_HUSKELISTEN = "0062"
```

### Auth URLs

```python
AUTH_BASE_URL = "https://login.aula.dk"
OAUTH_AUTHORIZE_PATH = "/simplesaml/module.php/oidc/authorize.php"
OAUTH_TOKEN_PATH = "/simplesaml/module.php/oidc/token.php"
APP_REDIRECT_URI = "https://app-private.aula.dk"
OAUTH_CLIENT_ID = "_99949a54b8b65423862aac1bf629599ed64231607a"  # Level 3 = full MitID
OAUTH_SCOPE = "aula-sensitive"
```

### CSRF

```python
CSRF_TOKEN_COOKIE = "Csrfp-Token"      # Cookie name (PascalCase)
CSRF_TOKEN_HEADER = "csrfp-token"      # Header name (lowercase)
```

### Other

```python
DOMAIN = "aula"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
BROKER_URL = "https://broker.unilogin.dk"
MITID_BASE_URL = "https://nemlog-in.mitid.dk"
```

---

## HTTP Layer

**Module:** `aula.http` (protocol), `aula.http_httpx` (implementation)

### HttpClient Protocol

```python
@runtime_checkable
class HttpClient(Protocol):
    async def request(
        self, method: str, url: str, *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> HttpResponse: ...

    async def download_bytes(self, url: str) -> bytes: ...
    def get_cookie(self, name: str) -> str | None: ...
    async def close(self) -> None: ...
```

### HttpResponse

```python
@dataclass
class HttpResponse:
    status_code: int
    data: Any = None                    # Pre-parsed JSON
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any: ...          # Returns self.data (sync)
    def raise_for_status(self) -> None: ...  # Maps status codes to exceptions
```

### HttpxHttpClient

```python
class HttpxHttpClient:
    def __init__(
        self,
        cookies: dict[str, str] | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None: ...
```

- `follow_redirects=True`
- Timeout: 30s connect, 60s read (120s read for downloads)
- Sets `User-Agent` from `const.USER_AGENT`
- If `httpx_client` is provided, caller retains ownership and must close it

---

## Authentication

**Module:** `aula.auth.mitid_client` (low-level), `aula.auth_flow` (high-level)

### High-Level Functions

#### authenticate()

```python
async def authenticate(
    mitid_username: str,
    token_storage: TokenStorage | None = None,
    on_qr_codes: Callable | None = None,
    on_login_required: Callable | None = None,
    httpx_client: httpx.AsyncClient | None = None,
    force_login: bool = False,
    on_identity_selected: Callable | None = None,
    auth_method: str = "app",            # "app" or "token"
    on_token_digits: Callable | None = None,
    on_password: Callable | None = None,
) -> dict[str, Any]
```

Handles cached tokens, refresh, and fresh MitID login. Returns token data dict.

#### create_client()

```python
async def create_client(
    token_data: dict[str, Any],
    http_client: HttpClient | None = None,
) -> AulaApiClient
```

Creates a ready-to-use `AulaApiClient` from stored credentials. Calls `init()` internally.

#### authenticate_and_create_client()

```python
async def authenticate_and_create_client(
    mitid_username: str,
    token_storage: TokenStorage,
    ...  # same params as authenticate()
) -> AulaApiClient
```

Convenience wrapper combining `authenticate()` + `create_client()`.

### MitIDAuthClient

```python
class MitIDAuthClient:
    def __init__(
        self,
        mitid_username: str,
        timeout: int = 30,
        on_qr_codes: Callable | None = None,
        httpx_client: httpx.AsyncClient | None = None,
        on_identity_selected: Callable | None = None,
        auth_method: str = "app",
        on_token_digits: Callable | None = None,
        on_password: Callable | None = None,
    ) -> None: ...

    async def authenticate(self) -> dict[str, Any]:
        """7-step OAuth + SAML + MitID flow. Returns {"success": True, "tokens": {...}}"""

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh using stored refresh_token. Returns updated token dict."""
```

**Properties:** `access_token`, `refresh_token`, `tokens`, `is_authenticated`, `cookies`

### Token Structure

```python
{
    "access_token": "...",
    "refresh_token": "...",
    "expires_in": 3600,
    "expires_at": 1709487234.5,   # Unix timestamp
    "token_type": "Bearer",
}
```

### Authentication Flow Steps

1. Start OAuth flow (PKCE parameters)
2. Follow redirect to MitID
3. MitID authentication (app QR/OTP or hardware token + password)
4. Complete MitID flow → SAML response
5. SAML broker processing
6. Complete Aula login
7. Exchange OAuth code for tokens

### Session Lifecycle

1. `access_token` passed as query param during `AulaApiClient.init()`
2. Server sets session cookies (including `Csrfp-Token`)
3. `access_token` is cleared after init
4. All subsequent requests use session cookies only
5. `csrfp-token` header is added to POST requests automatically

---

## Token Storage

**Module:** `aula.token_storage`

### TokenStorage (ABC)

```python
class TokenStorage(ABC):
    async def load(self) -> dict[str, Any] | None: ...
    async def save(self, data: dict[str, Any]) -> None: ...
```

### FileTokenStorage

```python
class FileTokenStorage(TokenStorage):
    def __init__(self, path: str | Path) -> None: ...
```

Persisted data format:

```python
{
    "timestamp": 1709487234.5,
    "created_at": "2024-03-03 10:00:34",
    "username": "mitid_username",
    "tokens": { ... },
    "cookies": {
        "Csrfp-Token": "...",
        # other session cookies
    }
}
```

---

## Common Patterns

### child.id vs child.profile_id

- `Child.id` = Institution profile ID. **Use this for API calls** (e.g. `get_daily_overview(child_id=child.id)`)
- `Child.profile_id` = User's profile ID. Displayed to users, matches `InstitutionProfile.profile_id`
- When mapping `DailyOverview.institution_profile` to a `Child`, match on the `id` field

### Widget Token Flow

1. Call `get_widgets()` to discover available widgets and their IDs
2. Internally, `_get_bearer_token(widget_id)` fetches a per-widget bearer token
3. Widget requests use this bearer token in the `Authorization` header
4. Each widget provider has its own API base URL (see Constants)

### Widget Method Parameters

Most widget methods share a common parameter pattern:

- `widget_id: str` — The widget ID constant (e.g. `WIDGET_MIN_UDDANNELSE`)
- `child_filter: list[str]` — List of child IDs (as strings)
- `institution_filter: list[str]` — List of institution codes (as strings)
- `week: str` — ISO week string (e.g. `"2024-W10"`)
- `session_uuid: str` — Unique session identifier

### API Version Handling

- Current default: `API_VERSION = "23"`
- `_request_with_version_retry()` automatically bumps the version on 410 Gone
- `_set_correct_api_version()` discovers the correct version during `init()`

### Package Exports

All public types are available from the top-level `aula` package:

```python
from aula import (
    AulaApiClient, AulaWidgetsClient,
    authenticate, create_client,
    HttpClient, HttpResponse, HttpxHttpClient,
    HttpRequestError, AulaAuthenticationError, AulaConnectionError,
    AulaNotFoundError, AulaRateLimitError, AulaServerError,
    TokenStorage, FileTokenStorage,
    Profile, Child, DailyOverview, Message, MessageThread,
    CalendarEvent, WidgetConfiguration,
)
```

Additional models must be imported from `aula.models`:

```python
from aula.models import (
    Appointment, EasyIQHomework, LibraryLoan, LibraryStatus,
    MeebookStudentPlan, MomoUserCourses, UserReminders,
    MUTask, MUWeeklyPerson, Notification, Post,
    PresenceWeekTemplate, DayTemplate, SpareTimeActivity,
)
```

Enums:

```python
from aula.models.presence import PresenceState
```

Constants:

```python
from aula.const import (
    WIDGET_EASYIQ, WIDGET_BIBLIOTEKET, WIDGET_MIN_UDDANNELSE,
    WIDGET_MEEBOOK, WIDGET_HUSKELISTEN, ...
)
```
