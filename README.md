# MiTY Research for Home Assistant

**Your home. Your data. Your choice.**

MiTY Research lets a Home Assistant installation self-enroll as a device in a MiTY citizen-science trial and contribute selected sensor readings to research — on the participant's own terms. No account, no email, no name: your Home Assistant instance enrolls anonymously using a study's enrollment code, and only pseudonymous sensor data is ever sent.

This integration follows the **Data Reciprocity Principle**: a participant chooses exactly what to share, how often, and can pause or leave at any time — nothing is collected that wasn't explicitly selected.

- You choose the data.
- You choose the frequency.
- You can pause at any time.
- Your device is pseudonymous — no personal information is ever transmitted.
- You can leave a study and request deletion of your data at any time.

## Status

This is an early, actively-developed release covering enrollment, data contribution, pass/fail feedback, and multi-study participation (roadmap milestones 1–4 and 6 below). Home health score / insights polling (milestone 5) has a confirmed backend contract but isn't built on the Home Assistant side yet. See [Roadmap](#roadmap) and [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md) for what's confirmed vs. still proposed.

## Installation

### HACS (custom repository, until this is listed in the default HACS store)

1. In Home Assistant, open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add this repository's URL with category **Integration**.
3. Search for **MiTY Research** in HACS and install it.
4. Restart Home Assistant.

### Manual

Copy `custom_components/mity` into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Setup

Go to **Settings → Devices & Services → Add Integration** and search for **MiTY Research**. You will need:

- The **MiTY endpoint URL** for the platform you're contributing to.
- The **enrollment code** for the specific study you're joining (provided by the study — e.g. a QR code or printed code on the study's own materials). This is *not* a personal password; it's shared by everyone enrolling in that study.

The setup flow has five steps:

