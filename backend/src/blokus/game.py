"""Turn order, which player controls which color, and player scores.

Seating follows BLOKUS.MD:
- 2 players: player 0 plays Blue and Red, player 1 plays Yellow and Green.
- 3 players: players 0-2 play Blue, Yellow and Red. Green is shared: the players take turns
  moving it (player 0, then 1, then 2, ...) and its score counts for nobody.
- 4 players: one color each.
"""

from __future__ import annotations

from dataclasses import dataclass

from blokus.board import Board, Color, IllegalMove, Move

TURN_ORDER: tuple[Color, ...] = tuple(Color)
SHARED_COLOR = Color.GREEN

_OWNERS: dict[int, dict[Color, int | None]] = {
    2: {Color.BLUE: 0, Color.YELLOW: 1, Color.RED: 0, Color.GREEN: 1},
    3: {Color.BLUE: 0, Color.YELLOW: 1, Color.RED: 2, SHARED_COLOR: None},
    4: {Color.BLUE: 0, Color.YELLOW: 1, Color.RED: 2, Color.GREEN: 3},
}


@dataclass(frozen=True, slots=True)
class Turn:
    """One color's turn: a placed piece, or `move=None` when the color had no legal move left."""

    number: int
    color: Color
    player: int
    move: Move | None


class Game:
    def __init__(self, num_players: int) -> None:
        if num_players not in _OWNERS:
            raise ValueError(f"Blokus needs 2, 3 or 4 players, not {num_players}.")
        self.num_players = num_players
        self.board = Board()
        self.turns: list[Turn] = []
        # Colors that had no legal move on their turn. Legal moves only shrink as the board
        # fills, so these colors are out for the rest of the game.
        self.finished: set[Color] = set()
        self._current: Color | None = TURN_ORDER[0]
        self._shared_moves = 0

    # Seating

    def owner(self, color: Color) -> int | None:
        """The player who owns a color, or None for the shared color in a 3-player game."""
        return _OWNERS[self.num_players][color]

    def colors_of(self, player: int) -> tuple[Color, ...]:
        return tuple(color for color in TURN_ORDER if self.owner(color) == player)

    def controller(self, color: Color) -> int:
        """The player who moves `color` on its next turn."""
        owner = self.owner(color)
        return owner if owner is not None else self._shared_moves % self.num_players

    def perspective(self, color: Color) -> tuple[tuple[Color, ...], tuple[Color, ...], bool]:
        """(friendly, opponents, scores_count) for whoever moves `color` next.

        Friendly colors are the mover's other scored colors; opponents are every scored color
        owned by another player. The shared color is neither.
        """
        player = self.controller(color)
        friendly = tuple(c for c in self.colors_of(player) if c != color)
        opponents = tuple(
            c for c in TURN_ORDER if (owner := self.owner(c)) is not None and owner != player
        )
        return friendly, opponents, self.owner(color) is not None

    # Progress

    @property
    def current_color(self) -> Color | None:
        """The color to move, or None once the game is over."""
        return self._current

    @property
    def is_over(self) -> bool:
        return self._current is None

    def play(self, move: Move) -> Turn:
        color = self._require_turn()
        if move.color != color:
            raise IllegalMove(f"It is {color.label}'s turn, not {move.color.label}'s.")
        player = self.controller(color)
        self.board.apply(move)
        if self.owner(color) is None:
            self._shared_moves += 1
        return self._record(color, player, move)

    def retire_current(self) -> Turn:
        """End the current color's game because it has no legal move."""
        color = self._require_turn()
        if self.board.has_legal_move(color):
            raise IllegalMove(f"{color.label} still has a legal move.")
        self.finished.add(color)
        return self._record(color, self.controller(color), None)

    def _require_turn(self) -> Color:
        if self._current is None:
            raise IllegalMove("The game is over.")
        return self._current

    def _record(self, color: Color, player: int, move: Move | None) -> Turn:
        turn = Turn(len(self.turns) + 1, color, player, move)
        self.turns.append(turn)
        self._current = next(
            (
                candidate
                for step in range(1, len(TURN_ORDER) + 1)
                if (candidate := TURN_ORDER[(color + step) % len(TURN_ORDER)]) not in self.finished
            ),
            None,
        )
        return turn

    # Scoring

    def player_score(self, player: int) -> int:
        return sum(self.board.score(color) for color in self.colors_of(player))

    def scores(self) -> list[int]:
        return [self.player_score(player) for player in range(self.num_players)]

    def winners(self) -> list[int]:
        """Players with the highest score (more than one on a tie)."""
        scores = self.scores()
        best = max(scores)
        return [player for player, score in enumerate(scores) if score == best]
