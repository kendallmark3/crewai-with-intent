"""Offline tests for the local web server. The crew is replaced with a fake; no API call happens."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from src import main as crew_app
from src import server


@pytest.fixture
def base_url():
    srv = server.make_server(port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _post(url, body: bytes):
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def test_binds_to_localhost_only():
    srv = server.make_server(port=0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def test_get_intent_returns_current_feature(base_url):
    with urllib.request.urlopen(f"{base_url}/api/intent") as resp:
        body = json.loads(resp.read())
    assert body["intent"] == crew_app.read_intent()
    assert body["source"] == "intent/current-feature.md"


@pytest.mark.parametrize("payload", [b"not json", b"[]", b'{"intent": ""}', b'{"intent": "   "}', b'{"intent": 5}'])
def test_run_rejects_bad_input(base_url, payload):
    status, body = _post(f"{base_url}/api/run", payload)
    assert status == 400 and body["error"]


def test_run_rejects_oversized_intent(base_url):
    payload = json.dumps({"intent": "x" * (server.MAX_INTENT_CHARS + 1)}).encode()
    status, _ = _post(f"{base_url}/api/run", payload)
    assert status == 400


def test_run_without_api_key_fails_before_crew(base_url, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(crew_app, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(crew_app, "run_crew", lambda _: pytest.fail("crew must not run without a key"))
    status, body = _post(f"{base_url}/api/run", b'{"intent": "# Intent"}')
    assert status == 500 and "ANTHROPIC_API_KEY" in body["error"]


def test_run_passes_pasted_intent_and_returns_verification(base_url, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-offline")
    seen = {}

    def fake_run(intent):
        seen["intent"] = intent
        return crew_app.RunResult(report="# Report\n", errors=["Missing section: '## 2. Architecture'"], verdict=None)

    monkeypatch.setattr(crew_app, "run_crew", fake_run)
    status, body = _post(f"{base_url}/api/run", json.dumps({"intent": "# My story"}).encode())
    assert status == 200
    assert seen["intent"] == "# My story"
    assert body == {"report": "# Report\n", "errors": ["Missing section: '## 2. Architecture'"], "verdict": None, "passed": False}


def test_crew_exception_is_reported_not_swallowed(base_url, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-offline")

    def boom(_):
        raise RuntimeError("upstream 529")

    monkeypatch.setattr(crew_app, "run_crew", boom)
    status, body = _post(f"{base_url}/api/run", b'{"intent": "# Intent"}')
    assert status == 502 and "upstream 529" in body["error"]


def test_second_run_while_busy_is_refused(base_url, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-offline")
    assert server._run_lock.acquire(blocking=False)
    try:
        status, body = _post(f"{base_url}/api/run", b'{"intent": "# Intent"}')
    finally:
        server._run_lock.release()
    assert status == 409 and "in progress" in body["error"]


def test_static_route_never_escapes_web_dist(base_url, monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<p>app</p>")
    monkeypatch.setattr(server, "WEB_DIST", tmp_path)
    with urllib.request.urlopen(f"{base_url}/../.env") as resp:
        assert resp.read() == b"<p>app</p>"


def test_port_defaults_to_8787_and_reads_crew_port():
    assert server.resolve_port(None) == 8787
    assert server.resolve_port("  ") == 8787
    assert server.resolve_port("9123") == 9123


@pytest.mark.parametrize("raw", ["abc", "0", "70000", "80.5"])
def test_bad_crew_port_fails_loudly(raw):
    with pytest.raises(ValueError, match="CREW_PORT"):
        server.resolve_port(raw)


def test_vite_proxy_default_matches_server():
    vite = (crew_app.ROOT / "web" / "vite.config.ts").read_text()
    assert f"const DEFAULT_PORT = {server.DEFAULT_PORT};" in vite
