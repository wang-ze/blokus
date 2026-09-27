"""Heuristic computer players. Each scores every legal move and plays the best one (one ply)."""

from __future__ import annotations

import asyncio
import random
from abc import abstractmethod
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from blokus.board import BOARD_SIZE, DIAGONAL, EMPTY, NUM_CELLS, ORTHOGONAL, Board, Color, Move
from blokus.pieces import PIECE_NAMES
from blokus.players import Decision, Player, TurnView

_MID = (BOARD_SIZE - 1) / 2
# How central each cell is: 0 in the corners, rising to 18 in the four middle cells.
CENTRALITY: tuple[float, ...] = tuple(
    BOARD_SIZE - 1 - (abs(row - _MID) + abs(col - _MID))
    for row, col in (divmod(i, BOARD_SIZE) for i in range(NUM_CELLS))
)
_EPSILON = 1e-9


class HeuristicPlayer(Player):
    kind = "bot"

    def __init__(self, name: str, seed: int | None = None) -> None:
        super().__init__(name)
        self._rng = random.Random(seed)

    async def choose_move(self, view: TurnView) -> Decision:
        # Scoring hundreds of moves is CPU work; keep the event loop (and the UI) responsive.
        return await asyncio.to_thread(self.decide, view)

    def decide(self, view: TurnView) -> Decision:
        """Play the highest-scoring legal move, breaking ties at random."""
        score = self.scorer(view)
        best: list[Move] = []
        best_score = float("-inf")
        for move in view.legal_moves:
            value = score(move)
            if value > best_score + _EPSILON:
                best, best_score = [move], value
            elif value >= best_score - _EPSILON:
                best.append(move)
        move = self._rng.choice(best)
        return Decision(move, reasoning=self.explain(view, move))

    @abstractmethod
    def scorer(self, view: TurnView) -> Callable[[Move], float]:
        """A scoring function for this turn's moves (it may precompute per-turn data)."""

    def explain(self, view: TurnView, move: Move) -> str:
        """A short note on the chosen move for the game log."""
        return ""


class RandomPlayer(HeuristicPlayer):
    """Plays a uniformly random legal move. The baseline for simulations."""

    @property
    def detail(self) -> str:
        return "Random legal moves"

    def decide(self, view: TurnView) -> Decision:
        return Decision(self._rng.choice(view.legal_moves))

    def scorer(self, view: TurnView) -> Callable[[Move], float]:
        return lambda move: 0.0


class GreedyPlayer(HeuristicPlayer):
    """Biggest piece first, as close to the center as possible. Ignores opponents."""

    @property
    def detail(self) -> str:
        return "Greedy heuristic: biggest piece, closest to the center"

    def scorer(self, view: TurnView) -> Callable[[Move], float]:
        return lambda move: 10 * len(move.cells) + 1.5 * sum(CENTRALITY[i] for i in move.cells)


@dataclass(frozen=True, slots=True)
class TacticianWeights:
    size: float = 3.0
    """Per square placed: unplayed squares cost points at the end."""
    mobility: float = 2.0
    """Per corner point gained (net) for the moving color."""
    block: float = 2.5
    """Per opponent corner point covered."""
    friendly: float = 1.5
    """Penalty per corner point covered that belongs to the mover's other color."""
    center: float = 1.0
    """Pull toward the center (per point of average centrality) while the color is young."""
    center_fade_moves: int = 6
    """The center pull fades to zero after this many pieces."""


class TacticianPlayer(HeuristicPlayer):
    """Balances piece size, its own corner points, and blocking opponents' corner points.

    Corner points ("anchors") are the cells where a color can attach its next piece, so they
    measure how much room a color has to keep playing.
    """

    def __init__(
        self, name: str, seed: int | None = None, weights: TacticianWeights | None = None
    ) -> None:
        super().__init__(name, seed)
        self.weights = weights or TacticianWeights()

    @property
    def detail(self) -> str:
        return "Tactician heuristic: size, own corner points, blocking opponents"

    def scorer(self, view: TurnView) -> Callable[[Move], float]:
        w = self.weights
        features = _Features(view)
        placed = len(PIECE_NAMES) - len(view.board.remaining[view.color])
        center_pull = w.center * max(0.0, 1 - placed / w.center_fade_moves)

        def score(move: Move) -> float:
            size = len(move.cells)
            mobility, blocked, hurt = features(move)
            if not view.scores_count:
                # The shared color scores nothing: use it purely to hinder opponents, with a
                # slight preference for bigger pieces, which take more space from them.
                return w.block * blocked - w.friendly * hurt + 0.1 * size
            center = center_pull * sum(CENTRALITY[i] for i in move.cells) / size
            return (
                w.size * size
                + w.mobility * mobility
                + w.block * blocked
                - w.friendly * hurt
                + center
            )

        return score

    def explain(self, view: TurnView, move: Move) -> str:
        mobility, blocked, hurt = _Features(view)(move)
        parts = [f"corner points {mobility:+d}"]
        if blocked:
            parts.append(f"blocks {blocked} opponent corner point{'s' * (blocked > 1)}")
        if hurt:
            parts.append(f"covers {hurt} of its own other color's corner points")
        return ", ".join(parts)


class _Features:
    """Per-turn precomputation of anchor data, then cheap per-move feature extraction."""

    def __init__(self, view: TurnView) -> None:
        board: Board = view.board
        self._grid = board.grid
        self._color: Color = view.color
        self._own = board.anchors(view.color)
        self._opponents = Counter(a for c in view.opponents for a in board.anchors(c))
        self._friendly = Counter(a for c in view.friendly for a in board.anchors(c))

    def __call__(self, move: Move) -> tuple[int, int, int]:
        """(net corner points gained, opponent corner points covered, friendly ones covered)."""
        grid, me, own, cells = self._grid, self._color, self._own, move.cells
        # Cells a later piece of this color can no longer cover: the piece and its edges.
        touched = set(cells)
        for i in cells:
            touched.update(ORTHOGONAL[i])
        lost = len(own & touched)
        gained = 0
        checked: set[int] = set()
        for i in cells:
            for j in DIAGONAL[i]:
                if j in touched or j in own or j in checked or grid[j] != EMPTY:
                    continue
                checked.add(j)
                if all(grid[k] != me for k in ORTHOGONAL[j]):
                    gained += 1
        blocked = sum(self._opponents[i] for i in cells)
        hurt = sum(self._friendly[i] for i in cells)
        return gained - lost, blocked, hurt
