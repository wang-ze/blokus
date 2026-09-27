# FallbackTag

A small red-tinted pill in the move log marking a move that the player did not choose itself.

The `.bk-tag` class in `render.py`. Static rendition.

- `tag` size, `bk-danger-fg` on `bk-danger-bg`, `radius-pill`, 4px left margin.
- Text is the fallback reason from the engine: "random fallback" (an LLM ran out of attempts) or "played by Tactician" / "played by Greedy" (a person ran out of time).