1. **Connect** — enter the endpoint and enrollment code, optionally name the study, and agree to the [MiTY Terms & Conditions](https://www.mi-ty-tre.co.uk/terms). Nothing is enrolled until you agree.
2. **Select parameters** — choose which of your existing Home Assistant entities to share. Every citizen-science trial currently shares one fixed set of fields: indoor temperature, indoor humidity, motion/occupancy, and energy usage. You can leave any of these blank.
3. **Zones** — for each sensor you mapped, pick which room/zone it's in (required by the HERD-IoT data format — see [What gets sent](#what-gets-sent)).
4. **Sensor details** *(optional)* — manufacturer, model, firmware version, calibration date, measurement uncertainty, and how the sensor connects. Skippable; used only to document measurement provenance for research purposes.
5. **Set frequency** — how often (in minutes) your data is sent. Default 240 minutes; allowed range 60–10,080 minutes (1 hour to 1 week).

On completion, MiTY creates a permanent, pseudonymous device identity for your installation and a device appears in Home Assistant, named after the study (or "MiTY Research" if you didn't give it a name).

You can change your parameter mapping, zones, sensor details, frequency, and the study's display name at any time from the integration's **Configure** option, without re-enrolling.

### Contributing to more than one study

A MiTY trial and a "study" are the same thing — there's no separate "browse and join" step today. To join a second study, add the **MiTY Research** integration again (**Settings → Devices & Services → Add Integration**) using that study's own enrollment code. Each study becomes its own device with its own status, entities, and events, so automations can target one study specifically if needed. Give each one a distinct name in step 1 (or rename later via **Configure**) so they're easy to tell apart.

Deleting a study's integration entry from Home Assistant automatically withdraws from that study on MiTY's side (equivalent to `mity.leave_study` with `remove_only` — your already-submitted data is kept). Use the `mity.leave_study` service first if you specifically want to request deletion of your data as part of leaving.

## What gets sent

Only the entities you explicitly map, on the schedule you set, as **HERD-IoT v1.0** observations (Rowan Tree Scientific's HERD-IoT Implementation Guide) — one JSON-LD entity per mapped sensor, submitted as a batch to `POST /api/v1/herd/direct`:

```json
{
  "id": "urn:herd-iot:MiTy-TRE:citizen-science:GDV-0000002a:living-room:env:temperature:sensor-living-room-temperature:0192e4a8-7b3c-7def-8123-4a5b6c7d8e9f",
  "type": "HERDObservation",
  "observedAt": "2026-08-31T18:00:00.000Z",
  "hasSimpleResult": { "type": "Property", "value": 21.4, "unitCode": "DEG_C" },
  "herdVersion": "1.0.0",
  "deviceProvenance": {
    "type": "Property",
    "value": {
      "manufacturer": "Aico",
      "model": "Environmental Sensor Gen 3",
      "samplingInterval": 14400,
      "communicationProtocol": "zigbee"
    }
  }
}
```

No entity IDs, friendly names, or anything else identifying your household is sent in plain form — the sensor identity in the URI (`sensor-living-room-temperature`) is derived from your entity ID but never reveals the value itself, and the property token is pseudonymous.

`deviceProvenance` (manufacturer/model/firmware/calibration date/measurement uncertainty/communication protocol) only appears if you fill it in during setup — entirely optional, asked for once during setup or via **Configure**, and shared across every sensor you map in that pass.

> **This is a live migration, not a finished integration.** The MiTY backend is being rebuilt against this spec at the time of writing, and several fields here are best-guess placeholders pending confirmation from the platform team — most importantly the pseudonymous property token, which this integration currently derives locally rather than receiving from a real Glass Door Vault enrollment (a real token can only come from the vault, by design). See [docs/HERD_IOT_MIGRATION.md](docs/HERD_IOT_MIGRATION.md) for the full list of what's confirmed vs. placeholder, and don't be surprised if `sensor.mity_status` shows `rejected` until the backend and this integration converge on the open items there.

## Entities

Once enrolled, a device appears (named after the study, per config entry) with:

| Entity | Type | Description |
|---|---|---|
| `sensor.mity_status` | Sensor | Result of the last submission (`accepted`, `rejected`, `error`, `paused`, `unconfigured`) |
| `sensor.mity_last_submission` | Sensor (timestamp) | When data was last sent |
| `sensor.mity_next_submission` | Sensor (timestamp) | When data will next be sent |
| `sensor.mity_parameters_configured` | Sensor | How many of the available parameters are mapped, e.g. `2/4` |
| `binary_sensor.mity_connected` | Binary sensor | On if the last submission reached MiTY |
| `binary_sensor.mity_submission_healthy` | Binary sensor (problem) | On if the last submission was rejected or errored |
| `binary_sensor.mity_paused` | Binary sensor | Mirrors the pause switch |
| `switch.mity_pause_contribution` | Switch | Pause/resume sending data. **MiTY never enforces pause server-side** — this switch is what actually stops submissions; it also tells MiTY's own dashboards your device is paused (not broken/offline) |
| `button.mity_send_data_now` | Button | Submit immediately, outside the normal schedule |
| `button.mity_refresh_configuration` | Button | Force a coordinator refresh |

## Events

Fired on the Home Assistant event bus so you can build your own automations:

| Event | Fired when |
|---|---|
| `mity_data_accepted` | A submission was accepted |
| `mity_data_rejected` | A submission was rejected |
| `mity_data_error` | A submission couldn't be completed (auth, connection, or other API error) |

Example automation — notify on a failed submission:

```yaml
automation:
  - alias: "Notify if MiTY submission fails"
    trigger:
      - platform: event
        event_type: mity_data_error
    action:
      - service: notify.mobile_app
        data:
          message: "MiTY data submission failed: {{ trigger.event.data.error }}"
```

## Services

| Service | Description |
|---|---|
| `mity.send_now` | Submit the currently mapped parameters immediately |
| `mity.leave_study` | Withdraw this device (`remove_only` keeps existing data; `remove_and_delete` also requests deletion, subject to the study's own policy — immediate or after a cool-off period) |
| `mity.rejoin_study` | Reactivate a previously-withdrawn device using its stored rejoin token (only works if the study's policy allows rejoining under the same identity) |

`mity.leave_study` and `mity.rejoin_study` are deliberately services rather than buttons — leaving a study is a meaningful decision that shouldn't be one accidental tap away. All three services take an `entry_id`, so if you've joined multiple studies, pick which one's config entry to act on (the entry ID picker in the Home Assistant service UI shows each by its study name).

## Privacy and data handling

- Enrollment is fully anonymous: no account, email, or name is ever collected by MiTY or requested by this integration.
- Your device's MiTY credentials (`device_api_key`, `rejoin_token`) are stored in Home Assistant's own encrypted config entry storage, the same way any other integration's API keys are. They are redacted from diagnostics downloads.
- Only the fields you explicitly map are ever sent — nothing is collected passively.
- You can pause contribution at any time (`switch.mity_pause_contribution`), or leave the study entirely (`mity.leave_study`), including requesting deletion of previously-submitted data.
- Full detail on how withdrawal, deletion and rejoining work is in the source design document: `Citizen Science AutoEnrollment Design 20260831.md` (MiTY platform repository).

## Architecture

```
Home Assistant
      │
      ▼
MiTY Research integration   (custom_components/mity)
  Config Flow · Options Flow · DataUpdateCoordinator
  Sensor / Binary Sensor / Switch / Button entities
  Events · Services · Diagnostics
      │
      ▼
HERD_IOT client              (custom_components/mity/api.py)
  enroll · policy · submitHerdEntities (/api/v1/herd/direct) · pause · remove · rejoin
      │
      ▼
MiTY citizen-science API
```

The HERD_IOT client (`api.py`) has no dependency on Home Assistant at all — it's a plain `aiohttp`-based wrapper around the MiTY HTTP contract, kept deliberately isolated so it could be extracted into its own PyPI package later without touching the rest of the integration, per Home Assistant's own guidance to keep external-service communication in a separate library.

## Development

```bash
pip install -r requirements_test.txt
ruff check custom_components tests
pytest
```

`tests/test_api.py` and `tests/test_coordinator_helpers.py` exercise pure logic (the HTTP client, value coercion) with no Home Assistant dependency. The rest of `tests/` needs a real Home Assistant test environment (via `pytest-homeassistant-custom-component`, installed by `requirements_test.txt`) — the recommended way to get one is the [Home Assistant integration dev container](https://developers.home-assistant.io/docs/development_environment/).

To try the integration against a real local Home Assistant instance rather than just running the test suite, see [docs/LOCAL_TESTING.md](docs/LOCAL_TESTING.md).

## Roadmap

- [x] **Milestone 1** — Config flow, enrollment, MiTY device with connection status
- [x] **Milestone 2** — Sensor discovery + parameter selection
- [x] **Milestone 3** — Scheduled data submission
- [x] **Milestone 4** — Pass/fail events + automations, pause/leave/rejoin
- [ ] **Milestone 5** — Insights + home health score polling — [API confirmed](docs/DESIGN_NOTES.md), backend implementation pending, HA side not yet built
- [x] **Milestone 6** — Joinable research studies — join/leave already works via one config entry per study; a public "browse studies" discovery API is [proposed, not yet confirmed](docs/DESIGN_NOTES.md)
- [x] **Milestone 7** — HACS release polish — reauth flow, release automation, [quality-scale self-assessment](docs/QUALITY_SCALE.md); default-store submission itself needs a few remaining human/GitHub actions, tracked in [docs/HACS_RELEASE_CHECKLIST.md](docs/HACS_RELEASE_CHECKLIST.md) (repo topics, a cut release, and — the one still genuinely open — brand/logo assets, since MiTY doesn't have one yet)

## Contributing

Issues and pull requests welcome. This integration is designed to eventually support **research-specific forks**: a researcher running a bespoke study can fork this repository and customise the fixed parameter set, config flow copy, and branding for their own trial while keeping the same HERD_IOT/MiTY plumbing underneath.

## License

[Apache License 2.0](LICENSE).
