"""Tests for custom_components.mity.api against mocked HTTP responses.

These exercise MityApiClient's request/response handling against the wire
contract in "Citizen Science AutoEnrollment Design 20260831.md" by
replacing `ClientSession.request` with a stdlib `unittest.mock` fake --
deliberately not a real server or a third-party HTTP-mocking library.

This file went through two earlier approaches, both abandoned for good
reasons worth recording:

1. A real `aiohttp.test_utils.TestServer` (a real, loopback-only socket),
   worked around `pytest-homeassistant-custom-component`'s global
   `pytest-socket` guard with the `enable_socket` marker. That surfaced a
   second, subtler problem: allowing real (even loopback) network I/O let
   a test trigger Python 3.12's asyncio default-executor watchdog thread,
   which HA's own strict thread-leak-detecting test fixture then failed
   on -- a real interaction between "uses a real server" and "this test
   framework is very strict about hygiene", not a bug in this
   integration's code.
2. `aioresponses`, to mock at the HTTP layer without a real server. That
   turned out to have its own live compatibility gap with recent aiohttp
   versions (`ClientResponse.__init__() missing... 'stream_writer'`,
   reproduced locally) and, in some setup path, *still* touched a real
   socket under `--disable-socket`.

A small local fake for exactly the one seam these tests need
(`session.request`) sidesteps both: no real *traffic* can occur because
nothing beneath the mocked `request()` ever runs -- but constructing a
real `aiohttp.ClientSession()` at all still trips `pytest-socket`'s guard
once, synchronously, at fixture setup: `TCPConnector.__init__` does a
one-shot IPv6-capability probe via a bare `socket.socket()` call, unrelated
to any actual connection attempt. That's the narrow, well-understood thing
`enable_socket` is covering here -- not real network I/O of any kind, so
it should not reproduce the executor-thread-leak issue from approach 1
above, which was caused by genuine HTTP traffic through a real connector.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.enable_socket


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

BASE_URL = "http://api.mi-ty-tre.co.uk"
VALID_CODE = "8f2a1c9e4b7d3f0a6c5e2b8d1f4a7c9e"
VALID_KEY = "2792d736deadbeef"


class _FakeResponse:
    """Just enough of aiohttp.ClientResponse for api.py's _request() to work."""

    def __init__(self, status: int, json_body: dict | None = None) -> None:
        self.status = status
        self._json_body = json_body if json_body is not None else {}
        self.headers = {"content-type": "application/json"}
        self.content_length = 1

    async def json(self, content_type: str | None = None) -> dict:
        return self._json_body


class _FakeRequestContext:
    """Mimics the async context manager ClientSession.request() returns."""

    def __init__(
        self,
        response: _FakeResponse | None = None,
        exception: Exception | None = None,
    ) -> None:
        self._response = response
        self._exception = exception

    async def __aenter__(self) -> _FakeResponse:
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _mock_response(session, status: int, json_body: dict | None = None) -> None:
    session.request = MagicMock(
        return_value=_FakeRequestContext(_FakeResponse(status, json_body))
    )


def _mock_exception(session, exception: Exception) -> None:
    session.request = MagicMock(
        return_value=_FakeRequestContext(exception=exception)
    )


@pytest.fixture
async def session():
    from aiohttp import ClientSession

    async with ClientSession() as s:
        yield s


@pytest.fixture
def client(session) -> MityApiClient:
    return MityApiClient(session, BASE_URL)


async def test_enroll_success(client: MityApiClient, session) -> None:
    _mock_response(
        session,
        200,
        {"instanceId": 42, "deviceApiKey": VALID_KEY, "rejoinToken": "rejoin-1"},
    )
    result = await client.enroll(VALID_CODE)
    assert result.instance_id == 42
    assert result.device_api_key == VALID_KEY
    assert result.rejoin_token == "rejoin-1"


async def test_enroll_invalid_code(client: MityApiClient, session) -> None:
    _mock_response(
        session, 404, {"error": "Invalid or inactive enrollment code"}
    )
    with pytest.raises(MityInvalidEnrollCodeError):
        await client.enroll("wrong-code")


async def test_get_policy(client: MityApiClient, session) -> None:
    _mock_response(
        session,
        200,
        {
            "autoDeleteOnRemove": False,
            "removalCooloffDays": 30,
            "rejoinPolicy": "same_identity",
        },
    )
    policy = await client.get_policy(VALID_KEY)
    assert policy.auto_delete_on_remove is False
    assert policy.removal_cooloff_days == 30
    assert policy.rejoin_policy == "same_identity"


async def test_get_policy_bad_key(client: MityApiClient, session) -> None:
    _mock_response(session, 401, {"error": "unauthorized"})
    with pytest.raises(MityAuthError):
        await client.get_policy("wrong-key")


async def test_submit(client: MityApiClient, session) -> None:
    _mock_response(session, 200, {"success": True, "id": 999})
    result = await client.submit(VALID_KEY, 42, {"temperature": 21.4})
    assert result.success is True
    assert result.submission_id == 999


async def test_submit_bad_key(client: MityApiClient, session) -> None:
    _mock_response(session, 403, {"error": "unauthorized"})
    with pytest.raises(MityAuthError):
        await client.submit("wrong-key", 42, {"temperature": 21.4})


async def test_rejoin_success(client: MityApiClient, session) -> None:
    _mock_response(
        session,
        200,
        {"instanceId": 42, "deviceApiKey": "new-key", "rejoinToken": "rejoin-2"},
    )
    result = await client.rejoin("some-token")
    assert result.device_api_key == "new-key"


async def test_rejoin_blocked(client: MityApiClient, session) -> None:
    _mock_response(
        session,
        404,
        {
            "error": "This trial requires a new enrollment after leaving",
            "code": "rejoin_not_permitted",
        },
    )
    with pytest.raises(MityRejoinNotPermittedError):
        await client.rejoin("blocked-token")


async def test_remove(client: MityApiClient, session) -> None:
    _mock_response(
        session,
        200,
        {
            "success": True,
            "dataWillBeDeleted": True,
            "deletedImmediately": False,
            "cooloffEndsAt": "2026-09-30",
        },
    )
    result = await client.remove(VALID_KEY, "remove_and_delete")
    assert result.success is True
    assert result.data_will_be_deleted is True
    assert result.deleted_immediately is False
    assert result.cooloff_ends_at == "2026-09-30"


async def test_connection_error(client: MityApiClient, session) -> None:
    from aiohttp import ClientConnectionError

    _mock_exception(session, ClientConnectionError("mock failure"))
    with pytest.raises(MityConnectionError):
        await client.enroll(VALID_CODE)
