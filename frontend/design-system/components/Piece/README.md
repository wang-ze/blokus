# Piece

One Blokus piece drawn as a small SVG of rounded squares in a player color.

From `render_piece(piece, color, cell=9)`. Static rendition.

- Supply the piece's cells (21 pieces, I1 to X5, listed in `pieces.py`), a color key (`blue`, `yellow`, `red`, `green`) and the cell pitch: `piece-cell` 9px in player cards, `pick-cell` 10px in the tray.
- Each square is `cell-1` wide with `radius-piece` (1.5px), class `bk-<color>`.
- Carries a `<title>` with the piece name.
