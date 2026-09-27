"""Running a game between players, as a stream of events for front ends."""

from __future__ import annotations

import random
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, replace

from blokus.board import BOARD_SIZE, Color, Move
from blokus.game import SHARED_COLOR, Game
from blokus.players import Decision, Player, Standing, TurnView
from blokus.players.heuristic import GreedyPlayer, TacticianPlayer
from blokus.players.human import HumanPlayer
from blokus.snapshot import (
    GameSnapshot,
    LogEntry,
    PlayerStats,
    PlayerView,
    ToMove,
    color_key,
    color_view,
    grid_view,
    human_turn,
)

MAX_GUESTS = 2
"""Players who can join the two bots: a person and LLMs, up to 4 players in all."""
RECENT_TURNS = 8
SHARED_PLAYER_NAME = "Shared"


def lineup(
    guests: Sequence[Player], *, shuffle: bool = True, seed: int | None = None
) -> list[Player]:
    """The seats for a game: the two heuristic bots plus 0-2 guests (a person and LLMs).

    Seat order decides colors (seat 0 plays Blue and moves first), so it is shuffled by default.
    """
    if len(guests) > MAX_GUESTS:
        raise ValueError(f"At most {MAX_GUESTS} players can join the two bots.")
    rng = random.Random(seed)
    players: list[Player] = [
        GreedyPlayer("Greedy", seed=rng.getrandbits(32)),
        TacticianPlayer("Tactician", seed=rng.getrandbits(32)),
        *guests,
    ]
    if shuffle:
        rng.shuffle(players)
    return players


@dataclass(frozen=True, slots=True)
class MatchEvent:
    kind: str
    """"start", "thinking", "move", "out" or "over"."""
    snapshot: GameSnapshot


class Match:
    def __init__(self, players: Sequence[Player]) -> None:
        self.players = tuple(players)
        self.game = Game(len(self.players))
        self._stats = [PlayerStats() for _ in self.players]
        self._log: list[LogEntry] = []

    async def play(self) -> AsyncIterator[MatchEvent]:
        """Play the game to the end, yielding an event (with a fresh snapshot) at each step."""
        game = self.game
        yield self._event("start")
        while (color := game.current_color) is not None:
            legal = game.board.legal_moves(color)
            if not legal:
                turn = game.retire_current()
                self._log.append(
                    LogEntry(turn.number, color_key(color), self._color_owner(color), None, ())
                )
                yield self._event("out")
                continue
            index = game.controller(color)
            yield self._event("thinking", legal)
            started = time.perf_counter()
            decision = await self.players[index].choose_move(self.turn_view(legal))
            seconds = time.perf_counter() - started
            turn = game.play(decision.move)
            self._record(index, decision, seconds, turn.number)
            yield self._event("move")
        yield self._event("over")

    def turn_view(self, legal: Sequence[Move] | None = None) -> TurnView:
        """What the player to move sees this turn. `legal` can pass already computed legal moves."""
        game = self.game
        color = game.current_color
        if color is None:
            raise RuntimeError("The game is over.")
        if legal is None:
            legal = game.board.legal_moves(color)
        friendly, opponents, scores_count = game.perspective(color)
        return TurnView(
            board=game.board.copy(),
            color=color,
            turn=len(game.turns) + 1,
            player=game.controller(color),
            friendly=friendly,
            opponents=opponents,
            scores_count=scores_count,
            legal_moves=tuple(legal),
            standings=tuple(
                Standing(
                    p.name,
                    game.colors_of(i),
                    game.player_score(i),
                    sum(game.board.remaining_squares(c) for c in game.colors_of(i)),
                )
                for i, p in enumerate(self.players)
            ),
            recent_turns=tuple(game.turns[-RECENT_TURNS:]),
        )

    def _record(self, index: int, decision: Decision, seconds: float, turn: int) -> None:
        stats = self._stats[index]
        self._stats[index] = replace(
            stats,
            moves=stats.moves + 1,
            think_seconds=stats.think_seconds + seconds,
            invalid_attempts=stats.invalid_attempts + decision.invalid_attempts,
            fallbacks=stats.fallbacks + bool(decision.fallback),
            tokens=stats.tokens + decision.tokens,
        )
        move = decision.move
        self._log.append(
            LogEntry(
                turn=turn,
                color=color_key(move.color),
                player=self.players[index].name,
                piece=move.piece,
                cells=tuple(move.cell_names),
                reasoning=decision.reasoning,
                fallback=decision.fallback,
                error=decision.error,
                seconds=seconds,
            )
        )

    def _color_owner(self, color: Color) -> str:
        owner = self.game.owner(color)
        return SHARED_PLAYER_NAME if owner is None else self.players[owner].name

    def _event(self, kind: str, legal: Sequence[Move] = ()) -> MatchEvent:
        return MatchEvent(kind, self.snapshot(kind, legal))

    def snapshot(self, event: str, legal: Sequence[Move] = ()) -> GameSnapshot:
        """The game as plain data. On "thinking" events for a person, pass the legal moves too."""
        game = self.game
        board = game.board

        def colors(player: int):
            return tuple(
                color_view(board, c, out=c in game.finished) for c in game.colors_of(player)
            )

        last_move = next((t.move for t in reversed(game.turns) if t.move is not None), None)
        color = game.current_color
        to_move = None
        waiting = None
        if color is not None:
            mover = self.players[game.controller(color)]
            to_move = ToMove(color_key(color), mover.name, mover.kind, mover.detail)
            if event == "thinking" and isinstance(mover, HumanPlayer) and legal:
                waiting = human_turn(board, len(game.turns) + 1, mover.time_limit, legal)
        return GameSnapshot(
            event=event,
            over=game.is_over,
            turn=len(game.turns),
            grid=grid_view(board),
            last_move=tuple(sorted(divmod(i, BOARD_SIZE) for i in last_move.cells))
            if last_move
            else (),
            to_move=to_move,
            players=tuple(
                PlayerView(
                    index=i,
                    name=p.name,
                    kind=p.kind,
                    identity=p.identity,
                    detail=p.detail,
                    score=game.player_score(i),
                    squares_left=sum(board.remaining_squares(c) for c in game.colors_of(i)),
                    active=any(c not in game.finished for c in game.colors_of(i)),
                    colors=colors(i),
                    stats=self._stats[i],
                )
                for i, p in enumerate(self.players)
            ),
            shared=(
                color_view(board, SHARED_COLOR, out=SHARED_COLOR in game.finished)
                if game.owner(SHARED_COLOR) is None
                else None
            ),
            log=tuple(self._log),
            winners=tuple(self.players[i].name for i in game.winners()) if game.is_over else (),
            human_turn=waiting,
        )
