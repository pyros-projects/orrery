import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from orrery.home import Home
from orrery.llm import FakeBackend, InvalidProposal, OpenAIBackend, backend_for, extract_json


def test_extract_json_reads_fenced_blocks_and_ignores_prose():
    assert extract_json('Sure!\n```json\n["a", "b"]\n```\nDone.') == ["a", "b"]
    assert extract_json('Here: {"add": ["x"]} hope that helps') == {"add": ["x"]}


def test_extract_json_rejects_text_without_json():
    with pytest.raises(InvalidProposal):
        extract_json("I cannot do that.")


def test_fake_backend_replays_replies_in_order():
    fake = FakeBackend(["one", "two"])
    assert [fake.complete("p"), fake.complete("p"), fake.complete("p")] == ["one", "two", "two"]
    assert fake.prompts == ["p", "p", "p"]


def test_backend_for_builds_fake_from_config(home):
    (home / "orrery.yaml").write_text("models:\n  library: {backend: fake, replies: ['[\"a\"]']}\n")
    assert backend_for(Home(home), "library").complete("x") == '["a"]'


def test_real_backends_are_refused_while_tests_force_fake(home):
    (home / "orrery.yaml").write_text("models:\n  library: {backend: transformers, path: /m}\n")
    with pytest.raises(RuntimeError, match="fake"):
        backend_for(Home(home), "library")


def test_openai_backend_talks_to_a_compatible_server():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            payload = json.dumps({"choices": [{"message": {"content": '["fog"]'}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        backend = OpenAIBackend(f"http://127.0.0.1:{server.server_port}/v1", "qwen")
        assert backend.complete("make a list") == '["fog"]'
    finally:
        server.shutdown()
    assert seen["path"] == "/v1/chat/completions"
    assert seen["body"]["model"] == "qwen"
    assert seen["body"]["messages"][-1] == {"role": "user", "content": "make a list"}
