# Changelog

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
