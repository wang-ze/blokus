# Blokus Arena

The interface for playing Blokus in a browser against heuristic bots and LLM agents, or watching them play each other. The app is a Gradio app using the Soft theme. Every game-specific surface (board, tray, player cards, log, tables) is plain HTML/SVG styled by the `bk-` classes in `components/bundle.css`.

## Principles

- The final product should include the comprehensive information about the UI and UX.
- The platform must look great in dark mode and light mode.
- Do not have classic LLM tells like gradients, overuse of purple, and the line on the left of panels.
- Show every player's full state. Cards list all remaining pieces, not just a count, and the log keeps every turn.
- Nothing moves under the pointer. `bk-msg` has a fixed height, so a message never shifts the board between two taps.

## Voice and content

- Use sentence case and plain words. Say "Your move", "Start game", "Pick a piece, then click or tap the board to place it."
- Address the person as "you". Players are named by identity: "Tactician", "Greedy", an LLM's model name, or "You" / "Human".
- Name squares in board notation: columns A–T, rows 1–20 ("J8", "T20"). Name pieces I1…X5 as in `pieces.py`.
- Join facts with " · ": "Turn 13 · Red · Tactician is thinking…", "47 squares left · 9 moves · avg 0.2s per move".
- Pluralize properly ("1 move", "2 illegal tries"). Use thousands separators for counts and one decimal for seconds.
- Times are UTC and say so. Scores can be negative: show them as they are.
- Explain rule errors in full: "J9 would share an edge with your own Blue piece at J8."
- The only emoji is 🏆 after a winner's name. Add no other emoji or decorative icons.

## Using tokens

Use regular Blokus game colors: Blue, Yellow, Red and Green.

- `bk-blue`, `bk-yellow`, `bk-red`, `bk-green` mean one thing each: that player's color. They are identical in both themes. Never use them for UI state such as success, warning or links. Turn order is Blue → Yellow → Red → Green; start corners are A1, T1, T20, A20.
- Grounds: page `gr-page`, cards and the status bar `bk-card`, board `bk-board` with empty cells `bk-empty`.
- Text: primary `gr-text`, secondary `bk-muted`, board coordinates `bk-label`.
- `bk-accent` marks state only: the player to move, the finished-game status, the tray, the selected piece. Don't use it for decoration.
- `bk-danger-fg` / `bk-danger-bg` are for errors, the fallback tag, the clock under 5 seconds and illegal placement previews.
- `bk-border` is a 1px hairline for cards, row dividers and the time-bar track. Separate panels with a full border and a radius, never a colored left edge.
- Type: set everything in `sans` (Montserrat, from the Gradio Soft theme). Numbers that change use tabular figures (`score`, `clock`, table numbers). The body is 14px; the `bk-` sizes are rem steps from 1.2rem (`clock`) down to 0.7rem (`tag`).
- Radii grow with size: `radius-piece` / `radius-3` for squares, `radius-6` for buttons, `radius-8` for the status bar, `radius-10` for cards and the tray, `radius-pill` for badges and tags.
- Spacing is the 1–12px set in `spacing`. Cards pad `space-10` × `space-12`, and card lists gap `space-10`.
- Depth: no shadows except `shadow-turn`, the 1px ring that doubles the accent border of the player who is thinking. Dim with the `opacity` tokens rather than new grays.

## Using components

- These components come from Python render functions in `frontend/src/blokus_ui/render.py`, not a JS library. There is no bundle script. Previews are static renditions of that markup styled by `bundle.css`. The board's interactivity lives in `frontend/src/blokus_ui/board.js`.
- The board SVG uses its own units (`board-cell`, `board-margin`) and scales to `board-max-width`. Don't restyle cells with CSS sizes; change the constants.
- Pair every Swatch with the color's name.
- Wrap wide tables in `bk-scroll`.
- Only the Tray is interactive. Everywhere else, pieces are pictures, not buttons.

## Accessibility

- Legible pairs, in both themes: `gr-text` on `gr-page` and `bk-card`; `bk-muted` on `bk-card` (4.8:1 light, 6.9:1 dark); `bk-danger-fg` on `bk-danger-bg` (5.8:1, 7.9:1); `bk-accent` borders on `bk-card` (5.2:1, 7.0:1).
- Known gaps, kept exact from the code: `bk-label` on `bk-board` is 3.2:1 in Light (10px text); `bk-yellow` is 1.7:1 on `bk-empty` in Light; the white `bk-mark` dot on Yellow is 1.9:1; `bk-border` hairlines are decorative (about 1.3:1).
- Color is never alone. Red and Green differ by hue only (1.3:1 in lightness), so every swatch sits next to the color's name, every log line names the player and the piece, and start corners are fixed positions.
- The app defines no custom focus ring. Keyboard focus is the browser's and Gradio's default, and R / F rotate and flip in the tray.
- The board is `role="img"` with a label. The move log and the status bar carry the same information as text.

## Not synced

- Gradio Soft chrome beyond the page ground and body text (inputs, tabs, and the indigo `primary` Start button) is not captured as tokens.
- Components use the read-only route: static renditions of `render.py` markup, with no JS bundle. The board's hover, rotate and flip behavior (`board.js`) is not live here.
- The font files are the Fontsource latin builds of Montserrat 400/700 and IBM Plex Mono 400, the same faces Gradio ships. Gradio's own copies were too deeply nested in the checkout to copy.
- No logos or icon set exist in the repo, so there are no assets.
