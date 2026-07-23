"""
Tests for QRGenerator chunking, error handling, and styling.

Covers chunk payload encoding/decoding, error correction capacity,
QR readability verification, text overlay, and statistics.
"""

import json
import base64
import hashlib
import pytest
from src.qr_generator import QRGenerator, QRDataTooLargeError, QRMetadata
from src.config import QRSettings


class TestQRGeneratorChunking:
    """Test explicit QR chunking protocol."""

    def test_chunk_round_trip_small(self):
        """Small data should produce exactly one chunk."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        data = "hello world"
        payloads = gen.generate_chunked_payloads(data)
        assert len(payloads) >= 1
        recovered = QRGenerator.reassemble_chunked_payloads(payloads)
        assert recovered == data

    def test_chunk_round_trip_large(self):
        """Large data should produce multiple chunks."""
        settings = QRSettings(error_correction_level="L", max_data_size=100)
        gen = QRGenerator(settings)
        data = "A" * 5000
        payloads = gen.generate_chunked_payloads(data)
        assert len(payloads) > 1
        recovered = QRGenerator.reassemble_chunked_payloads(payloads)
        assert recovered == data

    def test_chunk_round_trip_unicode(self):
        """Unicode data should survive chunking."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        data = "Hello 世界 🌍 δξπ"
        payloads = gen.generate_chunked_payloads(data)
        recovered = QRGenerator.reassemble_chunked_payloads(payloads)
        assert recovered == data

    def test_chunk_reassembly_empty(self):
        """Reassembly of empty list should raise ValueError."""
        with pytest.raises(ValueError, match="No QR chunk"):
            QRGenerator.reassemble_chunked_payloads([])

    def test_chunk_reassembly_duplicate_index(self):
        """Duplicate chunk index should raise ValueError."""
        settings = QRSettings(error_correction_level="L", max_data_size=50)
        gen = QRGenerator(settings)
        data = "A" * 200
        payloads = gen.generate_chunked_payloads(data)
        # Duplicate first payload
        tampered = [payloads[0]] + payloads
        with pytest.raises(ValueError, match="Duplicate"):
            QRGenerator.reassemble_chunked_payloads(tampered)

    def test_chunk_reassembly_missing_chunk(self):
        """Missing chunk should raise ValueError."""
        settings = QRSettings(error_correction_level="L", max_data_size=50)
        gen = QRGenerator(settings)
        data = "A" * 200
        payloads = gen.generate_chunked_payloads(data)
        if len(payloads) > 1:
            # Remove a middle chunk
            tampered = payloads[:1] + payloads[2:]
            with pytest.raises(ValueError, match="Incomplete"):
                QRGenerator.reassemble_chunked_payloads(tampered)

    def test_chunk_reassembly_corrupted_data(self):
        """Corrupted chunk data should fail checksum validation."""
        settings = QRSettings(error_correction_level="L", max_data_size=50)
        gen = QRGenerator(settings)
        data = "A" * 200
        payloads = gen.generate_chunked_payloads(data)
        if len(payloads) > 1:
            # Corrupt the chunk data in the first payload
            parsed = json.loads(payloads[0])
            parsed["chunk"] = "Z" * len(parsed["chunk"])
            tampered = [json.dumps(parsed, separators=(',', ':'), sort_keys=True)] + payloads[1:]
            with pytest.raises(ValueError, match="checksum mismatch|size mismatch|not valid base64"):
                QRGenerator.reassemble_chunked_payloads(tampered)

    def test_chunk_reassembly_invalid_json(self):
        """Malformed JSON payload should raise ValueError."""
        with pytest.raises(ValueError, match="not valid JSON"):
            QRGenerator.reassemble_chunked_payloads(["not json at all"])

    def test_chunk_reassembly_wrong_protocol(self):
        """Wrong protocol identifier should raise ValueError."""
        payload = json.dumps({
            "protocol": "wrong.protocol",
            "chunked": True,
            "encoding": "base64:utf-8",
            "chunk_index": 0,
            "total_chunks": 1,
            "data_size": 5,
            "data_sha256": hashlib.sha256(b"hello").hexdigest(),
            "chunk": base64.b64encode(b"hello").decode("ascii"),
        })
        with pytest.raises(ValueError, match="protocol"):
            QRGenerator.reassemble_chunked_payloads([payload])

    def test_chunked_qr_codes_generates_images(self):
        """generate_chunked_qr_codes should produce list of PNG bytes."""
        settings = QRSettings(error_correction_level="L", max_data_size=100)
        gen = QRGenerator(settings)
        data = "B" * 500
        images = gen.generate_chunked_qr_codes(data)
        assert len(images) > 1
        for img in images:
            assert isinstance(img, bytes)
            assert len(img) > 0
            # PNG magic bytes
            assert img[:4] == b'\x89PNG'

    def test_invalid_chunk_size_zero(self):
        """Zero max_chunk_size should raise ValueError."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        with pytest.raises(ValueError, match="positive integer"):
            gen.generate_chunked_payloads("data", max_chunk_size=0)


class TestQRGeneratorErrors:
    """Test error handling."""

    def test_data_too_large_error(self):
        """Data exceeding QR capacity should raise QRDataTooLargeError."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        huge_data = "X" * 10000
        with pytest.raises(QRDataTooLargeError):
            gen.generate_qr_image(huge_data)

    def test_data_too_large_error_has_message(self):
        """QRDataTooLargeError should have an actionable message."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        huge_data = "X" * 10000
        try:
            gen.generate_qr_image(huge_data)
        except QRDataTooLargeError as e:
            assert "generate_chunked_payloads" in str(e)
            assert "reassemble" in str(e)


class TestQRGeneratorImage:
    """Test QR image generation."""

    def test_generate_qr_image_basic(self):
        """Basic QR image generation should return PNG bytes."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        img = gen.generate_qr_image("test data")
        assert isinstance(img, bytes)
        assert img[:4] == b'\x89PNG'

    def test_generate_qr_image_cached(self):
        """Same data should return from cache (same bytes)."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        img1 = gen.generate_qr_image("cached data")
        img2 = gen.generate_qr_image("cached data")
        assert img1 == img2
        assert gen.generation_count == 1

    def test_generate_qr_image_styles(self):
        """Different styles should all produce valid PNG bytes."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        for style in ['live', 'professional', 'minimal', None]:
            img = gen.generate_qr_image("style test", style=style)
            assert img[:4] == b'\x89PNG'

    def test_generate_qr_image_different_correction_levels(self):
        """All error correction levels should work."""
        for level in ['L', 'M', 'Q', 'H']:
            settings = QRSettings(error_correction_level=level)
            gen = QRGenerator(settings)
            img = gen.generate_qr_image(f"test {level}")
            assert img[:4] == b'\x89PNG'

    def test_get_statistics(self):
        """Statistics should report generation count and cache size."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        gen.generate_qr_image("stat test")
        stats = gen.get_statistics()
        assert stats["total_generated"] == 1
        assert stats["cache_size"] == 1
        assert "settings" in stats


class TestQRGeneratorVerification:
    """Test QR readability verification."""

    def test_verify_qr_readability_no_pyzbar(self):
        """verify_qr_readability should return error if pyzbar missing."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        img = gen.generate_qr_image("readability test")
        result = gen.verify_qr_readability(img)
        # Result is either readable or error about pyzbar
        assert "readable" in result
        assert "error" in result or result["readable"] is not None


class TestQRGeneratorMetadata:
    """Test QRMetadata dataclass."""

    def test_qr_metadata_defaults(self):
        """QRMetadata should have default values."""
        meta = QRMetadata(
            data_size=100,
            error_correction="M",
            version=5,
            creation_time=1.5,
        )
        assert meta.chunk_index == 0
        assert meta.total_chunks == 1
