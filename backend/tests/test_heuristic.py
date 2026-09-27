import asyncio
from collections import Counter

import pytest

from blokus.board import START_CORNERS, Color
from blokus.match import Match
from blokus.players.heuristic import (
    GreedyPlayer,
    RandomPlayer,
    TacticianPlayer,
    TacticianWeights,
    _Features,
)
from blokus.simulate import play
from blokus.testing import FirstMovePlayer, random_game


def view_after(turns: int, seed: int, num_players: int = 4):
    """The view for whoever moves after `turns` random turns (skipping colors that are out)."""
    match = Match([FirstMovePlayer(f"P{i}") for i in range(num_players)])
    match.game = random_game(num_players, seed, turns)
    while not match.game.board.has_legal_move(match.game.current_color):
        match.game.retire_current()
    return match.turn_view()


def test_greedy_opens_with_a_pentomino_on_its_corner():
    view = view_after(0, seed=0)
    decision = GreedyPlayer("Greedy", seed=1).decide(view)
    assert len(decision.move.cells) == 5
    assert START_CORNERS[Color.BLUE] in decision.move.cells


@pytest.mark.parametrize(("turns", "seed"), [(0, 1), (9, 2), (24, 3), (41, 4)])
def test_tactician_features_match_a_full_recomputation(turns, seed):
    view = view_after(turns, seed)
    features = _Features(view)
    board = view.board
    own_before = len(board.anchors(view.color))
    for move in view.legal_moves[::7]:
        after = board.copy()
        after.apply(move)
        mobility, blocked, hurt = features(move)
        assert mobility == len(after.anchors(view.color)) - own_before
        assert blocked == sum(len(board.anchors(c) & move.cells) for c in view.opponents)
        assert hurt == sum(len(board.anchors(c) & move.cells) for c in view.friendly)


def test_tactician_with_a_huge_block_weight_picks_a_maximal_blocking_move():
    view = view_after(30, seed=6)
    features = _Features(view)
    most_blocked = max(features(m)[1] for m in view.legal_moves)
    assert most_blocked > 0
    player = TacticianPlayer("T", seed=0, weights=TacticianWeights(block=1000))
    assert features(player.decide(view).move)[1] == most_blocked


def test_heuristic_games_are_deterministic_per_seed():
    def moves(seed: int):
        players = [GreedyPlayer("Greedy", seed=seed), TacticianPlayer("Tactician", seed=seed)]
        return [(e.player, e.piece, e.cells) for e in asyncio.run(play(players)).log]

    assert moves(1) == moves(1)
    assert moves(1) != moves(2)


def test_a_full_bot_game_ends_in_a_consistent_state():
    players = [
        GreedyPlayer("Greedy", seed=3),
        TacticianPlayer("Tactician", seed=3),
        RandomPlayer("Random", seed=3),
    ]
    snapshot = asyncio.run(play(players))
    assert snapshot.over
    moves_by_player = Counter(e.player for e in snapshot.log if e.piece is not None)
    for player in snapshot.players:
        assert player.stats.moves == moves_by_player[player.name]
        assert player.squares_left == sum(p.size for c in player.colors for p in c.remaining)
    best = max(p.score for p in snapshot.players)
    assert set(snapshot.winners) == {p.name for p in snapshot.players if p.score == best}
