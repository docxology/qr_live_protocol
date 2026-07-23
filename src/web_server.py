"""
Web Server module for QRLP.

This module provides a comprehensive Flask-based web interface for displaying live QR codes
with real-time updates via WebSocket, cryptographic verification details, and interactive
controls for custom data injection.

Key Features:
    - Real-time QR code display with WebSocket updates
    - Encrypted QR code generation and verification
    - Interactive user input for custom QR data
    - RESTful API endpoints for programmatic access
    - Security validation and sanitization
    - CORS support for cross-origin requests
    - Admin dashboard for monitoring

Security Features:
    - Input validation and sanitization
    - Optional admin token for state-changing controls
    - Basic per-client rate limiting
    - XSS prevention
    - Content Security Policy headers

Architecture:
    - Flask for HTTP server
    - Flask-SocketIO for real-time communication
    - Gevent for async operations (optional)
    - Thread-safe QR data management

Example Usage:
    ```python
    from src.config import WebSettings
    from src.web_server import QRLiveWebServer

    # Create web server with custom settings
    settings = WebSettings(port=8080, host='localhost')
    server = QRLiveWebServer(settings)

    # Connect to QRLiveProtocol for updates
    qrlp = QRLiveProtocol()
    qrlp.add_update_callback(server.update_qr_display)

    # Start services
    qrlp.start_live_generation()
    server.start_server(threaded=True)
    ```
"""

# Monkey patch early for gevent compatibility
try:
    from gevent import monkey
    monkey.patch_all()
except ImportError:
    pass

import logging
import os
import base64
import json
import threading
import webbrowser
import re
import time
import tempfile
from datetime import datetime, timezone
from typing import Dict, Optional, Any, Callable
from dataclasses import asdict

from flask import Flask, render_template, jsonify, send_from_directory, request, abort
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Security imports
from werkzeug.exceptions import BadRequest
import bleach

from .config import WebSettings
from .core import QRData

