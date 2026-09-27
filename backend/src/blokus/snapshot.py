"""Plain-data views of a game, for front ends.

Front ends render only `GameSnapshot`s and never touch the engine, so the UI can be redesigned
or replaced without changing game code. `GameSnapshot.to_dict()` is JSON-serializable, so a
non-Python front end can consume the same data.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from blokus.board import BOARD_SIZE, EMPTY, Board, Color, Move
from blokus.pieces import PIECES


@dataclass(frozen=True, slots=True)
class PieceView:
    name: str
    size: int
    cells: tuple[tuple[int, int], ...]
    """(row, col) squares of the piece in its canonical orientation."""


@dataclass(frozen=True, slots=True)
class ColorView:
    color: str
    """Lowercase color key, e.g. "blue"."""
    label: str
    score: int
    squares_left: int
    out: bool
    """True once the color has no legal move left."""
    remaining: tuple[PieceView, ...]


@dataclass(frozen=True, slots=True)
class PlayerStats:
    moves: int = 0
    think_seconds: float = 0.0
    invalid_attempts: int = 0
    fallbacks: int = 0
    tokens: int = 0


@dataclass(frozen=True, slots=True)
class PlayerView:
    index: int
    name: str
    kind: str
    """"bot", "llm" or "human"."""
    identity: str
    """Who is playing across games, for ratings: the bot, the model, or "Human"."""
    detail: str
    score: int
    squares_left: int
    active: bool
    colors: tuple[ColorView, ...]
    stats: PlayerStats


@dataclass(frozen=True, slots=True)
class LogEntry:
    turn: int
    color: str
    player: str
    piece: str | None
    """None when the color had no legal move and is out."""
    cells: tuple[str, ...]
    reasoning: str = ""
    fallback: str = ""
    """Empty when the player chose the move, else who did, e.g. "random fallback"."""
    error: str | None = None
    seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class ToMove:
    color: str
    player: str
    player_kind: str
    player_detail: str


@dataclass(frozen=True, slots=True)
class HumanTurn:
    """What a person needs to place a piece. Sent on "thinking" events for human players."""

    turn: int
    """The number of the turn being played."""
    color: str
    seconds: float
    """The time limit for this move."""
    pieces: tuple[PieceView, ...]
    """This color's remaining pieces."""
    playable: tuple[str, ...]
    """Names of the remaining pieces that have at least one legal placement."""
    legal: tuple[str, ...]
    """Every legal placement, as a `placement_key`."""
    anchors: tuple[tuple[int, int], ...]
    """(row, col) of this color's corner points: every legal placement covers one of them."""


@dataclass(frozen=True, slots=True)
class GameSnapshot:
    event: str
    """What just happened: "start", "thinking", "move", "out" or "over"."""
    over: bool
    """True once no color can move. The last "out" event is already over, before "over" itself."""
    turn: int
    """Number of turns completed so far."""
    grid: tuple[tuple[str | None, ...], ...]
    """grid[row][col] is a color key, or None for an empty cell. Row 0 is the top row."""
    last_move: tuple[tuple[int, int], ...]
    to_move: ToMove | None
    """Who is to move (and, on "thinking" events, is thinking right now); None once over."""
    players: tuple[PlayerView, ...]
    shared: ColorView | None
    """The shared color in a 3-player game, which no player owns."""
    log: tuple[LogEntry, ...]
    """Every turn so far, oldest first."""
    winners: tuple[str, ...]
    """Names of the winners (several on a tie); empty until the game is over."""
    human_turn: HumanTurn | None = None
    """Set while a person is to move."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def color_key(color: Color) -> str:
    return color.name.lower()


def placement_key(piece: str, cells: Iterable[int]) -> str:
    """A placement as text: the piece name, then its cell indices (row * 20 + col) in ascending
    order, e.g. "I2:0,1". Front ends build the same key to look up whether a placement is legal."""
    return f"{piece}:{','.join(map(str, sorted(cells)))}"


def human_turn(board: Board, turn: int, seconds: float, legal: Iterable[Move]) -> HumanTurn:
    moves = tuple(legal)
    if not moves:
        raise ValueError("A human turn needs at least one legal move.")
    color = moves[0].color
    playable = {move.piece for move in moves}
    return HumanTurn(
        turn=turn,
        color=color_key(color),
        seconds=seconds,
        pieces=color_view(board, color, out=False).remaining,
        playable=tuple(name for name in board.remaining_pieces(color) if name in playable),
        legal=tuple(sorted(placement_key(move.piece, move.cells) for move in moves)),
        anchors=tuple(sorted(divmod(i, BOARD_SIZE) for i in board.anchors(color))),
    )


def grid_view(board: Board) -> tuple[tuple[str | None, ...], ...]:
    keys = {color.value: color_key(color) for color in Color}
    keys[EMPTY] = None
    return tuple(
        tuple(keys[board.grid[row * BOARD_SIZE + col]] for col in range(BOARD_SIZE))
        for row in range(BOARD_SIZE)
    )


def color_view(board: Board, color: Color, *, out: bool) -> ColorView:
    return ColorView(
        color=color_key(color),
        label=color.label,
        score=board.score(color),
        squares_left=board.remaining_squares(color),
        out=out,
        remaining=tuple(
            PieceView(name, PIECES[name].size, PIECES[name].shape)
            for name in board.remaining_pieces(color)
        ),
    )
