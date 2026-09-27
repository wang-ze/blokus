import asyncio
from itertools import pairwise

import pytest

from blokus.match import Match, lineup
from blokus.players.heuristic import GreedyPlayer, TacticianPlayer
from blokus.players.human import HumanPlayer
from blokus.testing import FirstMovePlayer


def run(match: Match):
    async def collect():
        return [event async for event in match.play()]

    return asyncio.run(collect())


def test_lineup_always_seats_both_bots_plus_the_llms():
    llms = [FirstMovePlayer("LLM 1"), FirstMovePlayer("LLM 2")]
    players = lineup(llms, shuffle=False)
    assert [p.name for p in players] == ["Greedy", "Tactician", "LLM 1", "LLM 2"]
    assert isinstance(players[0], GreedyPlayer)
    assert isinstance(players[1], TacticianPlayer)
    assert [p.name for p in lineup([], shuffle=False)] == ["Greedy", "Tactician"]


def test_lineup_shuffles_reproducibly_and_limits_guests():
    llm = [FirstMovePlayer("LLM 1")]
    orders = {tuple(p.name for p in lineup(llm, seed=s)) for s in range(20)}
    assert len(orders) > 1
    assert [p.name for p in lineup(llm, seed=4)] == [p.name for p in lineup(llm, seed=4)]
    with pytest.raises(ValueError, match="At most 2 players can join"):
        lineup([FirstMovePlayer(str(i)) for i in range(3)])


def test_lineup_seats_a_person_with_the_bots():
    human = HumanPlayer()
    players = lineup([human, FirstMovePlayer("LLM 1")], shuffle=False)
    assert [p.name for p in players] == ["Greedy", "Tactician", "Human", "LLM 1"]
    assert [p.identity for p in players] == ["Greedy", "Tactician", "Human", "LLM 1"]


@pytest.mark.parametrize("num_players", [2, 3, 4])
def test_match_event_stream(num_players):
    players = [FirstMovePlayer(f"P{i}") for i in range(num_players)]
    events = run(Match(players))
    kinds = [e.kind for e in events]
    assert kinds[0] == "start"
    assert kinds[-1] == "over"
    assert kinds.count("over") == 1
    assert kinds.count("out") == 4
    # Every "thinking" event is immediately followed by the move it announced.
    for before, after in pairwise(events):
        if before.kind == "thinking":
            assert after.kind == "move"
            assert after.snapshot.log[-1].player == before.snapshot.to_move.player
            assert after.snapshot.log[-1].color == before.snapshot.to_move.color
    moves = [e.snapshot.log[-1] for e in events if e.kind == "move"]
    assert len(moves) == kinds.count("thinking")
    final = events[-1].snapshot
    assert final.over and final.to_move is None and final.winners
    assert len(final.log) == len(moves) + 4


def test_shared_color_moves_rotate_and_views_describe_the_mover():
    players = [FirstMovePlayer(name) for name in ("A", "B", "C")]
    final = run(Match(players))[-1].snapshot
    green = [e.player for e in final.log if e.color == "green" and e.piece is not None]
    assert green == [("A", "B", "C")[i % 3] for i in range(len(green))]
    out_entry = next(e for e in final.log if e.color == "green" and e.piece is None)
    assert out_entry.player == "Shared"
    for player in players:
        for view in player.views:
            if view.color.name == "GREEN":
                assert not view.scores_count
                assert view.board is not None and view.legal_moves


def test_stats_accumulate_per_player():
    steady, flaky = FirstMovePlayer("Steady"), FirstMovePlayer("Flaky", fallback="stand-in")
    final = run(Match([steady, flaky]))[-1].snapshot
    by_name = {p.name: p for p in final.players}
    assert by_name["Steady"].stats.moves == len(steady.views)
    assert by_name["Steady"].stats.fallbacks == 0
    assert by_name["Flaky"].stats.fallbacks == by_name["Flaky"].stats.moves == len(flaky.views)
    assert all(e.fallback for e in final.log if e.player == "Flaky" and e.piece)


def test_players_get_a_private_copy_of_the_board():
    class Vandal(FirstMovePlayer):
        async def choose_move(self, view):
            decision = await super().choose_move(view)
            view.board.grid[:] = [0] * len(view.board.grid)
            return decision

    match = Match([Vandal("V"), FirstMovePlayer("B")])
    final = run(match)[-1].snapshot
    assert final.over
    assert match.game.board.grid.count(-1) > 0
