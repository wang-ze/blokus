import asyncio
import json
from datetime import UTC

import pytest

from blokus.match import Match
from blokus.records import GameRecord
from blokus.testing import FirstMovePlayer


def finished_snapshot(num_players: int):
    async def play():
        return [
            e async for e in Match([FirstMovePlayer(f"P{i}") for i in range(num_players)]).play()
        ]

    return asyncio.run(play())[-1].snapshot


@pytest.mark.parametrize("num_players", [2, 3, 4])
def test_record_from_a_finished_game(num_players):
    snapshot = finished_snapshot(num_players)
    record = GameRecord.from_snapshot(snapshot, game_id="g1")
    assert record.id == "g1"
    assert record.finished_at.tzinfo is UTC
    assert [p.name for p in record.players] == [p.name for p in snapshot.players]
    assert [p.score for p in record.players] == [p.score for p in snapshot.players]
    assert {p.name for p in record.winners} == set(snapshot.winners)
    assert sorted(record.color_scores) == ["blue", "green", "red", "yellow"]
    assert record.turns == snapshot.turn
    placed = [e for e in snapshot.log if e.piece is not None]
    assert len(record.moves) == len(placed)
    first = placed[0]
    assert record.moves[0] == f"{first.color} {first.piece} {' '.join(first.cells)}"
    if num_players == 3:
        assert record.shared == "green" and record.player_of("green") is None
    else:
        assert record.shared is None
        assert record.player_of("green") is not None
    assert record.player_of("blue") is record.players[0]


def test_records_round_trip_through_json():
    record = GameRecord.from_snapshot(finished_snapshot(3))
    text = json.dumps(record.to_json())
    assert GameRecord.from_json(json.loads(text)) == record


def test_only_finished_games_are_recorded():
    match = Match([FirstMovePlayer("A"), FirstMovePlayer("B")])
    with pytest.raises(ValueError, match="Only finished games"):
        GameRecord.from_snapshot(match.snapshot("start"))


def test_bad_json_is_rejected():
    data = GameRecord.from_snapshot(finished_snapshot(2)).to_json()
    with pytest.raises(ValueError, match="version"):
        GameRecord.from_json({**data, "version": 99})
    with pytest.raises(ValueError, match="time zone"):
        GameRecord.from_json({**data, "finished_at": "2026-09-26T10:00:00"})
