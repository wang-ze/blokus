"""The Docker image, the start and stop scripts, and the Hugging Face Space settings must agree.

A Docker Space builds the Dockerfile and reads its settings from README.md's front matter.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def front_matter() -> dict[str, str]:
    text = (ROOT / "README.md").read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "README.md must start with the Space's YAML front matter"
    pairs = (line.split(":", 1) for line in match[1].splitlines() if ":" in line)
    return {key.strip(): value.strip().strip('"') for key, value in pairs}


def dockerfile() -> str:
    return (ROOT / "Dockerfile").read_text()


def env_value(name: str) -> str:
    match = re.search(rf"^\s*(?:ENV\s+)?{name}=(\S+?)\s*\\?$", dockerfile(), re.M)
    assert match, f"the Dockerfile should set {name}"
    return match[1].strip('"')


def test_the_space_runs_the_docker_image_on_the_port_the_app_listens_on():
    config = front_matter()
    assert config["sdk"] == "docker"
    assert config["app_port"] == env_value("GRADIO_SERVER_PORT")
    assert re.search(rf"^EXPOSE {config['app_port']}$", dockerfile(), re.M)
    assert len(config["short_description"]) <= 60


def test_the_image_uses_the_project_python_and_the_source_folders():
    python = re.search(r"^ARG PYTHON_VERSION=(\S+)$", dockerfile(), re.M)
    assert python and python[1] == (ROOT / ".python-version").read_text().strip()
    paths = env_value("PYTHONPATH").split(":")
    assert paths == ["/app/backend/src", "/app/frontend/src"]
    for path in paths:
        assert (ROOT / path.removeprefix("/app/")).is_dir()
        assert f"COPY {path.removeprefix('/app/')} {path}" in dockerfile()


def test_secrets_and_game_history_stay_out_of_the_build_context():
    lines = [
        line.strip()
        for line in (ROOT / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines[0] == "*", "ignore everything, then list what the image needs"
    included = [line[1:] for line in lines if line.startswith("!")]
    assert not [p for p in included if ".env" in p or p.startswith("data")]


def script_names(path: Path) -> set[str]:
    text = path.read_text()
    return set(re.findall(r"""(?:image|container|Image|Container)\s*=\s*['"]?([\w.-]+)""", text))


def test_the_scripts_agree_on_names_and_ports():
    names = {p.name: script_names(p) for p in SCRIPTS.iterdir()}
    assert set(names) == {"start_mac.sh", "stop_mac.sh", "start_pc.ps1", "stop_pc.ps1"}
    assert all(found == {"blokus-arena"} for found in names.values()), names
    label = re.search(r'org\.opencontainers\.image\.title="([^"]+)"', dockerfile())
    assert label and label[1] == "blokus-arena"
    port = env_value("GRADIO_SERVER_PORT")
    for start in ("start_mac.sh", "start_pc.ps1"):
        text = (SCRIPTS / start).read_text()
        assert re.search(rf'127\.0\.0\.1:\$\{{\w+\}}:{port}"', text), start
        assert "OLLAMA_BASE_URL=http://host.docker.internal:11434/v1" in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_the_mac_scripts_are_executable_bash():
    for name in ("start_mac.sh", "stop_mac.sh"):
        path = SCRIPTS / name
        assert os.access(path, os.X_OK), f"chmod +x scripts/{name}"
        assert b"\r\n" not in path.read_bytes()
        subprocess.run(["bash", "-n", str(path)], check=True)


@pytest.mark.parametrize("name", ["start_pc.ps1", "stop_pc.ps1"])
def test_the_windows_scripts_are_plain_ascii(name):
    # Windows PowerShell 5.1 reads a file without a byte order mark as ANSI, not UTF-8.
    (SCRIPTS / name).read_bytes().decode("ascii")
