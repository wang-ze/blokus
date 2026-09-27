import pytest

from blokus.board import Color, IllegalMove
from blokus.game import SHARED_COLOR, TURN_ORDER, Game
from blokus.pieces import TOTAL_SQUARES
from blokus.testing import random_game

BLUE, YELLOW, RED, GREEN = Color


def test_player_count_must_be_2_to_4():
    for bad in (1, 5):
        with pytest.raises(ValueError, match="2, 3 or 4 players"):
            Game(bad)


def test_two_players_each_control_two_opposite_colors():
    game = Game(2)
    assert game.colors_of(0) == (BLUE, RED)
    assert game.colors_of(1) == (YELLOW, GREEN)
    assert game.perspective(BLUE) == ((RED,), (YELLOW, GREEN), True)


def test_three_players_share_green():
    game = Game(3)
    assert [game.colors_of(p) for p in range(3)] == [(BLUE,), (YELLOW,), (RED,)]
    assert game.owner(SHARED_COLOR) is None
    # Whoever moves the shared color treats their own color as friendly.
    assert game.perspective(GREEN) == ((BLUE,), (YELLOW, RED), False)


def test_four_players_one_color_each():
    game = Game(4)
    assert [game.colors_of(p) for p in range(4)] == [(c,) for c in TURN_ORDER]
    assert game.perspective(RED) == ((), (BLUE, YELLOW, GREEN), True)


def test_shared_color_rotates_between_the_three_players():
    game = random_game(3, seed=5)
    green_movers = [t.player for t in game.turns if t.color == GREEN and t.move is not None]
    assert len(green_movers) > 3
    assert green_movers == [i % 3 for i in range(len(green_movers))]


@pytest.mark.parametrize("num_players", [2, 3, 4])
def test_a_full_game_follows_turn_order_and_retires_each_color_once(num_players):
    game = random_game(num_players, seed=num_players)
    assert game.is_over
    assert game.current_color is None
    retired = [t.color for t in game.turns if t.move is None]
    assert sorted(retired) == list(Color)
    assert [t.number for t in game.turns] == list(range(1, len(game.turns) + 1))
    # Colors take turns in order, skipping colors that are out.
    out: set[Color] = set()
    expected = TURN_ORDER[0]
    for turn in game.turns:
        assert turn.color == expected
        if turn.move is None:
            out.add(turn.color)
        if len(out) == len(TURN_ORDER):
            break
        expected = next(
            c for step in range(1, 5) if (c := TURN_ORDER[(turn.color + step) % 4]) not in out
        )
    # No color moves after it is out.
    for color in Color:
        out_turn = next(t.number for t in game.turns if t.color == color and t.move is None)
        assert all(t.move is None or t.number < out_turn for t in game.turns if t.color == color)


def test_moves_must_match_the_color_to_play():
    game = Game(4)
    yellow_move = game.board.legal_moves(YELLOW)[0]
    with pytest.raises(IllegalMove, match="It is Blue's turn"):
        game.play(yellow_move)


def test_cannot_retire_a_color_that_can_move():
    with pytest.raises(IllegalMove, match="Blue still has a legal move"):
        Game(4).retire_current()


def test_nothing_can_happen_after_the_game_is_over():
    game = random_game(2, seed=9)
    with pytest.raises(IllegalMove, match="The game is over"):
        game.retire_current()


def test_player_scores_add_owned_colors_only():
    game = Game(3)
    assert game.scores() == [-TOTAL_SQUARES] * 3
    game.board.remaining[GREEN].clear()  # the shared color's score counts for nobody
    assert game.scores() == [-TOTAL_SQUARES] * 3

    game = Game(2)
    game.board.remaining[RED].clear()
    game.board.last_piece[RED] = "I1"
    assert game.scores() == [20 - TOTAL_SQUARES, -2 * TOTAL_SQUARES]


def test_winners_include_every_tied_player():
    game = Game(4)
    assert game.winners() == [0, 1, 2, 3]
    game.board.remaining[YELLOW].discard("X5")
    assert game.winners() == [1]
