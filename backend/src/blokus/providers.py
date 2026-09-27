"""LLM providers reachable through OpenAI-compatible chat completions APIs.

Models are named "provider:model_id", e.g. "gemini:gemini-3.1-flash-lite" or
"openrouter:nvidia/nemotron-3.5-lightning:free" (the model id may itself contain ":").
"""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from agents import Model, OpenAIChatCompletionsModel, set_tracing_disabled
from openai import AsyncOpenAI


@dataclass(frozen=True, slots=True)
class Provider:
    name: str
    base_url: str | None
    """None means the OpenAI default."""
    api_key_env: str | None
    """Environment variable holding the API key; None for local servers that need no key."""
    base_url_env: str | None = None
    """Environment variable that can override base_url, e.g. to reach the host from Docker."""

    def url(self, env: Mapping[str, str] = os.environ) -> str | None:
        return (env.get(self.base_url_env) if self.base_url_env else None) or self.base_url


PROVIDERS: dict[str, Provider] = {
    p.name: p
    for p in (
        Provider("openai", None, "OPENAI_API_KEY"),
        Provider("anthropic", "https://api.anthropic.com/v1/", "ANTHROPIC_API_KEY"),
        Provider(
            "gemini", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"
        ),
        Provider("deepseek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
        Provider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY"),
        Provider("grok", "https://api.x.ai/v1", "GROK_API_KEY"),
        Provider("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
        Provider("ollama", "http://localhost:11434/v1", None, "OLLAMA_BASE_URL"),
    )
}

# Offered in the UI when their provider is available. Any other "provider:model" can be typed in.
PRESETS: tuple[str, ...] = (
    "gemini:gemini-3.1-flash-lite",
    "openrouter:openrouter/free",
    "openrouter:nvidia/nemotron-3.5-lightning:free",
    "anthropic:claude-sonnet-5",
    "anthropic:claude-haiku-4-5-20251001",
    "openai:gpt-5-mini",
    "ollama:llama3.2",
)


@dataclass(frozen=True, slots=True)
class ModelSpec:
    provider: str
    model: str

    @classmethod
    def parse(cls, text: str) -> ModelSpec:
        provider, sep, model = text.strip().partition(":")
        provider, model = provider.strip().lower(), model.strip()
        if not sep or not model:
            raise ValueError(f"Model {text!r} should look like 'provider:model_id'.")
        if provider not in PROVIDERS:
            raise ValueError(
                f"Unknown provider {provider!r} in {text!r}. "
                f"Known providers: {', '.join(PROVIDERS)}."
            )
        return cls(provider, model)

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


def ollama_running(timeout: float = 0.5, env: Mapping[str, str] = os.environ) -> bool:
    """Whether the Ollama server answers."""
    url = f"{(PROVIDERS['ollama'].url(env) or '').rstrip('/')}/models"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except OSError:
        return False


def available_presets(
    env: Mapping[str, str] = os.environ,
    local_server_running: Callable[[], bool] = ollama_running,
) -> list[str]:
    """Presets whose provider has an API key set (or, for Ollama, a running server)."""
    local_ok: bool | None = None
    available = []
    for preset in PRESETS:
        provider = PROVIDERS[ModelSpec.parse(preset).provider]
        if provider.api_key_env is None:
            if local_ok is None:
                local_ok = local_server_running()
            if local_ok:
                available.append(preset)
        elif env.get(provider.api_key_env):
            available.append(preset)
    return available


CUSTOM_MODELS_ENV = "BLOKUS_CUSTOM_MODELS"


def custom_models_allowed(env: Mapping[str, str] = os.environ) -> bool:
    """Whether players may type any "provider:model" rather than pick a preset.

    Allowed by default, except on Hugging Face Spaces (which set SPACE_ID), where visitors would
    spend the owner's API credits. Set BLOKUS_CUSTOM_MODELS to 1 or 0 to choose explicitly.
    """
    choice = env.get(CUSTOM_MODELS_ENV, "").strip().lower()
    if choice:
        return choice in {"1", "true", "yes", "on"}
    return not env.get("SPACE_ID")


def build_model(spec: ModelSpec, env: Mapping[str, str] = os.environ) -> Model:
    """An Agents SDK model for this spec. Raises ValueError if its API key is missing."""
    provider = PROVIDERS[spec.provider]
    if provider.api_key_env is None:
        api_key = "not-needed"
    else:
        api_key = env.get(provider.api_key_env, "")
        if not api_key:
            raise ValueError(f"{spec} needs {provider.api_key_env} to be set (e.g. in .env).")
    client = AsyncOpenAI(base_url=provider.url(env), api_key=api_key)
    return OpenAIChatCompletionsModel(model=spec.model, openai_client=client)


def configure_tracing(env: Mapping[str, str] = os.environ) -> None:
    """Agents SDK traces are exported to the OpenAI platform, which needs an OpenAI key."""
    set_tracing_disabled(not env.get("OPENAI_API_KEY"))
