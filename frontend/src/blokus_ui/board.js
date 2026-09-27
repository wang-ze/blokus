// Interactive layer for the Blokus board. Gradio's gr.HTML runs this once, as `js_on_load`,
// with `element` (the component's root), `props` (props.value is the value Python set),
// `server` (Python functions exposed by the component) and `watch` (a callback after the
// template re-renders for a changed prop).
//
// props.value is {board, tray, token, turn}. `turn` is the snapshot's HumanTurn while this
// browser's player is to move, and null otherwise. Moves go to Python via server.submit_move,
// and the engine checks them there. The legal-placement lookup here only gives instant feedback.

const SVG_NS = 'http://www.w3.org/2000/svg';
const COLUMNS = 'ABCDEFGHIJKLMNOPQRST';
const LOW_SECONDS = 5;

const state = {
  key: null, // "<token>/<turn number>" of the turn being played, or null
  turn: null,
  token: null,
  legal: new Set(),
  shapes: new Map(), // piece name -> [[row, col], ...] in its canonical orientation
  piece: null,
  cells: null, // the selected piece in its current orientation
  hover: null, // [row, col] under the pointer
  armed: null, // on touch screens, the legal placement shown by the first tap
  deadline: 0,
  timer: null,
  done: false, // the move was sent, or time ran out
  pointer: 'mouse',
};

function normalize(cells) {
  const top = Math.min(...cells.map(([r]) => r));
  const left = Math.min(...cells.map(([, c]) => c));
  return cells
    .map(([r, c]) => [r - top, c - left])
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}

const rotate = (cells) => normalize(cells.map(([r, c]) => [c, -r])); // clockwise
const flip = (cells) => normalize(cells.map(([r, c]) => [r, -c])); // mirror left to right
const distance = (a, b) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2;
const cellName = ([r, c]) => COLUMNS[c] + (r + 1);

// The cell of the piece that sits under the pointer: the one nearest its middle.
function handle(cells) {
  const middle = [
    Math.max(...cells.map(([r]) => r)) / 2,
    Math.max(...cells.map(([, c]) => c)) / 2,
  ];
  return cells.reduce((best, cell) => (distance(cell, middle) < distance(best, middle) ? cell : best));
}

const board = () => element.querySelector('svg.bk-board');
const active = () => state.turn !== null && !state.done;

function geometry(svg) {
  return { margin: +svg.dataset.margin, cell: +svg.dataset.cell, size: +svg.dataset.size };
}

// Same format as placement_key() in snapshot.py: "<piece>:<ascending cell indices>".
function keyOf(cells, size) {
  if (cells.some(([r, c]) => r < 0 || r >= size || c < 0 || c >= size)) return null;
  const indices = cells.map(([r, c]) => r * size + c).sort((a, b) => a - b);
  return `${state.piece}:${indices.join(',')}`;
}

// Where the selected piece goes for the cell under the pointer. If centering it there is not
// legal, try each of its other cells under the pointer, so it snaps into a legal spot nearby.
function placementFor([row, col], size) {
  const cells = state.cells;
  const center = handle(cells);
  const at = ([pr, pc]) => cells.map(([r, c]) => [r - pr + row, c - pc + col]);
  const order = [center, ...cells.filter((cell) => cell !== center).sort(
    (a, b) => distance(a, center) - distance(b, center),
  )];
  for (const cell of order) {
    const placed = at(cell);
    const key = keyOf(placed, size);
    if (key !== null && state.legal.has(key)) return { cells: placed, key, legal: true };
  }
  const placed = at(center);
  return { cells: placed, key: keyOf(placed, size), legal: false };
}

function cellAt(svg, event) {
  const matrix = svg.getScreenCTM();
  if (!matrix) return null;
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
  const { margin, cell, size } = geometry(svg);
  const row = Math.floor((point.y - margin) / cell);
  const col = Math.floor((point.x - margin) / cell);
  return row >= 0 && row < size && col >= 0 && col < size ? [row, col] : null;
}

