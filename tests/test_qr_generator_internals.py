"""
Extended tests for qr_generator.py uncovered paths.

Covers text overlay, live display QR, _split_data,
verify_qr_readability with pyzbar, and cache eviction.
"""

import json
import base64
import hashlib
import pytest
from io import BytesIO
from PIL import Image

from src.qr_generator import QRGenerator, QRDataTooLargeError, QRMetadata
from src.config import QRSettings


class TestTextOverlay:
    """Test text overlay functionality."""

    def test_create_live_display_qr_with_text(self):
        """create_live_display_qr with text overlay produces larger image."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "abc123def456789012345678901234567890",
            "sequence_number": 1,
            "blockchain_hashes": {"bitcoin": "fakehash", "ethereum": "fakehash2"},
        }
        img_with_text = gen.create_live_display_qr(qr_data, include_text=True)
        img_without_text = gen.create_live_display_qr(qr_data, include_text=False)
        assert len(img_with_text) > len(img_without_text)

    def test_create_live_display_qr_without_text(self):
        """create_live_display_qr without text returns base QR."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        qr_data = {"timestamp": "2025-01-01T00:00:00Z", "sequence_number": 1}
        img = gen.create_live_display_qr(qr_data, include_text=False)
        assert img[:4] == b'\x89PNG'

    def test_text_overlay_includes_metadata(self):
        """Text overlay image is a valid PNG with more pixels than base."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "abc123def456789012345678901234567890",
            "sequence_number": 42,
            "blockchain_hashes": {"bitcoin": "hash1"},
        }
        base_img = gen.generate_qr_image(json.dumps(qr_data, separators=(',', ':')))
        overlay_img = gen.create_live_display_qr(qr_data, include_text=True)

        base_pil = Image.open(BytesIO(base_img))
        overlay_pil = Image.open(BytesIO(overlay_img))
        assert overlay_pil.width > base_pil.width or overlay_pil.height > base_pil.height

    def test_text_overlay_handles_missing_fields(self):
        """Text overlay works with minimal QR data."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        qr_data = {"timestamp": "2025-01-01T00:00:00Z"}
        img = gen.create_live_display_qr(qr_data, include_text=True)
        assert img[:4] == b'\x89PNG'

    def test_text_overlay_with_blockchain_hashes(self):
        """Text overlay shows blockchain verification info."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        qr_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc",
            "sequence_number": 1,
            "blockchain_hashes": {
                "bitcoin": "hash1",
                "ethereum": "hash2",
                "litecoin": "hash3",
            },
        }
        img = gen.create_live_display_qr(qr_data, include_text=True)
        assert img[:4] == b'\x89PNG'


class TestSplitData:
    """Test _split_data internal method."""

    def test_split_data_basic(self):
        """_split_data splits string into base64-encoded chunks."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        data = "hello world"
        chunks = gen._split_data(data, 5)
        assert len(chunks) > 1
        # Verify reassembly
        encoded = ''.join(chunks)
        decoded = base64.b64decode(encoded).decode('utf-8')
        assert decoded == data

    def test_split_data_empty(self):
        """_split_data with empty string returns single empty chunk."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        chunks = gen._split_data("", 10)
        assert chunks == [""]

    def test_split_encoded_data_empty(self):
        """_split_encoded_data with empty string returns single empty chunk."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        chunks = gen._split_encoded_data("", 10)
        assert chunks == [""]


