"""
Tests for QRLPConfig.from_env environment variable handling.

Covers the single os.getenv call optimization and all env var mappings.
"""

import os
import pytest
from src.config import QRLPConfig


class TestConfigFromEnv:
    """Test environment variable configuration."""

    def test_from_env_default(self):
        """from_env with no env vars should return defaults."""
        # Clear all QRLP env vars
        env_keys = [
            'QRLP_UPDATE_INTERVAL', 'QRLP_WEB_PORT', 'QRLP_WEB_HOST',
            'QRLP_WEB_CORS_ENABLED', 'QRLP_WEB_ADMIN_TOKEN',
            'QRLP_IDENTITY_FILE', 'QRLP_LOG_LEVEL', 'QRLP_ISSUER_ID',
            'QRLP_EVENT_ID',
        ]
        old_values = {}
        for key in env_keys:
            old_values[key] = os.environ.pop(key, None)

        try:
            config = QRLPConfig.from_env()
            assert config.update_interval == 5.0
            assert config.web_settings.port == 8080
            assert config.web_settings.host == "localhost"
            assert config.web_settings.cors_enabled is False
            assert config.web_settings.admin_token is None
            assert config.identity_settings.identity_file is None
            assert config.logging_settings.level == "INFO"
            assert config.security_settings.issuer_id is None
            assert config.security_settings.event_id == "default"
        finally:
            for key, value in old_values.items():
                if value is not None:
                    os.environ[key] = value

    def test_from_env_update_interval(self):
        """QRLP_UPDATE_INTERVAL should set update_interval."""
        os.environ['QRLP_UPDATE_INTERVAL'] = '2.5'
        try:
            config = QRLPConfig.from_env()
            assert config.update_interval == 2.5
        finally:
            del os.environ['QRLP_UPDATE_INTERVAL']

    def test_from_env_web_port(self):
        """QRLP_WEB_PORT should set web_settings.port."""
        os.environ['QRLP_WEB_PORT'] = '9090'
        try:
            config = QRLPConfig.from_env()
            assert config.web_settings.port == 9090
        finally:
            del os.environ['QRLP_WEB_PORT']

    def test_from_env_web_host(self):
        """QRLP_WEB_HOST should set web_settings.host."""
        os.environ['QRLP_WEB_HOST'] = '0.0.0.0'
        try:
            config = QRLPConfig.from_env()
            assert config.web_settings.host == '0.0.0.0'
        finally:
            del os.environ['QRLP_WEB_HOST']

    def test_from_env_cors_enabled(self):
        """QRLP_WEB_CORS_ENABLED should set cors_enabled."""
        for value in ['1', 'true', 'yes', 'on']:
            os.environ['QRLP_WEB_CORS_ENABLED'] = value
            try:
                config = QRLPConfig.from_env()
                assert config.web_settings.cors_enabled is True
            finally:
                del os.environ['QRLP_WEB_CORS_ENABLED']

    def test_from_env_cors_disabled(self):
        """QRLP_WEB_CORS_ENABLED with falsy values should disable CORS."""
        for value in ['0', 'false', 'no', 'off']:
            os.environ['QRLP_WEB_CORS_ENABLED'] = value
            try:
                config = QRLPConfig.from_env()
                assert config.web_settings.cors_enabled is False
            finally:
                del os.environ['QRLP_WEB_CORS_ENABLED']

    def test_from_env_admin_token(self):
        """QRLP_WEB_ADMIN_TOKEN should set admin_token."""
        os.environ['QRLP_WEB_ADMIN_TOKEN'] = 'secret123'
        try:
            config = QRLPConfig.from_env()
            assert config.web_settings.admin_token == 'secret123'
        finally:
            del os.environ['QRLP_WEB_ADMIN_TOKEN']

    def test_from_env_identity_file(self):
        """QRLP_IDENTITY_FILE should set identity_file."""
        os.environ['QRLP_IDENTITY_FILE'] = '/path/to/identity'
        try:
            config = QRLPConfig.from_env()
            assert config.identity_settings.identity_file == '/path/to/identity'
        finally:
            del os.environ['QRLP_IDENTITY_FILE']

    def test_from_env_log_level(self):
        """QRLP_LOG_LEVEL should set logging level."""
        os.environ['QRLP_LOG_LEVEL'] = 'DEBUG'
        try:
            config = QRLPConfig.from_env()
            assert config.logging_settings.level == 'DEBUG'
        finally:
            del os.environ['QRLP_LOG_LEVEL']

    def test_from_env_issuer_id(self):
        """QRLP_ISSUER_ID should set issuer_id."""
        os.environ['QRLP_ISSUER_ID'] = 'my-issuer'
        try:
            config = QRLPConfig.from_env()
            assert config.security_settings.issuer_id == 'my-issuer'
        finally:
            del os.environ['QRLP_ISSUER_ID']

    def test_from_env_event_id(self):
        """QRLP_EVENT_ID should set event_id."""
        os.environ['QRLP_EVENT_ID'] = 'event-2025'
        try:
            config = QRLPConfig.from_env()
            assert config.security_settings.event_id == 'event-2025'
        finally:
            del os.environ['QRLP_EVENT_ID']


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_valid_config(self):
        """Valid config should return no issues."""
        config = QRLPConfig()
        issues = config.validate()
        assert issues == []

    def test_validate_negative_interval(self):
        """Negative update_interval should be flagged."""
        config = QRLPConfig()
        config.update_interval = -1
        issues = config.validate()
        assert any("update_interval" in i for i in issues)

    def test_validate_invalid_port(self):
        """Invalid port should be flagged."""
        config = QRLPConfig()
        config.web_settings.port = 0
        issues = config.validate()
        assert any("port" in i for i in issues)

    def test_validate_invalid_error_correction(self):
        """Invalid error correction level should be flagged."""
        config = QRLPConfig()
        config.qr_settings.error_correction_level = "X"
        issues = config.validate()
        assert any("error correction" in i for i in issues)

    def test_validate_negative_time_drift(self):
        """Negative max_time_drift should be flagged."""
        config = QRLPConfig()
        config.verification_settings.max_time_drift = -1
        issues = config.validate()
        assert any("max_time_drift" in i for i in issues)

    def test_validate_invalid_signature_algorithm(self):
        """Invalid signature algorithm should be flagged."""
        config = QRLPConfig()
        config.security_settings.signature_algorithm = "dsa"
        issues = config.validate()
        assert any("signature_algorithm" in i for i in issues)
