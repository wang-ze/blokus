# Tray

The piece picker shown above the board while a person is to move: clock, time bar, playable pieces, rotate/flip and a message line.

From `render_tray(snapshot)` plus `board.js`. Static rendition.

- Container `bk-tray`: `radius-10` with a `bk-accent` border, so it reads as the active area.
- Head: swatch, "**Your move** as Blue", and the `clock` in seconds; under 5 seconds (`LOW_SECONDS`) it takes `bk-low` (`bk-danger-fg`).
- Time bar: `timebar` 4px high, track `bk-border`, fill in the player's color, width = time left.
- Picks: one `bk-pick` button per remaining piece (`pick-cell` 10px). `bk-selected` draws a `bk-accent` border. Disabled pieces have no legal placement (`opacity-disabled`).
- Controls: the `hand` box shows the selected piece in its current orientation, then Rotate (R) and Flip (F).
- `bk-msg` is fixed at two lines so text never moves the board; add `bk-error` for a rejected move.
- If time runs out, Greedy or Tactician moves for the person, and the log tags it "played by …".
