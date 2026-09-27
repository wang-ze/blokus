"""Gradio front end: layout and event wiring only. Rendering lives in `render.py`."""

from __future__ import annotations

import asyncio
import random
import secrets
from collections.abc import AsyncIterator
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import gradio as gr

from blokus.history import GameHistory
from blokus.match import MAX_GUESTS, Match, lineup
from blokus.players import Player
from blokus.players.human import TIME_LIMIT_SECONDS, HumanPlayer
from blokus.players.llm import LLMPlayer
from blokus.providers import available_presets, custom_models_allowed
from blokus.records import GameRecord
from blokus.snapshot import GameSnapshot
from blokus_ui.render import (
    CSS,
    render_board,
    render_history,
    render_leaderboard,
    render_log,
    render_players,
    render_status,
    render_stopped,
    render_tray,
)

MAX_CONCURRENT_GAMES = 8
BOARD_JS = Path(__file__).with_name("board.js").read_text(encoding="utf-8")

# People playing right now, by the secret token their browser sends with each move.
_humans: dict[str, HumanPlayer] = {}

type Frame = tuple[Any, ...]
"""Status, board, players, log, leaderboard, history, and the snapshot (kept for Stop).
The leaderboard and history only change when the game ends."""


def board_value(snapshot: GameSnapshot | None, token: str | None = None) -> dict[str, Any]:
    """The interactive board's value: its HTML, plus the move data when a person is to move."""
    waiting = snapshot.human_turn if snapshot else None
    return {
        "board": render_board(snapshot),
        "tray": render_tray(snapshot),
        "token": token if waiting else None,
        "turn": asdict(waiting) if waiting else None,
    }


async def submit_move(data: Any) -> dict[str, Any]:
    """Called from the browser (board.js) with {token, turn, piece, cells}."""
    try:
        human = _humans.get(str(data["token"]))
        if human is None:
            return {"ok": False, "error": "This game is no longer running."}
        cells = data["cells"]
        if not isinstance(cells, list):
            raise TypeError("cells must be a list")
        error = human.submit(int(data["turn"]), str(data["piece"]), [str(c) for c in cells])
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "error": "That move could not be read."}
    return {"ok": error is None, "error": error}


def _frame(
    snapshot: GameSnapshot, token: str | None = None, tables: tuple[str, str] | None = None
) -> Frame:
    leaderboard, history = tables or (gr.skip(), gr.skip())
    return (
        render_status(snapshot),
        board_value(snapshot, token),
        render_players(snapshot),
        render_log(snapshot),
        leaderboard,
        history,
        snapshot,
    )


def stopped(snapshot: GameSnapshot | None) -> tuple[Any, Any]:
    """Status and board after Stop: the position stays, without the piece picker."""
    if snapshot is None or snapshot.over:
        return gr.skip(), gr.skip()
    snapshot = replace(snapshot, human_turn=None)
    return render_stopped(snapshot), board_value(snapshot)


