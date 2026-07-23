"""
Tests for v1.2.0 features: VerificationResult, QRData.to_dict/__repr__,
config-validate, status --json, CSP headers, connection pooling.
"""

import json
import pytest
from click.testing import CliRunner

from src.cli import cli
from src.config import QRLPConfig, WebSettings
from src.core import QRData, VerificationResult, QRLiveProtocol
from src.web_server import QRLiveWebServer, SecurityValidator


@pytest.fixture
def runner():
    return CliRunner()


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


class TestVerificationResult:
    """Test VerificationResult dataclass."""

    def test_defaults(self):
        result = VerificationResult(valid_json=True)
        assert result.valid_json is True
        assert result.identity_verified is False
        assert result.time_verified is False
        assert result.valid is False
        assert result.trust_mode == "none"

    def test_all_fields(self):
        result = VerificationResult(
            valid_json=True,
            identity_verified=True,
            time_verified=True,
            blockchain_verified=True,
            signature_verified=True,
            hmac_verified=True,
            encrypted=False,
            valid=True,
            trust_mode="public_signature",
        )
        assert result.valid is True
        assert result.trust_mode == "public_signature"

    def test_to_dict(self):
        result = VerificationResult(valid_json=True, error="test error")
        d = result.to_dict()
        assert d["valid_json"] is True
        assert d["error"] == "test error"
        # False booleans are valid values and should be included
        assert d["identity_verified"] is False

    def test_to_dict_all_fields(self):
        result = VerificationResult(
            valid_json=True,
            identity_verified=True,
            valid=True,
        )
        d = result.to_dict()
        assert d["valid_json"] is True
        assert d["identity_verified"] is True
        assert d["valid"] is True

    def test_exported_from_src(self):
        from src import VerificationResult as SrcVR
        assert SrcVR is VerificationResult


class TestQRDataToDict:
    """Test QRData.to_dict and __repr__."""

    def test_to_dict_filters_none(self):
        qr = QRData(
            timestamp="2025-01-01T00:00:00Z",
            identity_hash="abc",
            blockchain_hashes={},
            time_server_verification={},
            sequence_number=1,
        )
        d = qr.to_dict()
        assert "timestamp" in d
        assert "sequence_number" in d
        assert "user_data" not in d
        assert "issuer_id" not in d

    def test_to_dict_includes_set_fields(self):
        qr = QRData(
            timestamp="2025-01-01T00:00:00Z",
            identity_hash="abc",
            blockchain_hashes={"bitcoin": "hash"},
            time_server_verification={},
            sequence_number=1,
            issuer_id="my-issuer",
            user_data={"key": "val"},
        )
        d = qr.to_dict()
        assert d["issuer_id"] == "my-issuer"
        assert d["user_data"] == {"key": "val"}
        assert d["blockchain_hashes"] == {"bitcoin": "hash"}

    def test_repr(self):
        qr = QRData(
            timestamp="2025-01-11T15:30:45.123Z",
            identity_hash="abc",
            blockchain_hashes={},
            time_server_verification={},
            sequence_number=42,
            issuer_id="test-issuer",
        )
        r = repr(qr)
        assert "seq=42" in r
        assert "issuer=test-issuer" in r
        assert "signed=no" in r

    def test_repr_signed(self):
        qr = QRData(
            timestamp="2025-01-11T15:30:45.123Z",
            identity_hash="abc",
            blockchain_hashes={},
            time_server_verification={},
            sequence_number=1,
            digital_signature="sig",
        )
        r = repr(qr)
        assert "signed=yes" in r

    def test_str_matches_repr(self):
        qr = QRData(
            timestamp="2025-01-01T00:00:00Z",
            identity_hash="abc",
            blockchain_hashes={},
            time_server_verification={},
            sequence_number=1,
        )
        assert str(qr) == repr(qr)


class TestCLIConfigValidate:
    """Test qrlp config-validate command."""

    def test_config_validate_valid(self, runner, config_file):
        result = runner.invoke(cli, ['config-validate', config_file])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()
        assert "Update interval" in result.output

    def test_config_validate_invalid_port(self, runner, tmp_path):
        config = {
            "update_interval": 1.0,
            "web_settings": {"port": 0},
            "blockchain_settings": {"enabled_chains": []},
            "time_settings": {"time_servers": []},
        }
        path = tmp_path / "bad_config.json"
        path.write_text(json.dumps(config))
        result = runner.invoke(cli, ['config-validate', str(path)])
        assert result.exit_code != 0
        assert "issue" in result.output.lower()

    def test_config_validate_nonexistent_file(self, runner):
        result = runner.invoke(cli, ['config-validate', '/nonexistent/path.json'])
        assert result.exit_code != 0


class TestCLIStatusJson:
    """Test qrlp status --json-output command."""

    def test_status_json(self, runner, config_file):
        result = runner.invoke(cli, ['--config', config_file, 'status', '--json-output'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "running" in data
        assert "total_updates" in data
        assert "sequence_number" in data

    def test_status_text(self, runner, config_file):
        result = runner.invoke(cli, ['--config', config_file, 'status'])
        assert result.exit_code == 0
        assert "QRLP Status" in result.output


class TestCSPHeaders:
    """Test Content-Security-Policy headers."""

    @pytest.fixture
    def web_server(self):
        settings = WebSettings(host="localhost", port=0, auto_open_browser=False)
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        return QRLiveWebServer(settings, verifier=QRLiveProtocol(config))

    def test_csp_header_present(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/api/status')
        assert "Content-Security-Policy" in response.headers

    def test_x_content_type_options(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/api/status')
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/api/status')
        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_referrer_policy(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/api/status')
        assert "Referrer-Policy" in response.headers


class TestConnectionPooling:
    """Test BlockchainVerifier connection pooling."""

    def test_get_session_creates_session(self):
        from src.blockchain_verifier import BlockchainVerifier
        from src.config import BlockchainSettings
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        assert verifier._session is None
        session = verifier._get_session()
        assert session is not None
        # Second call returns same session
        session2 = verifier._get_session()
        assert session is session2
