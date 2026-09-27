# MoveLog

Every turn, newest first, in a scrolling list.

From `render_log(snapshot)`. Static rendition.

- `ol.bk-log`, scrolling past `log-max-height` 420px; rows separated by `bk-border`.
- Row: `#turn` in muted tabular numbers, swatch, **player** played **piece**, then the cells and seconds in `detail`.
- If someone else made the move, add a FallbackTag ("random fallback", "played by Tactician").
- LLM reasoning follows in an italic `bk-reason`; an illegal attempt's reason in `bk-error` (`bk-danger-fg`).
- A color with no legal move: "Green has no legal move and is out."
