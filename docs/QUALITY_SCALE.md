# Integration Quality Scale — self-assessment

Home Assistant's [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) is a Core-only, machine-checked mechanism (a `quality_scale.yaml` hassfest validates) — it doesn't apply to a HACS custom-repository integration like this one. This document is a prose self-assessment against the same published tiers, done for two reasons: it's the honest way to show where this integration stands if it's ever proposed for HA Core, and it's a more useful "is this integration solid" checklist for reviewers/contributors than no assessment at all.

**Aiming for: Bronze now, Silver as a near-term target.** Not claiming Gold/Platinum — several of those rules depend on things outside this integration's control (see "Not yet met" below).

## Bronze — met

- **Config flow for all setup** — no YAML configuration; enrollment, parameter mapping, and frequency are all set via `config_flow.py`. ([config_flow.py](../custom_components/mity/config_flow.py))
- **Options flow for anything editable after setup** — parameter mapping, frequency, and study nickname are all editable via `MityOptionsFlow` without re-enrolling.
- **Connection/auth errors surfaced in the UI, not just logs** — `invalid_enroll_code`, `cannot_connect`, `must_agree_terms` are all shown as form errors in the config flow, not silent failures.
- **`ConfigEntryNotReady` on startup connection failure** — `async_setup_entry` raises it if the MiTY endpoint can't be reached, so Home Assistant retries setup automatically instead of marking the entry permanently failed.
- **Unique IDs on every entity and the config entry itself** — the config entry's unique ID is the MiTY-assigned `instance_id`; every entity's unique ID is derived from it, preventing duplicate entries for the same device and keeping entity IDs stable across restarts.
- **`has_entity_name = True`** — every entity uses the modern naming convention (device name + entity name), not a manually-composed friendly name.
- **Dependency isolation** — the HERD_IOT/MiTY client (`api.py`) has zero Home Assistant imports, matching the Bronze "external communication isolated" expectation and the platform team's own stated preference for a separable client library.
- **Diagnostics with credential redaction** — `diagnostics.py` exists and redacts `device_api_key`/`rejoin_token`.
- **Basic test coverage** — `tests/test_api.py`, `tests/test_config_flow.py`, `tests/test_init.py`, `tests/test_coordinator_helpers.py` cover the HTTP client, the full enrollment flow (including error paths and multi-entry/duplicate handling), and the removal lifecycle hook.
- **README covers installation, configuration, and removal** — see the main [README.md](../README.md).

## Silver — mostly met, one open item

- **`DataUpdateCoordinator` used correctly** — `coordinator.py` owns all polling/submission state; entities are simple `CoordinatorEntity` consumers, no entity does its own I/O.
- **Options flow re-applies changes without a restart** — `_async_update_listener` re-reads the scan interval immediately when options change.
- **Graceful degradation on repeated failures** — a failed submission sets `binary_sensor.mity_submission_healthy` on and fires `mity_data_error`, rather than raising into the coordinator update loop uncontrolled.
- **Entities removed/disabled appropriately** — n/a currently (no per-entity dynamic add/remove scenario yet; every entity is always relevant once enrolled).
- **Reauthentication flow** — a `MityAuthError` from a submission (device key revoked/reset on the MiTY side) triggers `entry.async_start_reauth()`, surfacing a "needs attention" prompt in Home Assistant rather than just a silently-failing sensor. The reauth flow tries the stored rejoin token first (`async_step_reauth_confirm`), and falls back to asking for a fresh enrollment code (`async_step_reauth_new_code`) only if the trial's policy requires a new identity after leaving.

## Gold/Platinum — not yet met, and partly out of this integration's control

- **Full device/entity availability semantics, dynamic discovery, icon translations, etc.** — not yet built; lower priority than closing the Silver reauth gap above.
- **Brand assets in `home-assistant/brands`** — see [HACS_RELEASE_CHECKLIST.md](HACS_RELEASE_CHECKLIST.md). Needs an actual logo/icon design decision before it can be submitted; this integration currently renders with Home Assistant's generic integration icon.
- **Listed in HA Core / the HACS default store** — this is a distribution/acceptance status, not a code property; see the checklist for what's still needed before that's even eligible to pursue.

## How to keep this honest

If you add a feature or fix a bug that changes where this integration sits against a rule above, update this file in the same PR — a stale self-assessment is worse than none, since it actively misleads a reviewer deciding whether to propose Core inclusion.
