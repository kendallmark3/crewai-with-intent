"""Local web front door for the crew: paste an intent, get a verified report.

Why the standard library and not FastAPI: one user, two JSON routes and a static
folder do not justify a new pinned dependency. The server binds to 127.0.0.1
only, because every run spends Anthropic credits.

Usage: python -m src.server [--port 8787]   (or set CREW_PORT; web/vite.config.ts reads the same variable)
Serves the built React app from web/dist when it exists.
"""
from __future__ import annotations

import argparse
import json
import os
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src import main as crew_app

HOST = "127.0.0.1"
# 8000, 8001 and 8080 are common defaults for other local servers; 8787 rarely clashes.
DEFAULT_PORT = 8787
PORT_ENV = "CREW_PORT"
WEB_DIST = crew_app.ROOT / "web" / "dist"
MAX_BODY_BYTES = 256 * 1024
MAX_INTENT_CHARS = 100_000

# One crew run at a time: runs take minutes and cost money, so a second click waits for nothing.
_run_lock = threading.Lock()


class InputError(ValueError):
    """The request itself is wrong; the client can fix it."""


def parse_intent(payload: object) -> str:
    """Validate the POST /api/run body and return the intent text."""
    if not isinstance(payload, dict):
        raise InputError("Body must be a JSON object like {\"intent\": \"...\"}.")
    intent = payload.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        raise InputError("'intent' must be a non-empty string of Markdown.")
    if len(intent) > MAX_INTENT_CHARS:
        raise InputError(f"'intent' is longer than {MAX_INTENT_CHARS} characters.")
    return intent


class Handler(BaseHTTPRequestHandler):
    server_version = "CrewServer/1.0"

    # ---------- routes ----------
    def do_GET(self) -> None:
        if self.path == "/api/intent":
            try:
                text = crew_app.read_intent()
            except FileNotFoundError as exc:
                self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            self._json(HTTPStatus.OK, {"intent": text, "source": "intent/current-feature.md"})
            return
        self._static()

    def do_POST(self) -> None:
        if self.path != "/api/run":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        try:
            intent = parse_intent(self._read_json())
        except InputError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        try:
            crew_app.require_api_key()
        except RuntimeError as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        if not _run_lock.acquire(blocking=False):
            self._json(HTTPStatus.CONFLICT, {"error": "A crew run is already in progress. Wait for it to finish."})
            return
        try:
            outcome = crew_app.run_crew(intent)
        except Exception as exc:  # surfaced to the user and logged, never swallowed
            self.log_error("crew run failed: %r", exc)
            self._json(HTTPStatus.BAD_GATEWAY, {"error": f"The crew run failed: {exc}"})
            return
        finally:
            _run_lock.release()

        # A failed verification is a valid result, not a server error: the UI shows why it failed.
        self._json(HTTPStatus.OK, {
            "report": outcome.report,
            "errors": outcome.errors,
            "verdict": outcome.verdict,
            "passed": outcome.passed,
        })

    # ---------- helpers ----------
    def _read_json(self) -> object:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise InputError("Invalid Content-Length header.")
        if length <= 0:
            raise InputError("Request body is empty.")
        if length > MAX_BODY_BYTES:
            raise InputError(f"Request body is larger than {MAX_BODY_BYTES} bytes.")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise InputError("Request body is not valid JSON.")

    def _json(self, status: HTTPStatus, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _static(self) -> None:
        if not WEB_DIST.is_dir():
            self._json(HTTPStatus.NOT_FOUND, {"error": "web/dist not found. Run 'npm run build' in web/ or use 'npm run dev'."})
            return
        rel = self.path.split("?", 1)[0].lstrip("/") or "index.html"
        target = (WEB_DIST / rel).resolve()
        # Refuse anything that escapes web/dist (e.g. /../.env).
        if WEB_DIST.resolve() not in target.parents or not target.is_file():
            target = WEB_DIST / "index.html"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def resolve_port(raw: str | None) -> int:
    """Read the port from CREW_PORT, validated once at startup so a typo fails loudly."""
    if raw is None or not raw.strip():
        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError:
        raise ValueError(f"{PORT_ENV} must be a whole number, got {raw!r}.") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"{PORT_ENV} must be between 1 and 65535, got {port}.")
    return port


def make_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((HOST, port), Handler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve the crew UI on localhost.")
    try:
        env_port = resolve_port(os.getenv(PORT_ENV))
    except ValueError as exc:
        parser.error(str(exc))
    parser.add_argument("--port", type=int, default=env_port, help=f"default: ${PORT_ENV} or {DEFAULT_PORT}")
    args = parser.parse_args(argv)
    try:
        server = make_server(args.port)
    except OSError as exc:
        # Usually another local app already owns the port; say which setting to change.
        parser.exit(1, f"Can't listen on {HOST}:{args.port} ({exc.strerror}). "
                       f"Pick another port with --port or {PORT_ENV}, and use the same {PORT_ENV} for 'npm run dev'.\n")
    print(f"Crew UI on http://{HOST}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
