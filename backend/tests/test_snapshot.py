import json

import pytest

from blokus.board import Color
from blokus.testing import mid_game_match


@pytest.mark.parametrize("num_players", [2, 3, 4])
def test_snapshot_mirrors_the_engine(num_players):
    match = mid_game_match(num_players)
    game, board = match.game, match.game.board
    snapshot = match.snapshot("move")
    json.dumps(snapshot.to_dict())  # plain data only

    assert snapshot.turn == len(game.turns)
    for row in range(20):
        for col in range(20):
            value = board.grid[row * 20 + col]
            expected = None if value == -1 else Color(value).name.lower()
            assert snapshot.grid[row][col] == expected

    for player in snapshot.players:
        colors = game.colors_of(player.index)
        assert [c.color for c in player.colors] == [c.name.lower() for c in colors]
        assert player.score == game.player_score(player.index)
        for view, color in zip(player.colors, colors, strict=True):
            assert [p.name for p in view.remaining] == board.remaining_pieces(color)
            assert view.squares_left == sum(p.size for p in view.remaining)
            assert view.score == board.score(color)

    if num_players == 3:
        assert snapshot.shared is not None and snapshot.shared.color == "green"
        assert [p.name for p in snapshot.shared.remaining] == board.remaining_pieces(Color.GREEN)
    else:
        assert snapshot.shared is None


def test_last_move_and_to_move():
    match = mid_game_match(4, turns=6)
    snapshot = match.snapshot("thinking")
    last = match.game.turns[-1].move
    assert {r * 20 + c for r, c in snapshot.last_move} == set(last.cells)
    assert snapshot.to_move.color == match.game.current_color.name.lower()
    assert snapshot.to_move.player_kind == "bot"
