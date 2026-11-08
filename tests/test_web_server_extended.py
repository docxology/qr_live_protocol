"""
Tests for web_server.py SecurityValidator, routes, and dashboard.

Uses Flask test_client() -- no actual server thread is started.
"""

import json
import re
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from werkzeug.exceptions import BadRequest

from src.config import QRLPConfig, WebSettings
from src.core import QRData, QRLiveProtocol
from src.web_server import QRLiveWebServer, SecurityValidator


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
        assert SecurityValidator.validate_user_text("  ") == ""

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
        qr_data, qr_image = web_server.verifier.generate_single_qr({"z": "first", "a": "second"})
        qr_data.ots_proof_path = "/local/test-proof.ots"
        web_server.update_qr_display(qr_data, qr_image)
        client = web_server.app.test_client()
        response = client.get('/api/qr/current')
        assert response.status_code == 200
        data = response.get_json()
        assert data["qr_json"] == qr_data.to_json()
        assert data["qr_data"] == json.loads(qr_data.to_json())
        assert b"/local/test-proof.ots" not in response.data
        assert b"/local/test-proof.ots" not in client.get("/api/improve/status").data
        assert "qr_image" in data

    def test_event_stream_sends_current_and_subsequent_frames(self, web_server):
        first = QRData("2026-01-01T00:00:00Z", "first", {}, {}, sequence_number=1)
        second = QRData("2026-01-01T00:00:05Z", "second", {}, {}, sequence_number=2)
        web_server.update_qr_display(first, b"first image")
        response = web_server.app.test_client().get("/api/qr/events", buffered=False)
        try:
            assert response.mimetype == "text/event-stream"
            assert response.headers["Cache-Control"] == "no-store"
            assert web_server.get_statistics()["event_stream_connections"] == 1
            frames = iter(response.response)
            first_event = next(frames)
            assert json.loads(first_event.removeprefix(b"data: "))["qr_data"]["sequence_number"] == 1
            web_server.update_qr_display(second, b"second image")
            assert json.loads(next(frames).removeprefix(b"data: ")) == (
                web_server.app.test_client().get("/api/qr/current").get_json()
            )
        finally:
            response.close()
        assert web_server.get_statistics()["event_stream_connections"] == 0

    def test_failed_worker_start_closes_listener(self, monkeypatch):
        from unittest.mock import Mock

        listener = Mock()
        monkeypatch.setattr("src.web_server.make_server", lambda *args, **kwargs: listener)
        monkeypatch.setattr("threading.Thread.start", Mock(side_effect=RuntimeError("no threads")))
        server = QRLiveWebServer(WebSettings(host="127.0.0.1", port=0, auto_open_browser=False))

        with pytest.raises(RuntimeError, match="no threads"):
            server.start_server()
        assert server.get_statistics()["is_running"] is False
        listener.server_close.assert_called_once()
        server.stop_server()
        listener.shutdown.assert_not_called()

    def test_http_server_releases_port_on_stop(self):
        server = QRLiveWebServer(WebSettings(host="127.0.0.1", port=0, auto_open_browser=False))
        server.start_server()
        status_url = f"{server.get_server_url()}/api/status"
        try:
            with urlopen(status_url, timeout=2) as response:
                assert json.load(response)["is_running"] is True
        finally:
            server.stop_server()
        with pytest.raises(URLError):
            urlopen(status_url, timeout=2)
        server.start_server()
        try:
            with urlopen(f"{server.get_server_url()}/api/status", timeout=2) as response:
                assert response.status == 200
        finally:
            server.stop_server()

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

    def test_obs_overlay_is_display_only_and_details_are_opt_in(self, web_server):
        web_server.settings.admin_token = "overlay-test-token"
        client = web_server.app.test_client()
        plain = client.get("/overlay")
        with_details = client.get("/overlay?details=1")
        assert plain.status_code == with_details.status_code == 200
        assert b'id="overlayDetails"' not in plain.data
        assert b'id="overlayDetails"' in with_details.data
        for response in (plain, with_details):
            assert b'<form' not in response.data
            assert b'/api/user-data' not in response.data
            assert b'overlay-test-token' not in response.data
        assert client.post("/overlay", json={}).status_code == 405

    @pytest.mark.parametrize("path", ["/", "/viewer", "/overlay", "/admin", "/improve"])
    def test_dashboard_scripts_use_the_response_nonce(self, web_server, path):
        response = web_server.app.test_client().get(path)
        policy = response.headers["Content-Security-Policy"]
        match = re.search(r"script-src 'self' 'nonce-([^']+)';", policy)
        assert match
        html = response.get_data(as_text=True)
        assert re.findall(r"<script[^>]+>", html)
        assert all(
            f'nonce="{match[1]}"' in script
            for script in re.findall(r"<script[^>]+>", html)
        )
        if path in {"/", "/viewer", "/overlay"}:
            assert "EventSource" in html
            assert "https://cdnjs.cloudflare.com" not in html
        if path == "/viewer":
            assert "/api/user-data" in html

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
        assert data["success"] is True
        assert data["signed_round_trip"]["trust_mode"] == "public_signature"
        assert data["verification"]["hmac_verified"] is False

    @pytest.mark.parametrize("body", ["[", "[]", "null", "false"])
    def test_improve_smoke_test_rejects_malformed_bodies(self, web_server, body):
        response = web_server.app.test_client().post(
            "/api/improve/smoke-test", data=body, content_type="application/json"
        )
        assert response.status_code == 400

    def test_improve_smoke_test_does_not_leak_exception(self, web_server, monkeypatch):
        def fail_smoke_test():
            raise RuntimeError("internal details")

        monkeypatch.setattr(web_server, "_run_improvement_smoke_test", fail_smoke_test)
        response = web_server.app.test_client().post("/api/improve/smoke-test", json={})
        assert response.status_code == 500
        assert b"internal details" not in response.data


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

    def test_post_user_data_clears_existing_message(self, web_server):
        client = web_server.app.test_client()
        client.post("/api/user-data", json={"user_text": "test message"})
        assert client.get("/api/user-data").get_json()["user_data"] == "test message"
        assert client.post("/api/user-data", json={"user_text": ""}).status_code == 200
        assert client.get("/api/user-data").get_json()["user_data"] is None

    def test_oversized_json_body_is_rejected(self, web_server):
        response = web_server.app.test_client().post(
            "/api/user-data", json={"user_text": "x", "padding": "x" * (128 * 1024)}
        )
        assert response.status_code == 413

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

    @pytest.mark.parametrize("host,request_options", [
        ("0.0.0.0", {}),
        ("localhost", {"environ_overrides": {"REMOTE_ADDR": "192.0.2.1"}}),
        ("localhost", {"base_url": "http://outside.test"}),
        ("localhost", {"headers": {"Origin": "https://outside.test"}}),
    ])
    def test_tokenless_controls_reject_nonlocal_and_cross_origin_requests(self, host, request_options):
        server = QRLiveWebServer(WebSettings(host=host))
        client = server.app.test_client()
        assert client.post("/api/user-data", json={"user_text": "message"}, **request_options).status_code == 401

    def test_public_views_do_not_expose_secrets(self, web_server_with_token):
        security = web_server_with_token.verifier.config.security_settings
        security.encryption_key = "test-encryption-key"
        security.private_key_file = "/local/test-private-key.pem"
        client = web_server_with_token.app.test_client()
        for route in ("/", "/viewer", "/improve", "/api/improve/status"):
            response = client.get(route)
            assert response.status_code == 200
            assert b"secret-token" not in response.data
            assert b"test-encryption-key" not in response.data
            assert b"/local/test-private-key.pem" not in response.data

    def test_socket_invalid_payload_is_rejected_and_text_can_be_cleared(self, web_server_with_token):
        socket = web_server_with_token.socketio.test_client(web_server_with_token.app)
        try:
            socket.emit("update_user_data", ["not", "an", "object"])
            assert socket.get_received()[0]["name"] == "user_data_error"
            socket.emit("update_user_data", {"admin_token": "secret-token", "user_text": "message"})
            assert socket.get_received()[0]["name"] == "user_data_updated"
            assert web_server_with_token.get_user_data() == "message"
            socket.emit("update_user_data", {"admin_token": "secret-token", "user_text": ""})
            assert socket.get_received()[0]["args"][0]["user_data"] is None
        finally:
            socket.disconnect()

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
        """A loopback socket may write without a configured token."""
        settings = WebSettings(admin_token=None)
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        server = QRLiveWebServer(settings, verifier=QRLiveProtocol(config))
        with server.app.test_request_context("/", environ_overrides={"REMOTE_ADDR": "127.0.0.1"}):
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

    def test_authorized_socket_handles_none_and_nonstring(self):
        """_authorized_socket safely handles None data and non-string tokens."""
        settings = WebSettings(admin_token="tok")
        server = QRLiveWebServer(settings, verifier=None)
        assert server._authorized_socket(None) is False
        assert server._authorized_socket({}) is False
        assert server._authorized_socket({"admin_token": 123}) is False
        assert server._authorized_socket({"admin_token": None}) is False
        assert server._authorized_socket({"admin_token": "tok"}) is True

    def test_authorized_request_constant_time(self, web_server_with_token):
        """_authorized_request uses constant-time comparison."""
        client = web_server_with_token.app.test_client()
        # Missing token -> 401
        assert client.post(
            '/api/user-data', json={"user_text": "x"},
            content_type='application/json').status_code == 401
        # Matching token -> 200
        assert client.post(
            '/api/user-data', json={"user_text": "x"},
            content_type='application/json',
            headers={"X-QRLP-Admin-Token": "secret-token"}).status_code == 200


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

    def test_rate_limit_not_bypassed_by_xff(self):
        """Rotating X-Forwarded-For must not bypass the per-peer rate limit."""
        settings = WebSettings(
            host="localhost", port=0, auto_open_browser=False,
            rate_limit_per_minute=3,
        )
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        server = QRLiveWebServer(settings, verifier=QRLiveProtocol(config))
        client = server.app.test_client()

        # Same peer address, distinct (spoofed) X-Forwarded-For values.
        for i in range(3):
            resp = client.get('/api/status',
                              headers={"X-Forwarded-For": f"1.2.3.{i}"})
            assert resp.status_code == 200

        # A new spoofed X-Forwarded-For still cannot reset the budget.
        resp = client.get('/api/status', headers={"X-Forwarded-For": "9.9.9.9"})
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

    def test_cors_requires_an_explicit_origin(self):
        server = QRLiveWebServer(WebSettings(cors_enabled=True))
        response = server.app.test_client().get("/api/status", headers={"Origin": "https://example.com"})
        assert "Access-Control-Allow-Origin" not in response.headers
