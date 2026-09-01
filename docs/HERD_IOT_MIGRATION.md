# HERD-IoT v1.0 migration: what's confirmed, what's placeholder

The MiTY backend is being rebuilt against the **HERD-IoT Implementation Guide v1.0** (Rowan Tree Scientific, part of the Glass Door Vault PhD portfolio) — a much richer, NGSI-LD-based data envelope than the flat JSON this integration previously sent. This document tracks exactly what changed, and — more importantly — what's a genuine best-guess pending confirmation from whoever owns the rebuilt backend, so nobody mistakes a placeholder for a settled decision later.

**This supersedes the data-format parts of `Citizen Science AutoEnrollment Design 20260831.md`** (the flat `/v1/ingest` body). That document's enrollment/withdrawal/rejoin/pause lifecycle (`/v1/citizen-science/*`) is assumed unchanged — the Implementation Guide doesn't mention citizen-science enrollment at all, only the data envelope and ingestion pathways, so nothing about how a device gets its `deviceApiKey` should be affected. That assumption itself is unconfirmed and worth flagging to the backend team explicitly.

## What's now built

- `custom_components/mity/uuid7.py` — RFC 9562 UUID v7 generator (stdlib only gained `uuid.uuid7()` in Python 3.14, newer than HA's minimum).
- `api.py`'s `submit_herd_entities()` — `POST /api/v1/herd/direct` (Implementation Guide 5.2.1), sending entities as a JSON array (works for both single and batch per the guide's own wording).
- `coordinator.py`'s `_build_herd_entities()` — constructs one `HERDObservation` entity per mapped channel with a current value: Layer 1 (Observation Core) always, Layer 2 (Device Provenance) when the participant filled in at least manufacturer+model.
- `config_flow.py` — two new steps: **zones** (required — the identifier needs one) and **device_provenance** (optional, shared across all mapped channels in this first pass).

## Fixed per-channel mapping to the controlled vocabularies

| HA channel | domain | measure | unitCode |
|---|---|---|---|
| `entity_temperature` | `env` | `temperature` | `DEG_C` |
| `entity_humidity` | `env` | `humidity` | `PERCENT` |
| `entity_motion` | `structural` | `occupancy` | `DIMENSIONLESS` |
| `entity_energy_usage` | `energy` | `kwh-import` | `KiloW-HR` |

Note: the guide's own Figure 4.1 worked example uses `unitCode: "CEL"` for temperature, while Table 3.3 (the vocabulary table) says `DEG_C`. This is an apparent inconsistency in the source document — `const.py`'s `HERD_CHANNEL_ENVELOPE` picked the vocabulary table as authoritative. Worth confirming with whoever owns the spec.

## Real placeholders — confirmed as best-guesses, not settled

These were built anyway per explicit instruction to move fast and accept rework risk, but every one of them needs a real answer before this can be considered done:

1. **`propertyToken`** (`coordinator.py::_property_token()`) — the identifier scheme requires a GDV-issued token, but GDV tokens are supposed to be a one-way mapping only the vault can produce (Appendix B: "cryptographically one-way... must not be possible to derive the original property address... without access to the mapping table"). A client self-generating a `GDV-`-prefixed value from its own `instance_id` (`GDV-{instance_id:08x}`) defeats that guarantee structurally — it's not a real pseudonymisation token, just a value in the right shape. **This needs to come from the backend**, most plausibly as part of the (also rebuilt?) enrollment response.
2. **`programme` / `provider`** (`HERD_PROGRAMME_ID` = `"MiTy-TRE"`, `HERD_PROVIDER` = `"citizen-science"` in `const.py`) — these two identifier components are designed around a registered research programme and a housing-provider organisation collecting on a resident's behalf. Neither concept exists cleanly in the self-enrolled citizen-science model. Fixed placeholders for now.
3. **`device-id` registration** (`coordinator.py::_sanitize_device_id()`) — section 3.3 says "the device-id must be registered in the Device Profile Table before data submission. Observations from unregistered devices will be rejected." This integration derives a device-id from the HA entity_id (`sensor.living_room_temperature` → `sensor-living-room-temperature`) and has no way to pre-register it anywhere. **Real risk**: submissions may be rejected outright until the backend either auto-registers on first submission for citizen-science devices, or provides some other mechanism.
4. **Layer 3 (Spatial and Property Context)** — not sent at all. `propertyToken`/`zone` alone don't cover it; `propertyArchetype`, `tenureType`, `epcRatingBand`, `constructionEra`, retrofit history are property-survey data a citizen-science HA install has no way to know without a dedicated onboarding questionnaire, which wasn't part of this build. Sending fabricated values for these would be actively worse than omitting the layer.
5. **Layer 4 (Research Governance)** — not sent at all, and structurally shouldn't be client-supplied: `ethicalApprovalRef`, `consentModel`, `consentVersion`, `dataSensitivityTier`, `fiveSafesRef` are trial-level governance facts set by the researcher running the study, not something a participant's Home Assistant install can know or should be trusted to self-report.
6. **Auth header scheme for `/api/v1/herd/direct`** — the guide says "API key issued to the managing organisation and, where the device supports it, a client TLS certificate." Neither the exact header format nor whether the existing `deviceApiKey`/`Authorization: Bearer` scheme from citizen-science enrollment is meant to work here is specified. This integration reuses that existing scheme (`_auth_headers()` in `api.py`) as the most consistent inference, unconfirmed.

## What this means practically

Given items 1–6 above, **submissions to `/api/v1/herd/direct` may well be rejected by the real backend** until at least the propertyToken and device-id registration questions are answered — the client-side construction is spec-shaped, not necessarily backend-accepted yet. `sensor.mity_status` will show `rejected` with per-observation error detail (via `HerdObservationResult.errors`) if that happens; that's expected, not a bug, until the open items above are resolved.

## Open questions for whoever owns the rebuilt backend

1. Does the citizen-science enrollment response (`POST /v1/citizen-science/enroll`) still return just `{instanceId, deviceApiKey, rejoinToken}`, or will it be extended to include a `propertyToken`/`programme`/`provider` the client should actually use?
2. Will citizen-science devices auto-register in the Device Profile Table on first submission, or is there a separate registration step this integration needs to call?
3. Confirm the auth scheme for `/api/v1/herd/direct` — same `deviceApiKey` bearer token as everything else, or something new?
4. Confirm `unitCode` for temperature: `DEG_C` (Table 3.3) or `CEL` (Figure 4.1)?
5. Is the flat `/v1/ingest` endpoint still live during migration, as a fallback? (Kept in `api.py` as `submit()`, marked superseded, not currently called from `coordinator.py`.)
