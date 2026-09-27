import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from agents import OpenAIChatCompletionsModel

from blokus.providers import (
    CUSTOM_MODELS_ENV,
    PRESETS,
    PROVIDERS,
    ModelSpec,
    available_presets,
    build_model,
    custom_models_allowed,
    ollama_running,
)


def test_parse_splits_on_the_first_colon_only():
    spec = ModelSpec.parse(" OpenRouter:nvidia/nemotron-3.5-lightning:free ")
    assert spec == ModelSpec("openrouter", "nvidia/nemotron-3.5-lightning:free")
    assert str(spec) == "openrouter:nvidia/nemotron-3.5-lightning:free"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("gemini-3.1-flash-lite", "should look like 'provider:model_id'"),
        ("gemini:", "should look like 'provider:model_id'"),
        ("acme:model-1", "Unknown provider 'acme'"),
    ],
)
def test_parse_rejects_malformed_specs(text, message):
    with pytest.raises(ValueError, match=message):
        ModelSpec.parse(text)


def test_presets_are_valid_specs():
    for preset in PRESETS:
        assert str(ModelSpec.parse(preset)) == preset


def test_available_presets_need_a_key_or_a_running_local_server():
    assert available_presets({}, lambda: False) == []
    only_gemini = available_presets({"GEMINI_API_KEY": "k", "GROQ_API_KEY": ""}, lambda: False)
    assert only_gemini == ["gemini:gemini-3.1-flash-lite"]
    assert available_presets({}, lambda: True) == ["ollama:llama3.2"]


def test_available_presets_probe_the_local_server_at_most_once():
    calls = []
    available_presets({}, lambda: calls.append(1) or False)
    assert len(calls) == 1


def test_build_model_needs_the_provider_key():
    with pytest.raises(ValueError, match="needs OPENROUTER_API_KEY"):
        build_model(ModelSpec("openrouter", "openrouter/free"), env={})
    model = build_model(ModelSpec("openrouter", "openrouter/free"), env={"OPENROUTER_API_KEY": "k"})
    assert isinstance(model, OpenAIChatCompletionsModel)
    assert isinstance(
        build_model(ModelSpec("ollama", "llama3.2"), env={}), OpenAIChatCompletionsModel
    )


def test_custom_models_are_off_on_spaces_unless_enabled():
    assert custom_models_allowed({})
    assert not custom_models_allowed({"SPACE_ID": "someone/blokus"})
    assert custom_models_allowed({"SPACE_ID": "someone/blokus", CUSTOM_MODELS_ENV: "1"})
    assert not custom_models_allowed({CUSTOM_MODELS_ENV: "0"})


def test_ollama_can_be_reached_at_another_address():
    ollama = PROVIDERS["ollama"]
    assert ollama.url({}) == "http://localhost:11434/v1"
    assert ollama.url({"OLLAMA_BASE_URL": "http://host.docker.internal:11434/v1"}) == (
        "http://host.docker.internal:11434/v1"
    )
    assert PROVIDERS["gemini"].url({"OLLAMA_BASE_URL": "http://elsewhere"}) == (
        PROVIDERS["gemini"].base_url
    )


def test_ollama_running_asks_the_configured_server_for_its_models():
    paths = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            self.send_response(200 if self.path == "/v1/models" else 404)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1/"
        assert ollama_running(env={"OLLAMA_BASE_URL": url})
        assert paths == ["/v1/models"]
    finally:
        server.shutdown()
        server.server_close()
    assert not ollama_running(env={"OLLAMA_BASE_URL": url})
