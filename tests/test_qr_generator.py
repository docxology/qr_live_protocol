"""
Focused tests for QR generator payload sizing and chunk recovery.
"""

import json
from io import BytesIO

import pytest
from PIL import Image

from src.config import QRSettings
from src.qr_generator import QRDataTooLargeError, QRGenerator


def make_generator() -> QRGenerator:
    """Create a small, fast QR generator for focused behavior tests."""
    return QRGenerator(QRSettings(error_correction_level="L", box_size=2))


def assert_png_image(image_bytes: bytes) -> None:
    """Assert bytes contain a valid PNG image."""
    assert image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(image_bytes)) as image:
        image.verify()


def test_generate_qr_image_returns_png_for_single_payload() -> None:
    generator = make_generator()

    image_bytes = generator.generate_qr_image('{"status":"ok"}')

    assert_png_image(image_bytes)
    assert generator.generation_count == 1


def test_generate_qr_image_rejects_oversized_payload_instead_of_metadata_qr() -> None:
    generator = make_generator()
    oversized_payload = "x" * (generator._max_single_qr_size() + 1)

    with pytest.raises(QRDataTooLargeError, match="generate_chunked_payloads"):
        generator.generate_qr_image(oversized_payload)

    assert generator.generation_count == 0


def test_chunked_payloads_reassemble_original_payload_and_generate_images() -> None:
    generator = make_generator()
    original_payload = ("chunk-me-" * 450) + "\\u2603"

    chunk_payloads = generator.generate_chunked_payloads(original_payload)
    decoded_payloads = [json.loads(payload) for payload in chunk_payloads]
    chunk_images = generator.generate_chunked_qr_codes(original_payload)

    assert len(chunk_payloads) > 1
    assert len(chunk_images) == len(chunk_payloads)
    assert QRGenerator.reassemble_chunked_payloads(list(reversed(chunk_payloads))) == original_payload
    assert [payload["chunk_index"] for payload in decoded_payloads] == list(range(len(chunk_payloads)))
    assert {payload["total_chunks"] for payload in decoded_payloads} == {len(chunk_payloads)}
    assert {payload["protocol"] for payload in decoded_payloads} == {QRGenerator.CHUNK_PROTOCOL}
    assert {payload["encoding"] for payload in decoded_payloads} == {QRGenerator.CHUNK_ENCODING}

    for chunk_image in chunk_images:
        assert_png_image(chunk_image)


def test_reassemble_chunked_payloads_rejects_missing_chunk() -> None:
    generator = make_generator()
    chunk_payloads = generator.generate_chunked_payloads("missing-check-" * 500)

    with pytest.raises(ValueError, match="Incomplete QR chunks"):
        QRGenerator.reassemble_chunked_payloads(chunk_payloads[:-1])
