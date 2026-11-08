# QRLP web server

The local QRLP web server displays the latest QR image and its payload metadata.
Use the live display at `/` or the viewer at `/viewer` as a browser source in OBS.
`/admin` shows current frame availability, active connections, and broadcast
counts. `/improve` shows configured capabilities and offers a local smoke
test for public-key verification and chunk recovery.

Run `qrlp live --no-browser` and open the URL printed by the command. The
default bind is `localhost:8080`. The viewer can set a message for the next
generated frame. Submitting an empty message clears it.

## Embed the server

```python
from src.config import QRLPConfig, WebSettings
from src.core import QRLiveProtocol
from src.web_server import QRLiveWebServer

config = QRLPConfig()
config.blockchain_settings.enabled_chains = set()
config.time_settings.time_servers = []

protocol = QRLiveProtocol(config)
server = QRLiveWebServer(WebSettings(port=0, auto_open_browser=False), verifier=protocol)
protocol.add_update_callback(server.update_qr_display)
protocol.set_user_data_callback(server.get_user_data)

server.start_server()
try:
    print(server.get_server_url())
    with protocol:
        input("Press Enter to stop the local overlay.\n")
finally:
    server.stop_server()
```

Startup binds the socket before returning. With port `0`, `get_server_url()`
reports the assigned port. `stop_server()` releases the listener and closes its
browser streams. The embedded listener uses a threaded development WSGI server
for local overlays. Deployments that expose the application on a network
should use a WSGI server and reverse proxy suitable for long-lived connections
and configure TLS, request limits, and an admin token.

## HTTP and live updates

| Endpoint | Behavior |
| --- | --- |
| `GET /api/qr/current` | Latest frame as JSON, or HTTP 404 before the first frame. |
| `GET /api/qr/events` | Server-sent events with the current frame followed by new frames. |
| `GET /api/status`, `GET /status` | Listener state, page views, live connections, and Socket.IO broadcasts. |
| `POST /api/verify` | Verify a JSON string supplied as `{"qr_data": "..."}`. |
| `GET /api/user-data` | Current message, or `null`. |
| `POST /api/user-data` | Set or clear the message with `{"user_text": "..."}`. |
| `GET /api/improve/status` | Readiness, signing and trust metadata, and public configuration. |
| `POST /api/improve/smoke-test` | Submit `{}` to test signed QR verification in a separate verifier and check chunk recovery. |

The browser pages use the same-origin event stream and require no CDN scripts.
The stream sends a comment heartbeat every 15 seconds when no new frame is
ready. A slow client receives the newest available frame. Configure proxies
to pass the event stream through without buffering. A Socket.IO client can
still listen for `qr_update` or emit `request_qr_update`. The current-frame API,
event stream, and Socket.IO use the same envelope with `qr_data` (the parsed
object), `qr_json` (the exact wire text), `qr_image` (a data URL), and
`timestamp` (the frame's publication time). Use `qr_json` to verify a detached
receipt against the original UTF-8 bytes. Local
OpenTimestamps proof paths stay on the issuer's machine.

## Access controls

Set `WebSettings.admin_token` for protected controls. The viewer and
improvement dashboard prompt for the token when one is configured. An HTTP
client can supply `X-QRLP-Admin-Token` or `Authorization: Bearer <token>`.
Socket.IO clients supply an `admin_token` property alongside `user_text` in
the `update_user_data` event. A successful message update emits
`user_data_updated`. Rejected socket updates emit `user_data_error`.

Without a configured token, message changes and smoke tests work only on a
loopback listener from a loopback peer using a loopback request host and
either no Origin header or the same origin. CORS is disabled by default.
Set both `cors_enabled` and explicit `cors_allowed_origins` for trusted browser
integrations. CORS permits cross-origin access to the configured routes and
Socket.IO transport subject to their normal authorization.

The server caps request bodies at 128 KiB and applies an in-memory per-peer
HTTP request limit. Treat displayed QR metadata and messages as public to
any client that can reach the server. The display lists evidence included
in a frame. Use the verification endpoint to evaluate that evidence.

An installed wheel includes its default templates. A custom
`WebSettings.template_dir` can be absolute or relative to the project root.
Custom templates with inline scripts must apply the per-response nonce,
`<script nonce="{{ script_nonce }}">`, to work with the default Content
Security Policy.
