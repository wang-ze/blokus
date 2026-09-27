# Leaderboard

ELO ratings, best first, as a compact table.

From `render_leaderboard(table)`. Static rendition.

- `table.bk-table.bk-ratings`: at least `min(100%, 24rem)` wide; rank and rating right-aligned in tabular numbers (`bk-num-cell`), rating bold.
- Player cell: identity plus a KindBadge. All people share one "Human" rating; everyone starts at 1500.
- Empty state: `bk-note` "No finished games yet. Ratings appear after the first game."
