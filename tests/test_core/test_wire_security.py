"""End-to-end regressions for encrypted and authenticated wire payloads."""

import json
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest

from src.core import QRLiveProtocol
from src.crypto import EncryptionError, KeyManager


def test_invalid_payload_cannot_consume_authenticated_nonce(qrlp_instance):
    qrlp_instance.config.verification_settings.enable_replay_protection = True
    qr_data, _ = qrlp_instance.generate_single_qr({"event": "opening"}, sign_data=True)
    altered = qr_data.to_dict()
    altered["user_data"] = {"event": "forged"}

    rejected = qrlp_instance.verify_qr_data(json.dumps(altered))
    assert rejected["valid"] is False
    assert rejected["replayed"] is False
    assert qrlp_instance.verify_qr_data(qr_data.to_json())["valid"] is True
    assert qrlp_instance.verify_qr_data(qr_data.to_json())["replayed"] is True


def test_replay_policy_rejects_authentic_legacy_payload_without_nonce(qrlp_instance):
    qr_data, _ = qrlp_instance.generate_single_qr(sign_data=False)
    payload = {name: value for name, value in qr_data.to_dict().items() if not name.startswith("_")}
    payload.pop("nonce")
    wire = json.dumps(qrlp_instance.hmac_manager.create_integrity_checked_qr(payload))
    assert qrlp_instance.verify_qr_data(wire)["valid"] is True
    qrlp_instance.config.verification_settings.enable_replay_protection = True
    result = qrlp_instance.verify_qr_data(wire)
    assert result["hmac_verified"] is True
    assert result["valid"] is False
    assert result["replayed"] is False
    assert result["error"] == "Replay protection requires a nonce"


def test_replay_policy_rejects_authentic_payload_with_invalid_window(qrlp_instance):
    settings = qrlp_instance.config.verification_settings
    settings.enable_replay_protection = True
    settings.replay_window_seconds = 0
    qr_data, _ = qrlp_instance.generate_single_qr()
    result = qrlp_instance.verify_qr_data(qr_data.to_json())
    assert result["hmac_verified"] is True
    assert result["valid"] is False
    assert result["error"] == "Replay protection requires a positive integer window"


@pytest.mark.parametrize("prefix", [
    '"timestamp":null,',
    '"new_field":{"nested":1,"nested":2},',
    '"new_field":1e309,',
])
def test_ambiguous_wire_is_rejected(qrlp_instance, prefix):
    qr_data, _ = qrlp_instance.generate_single_qr()
    wire = "{" + prefix + qr_data.to_json()[1:]
    result = qrlp_instance.verify_qr_data(wire)
    assert result["valid_json"] is False
    assert result["valid"] is False


@pytest.mark.parametrize(("field", "value"), [
    ("timestamp", 123),
    ("identity_hash", []),
    ("blockchain_hashes", "malformed"),
    ("time_server_verification", True),
])
def test_malformed_verification_fields_are_rejected(qrlp_instance, field, value):
    qr_data, _ = qrlp_instance.generate_single_qr()
    payload = qr_data.to_dict()
    payload[field] = value
    result = qrlp_instance.verify_qr_data(json.dumps(payload))
    assert result["valid_json"] is False
    assert result["valid"] is False


def test_configured_encryption_and_explicit_data_key_round_trip(qrlp_instance):
    qrlp_instance.config.security_settings.encrypt_qr_data = True
    key = qrlp_instance.encryptor.generate_data_key()
    qr_data, _ = qrlp_instance.generate_single_qr(
        {"secret": "opening"}, encryption_key_id=key.key_id,
    )
    assert qr_data._data_key_id == key.key_id
    assert "opening" not in qr_data.to_json()
    result = qrlp_instance.verify_qr_data(qr_data.to_json())
    assert result["encrypted"] is True
    assert result["valid"] is True
    assert result["trust_mode"] == "local_hmac"


def test_encryption_failure_emits_no_plaintext_qr(qrlp_instance, monkeypatch):
    render = Mock()
    monkeypatch.setattr(qrlp_instance.qr_generator, "generate_qr_image", render)
    with pytest.raises(EncryptionError, match="key not found"):
        qrlp_instance.generate_encrypted_qr({"secret": "opening"}, encryption_key_id="unknown")
    render.assert_not_called()
    assert qrlp_instance.get_current_qr_data() is None


