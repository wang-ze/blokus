"""Finished games as plain records, for the game history and the leaderboard."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from blokus.snapshot import GameSnapshot

RECORD_VERSION = 1


@dataclass(frozen=True, slots=True)
class PlayerResult:
    name: str
    """The name in that game, e.g. "LLM 1"."""
    kind: str
    """"bot", "llm" or "human"."""
    identity: str
    """Who played, across games: the bot, the model (e.g. "gemini:gemini-3.1-flash-lite"), or
    "Human"."""
    colors: tuple[str, ...]
    score: int
    winner: bool
    moves: int
    fallbacks: int
    """Moves someone else chose for this player (random fallbacks, or bots after a timeout)."""


@dataclass(frozen=True, slots=True)
class GameRecord:
    id: str
    finished_at: datetime
    """When the game ended, in UTC."""
    players: tuple[PlayerResult, ...]
    """In seat order: seat 0 played Blue."""
    color_scores: dict[str, int]
    """Every color's score, including a shared color's (which counts for nobody)."""
    shared: str | None
    """The color the players took turns moving, in a 3-player game."""
    turns: int
    moves: tuple[str, ...]
    """Every piece placed, oldest first, as "<color> <piece> <cells>", e.g. "blue I2 A1 B1"."""
    version: int = RECORD_VERSION

    @classmethod
    def from_snapshot(
        cls,
        snapshot: GameSnapshot,
        *,
        game_id: str | None = None,
        finished_at: datetime | None = None,
    ) -> GameRecord:
        if not snapshot.over:
            raise ValueError("Only finished games can be recorded.")
        winners = set(snapshot.winners)
        color_scores = {c.color: c.score for p in snapshot.players for c in p.colors}
        if snapshot.shared is not None:
            color_scores[snapshot.shared.color] = snapshot.shared.score
        return cls(
            id=game_id or uuid.uuid4().hex,
            finished_at=finished_at or datetime.now(UTC),
            players=tuple(
                PlayerResult(
                    name=p.name,
                    kind=p.kind,
                    identity=p.identity,
                    colors=tuple(c.color for c in p.colors),
                    score=p.score,
                    winner=p.name in winners,
                    moves=p.stats.moves,
                    fallbacks=p.stats.fallbacks,
                )
                for p in snapshot.players
            ),
            color_scores=color_scores,
            shared=snapshot.shared.color if snapshot.shared else None,
            turns=snapshot.turn,
            moves=tuple(
                f"{e.color} {e.piece} {' '.join(e.cells)}"
                for e in snapshot.log
                if e.piece is not None
            ),
        )

    @property
    def winners(self) -> tuple[PlayerResult, ...]:
        return tuple(p for p in self.players if p.winner)

    def player_of(self, color: str) -> PlayerResult | None:
        """Who owned `color`, or None for the shared color."""
        return next((p for p in self.players if color in p.colors), None)

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "id": self.id,
            "finished_at": self.finished_at.isoformat(),
            "players": [
                {
                    "name": p.name,
                    "kind": p.kind,
                    "identity": p.identity,
                    "colors": list(p.colors),
                    "score": p.score,
                    "winner": p.winner,
                    "moves": p.moves,
                    "fallbacks": p.fallbacks,
                }
                for p in self.players
            ],
            "color_scores": dict(self.color_scores),
            "shared": self.shared,
            "turns": self.turns,
            "moves": list(self.moves),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> GameRecord:
        version = data.get("version")
        if version != RECORD_VERSION:
            raise ValueError(f"Unsupported game record version {version!r}.")
        finished_at = datetime.fromisoformat(data["finished_at"])
        if finished_at.tzinfo is None:
            raise ValueError("finished_at must include a time zone.")
        return cls(
            id=str(data["id"]),
            finished_at=finished_at.astimezone(UTC),
            players=tuple(
                PlayerResult(
                    name=str(p["name"]),
                    kind=str(p["kind"]),
                    identity=str(p["identity"]),
                    colors=tuple(map(str, p["colors"])),
                    score=int(p["score"]),
                    winner=bool(p["winner"]),
                    moves=int(p["moves"]),
                    fallbacks=int(p["fallbacks"]),
                )
                for p in data["players"]
            ),
            color_scores={str(k): int(v) for k, v in data["color_scores"].items()},
            shared=data["shared"],
            turns=int(data["turns"]),
            moves=tuple(map(str, data["moves"])),
        )
