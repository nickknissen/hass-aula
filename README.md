# Aula for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/nickknissen/hass-aula)](https://github.com/nickknissen/hass-aula/releases)
[![License](https://img.shields.io/github/license/nickknissen/hass-aula)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/nickknissen/hass-aula)](https://github.com/nickknissen/hass-aula/issues)

A Home Assistant integration for [Aula](https://www.aula.dk) — the Danish school communication platform. Track your children's school presence, check-in/out times, and school calendar directly in Home Assistant.

> **Note:** Aula is a Danish platform. Authentication requires a Danish **MitID** account.

---

## Features

- **Presence tracking** — Know whether your child is present, sick, absent, on a field trip, or checked out
- **Check-in / check-out times** — See exactly when your child arrived and left school
- **Entry / exit times** — Track building entry and exit separately
- **Location** — Current location reported by the school
- **School calendar** — Upcoming events including teacher, substitute, and location info
- **Multi-child support** — Each child gets their own device with a full set of entities
- **Automatic re-authentication** — Prompts for re-login when your session expires

---

## Prerequisites

- Home Assistant **2026.1** or newer
- An [Aula](https://www.aula.dk) account with children registered
- A Danish **MitID** account and the MitID app installed on your phone

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
3. Enter your **MitID username**
4. A QR code will appear on screen — scan it with the **MitID app** on your phone
5. Approve the login on your phone, then click **Submit** in Home Assistant

Once authenticated, the integration discovers all children on your account and creates a device for each one.

> If your session expires, Home Assistant will notify you and prompt you to re-authenticate via the same QR code flow.

---

## Entities

The following entities are created **per child**:

### Sensors

| Entity | Description | Default |
|--------|-------------|---------|
| `sensor.<child>_presence` | Current presence status | Enabled |
| `sensor.<child>_check_in_time` | Time the child checked in | Enabled |
| `sensor.<child>_check_out_time` | Time the child checked out | Enabled |
| `sensor.<child>_entry_time` | Time the child entered the building | Disabled |
| `sensor.<child>_exit_time` | Time the child exited the building | Disabled |
| `sensor.<child>_location` | Current reported location | Disabled |

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

### Binary Sensors

| Entity | Description | On when |
|--------|-------------|---------|
| `binary_sensor.<child>_present` | Whether the child is at school | `present`, `fieldtrip`, `sleeping`, `spare_time_activity`, or `physical_placement` |

### Calendar

| Entity | Description |
|--------|-------------|
| `calendar.<child>_school` | Upcoming school events including teacher, substitute, and location |

---

## Automation Examples

**Notify when your child arrives at school:**

```yaml
automation:
  - alias: "Child arrived at school"
    trigger:
      - platform: state
        entity_id: binary_sensor.emma_present
        to: "on"
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

---

## Update Intervals

| Data | Interval |
|------|----------|
| Presence & times | Every 5 minutes |
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

## Contributing

Contributions are welcome! Please open an [issue](https://github.com/nickknissen/hass-aula/issues) or submit a pull request.

---

## License

This project is licensed under the [MIT License](LICENSE).
