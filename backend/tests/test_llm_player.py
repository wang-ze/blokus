import asyncio
import json
from collections import Counter

import pytest
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call

from blokus.board import Color, Move, parse_cell
from blokus.match import Match
from blokus.pieces import PIECES
from blokus.players.llm import LISTED_PLACEMENTS, MAX_INVALID_ATTEMPTS, LLMPlayer, list_placements
from blokus.players.prompts import NUDGE
from blokus.testing import FirstMovePlayer, random_game

TOP_EDGE_I5 = ["A1", "B1", "C1", "D1", "E1"]
BLUE_I5 = Move(Color.BLUE, "I5", frozenset(parse_cell(c) for c in TOP_EDGE_I5))


def place(cells: list[str], piece: str = "I5", reasoning: str = "Along the edge.", n: int = 0):
    return [
        function_call(
            "place_piece",
            {"reasoning": reasoning, "piece": piece, "cells": cells},
            call_id=f"place-{n}",
        )
    ]


def first_turn_view():
    """Blue's first turn in a 2-player game."""
    return Match([FirstMovePlayer("A"), FirstMovePlayer("B")]).turn_view()


def seen_by_model(model: ScriptedModel, call: int) -> str:
    """Everything the model received in one call, flattened for substring checks."""
    return json.dumps(model.calls[call].input, default=str)


def choose(player: LLMPlayer, view=None):
    return asyncio.run(player.choose_move(view or first_turn_view()))


def test_lists_moves_then_places_a_legal_one():
    model = ScriptedModel(
        [
            [function_call("list_legal_moves", {"piece": "I5", "corner_point": ""}, call_id="l")],
            place(TOP_EDGE_I5),
        ]
    )
    decision = choose(LLMPlayer("LLM 1", model, "scripted"))
    assert decision.move == BLUE_I5
    assert decision.reasoning == "Along the edge."
    assert not decision.fallback
    assert decision.invalid_attempts == 0
    assert model.remaining_steps == 0
    assert "2 legal placements for I5" in seen_by_model(model, 1)


def test_illegal_move_reason_is_sent_back_and_the_model_can_retry():
    model = ScriptedModel([place(["B1", "C1", "D1", "E1", "F1"]), place(TOP_EDGE_I5, n=1)])
    decision = choose(LLMPlayer("LLM 1", model, "scripted"))
    assert decision.move == BLUE_I5
    assert decision.invalid_attempts == 1
    assert not decision.fallback
    assert "must cover its starting corner A1" in seen_by_model(model, 1)


def test_repeated_illegal_moves_fall_back_to_a_random_legal_move():
    bad = ["B1", "C1", "D1", "E1", "F1"]
    model = ScriptedModel([place(bad, n=i) for i in range(MAX_INVALID_ATTEMPTS)])
    view = first_turn_view()
    decision = choose(LLMPlayer("LLM 1", model, "scripted", seed=0), view)
    assert decision.fallback
    assert decision.move in view.legal_moves
    assert decision.invalid_attempts == MAX_INVALID_ATTEMPTS
    assert decision.error.startswith(f"Gave up after {MAX_INVALID_ATTEMPTS} illegal moves")
    assert model.remaining_steps == 0


def test_model_errors_fall_back():
    model = ScriptedModel([ModelStep.raise_error(RuntimeError("provider down"))])
    decision = choose(LLMPlayer("LLM 1", model, "scripted"))
    assert decision.fallback
    assert decision.error == "RuntimeError: provider down"


def test_a_plain_text_reply_gets_one_nudge():
    model = ScriptedModel(
        [[assistant_message("I will play I5 on the top edge.")], place(TOP_EDGE_I5)]
    )
    decision = choose(LLMPlayer("LLM 1", model, "scripted"))
    assert decision.move == BLUE_I5
    assert not decision.fallback
    assert NUDGE in seen_by_model(model, 1)


def test_two_plain_text_replies_fall_back():
    model = ScriptedModel([[assistant_message("Hmm.")], [assistant_message("Still thinking.")]])
    decision = choose(LLMPlayer("LLM 1", model, "scripted"))
    assert decision.fallback
    assert decision.error == "Replied without placing a piece."


def test_slow_models_time_out_and_fall_back():
    async def slow(call):
        await asyncio.sleep(5)
        return place(TOP_EDGE_I5)

    model = ScriptedModel([ModelStep.respond(slow)])
    decision = choose(LLMPlayer("LLM 1", model, "scripted", timeout=0.05))
    assert decision.fallback
    assert decision.error == "No move within 0.05s."


def test_reasoning_is_carried_into_the_next_turn_as_notes():
    red_i5 = ["T20", "S20", "R20", "Q20", "P20"]
    model = ScriptedModel(
        [place(TOP_EDGE_I5, reasoning="Head for the center next."), place(red_i5, n=1)]
    )
    llm = LLMPlayer("LLM 1", model, "scripted")
    match = Match([llm, FirstMovePlayer("B")])
    game = match.game
    game.play(asyncio.run(llm.choose_move(match.turn_view())).move)  # Blue
    game.play(match.turn_view().legal_moves[0])  # Yellow
    decision = asyncio.run(llm.choose_move(match.turn_view()))  # Red, also LLM 1's color
    assert decision.move.color == Color.RED
    assert "Your notes from your previous turn: Head for the center next." in seen_by_model(
        model, 1
    )


def test_list_placements_filters_and_samples():
    view = first_turn_view()
    assert list_placements(view, "i5") == (
        "2 legal placements for I5:\nA1 B1 C1 D1 E1\nA1 A2 A3 A4 A5"
    )
    assert list_placements(view, "Q7").startswith("Unknown piece 'Q7'")
    assert list_placements(view, "L5", "J10") == "L5 has no legal placement covering J10 right now."
    assert "not a board cell" in list_placements(view, "L5", "Z99")

    match = Match([FirstMovePlayer("A"), FirstMovePlayer("B")])
    match.game = random_game(2, seed=11, turns=12)
    busy = match.turn_view()
    counts = Counter(m.piece for m in busy.legal_moves)
    piece, total = counts.most_common(1)[0]
    assert total > LISTED_PLACEMENTS
    listing = list_placements(busy, piece)
    assert listing.startswith(f"{total} legal placements for {piece} (a spread of")
    assert len(listing.splitlines()) == LISTED_PLACEMENTS + 1

    played = next(name for name in PIECES if name not in busy.board.remaining[busy.color])
    assert list_placements(busy, played) == f"You have already played {played}."


@pytest.mark.parametrize(
    ("spec", "message"),
    [("", "provider:model_id"), ("nope:model", "Unknown provider"), ("groq:llama", "GROQ_API_KEY")],
)
def test_from_spec_rejects_bad_specs(spec, message, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match=message):
        LLMPlayer.from_spec("LLM 1", spec)
