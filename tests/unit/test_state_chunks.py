"""Test that a chunked state is stored and read back correctly."""

from __future__ import annotations

import base64
import os
from types import SimpleNamespace
from typing import Any

import pytest

from tvb.__main__ import Vault

TOKEN = "test-token"  # noqa: S105
DECIMAL_CHUNK_KEYS = 10  # keys 0 to 9 sort the same as strings and as numbers


class FakeKV:
    """Minimal in-memory stand-in for the hvac KV v2 API used by Vault.

    Like Vault, list_secrets returns keys in lexicographic order.
    """

    def __init__(self) -> None:
        self.secrets: dict[str, dict[str, Any] | None] = {}

    def create_or_update_secret(self, path: str, secret: dict[str, Any], **_: Any) -> None:
        """Store a secret."""
        self.secrets[path] = secret

    def read_secret_version(self, path: str, **_: Any) -> dict[str, Any]:
        """Read a secret, marking deleted ones the way Vault does."""
        secret = self.secrets[path]
        deletion_time = "" if secret is not None else "2024-01-01T00:00:00Z"
        return {"data": {"data": secret, "metadata": {"deletion_time": deletion_time}}}

    def list_secrets(self, path: str, **_: Any) -> dict[str, Any]:
        """List the keys directly below a path, sorted as strings."""
        prefix = f"{path}/"
        keys = sorted(k.removeprefix(prefix) for k in self.secrets if k.startswith(prefix))
        return {"data": {"keys": keys}}

    def delete_latest_version_of_secret(self, path: str, **_: Any) -> None:
        """Soft delete a secret."""
        self.secrets[path] = None


@pytest.fixture
def vault(monkeypatch: pytest.MonkeyPatch) -> Vault:
    """Return a Vault backed by an in-memory KV store with a small chunk size."""
    kv = FakeKV()
    client = SimpleNamespace(secrets=SimpleNamespace(kv=SimpleNamespace(v2=kv)))
    monkeypatch.setattr(Vault, "_mk_client", lambda _self, _token: client)
    return Vault.from_coerced_attrs(
        vault_url="vault.example.com", mount_point="secret", secrets_path="tf", chunk_size=2000
    )


def test_state_roundtrip_with_more_than_ten_chunks(vault: Vault) -> None:
    """Test that a state split into more than ten chunks is reassembled in order."""
    # Random bytes do not compress, so the packed state needs well over ten chunks.
    state = {"blob": base64.b64encode(os.urandom(30_000)).decode()}
    vault.set_state(token=TOKEN, value=state)
    assert len(list(vault._get_chunk_keys(token=TOKEN))) > DECIMAL_CHUNK_KEYS  # noqa: SLF001
    assert vault.get_state(token=TOKEN) == state
