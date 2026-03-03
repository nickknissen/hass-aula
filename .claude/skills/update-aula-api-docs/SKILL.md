---
name: update-aula-api-docs
description: Regenerate docs/aula-package-api.md from the aula package source at ../aula
argument-hint: ""
---

# Update Aula Package API Reference

Regenerate `docs/aula-package-api.md` by reading the current source code of the `aula` PyPI package located at `../aula`.

## Steps

1. **Read the existing reference** at `docs/aula-package-api.md` to understand the current structure and format.

2. **Determine the package version** by reading `../aula/pyproject.toml`.

3. **Explore the source** at `../aula/src/aula/` using parallel agents. Cover all of these areas:
   - `api_client.py` — every public method on `AulaApiClient` with full signature, return type, one-line description
   - `widgets/client.py` — every public method on `AulaWidgetsClient`
   - `models/` — every dataclass with all fields and types
   - `models/presence.py` — `PresenceState` enum values
   - `http.py` — `HttpClient` protocol, `HttpResponse`, exception hierarchy
   - `http_httpx.py` — `HttpxHttpClient` implementation details
   - `const.py` — all constants (API URLs, widget IDs, auth endpoints)
   - `auth/` — `MitIDAuthClient`, `BrowserClient`, auth exceptions
   - `auth_flow.py` — `authenticate()`, `create_client()`, `authenticate_and_create_client()`
   - `token_storage.py` — `TokenStorage` ABC, `FileTokenStorage`
   - `__init__.py` — public exports / `__all__`

4. **Rewrite `docs/aula-package-api.md`** preserving the same section structure:
   - Table of Contents
   - AulaApiClient
   - AulaWidgetsClient
   - Data Models
   - Enums
   - Exceptions
   - Constants
   - HTTP Layer
   - Authentication
   - Token Storage
   - Common Patterns

5. **Update the version** in the header and the "Last updated" date.

6. **Spot-check** 3-5 items (method signatures, model fields, constants) to confirm accuracy.

## Formatting Rules

- Use tables for method listings: `| Method | Signature | Description |`
- Use fenced code blocks for class definitions showing fields
- Keep descriptions to one line
- Include `_raw: dict | None` note once in the Data Models preamble, don't repeat per-model
- Document both `child.id` (institution profile ID, for API calls) and `child.profile_id` (user profile ID) in Common Patterns
- Note deprecated methods in AulaApiClient that delegate to `self.widgets.*`
