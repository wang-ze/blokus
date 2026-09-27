"""Helpers for tests of the engine and of front ends: a scripted player, random positions
and sample game records. Nothing here is used by the app itself."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from blokus.game import Game
from blokus.match import Match
from blokus.players import Decision, Player, TurnView
from blokus.records import GameRecord, PlayerResult


def random_game(num_players: int, seed: int, turns: int | None = None) -> Game:
    """A game advanced with random legal moves, to the end or for `turns` turns."""
    rng = random.Random(seed)
    game = Game(num_players)
    while not game.is_over and (turns is None or len(game.turns) < turns):
        color = game.current_color
        assert color is not None
        moves = game.board.legal_moves(color)
        if moves:
            game.play(rng.choice(moves))
        else:
            game.retire_current()
    return game


class FirstMovePlayer(Player):
    """Always plays the first legal move. Optionally reports every move as a fallback."""

    kind = "bot"

    def __init__(self, name: str, *, fallback: str = "") -> None:
        super().__init__(name)
        self.fallback = fallback
        self.views: list[TurnView] = []

    @property
    def detail(self) -> str:
        return "first legal move"

    async def choose_move(self, view: TurnView) -> Decision:
        self.views.append(view)
        return Decision(view.legal_moves[0], fallback=self.fallback)


def make_record(
    *seats: tuple[str, int] | tuple[str, int, str],
    minutes: int = 0,
    game_id: str | None = None,
) -> GameRecord:
    """A record from (identity, score[, kind]) seats; the top score wins."""
    best = max(seat[1] for seat in seats)
    colors = (
        [("blue", "red"), ("yellow", "green")]
        if len(seats) == 2
        else [("blue",), ("yellow",), ("red",), ("green",)][: len(seats)]
    )
    players = tuple(
        PlayerResult(
            name=f"{seat[0]} {i}",
            kind=seat[2] if len(seat) > 2 else "bot",
            identity=seat[0],
            colors=colors[i],
            score=seat[1],
            winner=seat[1] == best,
            moves=10,
            fallbacks=0,
        )
        for i, seat in enumerate(seats)
    )
    return GameRecord(
        id=game_id or f"game-{minutes}-{'-'.join(s[0] for s in seats)}",
        finished_at=datetime(2026, 9, 26, 12, tzinfo=UTC) + timedelta(minutes=minutes),
        players=players,
        color_scores={c: 0 for p in players for c in p.colors},
        shared="green" if len(seats) == 3 else None,
        turns=40,
        moves=(),
    )


def mid_game_match(num_players: int, turns: int = 25) -> Match:
    """A match between first-move players, set to a random position `turns` turns in."""
    match = Match([FirstMovePlayer(f"P{i}") for i in range(num_players)])
    match.game = random_game(num_players, seed=num_players, turns=turns)
    return match
