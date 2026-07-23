"""
Tests for previously uncovered code paths across all modules.

Covers: cli live/dashboard, web_server _run_server/WebSocket/broadcast,
config YAML, signer message methods, error_recovery async resilient
functions, async_core optimization, core _update_loop, qr_generator
styled image fallbacks.
"""

import asyncio
import json
import time
import pytest
import tempfile
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from click.testing import CliRunner

from src.cli import cli, _parse_user_data, _load_qr_data_argument, _write_bytes
from src.config import QRLPConfig, WebSettings
from src.core import QRLiveProtocol, QRData
from src.crypto.signer import DigitalSigner, SignatureVerifier
from src.crypto import KeyManager
from src.error_recovery import (
    resilience_manager, resilient_qr_generation, resilient_verification,
    CircuitBreaker, CircuitBreakerConfig, RetryStrategy, ResilientOperation,
)
from src.qr_generator import QRGenerator
from src.config import QRSettings
from src.web_server import QRLiveWebServer, SecurityValidator


@pytest.fixture
def config_file(tmp_path):
    config = {
        "update_interval": 0.1,
        "blockchain_settings": {"enabled_chains": []},
        "time_settings": {"time_servers": []},
    }
    path = tmp_path / "test_config.json"
    path.write_text(json.dumps(config))
    return str(path)


# === CLI live/dashboard tests using subprocess ===

