# Forking for a specific research project

This integration is deliberately structured so a researcher can fork it and produce a custom variant for their own study, without having to rebuild the Home Assistant plumbing (config flow, coordinator, entities, events) from scratch.

This is a design intention for the project, not yet a supported, tooled workflow — there is no fork generator or template repository today. The notes below describe what a fork should touch and, just as importantly, what it should leave alone.

## What's safe to change per-fork

| File | What to customise |
|---|---|
| `custom_components/<your_domain>/const.py` | `DOMAIN`, `DATA_CHANNELS` / `CHANNEL_FIELD_NAMES` (if your study's HERD_IOT schema differs from the generic citizen-science one), default/min/max frequency, `TERMS_URL` |
| `custom_components/<your_domain>/manifest.json` | `domain`, `name`, `documentation`, `issue_tracker`, `codeowners` |
| `custom_components/<your_domain>/strings.json` + `translations/en.json` | All user-facing copy — study name, description text, terms wording |
| `hacs.json` / `info.md` / `README.md` | Branding, study-specific setup instructions |

Renaming the domain (`mity` → something study-specific) is expected for a fork that will be installed *alongside* the original in the same Home Assistant instance — two integrations can't share a domain.

## What should stay untouched

- `custom_components/<your_domain>/api.py` — the HERD_IOT/MiTY HTTP contract (`/v1/citizen-science/*`, `/v1/ingest`) is shared platform infrastructure. If your study genuinely needs different endpoints or auth, that's a MiTY platform-side conversation first, not something to patch locally — divergence here is exactly what makes forks hard to maintain.
- `coordinator.py`'s submission/error/event handling — the pass/fail event contract (`mity_data_accepted` / `mity_data_rejected` / `mity_data_error`) is what any automations or blueprints built against this integration rely on. Keep it stable even if you rename the domain.
- The pause/leave/rejoin lifecycle in `__init__.py` and `switch.py` — this is the participant-rights machinery (Section 5 of the citizen-science API design). A fork that drops or weakens this is dropping real withdrawal/deletion guarantees for participants, not just a code simplification.

## If your study's data schema differs from the generic one

The generic `HERD_IOT:citizen.home-assistant` schema (temperature/humidity/motion/energyUsage) is a starting point, not a ceiling. A study needing different fields should:

1. Get its own dedicated HERD_IOT family/field-map set up on the MiTY platform side (see "Citizen Science AutoEnrollment Design" Section 6 — this is an admin-side `HerdAdminController` operation, not something the Home Assistant app controls).
2. Update `DATA_CHANNELS` / `CHANNEL_FIELD_NAMES` / `CHANNEL_DOMAIN_FILTER` in `const.py` and `config_flow.py` to match.
3. Update the corresponding entries in `strings.json` and `translations/en.json`.

Keep the raw JSON field names sent by the app and the platform's saved field-map in lockstep — a mismatch here silently drops data rather than erroring loudly, since the platform simply won't recognise an unmapped field.

## Staying up to date with upstream

Since core plumbing (`api.py`, `coordinator.py`, the lifecycle services) is meant to stay shared, a fork should periodically rebase or merge from this repository rather than diverging permanently. If a fork finds itself needing to change one of the "should stay untouched" files above, that's usually a sign the change belongs upstream instead — please open an issue or PR here first.
