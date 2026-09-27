"""The Gradio layer, driven the way a browser would: frames out, moves in via submit_move."""

import asyncio

import gradio as gr
import pytest

from blokus.board import BOARD_SIZE, cell_name
from blokus.history import GameHistory
from blokus_ui import app
from blokus_ui.app import board_value, parse_seed, run_game, stopped, submit_move


def cells_of(key: str) -> tuple[str, list[str]]:
    piece, indices = key.split(":")
    return piece, [cell_name(int(i)) for i in indices.split(",")]


async def play_as_person(history: GameHistory) -> tuple[list, list]:
    """Play a whole game as a person who first tries a move that is never legal (two cells that
    are not connected), then makes the last listed legal move. Like a browser, it answers each
    frame while the game goes on waiting."""
    frames, replies = [], []

    async def answer(value):
        await asyncio.sleep(0.01)
        token, turn = value["token"], value["turn"]["turn"]
        wrong = {"token": token, "turn": turn, "piece": "I2", "cells": ["A1", "C3"]}
        replies.append(await submit_move(wrong))
        piece, cells = cells_of(value["turn"]["legal"][-1])
        right = {"token": token, "turn": turn, "piece": piece, "cells": cells}
        replies.append(await submit_move(right))

    answers = []
    async for frame in run_game(history, True, 0, None, None, True, "7", 0):
        frames.append(frame)
        value = frame[1]
        if isinstance(value, dict) and value["turn"] is not None:
            assert value["token"] in app._humans
            answers.append(asyncio.create_task(answer(value)))
    await asyncio.gather(*answers)
    return frames, replies


def test_a_person_plays_a_whole_game_and_it_is_recorded():
    history = GameHistory(None)
    frames, replies = asyncio.run(play_as_person(history))
    assert not app._humans  # the seat is released when the game ends
    wrong, right = replies[::2], replies[1::2]
    assert wrong and all(not r["ok"] and r["error"] for r in wrong)
    assert all(r == {"ok": True, "error": None} for r in right)
    *playing, final = frames
    assert all(f[4] == f[5] == gr.skip() for f in playing)
    assert all(f[6].turn == len(f[6].log) for f in frames)  # the snapshot, kept for Stop
    assert "Game over" in final[0]
    assert final[1]["turn"] is None and final[1]["token"] is None
    assert "Human" in final[4] and "Human" in final[5]
    (record,) = history.records()
    human = next(p for p in record.players if p.kind == "human")
    assert human.moves > 0 and human.fallbacks == 0
    assert len(record.players) == 3


def test_board_value_without_a_person_to_move():
    value = board_value(None)
    assert value["turn"] is None and value["token"] is None and value["tray"] == ""
    assert f'data-size="{BOARD_SIZE}"' in value["board"]


@pytest.mark.parametrize(
    "data",
    [None, {}, {"token": "nope", "turn": 1, "piece": "I1", "cells": ["A1"]}, "x", 3],
)
def test_submit_move_rejects_unknown_games_and_bad_data(data):
    reply = asyncio.run(submit_move(data))
    assert reply["ok"] is False and reply["error"]


def test_submit_move_rejects_malformed_moves(monkeypatch):
    class Human:
        def submit(self, turn, piece, cells):
            raise AssertionError("should not be called")

    monkeypatch.setitem(app._humans, "t", Human())
    for data in (
        {"token": "t", "turn": "one", "piece": "I1", "cells": ["A1"]},
        {"token": "t", "turn": 1, "piece": "I1", "cells": "A1"},
        {"token": "t", "turn": 1, "piece": "I1"},
    ):
        assert asyncio.run(submit_move(data)) == {
            "ok": False,
            "error": "That move could not be read.",
        }


def test_hosted_apps_only_offer_preset_models(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "someone/blokus")
    monkeypatch.delenv("BLOKUS_CUSTOM_MODELS", raising=False)
    monkeypatch.setattr(app, "available_presets", lambda: ["ollama:llama3.2"])

    async def start(spec):
        async for _ in run_game(GameHistory(None), False, 1, spec, None, True, "", 0):
            break

    with pytest.raises(gr.Error, match="Pick LLM 1 from the list"):
        asyncio.run(start("openrouter:some/expensive-model"))


def test_the_app_builds(tmp_path):
    blocks = app.build_app(GameHistory(tmp_path))
    assert isinstance(blocks, gr.Blocks)


def test_a_blank_seed_means_a_random_game():
    assert parse_seed("") is None and parse_seed(None) is None and parse_seed("  ") is None
    assert parse_seed(" 42 ") == 42 and parse_seed(7) == 7
    with pytest.raises(gr.Error, match="whole number"):
        parse_seed("abc")


def test_stop_keeps_the_position_but_removes_the_piece_picker():
    async def first_human_frame():
        frames = run_game(GameHistory(None), True, 0, None, None, False, "1", 0)
        try:
            async for frame in frames:
                if frame[1]["turn"] is not None:
                    return frame
        finally:
            await frames.aclose()

    frame = asyncio.run(first_human_frame())
    status, value = stopped(frame[6])
    assert "Game stopped after" in status and "Only finished games" in status
    assert value["turn"] is None and value["tray"] == ""
    assert "bk-anchor" not in value["board"] and "bk-interactive" not in value["board"]
    assert value["board"].count('<rect class="bk-blue"') == frame[1]["board"].count(
        '<rect class="bk-blue"'
    )
    assert stopped(None) == (gr.skip(), gr.skip())
