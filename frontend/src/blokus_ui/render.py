"""Pure functions from snapshots, game records and ratings to HTML/SVG.

Only plain data and board notation constants are used here, never live game state.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from blokus.board import BOARD_SIZE, COLUMNS, START_CORNERS, Color
from blokus.ratings import Rating
from blokus.records import GameRecord
from blokus.snapshot import (
    ColorView,
    GameSnapshot,
    HumanTurn,
    LogEntry,
    PieceView,
    PlayerView,
    color_key,
)

_CORNERS = {color_key(color): divmod(i, BOARD_SIZE) for color, i in START_CORNERS.items()}

# Colors are defined once here, as CSS custom properties, with dark-mode overrides.
CSS = """
:root {
  --bk-blue: #2f6fde;
  --bk-yellow: #eab308;
  --bk-red: #dc2d45;
  --bk-green: #1f9d55;
  --bk-empty: #eef1f5;
  --bk-board: #cbd2db;
  --bk-label: #6b7280;
  --bk-mark: #ffffff;
  --bk-muted: #6b7280;
  --bk-card: #ffffff;
  --bk-border: #e2e6ec;
  --bk-accent: #2563eb;
  --bk-danger-bg: #fdecec;
  --bk-danger-fg: #b42318;
}
.dark {
  --bk-empty: #1e2530;
  --bk-board: #0e131a;
  --bk-label: #9aa4b2;
  --bk-mark: #0e131a;
  --bk-muted: #9aa4b2;
  --bk-card: #161b22;
  --bk-border: #2b323c;
  --bk-accent: #7aa2ff;
  --bk-danger-bg: #3a1618;
  --bk-danger-fg: #ff9b95;
}
.bk-board { width: 100%; max-width: 620px; height: auto; display: block; margin: 0 auto; }
.bk-board .bk-bg { fill: var(--bk-board); }
.bk-board .bk-label { fill: var(--bk-label); font: 10px system-ui, sans-serif; }
.bk-empty { fill: var(--bk-empty); }
.bk-blue { fill: var(--bk-blue); }
.bk-yellow { fill: var(--bk-yellow); }
.bk-red { fill: var(--bk-red); }
.bk-green { fill: var(--bk-green); }
.bk-board .bk-last { fill: var(--bk-mark); opacity: 0.85; }
.bk-board .bk-corner { fill: none; stroke-width: 2.5; }
.bk-status { font-size: 1.05rem; padding: 8px 12px; border-radius: 8px;
  border: 1px solid var(--bk-border); background: var(--bk-card); }
.bk-status.bk-over { border-color: var(--bk-accent); font-weight: 600; }
.bk-players { display: flex; flex-direction: column; gap: 10px; }
.bk-player { border: 1px solid var(--bk-border); border-radius: 10px; padding: 10px 12px;
  background: var(--bk-card); }
.bk-player.bk-turn { border-color: var(--bk-accent); box-shadow: 0 0 0 1px var(--bk-accent); }
.bk-player.bk-inactive { opacity: 0.7; }
.bk-head { display: flex; align-items: center; gap: 8px; }
.bk-head .bk-name { font-weight: 600; }
.bk-head .bk-score { margin-left: auto; font-weight: 700; font-variant-numeric: tabular-nums; }
.bk-kind { font-size: 0.75rem; padding: 1px 6px; border-radius: 999px;
  border: 1px solid var(--bk-border); color: var(--bk-muted); }
.bk-detail, .bk-stats { font-size: 0.8rem; color: var(--bk-muted); margin-top: 2px; }
.bk-swatch { display: inline-block; width: 12px; height: 12px; border-radius: 3px;
  vertical-align: middle; }
