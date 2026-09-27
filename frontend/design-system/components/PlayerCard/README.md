# PlayerCard

One card per player: colors, name, kind, score, stats, and every remaining piece grouped by color.

From `render_players(snapshot)`, wrapped in `bk-players` (a column with a 10px gap). Static rendition.

- `bk-player`: `bk-card`, 1px `bk-border`, `radius-10`, padding `space-10` × `space-12`.
- States: `bk-turn` (the player who is thinking) sets the border to `bk-accent` plus `shadow-turn`. `bk-inactive` (no colors left in play, game not over) uses `opacity-inactive`.
- Head: one swatch per color, `player-name`, a KindBadge, and the `score` pushed right. Winners get " 🏆" after the name, the only emoji in the UI.
- `bk-detail` (model or strategy) and `bk-stats` ("47 squares left · 9 moves · avg 0.2s per move", plus illegal tries, random fallbacks and tokens for LLMs, or timeouts for people), joined with " · ".
- Color rows: label (swatch, name, "(out)", squares left) and the remaining pieces, or "all pieces played". A color that is out uses `opacity-out`.
- In 3-player games the shared color gets its own card: "Shared Green", badge "no score".
