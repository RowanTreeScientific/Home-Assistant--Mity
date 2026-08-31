# Changelog

## 0.3.3 — Fix real config flow bug + a test relying on real sockets

Found via the CI log after 0.3.2 fixed collection and CI could finally run to completion:

- **Real bug**: `config_flow.py`'s parameter-mapping schema set `default=None` on every unmapped channel, and `EntitySelector` validates whatever value is present — including a voluptuous-inserted default. `None` isn't a valid entity ID, so submitting the parameters step with *anything* left blank failed schema validation (`InvalidData: Schema validation failed @ data['entity_motion']`) rather than just skipping that channel. Reproduced directly with a standalone voluptuous check before fixing, and confirmed the fix preserves real prefilled defaults in the options flow. This would have broken the config flow for every real user leaving any channel unmapped, not just in tests — worth flagging as the more important fix in this release despite being caught by CI rather than manual testing.
- `tests/test_api.py::test_connection_error` opened a real socket to `127.0.0.1:1` to provoke a connection failure. `pytest-homeassistant-custom-component` globally blocks real sockets for the whole test session (by design, to keep HA's test suite from ever touching the network) — this affected the whole run, not just HA-dependent tests. Replaced with a mocked `ClientConnectionError` at the request layer: faster, deterministic, and no longer dependent on what's listening on localhost in a given environment.

## 0.3.2 — Fix pytest CI collection error

`tests/test_coordinator_helpers.py` loaded `coordinator.py` by file path (to avoid needing Home Assistant installed for a pure-logic test), but `coordinator.py` has `from .api import (...)`, a relative import that only resolves inside a real package. Loading it standalone made that import fail — invisible in local testing because Home Assistant wasn't installed there either, so the function bailed out earlier for an unrelated, already-handled reason, masking the real bug. In actual CI (`pytest (3.12)` job), Home Assistant *is* installed, so it got far enough to hit the broken relative import and errored the whole collection, failing every test in the run. Found via the real CI log (`gh run view --log-failed`, since GitHub gates log text behind an authenticated session that no automated tool here could reach). Fixed by importing `custom_components.mity.coordinator` normally instead — the same dotted-import approach `test_config_flow.py`/`test_init.py` already use successfully.

## 0.3.1 — CI fixes

Found by actually checking the Actions tab once the repo went public (previously unverifiable — no `gh`/API access from this environment against a private repo):

- `validate.yml`/`test.yml` were watching `branches: [main]`; this repo's default branch is `master`, so neither had ever run since the project's first commit. Fixed.
- `manifest.json` keys weren't in hassfest's required `domain, name, then alphabetical` order. Fixed.
- `hacs.json` had an `iot_class` key that isn't part of its schema. Fixed (removed; `manifest.json` already carries it correctly).
- `LICENSE` was a paraphrased Apache-2.0, not verbatim — GitHub's license detector returned `NOASSERTION`. Replaced with the verbatim official text.
- `test.yml`'s `--cov` flags need the `pytest-cov` plugin, missing from `requirements_test.txt` — every pytest run failed immediately on argument parsing before any test executed. Fixed.
- The `hacs` job's brand-assets check is expected to keep failing until real MiTY brand assets exist (tracked in [docs/HACS_RELEASE_CHECKLIST.md](docs/HACS_RELEASE_CHECKLIST.md)) — not a regression.

## 0.3.0 — Milestone 7: HACS release polish

- **Reauthentication flow**: a device key rejected by MiTY (`MityAuthError`) now triggers Home Assistant's standard reauth prompt instead of just failing silently forever. Tries the stored rejoin token first; falls back to asking for a fresh enrollment code if the trial's policy requires a new identity after leaving.
- Added `.github/workflows/release.yml` — pushing a `v*.*.*` tag now auto-creates a real GitHub Release with generated notes, which is what HACS's default store actually reads (not bare tags).
- Added `.github/CODEOWNERS`, matching `manifest.json`.
- Added [docs/QUALITY_SCALE.md](docs/QUALITY_SCALE.md) — an honest self-assessment against HA's published Integration Quality Scale tiers (Bronze met, Silver mostly met, Gold/Platinum not yet attempted).
- Added [docs/HACS_RELEASE_CHECKLIST.md](docs/HACS_RELEASE_CHECKLIST.md) — everything still needed for default-store submission that requires a human/GitHub-web action (repo topics, brand assets, the `hacs/default` PR itself) rather than code.
- Added [docs/LOCAL_TESTING.md](docs/LOCAL_TESTING.md) — how to install and exercise this integration on a real local Home Assistant instance.

## 0.2.0 — Milestone 6: research studies

- **Join multiple studies**: since a MiTY trial and a "study" are 1:1 in the confirmed backend contract, joining a second study is just running setup again with that study's own enrollment code — each becomes its own MiTY device/config entry. No new API was needed for this.
- Added an optional **study nickname** field (setup and options flow) so multiple joined studies stay distinguishable in the Home Assistant UI — the enrollment response carries no study name to use automatically.
- Deleting a MiTY integration entry now **best-effort withdraws from that study** (`remove_only`, keeping already-submitted data) instead of silently leaving an orphaned active device on the MiTY platform.
- Drafted (not yet built — awaiting backend confirmation) a proposed public **study discovery** API so participants can browse open studies before already having a code — see `docs/DESIGN_NOTES.md`.

## 0.1.0 — Milestones 1–4

- Config flow enrollment via MiTY citizen-science auto-enroll codes.
- HERD_IOT API client (`api.py`), scheduled data submission via `DataUpdateCoordinator`.
- Sensor / binary_sensor / switch / button entities, pass/fail events.
- Pause / leave / rejoin lifecycle services.
- Diagnostics with credential redaction.
