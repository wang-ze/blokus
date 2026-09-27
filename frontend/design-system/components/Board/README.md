# Board

The 20×20 Blokus board as one SVG: coordinates, cells, last-move dots, empty start corners and, on your move, corner points.

From `render_board(snapshot)`; the interactive layer is `frontend/src/blokus_ui/board.js`. Static rendition.

- Geometry: `board-cell` 24 units, `board-margin` 20 units, cells 22×22 with `radius-3`, background `bk-board` with `radius-4`; scales to `board-max-width` 620px.
- Cells take `bk-empty` or `bk-<color>`. Columns A–T, rows 1–20 in `board-label` / `bk-label`.
- Last move: a 3.5-unit `bk-mark` dot at `opacity-last` on each square.
- An empty start corner (Blue A1, Yellow T1, Red T20, Green A20) gets an outlined inner square stroked in its color.
- Your move: add `bk-interactive`; corner points are 3-unit dots in your color at `opacity-anchor`. A placement preview is a `g.bk-preview`: `bk-ok` fills your color at `opacity-preview`; `bk-bad` draws dashed `bk-danger-fg` outlines. The engine re-checks every move.
- The SVG carries `role="img"` and `aria-label="Blokus board"`; the move log is the text record of what happened.
