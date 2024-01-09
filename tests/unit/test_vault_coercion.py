"""Test that attrs to Vault are being coerced correctly."""
from typing import Any

from src.__main__ import Vault


def coerced_with(**attrs: Any) -> Vault:
    """Return a Vault instance merged with default attrs."""
    default_attrs = {"vault_url": "", "mount_point": "", "secrets_path": "", "chunk_size": "0"}
    new_attrs = {**default_attrs, **attrs}
    return Vault.from_coerced_attrs(**new_attrs)


def test_url_noop_coercion() -> None:
    """Test that http(s)-prefixed urls don't get coerced."""
    variants = ("http://10.0.0.1", "http://example.com", "https://www.example.com")
    for variant in variants:
        assert coerced_with(vault_url=variant).vault_url == variant


def test_url_coercion() -> None:
    """Test that non-http(s)-prefixed urls get coerced."""
    variants = ("10.0.0.1", "example.com", "www.example.com")
    for variant in variants:
        coerced = f"http://{variant}"
        assert coerced_with(vault_url=variant).vault_url == coerced


def test_mount_path_noop_coercion() -> None:
    """Test that a slash-less mount point don't get coerced."""
    val = "mountpoint"
    assert coerced_with(mount_point=val).mount_point == val


def test_mount_path_coercion() -> None:
    """Test that a slashed mount point get coerced."""
    variants = ("/mountpoint", "mountpoint/", "/mountpoint/")
    coerced = "mountpoint"
    for variant in variants:
        assert coerced_with(mount_point=variant).mount_point == coerced


def test_secrets_path_noop_coercion() -> None:
    """Test that a slash-less secrets path don't get coerced."""
    val = "secretspath"
    assert coerced_with(secrets_path=val).secrets_path == val


def test_secrets_path_coercion() -> None:
    """Test that a slashed secrets path get coerced."""
    variants = ("/secretspath", "secretspath/", "/secretspath/")
    coerced = "secretspath"
    for variant in variants:
        assert coerced_with(secrets_path=variant).secrets_path == coerced
