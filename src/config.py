"""
Configuration module for QRLP.

Defines all configuration structures and default values for the QR Live Protocol.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any


@dataclass
class QRSettings:
    """QR code generation settings."""
    error_correction_level: str = "M"  # L, M, Q, H
    border_size: int = 4
    box_size: int = 10
    fill_color: str = "black"
    back_color: str = "white"
    image_format: str = "PNG"
    max_data_size: int = 2000  # Maximum bytes per QR code


@dataclass
class TimeSettings:
    """Time provider settings."""
    update_interval: float = 1.0  # Seconds between time updates
    time_servers: list[str] = field(default_factory=lambda: [
        "time.nist.gov",
        "pool.ntp.org",
        "time.google.com",
        "time.cloudflare.com"
    ])
    timeout: float = 5.0  # Timeout for time server requests
    local_fallback: bool = True  # Use local time if servers unavailable
    timezone: str = "UTC"

    # OpenTimestamps (OTS) settings — additive verifiable timestamp layer.
    # When enabled, QR commitments are periodically stamped against a public
    # blockchain via an OpenTimestamps calendar server, producing ``.ots``
    # proof files that anyone can verify independently. Disabled by default so
    # existing behaviour is unchanged.
    ots_enabled: bool = False
    ots_server: str = "https://a.pool.opentimestamps.org"
    ots_min_interval: int = 300  # minimum seconds between stamps
    ots_proof_dir: str = "output/timestamps"


@dataclass
class BlockchainSettings:
    """Blockchain verification settings."""
    enabled_chains: set[str] = field(default_factory=lambda: {
        "bitcoin", "ethereum", "litecoin"
    })
    api_endpoints: dict[str, str] = field(default_factory=lambda: {
        "bitcoin": "https://blockstream.info/api",
        "ethereum": "https://api.etherscan.io/api",
        "litecoin": "https://api.blockcypher.com/v1/ltc/main"
    })
    cache_duration: int = 300  # Cache blockchain data for 5 minutes
    timeout: float = 10.0
    retry_attempts: int = 3


@dataclass
class IdentitySettings:
    """Identity management settings."""
    identity_file: str | None = None  # Path to identity file
    auto_generate: bool = True  # Generate identity if none exists
    hash_algorithm: str = "sha256"
    include_system_info: bool = True  # Include system info in identity
    include_file_hash: bool = True  # Include file hash if identity_file set


@dataclass
class WebSettings:
    """Web server settings."""
    host: str = "localhost"
    port: int = 8080
    auto_open_browser: bool = True
    template_dir: str = "templates"
    static_dir: str = "static"
    debug: bool = False
    cors_enabled: bool = False
    cors_allowed_origins: list[str] = field(default_factory=list)
    admin_token: str | None = None
    rate_limit_per_minute: int = 120


@dataclass
class VerificationSettings:
    """Verification settings."""
    max_time_drift: float = 30.0  # Maximum seconds for time verification
    require_blockchain: bool = False  # Require blockchain verification
    require_time_server: bool = False  # Require time server verification
    min_verifications: int = 1  # Minimum successful verifications required
    # Replay protection. When enabled, a verifier remembers the nonce of each
    # accepted QR (within replay_window_seconds) and marks a re-submitted QR as
    # a replay, which fails verification. Off by default to preserve the
    # existing stateless behaviour.
    enable_replay_protection: bool = False
    replay_window_seconds: int = 300


@dataclass
class SecuritySettings:
    """Security and encryption settings."""
    encrypt_qr_data: bool = False
    encryption_key: str | None = None  # 32 raw AES bytes, encoded as 64 hex characters
    sign_qr_data: bool = False
    private_key_file: str | None = None
    public_key_file: str | None = None
    key_dir: str | None = None
    issuer_id: str | None = None
    event_id: str = "default"
    signing_key_id: str | None = None
    signature_algorithm: str = "rsa"
    qr_ttl_seconds: int | None = None

    def get_encryption_key(self) -> bytes | None:
        """Decode an optional shared AES key without exposing invalid input."""
        key = self.encryption_key
        if key is None:
            return None
        if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdefABCDEF' for c in key):
            raise ValueError("security encryption_key must be 64 hexadecimal characters")
        return bytes.fromhex(key)


@dataclass
class LoggingSettings:
    """Logging configuration."""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_file: str | None = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class QRLPConfig:
    """Main QRLP configuration container."""

    # Core settings
    update_interval: float = 5.0  # Seconds between QR updates

    # Component settings
    qr_settings: QRSettings = field(default_factory=QRSettings)
    time_settings: TimeSettings = field(default_factory=TimeSettings)
    blockchain_settings: BlockchainSettings = field(default_factory=BlockchainSettings)
    identity_settings: IdentitySettings = field(default_factory=IdentitySettings)
    web_settings: WebSettings = field(default_factory=WebSettings)
    verification_settings: VerificationSettings = field(default_factory=VerificationSettings)
    security_settings: SecuritySettings = field(default_factory=SecuritySettings)
    logging_settings: LoggingSettings = field(default_factory=LoggingSettings)

    @classmethod
    def from_env(cls) -> QRLPConfig:
        """Create configuration from environment variables."""
        config = cls()

        # Update from environment variables
        update_interval = os.getenv('QRLP_UPDATE_INTERVAL')
        if update_interval:
            config.update_interval = _env_number('QRLP_UPDATE_INTERVAL', update_interval, float)

        web_port = os.getenv('QRLP_WEB_PORT')
        if web_port:
            config.web_settings.port = _env_number('QRLP_WEB_PORT', web_port, int)

        web_host = os.getenv('QRLP_WEB_HOST')
        if web_host:
            config.web_settings.host = web_host

        if os.getenv('QRLP_WEB_CORS_ENABLED'):
            config.web_settings.cors_enabled = os.getenv('QRLP_WEB_CORS_ENABLED', '').lower() in {
                '1', 'true', 'yes', 'on'
            }

        web_admin_token = os.getenv('QRLP_WEB_ADMIN_TOKEN')
        if web_admin_token:
            config.web_settings.admin_token = web_admin_token

        identity_file = os.getenv('QRLP_IDENTITY_FILE')
        if identity_file:
            config.identity_settings.identity_file = identity_file

        log_level = os.getenv('QRLP_LOG_LEVEL')
        if log_level:
            config.logging_settings.level = log_level

        issuer_id = os.getenv('QRLP_ISSUER_ID')
        if issuer_id:
            config.security_settings.issuer_id = issuer_id

        event_id = os.getenv('QRLP_EVENT_ID')
        if event_id:
            config.security_settings.event_id = event_id

        encryption_key = os.getenv('QRLP_ENCRYPTION_KEY')
        if encryption_key:
            config.security_settings.encryption_key = encryption_key

        return config

    @classmethod
    def from_file(cls, config_file: str | Path) -> QRLPConfig:
        """Load configuration from JSON or YAML file."""
        path = Path(config_file)
        if path.suffix.lower() == '.json':
            data = json.loads(path.read_text(encoding='utf-8'))
        elif path.suffix.lower() in {'.yml', '.yaml'}:
            try:
                import yaml
            except ImportError as exc:
                raise ImportError("Install the full extra for YAML configuration") from exc
            try:
                data = yaml.safe_load(path.read_text(encoding='utf-8'))
            except yaml.YAMLError as exc:
                raise ValueError("Invalid YAML configuration") from exc
        else:
            raise ValueError("Config file must be .json, .yml, or .yaml")

        config = cls()
        if not isinstance(data, dict):
            raise ValueError("Configuration must contain an object")
        # The canonical section wins over the legacy alias on overlapping fields.
        if 'web' in data:
            _update_dataclass(config.web_settings, data['web'], 'web')
        _update_dataclass(config, data)
        return config

    def to_dict(self) -> dict:
        """Return a JSON-compatible configuration dictionary."""
        from dataclasses import asdict

        data = asdict(self)
        data['blockchain_settings']['enabled_chains'] = sorted(self.blockchain_settings.enabled_chains)
        return data

    def validate(self) -> list[str]:
        """Validate configuration and return list of issues."""
        issues = []

        for name, value in (
            ("update_interval", self.update_interval),
            ("time_settings.update_interval", self.time_settings.update_interval),
            ("time_settings.timeout", self.time_settings.timeout),
            ("blockchain_settings.timeout", self.blockchain_settings.timeout),
        ):
            if not _finite_number(value) or value <= 0:
                issues.append(f"{name} must be positive and finite")

        if self.web_settings.port < 1 or self.web_settings.port > 65535:
            issues.append("web port must be between 1 and 65535")

        if self.qr_settings.error_correction_level not in ['L', 'M', 'Q', 'H']:
            issues.append("QR error correction level must be L, M, Q, or H")

        drift = self.verification_settings.max_time_drift
        if not _finite_number(drift) or drift < 0:
            issues.append("max_time_drift must be finite and non-negative")
        replay = self.verification_settings
        if replay.enable_replay_protection and (
            type(replay.replay_window_seconds) is not int or replay.replay_window_seconds <= 0
        ):
            issues.append("replay_window_seconds must be a positive integer when replay protection is enabled")

        if self.web_settings.rate_limit_per_minute < 0:
            issues.append("web rate_limit_per_minute must be non-negative")

        if self.security_settings.signature_algorithm not in {'rsa', 'ecdsa'}:
            issues.append("security signature_algorithm must be 'rsa' or 'ecdsa'")

        try:
            self.security_settings.get_encryption_key()
        except ValueError as exc:
            issues.append(str(exc))

        # Check file paths exist if specified
        if (self.identity_settings.identity_file and
            not os.path.exists(self.identity_settings.identity_file)):
            issues.append(f"Identity file not found: {self.identity_settings.identity_file}")

        return issues


def _env_number(name: str, value: str, converter: type[int] | type[float]) -> int | float:
    try:
        result = converter(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not _finite_number(result):
        raise ValueError(f"{name} must be finite")
    return result


def _finite_number(value: Any) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _update_dataclass(target: Any, values: Any, section: str = '') -> None:
    """Update recognized fields, checking the shapes before applying them."""
    if not isinstance(values, dict) or not all(isinstance(key, str) for key in values):
        raise ValueError(f"{section or 'Configuration'} must be an object with string keys")
    field_names = {item.name: item for item in fields(target)}
    for name, value in values.items():
        if name not in field_names:
            continue

        qualified = f"{section}.{name}" if section else name
        current_value = getattr(target, name)
        if is_dataclass(current_value):
            _update_dataclass(current_value, value, qualified)
            continue

        if isinstance(current_value, (list, set)):
            if not isinstance(value, (list, set, tuple)) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"{qualified} must be a list of strings")
            value = set(value) if isinstance(current_value, set) else list(value)
        elif isinstance(current_value, dict):
            if not isinstance(value, dict) or not all(
                isinstance(key, str) and isinstance(item, str) for key, item in value.items()
            ):
                raise ValueError(f"{qualified} must map strings to strings")
        elif type(current_value) is float:
            if not _finite_number(value):
                raise ValueError(f"{qualified} must be a finite number")
        elif current_value is not None:
            if type(value) is not type(current_value):
                raise ValueError(f"{qualified} must be {type(current_value).__name__}")
        elif value is not None:
            expected = int if name == 'qr_ttl_seconds' else str
            if type(value) is not expected:
                raise ValueError(f"{qualified} must be null or {expected.__name__}")
        setattr(target, name, value)
