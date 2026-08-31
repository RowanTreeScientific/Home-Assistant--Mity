"""Tests for custom_components.mity.api against a real aiohttp test server.

These tests exercise MityApiClient over actual HTTP (via aiohttp's test
server) rather than mocking internals, so they double as a check that the
client's request/response handling actually matches the wire contract in
"Citizen Science AutoEnrollment Design 20260831.md". They have no
dependency on Home Assistant itself.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer


def _load_api_module():
    """Load api.py directly, bypassing custom_components/mity/__init__.py.

    api.py has no Home Assistant dependency at all -- it's deliberately a
    standalone HTTP client -- but importing it as
    ``custom_components.mity.api`` would run the package's ``__init__.py``
    first, which does depend on ``homeassistant``. Loading it by file path
    keeps these tests free of that dependency.
    """
    module_path = Path(__file__).parent.parent / "custom_components" / "mity" / "api.py"
    spec = importlib.util.spec_from_file_location("mity_api", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_api = _load_api_module()
MityApiClient = _api.MityApiClient
MityAuthError = _api.MityAuthError
MityConnectionError = _api.MityConnectionError
MityInvalidEnrollCodeError = _api.MityInvalidEnrollCodeError
MityRejoinNotPermittedError = _api.MityRejoinNotPermittedError

VALID_CODE = "8f2a1c9e4b7d3f0a6c5e2b8d1f4a7c9e"
VALID_KEY = "2792d736deadbeef"


def _build_app() -> web.Application:
    app = web.Application()

    async def enroll(request: web.Request) -> web.Response:
        body = await request.json()
        if body.get("enrollCode") != VALID_CODE:
            return web.json_response(
                {"error": "Invalid or inactive enrollment code"}, status=404
            )
        return web.json_response(
            {"instanceId": 42, "deviceApiKey": VALID_KEY, "rejoinToken": "rejoin-1"}
        )

    async def policy(request: web.Request) -> web.Response:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {VALID_KEY}":
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response(
            {
                "autoDeleteOnRemove": False,
                "removalCooloffDays": 30,
                "rejoinPolicy": "same_identity",
            }
        )

    async def ingest(request: web.Request) -> web.Response:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {VALID_KEY}":
            return web.json_response({"error": "unauthorized"}, status=403)
        return web.json_response({"success": True, "id": 999})

    async def rejoin(request: web.Request) -> web.Response:
        body = await request.json()
        if body.get("rejoinToken") == "blocked-token":
            return web.json_response(
                {
                    "error": "This trial requires a new enrollment after leaving",
                    "code": "rejoin_not_permitted",
                },
                status=404,
            )
        return web.json_response(
            {"instanceId": 42, "deviceApiKey": "new-key", "rejoinToken": "rejoin-2"}
        )

    async def remove(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "success": True,
                "dataWillBeDeleted": True,
                "deletedImmediately": False,
                "cooloffEndsAt": "2026-09-30",
            }
        )

    app.router.add_post("/v1/citizen-science/enroll", enroll)
    app.router.add_get("/v1/citizen-science/policy", policy)
    app.router.add_post("/v1/ingest", ingest)
    app.router.add_post("/v1/citizen-science/rejoin", rejoin)
    app.router.add_post("/v1/citizen-science/remove", remove)
    return app


@pytest.fixture
async def client():
    server = TestServer(_build_app())
    test_client = TestClient(server)
    await test_client.start_server()
    base_url = str(test_client.make_url(""))
    yield MityApiClient(test_client.session, base_url)
    await test_client.close()


async def test_enroll_success(client: MityApiClient) -> None:
    result = await client.enroll(VALID_CODE)
    assert result.instance_id == 42
    assert result.device_api_key == VALID_KEY
    assert result.rejoin_token == "rejoin-1"


async def test_enroll_invalid_code(client: MityApiClient) -> None:
    with pytest.raises(MityInvalidEnrollCodeError):
        await client.enroll("wrong-code")


async def test_get_policy(client: MityApiClient) -> None:
    policy = await client.get_policy(VALID_KEY)
    assert policy.auto_delete_on_remove is False
    assert policy.removal_cooloff_days == 30
    assert policy.rejoin_policy == "same_identity"


async def test_get_policy_bad_key(client: MityApiClient) -> None:
    with pytest.raises(MityAuthError):
        await client.get_policy("wrong-key")


async def test_submit(client: MityApiClient) -> None:
    result = await client.submit(VALID_KEY, 42, {"temperature": 21.4})
    assert result.success is True
    assert result.submission_id == 999


async def test_submit_bad_key(client: MityApiClient) -> None:
    with pytest.raises(MityAuthError):
        await client.submit("wrong-key", 42, {"temperature": 21.4})


async def test_rejoin_success(client: MityApiClient) -> None:
    result = await client.rejoin("some-token")
    assert result.device_api_key == "new-key"


async def test_rejoin_blocked(client: MityApiClient) -> None:
    with pytest.raises(MityRejoinNotPermittedError):
        await client.rejoin("blocked-token")


async def test_remove(client: MityApiClient) -> None:
    result = await client.remove(VALID_KEY, "remove_and_delete")
    assert result.success is True
    assert result.data_will_be_deleted is True
    assert result.deleted_immediately is False
    assert result.cooloff_ends_at == "2026-09-30"


async def test_connection_error() -> None:
    """A real socket connection attempt is unnecessary and, under
    pytest-homeassistant-custom-component's global socket guard (part of
    the HA test suite this file otherwise has no dependency on), actively
    blocked -- mock the failure at the request layer instead, which is
    both faster and deterministic regardless of what's listening on
    localhost in a given test environment.
    """
    from unittest.mock import patch

    from aiohttp import ClientConnectionError, ClientSession

    async with ClientSession() as session:
        client = MityApiClient(session, "http://api.mi-ty-tre.co.uk")
        with (
            patch.object(
                session, "request", side_effect=ClientConnectionError("mock failure")
            ),
            pytest.raises(MityConnectionError),
        ):
            await client.enroll(VALID_CODE)