.bk-bg-blue { background: var(--bk-blue); }
.bk-bg-yellow { background: var(--bk-yellow); }
.bk-bg-red { background: var(--bk-red); }
.bk-bg-green { background: var(--bk-green); }
.bk-color-row { display: flex; gap: 8px; align-items: flex-start; margin-top: 8px; }
.bk-color-row.bk-out { opacity: 0.5; }
.bk-color-label { width: 64px; flex: none; font-size: 0.8rem; color: var(--bk-muted); }
.bk-pieces { display: flex; flex-wrap: wrap; gap: 6px 8px; align-items: flex-end; }
.bk-piece { display: block; }
.bk-none { font-size: 0.8rem; color: var(--bk-muted); }
.bk-log { list-style: none; margin: 0; padding: 0; max-height: 420px; overflow-y: auto; }
.bk-log li { padding: 6px 4px; border-bottom: 1px solid var(--bk-border); font-size: 0.9rem; }
.bk-log .bk-num { color: var(--bk-muted); font-variant-numeric: tabular-nums; margin-right: 4px; }
.bk-log .bk-cells { color: var(--bk-muted); font-size: 0.8rem; }
.bk-log .bk-reason { font-style: italic; color: var(--bk-muted); margin-top: 2px; }
.bk-log .bk-error { color: var(--bk-danger-fg); font-size: 0.8rem; margin-top: 2px; }
.bk-tag { font-size: 0.7rem; padding: 1px 6px; border-radius: 999px; margin-left: 4px;
  background: var(--bk-danger-bg); color: var(--bk-danger-fg); }
.bk-board.bk-interactive { cursor: pointer; touch-action: manipulation; }
.bk-board .bk-anchor { opacity: 0.9; }
.bk-board .bk-preview rect { pointer-events: none; }
.bk-board .bk-preview.bk-bad rect { fill: none; stroke: var(--bk-danger-fg); stroke-width: 2;
  stroke-dasharray: 4 2; }
.bk-board .bk-preview.bk-ok rect { opacity: 0.6; }
.bk-tray { border: 1px solid var(--bk-accent); border-radius: 10px; padding: 10px 12px;
  margin-bottom: 8px; background: var(--bk-card); }
.bk-tray-head { display: flex; align-items: center; gap: 8px; }
.bk-tray-head .bk-clock { margin-left: auto; font-weight: 700; font-size: 1.2rem;
  font-variant-numeric: tabular-nums; }
.bk-tray-head .bk-clock.bk-low { color: var(--bk-danger-fg); }
.bk-timebar { height: 4px; border-radius: 2px; background: var(--bk-border); margin: 6px 0 8px;
  overflow: hidden; }
