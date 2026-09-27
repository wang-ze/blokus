"""The 21 Blokus pieces and their orientations.

Shapes are sets of (row, col) offsets normalized so the smallest row and column are 0.
Each piece is listed once in a canonical orientation; `Piece.orientations` holds every
distinct rotation and reflection.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

type Shape = tuple[tuple[int, int], ...]

# Drawn with "X" for a square and "." for a gap. Order is by size, then name, and is used as
# the canonical piece order everywhere (move generation, prompts, rendering).
_DRAWINGS: dict[str, str] = {
    "I1": "X",
    "I2": "XX",
    "I3": "XXX",
    "V3": "XX\nX.",
    "I4": "XXXX",
    "L4": "X..\nXXX",
    "T4": "XXX\n.X.",
    "O4": "XX\nXX",
    "Z4": "XX.\n.XX",
    "I5": "XXXXX",
    "L5": "X...\nXXXX",
    "Y5": ".X..\nXXXX",
    "N5": "XX..\n.XXX",
    "P5": "XX\nXX\nX.",
    "U5": "X.X\nXXX",
    "V5": "X..\nX..\nXXX",
    "W5": "X..\nXX.\n.XX",
    "Z5": "XX.\n.X.\n.XX",
    "T5": "XXX\n.X.\n.X.",
    "F5": ".XX\nXX.\n.X.",
    "X5": ".X.\nXXX\n.X.",
}


def normalize(cells: Iterable[tuple[int, int]]) -> Shape:
    """Translate cells so the minimum row and column are 0, and sort them."""
    cells = list(cells)
    min_r = min(r for r, _ in cells)
    min_c = min(c for _, c in cells)
    return tuple(sorted((r - min_r, c - min_c) for r, c in cells))


def _orientations(shape: Shape) -> tuple[Shape, ...]:
    """All distinct rotations and reflections of a shape, in a deterministic order."""
    seen: dict[Shape, None] = {}
    for reflected in (shape, tuple((r, -c) for r, c in shape)):
        current = reflected
        for _ in range(4):
            seen.setdefault(normalize(current), None)
            current = tuple((c, -r) for r, c in current)
    return tuple(seen)


def _parse(drawing: str) -> Shape:
    return normalize(
        (r, c)
        for r, line in enumerate(drawing.splitlines())
        for c, ch in enumerate(line)
        if ch == "X"
    )


@dataclass(frozen=True, slots=True)
class Piece:
    name: str
    shape: Shape
    orientations: tuple[Shape, ...]

    @property
    def size(self) -> int:
        return len(self.shape)


PIECES: dict[str, Piece] = {
    name: Piece(name, shape, _orientations(shape))
    for name, shape in ((name, _parse(drawing)) for name, drawing in _DRAWINGS.items())
}
PIECE_NAMES: tuple[str, ...] = tuple(PIECES)
TOTAL_SQUARES: int = sum(p.size for p in PIECES.values())

_SHAPE_TO_PIECE: dict[Shape, str] = {
    shape: piece.name for piece in PIECES.values() for shape in piece.orientations
}


def piece_for_shape(cells: Iterable[tuple[int, int]]) -> str | None:
    """Name of the piece that has an orientation matching these cells, if any."""
    return _SHAPE_TO_PIECE.get(normalize(cells))


def drawing(shape: Shape) -> str:
    """ASCII drawing of a shape using "X" and "."."""
    rows = max(r for r, _ in shape) + 1
    cols = max(c for _, c in shape) + 1
    cells = set(shape)
    return "\n".join(
        "".join("X" if (r, c) in cells else "." for c in range(cols)) for r in range(rows)
    )
