# Changelog

## 0.3.13 — Consistent icon set, still placeholder-quality

`icon@2x.png` was swapped for a full "MiTY TRE" text-lockup design (by choice, not the original icon-only mark). Regenerated `icon.png` from the same source scaled down, so the 1x/2x icon pair shows the same design consistently rather than two different logos at two different sizes. Still soft/low-resolution throughout — see `assets/brand/README.md`.

## 0.3.12 — Placeholder brand assets

A real MiTY logo (`docs/Mity logo.png`, `docs/Mity logo with text.png`) was added to the project. Generated placeholder `icon.png`/`icon@2x.png`/`logo.png`/`logo@2x.png` at [assets/brand/](assets/brand/), at the exact sizes `home-assistant/brands` requires — upscaled from the low-resolution sources (79×71px original), so soft rather than crisp; explicitly documented as not submission-quality in `assets/brand/README.md`, not silently presented as finished. Excluded two unrelated MiTY-website marketing images (hero banners, ~4MB combined) that landed in the same `docs/` drop from version control via `.gitignore` — they aren't this integration's brand assets.

## 0.3.11 — CI fully green; bump actions off deprecated Node 20

**CI confirmed fully green end-to-end** for the first time: `hassfest` and both `pytest (3.12)`/`pytest (3.13)` all pass (`Tests` workflow conclusion: success). `Validate`'s `hacs` job remains red only on the known, tracked brand-assets gap.

Bumped `actions/checkout@v4` → `@v7` and `actions/setup-python@v5` → `@v7` across all three workflows (`test.yml`, `validate.yml`, `release.yml`), clearing a "Node.js 20 is deprecated" warning — confirmed both new major versions declare `using: node24` in their own `action.yml` before bumping, not just picked the latest tag blindly.

## 0.3.10 — Exact-pin pycares instead of a range

0.3.9's `pycares<4.9.0` range pin let `pytest (3.13)`'s "Install dependencies" step fail outright, taking `pytest (3.12)` down with it via matrix fail-fast before it even ran. Reproduced locally: a loose range gives pip's resolver room to wander backward through every version with no prebuilt wheel for the running Python (interacting with `pytest-homeassistant-custom-component`'s own transitive constraints), landing on `pycares==4.1.1` -- whose sdist is genuinely broken (`FileNotFoundError: PYPIREADME.rst`, a packaging bug in that release, unrelated to anything in this project).

Fixed by pinning the exact version instead of a range: `pycares==4.8.0`, confirmed via PyPI's own file listing to have real prebuilt manylinux wheels for both `cp312` and `cp313` on `x86_64` (what GitHub's `ubuntu-latest` runners need) -- an exact pin gives the resolver no room to wander into anything else.

## 0.3.9 — The actual fix: pin pycares, don't remove or block it

0.3.8's "uninstall aiodns/pycares" fix stopped the lingering-thread symptom, but broke 9 real tests with `RuntimeError: Resolver requires aiodns library` — the actual CI traceback (pasted directly) pinpointed why: `homeassistant/helpers/aiohttp_client.py` constructs `resolver=AsyncResolver()` directly, with **no fallback to `ThreadedResolver`**. `async_get_clientsession(hass)` -- which this integration's own `config_flow.py`/`__init__.py` call, matching real production behaviour -- hard-requires aiodns to be genuinely present and working. Both this attempt and 0.3.7's `sys.modules` block were fighting a dependency that has to stay functional; there was never a way to block or remove it without breaking real code paths this test suite legitimately needs to exercise.

