# HERD-IoT: what actually happened

**Correction (2026-09-01): the premise of the original version of this document was wrong.** It claimed "the MiTY backend is being rebuilt against the HERD-IoT Implementation Guide v1.0" and went on to build a full NGSI-LD/JSON-LD envelope, a `urn:herd-iot:...` identifier scheme, and a new `/api/v1/herd/direct` endpoint against that premise. **None of that was ever real.** The Implementation Guide (in the PhD portfolio's Supporting Documentation) is the *formal*, aspirational HERD-IoT specification — a genuine, complete standard, but not the one this integration talks to. MiTY's actual, live backend implements a deliberately simpler practical subset that was already correctly built in Milestones 1–4 and never changed underneath this integration: a flat JSON body over `POST /v1/ingest`.

Kept this file (rewritten) rather than deleting it outright, since the mistake and how it was found are worth a record for anyone who reads this integration's history later.

## What actually shipped after the correction

Confirmed against `MiTy - Home Assistant - API specification.md` (the authoritative source — read that file directly before changing anything here again) and the answers received to the six placeholder questions the wrong version of this document raised:

- **Endpoint**: `POST /v1/ingest`, unchanged since Milestone 3. `/api/v1/herd/direct` doesn't exist and was removed from `api.py`.
- **Auth**: `Authorization: Bearer <deviceApiKey>` — the same scheme already built, just pointed at the right endpoint.
- **No identifier scheme**: no `id`/URN field, no `propertyToken`, no `programmeId`/`provider`. Pseudonymisation happens entirely server-side on the plain `deviceId` string the app sends — the app never generates, sees, or needs a token. `uuid7.py`, the `HERD_CHANNEL_ENVELOPE` domain/measure/unitCode vocabulary table, and all URN construction were removed.
- **`deviceId` is real, but simple**: an optional plain string field inside `data`, one per ingest call (not one per URN component). This integration derives it from the participant's study nickname.
- **Provenance/zone (`_meta`)**: real, but far simpler than the formal spec's Layer 2/3 — a single optional `_meta` object inline in the ingest body:
  ```json
  {
    "InstanceID": 21,
    "data": {
      "deviceId": "outdoor-weather-01",
      "timestamp": "2026-09-01T11:56:08.455Z",
      "temperature": 21.4,
      "_meta": {
        "deviceProvenance": {
          "manufacturer": "Ecowitt",
          "model": "WS90",
          "samplingInterval": 60,
          "communicationProtocol": "wifi"
        },
        "zone": "living-room"
      }
    }
  }
  ```
  `deviceProvenance` and `zone` are **free text — no fixed vocabulary enforced**, unlike the formal spec's controlled vocabularies. One value per submission (a single ingest call already bundles every mapped channel's reading), not per individual sensor field. `_meta` also persists server-side as a standing device profile once sent, so it doesn't need resending on every call — this integration currently does resend it every time anyway, for simplicity; see "Not yet done" below.
- **No Layer 3/4 equivalent**: `propertyArchetype`/`tenureType`/`epcRatingBand`/etc. and `ethicalApprovalRef`/`consentModel`/etc. don't exist as concepts in this backend at all. Nothing to send, nothing lost by not sending it.
- **Config flow**: collapsed the old (wrong) per-channel `zones` step and separate `device_provenance` step into one combined, fully optional `device_details` step (zone + manufacturer + model + communication protocol), matching the real `_meta` shape's one-value-per-submission model. Fields use a dropdown-with-custom-entry selector (suggested common values, never enforced) rather than the formal spec's fixed vocabulary.

## What this integration does NOT yet use

- **`_meta.fields[<fieldKey>].{description, unit}`** — per-field free-text descriptions/units (e.g. documenting that a "solarIrradiance" reading is from a pyranometer, not a PV inverter). Real, live, not built — would need one more optional per-channel UI addition.
- **`POST /v1/citizen-science/device-profile`** (set once explicitly) / **`GET .../device-profile`** (read back) — the alternative to sending `_meta` inline on every call. Currently this integration just resends `_meta` on every submission instead, which works today but is slightly wasteful; worth switching to the explicit set-once form later.
- **The newer recognised HERD_IOT terms** beyond the original four this integration maps (`temperature`, `humidity`, `motion`, `energyUsage`): `solarIrradiance`, `windSpeed`, `rainfall`, `riverLevel`, `uvIndex` are all live, recognised fields on the real backend. Adding config-flow support for them is a reasonable follow-up, not done in this pass.

## Lesson for next time

The formal Implementation Guide reads as authoritative and doesn't flag itself as aspirational/parallel-track anywhere in its own text — nothing in the document itself distinguishes "this is the standard we're building towards" from "this is what the live system does today." When a document like that shows up, confirm which category it's in *before* writing client code against it, rather than after.
