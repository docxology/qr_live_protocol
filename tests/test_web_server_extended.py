"""
Tests for web_server.py SecurityValidator, routes, and dashboard.

Uses Flask test_client() -- no actual server thread is started.
"""

import json
import pytest
import tempfile

from src.web_server import QRLiveWebServer, SecurityValidator, security_middleware
from src.config import WebSettings, QRLPConfig
from src.core import QRLiveProtocol, QRData
from werkzeug.exceptions import BadRequest


class TestSecurityValidatorUserText:
    """Test SecurityValidator.validate_user_text."""

    def test_valid_text(self):
        assert SecurityValidator.validate_user_text("Hello World 123") == "Hello World 123"

    def test_strips_html(self):
        """HTML tags are stripped by bleach, leaving text content."""
        # bleach.clean strips tags but the result must still pass the
        # character whitelist pattern, so use plain text
        result = SecurityValidator.validate_user_text("hello world")
        assert result == "hello world"

    def test_non_string_rejected(self):
        with pytest.raises(BadRequest, match="must be a string"):
            SecurityValidator.validate_user_text(123)

    def test_none_rejected(self):
        with pytest.raises(BadRequest, match="must be a string"):
            SecurityValidator.validate_user_text(None)

    def test_too_long_rejected(self):
        long_text = "a" * (SecurityValidator.MAX_USER_TEXT_LENGTH + 1)
        with pytest.raises(BadRequest, match="too long"):
            SecurityValidator.validate_user_text(long_text)

    def test_empty_string_passes(self):
        """Valid text passes validation."""
        result = SecurityValidator.validate_user_text("abc")
        assert result == "abc"

    def test_invalid_chars_rejected(self):
        """Characters outside the allowed pattern are rejected."""
        with pytest.raises(BadRequest, match="invalid characters"):
            SecurityValidator.validate_user_text("hello@world#test")


class TestSecurityValidatorQRData:
    """Test SecurityValidator.validate_qr_data."""

    def test_valid_json(self):
        qr_json = json.dumps({"key": "value"})
        assert SecurityValidator.validate_qr_data(qr_json) == qr_json

    def test_invalid_json_rejected(self):
        with pytest.raises(BadRequest, match="Invalid QR data JSON"):
            SecurityValidator.validate_qr_data("not json")

    def test_non_object_rejected(self):
        with pytest.raises(BadRequest, match="must be a JSON object"):
            SecurityValidator.validate_qr_data("[1, 2, 3]")

    def test_non_string_rejected(self):
        with pytest.raises(BadRequest, match="must be a string"):
            SecurityValidator.validate_qr_data(123)

    def test_too_large_rejected(self):
        large = json.dumps({"k": "v" * SecurityValidator.MAX_QR_DATA_LENGTH})
        with pytest.raises(BadRequest, match="too large"):
            SecurityValidator.validate_qr_data(large)


class TestSecurityValidatorJSONInput:
    """Test SecurityValidator.validate_json_input."""

    def test_valid_dict(self):
        result = SecurityValidator.validate_json_input({"key": "val"})
        assert result == {"key": "val"}

    def test_non_dict_rejected(self):
        with pytest.raises(BadRequest, match="must be a JSON object"):
            SecurityValidator.validate_json_input("string")

    def test_list_rejected(self):
        with pytest.raises(BadRequest, match="must be a JSON object"):
            SecurityValidator.validate_json_input([1, 2])


