# Changelog

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
