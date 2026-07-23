"""
QR Serializer — centralized JSON serialization for QRLP.

Provides consistent canonical JSON serialization across all modules,
eliminating duplicated serialization logic in core.py, signer.py,
hmac.py, encryptor.py, and qr_generator.py.
"""

import json
from typing import Any, Dict


class QRSerializer:
    """Centralized JSON serialization for QR data payloads.

    All QRLP modules should use these methods instead of calling
    ``json.dumps`` directly, ensuring consistent key ordering,
    separator handling, and None-value filtering.
    """

    # Standard separators for compact JSON (no spaces)
    SEPARATORS = (',', ':')

    @staticmethod
    def serialize(data: Any, filter_none: bool = True, sort_keys: bool = False) -> str:
        """Serialize data to canonical JSON string.

        Args:
            data: Data to serialize (dict, list, or primitive)
            filter_none: If True, remove None values from dicts
            sort_keys: If True, sort keys alphabetically (for HMAC/signature canonicalization)

        Returns:
            Compact JSON string
        """
        if filter_none and isinstance(data, dict):
            data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, separators=QRSerializer.SEPARATORS, sort_keys=sort_keys)

    @staticmethod
    def serialize_for_signature(data: Any) -> str:
        """Serialize data for signature/HMAC canonicalization.

        Uses sort_keys=True and filter_none=True for deterministic output.
        """
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, separators=QRSerializer.SEPARATORS, sort_keys=True)

    @staticmethod
    def deserialize(json_str: str) -> Any:
        """Deserialize a JSON string.

        Args:
            json_str: JSON string to parse

        Returns:
            Parsed data (dict, list, or primitive)
        """
        return json.loads(json_str)

    @staticmethod
    def serialize_to_dict(data: Any, filter_none: bool = True) -> Dict[str, Any]:
        """Convert data to a clean dictionary, optionally filtering None values.

        Args:
            data: Data to convert (must be dict or have __dict__)
            filter_none: If True, remove None values

        Returns:
            Dictionary representation
        """
        if hasattr(data, '__dict__'):
            result = dict(data.__dict__)
        elif isinstance(data, dict):
            result = dict(data)
        else:
            result = {"value": data}

        if filter_none:
            result = {k: v for k, v in result.items() if v is not None}
        return result
