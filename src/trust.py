"""Public-key trust model for QR Live Protocol verification."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass(frozen=True)
class TrustedPublicKey:
    """Trusted public signing key for a QRLP issuer."""

    issuer_id: str
    key_id: str
    public_key_pem: bytes
    algorithm: str = "rsa"


class TrustStore:
    """In-memory registry of issuer public keys trusted by this verifier."""

    def __init__(self) -> None:
        self._keys: Dict[str, TrustedPublicKey] = {}

    def add_public_key(
        self,
        issuer_id: str,
        key_id: str,
        public_key_pem: Union[bytes, str],
        algorithm: str = "rsa",
    ) -> TrustedPublicKey:
        """Trust a public key for an issuer/key-id pair."""
        if isinstance(public_key_pem, str):
            public_key_pem = public_key_pem.encode("utf-8")

        trusted_key = TrustedPublicKey(
            issuer_id=issuer_id,
            key_id=key_id,
            public_key_pem=public_key_pem,
            algorithm=algorithm.lower(),
        )
        self._keys[self._lookup_key(issuer_id, key_id)] = trusted_key
        return trusted_key

    def add_public_key_file(
        self,
        issuer_id: str,
        key_id: str,
        public_key_path: Union[str, Path],
        algorithm: str = "rsa",
    ) -> TrustedPublicKey:
        """Load and trust a public key from a PEM file."""
        public_key_pem = Path(public_key_path).read_bytes()
        return self.add_public_key(issuer_id, key_id, public_key_pem, algorithm)

    def to_dict(self) -> Dict[str, List[Dict[str, str]]]:
        """Serialize trusted keys to a portable JSON-compatible shape."""
        return {
            "trusted_keys": [
                {
                    "issuer_id": key.issuer_id,
                    "key_id": key.key_id,
                    "algorithm": key.algorithm,
                    "public_key_pem": key.public_key_pem.decode("utf-8"),
                }
                for key in self.list_public_keys()
            ]
        }

    def to_file(self, path: Union[str, Path]) -> None:
        """Write trusted public keys to a JSON trust-store file."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrustStore":
        """Create a trust store from a JSON-compatible dictionary."""
        trust_store = cls()
        for item in data.get("trusted_keys", []):
            trust_store.add_public_key(
                issuer_id=item["issuer_id"],
                key_id=item["key_id"],
                public_key_pem=item["public_key_pem"],
                algorithm=item.get("algorithm", "rsa"),
            )
        return trust_store

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "TrustStore":
        """Load trusted public keys from a JSON trust-store file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Trust store must be a JSON object")
        return cls.from_dict(data)

    def get_public_key(self, issuer_id: Optional[str], key_id: Optional[str]) -> Optional[TrustedPublicKey]:
        """Return trusted public key metadata if this issuer/key-id is trusted."""
        if not issuer_id or not key_id:
            return None
        return self._keys.get(self._lookup_key(issuer_id, key_id))

    def is_trusted(self, issuer_id: Optional[str], key_id: Optional[str]) -> bool:
        """Return whether the issuer/key-id pair has trusted verifier material."""
        return self.get_public_key(issuer_id, key_id) is not None

    def list_public_keys(self) -> List[TrustedPublicKey]:
        """Return trusted public keys in stable order for display or export."""
        return [self._keys[key] for key in sorted(self._keys)]

    def __len__(self) -> int:
        return len(self._keys)

    @staticmethod
    def _lookup_key(issuer_id: str, key_id: str) -> str:
        return f"{issuer_id}:{key_id}"
