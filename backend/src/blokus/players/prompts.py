"""Prompts and text representations for LLM players."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from blokus.board import BOARD_SIZE, COLUMNS, START_CORNERS, Board, Color, cell_name
from blokus.pieces import PIECES, drawing
from blokus.players import TurnView

NUDGE = (
    "You must act by calling a tool. Call place_piece now with your chosen piece and the exact "
    "cells it covers."
)


def board_text(board: Board, marks: Iterable[int] = (), mark: str = "*") -> str:
    """The board as a labeled grid: B/Y/R/G for pieces, "." for empty cells, `mark` on `marks`."""
    marked = set(marks)
    letters = {color.value: color.letter for color in Color}
    lines = ["    " + " ".join(COLUMNS)]
    for row in range(BOARD_SIZE):
        cells = (
            mark if i in marked else letters.get(board.grid[i], ".")
            for i in range(row * BOARD_SIZE, (row + 1) * BOARD_SIZE)
        )
        lines.append(f"{row + 1:>3} " + " ".join(cells))
    return "\n".join(lines)


def _piece_catalog() -> str:
    return "\n\n".join(
        f"{piece.name} ({piece.size} square{'s' * (piece.size > 1)}):\n{drawing(piece.shape)}"
        for piece in PIECES.values()
    )


def _starts() -> str:
    return ", ".join(
        f"{color.label} ({color.letter}) at {cell_name(START_CORNERS[color])}" for color in Color
    )


def system_prompt(max_invalid_attempts: int) -> str:
    return f"""You are an expert player of the board game Blokus, playing on a 20x20 board.

# Board and coordinates
- Columns are letters A-T from left to right; rows are numbers 1-20 from top to bottom.
  A1 is the top-left cell and T20 the bottom-right cell. Cells are written column then row,
  e.g. K10.
- Starting corners: {_starts()}. Turn order is Blue, Yellow, Red, Green.

# Placement rules
1. A color's first piece must cover that color's starting corner.
2. Every later piece must touch at least one piece of the same color corner-to-corner.
3. A piece must never share an edge with a piece of the same color. Touching other colors along
   edges is fine.
4. Pieces cannot overlap other pieces or go off the board. Pieces may be rotated and flipped.
5. A color with no legal placement is out for the rest of the game.

# Scoring
Each unplayed square is -1 point. Playing all 21 pieces scores +15, plus 5 more if the last piece
was the single square I1. The player with the highest total wins.

# Pieces
Each color has these 21 pieces ("X" is a square). Any rotation or reflection may be used.

{_piece_catalog()}

# Your turn
- The board marks your color's corner points with "*". These are the empty cells where a new
  piece would touch your pieces corner-to-corner without sharing an edge with them. Every move
  must cover at least one corner point.
- Call list_legal_moves(piece, corner_point) to see exact legal placements for a piece.
- End your turn by calling place_piece(reasoning, piece, cells) with the exact cells the piece
  will cover. If the move is illegal you get the reason and can try again; after
  {max_invalid_attempts} illegal attempts your turn is played for you at random.
- Always act by calling tools, never with a plain text answer.

# Strategy
Play big pieces early, spread toward open space and the center, keep plenty of corner points
for yourself, and cover or cut off your opponents' corner points."""


def _labels(colors: Iterable[Color]) -> str:
    return ", ".join(color.label for color in colors) or "none"


def turn_prompt(view: TurnView, player_name: str, notes: str = "") -> str:
    """The situation for one turn, written from the moving player's point of view."""
    board, color = view.board, view.color
    anchors = sorted(board.anchors(color))
    placements = Counter(move.piece for move in view.legal_moves)
    pieces = ", ".join(
        f"{name} ({placements.get(name, 0)})" for name in board.remaining_pieces(color)
    )

    lines = [f"Turn {view.turn}. You are {player_name}, moving {color.label} ({color.letter})."]
    if not view.scores_count:
        lines.append(
            f"{color.label} is the shared color: its score counts for nobody and the players take "
            f"turns moving it. Use this move to block your opponents' corner points without "
            f"hurting your own color ({_labels(view.friendly)})."
        )
    elif view.friendly:
        lines.append(f"You also control {_labels(view.friendly)}; avoid blocking your own colors.")
    lines += [
        f"Opponent colors: {_labels(view.opponents)}.",
        "",
        f'Board ("*" marks your {color.label} corner points):',
        board_text(board, anchors),
        "",
        f"Your corner points: {' '.join(cell_name(i) for i in anchors)}",
        f"Your remaining pieces, with how many legal placements each has now: {pieces}",
        "",
        "Standings:",
    ]
    for index, standing in enumerate(view.standings):
        you = " (you)" if index == view.player else ""
        lines.append(
            f"- {standing.name}{you}: {_labels(standing.colors)}; score {standing.score}; "
            f"{standing.squares_left} squares left"
        )
    if view.recent_turns:
        lines += ["", "Recent turns:"]
        for turn in view.recent_turns:
            who = view.standings[turn.player].name
            if turn.move is None:
                lines.append(f"- Turn {turn.number}: {turn.color.label} had no legal move (out)")
            else:
                lines.append(f"- Turn {turn.number}: {turn.color.label} ({who}) played {turn.move}")
    if notes:
        lines += ["", f"Your notes from your previous turn: {notes}"]
    lines += ["", "Call list_legal_moves if you want exact placements, then call place_piece."]
    return "\n".join(lines)
