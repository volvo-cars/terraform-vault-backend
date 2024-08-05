"""Module for testing the chunking functions pack_state and unpack_state.

The main thing being asserted is their inverse relationship. It's less relevant
to check for e.g. individual objects being packed correctly, since this assert would be
highly volatile.
"""

import base64
from typing import Any, cast

import pytest

from src.__main__ import (
    FORMAT_VERSION,
    MissingFormatVersionError,
    UnsupportedFormatVersionError,
    pack_state,
    unpack_state,
)


def chunking_is_inverse(o: Any) -> bool:
    """Test that unpack_state(pack_state(o)) == o for any object o."""
    return cast(bool, unpack_state(pack_state(o)) == o)


def test_none_chunk() -> None:
    """Test that None is chunked currectly."""
    o = None
    assert chunking_is_inverse(o)


def test_str_chunk() -> None:
    """Test that a str is chunked correctly."""
    o = "foo"
    assert chunking_is_inverse(o)


def test_int_chunk() -> None:
    """Test that an int is chunked correctly."""
    o = 42
    assert chunking_is_inverse(o)


def test_list_chunk() -> None:
    """Test that a list is chunked correctly."""
    o = [1, 2, 3]
    assert chunking_is_inverse(o)


def test_dict_chunk() -> None:
    """Test that a dict is chunked correctly."""
    o = {"foo": "bar"}
    assert chunking_is_inverse(o)


def test_serialize_version_prefix() -> None:
    """Test that serialized state contains the current version as a prefix."""
    o = {"foo": "bar"}
    serialized = pack_state(o)
    assert serialized.startswith(f"{FORMAT_VERSION}:")


def test_deserialize_missing_version_prefix() -> None:
    """Test that deserialization fails on missing version prefix."""
    o = base64.b64encode(b"{'foo': 'bar'}").decode("utf-8")
    with pytest.raises(MissingFormatVersionError):
        unpack_state(o)


def test_deserialize_unsupported_version() -> None:
    """Test that deserialization fails on unsupported version."""
    payload = base64.b64encode(b"{'foo': 'bar'}").decode("utf-8")
    o = f"v1000000:{payload}"
    with pytest.raises(UnsupportedFormatVersionError):
        unpack_state(o)
