"""
Tests for the WebSocket QR-update throughput benchmark.

Covers the in-process benchmark on QRLiveWebServer and the ``qrlp
benchmark-ws`` CLI command.
"""

import json

from click.testing import CliRunner

from src.cli import cli
from src.config import QRLPConfig, WebSettings
from src.core import QRLiveProtocol
from src.web_server import QRLiveWebServer


def _server_with_qr():
    config = QRLPConfig()
    config.blockchain_settings.enabled_chains = set()
    config.time_settings.time_servers = []
    qrlp = QRLiveProtocol(config)
    qr_data, qr_image = qrlp.generate_single_qr({"benchmark": True})
    server = QRLiveWebServer(WebSettings(auto_open_browser=False), verifier=qrlp)
    server.current_qr_data = qr_data
    server.current_qr_image = qr_image
    return server


def test_benchmark_reports_stats():
    server = _server_with_qr()
    results = server.benchmark_websocket_throughput(iterations=30)
    assert results["iterations"] == 30
    assert results["total_seconds"] >= 0
    assert results["avg_ms"] >= 0
    assert results["updates_per_second"] > 0
    assert results["payload_bytes"] > 0
    assert 0 < results["p50_ms"] <= results["p95_ms"] or results["p95_ms"] >= results["p50_ms"]


def test_benchmark_payload_is_valid():
    server = _server_with_qr()
    results = server.benchmark_websocket_throughput(iterations=5)
    assert results["payload_bytes"] == len(
        json.dumps(server._build_qr_update_payload(), default=str)
    )


def test_benchmark_requires_qr_data():
    qrlp = QRLiveProtocol(QRLPConfig())
    server = QRLiveWebServer(WebSettings(auto_open_browser=False), verifier=qrlp)
    # No QR generated yet.
    import pytest

    with pytest.raises(RuntimeError):
        server.benchmark_websocket_throughput(iterations=5)


def test_benchmark_invalid_iterations():
    server = _server_with_qr()
    import pytest

    with pytest.raises(ValueError):
        server.benchmark_websocket_throughput(iterations=0)


def test_cli_benchmark_ws_json():
    runner = CliRunner()
    result = runner.invoke(cli, ["benchmark-ws", "--iterations", "10", "--json-output"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["iterations"] == 10
    assert data["updates_per_second"] > 0


def test_cli_benchmark_ws_text():
    runner = CliRunner()
    result = runner.invoke(cli, ["benchmark-ws", "--iterations", "10"])
    assert result.exit_code == 0, result.output
    assert "WebSocket QR-update throughput benchmark" in result.output
    assert "Updates / second" in result.output
