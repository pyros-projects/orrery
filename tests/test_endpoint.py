"""The language model as an API endpoint (#165): the backend, the key, the check."""

import os
import stat

import numpy as np
import pytest

from orrery import endpoint
from orrery.home import Home
from orrery.llm import OpenAIBackend, backend_for


def use_api(home, fake_api, model="gpt-5.4-mini", **llm):
    Home(home).save_config({"llm": {"source": "api", "api": {"base_url": fake_api.url, "model": model}, **llm}})


def test_a_model_that_refuses_max_tokens_and_temperature_is_asked_again_and_remembered(fake_api):
    fake_api.refuse = {"gpt-6-luna": ("max_tokens", "temperature")}
    backend = OpenAIBackend(fake_api.url, "gpt-6-luna", temperature=0.3, max_tokens=900)
    assert backend.complete("hi") == "OK"
    assert [sorted(k for k in r if k.startswith(("max", "temp"))) for r in fake_api.requests] == [
        ["max_tokens", "temperature"], ["max_completion_tokens", "temperature"], ["max_completion_tokens"]]
    fake_api.requests.clear()
    backend.complete("again")  # the model's quirks are known now: one request
    assert len(fake_api.requests) == 1 and fake_api.requests[0]["max_completion_tokens"] == 900


def test_frames_go_as_pictures_before_the_text(fake_api):
    frames = np.zeros((2, 40, 64, 3), dtype="float32")  # an IMAGE batch, as ComfyUI hands it
    OpenAIBackend(fake_api.url, "gpt-5.4-mini").complete("what happens", images=frames)
    content = fake_api.requests[0]["messages"][0]["content"]
    assert [part["type"] for part in content] == ["image_url", "image_url", "text"]
    assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,") and content[2]["text"] == "what happens"


def test_a_prompt_can_put_its_pictures_after_what_they_belong_to(fake_api):
    """#333: a writer's text shows the picture after the screenplay; without pictures the mark goes."""
    from orrery.llm import PICTURES

    frames = np.zeros((1, 40, 64, 3), dtype="float32")
    OpenAIBackend(fake_api.url, "gpt-5.4-mini").complete(f"the screenplay\n\nThe picture: {PICTURES} joins it.", images=frames)
    content = fake_api.requests[-1]["messages"][0]["content"]
    assert [part["type"] for part in content] == ["text", "image_url", "text"]
    assert content[0]["text"] == "the screenplay\n\nThe picture: " and content[2]["text"] == " joins it."
    OpenAIBackend(fake_api.url, "gpt-5.4-mini").complete(f"The picture: {PICTURES} joins it.")
    assert fake_api.requests[-1]["messages"][0]["content"] == "The picture:  joins it."


def test_a_busy_endpoint_is_asked_again_and_a_refused_key_says_so(fake_api):
    fake_api.busy = 2
    assert OpenAIBackend(fake_api.url, "gpt-5.4-mini").complete("hi") == "OK"
    fake_api.key = "sk-right"
    with pytest.raises(RuntimeError, match="Incorrect API key.*HTTP 401.*settings"):
        OpenAIBackend(fake_api.url, "gpt-5.4-mini", api_key="sk-wrong").complete("hi")


def test_the_key_lives_in_the_homes_env_file_and_the_environment_wins(home, monkeypatch):
    h = Home(home)
    (home / ".env").write_text("# mine\nOTHER=1\n")
    endpoint.save_key(h, "OPENAI_API_KEY", "sk-test-abcd1234")
    assert (home / ".env").read_text() == "# mine\nOTHER=1\nOPENAI_API_KEY=sk-test-abcd1234\n"
    assert stat.S_IMODE(os.stat(home / ".env").st_mode) == 0o600
    assert endpoint.key(h) == ("sk-test-abcd1234", "file") and endpoint.hint("sk-test-abcd1234") == "…1234"
    endpoint.save_key(h, "OPENAI_API_KEY", "sk-new-key-9999")
    assert (home / ".env").read_text().count("OPENAI_API_KEY") == 1
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-shell")
    assert endpoint.key(h) == ("sk-from-shell", "env")


def test_the_endpoint_writes_only_while_the_settings_choose_it(home, fake_api):
    assert endpoint.backend(Home(home)) is None
    use_api(home, fake_api, temperature=0.4, max_tokens=7000)
    api = endpoint.backend(Home(home))
    assert (api.model, api.temperature, api.max_tokens) == ("gpt-5.4-mini", 0.4, 7000)
    assert endpoint.backend(Home(home), temperature=0.8).temperature == 0.8
    Home(home).save_config({"llm": {"source": "comfy", "api": {"base_url": fake_api.url, "model": "gpt-5.4-mini"}}})
    assert endpoint.backend(Home(home)) is None


def test_tests_never_reach_a_real_endpoint(home):
    Home(home).save_config({"llm": {"source": "api", "api": {"model": "gpt-5.4-mini"}}})  # api.openai.com
    with pytest.raises(RuntimeError, match="fake"):
        endpoint.backend(Home(home))


def test_orrery_lib_uses_the_endpoint_when_no_library_model_is_set(home, fake_api):
    use_api(home, fake_api)
    assert backend_for(Home(home), "library").model == "gpt-5.4-mini"


def test_the_check_lists_chat_models_and_asks_the_model(fake_api):
    fake_api.key = "sk-right"
    checked = endpoint.check(fake_api.url, "sk-right", "gpt-6-luna")
    assert checked["ok"] and checked["answer"] == "OK" and checked["models"] == ["gpt-5.4-mini", "gpt-6-luna"]
    refused = endpoint.check(fake_api.url, "sk-wrong", "gpt-6-luna")
    assert not refused["ok"] and "refused the key" in refused["error"]
    assert endpoint.check(fake_api.url, "sk-right", "")["error"] == "Pick a model."