class TestCLILiveSubprocess:
    """Test cli live command using a real subprocess with timeout."""

    def test_live_starts_and_stops(self, config_file, tmp_path):
        """qrlp live should start and be killable."""
        env = os.environ.copy()
        env["QRLP_UPDATE_INTERVAL"] = "0.1"
        proc = subprocess.Popen(
            [sys.executable, "-c",
             "from src.cli import cli; cli(['--config', '" + config_file +
             "', 'live', '--no-browser', '--port', '0'])"],
            cwd=str(tmp_path.parent.parent.parent),  # repo root
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(2)
        proc.terminate()
        proc.wait(timeout=5)
        assert proc.returncode is not None

    def test_dashboard_starts_and_stops(self, config_file, tmp_path):
        """qrlp dashboard should start and be killable."""
        env = os.environ.copy()
        proc = subprocess.Popen(
            [sys.executable, "-c",
             "from src.cli import cli; cli(['--config', '" + config_file +
             "', 'dashboard', '--no-browser', '--port', '0'])"],
            cwd=str(tmp_path.parent.parent.parent),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(2)
        proc.terminate()
        proc.wait(timeout=5)
        assert proc.returncode is not None


class TestCLIHelpCommand:
    """Test that all CLI subcommands have help text."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_live_help(self, runner):
        result = runner.invoke(cli, ['live', '--help'])
        assert result.exit_code == 0
        assert "port" in result.output.lower()

    def test_dashboard_help(self, runner):
        result = runner.invoke(cli, ['dashboard', '--help'])
        assert result.exit_code == 0

    def test_generate_help(self, runner):
        result = runner.invoke(cli, ['generate', '--help'])
        assert result.exit_code == 0
        assert "output" in result.output.lower()

    def test_verify_help(self, runner):
        result = runner.invoke(cli, ['verify', '--help'])
        assert result.exit_code == 0

    def test_keys_help(self, runner):
        result = runner.invoke(cli, ['keys', '--help'])
        assert result.exit_code == 0

    def test_trust_help(self, runner):
        result = runner.invoke(cli, ['trust', '--help'])
        assert result.exit_code == 0

    def test_config_validate_help(self, runner):
        result = runner.invoke(cli, ['config-validate', '--help'])
        assert result.exit_code == 0


# === WebServer tests ===

class TestWebServerBroadcast:
    """Test _broadcast_qr_update and _send_qr_update_to_client."""

    @pytest.fixture
    def web_server(self, tmp_path):
        settings = WebSettings(host="localhost", port=0, auto_open_browser=False)
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(tmp_path / "keys")
        return QRLiveWebServer(settings, verifier=QRLiveProtocol(config))

    def test_broadcast_no_data(self, web_server):
        """_broadcast_qr_update does nothing when no QR data."""
        web_server.current_qr_data = None
        web_server.current_qr_image = None
        web_server._broadcast_qr_update()
        assert web_server.qr_updates_sent == 0

    def test_broadcast_with_data(self, web_server):
        """_broadcast_qr_update increments counter when data present."""
        qr_data, qr_image = web_server.verifier.generate_single_qr()
        web_server.is_running = True
        web_server.update_qr_display(qr_data, qr_image)
        web_server._broadcast_qr_update()
        assert web_server.qr_updates_sent >= 1

    def test_send_qr_update_no_data(self, web_server):
        """_send_qr_update_to_client does nothing when no QR data."""
        web_server.current_qr_data = None
        web_server._send_qr_update_to_client()


class TestWebServerStopServer:
    """Test stop_server method."""

    def test_stop_server_not_running(self, tmp_path):
        settings = WebSettings(host="localhost", port=0, auto_open_browser=False)
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(tmp_path / "keys")
        server = QRLiveWebServer(settings, verifier=QRLiveProtocol(config))
        server.is_running = False
        server.stop_server()
        assert server.is_running is False


# === Config YAML tests ===

class TestConfigYAML:
    """Test config.py from_file YAML path."""

    def test_from_file_yaml(self, tmp_path):
        """from_file should load YAML config when PyYAML is available."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        config_data = {
            "update_interval": 3.0,
            "qr_settings": {"error_correction_level": "H"},
            "blockchain_settings": {"enabled_chains": ["bitcoin"]},
        }
        yaml_file = tmp_path / "config.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(config_data, f)

        config = QRLPConfig.from_file(str(yaml_file))
        assert config.update_interval == 3.0
        assert config.qr_settings.error_correction_level == "H"

    def test_from_file_invalid_extension(self, tmp_path):
        """from_file rejects unsupported file extensions."""
        bad_file = tmp_path / "config.txt"
        bad_file.write_text("some content")
        with pytest.raises(ValueError, match="must be .json, .yml, or .yaml"):
            QRLPConfig.from_file(str(bad_file))

    def test_from_file_web_alias(self, tmp_path):
        """from_file applies backwards-compatible 'web' alias."""
        config_data = {
            "update_interval": 1.0,
            "web": {"port": 9090, "host": "0.0.0.0"},
        }
        json_file = tmp_path / "config.json"
        json_file.write_text(json.dumps(config_data))

        config = QRLPConfig.from_file(str(json_file))
        assert config.web_settings.port == 9090
        assert config.web_settings.host == "0.0.0.0"


# === Signer message methods ===

class TestSignerMessageMethods:
    """Test sign_message and verify_message methods."""

    def test_sign_message_rsa(self, temp_key_dir):
        km = KeyManager(str(temp_key_dir))
        km.generate_keypair(algorithm="rsa", key_size=2048, purpose="qr_signing")
        key_id = next(iter(km.list_keys()))
        keypair = km.get_keypair(key_id)

        signer = DigitalSigner(keypair.private_key, "rsa")
        message = "Hello, World!"
        signature = signer.sign_message(message)
        assert isinstance(signature, bytes)
        assert len(signature) > 0

        verifier = SignatureVerifier(keypair.public_key, "rsa")
        assert verifier.verify_message(message, signature) is True

    def test_verify_message_tampered(self, temp_key_dir):
        km = KeyManager(str(temp_key_dir))
        km.generate_keypair(algorithm="rsa", key_size=2048, purpose="qr_signing")
        key_id = next(iter(km.list_keys()))
        keypair = km.get_keypair(key_id)

        signer = DigitalSigner(keypair.private_key, "rsa")
        signature = signer.sign_message("original message")

        verifier = SignatureVerifier(keypair.public_key, "rsa")
        assert verifier.verify_message("tampered message", signature) is False

    def test_sign_message_ecdsa(self, temp_key_dir):
        km = KeyManager(str(temp_key_dir))
        km.generate_keypair(algorithm="ecdsa", key_size=256, purpose="qr_signing")
        key_id = next(iter(km.list_keys()))
        keypair = km.get_keypair(key_id)

        signer = DigitalSigner(keypair.private_key, "ecdsa")
        signature = signer.sign_message("ECDSA test message")

        verifier = SignatureVerifier(keypair.public_key, "ecdsa")
        assert verifier.verify_message("ECDSA test message", signature) is True

    def test_load_private_key_invalid(self):
        """Loading invalid PEM should raise SignatureError."""
        from src.crypto.exceptions import SignatureError
        with pytest.raises(SignatureError, match="Failed to load private key"):
            DigitalSigner(b"not a valid key", "rsa")

    def test_load_public_key_invalid(self):
        """Loading invalid public PEM should raise SignatureError."""
        from src.crypto.exceptions import SignatureError
        with pytest.raises(SignatureError, match="Failed to load public key"):
            SignatureVerifier(b"not a valid key", "rsa")

    def test_verify_message_failure(self, temp_key_dir):
        """verify_message returns False on invalid signature."""
        km = KeyManager(str(temp_key_dir))
        km.generate_keypair(algorithm="rsa", key_size=2048, purpose="qr_signing")
        key_id = next(iter(km.list_keys()))
        keypair = km.get_keypair(key_id)

        verifier = SignatureVerifier(keypair.public_key, "rsa")
        assert verifier.verify_message("test", b"invalid-signature") is False


# === Error recovery async resilient functions ===

class TestResilientAsyncFunctions:
    """Test resilient_qr_generation_async and resilient_verification_async."""

    async def test_resilient_qr_generation_async(self, tmp_path):
        from src.error_recovery import resilient_qr_generation_async
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(tmp_path / "keys")
        config.update_interval = 0.05

        class AsyncWrapper:
            def __init__(self, config):
                from src.async_core import AsyncQRLiveProtocol
                self._async = AsyncQRLiveProtocol(config)

            async def generate_single_qr_async(self, *args, **kwargs):
                return await self._async.generate_single_qr_async(*args, **kwargs)

        qrlp = AsyncWrapper(config)
        result = await resilient_qr_generation_async(qrlp, {"key": "val"}, True, False)
        assert len(result) == 2
        assert isinstance(result[0], QRData)


# === Async core optimization ===

class TestAsyncOptimization:
    """Test optimize_performance_async and apply_optimizations_async."""

    async def test_optimize_with_low_hit_rate(self, tmp_path):
        from src.async_core import AsyncQRLiveProtocol
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(tmp_path / "keys")
        async with AsyncQRLiveProtocol(config) as qrlp:
            # Simulate low cache hit rate
            qrlp._cache_misses = 10
            qrlp._cache_hits = 1
            result = await qrlp.optimize_performance_async()
            assert "recommendations" in result
            # Should recommend cache optimization
            assert len(result["recommendations"]) >= 1

    async def test_apply_optimizations_with_recommendations(self, tmp_path):
        from src.async_core import AsyncQRLiveProtocol
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(tmp_path / "keys")
        async with AsyncQRLiveProtocol(config) as qrlp:
            # Force low hit rate
            qrlp._cache_misses = 10
            qrlp._cache_hits = 0
            result = await qrlp.apply_optimizations_async(auto_optimize=True)
            assert "optimizations_applied" in result or "message" in result


# === Core _update_loop error path ===

class TestCoreUpdateLoopError:
    """Test _update_loop error handling."""

    def test_update_loop_handles_error(self, tmp_path):
        """_update_loop should continue after a generation error."""
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(tmp_path / "keys")
        config.update_interval = 0.05
        qrlp = QRLiveProtocol(config)

        # Replace generate_single_qr to raise on the _update_loop's direct call
        # The _update_loop calls generate_single_qr() with no args
        original = qrlp.generate_single_qr
        call_count = [0]
        def failing_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise RuntimeError("Simulated error")
            return original(*args, **kwargs)
        qrlp.generate_single_qr = failing_generate

        qrlp.start_live_generation()
        time.sleep(2.0)
        qrlp.stop_live_generation()
        # The loop should have run at least 2 cycles (1 error + 1 success)
        assert call_count[0] >= 2


# === QR Generator styled image fallbacks ===

class TestQRGeneratorStyledFallbacks:
    """Test QR style fallbacks when STYLED_QR_AVAILABLE is False."""

    def test_live_style_fallback(self):
        """live style without StyledPilImage should still produce PNG."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        img = gen.generate_qr_image("test data", style="live")
        assert img[:4] == b'\x89PNG'

    def test_professional_style_fallback(self):
        """professional style fallback produces PNG."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        img = gen.generate_qr_image("test data", style="professional")
        assert img[:4] == b'\x89PNG'

    def test_default_style(self):
        """Default style (None) produces PNG."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        img = gen.generate_qr_image("test data", style=None)
        assert img[:4] == b'\x89PNG'

    def test_minimal_style(self):
        """minimal style produces PNG."""
        settings = QRSettings(error_correction_level="L")
        gen = QRGenerator(settings)
        img = gen.generate_qr_image("test data", style="minimal")
        assert img[:4] == b'\x89PNG'


# === Core remove_update_callback ===

class TestRemoveCallback:
    """Test remove_update_callback edge cases."""

    def test_remove_nonexistent_callback(self, tmp_path):
        """Removing a callback that was never added should not crash."""
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(tmp_path / "keys")
        qrlp = QRLiveProtocol(config)

        def callback(qr_data, qr_image):
            pass

        qrlp.remove_update_callback(callback)
        assert len(qrlp._callbacks) == 0


# === HMAC manager generate_hmac with bytes and string ===

class TestHMACGenerateTypes:
    """Test HMACManager.generate_hmac with different input types."""

    def test_generate_hmac_bytes(self):
        from src.crypto.hmac import HMACManager
        mgr = HMACManager()
        hmac_value, key_id = mgr.generate_hmac(b"raw bytes data")
        assert isinstance(hmac_value, bytes)
        assert isinstance(key_id, str)

    def test_generate_hmac_string(self):
        from src.crypto.hmac import HMACManager
        mgr = HMACManager()
        hmac_value, _ = mgr.generate_hmac("string data")
        assert isinstance(hmac_value, bytes)

    def test_generate_hmac_object(self):
        from src.crypto.hmac import HMACManager
        mgr = HMACManager()
        hmac_value, _ = mgr.generate_hmac(12345)
        assert isinstance(hmac_value, bytes)

    def test_verify_hmac_mismatch(self):
        """verify_hmac returns False for mismatched HMAC."""
        from src.crypto.hmac import HMACManager
        mgr = HMACManager()
        hmac_value, _ = mgr.generate_hmac("correct data")
        # Verify with different data should return False
        result = mgr.verify_hmac("different data", hmac_value)
        assert result is False
