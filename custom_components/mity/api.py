"""HERD_IOT client for the MiTY citizen-science API.

This module is the "HERD_IOT wrapper" called for in the project objectives:
a small, HA-independent client for the handful of MiTY endpoints a citizen
science device needs. It knows nothing about Home Assistant entities or
config entries -- it only speaks the HTTP contract described in
"Citizen Science AutoEnrollment Design 20260831.md". Keeping it isolated
here means it could be lifted into its own PyPI package later without
touching anything else in this integration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Kept as a literal here, matching every other endpoint path in this file,
# rather than imported from const.py -- this module is deliberately kept
# free of any relative import (even to const.py) so it can be loaded
# standalone by file path in tests/test_api.py without needing the rest
# of the package (or Home Assistant) importable. See that file's module
# docstring for the exact failure mode a relative import here reintroduces.
HERD_DIRECT_PATH = "/api/v1/herd/direct"


class MityApiError(Exception):
    """Base error for any MiTY API failure."""


class MityConnectionError(MityApiError):
    """Raised when the MiTY server cannot be reached at all."""


class MityAuthError(MityApiError):
    """Raised on 401/403 -- the device credential is missing or invalid."""


class MityInvalidEnrollCodeError(MityApiError):
    """Raised on 404 from /enroll -- the enrollment code is wrong/inactive.

    Per the API design, MiTY deliberately returns the same generic error for
    an unknown code, a disabled trial, or a malformed code, so this
    exception intentionally carries no further detail either.
    """


class MityRejoinNotPermittedError(MityApiError):
    """Raised when a trial's rejoin_policy is 'new_identity_required'."""


class MityRateLimitedError(MityApiError):
    """Raised on 429."""


@dataclass
class EnrollmentResult:
    """Credentials returned by a successful enrollment or rejoin."""

    instance_id: int
    device_api_key: str
    rejoin_token: str


@dataclass
class CitizenSciencePolicy:
    """A trial's current withdrawal/rejoin policy, as told to the device."""

    auto_delete_on_remove: bool
    removal_cooloff_days: int
    rejoin_policy: str


@dataclass
class RemovalResult:
    """Response to a withdrawal request."""

    success: bool
    data_will_be_deleted: bool
    deleted_immediately: bool
    cooloff_ends_at: str | None


@dataclass
class IngestResult:
    """Response to a legacy flat /v1/ingest submission.

    Superseded by HerdSubmitResult / submit_herd_entities() now that the
    backend is being rebuilt against the HERD-IoT Implementation Guide
    v1.0 -- kept only because the flat /v1/ingest endpoint may still be
    live during the migration; see uses in coordinator.py.
    """

    success: bool
    submission_id: Any


@dataclass
class HerdObservationResult:
    """Per-observation outcome from a HERD-IoT direct submission."""

    observation_id: str | None
    status: str
    tier: str | None
    errors: list[str]
    warnings: list[str]

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


@dataclass
class HerdSubmitResult:
    """Response to POST /api/v1/herd/direct -- one result per entity sent."""

    results: list[HerdObservationResult]

    @property
    def all_accepted(self) -> bool:
        return bool(self.results) and all(r.accepted for r in self.results)