.bk-timebar-fill { height: 100%; width: 100%; }
.bk-picks { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.bk-pick { border: 2px solid transparent; border-radius: 6px; padding: 2px; background: none;
  cursor: pointer; line-height: 0; }
.bk-pick:hover { border-color: var(--bk-border); }
.bk-pick.bk-selected { border-color: var(--bk-accent); }
.bk-pick:disabled { opacity: 0.25; cursor: not-allowed; }
.bk-controls { display: flex; align-items: center; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.bk-controls button { border: 1px solid var(--bk-border); border-radius: 6px; padding: 2px 10px;
  background: var(--bk-card); cursor: pointer; font-size: 0.85rem; }
.bk-hand { display: inline-flex; width: 56px; height: 56px; align-items: center;
  justify-content: center; }
/* Fixed height, so messages never move the board between two taps. */
.bk-msg { font-size: 0.85rem; color: var(--bk-muted); height: 2.6em; line-height: 1.3em;
  overflow: hidden; margin-top: 4px; }
.bk-msg.bk-error { color: var(--bk-danger-fg); }
.bk-help { font-size: 0.75rem; color: var(--bk-muted); }
.bk-help summary { cursor: pointer; }
.bk-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; border: none; }
.bk-table tr { border: none; }
.bk-table th, .bk-table td { text-align: left; padding: 6px 8px; border: none;
  border-bottom: 1px solid var(--bk-border); vertical-align: top; }
.bk-table th { color: var(--bk-muted); font-weight: 600; white-space: nowrap; }
.bk-table td.bk-num-cell, .bk-table th.bk-num-cell { text-align: right;
  font-variant-numeric: tabular-nums; }
.bk-table .bk-sub { display: block; font-size: 0.75rem; color: var(--bk-muted); }
.bk-table .bk-when, .bk-table .bk-nowrap { white-space: nowrap; }
.bk-table.bk-ratings { width: auto; min-width: min(100%, 24rem); }
/* Gradio's page hides sideways overflow, so wide tables scroll inside their own box. */
.bk-scroll { overflow-x: auto; max-width: 100%; }
.bk-note { font-size: 0.85rem; color: var(--bk-muted); margin: 6px 0; }
"""

_CELL = 24
_MARGIN = 20


def render_board(snapshot: GameSnapshot | None) -> str:
    """The board as an SVG, with the last move marked and empty start corners outlined.

    While a person is to move, their corner points are marked too. The `data-` attributes give
    the grid geometry in SVG units, for the interactive layer.
    """
    grid = snapshot.grid if snapshot else ((None,) * BOARD_SIZE,) * BOARD_SIZE
    last = set(snapshot.last_move) if snapshot else set()
    waiting = snapshot.human_turn if snapshot else None
    size = _MARGIN + BOARD_SIZE * _CELL + 2
    classes = "bk-board bk-interactive" if waiting else "bk-board"
    parts = [
        f'<svg class="{classes}" viewBox="0 0 {size} {size}" role="img" '
        f'aria-label="Blokus board" data-margin="{_MARGIN}" data-cell="{_CELL}" '
        f'data-size="{BOARD_SIZE}">',
        f'<rect class="bk-bg" x="{_MARGIN - 1}" y="{_MARGIN - 1}" '
        f'width="{BOARD_SIZE * _CELL + 2}" height="{BOARD_SIZE * _CELL + 2}" rx="4"/>',
    ]
    for i, letter in enumerate(COLUMNS):
        x = _MARGIN + i * _CELL + _CELL / 2
        parts.append(f'<text class="bk-label" x="{x}" y="13" text-anchor="middle">{letter}</text>')
    for row in range(BOARD_SIZE):
        y = _MARGIN + row * _CELL + _CELL / 2 + 3.5
        parts.append(
            f'<text class="bk-label" x="{_MARGIN - 5}" y="{y}" text-anchor="end">{row + 1}</text>'
        )
    for row, cells in enumerate(grid):
        for col, color in enumerate(cells):
            x, y = _MARGIN + col * _CELL + 1, _MARGIN + row * _CELL + 1
            parts.append(
                f'<rect class="bk-{color or "empty"}" x="{x}" y="{y}" '
                f'width="{_CELL - 2}" height="{_CELL - 2}" rx="3"/>'
            )
            if (row, col) in last:
                parts.append(
                    f'<circle class="bk-last" cx="{x + _CELL / 2 - 1}" cy="{y + _CELL / 2 - 1}" '
                    f'r="3.5"/>'
                )
    for color, (row, col) in _CORNERS.items():
        if grid[row][col] is None:
            x, y = _MARGIN + col * _CELL + 4, _MARGIN + row * _CELL + 4
            parts.append(
                f'<rect class="bk-corner" style="stroke: var(--bk-{color})" x="{x}" y="{y}" '
                f'width="{_CELL - 8}" height="{_CELL - 8}" rx="2"/>'
            )
    if waiting:
        for row, col in waiting.anchors:
            cx, cy = _MARGIN + col * _CELL + _CELL / 2, _MARGIN + row * _CELL + _CELL / 2
            parts.append(
                f'<circle class="bk-anchor bk-{waiting.color}" cx="{cx}" cy="{cy}" r="3"/>'
            )
    parts.append("</svg>")
    return "".join(parts)


def render_tray(snapshot: GameSnapshot | None) -> str:
    """The piece picker for a person's move, or "" when no person is to move."""
    waiting: HumanTurn | None = snapshot.human_turn if snapshot else None
    if waiting is None:
        return ""
    playable = set(waiting.playable)
    picks = "".join(
        f'<button type="button" class="bk-pick" data-piece="{p.name}" title="{p.name}"'
        f"{'' if p.name in playable else ' disabled'}>"
        f"{render_piece(p, waiting.color, cell=10)}</button>"
        for p in waiting.pieces
    )
    label = Color[waiting.color.upper()].label
    return (
        f'<div class="bk-tray" data-turn="{waiting.turn}" data-color="{waiting.color}">'
        f'<div class="bk-tray-head"><span class="bk-swatch bk-bg-{waiting.color}"></span>'
        f"<b>Your move</b> as {label}"
        f'<span class="bk-clock">{waiting.seconds:g}</span></div>'
        f'<div class="bk-timebar"><div class="bk-timebar-fill bk-bg-{waiting.color}"></div></div>'
        f'<div class="bk-picks">{picks}</div>'
        '<div class="bk-controls"><span class="bk-hand"></span>'
        '<button type="button" data-action="rotate">Rotate (R)</button>'
        '<button type="button" data-action="flip">Flip (F)</button></div>'
        '<div class="bk-msg" role="status"></div>'
        '<details class="bk-help"><summary>Pick a piece, then click or tap the board to place '
        "it.</summary>It must cover one of your corner points (dots) and must not touch your own "
        "pieces along an edge. Rotate with R, a right-click or the button, and flip with F. "
        "On a touch screen, the first tap shows where the piece goes; tap the piece to place it. "
        "If time runs out, Greedy or Tactician moves for you.</details></div>"
    )


def render_piece(piece: PieceView, color: str, cell: int = 9) -> str:
    rows = max(r for r, _ in piece.cells) + 1
    cols = max(c for _, c in piece.cells) + 1
    squares = "".join(
        f'<rect class="bk-{color}" x="{c * cell}" y="{r * cell}" '
        f'width="{cell - 1}" height="{cell - 1}" rx="1.5"/>'
        for r, c in piece.cells
    )
    return (
        f'<svg class="bk-piece" width="{cols * cell}" height="{rows * cell}" '
        f'viewBox="0 0 {cols * cell} {rows * cell}"><title>{piece.name}</title>{squares}</svg>'
    )


def _color_row(view: ColorView, label: str | None = None) -> str:
    pieces = "".join(render_piece(p, view.color) for p in view.remaining)
    if not pieces:
        pieces = '<span class="bk-none">all pieces played</span>'
    state = " (out)" if view.out and view.remaining else ""
    return (
        f'<div class="bk-color-row{" bk-out" if view.out else ""}">'
        f'<div class="bk-color-label"><span class="bk-swatch bk-bg-{view.color}"></span> '
        f"{escape(label or view.label)}{state}<br>{view.squares_left} sq</div>"
        f'<div class="bk-pieces">{pieces}</div></div>'
    )


def render_stopped(snapshot: GameSnapshot) -> str:
    return (
        f'<div class="bk-status">Game stopped after {_plural(snapshot.turn, "turn")}. '
        "Only finished games are recorded.</div>"
    )


def _plural(count: int, noun: str, plural: str | None = None) -> str:
    return f"{count:,} {noun if count == 1 else plural or noun + 's'}"


_KIND_LABELS = {"llm": "LLM", "bot": "bot", "human": "human"}


def _kind_badge(kind: str) -> str:
    return f'<span class="bk-kind">{escape(_KIND_LABELS.get(kind, kind))}</span>'


def _stats_line(player: PlayerView) -> str:
    stats = player.stats
    parts = [f"{_plural(player.squares_left, 'square')} left", _plural(stats.moves, "move")]
    if stats.moves:
        parts.append(f"avg {stats.think_seconds / stats.moves:.1f}s per move")
    if player.kind == "llm":
        parts += [
            _plural(stats.invalid_attempts, "illegal try", "illegal tries"),
            _plural(stats.fallbacks, "random fallback"),
            _plural(stats.tokens, "token"),
        ]
    elif player.kind == "human":
        parts.append(f"{stats.fallbacks} timed out")
    return " · ".join(parts)


def render_players(snapshot: GameSnapshot | None) -> str:
    """One card per player (score, stats and all remaining pieces), plus the shared color."""
    if snapshot is None:
        return '<div class="bk-players"><p class="bk-none">Start a game to see players.</p></div>'
    mover = snapshot.to_move.player if snapshot.to_move else None
    winners = set(snapshot.winners)
    cards = []
    for player in snapshot.players:
        classes = ["bk-player"]
        if player.name == mover and snapshot.event == "thinking":
            classes.append("bk-turn")
        if not player.active and not snapshot.over:
            classes.append("bk-inactive")
        swatches = "".join(
            f'<span class="bk-swatch bk-bg-{c.color}"></span>' for c in player.colors
        )
        trophy = " 🏆" if player.name in winners else ""
        cards.append(
            f'<div class="{" ".join(classes)}">'
            f'<div class="bk-head">{swatches}<span class="bk-name">{escape(player.name)}'
            f"{trophy}</span>"
            f"{_kind_badge(player.kind)}"
            f'<span class="bk-score">{player.score}</span></div>'
            f'<div class="bk-detail">{escape(player.detail)}</div>'
            f'<div class="bk-stats">{_stats_line(player)}</div>'
            + "".join(_color_row(c) for c in player.colors)
            + "</div>"
        )
    if snapshot.shared is not None:
        shared = snapshot.shared
        cards.append(
            '<div class="bk-player"><div class="bk-head">'
            f'<span class="bk-swatch bk-bg-{shared.color}"></span>'
            f'<span class="bk-name">Shared {escape(shared.label)}</span>'
            '<span class="bk-kind">no score</span></div>'
            '<div class="bk-detail">Players take turns moving it; '
            "its score counts for nobody.</div>"
            f"{_color_row(shared)}</div>"
        )
    return f'<div class="bk-players">{"".join(cards)}</div>'


def _log_entry(entry: LogEntry) -> str:
    swatch = f'<span class="bk-swatch bk-bg-{entry.color}"></span>'
    head = f'<span class="bk-num">#{entry.turn}</span> {swatch} '
    if entry.piece is None:
        return f"<li>{head}{entry.color.capitalize()} has no legal move and is out.</li>"
    tag = f'<span class="bk-tag">{escape(entry.fallback)}</span>' if entry.fallback else ""
    body = (
        f"{head}<b>{escape(entry.player)}</b> played <b>{entry.piece}</b> "
        f'<span class="bk-cells">{" ".join(entry.cells)} · {entry.seconds:.1f}s</span>{tag}'
    )
    if entry.reasoning:
        body += f'<div class="bk-reason">{escape(entry.reasoning)}</div>'
    if entry.error:
        body += f'<div class="bk-error">{escape(entry.error)}</div>'
    return f"<li>{body}</li>"


def render_log(snapshot: GameSnapshot | None) -> str:
    """Every turn, newest first."""
    if snapshot is None or not snapshot.log:
        return '<ol class="bk-log"></ol>'
    return '<ol class="bk-log">' + "".join(_log_entry(e) for e in reversed(snapshot.log)) + "</ol>"


def render_status(snapshot: GameSnapshot | None) -> str:
    if snapshot is None:
        return '<div class="bk-status">Choose the players and start a game.</div>'
    if snapshot.over:
        scores = {p.name: p.score for p in snapshot.players}
        names = " and ".join(f"{escape(n)} ({scores[n]})" for n in snapshot.winners)
        verdict = f"Tie: {names}" if len(snapshot.winners) > 1 else f"Winner: {names}"
        summary = f"Game over after {snapshot.turn} turns · {verdict}"
        return f'<div class="bk-status bk-over">{summary}</div>'
    to_move = snapshot.to_move
    assert to_move is not None
    color = f'<span class="bk-swatch bk-bg-{to_move.color}"></span> {to_move.color.capitalize()}'
    if snapshot.human_turn is not None:
        seconds = f"{snapshot.human_turn.seconds:g}"
        return (
            f'<div class="bk-status">Turn {snapshot.turn + 1} · {color} · '
            f"<b>Your move</b>: you have {seconds} seconds.</div>"
        )
    who = escape(to_move.player)
    if to_move.player_kind == "llm":
        who += f" ({escape(to_move.player_detail)})"
    action = "is thinking…" if snapshot.event == "thinking" else "to move"
    return f'<div class="bk-status">Turn {snapshot.turn + 1} · {color} · {who} {action}</div>'


def _when(record: GameRecord) -> str:
    return f"{record.finished_at:%Y-%m-%d %H:%M} UTC"


def render_leaderboard(table: Sequence[Rating]) -> str:
    """ELO ratings, best first."""
    if not table:
        return '<p class="bk-note">No finished games yet. Ratings appear after the first game.</p>'
    rows = "".join(
        f"<tr><td class='bk-num-cell'>{rank}</td>"
        f"<td>{escape(r.identity)} {_kind_badge(r.kind)}</td>"
        f"<td class='bk-num-cell'><b>{r.rating:.0f}</b></td></tr>"
        for rank, r in enumerate(table, 1)
    )
    return (
        '<table class="bk-table bk-ratings"><thead><tr><th class="bk-num-cell">#</th>'
        '<th>Player</th><th class="bk-num-cell">ELO Rating</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def _seat_cell(record: GameRecord, color: str) -> str:
    score = record.color_scores.get(color)
    score_text = f"{score} pts" if score is not None else ""
    player = record.player_of(color)
    if player is None:
        if color == record.shared:
            return f"<td>Shared<span class='bk-sub'>{score_text}, counts for nobody</span></td>"
        return "<td></td>"
    notes = [score_text]
    if player.fallbacks:
        notes.append(f"{_plural(player.fallbacks, 'move')} by stand-ins")
    return (
        f"<td>{escape(player.identity)} {_kind_badge(player.kind)}"
        f"<span class='bk-sub'>{', '.join(notes)}</span></td>"
    )


def _winner_cell(record: GameRecord) -> str:
    lines = []
    for player in record.winners:
        swatches = "".join(f'<span class="bk-swatch bk-bg-{c}"></span>' for c in player.colors)
        colors = " & ".join(c.capitalize() for c in player.colors)
        lines.append(
            f"<div><span class='bk-nowrap'>{swatches} {colors}</span>"
            f"<span class='bk-sub'>{escape(player.identity)}, "
            f"{player.score} pts</span></div>"
        )
    tie = "<span class='bk-sub'>tie</span>" if len(lines) > 1 else ""
    return f"<td>{''.join(lines)}{tie}</td>"


def render_history(records: Sequence[GameRecord], limit: int = 200) -> str:
    """Finished games, newest first."""
    if not records:
        return '<p class="bk-note">No finished games yet.</p>'
    shown = list(reversed(records))[:limit]
    colors = [color_key(c) for c in Color]
    head = "".join(
        f'<th><span class="bk-swatch bk-bg-{c}"></span> {c.capitalize()}</th>' for c in colors
    )
    rows = "".join(
        f"<tr><td class='bk-when'>{_when(r)}<span class='bk-sub'>{len(r.players)} players, "
        f"{len(r.moves)} pieces</span></td>"
        + "".join(_seat_cell(r, c) for c in colors)
        + _winner_cell(r)
        + "</tr>"
        for r in shown
    )
    note = (
        f'<p class="bk-note">Showing the latest {limit} of {len(records)} games.</p>'
        if len(records) > limit
        else ""
    )
    return (
        f'{note}<div class="bk-scroll"><table class="bk-table"><thead><tr><th>Finished</th>'
        f"{head}<th>Winner</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )
