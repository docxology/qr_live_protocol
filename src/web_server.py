"""Local QR overlays, verification endpoints, and live update transports."""

import base64
import hmac
import json
import logging
import os
import re
import secrets
import tempfile
import threading
import time
import webbrowser
from collections import deque
from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit

import bleach
from flask import Flask, Response, abort, g, jsonify, render_template, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Security imports
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from werkzeug.serving import BaseWSGIServer, make_server

from .config import WebSettings
from .core import QRData

_logger = logging.getLogger("qrlp.web_server")
_MAX_REQUEST_BYTES = 128 * 1024
_RATE_WINDOW_SECONDS = 60
_MAX_RATE_CLIENTS = 4096
_HEARTBEAT_SECONDS = 15
_MAX_EVENT_STREAMS = 64


def _is_loopback(address: str | None) -> bool:
    if not address:
        return False
    if address.lower().rstrip(".") == "localhost":
        return True
    try:
        return ip_address(address).is_loopback
    except ValueError:
        return False


class SecurityValidator:
    """
    Input validation and security utilities for web server.

    This class provides comprehensive input validation and sanitization methods
    to prevent common web vulnerabilities including XSS, injection attacks,
    and malformed data.

    Security Measures:
        - Length validation to prevent DoS attacks
        - Character whitelisting for user input
        - HTML tag stripping to prevent XSS
        - JSON structure validation
        - Type checking for all inputs

    Example Usage:
        ```python
        # Validate user text input
        try:
            safe_text = SecurityValidator.validate_user_text(user_input)
        except BadRequest as e:
            return jsonify({"error": str(e)}), 400

        # Validate QR data
        try:
            safe_qr_data = SecurityValidator.validate_qr_data(qr_json)
        except BadRequest as e:
            return jsonify({"error": str(e)}), 400
        ```
    """

    # Maximum lengths for input validation
    MAX_USER_TEXT_LENGTH = 1000
    MAX_QR_DATA_LENGTH = 10000

    # Allowed characters for user text (basic sanitization)
    ALLOWED_USER_TEXT_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!?()]+$')

    @staticmethod
    def validate_user_text(text: str) -> str:
        """
        Validate and sanitize user text input.

        Performs comprehensive validation including:
        - Type checking
        - Length validation
        - HTML tag stripping
        - Character whitelisting

        Args:
            text: User-provided text input

        Returns:
            str: Sanitized and validated text

        Raises:
            BadRequest: If validation fails

        Example:
            ```python
            safe_text = SecurityValidator.validate_user_text("Hello, World!")
            ```
        """
        if not isinstance(text, str):
            raise BadRequest("User text must be a string")

        if len(text) > SecurityValidator.MAX_USER_TEXT_LENGTH:
            raise BadRequest(f"User text too long (max {SecurityValidator.MAX_USER_TEXT_LENGTH} characters)")

        # Basic sanitization - remove potentially dangerous characters
        sanitized = bleach.clean(text, tags=[], attributes={})
        sanitized = sanitized.strip()

        # Additional pattern validation
        if sanitized and not SecurityValidator.ALLOWED_USER_TEXT_PATTERN.fullmatch(sanitized):
            raise BadRequest("User text contains invalid characters")

        return sanitized

    @staticmethod
    def validate_qr_data(qr_data: str) -> str:
        """
        Validate QR data input.

        Ensures QR data is well-formed JSON within size limits.

        Args:
            qr_data: QR data as JSON string

        Returns:
            str: Validated QR data

        Raises:
            BadRequest: If validation fails

        Example:
            ```python
            safe_qr = SecurityValidator.validate_qr_data(qr_json_string)
            ```
        """
        if not isinstance(qr_data, str):
            raise BadRequest("QR data must be a string")

        if len(qr_data) > SecurityValidator.MAX_QR_DATA_LENGTH:
            raise BadRequest(f"QR data too large (max {SecurityValidator.MAX_QR_DATA_LENGTH} characters)")

        # Basic JSON validation
        try:
            parsed = json.loads(qr_data)
            if not isinstance(parsed, dict):
                raise BadRequest("QR data must be a JSON object")
        except (ValueError, RecursionError) as e:
            raise BadRequest("Invalid QR data JSON") from e

        return qr_data

    @staticmethod
    def validate_json_input(data: Any) -> dict[str, Any]:
        """
        Validate JSON input data.

        Args:
            data: Input data to validate

        Returns:
            Dict[str, Any]: Validated dictionary

        Raises:
            BadRequest: If data is not a dictionary

        Example:
            ```python
            validated = SecurityValidator.validate_json_input(request.get_json())
            ```
        """
        if not isinstance(data, dict):
            raise BadRequest("Request body must be a JSON object")

        return data


# Security middleware
def security_middleware(app: Flask, settings: WebSettings) -> None:
    """Add security middleware to Flask app."""
    request_log: dict[str, deque[float]] = {}
    request_log_lock = threading.Lock()

    @app.before_request
    def validate_request():
        """Validate incoming requests."""
        g.script_nonce = secrets.token_urlsafe(24)
        if settings.rate_limit_per_minute > 0:
            # Key rate limiting on the peer address only. The X-Forwarded-For
            # header is attacker-controlled unless a trusted reverse proxy is
            # guaranteed to overwrite it, so trusting it here would let clients
            # rotate the header to bypass the limit.
            client_id = request.remote_addr or "unknown"
            with request_log_lock:
                now = time.monotonic()
                window_start = now - _RATE_WINDOW_SECONDS
                if client_id not in request_log:
                    if len(request_log) >= _MAX_RATE_CLIENTS:
                        for peer, history in list(request_log.items()):
                            if history[-1] <= window_start:
                                del request_log[peer]
                        if len(request_log) >= _MAX_RATE_CLIENTS:
                            abort(429, "Rate limit capacity reached")
                    request_log[client_id] = deque()
                timestamps = request_log[client_id]
                while timestamps and timestamps[0] <= window_start:
                    timestamps.popleft()
                if len(timestamps) >= settings.rate_limit_per_minute:
                    abort(429, "Rate limit exceeded")
                timestamps.append(now)

        # Check Content-Type for POST requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            if request.mimetype != "application/json":
                abort(400, "Content-Type must be application/json")

    @app.errorhandler(BadRequest)
    def handle_bad_request(e):
        """Handle validation errors."""
        return jsonify({
            "error": "Bad Request",
            "message": str(e),
            "timestamp": datetime.now(UTC).isoformat()
        }), 400

    @app.errorhandler(500)
    def handle_internal_error(e):
        """Handle internal server errors."""
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.now(UTC).isoformat()
        }), 500

    @app.errorhandler(429)
    def handle_rate_limit(e):
        """Handle rate limit errors."""
        return jsonify({
            "error": "Too Many Requests",
            "message": str(e),
            "timestamp": datetime.now(UTC).isoformat()
        }), 429

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_request(e):
        return jsonify({"error": e.description}), 413

    @app.after_request
    def add_security_headers(response):
        """Add Content-Security-Policy and other security headers to all responses."""
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; "
            f"script-src 'self' 'nonce-{g.script_nonce}'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self';"
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.context_processor
    def template_security():
        return {"script_nonce": g.script_nonce}


