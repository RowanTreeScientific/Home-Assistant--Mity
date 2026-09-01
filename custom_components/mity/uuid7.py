"""Minimal UUID version 7 (RFC 9562) generator.

The HERD-IoT identifier scheme requires the observation-id component to
be a UUID v7 for temporal ordering (Implementation Guide section 3.1.2,
3.3). Python's stdlib gained `uuid.uuid7()` only in 3.14 -- newer than
Home Assistant's minimum supported Python -- so this implements the
layout directly rather than adding a third-party dependency for one
function.
"""

from __future__ import annotations

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """Generate a time-ordered UUID: 48-bit ms timestamp + 74 random bits."""
    ms = int(time.time() * 1000)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF

    value = ms << 80
    value |= 0x7 << 76  # version 7
    value |= rand_a << 64
    value |= 0b10 << 62  # RFC 4122 variant
    value |= rand_b

    return uuid.UUID(int=value)
