# Aula for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/nickknissen/hass-aula)](https://github.com/nickknissen/hass-aula/releases)
[![License](https://img.shields.io/github/license/nickknissen/hass-aula)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/nickknissen/hass-aula)](https://github.com/nickknissen/hass-aula/issues)

A Home Assistant integration for [Aula](https://www.aula.dk) — the Danish school communication platform. Track your children's school presence and school calendar directly in Home Assistant.

> **Note:** Aula is a Danish platform. Authentication requires a Danish **MitID** account.

---

## Features

- **Presence tracking** — Know whether your child is present, sick, absent, on a field trip, or checked out, with check-in/out times, entry/exit times, and location as attributes
- **School calendar** — Upcoming events including teacher, substitute, and location info
- **Notifications** — Fires a Home Assistant event for each new Aula notification, enabling automations to push alerts to your phone
- **Set pick-up times** — The `hass_aula.update_presence` action writes planned drop-off/pick-up times back to Aula for one or more children at once
- **Multi-child support** — Each child gets their own device with a full set of entities
- **Automatic re-authentication** — Prompts for re-login when your session expires

---

## Why a separate integration?

[scaarup/aula](https://github.com/scaarup/aula) came first, is in the HACS default store, and still works — if it covers what you need, use it. This project exists because of a structural difference, not a missing feature.

Everything Aula-specific here — the MitID login flow, the API client, the data models — lives in [`aula`](https://pypi.org/project/aula/), a standalone typed Python package with its own test suite and release cycle. It ships a CLI and can be used from any program, and this repository is only the thin Home Assistant layer on top. That split is what makes the rest practical: a coordinator per data domain with its own poll interval, typed models rather than dictionary lookups, reauthentication and reconfiguration flows, diagnostics, and translations.

Arriving there as a pull request would have meant replacing almost all of the existing integration's internals in one go — a rewrite wearing a PR's clothes, aimed at a codebase whose users are happy with it. Two integrations making different trade-offs seemed healthier than one disruptive change. Ideas still travel between them: `get_thread_messages` came from [a fork](https://github.com/dkpoulsen/hass-aula) of this project. And where the two look most alike — speaking the MitID protocol — both trace back to the same upstream, [Hundter/MitID-BrowserClient](https://github.com/Hundter/MitID-BrowserClient).

---

## Prerequisites

- Home Assistant **2026.1** or newer
- An [Aula](https://www.aula.dk) account with children registered
- A Danish **MitID** account, with either the MitID app on your phone or a MitID code display (kodeviser)

---

## Installation

### Via HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations**
3. Click the three-dot menu → **Custom repositories**
4. Add `https://github.com/nickknissen/hass-aula` with category **Integration**
5. Search for **Aula** and click **Download**
6. Restart Home Assistant

### Manual

1. Download the [latest release](https://github.com/nickknissen/hass-aula/releases/latest)
2. Copy the `custom_components/hass_aula` folder into your Home Assistant `custom_components` directory
3. Restart Home Assistant

---

## Configuration

The integration is configured entirely through the UI — no YAML required.

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Aula**
3. Enter your **MitID username** and pick a login method

**MitID app**

4. A QR code will appear on screen — scan it with the **MitID app** on your phone
5. Approve the login on your phone, then click **Submit** in Home Assistant

**MitID code display (kodeviser)**

4. Enter your **MitID password** and the 6 digits shown on your code display
5. Read the code right before you submit, since it expires quickly

The password and the code are used for that one login only. Neither is stored in Home Assistant.

Once authenticated, the integration discovers all children on your account and creates a device for each one.

> If your session expires, Home Assistant will notify you and prompt you to re-authenticate with the same method you chose at setup.

---

## Entities

The following entities are created **per child**:

### Sensors

**Per child:**

| Entity | Description |
|--------|-------------|
| `sensor.<child>_presence` | Current presence status (see values below) |

**Presence sensor attributes:**

| Attribute | Description |
|-----------|-------------|
| `check_in_time` | Time the child checked in |
| `check_out_time` | Time the child checked out |
| `entry_time` | Time the child entered the building |
| `exit_time` | Time the child exited the building |
| `location` | Current reported location |

**Presence status values:**

| Value | Meaning |
|-------|---------|
| `present` | Child is at school |
| `not_present` | Child is not at school |
| `sick` | Reported sick |
| `reported_absent` | Reported absent |
| `fieldtrip` | On a field trip |
| `sleeping` | Sleeping (e.g. nursery) |
| `spare_time_activity` | In a spare time activity |
| `physical_placement` | Physical placement |
| `checked_out` | Checked out |

**Per profile (parent account):**

| Entity | Description |
|--------|-------------|
| `sensor.<profile>_unread_notifications` | Number of unread Aula notifications |
| `sensor.<profile>_latest_messages` | Number of unread message threads |

**Unread notifications sensor attributes:**

| Attribute | Description |
|-----------|-------------|
| `total` | Total number of notifications |
| `recent` | List of the 5 most recent notification titles |

**Latest messages sensor attributes:**

| Attribute | Description |
|-----------|-------------|
| `messages` | The 5 most recent message threads |

Each entry in `messages` carries `thread_id`, `subject`, `sender`, `date`, `unread`
and a `preview` of the newest message in that thread (clipped to 200 characters).
Pass a `thread_id` to [`hass_aula.get_thread_messages`](#hass_aulaget_thread_messages)
to read the full text.

### Calendar

| Entity | Description |
|--------|-------------|
| `calendar.<child>_school` | Upcoming school events including teacher, substitute, and location |

---

## Actions

### `hass_aula.update_presence`

Sets the planned drop-off and pick-up times for one or more children — the same thing you would otherwise do by hand under **Komme/gå** in Aula.

Target one or more **child devices** (or any entity belonging to them). Every targeted child gets the same times, so a single call can cover all your children.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_time` | yes | Time the child is dropped off, e.g. `08:00` |
| `exit_time` | yes | Time the child is collected or allowed to leave, e.g. `15:30` |
| `date` | no | Day to update. Defaults to today |
| `activity_type` | no | `picked_up_by` (default), `self_decider`, `send_home`, `go_home_with`, `drop_off_time` |
| `exit_with` | conditional | Who collects the child. **Required** for `picked_up_by` and `go_home_with`. Include the relation exactly as Aula shows it, e.g. `"Nick Nissen (Far)"` |
| `comment` | no | Note for the staff |
| `repeat` | no | `never` (default), `weekly`, `every_2_weeks` |
| `expires_at` | no | When a repeating entry stops. Defaults to the end of the school year |

If a template already exists for that date it is **updated**, not duplicated. The presence sensors refresh automatically once the change is accepted.

```yaml
action: hass_aula.update_presence
target:
  device_id:
    - abc123def456  # Emilie
    - 789ghi012jkl  # Karla
data:
  entry_time: "08:00"
  exit_time: "15:30"
  activity_type: picked_up_by
  exit_with: "Nick Nissen (Far)"
  comment: "Går til fodbold bagefter"
```

**Leave work early on Fridays:**

```yaml
automation:
  - alias: "Early Friday pickup"
    triggers:
      - trigger: time
        at: "06:00:00"
    conditions:
      - condition: time
        weekday:
          - fri
    actions:
      - action: hass_aula.update_presence
        target:
          device_id: abc123def456
        data:
          entry_time: "08:00"
          exit_time: "13:00"
          exit_with: "Nick Nissen (Far)"
```

### `hass_aula.get_thread_messages`

Returns the full text of the messages in one thread. The `latest_messages` sensor only carries 200-character previews, so this is how you read a whole message.

| Field | Required | Description |
|-------|----------|-------------|
| `thread_id` | yes | Thread to read. Taken from the `messages` attribute of the Latest messages sensor |
| `limit` | no | How many of the newest messages to return, 1–50. Defaults to 5 |
| `config_entry_id` | no | Which Aula account to read. Only needed if you have more than one configured |

This action returns a response, so call it with `response_variable`:

```yaml
sequence:
  - action: hass_aula.get_thread_messages
    data:
      thread_id: >
        {{ state_attr('sensor.test_parent_latest_messages', 'messages')[0].thread_id }}
    response_variable: thread
  - action: notify.mobile_app_my_phone
    data:
      message: "{{ thread.messages[0].content }}"
```

Each entry in `messages` carries `id`, `content` (plain text) and `content_markdown`.

---

## Events

### `hass_aula_notification`

Fired each time a **new** notification appears on your Aula account (checked every 5 minutes). The first fetch after startup is silent — events are only fired for notifications that arrive after Home Assistant starts.

| Field | Type | Description |
|-------|------|-------------|
| `notification_id` | `string` | Unique notification ID |
| `title` | `string` | Notification title |
| `module` | `string \| null` | Aula module that generated the notification (e.g. `"messaging"`) |
| `event_type` | `string \| null` | Event type within the module |
| `related_child_name` | `string \| null` | Name of the child this notification relates to |
| `created_at` | `string \| null` | ISO timestamp of when the notification was created |

---

## Automation Examples

**Notify when your child arrives at school:**

```yaml
automation:
  - alias: "Child arrived at school"
    trigger:
      - platform: state
        entity_id: sensor.emma_presence
        to: "present"
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: "Emma has arrived at school"
```

**Notify when your child is reported sick:**

```yaml
automation:
  - alias: "Child reported sick"
    trigger:
      - platform: state
        entity_id: sensor.emma_presence
        to: "sick"
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: "Emma has been reported sick today"
```

**Push a notification to your phone when a new Aula message arrives:**

```yaml
automation:
  - alias: "Forward Aula notification to phone"
    trigger:
      - platform: event
        event_type: hass_aula_notification
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Aula: {{ trigger.event.data.title }}"
          message: >
            {% if trigger.event.data.related_child_name %}
              {{ trigger.event.data.related_child_name }}: {{ trigger.event.data.title }}
            {% else %}
              {{ trigger.event.data.title }}
            {% endif %}
```

**Only forward unread messages from a specific module:**

```yaml
automation:
  - alias: "Forward Aula messages"
    trigger:
      - platform: event
        event_type: hass_aula_notification
        event_data:
          module: messaging
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "New Aula message"
          message: "{{ trigger.event.data.title }}"
```

---

## Update Intervals

| Data | Interval |
|------|----------|
| Presence & times | Every 5 minutes |
| Notifications | Every 5 minutes |
| School calendar | Every 60 minutes |

---

## Troubleshooting

**QR code does not appear**
- Make sure no browser extension is blocking iframes or SVGs
- Try opening the integration setup in a different browser

**Authentication fails after scanning QR**
- Ensure you are approving in the MitID app *before* clicking Submit
- Check that your MitID app is up to date

**No children found after setup**
- Verify that your Aula account has children linked to it
- Try re-authenticating via **Settings → Devices & Services → Aula → Reconfigure**

**Entities show unavailable**
- Check Home Assistant logs for connection or rate limit errors
- Aula may be temporarily unavailable — the integration will retry automatically

---

## Development

### Setup

1. Clone the repository and create a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Install [prek](https://prek.j178.dev) and use the provided pre-commit config:

   ```bash
   uv tool install prek
   prek install
   ```

### Running Home Assistant locally

```bash
scripts/develop
```

This starts a local Home Assistant instance with the integration loaded from `custom_components/`.

## Contributing

Contributions are welcome! Please open an [issue](https://github.com/nickknissen/hass-aula/issues) or submit a pull request.

---

## License

This project is licensed under the [MIT License](LICENSE).