def parse_seed(text: str | float | None) -> int | None:
    """The seed typed in the setup form: blank means a random game."""
    text = str(text if text is not None else "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        raise gr.Error("The seed must be a whole number, or blank for a random game.") from None


def _guests(
    play_yourself: bool,
    num_llms: int,
    specs: list[str | None],
    rng: random.Random,
) -> list[Player]:
    guests: list[Player] = []
    if play_yourself:
        guests.append(HumanPlayer(seed=rng.getrandbits(32)))
    presets = available_presets()
    for i, spec in enumerate(specs[: int(num_llms)]):
        spec = (spec or "").strip()
        if spec not in presets and not custom_models_allowed():
            raise gr.Error(f"Pick LLM {i + 1} from the list of models.")
        try:
            guests.append(LLMPlayer.from_spec(f"LLM {i + 1}", spec, seed=rng.getrandbits(32)))
        except ValueError as error:
            raise gr.Error(str(error)) from None
    if len(guests) > MAX_GUESTS:
        raise gr.Error(f"At most {MAX_GUESTS} players can join the two bots.")
    return guests


async def run_game(
    history: GameHistory,
    play_yourself: bool,
    num_llms: int,
    model_1: str | None,
    model_2: str | None,
    shuffle: bool,
    seed: str | None,
    delay: float,
) -> AsyncIterator[Frame]:
    """Play one game, yielding a re-rendered frame after every event, then record it."""
    rng = random.Random(parse_seed(seed))
    guests = _guests(play_yourself, num_llms, [model_1, model_2], rng)
    players = lineup(guests, shuffle=shuffle, seed=rng.getrandbits(32))
    token = None
    human = next((p for p in guests if isinstance(p, HumanPlayer)), None)
    if human is not None:
        token = secrets.token_urlsafe(16)
        _humans[token] = human
    try:
        async for event in Match(players).play():
            if event.kind == "over":
                record = GameRecord.from_snapshot(event.snapshot)
                await asyncio.to_thread(history.add, record)
                tables = render_leaderboard(history.ratings()), render_history(history.records())
                yield _frame(event.snapshot, tables=tables)
                return
            yield _frame(event.snapshot, token)
            if event.kind == "move" and delay > 0:
                await asyncio.sleep(delay)
    finally:
        if token is not None:
            _humans.pop(token, None)


def _llm_choices(play_yourself: bool) -> list[int]:
    return list(range(MAX_GUESTS - int(play_yourself) + 1))


def build_app(history: GameHistory | None = None) -> gr.Blocks:
    history = history if history is not None else GameHistory.from_env()
    presets = available_presets()
    custom = custom_models_allowed()
    llms_available = bool(presets) or custom
    default_model = presets[0] if presets else None

    async def start_game(
        play_yourself: bool,
        num_llms: int,
        model_1: str | None,
        model_2: str | None,
        shuffle: bool,
        seed: str | None,
        delay: float,
    ) -> AsyncIterator[Frame]:
        async for frame in run_game(
            history, play_yourself, num_llms, model_1, model_2, shuffle, seed, delay
        ):
            yield frame

    def tables() -> tuple[str, str]:
        return render_leaderboard(history.ratings()), render_history(history.records())

    with gr.Blocks(title="Blokus Arena") as app:
        gr.Markdown(
            "# Blokus Arena\n"
            "Two heuristic bots, **Greedy** and **Tactician**, always play. "
            "You can join them, and so can up to two LLM players, for 2 to 4 players in all."
        )
        with gr.Tab("Play"):
            with gr.Row():
                with gr.Column(scale=1, min_width=260):
                    play_yourself = gr.Checkbox(
                        value=True,
                        label="I want to play",
                        info=f"You get {TIME_LIMIT_SECONDS:g} seconds per move. "
                        "If time runs out, Greedy or Tactician moves for you.",
                    )
                    num_llms = gr.Radio(
                        _llm_choices(True) if llms_available else [0],
                        value=0,
                        label="LLM players",
                        info="The same model can take both seats"
                        if llms_available
                        else "No LLM provider is set up on this server",
                        interactive=llms_available,
                    )
                    model_1 = gr.Dropdown(
                        presets,
                        value=default_model,
                        allow_custom_value=custom,
                        label="LLM 1 model",
                        info="Pick a preset or type provider:model_id" if custom else None,
                        visible=False,
                    )
                    model_2 = gr.Dropdown(
                        presets,
                        value=default_model,
                        allow_custom_value=custom,
                        label="LLM 2 model",
                        info="Pick a preset or type provider:model_id" if custom else None,
                        visible=False,
                    )
                    shuffle = gr.Checkbox(
                        value=True,
                        label="Shuffle seats",
                        info="The first seat plays Blue and starts",
                    )
                    # A textbox, because an empty gr.Number sends 0, which would repeat one game.
                    seed = gr.Textbox(
                        label="Seed (optional)",
                        placeholder="blank for a random game",
                        info="The same seed replays the same seats and bot moves",
                    )
                    delay = gr.Slider(0, 3, value=0.5, step=0.1, label="Pause after each move (s)")
                    with gr.Row():
                        start = gr.Button("Start game", variant="primary")
                        stop = gr.Button("Stop")
                with gr.Column(scale=3, min_width=340):
                    status = gr.HTML(render_status(None))
                    board = gr.HTML(
                        board_value(None),
                        html_template="${value.tray}${value.board}",
                        js_on_load=BOARD_JS,
                        server_functions=[submit_move],
                        elem_id="bk-board",
                    )
                with gr.Column(scale=3, min_width=320):
                    players = gr.HTML(render_players(None))
            gr.Markdown("### Moves")
            log = gr.HTML(render_log(None))
            last_snapshot = gr.State(None)
        with gr.Tab("Leaderboard") as leaderboard_tab:
            gr.Markdown(
                "ELO ratings from every finished game. "
                "A game counts as a match between each pair of players, won by the higher score. "
                "Everyone starts at 1500, and all people share the **Human** rating."
            )
            leaderboard = gr.HTML(render_leaderboard(history.ratings()))
            gr.Markdown("### Game history\nFinished games, newest first. Times are in UTC.")
            history_table = gr.HTML(render_history(history.records()))

        play_yourself.change(
            lambda me, n: gr.update(
                choices=_llm_choices(me), value=min(int(n), MAX_GUESTS - int(me))
            ),
            inputs=[play_yourself, num_llms],
            outputs=num_llms,
        )
        num_llms.change(
            lambda n: (gr.update(visible=n >= 1), gr.update(visible=n >= 2)),
            inputs=num_llms,
            outputs=[model_1, model_2],
        )
        started = start.click(
            start_game,
            inputs=[play_yourself, num_llms, model_1, model_2, shuffle, seed, delay],
            outputs=[status, board, players, log, leaderboard, history_table, last_snapshot],
            concurrency_limit=MAX_CONCURRENT_GAMES,
        )
        stop.click(stopped, inputs=last_snapshot, outputs=[status, board], cancels=[started])
        leaderboard_tab.select(tables, outputs=[leaderboard, history_table])
        app.load(tables, outputs=[leaderboard, history_table])
    return app


def launch() -> None:
    history = GameHistory.from_env()
    where = history.root.resolve() if history.root else "memory only"
    print(f"Blokus Arena: {len(history.records())} finished games loaded from {where}")
    # Server-side rendering is off so the page behaves the same locally and on Spaces.
    build_app(history).launch(css=CSS, theme=gr.themes.Soft(), show_error=True, ssr_mode=False)
