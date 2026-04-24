"""
OAuth Callback & Webhook Server.
Empfängt OAuth-Callbacks von Strava und Suunto sowie Suunto-Webhook-Benachrichtigungen.
Starte separat: python oauth_server.py
"""
import os
import json
import secrets
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from database import (
    init_db,
    save_suunto_tokens,
    get_chat_id_by_suunto_username,
    save_suunto_webhook_workout,
    save_suunto_sleep,
    save_suunto_recovery,
)
from strava import exchange_code_for_token, save_strava_tokens
from suunto import (
    exchange_code_for_token as suunto_exchange_code_for_token,
    verify_webhook_signature,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfigurierbare URLs
OAUTH_BASE_URL = os.getenv("OAUTH_BASE_URL", "http://localhost:5000")
SUUNTO_REDIRECT_URI = f"{OAUTH_BASE_URL}/suunto/callback"
SUUNTO_WEBHOOK_SECRET = os.getenv("SUUNTO_WEBHOOK_SECRET", "")

# CSRF-Schutz: Speichert gültige State-Tokens (chat_id → token)
_pending_states: dict[str, int] = {}


def generate_oauth_state(chat_id: int) -> str:
    """Generiert einen kryptographisch sicheren State-Token für OAuth CSRF-Schutz."""
    token = secrets.token_urlsafe(32)
    state = f"{chat_id}:{token}"
    _pending_states[state] = chat_id
    return state


def validate_oauth_state(state: str) -> int | None:
    """Validiert einen State-Token und gibt die chat_id zurück. Einmalig verwendbar."""
    chat_id = _pending_states.pop(state, None)
    return chat_id


# OAuth Rate-Limiting: max 5 Requests/Minute pro IP
OAUTH_RATE_LIMIT = 5
_oauth_requests: dict[str, list[float]] = {}

# HTTPS-Enforcement: Wenn REQUIRE_HTTPS=true, werden HTTP-Requests auf HTTPS umgeleitet
REQUIRE_HTTPS = os.getenv("REQUIRE_HTTPS", "false").lower() == "true"
SSL_CERTFILE = os.getenv("SSL_CERTFILE", "")
SSL_KEYFILE = os.getenv("SSL_KEYFILE", "")


def _check_oauth_rate_limit(ip: str) -> bool:
    """Gibt True zurück wenn die IP noch Requests senden darf."""
    import time
    now = time.time()
    if ip not in _oauth_requests:
        _oauth_requests[ip] = []
    _oauth_requests[ip] = [t for t in _oauth_requests[ip] if now - t < 60]
    if len(_oauth_requests[ip]) >= OAUTH_RATE_LIMIT:
        return False
    _oauth_requests[ip].append(now)
    return True


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def _check_https(self) -> bool:
        """Prüft ob HTTPS verwendet wird (direkt oder via Reverse-Proxy). Leitet um wenn nötig."""
        if not REQUIRE_HTTPS:
            return True
        # Reverse-Proxy setzt X-Forwarded-Proto
        proto = self.headers.get("X-Forwarded-Proto", "http")
        if proto == "https":
            return True
        # HTTP → HTTPS Redirect
        host = self.headers.get("Host", "localhost")
        self.send_response(301)
        self.send_header("Location", f"https://{host}{self.path}")
        self.end_headers()
        return False

    def do_GET(self):
        if not self._check_https():
            return

        parsed = urlparse(self.path)

        # Health-Check für Render
        if parsed.path == "/health":
            self._respond(200, "OK")
            return

        # Rate-Limiting pro IP
        client_ip = self.client_address[0]
        if not _check_oauth_rate_limit(client_ip):
            self._respond(429, "<html><body><h1>Too Many Requests</h1></body></html>")
            logger.warning(f"OAuth rate limit exceeded for IP {client_ip}")
            return

        if parsed.path == "/strava/callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            chat_id = params.get("state", [None])[0]

            if code and chat_id:
                token_data = exchange_code_for_token(code)
                if token_data:
                    save_strava_tokens(int(chat_id), token_data)
                    self._respond(200,
                        "<html><body style='font-family:sans-serif;text-align:center;padding:50px'>"
                        "<h1>✅ Strava verbunden!</h1>"
                        "<p>Du kannst dieses Fenster schließen und zurück zu Telegram gehen.</p>"
                        "</body></html>"
                    )
                    logger.info(f"Strava connected for chat_id {chat_id}")
                else:
                    self._respond(500,
                        "<html><body style='font-family:sans-serif;text-align:center;padding:50px'>"
                        "<h1>❌ Fehler</h1><p>Token-Austausch fehlgeschlagen. Versuch es nochmal.</p>"
                        "</body></html>"
                    )
            else:
                self._respond(400, "<html><body><h1>Fehlende Parameter</h1></body></html>")

        elif parsed.path == "/suunto/callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]

            # CSRF-Validierung
            chat_id = validate_oauth_state(state) if state else None
            if not chat_id:
                # Fallback: state könnte direkt die chat_id sein (Kompatibilität)
                try:
                    chat_id = int(state) if state else None
                except (ValueError, TypeError):
                    chat_id = None

            if code and chat_id:
                token_data = suunto_exchange_code_for_token(
                    code, SUUNTO_REDIRECT_URI
                )
                if token_data:
                    # Extract username from token response ('user' field)
                    username = token_data.get("user", "")
                    save_suunto_tokens(chat_id, {
                        "access_token": token_data.get("access_token", ""),
                        "refresh_token": token_data.get("refresh_token", ""),
                        "expires_at": token_data.get("expires_at", 0),
                        "username": username,
                    })
                    self._respond(200,
                        "<html><body style='font-family:sans-serif;text-align:center;padding:50px'>"
                        "<h1>✅ Suunto verbunden!</h1>"
                        "<p>Du kannst dieses Fenster schließen und zurück zu Telegram gehen.</p>"
                        "</body></html>"
                    )
                    logger.info(f"Suunto connected for chat_id {chat_id} (user={username})")
                else:
                    self._respond(500,
                        "<html><body style='font-family:sans-serif;text-align:center;padding:50px'>"
                        "<h1>❌ Fehler</h1><p>Suunto Token-Austausch fehlgeschlagen. Versuch es nochmal.</p>"
                        "</body></html>"
                    )
            else:
                self._respond(400, "<html><body><h1>Fehlende Parameter</h1></body></html>")

        else:
            self._respond(404, "<html><body><h1>Not Found</h1></body></html>")

    def do_POST(self):
        if not self._check_https():
            return

        # Rate-Limiting pro IP
        client_ip = self.client_address[0]
        if not _check_oauth_rate_limit(client_ip):
            self._respond(429, "Too Many Requests")
            logger.warning(f"Webhook rate limit exceeded for IP {client_ip}")
            return

        parsed = urlparse(self.path)

        if parsed.path == "/suunto/webhook":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            signature = self.headers.get("X-HMAC-SHA256-Signature", "")

            # Validate HMAC signature
            if not verify_webhook_signature(body, signature, SUUNTO_WEBHOOK_SECRET):
                logger.warning("Suunto webhook: invalid HMAC signature")
                self._respond(401, "Unauthorized")
                return

            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                logger.error("Suunto webhook: invalid JSON body")
                self._respond(400, "Bad Request")
                return

            event_type = payload.get("type", "")
            username = payload.get("username", "")

            # Resolve username → chat_id
            chat_id = get_chat_id_by_suunto_username(username) if username else None
            if not chat_id:
                logger.warning(f"Suunto webhook: unknown username '{username}'")
                self._respond(200, "OK")
                return

            if event_type == "WORKOUT_CREATED":
                workout = payload.get("payload", {})
                save_suunto_webhook_workout(chat_id, {
                    "workout_key": workout.get("workoutKey", ""),
                    "sport": str(workout.get("activityId", "")),
                    "duration_sec": workout.get("totalTime", 0),
                    "distance_m": workout.get("totalDistance", 0),
                    "hr_avg": workout.get("hrdata", {}).get("workoutAvgHR", 0),
                    "hr_max": workout.get("hrdata", {}).get("workoutMaxHR", 0),
                    "ascent_m": workout.get("totalAscent", 0),
                    "descent_m": workout.get("totalDescent", 0),
                })
                logger.info(f"Suunto webhook: WORKOUT_CREATED saved for chat_id {chat_id}")

            elif event_type == "SUUNTO_247_SLEEP_CREATED":
                samples = payload.get("payload", {})
                save_suunto_sleep(chat_id, {
                    "date": samples.get("date", ""),
                    "deep_sleep_min": samples.get("DeepSleepDuration", 0),
                    "light_sleep_min": samples.get("LightSleepDuration", 0),
                    "rem_sleep_min": samples.get("REMSleepDuration", 0),
                    "hr_avg": samples.get("HRAvg", 0),
                    "hr_min": samples.get("HRMin", 0),
                    "sleep_quality_score": samples.get("SleepQualityScore", 0),
                    "avg_hrv": samples.get("AvgHRV", 0),
                })
                logger.info(f"Suunto webhook: SLEEP saved for chat_id {chat_id}")

            elif event_type == "SUUNTO_247_RECOVERY_CREATED":
                samples = payload.get("payload", {})
                save_suunto_recovery(chat_id, {
                    "date": samples.get("date", ""),
                    "balance": samples.get("Balance", 0),
                    "stress_state": samples.get("StressState", 0),
                })
                logger.info(f"Suunto webhook: RECOVERY saved for chat_id {chat_id}")

            else:
                logger.info(f"Suunto webhook: ignoring unknown type '{event_type}'")

            self._respond(200, "OK")
        else:
            self._respond(404, "Not Found")

    def _respond(self, status: int, html: str):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        logger.info(f"HTTP: {args[0]}")


def main():
    init_db()

    host = os.getenv("OAUTH_HOST", "localhost")
    port = int(os.getenv("OAUTH_PORT", "5000"))

    server = HTTPServer((host, port), OAuthCallbackHandler)

    # SSL aktivieren wenn Zertifikate konfiguriert sind
    if SSL_CERTFILE and SSL_KEYFILE:
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(SSL_CERTFILE, SSL_KEYFILE)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        logger.info(f"OAuth Server läuft auf https://{host}:{port} (SSL)")
    else:
        logger.info(f"OAuth Server läuft auf http://{host}:{port}")
        if REQUIRE_HTTPS:
            logger.info("HTTPS-Redirect aktiv (erwartet Reverse-Proxy)")

    server.serve_forever()


if __name__ == "__main__":
    main()
