import asyncio

from blokus.board import BOARD_SIZE, Color, cell_name
from blokus.match import Match
from blokus.players.human import HumanPlayer
from blokus.snapshot import placement_key
from blokus.testing import FirstMovePlayer, random_game


def turn_view(num_players=2, seed=3, turns=6):
    match = Match([FirstMovePlayer(f"P{i}") for i in range(num_players)])
    match.game = random_game(num_players, seed=seed, turns=turns)
    return match.turn_view()


def names(move):
    return [cell_name(i) for i in sorted(move.cells)]


async def play_turn(human, view, *submissions):
    """Run choose_move while submitting moves; returns (decision, replies to each submit)."""
    task = asyncio.create_task(human.choose_move(view))
    await asyncio.sleep(0)
    replies = [human.submit(*args) for args in submissions]
    return await task, replies


def test_a_submitted_legal_move_is_played():
    view = turn_view()
    move = view.legal_moves[-1]
    human = HumanPlayer(time_limit=5)
    decision, replies = asyncio.run(play_turn(human, view, (view.turn, move.piece, names(move))))
    assert replies == [None]
    assert decision.move == move
    assert not decision.fallback and decision.error is None
    assert human.waiting_for is None


def test_illegal_or_stale_moves_are_explained_and_the_turn_goes_on():
    view = turn_view()
    move = view.legal_moves[0]
    human = HumanPlayer(time_limit=5)
    decision, replies = asyncio.run(
        play_turn(
            human,
            view,
            (view.turn - 1, move.piece, names(move)),
            (view.turn, move.piece, ["A1", "Z99"]),
            (view.turn, "X5", ["K10"]),
            (view.turn, move.piece, names(move)),
            (view.turn, move.piece, names(move)),
        )
    )
    assert replies[0] == "It is not your turn any more."
    assert "'Z99' is not a board cell" in replies[1]
    assert "X5" in replies[2]
    assert replies[3] is None
    assert replies[4] == "It is not your turn any more."
    assert decision.move == move


def test_a_bot_moves_when_time_runs_out(monkeypatch):
    monkeypatch.setattr("blokus.players.human.SUBMIT_GRACE_SECONDS", 0.0)
    view = turn_view()
    human = HumanPlayer(time_limit=0.01, seed=1)
    stand_ins = set()
    for _ in range(12):
        decision, _ = asyncio.run(play_turn(human, view))
        assert decision.move in view.legal_moves
        assert decision.fallback in {"played by Greedy", "played by Tactician"}
        assert decision.error == "No move within 0.01s."
        stand_ins.add(decision.fallback)
    assert len(stand_ins) == 2
    assert human.submit(view.turn, "I1", ["A1"]) == "It is not your turn any more."


def test_human_turn_in_snapshots_lists_every_legal_placement():
    async def first_human_turn(match):
        events = match.play()
        try:
            async for event in events:
                if event.snapshot.human_turn is not None:
                    return event, match.turn_view()
        finally:
            await events.aclose()

    human = HumanPlayer()
    match = Match([FirstMovePlayer("A"), human])
    event, view = asyncio.run(first_human_turn(match))
    turn = event.snapshot.human_turn
    assert event.kind == "thinking"
    assert event.snapshot.to_move.player_kind == "human"
    assert turn.turn == view.turn == event.snapshot.turn + 1
    assert turn.color == view.color.name.lower() == "yellow"
    assert turn.seconds == human.time_limit
    assert set(turn.legal) == {placement_key(m.piece, m.cells) for m in view.legal_moves}
    assert len(turn.legal) == len(view.legal_moves)
    assert [p.name for p in turn.pieces] == view.board.remaining_pieces(Color.YELLOW)
    assert set(turn.playable) == {m.piece for m in view.legal_moves}
    assert turn.anchors == ((0, BOARD_SIZE - 1),)


def test_placement_keys_sort_cells_numerically():
    assert placement_key("I3", [40, 0, 20]) == "I3:0,20,40"


def test_a_game_with_a_person_who_never_moves_still_finishes(monkeypatch):
    monkeypatch.setattr("blokus.players.human.SUBMIT_GRACE_SECONDS", 0.0)

    async def play(match):
        return [event async for event in match.play()]

    human = HumanPlayer(time_limit=0.001, seed=2)
    events = asyncio.run(play(Match([FirstMovePlayer("A"), human, FirstMovePlayer("B")])))
    final = events[-1].snapshot
    assert final.over and final.human_turn is None
    person = next(p for p in final.players if p.kind == "human")
    assert person.identity == "Human"
    assert person.stats.moves > 0 and person.stats.fallbacks == person.stats.moves
    human_turns = [e for e in events if e.snapshot.human_turn is not None]
    assert human_turns and all(e.kind == "thinking" for e in human_turns)
    assert all(e.snapshot.to_move.player == "Human" for e in human_turns)