class QRLiveWebServer:
    """
    Web server for QRLP live QR display.

    Provides real-time web interface showing QR codes with verification
    information, suitable for livestreaming and official video releases.
    """

    def __init__(self, settings: WebSettings, verifier: Any | None = None):
        """
        Initialize web server with settings.

        Args:
            settings: WebSettings configuration object
            verifier: Optional QRLiveProtocol-compatible verifier
        """
        self.settings = settings
        self.verifier = verifier
        self.app = Flask(__name__,
                        template_folder=self._get_template_dir(),
                        static_folder=self._get_static_dir())

        self.app.config.update(SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=_MAX_REQUEST_BYTES)
        self.app.debug = settings.debug

        origins = settings.cors_allowed_origins if settings.cors_enabled else []
        if origins:
            CORS(self.app, origins=origins)

        self.socketio = SocketIO(
            self.app, async_mode="threading", cors_allowed_origins=origins or None,
            max_http_buffer_size=_MAX_REQUEST_BYTES,
        )

        # Apply security middleware
        security_middleware(self.app, self.settings)

        # State management
        self.current_qr_data: QRData | None = None
        self.current_qr_image: bytes | None = None
        self._published_at: str | None = None
        self._frame_revision = 0
        self._stream_epoch = 0
        self._changed = threading.Condition()
        self._http_server: BaseWSGIServer | None = None
        self._server_thread: threading.Thread | None = None
        self.is_running = False
        self.update_callback: Callable | None = None

        # User input for QR codes
        self.user_input_data: str | None = None

        # Statistics
        self.page_views = 0
        self.websocket_connections = 0
        self.event_stream_connections = 0
        self.qr_updates_sent = 0

        # Setup routes
        self._setup_routes()
        self._setup_websocket_events()

    def start_server(self, threaded: bool = True) -> None:
        """Bind the listener before returning or entering the server loop."""
        with self._changed:
            if self._http_server is not None:
                return
            try:
                server = make_server(self.settings.host, self.settings.port, self.app, threaded=True)
            except (OSError, SystemExit) as exc:
                raise RuntimeError(f"Could not bind QRLP web server at {self.get_server_url()}") from exc
            self._http_server = server
            self.is_running = True
            if threaded:
                self._server_thread = threading.Thread(
                    target=self._run_server, args=(server,), daemon=True, name="QRLP-WebServer",
                )
                try:
                    self._server_thread.start()
                except RuntimeError:
                    self._server_thread = None
                    self._http_server = None
                    self.is_running = False
                    server.server_close()
                    raise
            if self.settings.auto_open_browser:
                browser_timer = threading.Timer(0.1, self._open_browser)
                browser_timer.daemon = True
                try:
                    browser_timer.start()
                except RuntimeError:
                    _logger.warning("Could not schedule browser launch. Open the server URL manually.")
            if threaded:
                return
        self._run_server(server)

    def stop_server(self) -> None:
        """Stop accepting requests and close current overlay streams."""
        with self._changed:
            server, thread = self._http_server, self._server_thread
            if not self.is_running:
                return
            self.is_running = False
            self._stream_epoch += 1
            self._changed.notify_all()

        if server is not None:
            server.shutdown()
        if thread is not None:
            thread.join()

    def update_qr_display(self, qr_data: QRData, qr_image: bytes) -> None:
        """
        Update the QR code display with new data.

        Args:
            qr_data: QR data object
            qr_image: QR code image as bytes
        """
        with self._changed:
            self.current_qr_data = deepcopy(qr_data)
            self.current_qr_image = qr_image
            self._published_at = datetime.now(UTC).isoformat()
            self._frame_revision += 1
            self._changed.notify_all()
            if self.is_running or self.websocket_connections:
                self._broadcast_qr_update()

    def get_server_url(self) -> str:
        """Get the server URL."""
        with self._changed:
            port = self._http_server.port if self._http_server else self.settings.port
        host = self.settings.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{port}"

    def get_statistics(self) -> dict[str, Any]:
        """Get web server statistics."""
        with self._changed:
            return {
                "is_running": self.is_running,
                "page_views": self.page_views,
                "websocket_connections": self.websocket_connections,
                "event_stream_connections": self.event_stream_connections,
                "qr_updates_sent": self.qr_updates_sent,
                "server_url": self.get_server_url(),
                "current_qr_available": bool(self.current_qr_data and self.current_qr_image),
            }

    def get_user_data(self) -> str | None:
        """Get current user input data for QR generation."""
        with self._changed:
            return self.user_input_data

    def _set_user_data(self, data: dict[str, Any]) -> str | None:
        text = SecurityValidator.validate_user_text(data.get("user_text")) or None
        with self._changed:
            self.user_input_data = text
            self.socketio.emit("user_data_updated", {"user_data": text, "timestamp": datetime.now(UTC).isoformat()})
        return text

    def _setup_routes(self) -> None:
        """Setup Flask routes."""

        @self.app.route('/')
        def index():
            """Main QR display page."""
            with self._changed:
                self.page_views += 1
            return render_template(
                'index.html', server_url=self.get_server_url(), settings=self._public_web_settings(),
            )

        @self.app.route('/api/qr/current')
        def get_current_qr():
            """API endpoint for current QR data."""
            payload = self._build_qr_update_payload()
            if payload is None:
                return jsonify({"error": "No QR data available"}), 404
            return jsonify(payload), 200, {"Cache-Control": "no-store"}

        @self.app.get('/api/qr/events')
        def qr_events():
            """Stream the latest QR frames to native browser EventSource clients."""
            with self._changed:
                if self.event_stream_connections >= _MAX_EVENT_STREAMS:
                    return jsonify({"error": "Too many active QR streams"}), 503
                self.event_stream_connections += 1
                epoch = self._stream_epoch
            response = Response(
                self._stream_qr_events(epoch), mimetype="text/event-stream",
                headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
            )
            response.call_on_close(self._close_event_stream)
            return response

        @self.app.route('/api/status')
        def get_status():
            """API endpoint for server status."""
            return jsonify(self.get_statistics())

        @self.app.route('/status')
        def get_status_simple():
            """Simple status endpoint for /status route."""
            return jsonify(self.get_statistics())

        @self.app.route('/api/verify', methods=['POST'])
        def verify_qr():
            """API endpoint for QR verification."""
            try:
                # Validate input
                data = SecurityValidator.validate_json_input(request.get_json())
                qr_json = data.get('qr_data')

                if not qr_json:
                    return jsonify({"error": "No QR data provided"}), 400

                # Validate QR data format
                validated_qr_data = SecurityValidator.validate_qr_data(qr_json)

                verifier = self._get_verifier()
                verification_result = verifier.verify_qr_data(validated_qr_data)
                verification_result["timestamp"] = datetime.now(UTC).isoformat()
                verification_result["data_length"] = len(validated_qr_data)

                return jsonify(verification_result)

            except BadRequest as e:
                return jsonify({"error": str(e)}), 400
            except RequestEntityTooLarge:
                raise
            except Exception:
                _logger.exception("QR verification failed")
                return jsonify({"error": "Internal server error"}), 500

        @self.app.route('/viewer')
        def viewer():
            """QR viewer page for external displays."""
            return render_template('viewer.html', requires_admin_token=bool(self.settings.admin_token))

        @self.app.route('/admin')
        def admin():
            """Admin interface for monitoring."""
            return render_template('admin.html', statistics=self.get_statistics())

        @self.app.route('/improve')
        def improve_dashboard():
            """Improvement dashboard for verification and readiness checks."""
            return render_template('improve.html',
                                 server_url=self.get_server_url(),
                                 requires_admin_token=bool(self.settings.admin_token))

        @self.app.route('/api/improve/status')
        def improve_status():
            """API endpoint for improvement dashboard status."""
            return jsonify(self._get_improvement_status())

        @self.app.route('/api/improve/smoke-test', methods=['POST'])
        def improve_smoke_test():
            """Run a local signed-QR and chunk-recovery smoke test."""
            try:
                if not self._authorized_request():
                    return jsonify({"error": "Unauthorized"}), 401
                SecurityValidator.validate_json_input(request.get_json())
                return jsonify(self._run_improvement_smoke_test())
            except BadRequest as e:
                return jsonify({"error": str(e)}), 400
            except RequestEntityTooLarge:
                raise
            except Exception:
                _logger.exception("Improvement smoke test failed")
                return jsonify({
                    "success": False,
                    "error": "Internal server error",
                    "timestamp": datetime.now(UTC).isoformat(),
                }), 500

        @self.app.route('/api/user-data', methods=['POST'])
        def update_user_data():
            """API endpoint for updating user data."""
            try:
                if not self._authorized_request():
                    return jsonify({"error": "Unauthorized"}), 401

                data = SecurityValidator.validate_json_input(request.get_json())
                return jsonify({
                    "success": True,
                    "message": "User data updated successfully",
                    "user_data": self._set_user_data(data),
                    "timestamp": datetime.now(UTC).isoformat()
                })

            except BadRequest as e:
                return jsonify({"error": str(e)}), 400
            except RequestEntityTooLarge:
                raise
            except Exception:
                _logger.exception("User data update failed")
                return jsonify({"error": "Internal server error"}), 500

        @self.app.route('/api/user-data', methods=['GET'])
        def get_user_data():
            """API endpoint for getting current user data."""
            return jsonify({"user_data": self.get_user_data()})

    def _setup_websocket_events(self) -> None:
        """Setup SocketIO events for real-time updates."""

        @self.socketio.on('connect')
        def handle_connect(_auth=None):
            """Handle client connection."""
            with self._changed:
                self.websocket_connections += 1
            self._send_qr_update_to_client()

        @self.socketio.on('disconnect')
        def handle_disconnect(_reason=None):
            """Handle client disconnection."""
            with self._changed:
                self.websocket_connections -= 1

        @self.socketio.on('request_qr_update')
        def handle_qr_request():
            """Handle client request for QR update."""
            self._send_qr_update_to_client()

        @self.socketio.on('update_user_data')
        def handle_user_data_update(data=None):
            """Handle user data update from client."""
            try:
                data = SecurityValidator.validate_json_input(data)
                if not self._authorized_socket(data):
                    emit('user_data_error', {"error": "Unauthorized"})
                    return
                self._set_user_data(data)
            except BadRequest as e:
                emit('user_data_error', {"error": str(e)})
            except Exception:
                _logger.exception("Socket.IO user data update failed")
                emit('user_data_error', {"error": "Internal server error"})

    def _broadcast_qr_update(self) -> None:
        """Broadcast QR update to all connected clients."""
        with self._changed:
            payload = self._build_qr_update_payload()
            if payload is not None:
                self.socketio.emit('qr_update', payload)
                self.qr_updates_sent += 1

    def _send_qr_update_to_client(self) -> None:
        """Send QR update to requesting client."""
        payload = self._build_qr_update_payload()
        if payload is not None:
            emit('qr_update', payload)

    def _build_qr_update_payload(self) -> dict[str, Any] | None:
        """Encode a consistent data and image pair for every transport."""
        with self._changed:
            qr_data, qr_image, published_at = self.current_qr_data, self.current_qr_image, self._published_at
        if qr_data is None or not qr_image:
            return None
        image_b64 = base64.b64encode(qr_image).decode('ascii')
        mime_type = "image/jpeg" if qr_image.startswith(b"\xff\xd8\xff") else "image/png"
        qr_json = qr_data.to_json()
        return {
            "qr_data": json.loads(qr_json),
            "qr_json": qr_json,
            "qr_image": f"data:{mime_type};base64,{image_b64}",
            "timestamp": published_at or qr_data.timestamp,
        }

    def _stream_qr_events(self, epoch: int) -> Iterator[str]:
        revision = -1
        while True:
            with self._changed:
                self._changed.wait_for(
                    lambda: self._frame_revision != revision or self._stream_epoch != epoch,
                    timeout=_HEARTBEAT_SECONDS,
                )
                if self._stream_epoch != epoch:
                    return
                payload = self._build_qr_update_payload() if self._frame_revision != revision else None
                revision = self._frame_revision
            if payload is None:
                yield ": heartbeat\n\n"
            else:
                yield f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"

    def _close_event_stream(self) -> None:
        with self._changed:
            self.event_stream_connections -= 1

    def benchmark_websocket_throughput(self, iterations: int = 100) -> dict:
        """
        Benchmark WebSocket QR-update throughput (payload build + encode cost).

        Measures the per-update latency of building the broadcast payload for
        ``iterations`` simulated socket clients and reports the aggregate
        throughput. Runs entirely in-process (no network transport required).

        Args:
            iterations: Number of simulated client updates to benchmark.

        Returns:
            A dict with latency/throughput statistics.
        """
        if iterations < 1:
            raise ValueError("iterations must be at least 1")
        if self.current_qr_data is None or self.current_qr_image is None:
            raise RuntimeError(
                "No current QR data; generate a QR before benchmarking"
            )

        latencies = []
        start = time.perf_counter()
        for _ in range(iterations):
            t0 = time.perf_counter()
            payload = self._build_qr_update_payload()
            latencies.append(time.perf_counter() - t0)
            if payload is None:
                raise RuntimeError("QR payload was empty during benchmark")
        total = time.perf_counter() - start

        latencies.sort()
        n = len(latencies)
        return {
            "iterations": n,
            "total_seconds": total,
            "avg_ms": (sum(latencies) / n) * 1000,
            "p50_ms": latencies[n // 2] * 1000,
            "p95_ms": latencies[int(n * 0.95) - 1] * 1000,
            "updates_per_second": n / total if total > 0 else 0.0,
            "payload_bytes": len(
                json.dumps(self._build_qr_update_payload(), default=str)
            ),
            "simulated_clients": 1,
        }

    def _run_server(self, server: BaseWSGIServer) -> None:
        """Run the local WSGI server without the interactive debugger or reloader."""
        try:
            _logger.info("QRLP web server listening at %s", self.get_server_url())
            server.serve_forever(poll_interval=0.1)
        finally:
            with self._changed:
                self.is_running = False
                self._http_server = None
                self._server_thread = None
                self._stream_epoch += 1
                self._changed.notify_all()

    def _open_browser(self) -> None:
        """Open browser to server URL."""
        if not self.is_running:
            return
        try:
            webbrowser.open(self.get_server_url())
        except Exception as e:
            _logger.warning(f"Could not open browser: {e}")

    def open_improve_dashboard(self) -> None:
        """Open browser directly to the improvement dashboard."""
        try:
            webbrowser.open(f"{self.get_server_url()}/improve")
        except Exception as e:
            _logger.warning(f"Could not open improve dashboard: {e}")

    def _get_verifier(self):
        """Return configured verifier, creating a local default if needed."""
        with self._changed:
            if self.verifier is None:
                from .config import QRLPConfig
                from .core import QRLiveProtocol

                config = QRLPConfig()
                config.blockchain_settings.enabled_chains = set()
                config.time_settings.time_servers = []
                self.verifier = QRLiveProtocol(config)
            return self.verifier

    def _get_improvement_status(self) -> dict[str, Any]:
        """Return dashboard-ready implementation and readiness status."""
        verifier = self._get_verifier()
        verifier_stats = verifier.get_statistics() if hasattr(verifier, "get_statistics") else {}
        if isinstance(verifier_stats.get("current_qr_data"), dict):
            verifier_stats = dict(verifier_stats)
            verifier_stats["current_qr_data"] = {
                name: value for name, value in verifier_stats["current_qr_data"].items()
                if name != "ots_proof_path"
            }
        config = getattr(verifier, "config", None)
        key_manager = getattr(verifier, "key_manager", None)
        trust_store = getattr(verifier, "trust_store", None)

        signing_keys = []
        if key_manager is not None and hasattr(key_manager, "list_keys"):
            for key_id, key_info in key_manager.list_keys().items():
                signing_keys.append({
                    "key_id": key_id,
                    "algorithm": getattr(key_info, "algorithm", None),
                    "purpose": getattr(key_info, "purpose", None),
                    "usage_count": getattr(key_info, "usage_count", 0),
                })

        trusted_keys = []
        if trust_store is not None and hasattr(trust_store, "list_public_keys"):
            trusted_keys = [
                {
                    "issuer_id": key.issuer_id,
                    "key_id": key.key_id,
                    "algorithm": key.algorithm,
                }
                for key in trust_store.list_public_keys()
            ]

        features = [
            self._feature_status("signed_qr_generation", callable(getattr(verifier, "generate_signed_qr", None)), "fail"),
            self._feature_status("public_key_trust_store", trust_store is not None, "fail"),
            self._feature_status("web_verify_endpoint", callable(getattr(verifier, "verify_qr_data", None)), "fail"),
            self._feature_status(
                "explicit_qr_chunking",
                callable(getattr(getattr(verifier, "qr_generator", None), "generate_chunked_payloads", None)),
                "fail",
            ),
            self._feature_status("admin_token_configured", bool(self.settings.admin_token), "warn"),
            self._feature_status(
                "cors_restricted",
                not self.settings.cors_enabled or "*" not in self.settings.cors_allowed_origins,
                "warn",
            ),
            self._feature_status("rate_limit_configured", self.settings.rate_limit_per_minute > 0, "fail"),
        ]

        optional_features = {"admin_token_configured", "cors_restricted"}
        required_features = [feature for feature in features if feature["name"] not in optional_features]
        passed = sum(1 for feature in required_features if feature["ok"])
        with self._changed:
            current_qr = json.loads(self.current_qr_data.to_json()) if self.current_qr_data else None
        security = config.security_settings if config else None

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "server": self.get_statistics(),
            "readiness": {
                "passed": passed,
                "total": len(required_features),
                "score": round(passed / len(required_features), 2),
                "state": "ready" if passed == len(required_features) else "needs_attention",
            },
            "features": features,
            "trust": {
                "trusted_key_count": len(trusted_keys),
                "trusted_keys": trusted_keys,
            },
            "keys": {
                "signing_key_count": len(signing_keys),
                "signing_keys": signing_keys,
            },
            "configuration": {
                "qr_settings": asdict(config.qr_settings) if config else {},
                "security_settings": {
                    "encrypt_qr_data": security.encrypt_qr_data,
                    "sign_qr_data": security.sign_qr_data,
                    "issuer_id": security.issuer_id,
                    "event_id": security.event_id,
                    "signing_key_id": security.signing_key_id,
                    "signature_algorithm": security.signature_algorithm,
                    "qr_ttl_seconds": security.qr_ttl_seconds,
                } if security else {},
                "web_settings": self._public_web_settings(),
            },
            "current_qr": current_qr,
            "verifier": verifier_stats,
        }

    def _run_improvement_smoke_test(self) -> dict[str, Any]:
        """Run a deterministic local smoke test for dashboard controls."""
        from .config import QRLPConfig
        from .core import QRLiveProtocol
        from .qr_generator import QRGenerator
        from .trust import TrustStore

        with tempfile.TemporaryDirectory(prefix="qrlp-improve-") as key_dir:
            config = QRLPConfig()
            config.blockchain_settings.enabled_chains = set()
            config.time_settings.time_servers = []
            config.security_settings.key_dir = key_dir
            config.security_settings.issuer_id = "dashboard-smoke"
            config.security_settings.sign_qr_data = True

            generator_payload = "dashboard-chunk-" * 500
            qrlp = QRLiveProtocol(config)
            qr_data, qr_image = qrlp.generate_single_qr(
                user_data={"dashboard_smoke": True},
                sign_data=True,
            )

            public_key = qrlp.key_manager.export_public_key(qr_data.signing_key_id)
            trust_store = TrustStore()
            trust_store.add_public_key(
                qr_data.issuer_id,
                qr_data.signing_key_id,
                public_key,
                qr_data.signature_algorithm,
            )
            verifier_config = replace(
                config,
                security_settings=replace(
                    config.security_settings, key_dir=os.path.join(key_dir, "verifier"),
                ),
            )
            verifier = QRLiveProtocol(verifier_config, trust_store=trust_store)
            verification = verifier.verify_qr_data(qr_data.to_json())

            chunk_payloads = qrlp.qr_generator.generate_chunked_payloads(generator_payload)
            reassembled = QRGenerator.reassemble_chunked_payloads(list(reversed(chunk_payloads)))
            chunk_ok = reassembled == generator_payload and len(chunk_payloads) > 1

            return {
                "success": bool(verification.get("valid")) and chunk_ok and len(qr_image) > 0,
                "timestamp": datetime.now(UTC).isoformat(),
                "signed_round_trip": {
                    "valid": verification.get("valid"),
                    "trust_mode": verification.get("trust_mode"),
                    "signature_verified": verification.get("signature_verified"),
                    "issuer_id": qr_data.issuer_id,
                    "key_id": qr_data.signing_key_id,
                },
                "chunk_recovery": {
                    "valid": chunk_ok,
                    "chunk_count": len(chunk_payloads),
                    "payload_size": len(generator_payload.encode("utf-8")),
                },
                "qr_image_bytes": len(qr_image),
                "verification": verification,
            }

    @staticmethod
    def _feature_status(name: str, ok: bool, severity: str) -> dict[str, Any]:
        return {
            "name": name,
            "ok": ok,
            "severity": "pass" if ok else severity,
        }

    def _public_web_settings(self) -> dict[str, Any]:
        return {
            "host": self.settings.host,
            "port": self.settings.port,
            "auto_open_browser": self.settings.auto_open_browser,
            "debug": self.settings.debug,
            "cors_enabled": self.settings.cors_enabled,
            "cors_allowed_origins": self.settings.cors_allowed_origins,
            "rate_limit_per_minute": self.settings.rate_limit_per_minute,
        }

    def _authorized_request(self) -> bool:
        if not self.settings.admin_token:
            return self._allows_unauthenticated_write()

        token = request.headers.get("X-QRLP-Admin-Token")
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ").strip()
        return self._token_matches(token)

    def _authorized_socket(self, data: dict[str, Any] | None) -> bool:
        if not self.settings.admin_token:
            return self._allows_unauthenticated_write()
        return self._token_matches(data.get("admin_token") if isinstance(data, dict) else None)

    def _allows_unauthenticated_write(self) -> bool:
        origin = request.headers.get("Origin")
        try:
            host = urlsplit(request.host_url).hostname
        except ValueError:
            return False
        return (
            _is_loopback(self.settings.host)
            and _is_loopback(request.remote_addr)
            and _is_loopback(host)
            and (origin is None or origin == request.host_url.rstrip("/"))
        )

    def _token_matches(self, supplied: object) -> bool:
        expected = self.settings.admin_token
        if not isinstance(supplied, str) or not expected:
            return False
        try:
            return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))
        except UnicodeEncodeError:
            return False

    def _get_template_dir(self) -> str:
        """Get template directory path."""
        if os.path.isabs(self.settings.template_dir):
            return self.settings.template_dir

        module_dir = os.path.dirname(__file__)
        if self.settings.template_dir == "templates":
            installed = os.path.join(module_dir, "templates")
            if os.path.isdir(installed):
                return installed
        return os.path.join(os.path.dirname(module_dir), self.settings.template_dir)

    def _get_static_dir(self) -> str:
        """Get static files directory path."""
        if os.path.isabs(self.settings.static_dir):
            return self.settings.static_dir

        # Relative to project root directory (one level up from src)
        project_root = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(project_root, self.settings.static_dir)
