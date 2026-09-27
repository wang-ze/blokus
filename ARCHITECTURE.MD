# Architecture

The code is split into two Python packages in one [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/), with one lock file.

- `backend/src/blokus` is the engine, the players, and game records and ratings.
  It does not depend on Gradio.
- `frontend/src/blokus_ui` is the Gradio web app.
  It depends on `blokus` and only draws plain data from it: snapshots of a game, and records and ratings of finished games.

The root `pyproject.toml` ties the two together, so `uv sync` installs both.
The layers inside them look like this:

```
pieces.py ─► board.py ─► game.py ─► match.py ─► snapshot.py ─► blokus_ui
                                       ▲             │          ▲
     players/ (heuristic, llm, human) ─┘             ▼          │
                 ▲                              records.py ─► ratings.py, history.py
             providers.py
```

## Engine

`pieces.py` defines the 21 pieces as ASCII drawings and precomputes their 91 distinct rotations and reflections.

`board.py` holds the 20x20 grid and each color's unplayed pieces.
Cells are indexed row-major, and players and LLMs see them as spreadsheet-style names (`A1` top-left, `T20` bottom-right).
A color's *anchors* (corner points) are the empty cells diagonal to its pieces and not edge-adjacent to them.
Move generation aligns every cell of every orientation onto every anchor, so each candidate already has corner contact and only needs its emptiness and same-color edges checked.
This takes about a millisecond per call in pure Python.
`Board.check` validates any move independently and gives a readable reason for any rule it breaks.
A test compares the generator against a brute-force search over every placement that `check` accepts.

`game.py` handles turn order, which player controls which color, and scoring.
A color with no legal move is out for good, because legal moves only shrink as the board fills.
In a 3-player game the shared Green color is moved by each player in turn, and its score counts for nobody.

## Players

Every player implements `Player.choose_move(view) -> Decision`.
A `TurnView` holds a private copy of the board, the legal moves (never empty), which colors are friendly and which are opponents, whether this color's score counts, the standings, and recent turns.
A `Decision` names a `fallback` when someone else chose the move, such as "random fallback" for an LLM or "played by Tactician" for a person who ran out of time.
Each player also has an `identity` for ratings: the bot's name, the LLM's `provider:model_id`, or "Human".

`players/heuristic.py` has one-ply bots that score every legal move:

- **Greedy**: `10 * size + 1.5 * centrality`, and it ignores opponents.
- **Tactician**: piece size, the net corner points it gains, opponent corner points it covers, a penalty for covering its own other color's corner points, and a pull toward the center that fades after the first few pieces.
  It computes corner-point changes locally from the placed cells instead of copying the board.
  When it moves the shared color, it only tries to block opponents.

Tactician's weights were checked with `blokus-sim`.
Over 400 seeded 2-player games it wins about 85% against Greedy, and both bots beat random play every time.
In 3- and 4-player games with Greedy and random players it wins about 70-75%.

`players/llm.py` runs an OpenAI Agents SDK agent each turn, using the tools `list_legal_moves` and `place_piece`.
A custom `tool_use_behavior` ends the run as soon as the engine accepts a move, or once the model has used up its illegal attempts.
A plain-text reply gets one reminder to call a tool.
Any failure falls back to a random legal move, and the `Decision` records that it was a fallback and why.
The model's reasoning from its last turn goes into its next prompt as short-term memory.

`providers.py` maps `provider:model_id` specs to OpenAI-compatible endpoints (`OpenAIChatCompletionsModel` over `AsyncOpenAI`).
On Hugging Face Spaces only the presets are offered, since the owner pays for every model call.

`players/human.py` has `HumanPlayer`, a seat for a person.
`choose_move` waits on a future for up to 15 seconds (plus 1 second for the move to arrive).
The front end calls `submit(turn, piece, cells)`, which checks the move against the board and returns the reason if it is illegal, so the person can try again.
If time runs out, Greedy or Tactician, picked at random, decides the move from the same `TurnView`.

## Match and front-end seam

`match.py` seats the two bots and up to two guests, a person and LLMs (shuffled by default), and runs the game as an async stream of events: `start`, `thinking`, `move`, `out` and `over`.
Each event carries a `GameSnapshot` from `snapshot.py`.

A snapshot is frozen plain data that `to_dict()` can serialize to JSON.
It includes the grid, the last move, who is to move, every player's score, stats and **all remaining pieces** (grouped by color, the shared color separately), the move log, and the winners.
While a person is to move, it also has a `HumanTurn`: the time limit, the remaining pieces, which of them can be played, the corner points, and every legal placement as a `placement_key` such as `"I2:0,1"`.
The front end reads nothing else, so it can be redesigned or replaced without touching the engine.

