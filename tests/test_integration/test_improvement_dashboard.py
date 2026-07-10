"""Integration contract tests for the QRLP improvement dashboard."""

import json
from pathlib import Path

from click.testing import CliRunner

import src.cli as cli_module
from src.cli import cli
from src.config import QRLPConfig, WebSettings
from src.core import QRLiveProtocol
from src.crypto import KeyManager
from src.web_server import QRLiveWebServer


def _make_local_qrlp(tmp_path: Path) -> QRLiveProtocol:
    """Create a QRLP verifier without external time or chain services."""
    config = QRLPConfig()
    config.blockchain_settings.enabled_chains = set()
    config.time_settings.time_servers = []
    config.security_settings.key_dir = str(tmp_path / "keys")
    config.security_settings.issuer_id = "dashboard-contract"
    return QRLiveProtocol(
        config,
        key_manager=KeyManager(str(tmp_path / "keys")),
    )


def _make_web_server(tmp_path: Path) -> QRLiveWebServer:
    settings = WebSettings()
    settings.host = "localhost"
    settings.port = 8099
    settings.auto_open_browser = False
    settings.rate_limit_per_minute = 0
    return QRLiveWebServer(settings, verifier=_make_local_qrlp(tmp_path))


def _write_cli_config(path: Path, key_dir: str) -> None:
    path.write_text(
        json.dumps(
            {
                "blockchain_settings": {"enabled_chains": []},
                "time_settings": {"time_servers": []},
                "security_settings": {
                    "key_dir": key_dir,
                    "issuer_id": "dashboard-cli",
                },
                "web_settings": {
                    "host": "localhost",
                    "port": 8099,
                    "auto_open_browser": False,
                    "rate_limit_per_minute": 0,
                },
            }
        ),
        encoding="utf-8",
    )


def test_get_improve_returns_dashboard_html(tmp_path):
    """GET /improve should render the improvement dashboard document."""
    server = _make_web_server(tmp_path)

    with server.app.test_client() as client:
        response = client.get("/improve")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.mimetype == "text/html"
    html = response.get_data(as_text=True).lower()
    assert "<html" in html or "<!doctype html" in html
    assert "dashboard" in html
    assert "improve" in html or "improvement" in html
    assert "smoke" in html


def test_get_improve_status_returns_structured_feature_status_json(tmp_path):
    """GET /api/improve/status should expose dashboard-ready status JSON."""
    server = _make_web_server(tmp_path)

    with server.app.test_client() as client:
        response = client.get("/api/improve/status")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.mimetype == "application/json"

    payload = response.get_json()
    assert set(payload) >= {
        "timestamp",
        "server",
        "readiness",
        "features",
        "trust",
        "keys",
        "configuration",
        "current_qr",
        "verifier",
    }

    readiness = payload["readiness"]
    assert set(readiness) == {"passed", "total", "score", "state"}
    assert isinstance(readiness["passed"], int)
    assert isinstance(readiness["total"], int)
    assert 0 <= readiness["passed"] <= readiness["total"]
    assert 0 <= readiness["score"] <= 1
    assert readiness["state"] in {"ready", "needs_attention"}

    features = payload["features"]
    assert isinstance(features, list)
    assert features
    feature_names = {feature["name"] for feature in features}
    expected_core_features = {
        "signed_qr_generation",
        "public_key_trust_store",
        "web_verify_endpoint",
        "explicit_qr_chunking",
        "admin_token_configured",
        "cors_restricted",
        "rate_limit_configured",
    }
    assert feature_names >= expected_core_features
    for feature in features:
        assert set(feature) == {"name", "ok", "severity"}
        assert isinstance(feature["name"], str)
        assert isinstance(feature["ok"], bool)
        assert feature["severity"] in {"pass", "warn", "fail"}

    assert set(payload["server"]) >= {
        "is_running",
        "server_url",
        "current_qr_available",
    }
    assert payload["server"]["server_url"] == "http://localhost:8099"
    assert set(payload["trust"]) == {"trusted_key_count", "trusted_keys"}
    assert set(payload["keys"]) == {"signing_key_count", "signing_keys"}
    assert set(payload["configuration"]) == {
        "qr_settings",
        "security_settings",
        "web_settings",
    }


def test_post_improve_smoke_test_runs_signed_qr_round_trip(tmp_path):
    """POST /api/improve/smoke-test should prove a local signed QR verifies."""
    server = _make_web_server(tmp_path)

    with server.app.test_client() as client:
        response = client.post("/api/improve/smoke-test", json={})

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert set(payload) >= {
        "success",
        "timestamp",
        "signed_round_trip",
        "chunk_recovery",
        "qr_image_bytes",
        "verification",
    }
    assert payload["success"] is True
    assert payload["qr_image_bytes"] > 0

    round_trip = payload["signed_round_trip"]
    assert set(round_trip) >= {
        "valid",
        "trust_mode",
        "signature_verified",
        "issuer_id",
        "key_id",
    }
    assert round_trip["valid"] is True
    assert round_trip["signature_verified"] is True
    assert round_trip["trust_mode"] in {"local_signature", "public_signature"}
    assert round_trip["issuer_id"] == "dashboard-smoke"
    assert isinstance(round_trip["key_id"], str)
    assert round_trip["key_id"]

    verification = payload["verification"]
    assert verification["valid_json"] is True
    assert verification["valid"] is True
    assert verification["signature_verified"] is True


def test_cli_dashboard_no_browser_can_be_smoke_invoked(monkeypatch):
    """qrlp dashboard --no-browser should start and stop cleanly."""
    runner = CliRunner()
    start_calls = []
    stop_calls = []

    def fake_start_server(self, threaded=True):
        server_call = ("server", threaded, self.settings.auto_open_browser)
        start_calls.append(server_call)
        self.is_running = True

    def fake_stop_server(self):
        stop_calls.append("server")
        self.is_running = False

    def fake_start_live_generation(self):
        start_calls.append(("qrlp",))

    def fake_stop_live_generation(self):
        stop_calls.append("qrlp")

    def interrupt_loop(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(QRLiveWebServer, "start_server", fake_start_server)
    monkeypatch.setattr(QRLiveWebServer, "stop_server", fake_stop_server)
    monkeypatch.setattr(
        QRLiveProtocol,
        "start_live_generation",
        fake_start_live_generation,
    )
    monkeypatch.setattr(
        QRLiveProtocol,
        "stop_live_generation",
        fake_stop_live_generation,
    )
    monkeypatch.setattr(cli_module.time, "sleep", interrupt_loop)

    with runner.isolated_filesystem():
        config_path = Path("dashboard.json")
        _write_cli_config(config_path, "dashboard_keys")

        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_path),
                "dashboard",
                "--no-browser",
            ],
        )

    assert result.exit_code == 0, result.output
    assert ("server", True, False) in start_calls
    assert ("qrlp",) in start_calls
    assert stop_calls == ["qrlp", "server"]
    assert "dashboard" in result.output.lower()
    assert "/improve" in result.output