function say(text, isError = false) {
  const message = element.querySelector('.bk-msg');
  if (!message) return;
  message.textContent = text;
  message.classList.toggle('bk-error', isError);
}

function drawPreview() {
  const svg = board();
  if (!svg) return;
  let group = svg.querySelector('g.bk-preview');
  if (!active() || !state.cells || !(state.armed || state.hover)) {
    group?.remove();
    return;
  }
  const { margin, cell, size } = geometry(svg);
  const placement = state.armed || placementFor(state.hover, size);
  if (!group) {
    group = document.createElementNS(SVG_NS, 'g');
    svg.appendChild(group);
  }
  group.setAttribute('class', `bk-preview ${placement.legal ? 'bk-ok' : 'bk-bad'}`);
  group.replaceChildren(
    ...placement.cells
      .filter(([r, c]) => r >= 0 && r < size && c >= 0 && c < size)
      .map(([r, c]) => {
        const rect = document.createElementNS(SVG_NS, 'rect');
        rect.setAttribute('x', margin + c * cell + 1);
        rect.setAttribute('y', margin + r * cell + 1);
        rect.setAttribute('width', cell - 2);
        rect.setAttribute('height', cell - 2);
        rect.setAttribute('rx', 3);
        if (placement.legal) rect.setAttribute('class', `bk-${state.turn.color}`);
        return rect;
      }),
  );
}

function drawHand() {
  const hand = element.querySelector('.bk-hand');
  if (!hand) return;
  if (!state.turn || !state.cells) {
    hand.replaceChildren();
    return;
  }
  const unit = 10;
  const rows = Math.max(...state.cells.map(([r]) => r)) + 1;
  const cols = Math.max(...state.cells.map(([, c]) => c)) + 1;
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('width', cols * unit);
  svg.setAttribute('height', rows * unit);
  svg.setAttribute('aria-label', `${state.piece} as it will be placed`);
  for (const [r, c] of state.cells) {
    const rect = document.createElementNS(SVG_NS, 'rect');
    rect.setAttribute('x', c * unit);
    rect.setAttribute('y', r * unit);
    rect.setAttribute('width', unit - 1);
    rect.setAttribute('height', unit - 1);
    rect.setAttribute('rx', 1.5);
    rect.setAttribute('class', `bk-${state.turn.color}`);
    svg.appendChild(rect);
  }
  hand.replaceChildren(svg);
}

function refreshTray() {
  for (const button of element.querySelectorAll('.bk-pick')) {
    button.classList.toggle('bk-selected', button.dataset.piece === state.piece);
  }
  drawHand();
}

function select(name) {
  if (!active() || !state.turn.playable.includes(name)) return;
  if (name !== state.piece) {
    state.piece = name;
    state.cells = state.shapes.get(name);
  }
  state.armed = null;
  refreshTray();
  drawPreview();
}

function transform(kind) {
  if (!active() || !state.cells) return;
  state.cells = kind === 'flip' ? flip(state.cells) : rotate(state.cells);
  state.armed = null;
  refreshTray();
  drawPreview();
}

function stopClock() {
  clearInterval(state.timer);
  state.timer = null;
}

function tick() {
  if (!state.turn) return;
  const left = Math.max(0, state.deadline - performance.now());
  const clock = element.querySelector('.bk-clock');
  const fill = element.querySelector('.bk-timebar-fill');
  if (clock) {
    clock.textContent = String(Math.ceil(left / 1000));
    clock.classList.toggle('bk-low', left < LOW_SECONDS * 1000);
  }
  if (fill) fill.style.width = `${(100 * left) / (state.turn.seconds * 1000)}%`;
  if (left > 0) return;
  stopClock();
  if (!state.done) {
    state.done = true;
    say("Time's up: a bot is moving for you.", true);
    drawPreview();
  }
}

