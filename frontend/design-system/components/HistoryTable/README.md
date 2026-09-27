# HistoryTable

Finished games, newest first: one column per color with who sat there and their score, and the winner.

From `render_history(records, limit=200)`. Static rendition.

- Wrap in `bk-scroll` so the wide table scrolls inside its own box (Gradio hides page-level sideways overflow).
- Headers: swatch plus color name. Cells: identity, KindBadge, and a `bk-sub` line ("-9 pts", "1 move by stand-ins").
- The shared color reads "Shared" with "counts for nobody". Winners list swatches and colors ("Yellow & Green"), then identity and points; ties add a "tie" sub-line.
- Times are UTC, `YYYY-MM-DD HH:MM UTC`. Beyond 200 games, a `bk-note` says how many are shown.
