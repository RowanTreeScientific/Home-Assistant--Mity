# Testing this integration on a local Home Assistant instance

## 1. Get a Home Assistant instance to test against

If you don't already have one running, the fastest way to get a disposable test instance (Docker required):

```bash
docker run -d --name ha-test -p 8123:8123 -v ha_test_config:/config ghcr.io/home-assistant/home-assistant:stable
```

Wait about a minute, then open `http://localhost:8123` and complete the one-time onboarding (create a local user — this stays entirely on your machine).

If you already have a real Home Assistant instance (a Raspberry Pi, HA OS box, an existing Docker/venv setup), you can install into that instead — skip to step 2 and use that instance's own `config/custom_components/` directory in place of the Docker volume path below.

## 2. Copy the integration into `custom_components`

Copy the `custom_components/mity` folder from this repository into your Home Assistant config directory.

**Docker (from step 1):**

```bash
docker cp "custom_components/mity" ha-test:/config/custom_components/mity
docker restart ha-test
```

**Any other install (venv, HA OS via Samba/SSH add-on, etc.):**

Copy `custom_components/mity` so it ends up at `<your config dir>/custom_components/mity/` (i.e. the `mity` folder itself, containing `manifest.json`, sits directly under `custom_components/`), then restart Home Assistant from its own UI (**Settings → System → Restart**) or however you normally restart it.

## 3. Add the integration

1. **Settings → Devices & Services → Add Integration**, search for **MiTY Research**.
2. If it doesn't appear, check **Settings → System → Logs** for a traceback on load — that means step 2 didn't land the files somewhere Home Assistant scans, or `manifest.json` is missing/invalid.
3. You'll need a real MiTY endpoint and a real study enrollment code to get past step 1 of setup — this integration talks to an actual MiTY server, there's no built-in mock/demo mode. Use a real (ideally test/internal) study's code, not a production one, until you're confident in what you're testing (see the auto-enrollment design's note: don't distribute a real code to real members of the public before the endpoint is on HTTPS).

## 4. What to actually test

- **Enrollment**: correct endpoint + valid code succeeds and creates a device; a wrong code shows `invalid_enroll_code` without crashing the flow; unreachable endpoint shows `cannot_connect`.
- **Parameter mapping**: pick a couple of existing `sensor.*`/`binary_sensor.*` entities in your test instance (or use one of the built-in demo sensors if using a fresh HA install with the `demo` integration enabled) for temperature/humidity/motion.
- **Submission**: use `button.mity_send_data_now` to trigger a submission on demand rather than waiting for the schedule; watch `sensor.mity_status` and the `mity_data_accepted`/`mity_data_rejected`/`mity_data_error` events in **Developer Tools → Events** (listen for `mity_data_*`).
- **Pause**: toggle `switch.mity_pause_contribution` and confirm `sensor.mity_status` reports `paused` on the next update instead of submitting.
- **Multi-study**: run **Add Integration** a second time with a different code (or the same code, if your test trial allows re-enrolling the same code into a second device) to confirm two independent devices appear, each named by nickname.
- **Leave/remove**: delete one of the integration entries (**⋮ → Delete**) and confirm (via logs, or the MiTY side if you have access) that a `remove_only` withdrawal was attempted.
- **Reauth**: harder to trigger deliberately without MiTY-side access to revoke a key mid-test — if you can revoke a device's key from the MiTY admin side, the next failed submission should raise a repair/reauth notification in Home Assistant (**Settings → Devices & Services**, the integration card shows "Reconfigure"/a warning badge).
- **Diagnostics**: download diagnostics for the device (**⋮ → Download diagnostics**) and confirm `device_api_key`/`rejoin_token` show as `**REDACTED**`, not the real values.

## 5. Iterating on code changes

After editing files in this repo, re-copy `custom_components/mity` into the test instance's `custom_components/` (steps above) and restart Home Assistant — custom integrations aren't hot-reloaded on file change by default. If you're doing this repeatedly, consider mounting this repo's `custom_components/mity` directly as the Docker volume instead of copying each time:

```bash
docker run -d --name ha-test -p 8123:8123 \
  -v ha_test_config:/config \
  -v "$(pwd)/custom_components/mity:/config/custom_components/mity" \
  ghcr.io/home-assistant/home-assistant:stable
```

With this mount, a plain `docker restart ha-test` picks up your local edits without any copy step.