async function place(placement) {
  if (!placement.legal) {
    say("That piece doesn't fit there.", true);
    return;
  }
  state.done = true;
  say('Placing…');
  let result;
  try {
    result = await server.submit_move({
      token: state.token,
      turn: state.turn.turn,
      piece: state.piece,
      cells: placement.cells.map(cellName),
    });
  } catch (error) {
    result = { ok: false, error: 'Could not reach the server. Try again.' };
  }
  if (result && result.ok) {
    stopClock();
    say('Placed.');
    return;
  }
  const timeLeft = state.deadline - performance.now() > 0;
  state.done = !timeLeft;
  say((result && result.error) || 'The move was not accepted.', true);
}

// Called after every value update from Python.
function sync() {
  const value = props.value || {};
  const turn = value.turn || null;
  const key = turn && value.token ? `${value.token}/${turn.turn}` : null;
  if (key !== state.key) {
    stopClock();
    Object.assign(state, { key, turn: key ? turn : null, token: value.token || null });
    Object.assign(state, { armed: null, done: false, hover: null });
    if (state.turn) {
      state.legal = new Set(turn.legal);
      state.shapes = new Map(turn.pieces.map((piece) => [piece.name, piece.cells]));
      // Keep the last piece if it can still be played, else pick the biggest playable one.
      if (!turn.playable.includes(state.piece)) state.piece = turn.playable.at(-1);
      state.cells = state.shapes.get(state.piece);
      state.deadline = performance.now() + turn.seconds * 1000;
      state.timer = setInterval(tick, 100);
      tick();
    }
  }
  refreshTray();
  drawPreview();
}

element.addEventListener('pointerdown', (event) => {
  state.pointer = event.pointerType || 'mouse';
});

element.addEventListener('pointermove', (event) => {
  if (!active() || event.pointerType !== 'mouse') return;
  const svg = event.target.closest && event.target.closest('svg.bk-board');
  const cell = svg ? cellAt(svg, event) : null;
  if (String(cell) === String(state.hover)) return;
  state.hover = cell;
  drawPreview();
});

element.addEventListener('pointerleave', () => {
  state.hover = null;
  drawPreview();
});

element.addEventListener('click', (event) => {
  const pick = event.target.closest('[data-piece]');
  if (pick) {
    select(pick.dataset.piece);
    return;
  }
  const action = event.target.closest('[data-action]');
  if (action) {
    transform(action.dataset.action);
    return;
  }
  const svg = event.target.closest('svg.bk-board');
  if (!svg || !active() || !state.cells) return;
  const cell = cellAt(svg, event);
  if (!cell) return;
  if (state.pointer === 'mouse') {
    state.hover = cell;
    drawPreview();
    place(placementFor(cell, geometry(svg).size));
    return;
  }
  // Touch and pen have no hover: the first tap shows where the piece would go, and a tap
  // anywhere on that preview places it.
  const armed = state.armed;
  if (armed && armed.cells.some(([r, c]) => r === cell[0] && c === cell[1])) {
    place(armed);
    return;
  }
  const placement = placementFor(cell, geometry(svg).size);
  state.armed = placement.legal ? placement : null;
  state.hover = cell;
  drawPreview();
  say(placement.legal ? 'Tap the piece again to place it.' : "That piece doesn't fit there.",
    !placement.legal);
});

element.addEventListener('contextmenu', (event) => {
  if (!active() || !event.target.closest('svg.bk-board')) return;
  event.preventDefault();
  transform('rotate');
});

// One keyboard handler per page, replaced if the component is ever mounted again.
document.removeEventListener('keydown', window.__blokusKeys);
window.__blokusKeys = (event) => {
  if (!active() || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.target.closest && event.target.closest('input, textarea, select, [contenteditable]')) {
    return;
  }
  const key = event.key.toLowerCase();
  if (key !== 'r' && key !== 'f') return;
  event.preventDefault();
  transform(key === 'f' ? 'flip' : 'rotate');
};
document.addEventListener('keydown', window.__blokusKeys);

watch('value', sync);
sync();
