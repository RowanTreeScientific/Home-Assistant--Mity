# Path to the HACS default store

This integration already works as a **HACS custom repository** (README's Installation section). This checklist covers what's still needed to submit it to the **HACS default store** so users can find and install it without adding a custom repository URL first — see the [HACS publishing docs](https://www.hacs.xyz/docs/publish/start/) for the authoritative, up-to-date requirements.

Everything below needs a repo-owner action on GitHub itself (repo settings, a signed-in `gh`/browser session, or a decision only a human can make) — none of it can be done by an agent working from a local clone with plain `git`.

## 1. Repository settings

- [x] **Add GitHub topics**: `home-assistant`, `hacs-integration`, `hacs`, `mity`. Done via `gh repo edit --add-topic`; confirmed live.
- [x] **Add a repository description and homepage URL.** Confirmed live: description "Contribute Home Assistant sensor data to MiTY citizen-science research", homepage `www.mi-ty-tre.co.uk`.
- [x] **Repository is public.** Confirmed.

## 2. Cut a real release

`.github/workflows/release.yml` (already added) auto-creates a GitHub Release with generated notes whenever a `v*.*.*` tag is pushed — HACS reads actual Release objects, not bare git tags, so this step matters.

- [x] **v0.3.0 cut and confirmed live** on the repo's Releases page (2026-08-31). Repeat for every future version bump in `manifest.json`:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

## 3. Validate cleanly in CI

- [x] `validate.yml`/`test.yml` triggering at all — **found and fixed** (2026-08-31): both watched `branches: [main]` but this repo's default branch is `master`, so neither had ever run despite multiple pushes. Confirmed fixed — they now fire on push to `master`.
- [x] `hassfest` job — **found and fixed**: `manifest.json` keys weren't in the required `domain, name, then alphabetical` order.
- [x] `hacs` job, JSON schema — **found and fixed**: `hacs.json` had an `iot_class` key, which isn't part of its schema (that belongs in `manifest.json` only, where it already was).
- [x] `hacs` job, license detection — **found and fixed**: `LICENSE` was a paraphrased Apache-2.0 (close but not verbatim), which GitHub's license detector scored as `NOASSERTION`. Replaced with the verbatim official text.
- [x] `hacs` job, brand assets — **confirmed to be the only remaining `hacs` failure** (checked the actual check-run annotations): `<Validation brands> failed: The repository does not provide brand assets and is not listed in the Home Assistant brands repository.` Expected to keep failing until the brand-assets gap in Section 4 below is closed — not a bug, `hacs/action` is correctly flagging a real gap. Don't mistake continued red here for a regression.
- [x] `test.yml`, `pytest-cov` missing — **found and fixed**: `--cov=...`/`--cov-report=...` need the `pytest-cov` plugin, absent from `requirements_test.txt`. Added.
- [x] `test.yml`, pytest (3.12) collection error — **found and fixed** (this was the actual cause of the exit-code-2 failure, confirmed via the real CI log — the `pytest-cov` gap above was a real but separate issue): `tests/test_coordinator_helpers.py` loaded `coordinator.py` by raw file path to avoid needing Home Assistant installed, but `coordinator.py`'s `from .api import (...)` relative import can't resolve outside a real package, erroring collection for the whole run. Fixed by importing `custom_components.mity.coordinator` normally instead, like the other HA-dependent test files already do. See CHANGELOG.md 0.3.2.
- [x] `test.yml`, real config flow bug — **found and fixed** (0.3.3): the parameter-mapping schema's `default=None` on unmapped channels made `EntitySelector` validate `None` and reject it, breaking the config flow for any real user who left a channel unmapped, not just in tests. See CHANGELOG.md 0.3.3.
- [x] `test.yml`, socket-blocked test — **found and fixed** (0.3.3): `test_connection_error` opened a real socket, blocked by `pytest-homeassistant-custom-component`'s global socket guard. Replaced with a mock.
- [x] `test.yml`, remaining socket-blocked tests — **found and fixed** (0.3.4): 9 more tests in `test_api.py` use a real loopback `aiohttp.test_utils.TestServer`, also blocked by the same guard. Fixed with `pytest.mark.enable_socket`; verified locally with `pytest-socket --disable-socket` (the actual mechanism the HA plugin uses) that this genuinely re-enables the server rather than being silently ignored.
- [x] `test.yml`, executor-thread leak from real network I/O — **found and fixed** (0.3.5): the 0.3.4 fix let real HTTP traffic occur, which triggered a Python 3.12 asyncio watchdog thread that HA's own strict cleanup fixture failed on. Rewrote `test_api.py` to mock `ClientSession.request` directly (no real server, no third-party mocking library — `aioresponses` was tried and rejected for a live compatibility gap with recent aiohttp, reproduced locally) so no real traffic can occur at all. Verified directly (not just asserted) that no thread leaks with this pattern.
- [x] `test.yml`, lingering thread — **root cause found and fixed** (0.3.6): the 0.3.5 fix addressed the wrong hypothesis (real network traffic) — the exact same failure recurred with zero real traffic. Actual cause, confirmed against a known upstream issue rather than guessed: pycares (aiohttp's optional C-ares resolver, pulled in transitively) changed its shutdown logic and leaves a lingering thread merely by being aiohttp's auto-selected resolver, unrelated to whether any request occurs. Fixed by explicitly forcing `ThreadedResolver` on the test session's connector. See [pytest-homeassistant-custom-component#219](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component/issues/219) (open upstream, no released fix) and CHANGELOG.md 0.3.6.
- [x] `test.yml`, lingering thread — **fixed at the correct scope** (0.3.7): 0.3.6 fixed `test_api.py` completely but the identical failure resurfaced one file later (`test_config_flow.py`, the first test touching HA's own `async_get_clientsession`), confirming the root cause is process-wide resolver selection, not anything scoped to one file's fixtures. Moved the fix to `tests/conftest.py` (`sys.modules["aiodns"] = None`, before anything else runs) so it applies to every `ClientSession` in the whole test session, including Home Assistant's own internals. Verified directly with `aiodns`/`pycares` actually installed locally that this flips `aiohttp.resolver.DefaultResolver` from the pycares-backed `AsyncResolver` to `ThreadedResolver`.
- [x] `test.yml`, lingering thread — **fixed by removing the package, not racing its import** (0.3.8): the 0.3.7 conftest.py block was directly verified to work in isolation but still failed in real CI, because `pytest-aiohttp`/`pytest-homeassistant-custom-component` load as entry-point plugins during pytest's own startup, before any conftest.py is ever collected — no conftest.py-level fix can reliably win that race. Fixed at the workflow level instead: `pip uninstall -y aiodns pycares` right after installing test requirements, so there's nothing to import early or late. See CHANGELOG.md 0.3.8.
- [x] `test.yml`, lingering thread — **the actual fix** (0.3.9): 0.3.8's uninstall approach stopped the symptom but broke 9 real tests — `homeassistant/helpers/aiohttp_client.py` hard-requires `AsyncResolver()`/aiodns with no fallback, confirmed via the real traceback. Reverted the uninstall step and the conftest.py block; pinned `pycares<4.9.0` (the version that introduced the shutdown regression) in `requirements_test.txt` instead, keeping aiodns fully installed and functional while avoiding the specific buggy version. See CHANGELOG.md 0.3.9.
- [x] `test.yml`, dependency install itself failing — **found and fixed** (0.3.10): 0.3.9's `pycares<4.9.0` range let pip's resolver wander into unrelated old versions with no prebuilt wheel for the running Python, landing on a genuinely broken sdist (`pycares==4.1.1`) and failing the install step on Python 3.13, which took 3.12 down with it via fail-fast before it even ran. Reproduced locally. Fixed with an exact pin (`pycares==4.8.0`), confirmed via PyPI to have real wheels for both `cp312`/`cp313` manylinux `x86_64`.
- [x] **Confirmed fully green end-to-end** (2026-09-01, commit `37c8375`, verified via `gh run view`): `hassfest` success, `pytest (3.12)` success, `pytest (3.13)` success — `Tests` workflow conclusion: success. `Validate`'s `hacs` job remains red only on the known brand-assets gap (Section 4).
- [x] Node.js 20 deprecation warning — **fixed** (0.3.11): bumped `actions/checkout@v4`→`@v7` and `actions/setup-python@v5`→`@v7` across all three workflows, confirmed both target `node24` in their own `action.yml` before bumping.

## 4. Brand assets

Home Assistant's frontend pulls integration icons/logos from the separate [`home-assistant/brands`](https://github.com/home-assistant/brands) repository. **HACS's own validation, however, accepts a local fallback**: a `custom_components/<domain>/brand/` directory containing at least `icon.png` satisfies its `check-brands` step without needing anything merged upstream (confirmed via [hacs.xyz's own publish docs](https://hacs.xyz/docs/publish/include) and the exact path named in the `hacs/action` failure annotation).

- [x] A MiTY logo now exists in the project (originally `docs/Mity logo.png`/`Mity logo with text.png`, since superseded).
- [x] Placeholder `icon.png`/`icon@2x.png`/`logo.png`/`logo@2x.png` generated at [assets/brand/](../assets/brand/) at the sizes `home-assistant/brands` requires. **Still upscaled from a low-resolution original and soft, not submission-quality** — see [assets/brand/README.md](../assets/brand/README.md).
- [x] **Copied into `custom_components/mity/brand/`** (2026-09-01) — this is what actually clears the `hacs` job's brand-assets check in CI, since HACS checks this local path before falling back to the external repo. Confirmed via the `hacs/action` annotation naming exactly this path (`custom_components/mity/brand/icon.png`) as what it looks for.
- [ ] Not yet re-confirmed green — check the **Actions** tab after this push lands.
- [ ] Replace the placeholders (in both `assets/brand/` and `custom_components/mity/brand/`) with exports from a real high-resolution (ideally vector) source when available.
- [ ] Optional `dark_icon.png`/`dark_logo.png` variants for dark theme — not attempted yet.
- [ ] A PR to `home-assistant/brands` itself (adding assets under `custom_integrations/mity/`, per their [contribution guide](https://github.com/home-assistant/brands#contributing)) is still worth doing eventually for Home Assistant Core's own frontend to show the icon — the local `custom_components/mity/brand/` copy only satisfies HACS's *validation*, not Home Assistant's actual UI rendering, which still reads from the external repo. Not blocking anything right now.

## 5. Submit to `hacs/default`

Once 1–4 are done and the repository has been public with real usage for a reasonable period (HACS's actual current bar — check [their docs](https://www.hacs.xyz/docs/publish/include/) rather than relying on this checklist, since it's tightened over time), submission is a PR to [`hacs/default`](https://github.com/hacs/default) adding this repository to `integration.json` (or via their in-repo submission Issue form — check current process). The `hacs/action` workflow already in this repo (`validate.yml`) runs the same validation HACS's own reviewers will check, so a clean run there is the best local signal of readiness.

## What's already done

- `hacs.json`, `info.md` — present and valid.
- `manifest.json` — has `documentation`, `issue_tracker`, `codeowners`, `version`.
- `.github/workflows/validate.yml` — hassfest + HACS action validation on every push/PR and weekly.
- `.github/workflows/release.yml` — auto-creates a GitHub Release from any `v*.*.*` tag push.
- `.github/CODEOWNERS` — matches `manifest.json`'s `codeowners`.
- `LICENSE` — Apache 2.0.
- README covers installation (HACS custom repo + manual), setup, entities, events, services, privacy, architecture, development, and forking guidance.
- [docs/QUALITY_SCALE.md](QUALITY_SCALE.md) — honest self-assessment against HA's published Integration Quality Scale tiers.