def test_configured_encryption_round_trips_across_instances(test_config, tmp_path):
    test_config.security_settings.encryption_key = "a1" * 32
    issuer = QRLiveProtocol(test_config, key_manager=KeyManager(str(tmp_path / "issuer")))
    verifier = QRLiveProtocol(test_config, key_manager=KeyManager(str(tmp_path / "verifier")))
    qr_data, _ = issuer.generate_encrypted_qr({"secret": "opening"})
    verifier.trust_store.add_public_key(
        qr_data.issuer_id, qr_data.signing_key_id,
        issuer.key_manager.export_public_key(qr_data.signing_key_id),
        qr_data.signature_algorithm,
    )

    assert "opening" not in qr_data.to_json()
    result = verifier.verify_qr_data(qr_data.to_json())
    assert result["encrypted"] is True
    assert result["valid"] is True
    assert result["trust_mode"] == "public_signature"
    assert result["hmac_verified"] is False


def test_damaged_encrypted_field_rejects_whole_payload(qrlp_instance):
    qr_data, _ = qrlp_instance.generate_encrypted_qr({"secret": "opening"})
    altered = qr_data.to_dict()
    altered["user_data"] = "invalid-base64"
    result = qrlp_instance.verify_qr_data(json.dumps(altered))
    assert result["encrypted"] is True
    assert result["replayed"] is False
    assert result["valid_json"] is False
    assert result["valid"] is False


@pytest.mark.parametrize("encrypt_data", [False, True])
def test_legacy_dataclass_exports_allow_null_encryption_fields(qrlp_instance, encrypt_data):
    qr_data, _ = qrlp_instance.generate_single_qr(sign_data=True, encrypt_data=encrypt_data)
    assert qr_data._data_key_id is None
    wire = json.dumps(qr_data.__dict__)
    result = qrlp_instance.verify_qr_data(wire)
    assert result["encrypted"] is encrypt_data
    assert result["hmac_verified"] is True
    assert result["signature_verified"] is True
    assert result["valid"] is True


@pytest.mark.parametrize("marker", [False, [], "", {}])
def test_malformed_non_null_encryption_marker_is_rejected(qrlp_instance, marker):
    qr_data, _ = qrlp_instance.generate_signed_qr()
    payload = qr_data.to_dict()
    payload["_encrypted_fields"] = marker
    result = qrlp_instance.verify_qr_data(json.dumps(payload))
    assert result["encrypted"] is True
    assert result["valid"] is False
    assert result["error"] == "Decryption failed"


def test_wire_bytes_match_renderer_and_timestamp_commitment(qrlp_instance, monkeypatch):
    qrlp_instance.config.time_settings.ots_enabled = True
    render = Mock(return_value=b"rendered")
    stamp = Mock(return_value=Path("proof.ots"))
    monkeypatch.setattr(qrlp_instance.qr_generator, "generate_qr_image", render)
    monkeypatch.setattr(qrlp_instance.time_stamper, "stamp", stamp)

    qr_data, _ = qrlp_instance.generate_single_qr(sign_data=True)
    render.assert_called_once_with(qr_data.to_json())
    stamp.assert_called_once_with(qr_data.to_json().encode("utf-8"))
    assert qr_data.ots_proof_path == "proof.ots"
    assert "ots_proof_path" not in json.loads(qr_data.to_json())
    assert qrlp_instance.verify_qr_data(qr_data.to_json())["valid"] is True


def test_configured_ecdsa_generates_and_verifies(qrlp_instance):
    qrlp_instance.config.security_settings.signature_algorithm = "ecdsa"
    qr_data, _ = qrlp_instance.generate_signed_qr()
    assert qr_data.signature_algorithm == "ecdsa"
    assert qrlp_instance.verify_qr_data(qr_data.to_json())["signature_verified"] is True


def test_local_signature_verification_reads_only_public_key(qrlp_instance, monkeypatch):
    qr_data, _ = qrlp_instance.generate_signed_qr()
    read_private = Mock(side_effect=AssertionError("private key accessed during verification"))
    monkeypatch.setattr(qrlp_instance.key_manager, "get_keypair", read_private)
    assert qrlp_instance.verify_qr_data(qr_data.to_json())["trust_mode"] == "local_signature"
    read_private.assert_not_called()


def test_empty_trusted_pem_does_not_fall_back_to_local_signer(qrlp_instance):
    qr_data, _ = qrlp_instance.generate_signed_qr()
    qrlp_instance.trust_store.add_public_key(qr_data.issuer_id, qr_data.signing_key_id, b"")
    result = qrlp_instance.verify_qr_data(qr_data.to_json())
    assert result["signature_verified"] is False
    assert result["trust_mode"] == "local_hmac"


def test_generation_callback_can_stop_its_worker(qrlp_instance):
    stopped = Event()

    def stop_from_callback(*_):
        qrlp_instance.stop_live_generation()
        stopped.set()

    qrlp_instance.add_update_callback(stop_from_callback)
    qrlp_instance.start_live_generation()
    try:
        assert stopped.wait(2.0)
    finally:
        qrlp_instance.stop_live_generation()
    assert qrlp_instance.get_statistics()["running"] is False
