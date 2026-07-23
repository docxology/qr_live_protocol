"""
QR Code Generation module for QRLP.

Handles QR code creation, optimization, and image generation based on the qrkey protocol.
"""

import logging
import binascii
import hashlib

import qrcode
import qrcode.constants
import qrcode.exceptions

_logger = logging.getLogger("qrlp.qr_generator")

try:
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer, SquareModuleDrawer
    STYLED_QR_AVAILABLE = True
except ImportError:
    # Fallback for older qrcode versions
    STYLED_QR_AVAILABLE = False
    StyledPilImage = None
    RoundedModuleDrawer = None
    SquareModuleDrawer = None

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64
import json
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

from .config import QRSettings


@dataclass
class QRMetadata:
    """Metadata for QR code generation."""
    data_size: int
    error_correction: str
    version: int
    creation_time: float
    chunk_index: int = 0
    total_chunks: int = 1


class QRDataTooLargeError(ValueError):
    """Raised when data must be encoded through explicit QR chunking."""


class QRGenerator:
    """
    QR Code generator for QRLP.
    
    Handles creation of QR codes with embedded metadata, chunking for large data,
    and various styling options for livestreaming display.
    """
    
    # Error correction level mapping
    ERROR_CORRECTION_LEVELS = {
        'L': qrcode.constants.ERROR_CORRECT_L,  # ~7%
        'M': qrcode.constants.ERROR_CORRECT_M,  # ~15%
        'Q': qrcode.constants.ERROR_CORRECT_Q,  # ~25%
        'H': qrcode.constants.ERROR_CORRECT_H   # ~30%
    }

    BYTE_CAPACITY_BY_ERROR_CORRECTION = {
        'L': [17, 32, 53, 78, 106, 134, 154, 192, 230, 271, 321, 367, 425, 458, 520, 586, 644, 718, 792, 858,
              929, 1003, 1091, 1171, 1273, 1367, 1465, 1528, 1628, 1732, 1840, 1952, 2068, 2188, 2303, 2431,
              2563, 2699, 2809, 2953],
        'M': [14, 26, 42, 62, 84, 106, 122, 152, 180, 213, 251, 287, 331, 362, 412, 450, 504, 560, 624, 666,
              711, 779, 857, 911, 997, 1059, 1125, 1190, 1264, 1370, 1452, 1538, 1628, 1722, 1809, 1911,
              1989, 2099, 2213, 2331],
        'Q': [11, 20, 32, 46, 60, 74, 86, 108, 130, 151, 177, 203, 241, 258, 292, 322, 364, 394, 442, 482,
              509, 565, 611, 661, 715, 751, 805, 868, 908, 982, 1039, 1111, 1164, 1229, 1273, 1362, 1434,
              1504, 1574, 1662],
        'H': [7, 14, 24, 34, 44, 58, 64, 84, 98, 119, 137, 155, 177, 194, 220, 250, 280, 310, 338, 382,
              403, 439, 461, 511, 535, 593, 625, 658, 698, 742, 790, 842, 902, 940, 1002, 1064, 1126,
              1194, 1272, 1273]
    }

    CHUNK_PROTOCOL = "qrlp.chunk.v1"
    CHUNK_ENCODING = "base64:utf-8"
    
    def __init__(self, settings: QRSettings):
        """
        Initialize QR generator with settings.
        
        Args:
            settings: QRSettings configuration object
        """
        self.settings = settings
        self.cache = {}  # Cache for recently generated QR codes
        self.generation_count = 0
        
    def generate_qr_image(self, data: str, style: Optional[str] = None) -> bytes:
        """
        Generate QR code image as bytes.

        Args:
            data: String data to encode in QR code
            style: Optional style preset ('live', 'professional', 'minimal')

        Returns:
            QR code image as bytes (PNG format)
        """
        # Check cache first
        cache_key = f"{hash(data)}_{style}_{self.settings.error_correction_level}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Check if data is too large for single QR code
        estimated_version = self._estimate_qr_version(data)
        if estimated_version > 40:
            raise QRDataTooLargeError(self._large_payload_error_message(data))

        # Create QR code instance
        qr = self._create_qr_instance()

        # Add data and optimize
        try:
            qr.add_data(data)
            qr.make(fit=True)
        except qrcode.exceptions.DataOverflowError as exc:
            raise QRDataTooLargeError(self._large_payload_error_message(data)) from exc

        # Generate image with styling
        img = self._generate_styled_image(qr, style)

        # Convert to bytes
        img_bytes = self._image_to_bytes(img)

        # Cache result (limit cache size)
        if len(self.cache) > 100:
            # Remove oldest entries
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

        self.cache[cache_key] = img_bytes
        self.generation_count += 1

        return img_bytes

    def _estimate_qr_version(self, data: str) -> int:
        """
        Estimate the QR code version needed for the data.

        Args:
            data: Data string to encode

        Returns:
            Estimated QR code version (1-40)
        """
        # Rough estimation based on data length and error correction
        data_length = len(data.encode('utf-8'))

        # Use the configured error correction level
        capacity = self._capacity_for_error_correction()

        # Find the minimum version that can hold the data
        for version in range(len(capacity)):
            if data_length <= capacity[version]:
                return version + 1  # Versions start from 1

        # If data is too large, return maximum version + 1
        return 41

    def _generate_chunked_qr(self, data: str, style: Optional[str] = None) -> bytes:
        """
        Fail clearly for callers still reaching the old private chunk path.
        """
        raise QRDataTooLargeError(self._large_payload_error_message(data))

    def generate_chunked_payloads(self, data: str, max_chunk_size: Optional[int] = None) -> List[str]:
        """
        Generate recoverable JSON payloads for multi-QR transmission.

        Each payload contains its chunk data plus enough metadata to validate
        ordering, completeness, original byte length, encoding, and checksum.
        The returned strings are suitable inputs to generate_qr_image().
        """
        data_bytes = data.encode('utf-8')
        encoded_data = base64.b64encode(data_bytes).decode('ascii')
        data_hash = hashlib.sha256(data_bytes).hexdigest()
        chunk_size = self._resolve_chunk_size(
            encoded_data=encoded_data,
            data_size=len(data_bytes),
            data_hash=data_hash,
            max_chunk_size=max_chunk_size,
        )
        chunks = self._split_encoded_data(encoded_data, chunk_size)

        return [
            self._encode_chunk_payload(
                chunk=chunk,
                chunk_index=index,
                total_chunks=len(chunks),
                data_size=len(data_bytes),
                data_hash=data_hash,
            )
            for index, chunk in enumerate(chunks)
        ]

    @classmethod
    def reassemble_chunked_payloads(cls, payloads: List[str]) -> str:
        """
        Reassemble payloads produced by generate_chunked_payloads().

        Raises:
            ValueError: If any payload is malformed, duplicated, incomplete,
                incompatible with the others, or fails checksum validation.
        """
        if not payloads:
            raise ValueError("No QR chunk payloads provided for reassembly")

        parsed_payloads = [cls._decode_chunk_payload(payload) for payload in payloads]
        first = parsed_payloads[0]
        total_chunks = first["total_chunks"]

        chunks_by_index = {}
        for payload in parsed_payloads:
            cls._validate_compatible_chunk_payload(first, payload)
            chunk_index = payload["chunk_index"]
            if chunk_index in chunks_by_index:
                raise ValueError(f"Duplicate QR chunk index {chunk_index}")
            chunks_by_index[chunk_index] = payload["chunk"]

        expected_indexes = set(range(total_chunks))
        actual_indexes = set(chunks_by_index)
        if actual_indexes != expected_indexes:
            missing = sorted(expected_indexes - actual_indexes)
            extra = sorted(actual_indexes - expected_indexes)
            raise ValueError(f"Incomplete QR chunks; missing={missing}, unexpected={extra}")

        encoded_data = ''.join(chunks_by_index[index] for index in range(total_chunks))
        try:
            data_bytes = base64.b64decode(encoded_data.encode('ascii'), validate=True)
            data = data_bytes.decode('utf-8')
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ValueError("QR chunk payload data is not valid base64-encoded UTF-8") from exc

        if len(data_bytes) != first["data_size"]:
            raise ValueError(
                f"QR chunk payload size mismatch: expected {first['data_size']} bytes, got {len(data_bytes)}"
            )

        actual_hash = hashlib.sha256(data_bytes).hexdigest()
        if actual_hash != first["data_sha256"]:
            raise ValueError("QR chunk payload checksum mismatch")

        return data
    
    def generate_chunked_qr_codes(self, data: str, max_chunk_size: Optional[int] = None) -> List[bytes]:
        """
        Generate multiple QR codes for large data by chunking.
        
        Args:
            data: Large string data to encode
            max_chunk_size: Maximum bytes per chunk (uses config default if None)
            
        Returns:
            List of QR code image bytes. Each QR contains a recoverable chunk
            payload produced by generate_chunked_payloads().
        """
        return [
            self.generate_qr_image(payload, style='live')
            for payload in self.generate_chunked_payloads(data, max_chunk_size)
        ]
    
    def create_live_display_qr(self, qr_data: Dict, include_text: bool = True) -> bytes:
        """
        Create QR code optimized for live display with text overlay.
        
        Args:
            qr_data: Dictionary containing QR data
            include_text: Whether to include readable text overlay
            
        Returns:
            QR code image with text overlay as bytes
        """
        # Generate base QR code
        qr_json = json.dumps(qr_data, separators=(',', ':'))
        qr_img_bytes = self.generate_qr_image(qr_json, style='live')
        
        if not include_text:
            return qr_img_bytes
        
        # Add text overlay
        return self._add_text_overlay(qr_img_bytes, qr_data)
    
    def verify_qr_readability(self, qr_image: bytes) -> Dict[str, Union[bool, float]]:
        """
        Verify QR code readability and quality metrics.
        
        Args:
            qr_image: QR code image as bytes
            
        Returns:
            Dictionary with readability metrics
        """
        try:
            from pyzbar import pyzbar
            import cv2
            import numpy as np
            
            # Convert bytes to numpy array
            nparr = np.frombuffer(qr_image, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Decode QR code
            decoded_objects = pyzbar.decode(img)
            
            if decoded_objects:
                return {
                    "readable": True,
                    "confidence": 1.0,
                    "data_length": len(decoded_objects[0].data),
                    "type": decoded_objects[0].type
                }
            else:
                return {
                    "readable": False,
                    "confidence": 0.0,
                    "error": "Could not decode QR code"
                }
                
        except ImportError:
            return {
                "readable": None,
                "error": "pyzbar library not available for verification"
            }
        except Exception as e:
            return {
                "readable": False,
                "error": str(e)
            }
    
    def get_statistics(self) -> Dict:
        """Get generator statistics."""
        return {
            "total_generated": self.generation_count,
            "cache_size": len(self.cache),
            "settings": self.settings.__dict__
        }
    
    def _create_qr_instance(self) -> qrcode.QRCode:
        """Create QR code instance with current settings."""
        error_level = self.ERROR_CORRECTION_LEVELS.get(
            self.settings.error_correction_level, 
            qrcode.constants.ERROR_CORRECT_M
        )
        
        return qrcode.QRCode(
            version=1,  # Auto-determined
            error_correction=error_level,
            box_size=self.settings.box_size,
            border=self.settings.border_size,
        )

    def _capacity_for_error_correction(self) -> List[int]:
        """Return estimated byte capacities for the configured error correction level."""
        return self.BYTE_CAPACITY_BY_ERROR_CORRECTION.get(
            self.settings.error_correction_level,
            self.BYTE_CAPACITY_BY_ERROR_CORRECTION['M'],
        )

    def _max_single_qr_size(self) -> int:
        """Return the estimated maximum bytes a version-40 QR can hold."""
        return self._capacity_for_error_correction()[-1]

    def _large_payload_error_message(self, data: str) -> str:
        """Build an actionable error for oversized single-QR payloads."""
        data_size = len(data.encode('utf-8'))
        max_size = self._max_single_qr_size()
        return (
            f"Data is {data_size} bytes, which exceeds a single QR code capacity "
            f"of about {max_size} bytes for error correction level "
            f"{self.settings.error_correction_level}. Use generate_chunked_payloads() "
            "or generate_chunked_qr_codes(), then reassemble with "
            "QRGenerator.reassemble_chunked_payloads()."
        )

    def _resolve_chunk_size(
        self,
        encoded_data: str,
        data_size: int,
        data_hash: str,
        max_chunk_size: Optional[int],
    ) -> int:
        """Find the largest requested chunk size that still fits QR payload metadata."""
        requested_size = max_chunk_size if max_chunk_size is not None else self.settings.max_data_size
        if requested_size <= 0:
            raise ValueError("max_chunk_size must be a positive integer")

        high = max(1, min(requested_size, self._max_single_qr_size()))
        low = 1
        best_size: Optional[int] = None

        while low <= high:
            candidate_size = (low + high) // 2
            if self._chunk_payloads_fit(encoded_data, candidate_size, data_size, data_hash):
                best_size = candidate_size
                low = candidate_size + 1
            else:
                high = candidate_size - 1

        if best_size is None:
            raise QRDataTooLargeError(
                "QR chunk metadata cannot fit into a single QR code with the current settings"
            )

        return best_size

    def _chunk_payloads_fit(
        self,
        encoded_data: str,
        chunk_size: int,
        data_size: int,
        data_hash: str,
    ) -> bool:
        """Return whether every chunk payload fits into one QR code."""
        chunks = self._split_encoded_data(encoded_data, chunk_size)
        total_chunks = len(chunks)
        return all(
            self._estimate_qr_version(
                self._encode_chunk_payload(
                    chunk=chunk,
                    chunk_index=index,
                    total_chunks=total_chunks,
                    data_size=data_size,
                    data_hash=data_hash,
                )
            ) <= 40
            for index, chunk in enumerate(chunks)
        )

    def _encode_chunk_payload(
        self,
        chunk: str,
        chunk_index: int,
        total_chunks: int,
        data_size: int,
        data_hash: str,
    ) -> str:
        """Encode one chunk with enough metadata for validated reassembly."""
        payload = {
            "protocol": self.CHUNK_PROTOCOL,
            "chunked": True,
            "encoding": self.CHUNK_ENCODING,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "data_size": data_size,
            "data_sha256": data_hash,
            "chunk": chunk,
        }
        return json.dumps(payload, separators=(',', ':'), sort_keys=True)
    
    def _generate_styled_image(self, qr: qrcode.QRCode, style: Optional[str]) -> Image.Image:
        """Generate styled QR code image."""
        if style == 'live' and STYLED_QR_AVAILABLE:
            # High contrast for video streaming
            return qr.make_image(
                fill_color='black',
                back_color='white',
                image_factory=StyledPilImage,
                module_drawer=SquareModuleDrawer()
            )
        elif style == 'professional' and STYLED_QR_AVAILABLE:
            # Rounded corners for professional look
            return qr.make_image(
                fill_color=self.settings.fill_color,
                back_color=self.settings.back_color,
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer()
            )
        elif style == 'minimal':
            # Minimal styling
            return qr.make_image(
                fill_color='#333333',
                back_color='#ffffff'
            )
        elif style == 'live':
            # Fallback for live style without advanced styling
            return qr.make_image(
                fill_color='black',
                back_color='white'
            )
        elif style == 'professional':
            # Fallback for professional style
            return qr.make_image(
                fill_color=self.settings.fill_color,
                back_color=self.settings.back_color
            )
        else:
            # Default styling
            return qr.make_image(
                fill_color=self.settings.fill_color,
                back_color=self.settings.back_color
            )

    @classmethod
    def _decode_chunk_payload(cls, payload: str) -> Dict[str, Union[str, int, bool]]:
        """Decode and validate one chunk payload's shape."""
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("QR chunk payload is not valid JSON") from exc

        if not isinstance(decoded, dict):
            raise ValueError("QR chunk payload must be a JSON object")
        if decoded.get("protocol") != cls.CHUNK_PROTOCOL:
            raise ValueError("QR chunk payload protocol is unsupported")
        if decoded.get("chunked") is not True:
            raise ValueError("QR chunk payload is missing chunked=true")
        if decoded.get("encoding") != cls.CHUNK_ENCODING:
            raise ValueError("QR chunk payload encoding is unsupported")

        for field_name in ("chunk_index", "total_chunks", "data_size"):
            if type(decoded.get(field_name)) is not int:
                raise ValueError(f"QR chunk payload field {field_name} must be an integer")

        chunk_index = decoded["chunk_index"]
        total_chunks = decoded["total_chunks"]
        data_size = decoded["data_size"]
        if total_chunks < 1:
            raise ValueError("QR chunk total_chunks must be at least 1")
        if chunk_index < 0 or chunk_index >= total_chunks:
            raise ValueError("QR chunk index is outside the expected range")
        if data_size < 0:
            raise ValueError("QR chunk data_size must be non-negative")

        data_sha256 = decoded.get("data_sha256")
        if not isinstance(data_sha256, str) or len(data_sha256) != 64:
            raise ValueError("QR chunk payload data_sha256 must be a SHA-256 hex digest")
        try:
            int(data_sha256, 16)
        except ValueError as exc:
            raise ValueError("QR chunk payload data_sha256 must be hexadecimal") from exc

        if not isinstance(decoded.get("chunk"), str):
            raise ValueError("QR chunk payload field chunk must be a string")

        return decoded

    @classmethod
    def _validate_compatible_chunk_payload(
        cls,
        expected: Dict[str, Union[str, int, bool]],
        actual: Dict[str, Union[str, int, bool]],
    ) -> None:
        """Ensure one chunk belongs to the same payload set as another chunk."""
        for field_name in ("protocol", "encoding", "total_chunks", "data_size", "data_sha256"):
            if actual[field_name] != expected[field_name]:
                raise ValueError(f"QR chunk payload field {field_name} does not match")

    def _split_encoded_data(self, encoded_data: str, chunk_size: int) -> List[str]:
        """Split already-encoded data into QR-sized chunks."""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not encoded_data:
            return [""]
        return [
            encoded_data[index:index + chunk_size]
            for index in range(0, len(encoded_data), chunk_size)
        ]
    
    def _split_data(self, data: str, chunk_size: int) -> List[str]:
        """Split data into chunks for multiple QR codes."""
        # Use base64 encoding for binary safety
        encoded_data = base64.b64encode(data.encode('utf-8')).decode('ascii')

        return self._split_encoded_data(encoded_data, chunk_size)
    
    def _image_to_bytes(self, img: Image.Image) -> bytes:
        """Convert PIL Image to bytes."""
        img_buffer = BytesIO()
        img.save(img_buffer, format=self.settings.image_format)
        img_buffer.seek(0)
        return img_buffer.getvalue()
    
    def _add_text_overlay(self, qr_img_bytes: bytes, qr_data: Dict) -> bytes:
        """Add text overlay to QR code for live display."""
        try:
            # Load QR image
            qr_img = Image.open(BytesIO(qr_img_bytes))
            
            # Create larger canvas for text
            canvas_width = qr_img.width + 400  # Extra space for text
            canvas_height = qr_img.height + 100
            canvas = Image.new('RGB', (canvas_width, canvas_height), 'white')
            
            # Paste QR code
            qr_x = 20
            qr_y = 50
            canvas.paste(qr_img, (qr_x, qr_y))
            
            # Add text information
            draw = ImageDraw.Draw(canvas)
            
            try:
                # Try to load a nice font
                font_large = ImageFont.truetype("arial.ttf", 24)
                font_medium = ImageFont.truetype("arial.ttf", 16)
                font_small = ImageFont.truetype("arial.ttf", 12)
            except (OSError, IOError):
                # Fallback to default font
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Text position
            text_x = qr_img.width + 40
            text_y = 50
            
            # Title
            draw.text((text_x, text_y), "QR Live Protocol", fill='black', font=font_large)
            text_y += 40
            
            # Timestamp
            if 'timestamp' in qr_data:
                timestamp_text = f"Time: {qr_data['timestamp'][:19]}"
                draw.text((text_x, text_y), timestamp_text, fill='black', font=font_medium)
                text_y += 30
            
            # Sequence number
            if 'sequence_number' in qr_data:
                seq_text = f"Sequence: #{qr_data['sequence_number']}"
                draw.text((text_x, text_y), seq_text, fill='black', font=font_medium)
                text_y += 30
            
            # Identity hash (shortened)
            if 'identity_hash' in qr_data:
                identity_short = qr_data['identity_hash'][:16] + "..."
                identity_text = f"Identity: {identity_short}"
                draw.text((text_x, text_y), identity_text, fill='black', font=font_small)
                text_y += 25
            
            # Blockchain info
            if 'blockchain_hashes' in qr_data and qr_data['blockchain_hashes']:
                draw.text((text_x, text_y), "Blockchain Verified:", fill='green', font=font_small)
                text_y += 20
                for chain in list(qr_data['blockchain_hashes'].keys())[:3]:  # Show max 3
                    draw.text((text_x + 10, text_y), f"• {chain.title()}", fill='green', font=font_small)
                    text_y += 18
            
            # Convert back to bytes
            return self._image_to_bytes(canvas)
            
        except Exception as e:
            # Return original QR if text overlay fails
            _logger.error(f"Text overlay error: {e}")
            return qr_img_bytes