class MityApiClient:
    """Thin async wrapper around the MiTY citizen-science HTTP API."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method, url, headers=headers, json=json
            ) as resp:
                if resp.status == 401 or resp.status == 403:
                    raise MityAuthError(f"{method} {path} -> {resp.status}")
                if resp.status == 404 and path == "/v1/citizen-science/enroll":
                    raise MityInvalidEnrollCodeError()
                if resp.status == 429:
                    raise MityRateLimitedError(f"{method} {path} rate limited")
                body: dict[str, Any] = {}
                if resp.content_length or resp.headers.get(
                    "content-type", ""
                ).startswith("application/json"):
                    try:
                        body = await resp.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError):
                        body = {}
                if resp.status == 404 and body.get("code") == "rejoin_not_permitted":
                    raise MityRejoinNotPermittedError(
                        body.get("error", "Rejoin not permitted")
                    )
                if resp.status >= 400:
                    raise MityApiError(
                        f"{method} {path} -> {resp.status}: {body.get('error', body)}"
                    )
                return body
        except aiohttp.ClientError as err:
            raise MityConnectionError(str(err)) from err

    def _auth_headers(self, device_api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {device_api_key}"}

    async def enroll(self, enroll_code: str) -> EnrollmentResult:
        """Call POST /v1/citizen-science/enroll with a study's enrollment code."""
        body = await self._request(
            "POST",
            "/v1/citizen-science/enroll",
            json={"enrollCode": enroll_code},
        )
        return EnrollmentResult(
            instance_id=body["instanceId"],
            device_api_key=body["deviceApiKey"],
            rejoin_token=body["rejoinToken"],
        )

    async def get_policy(self, device_api_key: str) -> CitizenSciencePolicy:
        """Call GET /v1/citizen-science/policy with the device's own credentials."""
        body = await self._request(
            "GET",
            "/v1/citizen-science/policy",
            headers=self._auth_headers(device_api_key),
        )
        return CitizenSciencePolicy(
            auto_delete_on_remove=body["autoDeleteOnRemove"],
            removal_cooloff_days=body["removalCooloffDays"],
            rejoin_policy=body["rejoinPolicy"],
        )

    async def submit(
        self,
        device_api_key: str,
        instance_id: int,
        data: dict[str, Any],
        reference: str | None = None,
    ) -> IngestResult:
        """Call POST /v1/ingest -- the same endpoint every MiTY data source uses."""
        payload: dict[str, Any] = {"InstanceID": instance_id, "data": data}
        if reference:
            payload["Reference"] = reference
        body = await self._request(
            "POST",
            "/v1/ingest",
            headers=self._auth_headers(device_api_key),
            json=payload,
        )
        return IngestResult(
            success=bool(body.get("success")), submission_id=body.get("id")
        )

    async def set_paused(self, device_api_key: str, paused: bool) -> None:
        """Call POST /v1/citizen-science/pause.

        Purely informational for MiTY's own dashboards -- MiTY never enforces
        this. The integration itself is what actually stops sending data.
        """
        await self._request(
            "POST",
            "/v1/citizen-science/pause",
            headers=self._auth_headers(device_api_key),
            json={"paused": paused},
        )

    async def remove(self, device_api_key: str, action: str) -> RemovalResult:
        """Call POST /v1/citizen-science/remove.

        `action` is "remove_only" or "remove_and_delete". This revokes the
        device's own ingest key immediately -- the returned key stops
        working the moment this call succeeds.
        """
        body = await self._request(
            "POST",
            "/v1/citizen-science/remove",
            headers=self._auth_headers(device_api_key),
            json={"action": action},
        )
        return RemovalResult(
            success=bool(body.get("success")),
            data_will_be_deleted=bool(body.get("dataWillBeDeleted")),
            deleted_immediately=bool(body.get("deletedImmediately")),
            cooloff_ends_at=body.get("cooloffEndsAt"),
        )

    async def submit_herd_entities(
        self, device_api_key: str, entities: list[dict[str, Any]]
    ) -> HerdSubmitResult:
        """POST /api/v1/herd/direct -- HERD-IoT Spec v1.0 Pathway 1 (Direct Submission).

        Body is always sent as a JSON array (Implementation Guide 5.2.1:
        "a single... entity, or an array of entities for batch
        submission" -- sending a one-element array works for either case
        and keeps this method's response parsing uniform). Response
        shape isn't fully specified for the batch case beyond "an array
        of per-observation results" (5.2.3), so this tolerates either a
        bare JSON array or a dict wrapping one under a "results" key,
        and falls back to treating a single dict response (Figure 5.1's
        shape) as a one-result list.

        Bypasses the shared `_request()` helper deliberately: that
        method assumes a dict-shaped body throughout (`body.get(...)`),
        which a bare top-level JSON array response would break.
        """
        url = f"{self._base_url}{HERD_DIRECT_PATH}"
        headers = self._auth_headers(device_api_key)
        try:
            async with self._session.request(
                "POST", url, headers=headers, json=entities
            ) as resp:
                if resp.status in (401, 403):
                    raise MityAuthError(f"POST {HERD_DIRECT_PATH} -> {resp.status}")
                if resp.status == 429:
                    raise MityRateLimitedError(
                        f"POST {HERD_DIRECT_PATH} rate limited"
                    )
                raw: Any = None
                if resp.content_length or resp.headers.get(
                    "content-type", ""
                ).startswith("application/json"):
                    try:
                        raw = await resp.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError):
                        raw = None
                if resp.status >= 400:
                    raise MityApiError(
                        f"POST {HERD_DIRECT_PATH} -> {resp.status}: {raw}"
                    )
                return _parse_herd_submit_response(raw)
        except aiohttp.ClientError as err:
            raise MityConnectionError(str(err)) from err

    async def rejoin(self, rejoin_token: str) -> EnrollmentResult:
        """Call POST /v1/citizen-science/rejoin using the stored rejoin token.

        Deliberately does not use the (possibly revoked) device API key --
        the rejoin token is a separate secret that keeps working after
        withdrawal, by design.
        """
        body = await self._request(
            "POST",
            "/v1/citizen-science/rejoin",
            json={"rejoinToken": rejoin_token},
        )
        return EnrollmentResult(
            instance_id=body["instanceId"],
            device_api_key=body["deviceApiKey"],
            rejoin_token=body["rejoinToken"],
        )


def _parse_herd_observation_result(item: dict[str, Any]) -> HerdObservationResult:
    validation = item.get("validationResult") or {}
    return HerdObservationResult(
        observation_id=item.get("observationId") or item.get("id"),
        status=str(item.get("status", "unknown")),
        tier=validation.get("tier"),
        errors=list(validation.get("errors") or []),
        warnings=list(validation.get("warnings") or []),
    )


def _parse_herd_submit_response(raw: Any) -> HerdSubmitResult:
    """Normalise whichever of the response shapes described in
    submit_herd_entities()'s docstring the server actually returned."""
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and isinstance(raw.get("results"), list):
        items = raw["results"]
    elif isinstance(raw, dict) and raw:
        items = [raw]
    else:
        items = []
    return HerdSubmitResult(
        results=[_parse_herd_observation_result(item) for item in items]
    )
