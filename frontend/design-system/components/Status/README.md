# Status

The one-line game status above the board: who is to move, whether it is your move, or the result.

From `render_status(snapshot)` in `frontend/src/blokus_ui/render.py`. Static rendition; the app renders it in Python.

- Markup: `<div class="bk-status">` with text; add `bk-over` when the game is finished (bk-accent border, weight 600).
- Content supplied: turn number (1-based), a `bk-swatch` plus the color's name, the player and its state ("is thinking…", "to move"), or "**Your move**: you have N seconds."
- Always write the color's name next to its swatch.
- Finished: "Game over after N turns · Winner: Name (score)", or "Tie: A (s) and B (s)".
