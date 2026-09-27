import pytest

from blokus.board import (
    ALL_PIECES_BONUS,
    BOARD_SIZE,
    MONOMINO_LAST_BONUS,
    NUM_CELLS,
    START_CORNERS,
    Board,
    Color,
    IllegalMove,
    Move,
    cell_name,
    parse_cell,
)
from blokus.pieces import PIECES, TOTAL_SQUARES
from blokus.testing import random_game

BLUE, YELLOW = Color.BLUE, Color.YELLOW


def move(color: Color, piece: str, *cells: str) -> Move:
    return Move(color, piece, frozenset(parse_cell(c) for c in cells))


def board_with(*moves: Move) -> Board:
    board = Board()
    for m in moves:
        board.apply(m)
    return board


def test_cell_notation_round_trips():
    assert [parse_cell(cell_name(i)) for i in range(NUM_CELLS)] == list(range(NUM_CELLS))
    assert cell_name(0) == "A1"
    assert cell_name(NUM_CELLS - 1) == "T20"
    assert parse_cell(" k10 ") == 9 * BOARD_SIZE + 10


@pytest.mark.parametrize("text", ["U1", "A0", "A21", "", "11", "AA", "A1.5"])
def test_parse_cell_rejects_cells_off_the_board(text):
    with pytest.raises(ValueError, match="not a board cell"):
        parse_cell(text)


def test_start_corners_are_the_four_corners_clockwise():
    assert [cell_name(START_CORNERS[c]) for c in Color] == ["A1", "T1", "T20", "A20"]


def test_first_move_must_cover_the_starting_corner():
    board = Board()
    with pytest.raises(IllegalMove, match="must cover its starting corner A1"):
        board.check(move(BLUE, "I2", "B1", "C1"))
    board.check(move(BLUE, "I2", "A1", "B1"))
    assert board.anchors(BLUE) == {START_CORNERS[BLUE]}


def test_same_color_pieces_may_not_share_an_edge():
    board = board_with(move(BLUE, "I2", "A1", "B1"))
    with pytest.raises(IllegalMove, match="C1 would share an edge with your own Blue piece at B1"):
        board.check(move(BLUE, "I3", "C1", "C2", "C3"))


def test_same_color_corner_contact_is_legal():
    board = board_with(move(BLUE, "I2", "A1", "B1"))
    board.check(move(BLUE, "I3", "C2", "D2", "E2"))


def test_later_moves_need_corner_contact():
    board = board_with(move(BLUE, "I2", "A1", "B1"))
    with pytest.raises(IllegalMove, match=r"Your available corner points are: C2\.$"):
        board.check(move(BLUE, "I3", "E5", "F5", "G5"))


def test_different_colors_may_share_edges():
    board = board_with(
        move(BLUE, "L5", "A1", "B1", "C1", "D1", "D2"),
        move(BLUE, "I5", "E3", "F3", "G3", "H3", "I3"),
        move(YELLOW, "I4", "T1", "S1", "R1", "Q1"),
        move(YELLOW, "I5", "P2", "O2", "N2", "M2", "L2"),
    )
    # Yellow J3 touches Blue I3 along an edge, which is fine for different colors.
    board.check(move(YELLOW, "V3", "K3", "J3", "J4"))


def test_pieces_may_not_overlap():
    board = board_with(
        move(BLUE, "I5", "A1", "B1", "C1", "D1", "E1"),
        move(BLUE, "I4", "F2", "G2", "H2", "I2"),
        move(YELLOW, "I4", "T1", "S1", "R1", "Q1"),
        move(YELLOW, "I5", "P2", "O2", "N2", "M2", "L2"),
    )
    with pytest.raises(IllegalMove, match="I2 is already occupied by Blue"):
        board.check(move(YELLOW, "I2", "I2", "I3"))


