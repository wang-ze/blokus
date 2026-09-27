"""Headless tournaments between heuristic bots, for tuning and sanity checks.

    uv run blokus-sim --games 40 --players 2 --seed 1

Seats rotate every game so each bot plays every color equally often.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from blokus.match import Match
from blokus.players import Player
from blokus.players.heuristic import GreedyPlayer, RandomPlayer, TacticianPlayer
from blokus.snapshot import GameSnapshot

BOTS: dict[str, Callable[[str, int], Player]] = {
    "greedy": lambda name, seed: GreedyPlayer(name, seed=seed),
    "tactician": lambda name, seed: TacticianPlayer(name, seed=seed),
    "random": lambda name, seed: RandomPlayer(name, seed=seed),
}


@dataclass
class SeriesResult:
    names: list[str]
    games: int = 0
    wins: dict[str, float] = field(default_factory=dict)
    total_scores: dict[str, int] = field(default_factory=dict)
    moves: int = 0
    seconds: float = 0.0

    def report(self) -> str:
        lines = [f"{' vs '.join(self.names)}: {self.games} games"]
        for name in self.names:
            win_rate = self.wins.get(name, 0.0) / self.games
            avg_score = self.total_scores.get(name, 0) / self.games
            lines.append(f"  {name:<12} win rate {win_rate:6.1%}   avg score {avg_score:6.1f}")
        lines.append(f"  {1000 * self.seconds / max(self.moves, 1):.1f} ms per move")
        return "\n".join(lines)


async def play(players: Sequence[Player]) -> GameSnapshot:
    snapshot = None
    async for event in Match(players).play():
        snapshot = event.snapshot
    assert snapshot is not None and snapshot.over
    return snapshot


def run_series(kinds: Sequence[str], games: int, seed: int) -> SeriesResult:
    """Play `games` games between bots of the given kinds, rotating seats each game."""
    names = []
    for i, kind in enumerate(kinds):
        suffix = f" {kinds[: i + 1].count(kind)}" if kinds.count(kind) > 1 else ""
        names.append(kind.capitalize() + suffix)
    result = SeriesResult(names)
    rng = random.Random(seed)
    for game in range(games):
        shift = game % len(kinds)
        order = list(range(len(kinds)))[shift:] + list(range(len(kinds)))[:shift]
        players = [BOTS[kinds[i]](names[i], rng.getrandbits(32)) for i in order]
        started = time.perf_counter()
        snapshot = asyncio.run(play(players))
        result.seconds += time.perf_counter() - started
        result.moves += sum(1 for entry in snapshot.log if entry.piece is not None)
        result.games += 1
        for winner in snapshot.winners:
            result.wins[winner] = result.wins.get(winner, 0.0) + 1 / len(snapshot.winners)
        for player in snapshot.players:
            result.total_scores[player.name] = (
                result.total_scores.get(player.name, 0) + player.score
            )
    return result


LINEUPS: dict[int, list[list[str]]] = {
    2: [["tactician", "greedy"], ["tactician", "random"], ["greedy", "random"]],
    3: [["tactician", "greedy", "random"]],
    4: [["tactician", "greedy", "random", "random"]],
}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--games", type=int, default=20, help="games per lineup")
    parser.add_argument("--players", type=int, choices=sorted(LINEUPS), default=2)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    for kinds in LINEUPS[args.players]:
        print(run_series(kinds, args.games, args.seed).report())


if __name__ == "__main__":
    main()
