"""The player interface shared by heuristic bots, LLM agents and people."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Literal

from blokus.board import Board, Color, Move
from blokus.game import Turn


@dataclass(frozen=True, slots=True)
class Standing:
    """How one player is doing, as shown to other players."""

    name: str
    colors: tuple[Color, ...]
    score: int
    squares_left: int


@dataclass(frozen=True, slots=True)
class TurnView:
    """Everything a player may use to choose a move.

    `board` is a private copy, so players can inspect it freely. `legal_moves` is never empty:
    colors without a legal move are retired by the match before any player is asked.
    """

    board: Board
    color: Color
    turn: int
    player: int
    friendly: tuple[Color, ...]
    opponents: tuple[Color, ...]
    scores_count: bool
    legal_moves: tuple[Move, ...]
    standings: tuple[Standing, ...]
    recent_turns: tuple[Turn, ...]


@dataclass(frozen=True, slots=True)
class Decision:
    move: Move
    reasoning: str = ""
    fallback: str = ""
    """Empty when the player chose the move. Otherwise who chose it instead, as a short label
    such as "random fallback" or "played by Tactician"."""
    error: str | None = None
    invalid_attempts: int = 0
    tokens: int = 0


type PlayerKind = Literal["bot", "llm", "human"]


class Player(ABC):
    kind: ClassVar[PlayerKind]

    def __init__(self, name: str) -> None:
        self.name = name
        """The name shown in this game, e.g. "LLM 1"."""

    @property
    def identity(self) -> str:
        """Who is playing across games, for ratings: the bot, the model, or "Human"."""
        return self.name

    @property
    @abstractmethod
    def detail(self) -> str:
        """A short description, such as the strategy or the model."""

    @abstractmethod
    async def choose_move(self, view: TurnView) -> Decision:
        """Pick one of `view.legal_moves`."""
