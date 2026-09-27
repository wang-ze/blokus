from blokus.board import Board, Color, cell_name
from blokus.match import Match
from blokus.pieces import PIECES, drawing
from blokus.players.prompts import board_text, system_prompt, turn_prompt
from blokus.testing import FirstMovePlayer


def test_board_text_is_a_labeled_grid_with_marks():
    board = Board()
    board.apply(board.validate(Color.BLUE, "I2", ["A1", "B1"]))
    lines = board_text(board, marks=board.anchors(Color.BLUE)).splitlines()
    assert len(lines) == 21
    assert lines[0] == "    A B C D E F G H I J K L M N O P Q R S T"
    assert lines[1] == "  1 B B" + " ." * 18
    assert lines[2] == "  2 . . *" + " ." * 17
    assert lines[20].startswith(" 20 .")


def test_system_prompt_explains_every_piece_and_the_retry_budget():
    prompt = system_prompt(3)
    for piece in PIECES.values():
        assert f"{piece.name} (" in prompt
        assert drawing(piece.shape) in prompt
    assert "after\n  3 illegal attempts" in prompt
    assert "Blue (B) at A1" in prompt


def test_turn_prompt_for_a_two_color_player():
    view = Match([FirstMovePlayer("Alice"), FirstMovePlayer("Bob")]).turn_view()
    prompt = turn_prompt(view, "Alice", notes="Aim for the middle.")
    assert prompt.startswith("Turn 1. You are Alice, moving Blue (B).")
    assert "You also control Red" in prompt
    assert "Opponent colors: Yellow, Green." in prompt
    assert f"Your corner points: {cell_name(0)}" in prompt
    assert "I5 (2)" in prompt
    assert "- Alice (you): Blue, Red; score -178; 178 squares left" in prompt
    assert "Your notes from your previous turn: Aim for the middle." in prompt


def test_turn_prompt_for_the_shared_color():
    match = Match([FirstMovePlayer(name) for name in ("A", "B", "C")])
    game = match.game
    for _ in range(3):  # Blue, Yellow and Red open; Green (shared) is next
        game.play(match.turn_view().legal_moves[0])
    view = match.turn_view()
    assert view.color == Color.GREEN
    prompt = turn_prompt(view, "A")
    assert "Green is the shared color" in prompt
    assert "without hurting your own color (Blue)" in prompt
    assert "- Turn 3: Red (C) played" in prompt