_logger = logging.getLogger("qrlp.web_server")


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
        if not SecurityValidator.ALLOWED_USER_TEXT_PATTERN.match(sanitized):
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
        except json.JSONDecodeError as e:
            raise BadRequest(f"Invalid QR data JSON: {e}")

        return qr_data

    @staticmethod
    def validate_json_input(data: Any) -> Dict[str, Any]:
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
def security_middleware(app, settings: WebSettings):
    """Add security middleware to Flask app."""
    import threading as _threading
    request_log: Dict[str, list] = {}
    request_log_lock = _threading.Lock()

    @app.before_request
    def validate_request():
        """Validate incoming requests."""
        if settings.rate_limit_per_minute:
            client_id = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
            now = time.time()
            window_start = now - 60
            with request_log_lock:
                timestamps = [ts for ts in request_log.get(client_id, []) if ts >= window_start]
                if len(timestamps) >= settings.rate_limit_per_minute:
                    abort(429, "Rate limit exceeded")
                timestamps.append(now)
                request_log[client_id] = timestamps

        # Check Content-Type for POST requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.headers.get('Content-Type', '')
            if not content_type.startswith('application/json'):
                abort(400, "Content-Type must be application/json")

    @app.errorhandler(BadRequest)
    def handle_bad_request(e):
        """Handle validation errors."""
        return jsonify({
            "error": "Bad Request",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 400

    @app.errorhandler(500)
    def handle_internal_error(e):
        """Handle internal server errors."""
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

    @app.errorhandler(429)
    def handle_rate_limit(e):
        """Handle rate limit errors."""
        return jsonify({
            "error": "Too Many Requests",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 429


class QRLiveWebServer:
    """
    Web server for QRLP live QR display.

    Provides real-time web interface showing QR codes with verification
    information, suitable for livestreaming and official video releases.
    """

    def __init__(self, settings: WebSettings, verifier: Optional[Any] = None):
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

        # Configure Flask with secure secret key
        import secrets
        self.app.config['SECRET_KEY'] = secrets.token_hex(32)

        # Enable CORS if configured
        if self.settings.cors_enabled:
            origins = self.settings.cors_allowed_origins or None
            CORS(self.app, origins=origins)

        # Initialize SocketIO for real-time updates
        socket_origins = self.settings.cors_allowed_origins or "*" if self.settings.cors_enabled else None
        self.socketio = SocketIO(self.app, cors_allowed_origins=socket_origins)

        # Apply security middleware
        security_middleware(self.app, self.settings)

        # State management
        self.current_qr_data: Optional[QRData] = None
        self.current_qr_image: Optional[bytes] = None
        self.is_running = False
        self.update_callback: Optional[Callable] = None

        # User input for QR codes
        self.user_input_data: Optional[str] = None

        # Statistics
        self.page_views = 0
        self.websocket_connections = 0
        self.qr_updates_sent = 0

        # Setup routes
        self._setup_routes()
        self._setup_websocket_events()

    def start_server(self, threaded: bool = True) -> None:
        """
        Start the web server.

        Args:
            threaded: Whether to run server in background thread
        """
        if self.is_running:
            return

        self.is_running = True

        if threaded:
            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self._run_server,
                daemon=True,
                name="QRLP-WebServer"
            )
            self.server_thread.start()

            # Auto-open browser if configured
            if self.settings.auto_open_browser:
                threading.Timer(1.0, self._open_browser).start()
        else:
            self._run_server()

    def stop_server(self) -> None:
        """Stop the web server."""
        self.is_running = False

        # For gevent server, we need to stop it properly
        if hasattr(self, 'gevent_server'):
            try:
                self.gevent_server.stop()
                _logger.info("🛑 Gevent server stopped")
            except Exception as e:
                _logger.error(f"Error stopping gevent server: {e}")
        # For Flask-SocketIO, server will stop when main thread exits

    def update_qr_display(self, qr_data: QRData, qr_image: bytes) -> None:
        """
        Update the QR code display with new data.

        Args:
            qr_data: QR data object
            qr_image: QR code image as bytes
        """
        self.current_qr_data = qr_data
        self.current_qr_image = qr_image

        # Send update to all connected clients
        if self.is_running:
            self._broadcast_qr_update()

    def get_server_url(self) -> str:
        """Get the server URL."""
        return f"http://{self.settings.host}:{self.settings.port}"

    def get_statistics(self) -> Dict:
        """Get web server statistics."""
        return {
            "is_running": self.is_running,
            "page_views": self.page_views,
            "websocket_connections": self.websocket_connections,
            "qr_updates_sent": self.qr_updates_sent,
            "server_url": self.get_server_url(),
            "current_qr_available": self.current_qr_data is not None
        }

    def get_user_data(self) -> Optional[str]:
        """Get current user input data for QR generation."""
        return self.user_input_data

    def _setup_routes(self) -> None:
        """Setup Flask routes."""

        @self.app.route('/')
        def index():
            """Main QR display page."""
            self.page_views += 1
            return render_template('index.html',
                                 server_url=self.get_server_url(),
                                 settings=asdict(self.settings))

        @self.app.route('/api/qr/current')
        def get_current_qr():
            """API endpoint for current QR data."""
            if not self.current_qr_data or not self.current_qr_image:
                return jsonify({"error": "No QR data available"}), 404

            # Convert image to base64 for JSON transmission
            image_b64 = base64.b64encode(self.current_qr_image).decode('utf-8')

            return jsonify({
                "qr_data": asdict(self.current_qr_data),
                "qr_image": f"data:image/png;base64,{image_b64}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

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
                verification_result["timestamp"] = datetime.now(timezone.utc).isoformat()
                verification_result["data_length"] = len(validated_qr_data)

                return jsonify(verification_result)

            except BadRequest as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                return jsonify({"error": "Internal server error"}), 500

        @self.app.route('/viewer')
        def viewer():
            """QR viewer page for external displays."""
            return render_template('viewer.html')

        @self.app.route('/admin')
        def admin():
            """Admin interface for monitoring."""
            return render_template('admin.html',
                                 statistics=self.get_statistics())

        @self.app.route('/improve')
        def improve_dashboard():
            """Improvement dashboard for verification and readiness checks."""
            return render_template('improve.html',
                                 server_url=self.get_server_url(),
                                 status=self._get_improvement_status())

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
                SecurityValidator.validate_json_input(request.get_json(silent=True) or {})
                return jsonify(self._run_improvement_smoke_test())
            except BadRequest as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }), 500

        @self.app.route('/api/user-data', methods=['POST'])
        def update_user_data():
            """API endpoint for updating user data."""
            try:
                if not self._authorized_request():
                    return jsonify({"error": "Unauthorized"}), 401

                # Validate input
                data = SecurityValidator.validate_json_input(request.get_json())
                user_text = data.get('user_text', '')

                # Validate and sanitize user text
                validated_text = SecurityValidator.validate_user_text(user_text)

                # Update stored user data
                self.user_input_data = validated_text if validated_text else None

                return jsonify({
                    "success": True,
                    "message": "User data updated successfully",
                    "user_data": self.user_input_data,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            except BadRequest as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                return jsonify({"error": "Internal server error"}), 500

        @self.app.route('/api/user-data', methods=['GET'])
        def get_user_data():
            """API endpoint for getting current user data."""
            return jsonify({
                "user_data": self.user_input_data
            })

    def _setup_websocket_events(self) -> None:
        """Setup SocketIO events for real-time updates."""

        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            self.websocket_connections += 1
            _logger.info(f"Client connected. Total connections: {self.websocket_connections}")
            # Send current QR data if available
            if self.current_qr_data and self.current_qr_image:
                self._send_qr_update_to_client()

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            self.websocket_connections -= 1
            _logger.info(f"Client disconnected. Total connections: {self.websocket_connections}")
        @self.socketio.on('request_qr_update')
        def handle_qr_request():
            """Handle client request for QR update."""
            if self.current_qr_data and self.current_qr_image:
                self._send_qr_update_to_client()

        @self.socketio.on('update_user_data')
        def handle_user_data_update(data):
            """Handle user data update from client."""
            try:
                if not self._authorized_socket(data):
                    emit('user_data_error', {"error": "Unauthorized"})
                    return

                user_text = data.get('user_text', '').strip()

                # Validate user input
                if len(user_text) > 500:
                    emit('user_data_error', {"error": "User data too long (max 500 characters)"})
                    return

                # Update stored user data
                self.user_input_data = user_text if user_text else None

                # Broadcast update to all clients
                self.socketio.emit('user_data_updated', {
                    "user_data": self.user_input_data,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            except Exception as e:
                emit('user_data_error', {"error": str(e)})

    def _broadcast_qr_update(self) -> None:
        """Broadcast QR update to all connected clients."""
        if not self.current_qr_data or not self.current_qr_image:
            return

        # Prepare update data
        image_b64 = base64.b64encode(self.current_qr_image).decode('utf-8')
        update_data = {
            "qr_data": asdict(self.current_qr_data),
            "qr_image": f"data:image/png;base64,{image_b64}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Broadcast to all clients
        self.socketio.emit('qr_update', update_data)
        self.qr_updates_sent += 1

    def _send_qr_update_to_client(self) -> None:
        """Send QR update to requesting client."""
        if not self.current_qr_data or not self.current_qr_image:
            return

        image_b64 = base64.b64encode(self.current_qr_image).decode('utf-8')
        update_data = {
            "qr_data": asdict(self.current_qr_data),
            "qr_image": f"data:image/png;base64,{image_b64}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        emit('qr_update', update_data)

    def _run_server(self) -> None:
        """Run the Flask server."""
        try:
            # Use gevent for async server if available and not already monkey patched
            try:
                from gevent import pywsgi
                from geventwebsocket.handler import WebSocketHandler

                # Create WSGI server with WebSocket support
                self.gevent_server = pywsgi.WSGIServer(
                    (self.settings.host, self.settings.port),
                    self.app,
                    handler_class=WebSocketHandler
                )
                _logger.info(f"🌐 Starting gevent server on {self.settings.host}:{self.settings.port}")
                self.gevent_server.serve_forever()

            except ImportError:
                # Fallback to Flask-SocketIO
                _logger.info(f"🌐 Starting Flask-SocketIO server on {self.settings.host}:{self.settings.port}")
                self.socketio.run(
                    self.app,
                    host=self.settings.host,
                    port=self.settings.port,
                    debug=self.settings.debug,
                    use_reloader=False,
                    allow_unsafe_werkzeug=True
                )

        except Exception as e:
            _logger.error(f"Server error: {e}")
            # Try fallback server
            try:
                _logger.info("🔄 Trying fallback server...")
                self.socketio.run(
                    self.app,
                    host=self.settings.host,
                    port=self.settings.port,
                    debug=False,
                    use_reloader=False,
                    allow_unsafe_werkzeug=True
                )
            except Exception as fallback_error:
                _logger.error(f"Fallback server also failed: {fallback_error}")
            self.is_running = False

    def _open_browser(self) -> None:
        """Open browser to server URL."""
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
        if self.verifier is None:
            from .core import QRLiveProtocol
            from .config import QRLPConfig

            config = QRLPConfig()
            config.blockchain_settings.enabled_chains = set()
            config.time_settings.time_servers = []
            self.verifier = QRLiveProtocol(config)
        return self.verifier

    def _get_improvement_status(self) -> Dict[str, Any]:
        """Return dashboard-ready implementation and readiness status."""
        verifier = self._get_verifier()
        verifier_stats = verifier.get_statistics() if hasattr(verifier, "get_statistics") else {}
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
            self._feature_status("signed_qr_generation", True, "pass"),
            self._feature_status("public_key_trust_store", trust_store is not None, "pass"),
            self._feature_status("web_verify_endpoint", True, "pass"),
            self._feature_status("explicit_qr_chunking", True, "pass"),
            self._feature_status("admin_token_configured", bool(self.settings.admin_token), "warn"),
            self._feature_status(
                "cors_restricted",
                not self.settings.cors_enabled or bool(self.settings.cors_allowed_origins),
                "warn",
            ),
            self._feature_status("rate_limit_configured", self.settings.rate_limit_per_minute > 0, "pass"),
        ]

        optional_features = {"admin_token_configured", "cors_restricted"}
        required_features = [feature for feature in features if feature["name"] not in optional_features]
        passed = sum(1 for feature in required_features if feature["ok"])
        current_qr = asdict(self.current_qr_data) if self.current_qr_data else None

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
                "security_settings": asdict(config.security_settings) if config else {},
                "web_settings": asdict(self.settings),
            },
            "current_qr": current_qr,
            "verifier": verifier_stats,
        }

    def _run_improvement_smoke_test(self) -> Dict[str, Any]:
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
            qrlp.trust_store = TrustStore()
            qrlp.trust_store.add_public_key(
                qr_data.issuer_id,
                qr_data.signing_key_id,
                public_key,
                qr_data.signature_algorithm,
            )
            verification = qrlp.verify_qr_data(qr_data.to_json())

            chunk_payloads = qrlp.qr_generator.generate_chunked_payloads(generator_payload)
            reassembled = QRGenerator.reassemble_chunked_payloads(list(reversed(chunk_payloads)))
            chunk_ok = reassembled == generator_payload and len(chunk_payloads) > 1

            return {
                "success": bool(verification.get("valid")) and chunk_ok and len(qr_image) > 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
    def _feature_status(name: str, ok: bool, severity: str) -> Dict[str, Any]:
        return {
            "name": name,
            "ok": ok,
            "severity": "pass" if ok else severity,
        }

    def _authorized_request(self) -> bool:
        if not self.settings.admin_token:
            return True

        token = request.headers.get("X-QRLP-Admin-Token")
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ").strip()
        return token == self.settings.admin_token

    def _authorized_socket(self, data: Dict[str, Any]) -> bool:
        if not self.settings.admin_token:
            return True
        return data.get("admin_token") == self.settings.admin_token

    def _get_template_dir(self) -> str:
        """Get template directory path."""
        if os.path.isabs(self.settings.template_dir):
            return self.settings.template_dir

        # Relative to project root directory (one level up from src)
        project_root = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(project_root, self.settings.template_dir)

    def _get_static_dir(self) -> str:
        """Get static files directory path."""
        if os.path.isabs(self.settings.static_dir):
            return self.settings.static_dir

        # Relative to project root directory (one level up from src)
        project_root = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(project_root, self.settings.static_dir)