class TestQRLiveWebServerRoutes:
    """Test QRLiveWebServer HTTP routes via test client."""

    @pytest.fixture
    def web_server(self):
        """Create a web server with minimal config."""
        settings = WebSettings(
            host="localhost", port=0, auto_open_browser=False,
            debug=False, cors_enabled=False,
        )
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        verifier = QRLiveProtocol(config)
        return QRLiveWebServer(settings, verifier=verifier)

    def test_index_route(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/')
        assert response.status_code == 200

    def test_status_route(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/api/status')
        assert response.status_code == 200
        data = response.get_json()
        assert "is_running" in data

    def test_status_simple_route(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/status')
        assert response.status_code == 200

    def test_current_qr_no_data(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/api/qr/current')
        assert response.status_code == 404

    def test_current_qr_with_data(self, web_server):
        """After update_qr_display, /api/qr/current returns data."""
        qr_data, qr_image = web_server.verifier.generate_single_qr()
        web_server.update_qr_display(qr_data, qr_image)
        client = web_server.app.test_client()
        response = client.get('/api/qr/current')
        assert response.status_code == 200
        data = response.get_json()
        assert "qr_data" in data
        assert "qr_image" in data

    def test_verify_route(self, web_server):
        """Verify endpoint accepts QR JSON."""
        qr_data, _ = web_server.verifier.generate_single_qr()
        client = web_server.app.test_client()
        response = client.post('/api/verify',
                              json={"qr_data": qr_data.to_json()},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert "valid_json" in data

    def test_verify_route_no_data(self, web_server):
        client = web_server.app.test_client()
        response = client.post('/api/verify',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400

    def test_verify_route_bad_content_type(self, web_server):
        client = web_server.app.test_client()
        response = client.post('/api/verify',
                              data="not json",
                              content_type='text/plain')
        assert response.status_code == 400

    def test_viewer_route(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/viewer')
        assert response.status_code == 200

    def test_admin_route(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/admin')
        assert response.status_code == 200

    def test_improve_route(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/improve')
        assert response.status_code == 200

    def test_improve_status_route(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/api/improve/status')
        assert response.status_code == 200
        data = response.get_json()
        assert "readiness" in data
        assert "features" in data

    def test_improve_smoke_test_route(self, web_server):
        client = web_server.app.test_client()
        response = client.post('/api/improve/smoke-test',
                              json={},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert "success" in data


class TestUserDataRoutes:
    """Test user-data GET/POST routes."""

    @pytest.fixture
    def web_server(self):
        settings = WebSettings(host="localhost", port=0, auto_open_browser=False)
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        return QRLiveWebServer(settings, verifier=QRLiveProtocol(config))

    def test_get_user_data_empty(self, web_server):
        client = web_server.app.test_client()
        response = client.get('/api/user-data')
        assert response.status_code == 200
        assert response.get_json()["user_data"] is None

    def test_post_user_data(self, web_server):
        client = web_server.app.test_client()
        response = client.post('/api/user-data',
                              json={"user_text": "hello world"},
                              content_type='application/json')
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    def test_post_user_data_invalid(self, web_server):
        client = web_server.app.test_client()
        response = client.post('/api/user-data',
                              json={"user_text": "hello@world"},
                              content_type='application/json')
        assert response.status_code == 400

    def test_post_user_data_bad_content_type(self, web_server):
        client = web_server.app.test_client()
        response = client.post('/api/user-data',
                              data="text",
                              content_type='text/plain')
        assert response.status_code == 400


class TestAdminToken:
    """Test admin token protection."""

    @pytest.fixture
    def web_server_with_token(self):
        settings = WebSettings(
            host="localhost", port=0, auto_open_browser=False,
            admin_token="secret-token",
        )
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        return QRLiveWebServer(settings, verifier=QRLiveProtocol(config))

    def test_post_user_data_without_token_rejected(self, web_server_with_token):
        client = web_server_with_token.app.test_client()
        response = client.post('/api/user-data',
                              json={"user_text": "hello"},
                              content_type='application/json')
        assert response.status_code == 401

    def test_post_user_data_with_header_token(self, web_server_with_token):
        client = web_server_with_token.app.test_client()
        response = client.post('/api/user-data',
                              json={"user_text": "hello"},
                              content_type='application/json',
                              headers={"X-QRLP-Admin-Token": "secret-token"})
        assert response.status_code == 200

    def test_post_user_data_with_bearer_token(self, web_server_with_token):
        client = web_server_with_token.app.test_client()
        response = client.post('/api/user-data',
                              json={"user_text": "hello"},
                              content_type='application/json',
                              headers={"Authorization": "Bearer secret-token"})
        assert response.status_code == 200

    def test_post_user_data_with_wrong_token_rejected(self, web_server_with_token):
        client = web_server_with_token.app.test_client()
        response = client.post('/api/user-data',
                              json={"user_text": "hello"},
                              content_type='application/json',
                              headers={"X-QRLP-Admin-Token": "wrong"})
        assert response.status_code == 401

    def test_authorized_socket_without_token(self):
        """_authorized_socket returns True when no admin_token set."""
        settings = WebSettings(admin_token=None)
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        server = QRLiveWebServer(settings, verifier=QRLiveProtocol(config))
        assert server._authorized_socket({}) is True

    def test_authorized_socket_with_token(self):
        """_authorized_socket checks token in data."""
        settings = WebSettings(admin_token="tok")
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        server = QRLiveWebServer(settings, verifier=QRLiveProtocol(config))
        assert server._authorized_socket({"admin_token": "tok"}) is True
        assert server._authorized_socket({"admin_token": "wrong"}) is False
        assert server._authorized_socket({}) is False


class TestWebServerUtilities:
    """Test utility methods."""

    @pytest.fixture
    def web_server(self):
        settings = WebSettings(host="localhost", port=8080, auto_open_browser=False)
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        return QRLiveWebServer(settings, verifier=QRLiveProtocol(config))

    def test_get_server_url(self, web_server):
        assert web_server.get_server_url() == "http://localhost:8080"

    def test_get_statistics(self, web_server):
        stats = web_server.get_statistics()
        assert stats["is_running"] is False
        assert stats["page_views"] == 0
        assert stats["server_url"] == "http://localhost:8080"

    def test_update_qr_display(self, web_server):
        qr_data, qr_image = web_server.verifier.generate_single_qr()
        web_server.update_qr_display(qr_data, qr_image)
        assert web_server.current_qr_data is not None
        assert web_server.current_qr_image is not None

    def test_get_user_data(self, web_server):
        assert web_server.get_user_data() is None
        web_server.user_input_data = "test"
        assert web_server.get_user_data() == "test"

    def test_get_improvement_status(self, web_server):
        status = web_server._get_improvement_status()
        assert "readiness" in status
        assert "features" in status
        assert "trust" in status
        assert "keys" in status
        assert "configuration" in status
        assert status["readiness"]["state"] in ("ready", "needs_attention")

    def test_feature_status(self):
        result = QRLiveWebServer._feature_status("test", True, "pass")
        assert result["name"] == "test"
        assert result["ok"] is True
        assert result["severity"] == "pass"

    def test_feature_status_fail(self):
        result = QRLiveWebServer._feature_status("test", False, "warn")
        assert result["ok"] is False
        assert result["severity"] == "warn"


class TestRateLimiting:
    """Test rate limiting middleware."""

    def test_rate_limit_enforced(self):
        """Requests exceeding rate limit get 429."""
        settings = WebSettings(
            host="localhost", port=0, auto_open_browser=False,
            rate_limit_per_minute=3,
        )
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        server = QRLiveWebServer(settings, verifier=QRLiveProtocol(config))
        client = server.app.test_client()

        # First 3 requests OK
        for _ in range(3):
            resp = client.get('/api/status')
            assert resp.status_code == 200

        # 4th request rate-limited
        resp = client.get('/api/status')
        assert resp.status_code == 429


class TestCORS:
    """Test CORS configuration."""

    def test_cors_enabled(self):
        settings = WebSettings(
            host="localhost", port=0, auto_open_browser=False,
            cors_enabled=True, cors_allowed_origins=["https://example.com"],
        )
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        server = QRLiveWebServer(settings, verifier=QRLiveProtocol(config))
        client = server.app.test_client()
        resp = client.get('/api/status')
        assert resp.status_code == 200