def test_cells_must_form_the_named_piece():
    board = Board()
    with pytest.raises(IllegalMove, match=r"do not form L4 .*\(that shape is I4\)"):
        board.check(move(BLUE, "L4", "A1", "B1", "C1", "D1"))
    with pytest.raises(IllegalMove, match="not one connected piece"):
        board.check(move(BLUE, "I2", "A1", "C1"))
    with pytest.raises(IllegalMove, match="I5 has 5 squares but 2 cells were given"):
        board.check(move(BLUE, "I5", "A1", "B1"))


def test_validate_parses_names_and_reports_input_mistakes():
    board = Board()
    assert board.validate(BLUE, " i2 ", ["a1", "B1"]) == move(BLUE, "I2", "A1", "B1")
    with pytest.raises(IllegalMove, match="Unknown piece 'Q9'"):
        board.validate(BLUE, "Q9", ["A1"])
    with pytest.raises(IllegalMove, match="not a board cell"):
        board.validate(BLUE, "I1", ["Z1"])
    with pytest.raises(IllegalMove, match="A1 is listed more than once"):
        board.validate(BLUE, "I2", ["A1", "a1"])
    board.apply(move(BLUE, "I1", "A1"))
    with pytest.raises(IllegalMove, match="Blue has already played I1"):
        board.validate(BLUE, "I1", ["B2"])


def test_apply_rejects_illegal_moves_without_changing_the_board():
    board = Board()
    before = board.copy()
    with pytest.raises(IllegalMove):
        board.apply(move(BLUE, "I2", "B1", "C1"))
    assert board.grid == before.grid
    assert board.remaining == before.remaining


def test_copy_is_independent():
    board = Board()
    copy = board.copy()
    copy.apply(move(BLUE, "I1", "A1"))
    assert board.grid[0] == -1
    assert "I1" in board.remaining[BLUE]
    assert not board.has_started(BLUE)


def test_score_counts_unplayed_squares_and_bonuses():
    board = Board()
    assert board.score(BLUE) == -TOTAL_SQUARES
    board.remaining[BLUE].clear()
    board.last_piece[BLUE] = "X5"
    assert board.score(BLUE) == ALL_PIECES_BONUS
    board.last_piece[BLUE] = "I1"
    assert board.score(BLUE) == ALL_PIECES_BONUS + MONOMINO_LAST_BONUS
    board.remaining[BLUE].add("V3")
    assert board.score(BLUE) == -3


def brute_force_legal(board: Board, color: Color) -> set[frozenset[int]]:
    """Every placement of every remaining piece that `Board.check` accepts."""
    legal = set()
    for name in board.remaining[color]:
        for shape in PIECES[name].orientations:
            height = max(r for r, _ in shape) + 1
            width = max(c for _, c in shape) + 1
            for top in range(BOARD_SIZE - height + 1):
                for left in range(BOARD_SIZE - width + 1):
                    cells = frozenset((top + r) * BOARD_SIZE + left + c for r, c in shape)
                    try:
                        board.check(Move(color, name, cells))
                    except IllegalMove:
                        continue
                    legal.add(cells)
    return legal


@pytest.mark.parametrize(("seed", "turns"), [(0, 0), (1, 10), (2, 30), (3, 55)])
def test_move_generator_matches_a_brute_force_oracle(seed, turns):
    board = random_game(4, seed, turns).board
    for color in Color:
        moves = board.legal_moves(color)
        generated = {m.cells for m in moves}
        assert len(generated) == len(moves), "duplicate placements"
        assert generated == brute_force_legal(board, color)
        assert board.has_legal_move(color) == bool(moves)
        for m in moves:
            assert PIECES[m.piece].size == len(m.cells)


def test_legal_moves_for_one_piece():
    board = Board()
    moves = board.legal_moves(BLUE, "L4")
    # An orientation fits in the corner only if its top-left bounding-box cell is a square.
    assert len(moves) == sum((0, 0) in shape for shape in PIECES["L4"].orientations)
    assert all(m.piece == "L4" and START_CORNERS[BLUE] in m.cells for m in moves)
    board.apply(moves[0])
    assert board.legal_moves(BLUE, "L4") == []
