"""Elo ratings from finished games.

A game with N players counts as a match between every pair of players, won by the one with the
higher score (equal scores are a draw). Each pairing moves ratings by up to K / (N - 1) points,
so a whole game is worth about as much as one head-to-head match. Everyone's changes are worked
out from their ratings before the game.

A bot, a model or "Human" can fill two seats in one game (for example the same model in both LLM
seats). Those two seats are not compared with each other, but both count against everyone else.

Ratings are recomputed from the full history, oldest game first, so the history is the only
state to keep.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations

from blokus.records import GameRecord

INITIAL_RATING = 1500.0
K_FACTOR = 32.0


@dataclass(frozen=True, slots=True)
class Rating:
    kind: str
    identity: str
    rating: float
    games: int
    wins: int
    """Games won, including ties for first place."""
    last_played: datetime


def expected_score(rating: float, opponent: float) -> float:
    """The chance of beating `opponent`, counting a draw as half a win."""
    return 1 / (1 + 10 ** ((opponent - rating) / 400))


def ratings(
    records: Iterable[GameRecord],
    *,
    k_factor: float = K_FACTOR,
    initial: float = INITIAL_RATING,
) -> list[Rating]:
    """Everyone's rating after `records`, best first."""
    rating: dict[tuple[str, str], float] = defaultdict(lambda: initial)
    games: dict[tuple[str, str], int] = defaultdict(int)
    wins: dict[tuple[str, str], int] = defaultdict(int)
    last_played: dict[tuple[str, str], datetime] = {}
    for record in sorted(records, key=lambda r: r.finished_at):
        seats = [((p.kind, p.identity), p.score) for p in record.players]
        if len(seats) < 2:
            continue
        step = k_factor / (len(seats) - 1)
        change: dict[tuple[str, str], float] = defaultdict(float)
        for (a, score_a), (b, score_b) in combinations(seats, 2):
            if a == b:
                continue
            actual = 1.0 if score_a > score_b else 0.5 if score_a == score_b else 0.0
            delta = step * (actual - expected_score(rating[a], rating[b]))
            change[a] += delta
            change[b] -= delta
        for key, delta in change.items():
            rating[key] += delta
        for key in {key for key, _ in seats}:
            games[key] += 1
            last_played[key] = record.finished_at
        for key in {(p.kind, p.identity) for p in record.winners}:
            wins[key] += 1
    table = [
        Rating(*key, rating=rating[key], games=count, wins=wins[key], last_played=last_played[key])
        for key, count in games.items()
    ]
    return sorted(table, key=lambda r: (-r.rating, -r.games, r.identity))
