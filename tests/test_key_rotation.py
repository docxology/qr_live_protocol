"""
Tests for extended key rotation in src.crypto.key_manager and the CLI.

Covers archiving keys, automated signing-key rotation, and the CLI
``keys rotate --trust-store`` workflow.
"""

import json

from click.testing import CliRunner

from src.cli import cli
from src.crypto.key_manager import KeyManager
from src.trust import TrustStore


def _key_manager(tmp_path) -> KeyManager:
    return KeyManager(str(tmp_path))


def test_archive_key_moves_file_and_returns_public(tmp_path):
    km = _key_manager(tmp_path)
    km.generate_keypair("rsa", 2048, purpose="qr_signing")
    key_id = next(iter(km.list_keys()))

    public_pem = km.archive_key(key_id)
    assert public_pem is not None
    # Key no longer active.
    assert key_id not in km.list_keys()
    # Its key file was moved under the default archive dir.
    assert (tmp_path / "archive" / f"{key_id}.key").exists()
    # get_keypair no longer resolves it.
    assert km.get_keypair(key_id) is None


def test_archive_key_custom_archive_dir(tmp_path):
    km = _key_manager(tmp_path)
    km.generate_keypair("rsa", 2048)
    key_id = next(iter(km.list_keys()))

    archive_dir = tmp_path / "custom_archive"
    public_pem = km.archive_key(key_id, str(archive_dir))
    assert public_pem is not None
    assert (archive_dir / f"{key_id}.key").exists()


def test_archive_missing_key_returns_none(tmp_path):
    km = _key_manager(tmp_path)
    assert km.archive_key("does_not_exist") is None


def test_rotate_signing_key_archives_old(tmp_path):
    km = _key_manager(tmp_path)
    km.generate_keypair("rsa", 2048, purpose="qr_signing")
    old_id = next(iter(km.list_keys()))

    new_id, old_public = km.rotate_signing_key(key_id=old_id)
    assert new_id != old_id
    assert old_public is not None
    assert old_id not in km.list_keys()
    assert new_id in km.list_keys()
    assert (tmp_path / "archive" / f"{old_id}.key").exists()


def test_rotate_signing_key_without_old(tmp_path):
    km = _key_manager(tmp_path)
    new_id, old_public = km.rotate_signing_key()
    assert old_public is None
    assert new_id in km.list_keys()


def test_rotate_preserves_verification_via_trust_store(tmp_path):
    """Rotating an old signing key and trusting its public key keeps old QRs verifiable."""
    km = _key_manager(tmp_path)
    km.generate_keypair("rsa", 2048, purpose="qr_signing")
    old_id = next(iter(km.list_keys()))
    old_public = km.export_public_key(old_id)

    new_id, rotated_public = km.rotate_signing_key(key_id=old_id)
    assert rotated_public == old_public

    store = TrustStore()
    assert rotated_public is not None
    store.add_public_key("issuer", old_id, rotated_public, "rsa")
    assert store.is_trusted("issuer", old_id)
    assert not store.is_trusted("issuer", new_id)


def test_cli_keys_rotate_with_trust_store(tmp_path):
    """`qrlp keys rotate --trust-store` should archive the old key and record it."""
    runner = CliRunner()
    config = tmp_path / "config.json"
    key_dir = tmp_path / "keys"
    config.write_text(
        json.dumps(
            {
                "blockchain_settings": {"enabled_chains": []},
                "time_settings": {"time_servers": []},
                "security_settings": {"key_dir": str(key_dir)},
                "web_settings": {"auto_open_browser": False},
            }
        ),
        encoding="utf-8",
    )

    gen = runner.invoke(
        cli, ["--config", str(config), "keys", "generate", "--purpose", "qr_signing"]
    )
    assert gen.exit_code == 0, gen.output
    key_id = gen.output.split("Generated key: ", 1)[1].splitlines()[0]

    trust_store = tmp_path / "trust.json"
    rotate = runner.invoke(
        cli,
        [
            "--config",
            str(config),
            "keys",
            "rotate",
            key_id,
            "--trust-store",
            str(trust_store),
            "--issuer",
            "issuer-cli",
        ],
    )
    assert rotate.exit_code == 0, rotate.output
    assert trust_store.exists()
    data = json.loads(trust_store.read_text())
    stored_keys = data["trusted_keys"]
    assert any(k["key_id"] == key_id for k in stored_keys)