`blokus_ui/render.py` turns snapshots, records and ratings into HTML and SVG with pure functions.
All colors are CSS custom properties defined once, with dark-mode overrides.
`blokus_ui/app.py` holds only the Gradio layout and event wiring.
The Start handler is an async generator over match events, so game state lives inside each request and concurrent games don't interfere.

The board is a `gr.HTML` component whose value is `{board, tray, token, turn}`, with `blokus_ui/board.js` as its `js_on_load` script.
The script only runs in the browser: it draws a preview of the selected piece, snaps it to a legal spot by looking up placement keys, runs the countdown, and sends the move to the Python function `submit_move` through the component's `server_functions`.
That call does not go through Gradio's queue, and it runs on the same event loop as the game, so it resolves the waiting `HumanPlayer` directly.
Each game with a person gets a random token, so a browser can only move for its own seat.
The engine still checks every move, and the lookup in the browser is only for instant feedback.

## Records, ratings and history

When a game ends, `records.py` turns the final snapshot into a `GameRecord`: when it ended (UTC), each player's kind, identity, colors, score and fallbacks, every color's score, and every move.
`ratings.py` computes Elo ratings by replaying all records, oldest first.
An N-player game counts as a match between every pair of players, each worth K / (N - 1) points with K = 32, and everyone's changes come from their ratings before the game.
Two seats with the same identity (the same model in both LLM seats) are not compared with each other.

`history.py` keeps the records in memory and saves them as JSON Lines under `$BLOKUS_DATA_DIR/games/<YYYY-MM>/<run id>.jsonl`.
Each server process only writes its own file per month, and rewrites it whole after each game.
No file is appended to or shared between processes, which suits a Hugging Face Storage Bucket mounted into a Space: those mounts upload whole files on close and do not support editing files in place.
On startup every file is read, and bad lines are skipped with a warning.

## Container and hosting

The `Dockerfile` builds one image for local use and for a Hugging Face Docker Space.
Its build stage installs the dependencies pinned in `uv.lock` into a virtual environment, without the project's own code.
The runtime stage copies that environment, then `backend/src` and `frontend/src`, and puts both on `PYTHONPATH`.
So the large dependency layer is reused until `uv.lock` changes, and a code change only replaces the small source layers.
(Installing the packages into the environment would change it on every edit, because uv records the source files' timestamps.)
The container runs `python -m blokus_ui` as user 1000, as Spaces require, listens on port 7860, and keeps game history in `/data`.
`docker stop` sends SIGINT, because Python ignores SIGTERM when it runs as process 1.
`.dockerignore` lists only what the image needs, so `.env`, `data/` and the notebooks never enter the build context.

The start scripts in `scripts/` stop and remove the old container, check that the port is free, rebuild the image, and run it.
They mount `data/` at `/data` and `.env` read-only at `/app/.env`, where the app's `.env` lookup (from the working directory up) finds it.
They also point `OLLAMA_BASE_URL` at `host.docker.internal`, so the container can reach an Ollama server on the host.
Some Docker setups, such as Colima, don't report a port that another program already holds, so the scripts check that themselves.

On a Space, the README's front matter (`sdk: docker`, `app_port: 7860`) is the configuration, secrets arrive as environment variables, and a Storage Bucket is mounted at `/data`.
A test checks that the front matter, the `Dockerfile`, `.dockerignore` and the scripts agree.

## Testing

The engine's tests are in `backend/tests`: the pieces, board rules (including the brute-force check), turn order and scoring, heuristic features, the LLM player, the human player, the match event stream, snapshots, records, ratings, history storage, and providers.
The web app's tests are in `frontend/tests`: rendering and the Gradio layer.
`tests/` checks the container setup, and runs the walkthrough notebook `prototype.ipynb` in a fresh kernel.
The notebook runs there offline: with no API keys and no Ollama server, it skips its one cell that calls a real model.
Both packages' tests use `blokus.testing`, which has a scripted player, random positions and sample records.
The LLM player tests use the Agents SDK's `ScriptedModel`, so they make no network calls.
The app tests play whole games as a person by answering each frame through `submit_move`, as the browser does.
`board.js` has no automated tests in this repository.
It was checked by playing full games in headless Chrome, with a mouse and with emulated touch, both with `uv run blokus` and in the container.
The PowerShell scripts were written for Windows PowerShell 5.1 and PowerShell 7, but have not been run on Windows yet.
