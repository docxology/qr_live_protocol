# QRLP cryptography

QRLP applies three layers to a generated payload in order. A digital signature lets a verifier check the payload using a trusted public key. A mandatory HMAC lets verifiers with the matching secret authenticate it locally. Optional AES-GCM encrypts sensitive fields before the payload is rendered.

## Sign and verify across instances

```python
from src import KeyManager, QRLiveProtocol, TrustStore

issuer_keys = KeyManager("./issuer-keys")
issuer = QRLiveProtocol(key_manager=issuer_keys, issuer_id="studio")
data, image = issuer.generate_signed_qr({"segment": "opening"})
public_pem = issuer_keys.export_public_key(data.signing_key_id)

trust = TrustStore()
trust.add_public_key("studio", data.signing_key_id, public_pem, data.signature_algorithm)
verifier = QRLiveProtocol(key_manager=KeyManager("./verifier-keys"), trust_store=trust)

result = verifier.verify_qr_data(data.to_json())
assert result["valid"] and result["trust_mode"] == "public_signature"
```

Distribute the PEM and issuer/key-ID mapping through a trusted channel. A verifier selects a public key by that pair or by its own local key store. Signature verification needs only public key material. QRLP supports RSA-PSS and ECDSA. A new automatic signing key uses RSA-2048 by default or P-256 when configured for ECDSA.

The signature covers compact, key-sorted JSON after omitting top-level null values and signature, HMAC, and encryption envelope fields. Verification retains unfamiliar payload fields for this check. The HMAC also covers the embedded signature. Canonicalization preserves the existing wire format.

A standalone verifier usually reports `hmac_verified=False` for an issuer's QR. A trusted public signature can satisfy authenticity on its own. Inspect `valid` for the overall decision, and inspect `trust_mode` to distinguish the verification key or secret used. A local identity hash match is a separate diagnostic.

## Encrypt QR fields

To decrypt across processes, configure the same 32-byte AES key as a 64-character hex string on both sides using `QRLP_ENCRYPTION_KEY` or `security_settings.encryption_key`. Set `encrypt_qr_data` to enable encryption by default, or request it for a single payload. An unconfigured Python instance uses an ephemeral key.

```python
from src import QRLiveProtocol, QRLPConfig

# Supply QRLP_ENCRYPTION_KEY to the issuer and verifier environments.
issuer = QRLiveProtocol(QRLPConfig.from_env())
data, image = issuer.generate_encrypted_qr({"segment": "opening"})
```

`DataEncryptor.generate_data_key()` creates and registers a separate key for callers that want an explicit `encryption_key_id`. Register that ID and key bytes with `DataEncryptor.add_key()` on other verifiers. An unknown explicit ID fails decryption. Retained master keys can decrypt QR payloads made before an in-process rotation.

The wire format stores a Base64-encoded 12-byte nonce, 16-byte GCM tag, and ciphertext per protected field. The field name is bound as associated data. A failed field rejects the whole encrypted payload. A failed encryption request raises before publishing a QR. Encryption protects the fields listed in the envelope. Timestamps, issuer IDs, and other routing metadata remain visible.

## Store and rotate keys

`KeyManager` stores encrypted signing keys under the configured key directory, or `~/.qrlp/keys` by default. Keep that directory private. Without a supplied password, a generated master key is stored beside the encrypted signing keys. With a password, the master key is derived with PBKDF2 using a stored salt.

Use `rotate_signing_key()` to create a replacement and move the old encrypted signing key to an archive. Retain the old public key in verifiers' trust stores if they must verify payloads signed before the rotation. The verifier's timestamp and replay policy still applies. The legacy `backup_keys()` method writes an owner-only JSON export with Base64-encoded private PEM. Treat this export as private key material.

Run the focused regression suite from the checkout:

```sh
uv run --locked pytest --no-cov tests/test_crypto tests/test_core/test_wire_security.py
```
