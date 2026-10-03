import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An isolated orrery home with two small libraries."""
    root = tmp_path / "orrery-home"
    lib = root / "library"
    lib.mkdir(parents=True)
    (lib / "animal.yaml").write_text("- fox\n- heron\n- owl\n")
    (lib / "style.yaml").write_text("- linocut\n- gouache\n")
    monkeypatch.setenv("ORRERY_HOME", str(root))
    return root


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Never read or write the real ~/.config/orrery/home pointer."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))


@pytest.fixture(autouse=True)
def _force_fake_llm(monkeypatch):
    """Never let the test suite load or call a real model (lesson LS-G0010)."""
    monkeypatch.setenv("ORRERY_FORCE_FAKE_LLM", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # a key in the shell never reaches a test


class FakeAPI:
    """An OpenAI-compatible endpoint on 127.0.0.1 (#165). `answer(body)` is the reply's text; `refuse` maps a
    model to the parameters it refuses; `key` is the one key it takes (None: any); `busy` answers 429 that often."""

    def __init__(self):
        self.requests, self.key, self.refuse, self.busy = [], None, {}, 0
        self.models = ["gpt-5.4-mini", "gpt-4o-mini-tts", "text-embedding-3-small", "gpt-6-luna"]
        self.answer = lambda body: "OK"
        self.url = ""


@pytest.fixture
def fake_api(monkeypatch):
    from orrery import llm
    monkeypatch.setattr(llm, "RETRIES", (0, 0))
    api = FakeAPI()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, data):
            payload = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _refused(self):
            if api.key is not None and self.headers.get("Authorization") != f"Bearer {api.key}":
                self._send(401, {"error": {"message": "Incorrect API key provided.", "code": "invalid_api_key"}})
                return True
            return False

        def do_GET(self):
            if not self._refused():
                self._send(200, {"data": [{"id": m} for m in api.models]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            api.requests.append(body)
            if self._refused():
                return
            if api.busy:
                api.busy -= 1
                return self._send(429, {"error": {"message": "Rate limit reached."}})
            for param in api.refuse.get(body.get("model"), ()):
                if param in body:
                    return self._send(400, {"error": {"message": f"Unsupported parameter: '{param}'.", "param": param}})
            self._send(200, {"choices": [{"message": {"content": api.answer(body)}}]})

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api.url = f"http://127.0.0.1:{server.server_port}/v1"
    yield api
    server.shutdown()
