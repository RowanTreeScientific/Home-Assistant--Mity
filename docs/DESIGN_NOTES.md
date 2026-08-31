# Design notes: what's confirmed vs. proposed

This integration is built against a specific, confirmed MiTY backend contract for enrollment and withdrawal. Two further pieces of the roadmap needed their own design pass before any code could be written against them, since no backend contract existed yet:

## Confirmed and built

- **Enrollment, withdrawal, rejoin, pause** (`POST /v1/citizen-science/enroll`, `GET .../policy`, `POST .../remove`, `POST .../rejoin`, `POST .../pause`) and data submission (`POST /v1/ingest`) — the contract this integration is built against for Milestones 1–4.
- **Home Health Score / Home Insights / Research Insights polling** — proposed by this project, reviewed, and **signed off for backend implementation**. Not yet built on the Home Assistant side pending the corresponding MiTY API shipping.

## Proposed, not yet confirmed

- **Public study discovery** (`GET /v1/citizen-science/studies`) — a directory letting a participant browse open studies before they already have an enrollment code. Proposed, not yet reviewed by the MiTY platform team. Nothing in the Home Assistant integration depends on this landing: joining and leaving studies already works today via the confirmed enrollment/withdrawal contract, since a MiTY trial and a "study" are 1:1 — see [README.md's "Contributing to more than one study"](../README.md#contributing-to-more-than-one-study).

## Why this matters for contributors

If you're picking up unbuilt roadmap items, check whether a backend contract for them actually exists and is confirmed before writing client code against an assumed shape — two of the six milestones in this project's roadmap turned out to have only a plain-English requirement and a non-authoritative brainstorm mockup behind them, not an implemented API. Building against an unconfirmed shape risks a rewrite the moment the real contract lands with different field names or semantics.
