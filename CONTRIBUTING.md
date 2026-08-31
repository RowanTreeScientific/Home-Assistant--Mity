# Contributing

Thanks for considering a contribution to MiTY Research for Home Assistant.

## Reporting issues

Please open a GitHub issue with:

- Home Assistant version and how the integration was installed (HACS / manual).
- Steps to reproduce, and what you expected vs. what happened.
- Relevant log lines from **Settings → System → Logs**, filtered to `custom_components.mity`.
- If it's a data submission problem, a diagnostics download (**Settings → Devices & Services → MiTY Research → ⋮ → Download diagnostics**) — credentials are automatically redacted, so this is safe to attach.

## Development setup

1. Clone the repository.
2. `pip install -r requirements_test.txt`.
3. Run `ruff check custom_components tests` and `pytest` before opening a PR.
4. For anything touching the config flow, coordinator, or entities, use the [Home Assistant integration dev container](https://developers.home-assistant.io/docs/development_environment/) to run a real Home Assistant instance against your changes — `pytest-homeassistant-custom-component` tests (`tests/test_config_flow.py`) need it too.

## Code style

- `ruff` for linting/formatting, `mypy` for typing — both run in CI.
- Keep the HERD_IOT client (`custom_components/mity/api.py`) free of any `homeassistant` import. It's designed to be extractable into its own package later; a stray HA import there is a regression.
- Follow the [Home Assistant integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) — config flow for all setup, options flow for anything editable afterwards, diagnostics with credentials redacted, and a `DataUpdateCoordinator` for the polling/submission cycle.

## Forking for a specific research project

See [docs/FORKING.md](docs/FORKING.md) if you're a researcher customising this integration for your own study rather than contributing back to this repository.

## Pull requests

- One logical change per PR.
- Update `README.md`/`strings.json`/`translations/en.json` together when adding or changing anything user-facing — they need to stay in sync.
- Add or update tests for any behavioural change.
