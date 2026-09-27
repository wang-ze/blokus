import asyncio
import re
from dataclasses import replace

import pytest

from blokus.match import Match
from blokus.players.human import HumanPlayer
from blokus.ratings import ratings
from blokus.snapshot import LogEntry
from blokus.testing import FirstMovePlayer, make_record, mid_game_match
from blokus_ui.render import (
    render_board,
    render_history,
    render_leaderboard,
    render_log,
    render_players,
    render_status,
    render_tray,
)


def first_human_turn_snapshot():
    async def find():
        events = Match([HumanPlayer(), FirstMovePlayer("Bot")]).play()
        try:
            async for event in events:
                if event.snapshot.human_turn is not None:
                    return event.snapshot
        finally:
            await events.aclose()

    return asyncio.run(find())


def test_a_person_to_move_gets_a_tray_and_corner_points():
    snapshot = first_human_turn_snapshot()
    turn = snapshot.human_turn
    tray = render_tray(snapshot)
    assert tray.count('class="bk-pick"') == len(turn.pieces) == 21
    assert tray.count(" disabled>") == len(turn.pieces) - len(turn.playable)
    assert f'data-turn="{turn.turn}"' in tray and "Your move</b> as Blue" in tray
    board = render_board(snapshot)
    assert "bk-interactive" in board
    assert board.count('class="bk-anchor bk-blue"') == len(turn.anchors) == 1
    assert "Your move" in render_status(snapshot)
    assert "human" in render_players(snapshot)


def test_no_tray_when_nobody_is_waiting():
    snapshot = replace(first_human_turn_snapshot(), human_turn=None)
    assert render_tray(snapshot) == render_tray(None) == ""
    assert "bk-interactive" not in render_board(snapshot)
    assert "bk-anchor" not in render_board(snapshot)


def test_fallback_tags_say_who_moved():
    snapshot = first_human_turn_snapshot()
    entry = LogEntry(
        1, "blue", "Human", "I1", ("A1",), fallback="played by <Tactician>", error="No move."
    )
    html = render_log(replace(snapshot, log=(entry,)))
    assert "played by &lt;Tactician&gt;" in html and "No move." in html


def test_leaderboard():
    records = [
        make_record(("Tactician", 0), ("Greedy", -5), minutes=0),
        make_record(("<b>model</b>", 0, "llm"), ("Greedy", -5), minutes=1),
    ]
    html = render_leaderboard(ratings(records))
    rows = re.findall(r"<tr><td class='bk-num-cell'>(\d+)</td>", html)
    assert rows == ["1", "2", "3"]
    assert "&lt;b&gt;model&lt;/b&gt;" in html and "<b>model</b>" not in html
    assert re.findall(r"<th[^>]*>([^<]*)</th>", html) == ["#", "Player", "ELO Rating"]
    assert "No finished games" in render_leaderboard([])


def test_history_shows_every_color_and_the_winner():
    two = make_record(("Human", -3, "human"), ("Tactician", -10), minutes=0)
    three = make_record(("A", 1), ("B", 1), ("C", -4), minutes=1)
    html = render_history([two, three])
    assert html.index("2026-09-26 12:01 UTC") < html.index("2026-09-26 12:00 UTC")  # newest first
    newest = html.split("<tr>")[2]
    assert "Shared" in newest and "tie" in newest
    oldest = html.split("<tr>")[3]
    assert oldest.count("Human") == 3  # Blue and Red, and the winner
    assert "Blue &amp; Red" in oldest or "Blue & Red" in oldest
    assert "No finished games" in render_history([])


def test_history_is_capped():
    records = [make_record(("A", 0), ("B", -1), minutes=m) for m in range(5)]
    html = render_history(records, limit=3)
    assert html.count("<tr>") == 4 and "latest 3 of 5 games" in html


@pytest.mark.parametrize("num_players", [2, 3])
def test_rendering_draws_every_remaining_piece(num_players):
    snapshot = mid_game_match(num_players).snapshot("move")
    html = render_players(snapshot)
    remaining = sum(len(c.remaining) for p in snapshot.players for c in p.colors)
    if snapshot.shared:
        remaining += len(snapshot.shared.remaining)
    assert html.count('<svg class="bk-piece"') == remaining
    board = render_board(snapshot)
    assert len(re.findall(r'<rect class="bk-(?:empty|blue|yellow|red|green)"', board)) == 400


def test_rendering_escapes_player_supplied_text():
    snapshot = asyncio.run(
        _first_thinking_snapshot(Match([FirstMovePlayer("<b>x</b>"), FirstMovePlayer("B")]))
    )
    evil = LogEntry(1, "blue", "<b>x</b>", "I1", ("A1",), reasoning="<script>alert(1)</script>")
    html = render_log(replace(snapshot, log=(evil,)))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<b>x</b>" not in render_players(snapshot)
    assert "<b>x</b>" not in render_status(snapshot)


@pytest.mark.parametrize("num_players", [2, 3, 4])
def test_every_event_of_a_full_game_renders(num_players):
    async def events():
        return [
            e async for e in Match([FirstMovePlayer(f"P{i}") for i in range(num_players)]).play()
        ]

    frames = asyncio.run(events())
    for event in frames:
        snapshot = event.snapshot
        assert snapshot.over == (snapshot.to_move is None)
        for render in (render_status, render_board, render_players, render_log):
            assert render(snapshot)
    assert frames[-2].kind == "out" and frames[-2].snapshot.over
    assert "Game over" in render_status(frames[-2].snapshot)


def test_status_line():
    match = mid_game_match(2, turns=4)
    assert "is thinking" in render_status(match.snapshot("thinking"))
    finished = mid_game_match(2, turns=10_000)
    status = render_status(finished.snapshot("over"))
    assert status.startswith('<div class="bk-status bk-over">Game over after')
    assert render_status(None).endswith("start a game.</div>")


async def _first_thinking_snapshot(match: Match):
    events = match.play()
    try:
        async for event in events:
            if event.kind == "thinking":
                return event.snapshot
    finally:
        await events.aclose()
    raise AssertionError("no thinking event")
