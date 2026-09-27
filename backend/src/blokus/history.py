"""Where finished games are kept, so the history and ratings survive restarts.

Games are saved as JSON Lines under `<data dir>/games/<YYYY-MM>/<run id>.jsonl`. Each server
process writes only its own file per month, and rewrites it whole after every game. No file is
ever appended to or shared between processes, so this works on a local disk and on storage that
only supports writing whole files, such as a Hugging Face Storage Bucket mounted into a Space.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from blokus.ratings import Rating, ratings
from blokus.records import GameRecord

DATA_DIR_ENV = "BLOKUS_DATA_DIR"
DEFAULT_DATA_DIR = "data"

log = logging.getLogger(__name__)


class GameHistory:
    """Finished games, oldest first. Thread-safe.

    With `root=None` games are only kept in memory.
    """

    def __init__(self, root: Path | None, *, run_id: str | None = None) -> None:
        self.root = root
        self.run_id = run_id or f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
        self._lock = threading.Lock()
        self._records: list[GameRecord] = []
        self._ids: set[str] = set()
        self._mine: dict[str, list[GameRecord]] = {}
        """This run's games by month, as saved in this run's files."""
        self._ratings: list[Rating] | None = None
        if root is not None:
            self._load(root / "games")

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> GameHistory:
        """History under $BLOKUS_DATA_DIR, or ./data by default."""
        return cls(Path(env.get(DATA_DIR_ENV) or DEFAULT_DATA_DIR))

    def records(self) -> tuple[GameRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def ratings(self) -> list[Rating]:
        with self._lock:
            if self._ratings is None:
                self._ratings = ratings(self._records)
            return list(self._ratings)

    def add(self, record: GameRecord) -> None:
        """Keep a finished game, and save it if there is a data directory.

        A failure to save is logged rather than raised: the game still counts until a restart.
        """
        with self._lock:
            if record.id in self._ids:
                return
            self._ids.add(record.id)
            self._records.append(record)
            self._records.sort(key=lambda r: r.finished_at)
            self._ratings = None
            month = f"{record.finished_at:%Y-%m}"
            mine = self._mine.setdefault(month, [])
            mine.append(record)
            if self.root is None:
                return
            path = self.root / "games" / month / f"{self.run_id}.jsonl"
            text = "".join(json.dumps(r.to_json(), separators=(",", ":")) + "\n" for r in mine)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            except OSError:
                log.exception("Could not save game %s to %s", record.id, path)

    def _load(self, folder: Path) -> None:
        if not folder.is_dir():
            return
        for path in sorted(folder.glob("*/*.jsonl")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                log.exception("Could not read %s", path)
                continue
            for number, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                try:
                    record = GameRecord.from_json(json.loads(line))
                except (ValueError, KeyError, TypeError) as error:
                    log.warning("Skipping %s line %d: %s", path, number, error)
                    continue
                if record.id not in self._ids:
                    self._ids.add(record.id)
                    self._records.append(record)
        self._records.sort(key=lambda r: r.finished_at)