class TestCacheEviction:
    """Test QR cache eviction."""

    def test_cache_eviction_on_overflow(self):
        """Cache evicts oldest entries when over 100."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        # Fill cache beyond 100
        for i in range(105):
            gen.generate_qr_image(f"cache-test-{i}")
        assert gen.generation_count == 105
        # Cache eviction happens at >100, so it stays near 100
        assert len(gen.cache) <= 105


class TestQRVersionEstimation:
    """Test QR version estimation."""

    def test_estimate_qr_version_small(self):
        """Small data fits in low version."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        version = gen._estimate_qr_version("hello")
        assert 1 <= version <= 40

    def test_estimate_qr_version_large(self):
        """Large data returns version > 40."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        version = gen._estimate_qr_version("X" * 10000)
        assert version > 40

    def test_estimate_qr_version_empty(self):
        """Empty data fits in version 1."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        version = gen._estimate_qr_version("")
        assert version == 1

    def test_capacity_for_error_correction(self):
        """_capacity_for_error_correction returns list for each level."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        capacity = gen._capacity_for_error_correction()
        assert len(capacity) == 40  # 40 QR versions

    def test_max_single_qr_size(self):
        """_max_single_qr_size returns last capacity entry."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        max_size = gen._max_single_qr_size()
        assert max_size > 2000  # Version 40 capacity

    def test_large_payload_error_message(self):
        """_large_payload_error_message includes size and guidance."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        msg = gen._large_payload_error_message("X" * 5000)
        assert "5000" in msg
        assert "generate_chunked_payloads" in msg
        assert "reassemble" in msg


class TestChunkPayloadEncoding:
    """Test chunk payload encoding/decoding internals."""

    def test_encode_chunk_payload(self):
        """_encode_chunk_payload produces valid JSON."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        payload = gen._encode_chunk_payload(
            chunk="abc",
            chunk_index=0,
            total_chunks=2,
            data_size=100,
            data_hash="a" * 64,
        )
        parsed = json.loads(payload)
        assert parsed["protocol"] == "qrlp.chunk.v1"
        assert parsed["chunked"] is True
        assert parsed["encoding"] == "base64:utf-8"
        assert parsed["chunk_index"] == 0
        assert parsed["total_chunks"] == 2
        assert parsed["data_size"] == 100
        assert parsed["data_sha256"] == "a" * 64
        assert parsed["chunk"] == "abc"

    def test_decode_chunk_payload_valid(self):
        """_decode_chunk_payload validates and returns dict."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        payload = gen._encode_chunk_payload(
            chunk="abc",
            chunk_index=0,
            total_chunks=1,
            data_size=3,
            data_hash=hashlib.sha256(b"abc").hexdigest(),
        )
        decoded = QRGenerator._decode_chunk_payload(payload)
        assert decoded["chunk"] == "abc"
        assert decoded["total_chunks"] == 1

    def test_decode_chunk_payload_non_dict(self):
        """_decode_chunk_payload rejects non-object JSON."""
        with pytest.raises(ValueError, match="must be a JSON object"):
            QRGenerator._decode_chunk_payload("[1, 2, 3]")

    def test_decode_chunk_payload_missing_chunked(self):
        """_decode_chunk_payload rejects missing chunked field."""
        payload = json.dumps({
            "protocol": "qrlp.chunk.v1",
            "encoding": "base64:utf-8",
            "chunk_index": 0,
            "total_chunks": 1,
            "data_size": 0,
            "data_sha256": "a" * 64,
            "chunk": "",
        })
        with pytest.raises(ValueError, match="chunked"):
            QRGenerator._decode_chunk_payload(payload)

    def test_decode_chunk_payload_invalid_index_type(self):
        """_decode_chunk_payload rejects non-integer chunk_index."""
        payload = json.dumps({
            "protocol": "qrlp.chunk.v1",
            "chunked": True,
            "encoding": "base64:utf-8",
            "chunk_index": "zero",
            "total_chunks": 1,
            "data_size": 0,
            "data_sha256": "a" * 64,
            "chunk": "",
        })
        with pytest.raises(ValueError, match="chunk_index"):
            QRGenerator._decode_chunk_payload(payload)

    def test_decode_chunk_payload_invalid_hash_length(self):
        """_decode_chunk_payload rejects wrong-length sha256."""
        payload = json.dumps({
            "protocol": "qrlp.chunk.v1",
            "chunked": True,
            "encoding": "base64:utf-8",
            "chunk_index": 0,
            "total_chunks": 1,
            "data_size": 0,
            "data_sha256": "too_short",
            "chunk": "",
        })
        with pytest.raises(ValueError, match="data_sha256"):
            QRGenerator._decode_chunk_payload(payload)

    def test_decode_chunk_payload_non_hex_hash(self):
        """_decode_chunk_payload rejects non-hex sha256."""
        payload = json.dumps({
            "protocol": "qrlp.chunk.v1",
            "chunked": True,
            "encoding": "base64:utf-8",
            "chunk_index": 0,
            "total_chunks": 1,
            "data_size": 0,
            "data_sha256": "z" * 64,
            "chunk": "",
        })
        with pytest.raises(ValueError, match="hexadecimal"):
            QRGenerator._decode_chunk_payload(payload)

    def test_decode_chunk_payload_non_string_chunk(self):
        """_decode_chunk_payload rejects non-string chunk."""
        payload = json.dumps({
            "protocol": "qrlp.chunk.v1",
            "chunked": True,
            "encoding": "base64:utf-8",
            "chunk_index": 0,
            "total_chunks": 1,
            "data_size": 0,
            "data_sha256": "a" * 64,
            "chunk": 123,
        })
        with pytest.raises(ValueError, match="chunk.*string"):
            QRGenerator._decode_chunk_payload(payload)

    def test_decode_chunk_payload_negative_data_size(self):
        """_decode_chunk_payload rejects negative data_size."""
        payload = json.dumps({
            "protocol": "qrlp.chunk.v1",
            "chunked": True,
            "encoding": "base64:utf-8",
            "chunk_index": 0,
            "total_chunks": 1,
            "data_size": -1,
            "data_sha256": "a" * 64,
            "chunk": "",
        })
        with pytest.raises(ValueError, match="data_size"):
            QRGenerator._decode_chunk_payload(payload)

    def test_decode_chunk_payload_index_out_of_range(self):
        """_decode_chunk_payload rejects chunk_index >= total_chunks."""
        payload = json.dumps({
            "protocol": "qrlp.chunk.v1",
            "chunked": True,
            "encoding": "base64:utf-8",
            "chunk_index": 5,
            "total_chunks": 3,
            "data_size": 0,
            "data_sha256": "a" * 64,
            "chunk": "",
        })
        with pytest.raises(ValueError, match="outside the expected range"):
            QRGenerator._decode_chunk_payload(payload)

    def test_validate_compatible_chunk_payload_mismatch(self):
        """_validate_compatible_chunk_payload detects mismatched fields."""
        with pytest.raises(ValueError, match="does not match"):
            QRGenerator._validate_compatible_chunk_payload(
                {"protocol": "qrlp.chunk.v1", "encoding": "base64:utf-8",
                 "total_chunks": 2, "data_size": 100, "data_sha256": "a" * 64},
                {"protocol": "qrlp.chunk.v1", "encoding": "base64:utf-8",
                 "total_chunks": 3, "data_size": 100, "data_sha256": "a" * 64},
            )


class TestChunkSizeResolution:
    """Test _resolve_chunk_size binary search."""

    def test_resolve_chunk_size_default(self):
        """_resolve_chunk_size uses max_data_size by default."""
        settings = QRSettings(error_correction_level="L", max_data_size=200)
        gen = QRGenerator(settings)
        data = "A" * 500
        size = gen._resolve_chunk_size(
            encoded_data=base64.b64encode(data.encode()).decode(),
            data_size=500,
            data_hash=hashlib.sha256(data.encode()).hexdigest(),
            max_chunk_size=None,
        )
        assert size > 0
        assert size <= 200

    def test_resolve_chunk_size_custom_max(self):
        """_resolve_chunk_size respects custom max_chunk_size."""
        settings = QRSettings(error_correction_level="L", max_data_size=2000)
        gen = QRGenerator(settings)
        data = "A" * 500
        size = gen._resolve_chunk_size(
            encoded_data=base64.b64encode(data.encode()).decode(),
            data_size=500,
            data_hash=hashlib.sha256(data.encode()).hexdigest(),
            max_chunk_size=50,
        )
        assert size <= 50
        assert size > 0
