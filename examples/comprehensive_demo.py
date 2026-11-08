#!/usr/bin/env python3
"""Generate, independently verify, and save a signed QR without external services."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import QRLPConfig, QRLiveProtocol, TrustStore


def offline_config(key_dir: Path) -> QRLPConfig:
    config = QRLPConfig()
    config.time_settings.time_servers = []
    config.blockchain_settings.enabled_chains.clear()
    config.qr_settings.error_correction_level = "L"
    config.security_settings.key_dir = str(key_dir)
    config.security_settings.signature_algorithm = "ecdsa"
    return config


def run_demo(output: Path) -> None:
    """Save public artifacts and use separate temporary issuer and verifier stores."""
    with TemporaryDirectory(prefix="qrlp-demo-keys-") as temp:
        keys = Path(temp)
        producer_config = offline_config(keys / "issuer")
        producer_config.security_settings.issuer_id = "studio.example"
        receiver_config = offline_config(keys / "verifier")
        shared_key = secrets.token_hex(32)
        producer_config.security_settings.encryption_key = shared_key
        receiver_config.security_settings.encryption_key = shared_key

        producer = QRLiveProtocol(producer_config)
        local, _ = producer.generate_single_qr({"message": "Local integrity check"})
        if not producer.verify_qr_data(local.to_json())["hmac_verified"]:
            raise RuntimeError("Local HMAC check failed")

        payload, png = producer.generate_signed_qr({"title": "Episode 1"})
        public_key = producer.key_manager.export_public_key(payload.signing_key_id)
        if public_key is None:
            raise RuntimeError("Signed QR did not export a public key")
        trust = TrustStore()
        trust.add_public_key(payload.issuer_id, payload.signing_key_id, public_key, payload.signature_algorithm)
        receiver = QRLiveProtocol(receiver_config, trust_store=trust)

        wire = payload.to_json()
        result = receiver.verify_qr_data(wire)
        if not result["valid"] or result["trust_mode"] != "public_signature":
            raise RuntimeError(f"External verification failed: {result}")

        changed = json.loads(wire)
        changed["user_data"]["title"] = "Changed title"
        if receiver.verify_qr_data(json.dumps(changed))["valid"]:
            raise RuntimeError("Modified payload was accepted")

        encrypted, _ = producer.generate_encrypted_qr({"message": "Example protected field"})
        result = receiver.verify_qr_data(encrypted.to_json())
        if not result["valid"] or not result["encrypted"]:
            raise RuntimeError(f"Encrypted payload verification failed: {result}")

        (output / "release.png").write_bytes(png)
        (output / "release.json").write_bytes(wire.encode("utf-8"))
        trust.to_file(output / "trust.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory for public artifacts (default: temporary directory)")
    args = parser.parse_args()
    output = args.output or Path(mkdtemp(prefix="qrlp-demo-"))
    if args.output:
        output.mkdir(parents=True, exist_ok=False)
    run_demo(output)
    print(f"Local HMAC, independent signature, tamper rejection, and decryption passed. Artifacts: {output}")


if __name__ == "__main__":
    main()
