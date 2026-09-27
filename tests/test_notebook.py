"""prototype.ipynb, the walkthrough for new contributors, must keep working and keep no secrets.

The notebook runs in a fresh kernel, offline: without API keys or an Ollama server, it skips its
one cell that calls a real model.
"""

import json
import os
import re
from pathlib import Path

import pytest
from dotenv import dotenv_values

from blokus.providers import PROVIDERS

kernel_manager = pytest.importorskip("jupyter_client.manager", reason="needs the dev dependencies")

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "prototype.ipynb"
KEY_NAMES = {p.api_key_env for p in PROVIDERS.values() if p.api_key_env}
OFFLINE_OLLAMA = "http://127.0.0.1:9/v1"
"""Port 9 (discard) is closed, so the Ollama server looks absent."""
KEY_PATTERNS = (r"AIza[0-9A-Za-z_-]{30,}", r"\bsk-[0-9A-Za-z_-]{20,}")


def code_cells() -> list[str]:
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    return ["".join(cell["source"]) for cell in cells if cell["cell_type"] == "code"]


def test_the_notebook_runs_from_top_to_bottom_offline(tmp_path):
    env = {name: value for name, value in os.environ.items() if name not in KEY_NAMES}
    env["OLLAMA_BASE_URL"] = OFFLINE_OLLAMA
    manager = kernel_manager.KernelManager(kernel_name="python3")
    # An empty working folder, so the notebook finds no .env with API keys in it.
    manager.start_kernel(cwd=str(tmp_path), env=env)
    client = manager.client()
    client.start_channels()
    printed: list[str] = []

    def collect(message):
        if message["msg_type"] == "stream":
            printed.append(message["content"]["text"])

    try:
        client.wait_for_ready(timeout=60)
        for number, source in enumerate(code_cells(), 1):
            reply = client.execute_interactive(source, timeout=120, output_hook=collect)
            content = reply["content"]
            if content["status"] != "ok":
                traceback = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(content.get("traceback", [])))
                pytest.fail(f"Code cell {number} failed:\n{source}\n\n{traceback}")
    finally:
        client.stop_channels()
        manager.shutdown_kernel(now=True)
    assert "No LLM provider is set up" in "".join(printed), "the notebook should run offline"


def test_the_notebook_keeps_no_api_keys():
    text = NOTEBOOK.read_text(encoding="utf-8")
    assert not [pattern for pattern in KEY_PATTERNS if re.search(pattern, text)]
    secrets = {
        name: value
        for name, value in dotenv_values(ROOT / ".env").items()
        if value and re.search(r"KEY|TOKEN|SECRET", name)
    }
    # Compare names only, so a failure never prints a secret.
    assert sorted(name for name, value in secrets.items() if value in text) == []
