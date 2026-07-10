"""Integration tests for QRLP CLI trust and key workflows."""

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import cli


def _write_config(path: Path, key_dir: str, issuer_id: str = "issuer-cli") -> None:
    path.write_text(
        json.dumps(
            {
                "blockchain_settings": {"enabled_chains": []},
                "time_settings": {"time_servers": []},
                "security_settings": {
                    "key_dir": key_dir,
                    "issuer_id": issuer_id,
                },
                "web_settings": {"auto_open_browser": False},
            }
        ),
        encoding="utf-8",
    )


def test_cli_generate_exports_trust_store_and_external_verify():
    """Signed QR generation should produce verifier-ready public trust material."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        issuer_config = Path("issuer.json")
        verifier_config = Path("verifier.json")
        _write_config(issuer_config, "issuer_keys")
        _write_config(verifier_config, "verifier_keys")

        generate_result = runner.invoke(
            cli,
            [
                "--config",
                str(issuer_config),
                "generate",
                "--output",
                "qr",
                "--format",
                "json",
                "--user-data",
                '{"event":"cli"}',
                "--sign",
                "--public-key-output",
                "issuer.pem",
                "--trust-record-output",
                "trust.json",
            ],
        )

        assert generate_result.exit_code == 0, generate_result.output
        assert Path("qr.json").exists()
        assert Path("issuer.pem").exists()
        assert Path("trust.json").exists()

        qr_json = Path("qr.json").read_text(encoding="utf-8")
        verify_result = runner.invoke(
            cli,
            [
                "--config",
                str(verifier_config),
                "verify",
                "--file",
                "qr.json",
                "--trust-store",
                "trust.json",
                "--json-output",
            ],
        )

        assert verify_result.exit_code == 0, verify_result.output
        verification = json.loads(verify_result.output)
        assert verification["valid"] is True
        assert verification["signature_verified"] is True
        assert verification["hmac_verified"] is False
        assert verification["trust_mode"] == "public_signature"


def test_cli_verify_without_trust_rejects_external_qr():
    """A verifier without local key or trust-store material must reject authenticity."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        issuer_config = Path("issuer.json")
        verifier_config = Path("verifier.json")
        _write_config(issuer_config, "issuer_keys")
        _write_config(verifier_config, "verifier_keys")

        generate_result = runner.invoke(
            cli,
            [
                "--config",
                str(issuer_config),
                "generate",
                "--output",
                "qr",
                "--format",
                "json",
                "--user-data",
                '{"event":"cli"}',
                "--sign",
            ],
        )
        assert generate_result.exit_code == 0, generate_result.output

        qr_json = Path("qr.json").read_text(encoding="utf-8")
        verify_result = runner.invoke(
            cli,
            [
                "--config",
                str(verifier_config),
                "verify",
                qr_json,
                "--json-output",
            ],
        )

        assert verify_result.exit_code == 0, verify_result.output
        verification = json.loads(verify_result.output)
        assert verification["valid"] is False
        assert verification["signature_verified"] is False
        assert verification["hmac_verified"] is False


def test_cli_keys_and_trust_commands_round_trip():
    """Key export plus trust add/list should create a usable trust-store record."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        config = Path("config.json")
        _write_config(config, "keys")

        generate_result = runner.invoke(
            cli,
            [
                "--config",
                str(config),
                "keys",
                "generate",
                "--public-key-output",
                "public.pem",
            ],
        )
        assert generate_result.exit_code == 0, generate_result.output
        key_id = generate_result.output.split("Generated key: ", 1)[1].splitlines()[0]

        list_result = runner.invoke(cli, ["--config", str(config), "keys", "list"])
        assert list_result.exit_code == 0, list_result.output
        assert key_id in list_result.output

        trust_add_result = runner.invoke(
            cli,
            [
                "trust",
                "add",
                "--issuer",
                "issuer-cli",
                "--key-id",
                key_id,
                "--public-key",
                "public.pem",
                "--store",
                "trust.json",
            ],
        )
        assert trust_add_result.exit_code == 0, trust_add_result.output

        trust_list_result = runner.invoke(cli, ["trust", "list", "trust.json"])
        assert trust_list_result.exit_code == 0, trust_list_result.output
        assert "issuer-cli" in trust_list_result.output
        assert key_id in trust_list_result.output
