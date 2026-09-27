"""A seat for a person, who places pieces through the front end."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Sequence
from dataclasses import dataclass

from blokus.board import Move
from blokus.players import Decision, Player, TurnView
from blokus.players.heuristic import GreedyPlayer, HeuristicPlayer, TacticianPlayer

HUMAN_NAME = "Human"
TIME_LIMIT_SECONDS = 15.0
SUBMIT_GRACE_SECONDS = 1.0
"""Extra time the server waits, so a move sent at the last moment can still arrive."""


@dataclass(slots=True)
class _Pending:
    turn: int
    view: TurnView
    move: asyncio.Future[Move]


class HumanPlayer(Player):
    """Waits for `submit` from the front end. When time runs out, a bot moves instead.

    The stand-in is chosen at random for each timed-out turn, from Greedy and Tactician.
    """

    kind = "human"

    def __init__(
        self,
        name: str = HUMAN_NAME,
        *,
        time_limit: float = TIME_LIMIT_SECONDS,
        seed: int | None = None,
    ) -> None:
        super().__init__(name)
        self.time_limit = time_limit
        self._rng = random.Random(seed)
        self._stand_ins: tuple[HeuristicPlayer, ...] = (
            GreedyPlayer("Greedy", seed=self._rng.getrandbits(32)),
            TacticianPlayer("Tactician", seed=self._rng.getrandbits(32)),
        )
        self._pending: _Pending | None = None

    @property
    def identity(self) -> str:
        return HUMAN_NAME

    @property
    def detail(self) -> str:
        return f"You: {self.time_limit:g}s per move, or a bot moves for you"

    @property
    def waiting_for(self) -> int | None:
        """The number of the turn waiting for a move, if any."""
        return self._pending.turn if self._pending else None

    async def choose_move(self, view: TurnView) -> Decision:
        pending = _Pending(view.turn, view, asyncio.get_running_loop().create_future())
        self._pending = pending
        try:
            move = await asyncio.wait_for(pending.move, self.time_limit + SUBMIT_GRACE_SECONDS)
            return Decision(move)
        except TimeoutError:
            pass
        finally:
            self._pending = None
        stand_in = self._rng.choice(self._stand_ins)
        decision = await stand_in.choose_move(view)
        return Decision(
            decision.move,
            reasoning=decision.reasoning,
            fallback=f"played by {stand_in.name}",
            error=f"No move within {self.time_limit:g}s.",
        )

    def submit(self, turn: int, piece: str, cells: Sequence[str]) -> str | None:
        """Play `piece` on `cells` (e.g. ["A1", "B1"]) for turn number `turn`.

        Returns None if the move was accepted, or else why not. Call it from the event loop that
        runs the match.
        """
        pending = self._pending
        if pending is None or pending.turn != turn or pending.move.done():
            return "It is not your turn any more."
        view = pending.view
        try:
            move = view.board.validate(view.color, piece, cells)
        except ValueError as error:
            return str(error)
        pending.move.set_result(move)
        return None
