"""LLM players, built on the OpenAI Agents SDK.

Each turn is a fresh agent run with two tools: `list_legal_moves` to look up exact placements,
and `place_piece` to submit a move. The engine validates every submission and returns the
reason when it is illegal, so the model can correct itself. The run ends as soon as a move is
accepted. If the model never gets there (too many illegal moves, an API error, a timeout), the
player falls back to a random legal move and flags the decision.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

from agents import (
    Agent,
    FunctionToolResult,
    Model,
    RunContextWrapper,
    Runner,
    ToolsToFinalOutputResult,
    function_tool,
)

from blokus.board import Board, IllegalMove, Move, parse_cell
from blokus.pieces import PIECES
from blokus.players import Decision, Player, TurnView
from blokus.players.prompts import NUDGE, system_prompt, turn_prompt
from blokus.providers import ModelSpec, build_model

MAX_INVALID_ATTEMPTS = 3
MAX_MODEL_CALLS = 10
"""Per agent run; a turn has at most two runs (the second after a nudge)."""
TURN_TIMEOUT_SECONDS = 120.0
LISTED_PLACEMENTS = 40
MAX_REASONING_CHARS = 500
MAX_ERROR_CHARS = 300
RANDOM_FALLBACK = "random fallback"


@dataclass
class _TurnState:
    view: TurnView
    move: Move | None = None
    reasoning: str = ""
    invalid_attempts: int = 0
    last_error: str | None = None

    @property
    def gave_up(self) -> bool:
        return self.invalid_attempts >= MAX_INVALID_ATTEMPTS

    @property
    def decided(self) -> bool:
        return self.move is not None or self.gave_up


def list_placements(view: TurnView, piece: str, corner_point: str = "") -> str:
    """Legal placements of one piece, as text for the model (a spread of them if there are many)."""
    name = piece.strip().upper()
    if name not in PIECES:
        return f"Unknown piece {piece!r}. Piece names are: {', '.join(PIECES)}."
    if name not in view.board.remaining[view.color]:
        return f"You have already played {name}."
    moves = [move for move in view.legal_moves if move.piece == name]
    where = ""
    if corner_point.strip():
        try:
            anchor = parse_cell(corner_point)
        except ValueError as error:
            return str(error)
        moves = [move for move in moves if anchor in move.cells]
        where = f" covering {corner_point.strip().upper()}"
    if not moves:
        return f"{name} has no legal placement{where} right now."
    moves.sort(key=lambda move: sorted(move.cells))
    header = f"{len(moves)} legal placements for {name}{where}"
    if len(moves) > LISTED_PLACEMENTS:
        step = len(moves) / LISTED_PLACEMENTS
        moves = [moves[int(k * step)] for k in range(LISTED_PLACEMENTS)]
        header += f" (a spread of {LISTED_PLACEMENTS}; pass corner_point to see all near one spot)"
    return header + ":\n" + "\n".join(" ".join(move.cell_names) for move in moves)


@function_tool
def list_legal_moves(ctx: RunContextWrapper[_TurnState], piece: str, corner_point: str) -> str:
    """List legal placements for one of your remaining pieces.

    Args:
        piece: Piece name, e.g. "L5".
        corner_point: Only list placements covering this corner point, e.g. "F6". Use "" to list
            placements at any corner point.
    """
    return list_placements(ctx.context.view, piece, corner_point)


@function_tool
def place_piece(
    ctx: RunContextWrapper[_TurnState], reasoning: str, piece: str, cells: list[str]
) -> str:
    """Place a piece on the board. This ends your turn if the move is legal.

    Args:
        reasoning: One or two sentences on why this is a good move.
        piece: Piece name, e.g. "L5".
        cells: Every cell the piece will cover, e.g. ["E5", "E6", "E7", "E8", "F8"].
    """
    state = ctx.context
    if state.move is not None:
        return "Your move was already accepted; your turn is over."
    if state.gave_up:
        return "No attempts left; your turn is over."
    board: Board = state.view.board
    try:
        move = board.validate(state.view.color, piece, cells)
    except IllegalMove as error:
        state.invalid_attempts += 1
        state.last_error = str(error)
        attempts_left = MAX_INVALID_ATTEMPTS - state.invalid_attempts
        if attempts_left <= 0:
            return f"Illegal move: {error} No attempts left; your turn will be played at random."
        return (
            f"Illegal move: {error} You have {attempts_left} attempt(s) left. "
            "list_legal_moves shows exact legal placements."
        )
    state.move = move
    state.reasoning = reasoning.strip()[:MAX_REASONING_CHARS]
    return "Move accepted."


def _stop_when_decided(
    ctx: RunContextWrapper[_TurnState], results: list[FunctionToolResult]
) -> ToolsToFinalOutputResult:
    if ctx.context.decided:
        return ToolsToFinalOutputResult(is_final_output=True, final_output="done")
    return ToolsToFinalOutputResult(is_final_output=False)


class LLMPlayer(Player):
    kind = "llm"

    def __init__(
        self,
        name: str,
        model: Model,
        model_label: str,
        *,
        seed: int | None = None,
        timeout: float = TURN_TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(name)
        self.model_label = model_label
        self._rng = random.Random(seed)
        self._timeout = timeout
        self._notes = ""
        self._agent = Agent[_TurnState](
            name=name,
            instructions=system_prompt(MAX_INVALID_ATTEMPTS),
            model=model,
            tools=[list_legal_moves, place_piece],
            tool_use_behavior=_stop_when_decided,
        )

    @classmethod
    def from_spec(cls, name: str, spec: str, *, seed: int | None = None) -> LLMPlayer:
        """Build a player for a "provider:model" spec. Raises ValueError for a bad spec or key."""
        model_spec = ModelSpec.parse(spec)
        return cls(name, build_model(model_spec), str(model_spec), seed=seed)

    @property
    def identity(self) -> str:
        return self.model_label

    @property
    def detail(self) -> str:
        return self.model_label

    async def choose_move(self, view: TurnView) -> Decision:
        state = _TurnState(view)
        tokens = 0
        error: str | None = None
        try:
            async with asyncio.timeout(self._timeout):
                tokens = await self._converse(state, turn_prompt(view, self.name, self._notes))
        except TimeoutError:
            error = f"No move within {self._timeout:g}s."
        except Exception as exc:  # Any model or SDK failure: fall back rather than end the game.
            error = f"{type(exc).__name__}: {exc}"

        if state.move is not None:
            self._notes = state.reasoning
            return Decision(
                state.move,
                reasoning=state.reasoning,
                invalid_attempts=state.invalid_attempts,
                tokens=tokens,
            )
        if error is None:
            error = (
                f"Gave up after {state.invalid_attempts} illegal moves. Last: {state.last_error}"
                if state.gave_up
                else "Replied without placing a piece."
            )
        return Decision(
            self._rng.choice(view.legal_moves),
            fallback=RANDOM_FALLBACK,
            error=error[:MAX_ERROR_CHARS],
            invalid_attempts=state.invalid_attempts,
            tokens=tokens,
        )

    async def _converse(self, state: _TurnState, prompt: str) -> int:
        """Run the agent until it places a piece or gives up. Returns the tokens used."""
        result = await Runner.run(self._agent, prompt, context=state, max_turns=MAX_MODEL_CALLS)
        tokens = result.context_wrapper.usage.total_tokens
        if not state.decided:
            # It answered in plain text instead of calling a tool: remind it once.
            follow_up = [*result.to_input_list(), {"role": "user", "content": NUDGE}]
            result = await Runner.run(
                self._agent, follow_up, context=state, max_turns=MAX_MODEL_CALLS
            )
            tokens += result.context_wrapper.usage.total_tokens
        return tokens
