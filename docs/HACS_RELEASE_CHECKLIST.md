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

- [ ] Confirm `.github/workflows/validate.yml` (hassfest + `hacs/action`) passes on the `master` branch — check the **Actions** tab. Both were added at project start but have never been confirmed green from this side (no `gh` CLI / API access available in this environment to check run status).
- [ ] Confirm `.github/workflows/test.yml` (ruff + pytest, including the HA-dependent suite under `pytest-homeassistant-custom-component`) passes.

## 4. Brand assets

HACS and Home Assistant's frontend pull integration icons/logos from the separate [`home-assistant/brands`](https://github.com/home-assistant/brands) repository, not from anything in this repo. Until a submission is made there, this integration shows Home Assistant's generic puzzle-piece icon — functionally fine, just not distinctive.

**This needs a design decision before it can be built**: MiTY doesn't currently have a logo/icon asset anywhere in this project's source material (checked — none exists). Submitting requires:
- `icon.png` (256×256) and `icon@2x.png` (512×512) — required.
- `logo.png` and `logo@2x.png` — optional but recommended (wider aspect ratio, used in more UI contexts).
- Optional `dark_icon.png`/`dark_logo.png` variants for dark theme.
- A PR to `home-assistant/brands` adding these under `custom_integrations/mity/`, following their [contribution guide](https://github.com/home-assistant/brands#contributing).

Once a logo exists (from the MiTY brand/marketing side) and the `home-assistant/brands` PR is merged, no code change is needed here — `manifest.json`'s `domain` (`mity`) is already what brands looks up by.

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
