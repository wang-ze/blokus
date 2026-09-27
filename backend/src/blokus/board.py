"""Board state, cell notation and placement rules.

Cells are indexed row-major: index = row * 20 + col, with row 0 at the top.
Players and LLMs see cells as spreadsheet-style names: columns A-T and rows 1-20, so "A1" is
the top-left cell and "T20" the bottom-right one.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import IntEnum

from blokus.pieces import PIECE_NAMES, PIECES, Shape, normalize, piece_for_shape

BOARD_SIZE = 20
NUM_CELLS = BOARD_SIZE * BOARD_SIZE
EMPTY = -1
COLUMNS = "ABCDEFGHIJKLMNOPQRST"

ALL_PIECES_BONUS = 15
MONOMINO_LAST_BONUS = 5


class Color(IntEnum):
    """Piece colors, in turn order (clockwise from the top-left corner)."""

    BLUE = 0
    YELLOW = 1
    RED = 2
    GREEN = 3

    @property
    def label(self) -> str:
        return self.name.capitalize()

    @property
    def letter(self) -> str:
        return self.name[0]


START_CORNERS: dict[Color, int] = {
    Color.BLUE: 0,
    Color.YELLOW: BOARD_SIZE - 1,
    Color.RED: NUM_CELLS - 1,
    Color.GREEN: NUM_CELLS - BOARD_SIZE,
}


def cell_name(index: int) -> str:
    row, col = divmod(index, BOARD_SIZE)
    return f"{COLUMNS[col]}{row + 1}"


def parse_cell(text: str) -> int:
    """Parse a cell name like "K10" into an index. Raises ValueError if it is not on the board."""
    name = text.strip().upper()
    col = COLUMNS.find(name[:1]) if name else -1
    row_text = name[1:]
    if col < 0 or not row_text.isdigit() or not 1 <= int(row_text) <= BOARD_SIZE:
        raise ValueError(
            f"{text!r} is not a board cell; columns are A-T and rows are 1-{BOARD_SIZE} (e.g. K10)."
        )
    return (int(row_text) - 1) * BOARD_SIZE + col


def _neighbors(index: int, deltas: tuple[tuple[int, int], ...]) -> tuple[int, ...]:
    row, col = divmod(index, BOARD_SIZE)
    return tuple(
        (row + dr) * BOARD_SIZE + col + dc
        for dr, dc in deltas
        if 0 <= row + dr < BOARD_SIZE and 0 <= col + dc < BOARD_SIZE
    )


ORTHOGONAL: tuple[tuple[int, ...], ...] = tuple(
    _neighbors(i, ((-1, 0), (1, 0), (0, -1), (0, 1))) for i in range(NUM_CELLS)
)
DIAGONAL: tuple[tuple[int, ...], ...] = tuple(
    _neighbors(i, ((-1, -1), (-1, 1), (1, -1), (1, 1))) for i in range(NUM_CELLS)
)

# Per piece: each orientation with its height and width, for fast bounds checks.
_ORIENTATIONS: dict[str, tuple[tuple[Shape, int, int], ...]] = {
    name: tuple(
        (shape, max(r for r, _ in shape) + 1, max(c for _, c in shape) + 1)
        for shape in piece.orientations
    )
    for name, piece in PIECES.items()
}


class IllegalMove(ValueError):
    """A move that breaks the placement rules. The message explains why, for players and LLMs."""


@dataclass(frozen=True, slots=True)
class Move:
    color: Color
    piece: str
    cells: frozenset[int]

    @property
    def cell_names(self) -> list[str]:
        return [cell_name(i) for i in sorted(self.cells)]

    def __str__(self) -> str:
        return f"{self.piece} at {' '.join(self.cell_names)}"


class Board:
    """The 20x20 board plus each color's unplayed pieces."""

    __slots__ = ("_occupied", "grid", "last_piece", "remaining")

    def __init__(self) -> None:
        self.grid: list[int] = [EMPTY] * NUM_CELLS
        self.remaining: dict[Color, set[str]] = {color: set(PIECE_NAMES) for color in Color}
        self.last_piece: dict[Color, str | None] = dict.fromkeys(Color)
        self._occupied: dict[Color, list[int]] = {color: [] for color in Color}

    def copy(self) -> Board:
        new = Board.__new__(Board)
        new.grid = self.grid.copy()
        new.remaining = {color: set(names) for color, names in self.remaining.items()}
        new.last_piece = dict(self.last_piece)
        new._occupied = {color: list(cells) for color, cells in self._occupied.items()}
        return new

    # Queries

    def occupied(self, color: Color) -> tuple[int, ...]:
        return tuple(self._occupied[color])

    def has_started(self, color: Color) -> bool:
        return bool(self._occupied[color])

    def remaining_pieces(self, color: Color) -> list[str]:
        """Unplayed pieces of a color, in canonical piece order."""
        remaining = self.remaining[color]
        return [name for name in PIECE_NAMES if name in remaining]

    def remaining_squares(self, color: Color) -> int:
        return sum(PIECES[name].size for name in self.remaining[color])

    def score(self, color: Color) -> int:
        """Score of one color: -1 per unplayed square, or the bonuses for playing every piece."""
        if self.remaining[color]:
            return -self.remaining_squares(color)
        bonus = MONOMINO_LAST_BONUS if self.last_piece[color] == "I1" else 0
        return ALL_PIECES_BONUS + bonus

    def anchors(self, color: Color) -> set[int]:
        """Empty cells a new piece of this color could cover to make legal corner contact.

        Before a color's first move this is just its starting corner.
        """
        grid = self.grid
        if not self._occupied[color]:
            corner = START_CORNERS[color]
            return {corner} if grid[corner] == EMPTY else set()
        return {
            j
            for i in self._occupied[color]
            for j in DIAGONAL[i]
            if grid[j] == EMPTY and all(grid[k] != color for k in ORTHOGONAL[j])
        }

    def legal_moves(self, color: Color, piece: str | None = None) -> list[Move]:
        """Every legal placement for a color (optionally one piece), in a deterministic order."""
        seen: set[frozenset[int]] = set()
        moves: list[Move] = []
        for name, cells in self._placements(color, piece):
            if cells not in seen:
                seen.add(cells)
                moves.append(Move(color, name, cells))
        return moves

    def has_legal_move(self, color: Color) -> bool:
        return next(self._placements(color), None) is not None

    def _placements(
        self, color: Color, piece: str | None = None
    ) -> Iterator[tuple[str, frozenset[int]]]:
        """Yield legal placements, possibly repeated, by aligning each orientation's cells onto
        each anchor. Any placement built this way covers an anchor, so only emptiness and
        same-color edge contact need checking."""
        anchors = sorted(self.anchors(color))
        if not anchors:
            return
        if piece is None:
            names = self.remaining_pieces(color)
        elif piece in self.remaining[color]:
            names = [piece]
        else:
            return
        blocked = self._blocked(color)
        for name in names:
            for shape, height, width in _ORIENTATIONS[name]:
                for anchor in anchors:
                    anchor_row, anchor_col = divmod(anchor, BOARD_SIZE)
                    for pr, pc in shape:
                        top, left = anchor_row - pr, anchor_col - pc
                        if top < 0 or left < 0:
                            continue
                        if top + height > BOARD_SIZE or left + width > BOARD_SIZE:
                            continue
                        base = top * BOARD_SIZE + left
                        cells = [base + r * BOARD_SIZE + c for r, c in shape]
                        if not any(blocked[i] for i in cells):
                            yield name, frozenset(cells)

    def _blocked(self, color: Color) -> bytearray:
        """1 for cells this color may not cover: occupied, or edge-adjacent to its own pieces."""
        blocked = bytearray(cell != EMPTY for cell in self.grid)
        for i in self._occupied[color]:
            for j in ORTHOGONAL[i]:
                blocked[j] = 1
        return blocked

    # Validation and mutation

    def validate(self, color: Color, piece: str, cells: Iterable[str]) -> Move:
        """Build a move from a piece name and cell names, raising IllegalMove if it is not legal."""
        name = piece.strip().upper()
        indices: list[int] = []
        for text in cells:
            try:
                index = parse_cell(text)
            except ValueError as error:
                raise IllegalMove(str(error)) from None
            if index in indices:
                raise IllegalMove(f"Cell {cell_name(index)} is listed more than once.")
            indices.append(index)
        move = Move(color, name, frozenset(indices))
        self.check(move)
        return move

    def check(self, move: Move) -> None:
        """Raise IllegalMove unless the move is legal for its color on this board."""
        color, name, cells = move.color, move.piece, move.cells
        piece = PIECES.get(name)
        if piece is None:
            raise IllegalMove(f"Unknown piece {name!r}. Piece names are: {', '.join(PIECE_NAMES)}.")
        if name not in self.remaining[color]:
            remaining = ", ".join(self.remaining_pieces(color)) or "none"
            raise IllegalMove(
                f"{color.label} has already played {name}. Remaining pieces: {remaining}."
            )
        if len(cells) != piece.size:
            raise IllegalMove(f"{name} has {piece.size} squares but {len(cells)} cells were given.")
        coords = [divmod(i, BOARD_SIZE) for i in cells]
        if normalize(coords) not in piece.orientations:
            actual = piece_for_shape(coords)
            hint = f" (that shape is {actual})" if actual else " (they are not one connected piece)"
            raise IllegalMove(
                f"Cells {' '.join(move.cell_names)} do not form {name} in any rotation or "
                f"reflection{hint}."
            )
        ordered = sorted(cells)
        for i in ordered:
            if self.grid[i] != EMPTY:
                owner = Color(self.grid[i]).label
                raise IllegalMove(f"{cell_name(i)} is already occupied by {owner}.")
        for i in ordered:
            for j in ORTHOGONAL[i]:
                if self.grid[j] == color:
                    raise IllegalMove(
                        f"{cell_name(i)} would share an edge with your own {color.label} piece at "
                        f"{cell_name(j)}; pieces of the same color may only touch at corners."
                    )
        if not self.has_started(color):
            corner = START_CORNERS[color]
            if corner not in cells:
                raise IllegalMove(
                    f"{color.label}'s first piece must cover its starting corner "
                    f"{cell_name(corner)}."
                )
        elif not cells & self.anchors(color):
            corners = " ".join(cell_name(i) for i in sorted(self.anchors(color)))
            raise IllegalMove(
                f"No cell touches one of your {color.label} pieces corner-to-corner. "
                f"Your available corner points are: {corners}."
            )

    def apply(self, move: Move) -> None:
        """Place a piece. Raises IllegalMove (leaving the board unchanged) if it is not legal."""
        self.check(move)
        for i in move.cells:
            self.grid[i] = move.color.value
        self.remaining[move.color].remove(move.piece)
        self.last_piece[move.color] = move.piece
        self._occupied[move.color].extend(sorted(move.cells))
