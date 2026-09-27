---
title: Blokus Arena
emoji: 🟦
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Play Blokus against heuristic bots and LLM agents
---

# Blokus Arena

Play Blokus in your browser against heuristic bots and LLM agents, or watch them play each other.

**Play it now at [huggingface.co/spaces/wang-ze/blokus-arena](https://huggingface.co/spaces/wang-ze/blokus-arena)**, with nothing to install.

## The game

[Blokus](BLOKUS.MD) is a board game for 2 to 4 players on a 20x20 grid.
Each color has 21 pieces of 1 to 5 squares, and each new piece must touch a piece of its own color at a corner, never along a side.
When nobody can place another piece, every unplaced square costs a point, and the highest score wins.

Every game in Blokus Arena has 2, 3 or 4 players:

- **Two bots always play.**
  **Greedy** plays its biggest piece as close to the center as possible.
  **Tactician** balances piece size, keeping its own corner points open, and covering its opponents' corner points.
- **You can join** and place your pieces on the board, with 15 seconds per move, or stay out and watch as a spectator.
- **LLM players** can take the other seats: up to one when you play, and up to two when you watch.
  The same model can take both LLM seats.

Every finished game goes into a game history and an **ELO leaderboard**, which ranks the bots, each LLM model, and people, who share one "Human" rating.

## Project layout

| Folder | What it holds |
|---|---|
| `backend/` | The `blokus` package: the rules engine, the bots, LLM and human players, and game records, ratings and history. |
| `frontend/` | The `blokus_ui` package (the Gradio web app) and its design system. |
| `scripts/` | Start and stop the Docker container on a Mac or a Windows PC. |
| `tests/` | Checks that the Dockerfile, the scripts and the Space settings agree, and that the walkthrough notebook runs. |

The `Dockerfile` at the root builds one image with both packages.
See [ARCHITECTURE.MD](ARCHITECTURE.MD) for how the code is organized.

New to the code? [prototype.ipynb](prototype.ipynb) walks through how the game is built: the rules engine, the bots, the LLM players, and a human player, ending with a game you can play in the notebook.
Open it with the project's `.venv` as the kernel, for example in VS Code.

## API keys

Put API keys for the providers you want in `.env` at the repository root, which is git-ignored:

```sh
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
```

| Provider | Key | Example model |
|---|---|---|
| `gemini` | `GEMINI_API_KEY` | `gemini:gemini-3.1-flash-lite` |
| `openrouter` | `OPENROUTER_API_KEY` | `openrouter:nvidia/nemotron-3.5-lightning:free` |
| `anthropic` | `ANTHROPIC_API_KEY` | `anthropic:claude-sonnet-5` |
| `openai` | `OPENAI_API_KEY` | `openai:gpt-5-mini` |
| `deepseek`, `groq`, `grok` | `DEEPSEEK_API_KEY`, `GROQ_API_KEY`, `GROK_API_KEY` | any model id |
| `ollama` | none (a server on port 11434, or set `OLLAMA_BASE_URL`) | `ollama:llama3.2` |

## Run with Docker

You need Docker: [Docker Desktop](https://www.docker.com/products/docker-desktop/), or [Colima](https://github.com/abiosoft/colima) on a Mac.

| | Start | Stop |
|---|---|---|
| Mac | `scripts/start_mac.sh` | `scripts/stop_mac.sh` |
| Windows | `powershell -ExecutionPolicy Bypass -File scripts\start_pc.ps1` | `powershell -ExecutionPolicy Bypass -File scripts\stop_pc.ps1` |

The start script stops the container if it is running, rebuilds the image, starts a new container, and waits until the app answers at http://127.0.0.1:7870.
Set `BLOKUS_PORT` to use another port.
The default leaves Gradio's usual port, 7860, free for other Gradio apps and for `uv run blokus`.

The container reads `.env` from the repository root (mounted read-only, never copied into the image).
It keeps the game history in the repository's `data/` folder, so games played with Docker and with `uv run blokus` share one leaderboard.
LLM players can use an Ollama server running on the same computer.
Follow the app's log with `docker logs --follow blokus-arena`.

After a code change, a rebuild takes a few seconds, because the dependencies sit in an image layer of their own that is rebuilt only when `uv.lock` changes.

## Run without Docker

You need Python 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run blokus
```

The app opens at http://127.0.0.1:7860 (set `GRADIO_SERVER_PORT` to change the port).

## Using the app

Choose whether you want to play and how many LLM players join, then press **Start game**.
The model dropdown lists presets whose API key is set, and you can type any other `provider:model_id` (except on a Hugging Face Space; see [Host on Hugging Face Spaces](#host-on-hugging-face-spaces)).
Seats are shuffled by default, because the first seat plays Blue and moves first.
Leave the seed blank for a random game, or enter a number to replay the same seats and bot moves.

## Playing yourself

When it is your turn, a tray above the board shows your remaining pieces and a 15-second clock.
The biggest piece you can play is picked for you, so you can often place it right away.

- Click a piece to pick it.
- Rotate it with **R**, a right-click on the board, or the button, and flip it with **F** or the button.
- Move the pointer over the board to see where the piece would go, and click to place it.
  Your corner points are marked with dots, and a legal placement snaps into place near the pointer.
- On a touch screen, tap the board to see where the piece goes, then tap the piece to place it.

If you don't place a piece within 15 seconds, Greedy or Tactician (chosen at random each time) moves for you.
Those moves are tagged in the move log, counted on your card, and noted in the game history.
In a 2-player game you control two colors, and in a 3-player game you also take turns moving the shared Green.

## Leaderboard and history

The **Leaderboard** tab ranks players by ELO rating, and below the ratings it lists finished games, newest first: when each ended (in UTC), who played each color, the scores, and the winner.
Stopped games are not recorded.

A game counts as a match between every pair of players, won by the higher score (equal scores are a draw).
Each pairing moves ratings by up to 32 / (players - 1) points, so a whole game is worth about one head-to-head match.
Everyone starts at 1500.
Bots are rated by name, LLMs by their `provider:model_id`, and all people share one **Human** rating.
When the same model fills both LLM seats, its two seats are not compared with each other.
Ratings are recomputed from the whole history, so the history is the only thing stored.

Games are saved as JSON Lines under `data/games/` (git-ignored), with Docker or without.
Without Docker, set `BLOKUS_DATA_DIR` to keep them somewhere else.

## How LLM players work

Each turn, the LLM gets the board as a text grid with its corner points marked, its remaining pieces with how many legal placements each has, the standings, and the recent moves.
It has two tools: `list_legal_moves` to look up exact placements for a piece, and `place_piece` to submit a move.
The engine checks every submission and explains why an illegal move is illegal, so the model can correct itself.
After 3 illegal attempts, an API error, or a 120 second timeout, the engine plays a random legal move for it instead.
Those moves are tagged "random fallback" in the move log and counted on the player's card.
Free API tiers often hit rate limits partway through a game, and those turns show up as fallbacks with the provider's error message.

## Host on Hugging Face Spaces

This project uses a Docker Space, built from the same [Dockerfile](Dockerfile) as the local container scripts.
The README metadata above selects the Docker SDK and sets the Space port to `7860`.
Docker Spaces require a paid Hugging Face plan.

The Space's own disk is temporary, so attach a [Storage Bucket](https://huggingface.co/docs/hub/storage-buckets) at `/data` to persist game history across restarts.
The bucket can be private; check [current storage limits](https://huggingface.co/docs/hub/storage-limits) for the included quota and any applicable charges.

1. Log in with a Hugging Face token that has write access:

   ```sh
   uv run hf auth login
   ```

2. Replace `USER` with your Hugging Face username and create a private bucket:

   ```sh
   uv run hf buckets create USER/blokus-arena-data --private
   ```

3. Create a Docker Space:

   ```sh
   uv run hf repos create USER/blokus-arena --repo-type space --sdk docker
   ```

   Add `--private` to keep the Space private.

4. Attach the bucket as a read-write volume:

   ```sh
   uv run hf spaces volumes set USER/blokus-arena \
     -v hf://buckets/USER/blokus-arena-data:/data
   ```

   Setting volumes replaces the Space's volume list.

5. In **Settings → Variables and secrets**, add provider API keys (for example, `GEMINI_API_KEY` and `OPENROUTER_API_KEY`) as **Secrets**.
   The Dockerfile sets `BLOKUS_DATA_DIR=/data`, so the app saves history to the mounted bucket.
   Never upload `.env` or put API key values in source control.

6. Upload the Docker build files and application sources from the project root:

   ```sh
   uv run hf upload USER/blokus-arena . . --repo-type space \
     --include README.md --include Dockerfile --include .dockerignore --include BLOKUS.MD \
     --include pyproject.toml --include uv.lock \
     --include "backend/pyproject.toml" --include "backend/src/**" \
     --include "frontend/pyproject.toml" --include "frontend/src/**" \
     --exclude ".env" --exclude "data/**" --exclude ".venv/**" \
     --exclude "*.pyc" --exclude "*/__pycache__/*"
   ```

   Repeat the upload after code changes.
   The Dockerfile installs the locked dependency versions and sets the server port, import paths, and data directory.

LLM moves use your provider account and may incur separate provider charges.
So on a Space, visitors can only pick the preset models whose API key is set, and cannot type in other models.
To allow any `provider:model_id`, add the variable `BLOKUS_CUSTOM_MODELS=1` under **Settings → Variables and secrets**.

## Simulate bot games

```sh
uv run blokus-sim --games 40 --players 2
```

This plays bot-only games with rotating seats and prints win rates, average scores and time per move.
With `--players 2` it pits Tactician, Greedy and a random baseline against each other in pairs.
Simulated games are not recorded.

## Develop

```sh
uv run pytest
uv run ruff check && uv run ruff format --check
```

The engine's tests are in `backend/tests`, the web app's in `frontend/tests`, and the container and notebook checks in `tests/`.
`blokus.testing` has the scripted player, random positions and sample records that both test suites use.

A test runs `prototype.ipynb` from top to bottom in a fresh kernel, offline, and checks that it holds no API keys.
After changing the notebook, run all of its cells and save it with the outputs, since those are what readers see on GitHub.