Reverted both. The actual fix: pin `pycares<4.9.0` in `requirements_test.txt` -- 4.9.0 (released 2025-06-12) is the version that introduced the shutdown-logic regression (matches the timeline in [pytest-homeassistant-custom-component#219](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component/issues/219), opened 2025-07-07 referencing a change "last month"). This keeps `aiodns`/`AsyncResolver` fully installed and selected, satisfying HA's hard requirement, while avoiding the specific buggy version. Verified directly: confirmed the pin resolves to 4.8.0, and confirmed `aiohttp.resolver.DefaultResolver` is still correctly `AsyncResolver` with it installed.

## 0.3.8 — Fix the lingering thread by removing the package, not racing its import

0.3.7's `sys.modules["aiodns"] = None` conftest.py block was directly verified to work in isolation (confirmed `aiohttp.resolver.DefaultResolver` really does flip from the pycares-backed `AsyncResolver` back to `ThreadedResolver`) -- but CI failed again anyway, at the exact same place. The reason: `pytest-aiohttp` and `pytest-homeassistant-custom-component` load as entry-point plugins during pytest's own startup, *before* any conftest.py -- even the rootdir one -- is collected. By the time `tests/conftest.py` runs, `aiohttp.resolver`'s module-level resolver selection can already be cached. No conftest.py-level fix can reliably win that race.

Fixed by not racing it at all: `.github/workflows/test.yml` now uninstalls `aiodns`/`pycares` immediately after `pip install -r requirements_test.txt`, so they simply aren't present in the environment for anything to import, at any point, regardless of load order. The conftest.py block stays as a documented best-effort fallback for local runs that don't follow that workflow step, with its comment corrected to no longer claim it's sufficient on its own.

## 0.3.7 — Fix the lingering thread at its actual scope: the whole test session

0.3.6's fix (forcing `ThreadedResolver` on `test_api.py`'s own session) worked exactly as intended — `test_api.py` now passes with zero errors — but the identical failure immediately reappeared one file later, in `test_config_flow.py::test_full_flow_creates_entry`, the first test that exercises the real `async_setup_entry` path through Home Assistant's own `async_get_clientsession(hass)`. Confirmed via the pasted CI log this was the same mechanism, not a new bug: aiohttp's pycares-vs-plain resolver selection happens once, at `aiohttp.resolver` module import time, and is cached for the rest of the process — whichever `ClientSession` gets constructed *first* anywhere in the whole test session (mine or Home Assistant's own internals) triggers it. Patching individual fixtures was always going to be whack-a-mole against that.

Fixed at the actual scope of the problem instead: `tests/conftest.py` now sets `sys.modules["aiodns"] = None` before anything else in the session runs, which is the documented CPython mechanism for forcing a future `import aiodns` to raise `ImportError` — exactly the branch `aiohttp.resolver`'s own `try/except ImportError` already falls back cleanly from. One line, at the one place that actually needs it. Verified directly, not assumed: installed `aiodns`/`pycares` locally, confirmed `aiohttp.resolver.DefaultResolver` really does become the pycares-backed `AsyncResolver` without the block, and confirmed the block reliably forces it back to `ThreadedResolver`.

## 0.3.6 — Actually fix the lingering thread (root cause, not symptom)

0.3.5's rewrite eliminated all real HTTP traffic, but the exact same `_run_safe_shutdown_loop` teardown failure recurred anyway, at the exact same test (`test_enroll_success`, the first async test in the whole session) — direct evidence the earlier "real network traffic" hypothesis was wrong. Checked whether this was a known upstream issue rather than guessing further: it is — [pytest-homeassistant-custom-component#219](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component/issues/219), open, no released fix. `pycares` (aiohttp's optional C-ares DNS resolver, pulled in transitively) changed its shutdown logic and now leaves this exact thread behind, unrelated to whether any request was ever made — merely being aiohttp's *auto-selected* resolver is enough, and resolver selection happens at `ClientSession`/`TCPConnector` construction, before any traffic occurs.

Fixed by explicitly constructing the test session's `TCPConnector` with aiohttp's plain `ThreadedResolver`, bypassing the auto-detection that would otherwise prefer the pycares-backed one whenever it happens to be installed. Deterministic regardless of environment; doesn't require waiting on the upstream fix.

## 0.3.5 — Rewrite test_api.py to eliminate real socket usage entirely

The 0.3.4 `enable_socket` marker fixed the immediate `SocketBlockedError`s but only papered over a deeper problem: allowing real (even loopback) network I/O let `test_enroll_success` trigger Python 3.12's asyncio default-executor watchdog thread on real request completion, which HA's own strict thread-leak-detecting test fixture then failed on (found from the actual CI log, pasted directly — `AssertionError` in `pytest_homeassistant_custom_component.plugins.verify_cleanup`, a `Thread-1 (_run_safe_shutdown_loop)` left behind). Real bug in the test's design, not in `coordinator.py`/`api.py`.

Tried `aioresponses` (mock at the HTTP layer, no real server) as the fix — but it has a live compatibility gap with recent aiohttp (`ClientResponse.__init__() missing... 'stream_writer'`, reproduced locally with the latest PyPI release of each) and, in some setup path, *still* touched a real socket under `--disable-socket`. Not worth the added dependency risk.

Settled on a small stdlib-only fake replacing `ClientSession.request` directly — no real server, no third-party mocking library, no HTTP traffic of any kind, so the executor-thread trigger can't recur. `enable_socket` is still needed for one narrow, well-understood reason: constructing a real `ClientSession()` at all makes `TCPConnector.__init__` do a one-shot, synchronous IPv6-capability probe via `socket.socket()`, unrelated to any connection attempt. Verified directly (not just asserted) that this doesn't leak a thread: ran the same session-construct-then-mocked-request pattern outside pytest entirely and diffed `threading.enumerate()` before/after — no leaked threads.

## 0.3.4 — Fix remaining socket-blocked tests

The 0.3.3 socket fix only covered `test_connection_error`; 9 other tests in `tests/test_api.py` use a *different* real-socket mechanism — the `client` fixture spins up a real `aiohttp.test_utils.TestServer` to exercise `MityApiClient` end-to-end over actual HTTP, and binding that loopback server also trips `pytest-homeassistant-custom-component`'s global `pytest-socket` guard. Found from the actual CI failure log (pasted directly this time, all 9 `SocketBlockedError`s). Fixed with `pytest-socket`'s own purpose-built escape hatch — `pytestmark = pytest.mark.enable_socket` at module level — rather than rewriting the tests to avoid a real server. Verified directly: installed `pytest-socket` locally and ran the suite with `--disable-socket` (the same mechanism the HA plugin uses), confirming the marker genuinely re-enables the loopback server rather than being silently ignored.

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
