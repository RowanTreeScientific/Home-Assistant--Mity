"""Tests for the UUID v7 generator (custom_components/mity/uuid7.py).

No Home Assistant dependency and no relative imports in the module under
test, so this loads and runs like test_api.py -- standalone, by file path.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path


def _load_uuid7_module():
    module_path = (
        Path(__file__).parent.parent / "custom_components" / "mity" / "uuid7.py"
    )
    spec = importlib.util.spec_from_file_location("mity_uuid7", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_mod = _load_uuid7_module()
uuid7 = _mod.uuid7


def test_version_is_7() -> None:
    assert uuid7().version == 7


def test_variant_bits() -> None:
    # RFC 4122 variant: the two most significant bits of byte 8 are '10'.
    u = uuid7()
    assert (u.bytes[8] & 0b11000000) == 0b10000000


def test_unique_across_many_calls() -> None:
    values = {str(uuid7()) for _ in range(1000)}
    assert len(values) == 1000


def test_lexicographically_time_ordered() -> None:
    """The canonical hex string form must sort the same way generation
    order does -- that's the entire point of a v7 UUID (time-ordering)."""
    first = str(uuid7())
    time.sleep(0.01)
    second = str(uuid7())
    assert first < second
