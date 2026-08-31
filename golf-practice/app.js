import * as db from './db.js';
import {
  getTemplate, newSession, computeMetrics, compareSessions,
  PROGRESS_METRICS, fmtDate, fmtTime, fmtDuration, buildSummaryText,
  DEFAULT_LOCATION,
} from './templates.js';
import { renderTrendChart } from './charts.js';

// ---------------------------------------------------------------- state

const state = {
  tab: 'practice',
  session: null,       // active practice session (status 'active'), if any
  editSession: null,   // completed session being edited from History
  editIndex: 0,
  historyId: null,     // open session in History detail view
  locations: [DEFAULT_LOCATION],
  startLocation: '',
  installHintDismissed: false,
};

const $screen = document.getElementById('screen');
let elapsedTimer = null;
let renderToken = 0;

// ---------------------------------------------------------------- utils

function h(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'class') e.className = v;
    else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of children.flat(2)) {
    if (c == null || c === false) continue;
    e.append(c.nodeType ? c : document.createTextNode(c));
  }
  return e;
}

function buzz() {
  if (navigator.vibrate) { try { navigator.vibrate(8); } catch { /* no-op */ } }
}

let toastTimer = null;
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 1800);
}

function confirmSheet({ title, message, confirmLabel = 'Delete', danger = true }) {
  return new Promise((resolve) => {
    const backdrop = document.getElementById('sheet-backdrop');
    const sheet = document.getElementById('sheet');
    const close = (v) => {
      backdrop.hidden = true;
      sheet.hidden = true;
      sheet.replaceChildren();
      resolve(v);
    };
    sheet.replaceChildren(
      h('h3', {}, title),
      h('p', {}, message),
      h('div', { class: 'btn-row' },
        h('button', { class: 'btn btn-secondary', onclick: () => close(false) }, 'Cancel'),
        h('button', { class: `btn ${danger ? 'btn-danger' : 'btn-primary'}`, onclick: () => close(true) }, confirmLabel),
      ),
    );
    backdrop.onclick = () => close(false);
    backdrop.hidden = false;
    sheet.hidden = false;
  });
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { /* no-op */ }
    ta.remove();
    return ok;
  }
}

async function saveSession(session) {
  await db.putSession(session);
}

function elapsedMin(iso) {
  return Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
}

// ---------------------------------------------------------------- render root

async function render() {
  const token = ++renderToken;
  clearInterval(elapsedTimer);
  for (const b of document.querySelectorAll('.tab')) {
    b.classList.toggle('active', b.dataset.tab === state.tab);
  }
  let view;
  if (state.tab === 'practice') {
    view = state.session ? renderSessionFlow(state.session, false) : renderStart();
  } else if (state.tab === 'history') {
    if (state.editSession) view = renderSessionFlow(state.editSession, true);
    else if (state.historyId) view = await renderHistoryDetail(state.historyId);
    else view = await renderHistoryList();
  } else {
    view = await renderProgress();
  }
  if (token !== renderToken) return; // a newer render superseded this one
  $screen.replaceChildren(view);
  window.scrollTo(0, 0);
}

// ---------------------------------------------------------------- practice: start

function renderStart() {
  const t = getTemplate('putting-chipping-v1');
  const root = h('div', {});
  root.append(h('div', { class: 'page-title' }, 'Practice'));

  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  if (!isStandalone && !state.installHintDismissed) {
    root.append(h('div', { class: 'install-hint' },
      h('div', {}, 'Tip: in Safari tap Share, then “Add to Home Screen” to install this as an app that works offline.'),
      h('button', {
        onclick: async (e) => {
          state.installHintDismissed = true;
          await db.setPref('installHintDismissed', true);
          e.target.closest('.install-hint').remove();
        },
      }, 'OK'),
    ));
  }

  const input = h('input', {
    class: 'text-input', type: 'text', placeholder: DEFAULT_LOCATION,
    value: state.startLocation, autocomplete: 'off', enterkeyhint: 'done',
    oninput: (e) => { state.startLocation = e.target.value; },
  });
  const chips = h('div', { class: 'chip-row' },
    state.locations.map((loc) => h('button', {
      class: 'chip' + (loc === state.startLocation ? ' selected' : ''),
      onclick: (e) => {
        state.startLocation = loc;
        input.value = loc;
        for (const c of e.target.parentNode.children) c.classList.remove('selected');
        e.target.classList.add('selected');
        buzz();
      },
    }, loc)),
  );

  root.append(
    h('div', { class: 'card' },
      h('div', { class: 'hero-icon' }, '⛳️'),
      h('h2', {}, t.name),
      h('p', { class: 'sub' }, t.tagline),
      h('ul', { class: 'drill-preview' },
        t.drills.map((d, i) => h('li', {},
          h('span', {}, `${i + 1}. ${d.name}${d.priority ? ' ★' : ''}`),
          h('span', { class: 'mins' }, `${d.minutes} min`),
        )),
      ),
    ),
    h('div', { class: 'card' },
      h('p', { class: 'field-label' }, 'Location (optional)'),
      input,
      chips,
    ),
    h('button', { class: 'btn btn-primary', onclick: startSession }, 'Start Session'),
  );
  return root;
}

async function startSession() {
  const loc = (state.startLocation || '').trim() || DEFAULT_LOCATION;
  const session = newSession('putting-chipping-v1', loc);
  // remember the location, most recent first
  state.locations = [loc, ...state.locations.filter((l) => l !== loc)].slice(0, 12);
  await db.setPref('locations', state.locations);
  await saveSession(session);
  state.session = session;
  buzz();
  render();
}

// ---------------------------------------------------------------- session flow (drills + summary)

function renderSessionFlow(session, editing) {
  const t = getTemplate(session.templateId);
  const idx = editing ? state.editIndex : session.currentDrillIndex;
  if (!editing && idx >= t.drills.length) return renderSummary(session, 'live');
  return renderDrill(session, t, Math.min(idx, t.drills.length - 1), editing);
}

function setIndex(session, editing, idx) {
  if (editing) {
    state.editIndex = idx;
  } else {
    session.currentDrillIndex = idx;
    saveSession(session);
  }
  render();
}

async function exitEditing() {
  await saveSession(state.editSession);
  state.historyId = state.editSession.id;
  state.editSession = null;
  render();
}

function renderDrill(session, t, idx, editing) {
  const drill = t.drills[idx];
  const rec = session.drills[drill.id];
  const refreshers = [];
  const root = h('div', {});

  const touch = () => {
    rec.touched = true;
    saveSession(session);
    for (const r of refreshers) r();
  };

  // --- sticky header: progress + dots
  const elapsedEl = h('span', { class: 'elapsed' });
  const updateElapsed = () => {
    elapsedEl.textContent = editing
      ? `Editing · ${fmtDate(session.startedAt)}`
      : `${elapsedMin(session.startedAt)} min elapsed`;
  };
  updateElapsed();
  if (!editing) elapsedTimer = setInterval(updateElapsed, 30000);

  root.append(h('div', { class: 'drill-header' },
    h('div', { class: 'drill-progress' },
      h('span', { class: 'label' }, `Drill ${idx + 1} of ${t.drills.length}`),
      elapsedEl,
    ),
    h('div', { class: 'dots' },
      t.drills.map((d, i) => {
        const st = session.drills[d.id].status;
        const cls = ['dot', i === idx ? 'current' : '', st === 'complete' ? 'done' : '', st === 'skipped' ? 'skipped' : ''].join(' ').trim();
        return h('button', {
          class: cls,
          'aria-label': `Go to drill ${i + 1}: ${d.name}`,
          onclick: () => setIndex(session, editing, i),
        }, st === 'complete' ? '✓' : String(i + 1));
      }),
    ),
  ));

  // --- title + instructions
  root.append(
    h('div', { class: 'drill-title-row' },
      h('h1', {}, drill.name),
      h('span', { class: 'badge time' }, `≈ ${drill.minutes} min`),
      drill.priority ? h('span', { class: 'badge' }, 'Priority') : null,
      rec.status === 'complete' ? h('span', { class: 'badge', style: 'background: var(--accent); color: var(--accent-ink);' }, '✓ Done') : null,
      rec.status === 'skipped' ? h('span', { class: 'badge time' }, 'Skipped') : null,
    ),
    h('div', { class: 'instructions' }, drill.instructions.map((p) => h('p', {}, p))),
  );

  // --- inputs
  const validationEl = h('div', { class: 'validation-msg' });

  if (drill.kind === 'form') {
    const sumOf = () => (drill.sum ? drill.sum.keys.reduce((a, k) => a + (rec.data[k] || 0), 0) : 0);
    for (const f of drill.fields) {
      if (f.type === 'stepper') {
        root.append(makeStepperCard({
          label: f.label,
          hint: f.hint,
          of: f.of,
          get: () => rec.data[f.key] || 0,
          canInc: () => (rec.data[f.key] || 0) < f.max && (!drill.sum || sumOf() < drill.sum.max),
          set: (v) => { rec.data[f.key] = v; touch(); },
          refreshers,
        }));
      } else if (f.type === 'segment') {
        root.append(makeSegmentCard({
          label: f.label,
          options: f.options,
          get: () => rec.data[f.key],
          set: (v) => { rec.data[f.key] = v; touch(); },
          refreshers,
        }));
      }
    }
    if (drill.sum) {
      const note = h('div', { class: 'count-note' });
      const refreshNote = () => {
        const s = sumOf();
        note.textContent = `${s} of ${drill.sum.max} ${drill.sum.unit} recorded`;
        note.className = 'count-note' + (s === drill.sum.max ? ' full' : '');
      };
      refreshNote();
      refreshers.push(refreshNote);
      root.append(note);
    }
    if (drill.live) {
      const stats = h('div', { class: 'live-stats' });
      const refreshStats = () => {
        stats.replaceChildren(...drill.live(rec.data).map((s) =>
          h('div', { class: 'live-stat' }, h('div', { class: 'v' }, s.v), h('div', { class: 'k' }, s.k)),
        ));
      };
      refreshStats();
      refreshers.push(refreshStats);
      root.append(stats);
    }
  } else if (drill.kind === 'holes') {
    const card = h('div', { class: 'card', style: 'padding: 4px 4px;' });
    rec.data.holes.forEach((hole, i) => {
      const tpBtn = h('button', { class: 'tp-toggle' }, '3-putt');
      const nameEl = h('div', { class: 'hole-name' }, `Hole ${i + 1}`, h('small', {}, 'Par 2'));
      const refreshRow = () => {
        tpBtn.classList.toggle('on', !!hole.threePutt);
        tpBtn.disabled = hole.strokes < 4;
        nameEl.replaceChildren(`Hole ${i + 1}`, h('small', {},
          hole.strokes > 0 && hole.strokes <= 2 ? h('span', { class: 'ud-tag' }, '✓ Up & down') : 'Par 2'));
      };
      tpBtn.addEventListener('click', () => {
        hole.threePutt = !hole.threePutt;
        buzz();
        touch();
      });
      card.append(h('div', { class: 'hole-row' },
        nameEl,
        makeStepper({
          get: () => hole.strokes,
          canInc: () => hole.strokes < 10,
          set: (v) => {
            hole.strokes = v;
            if (hole.strokes < 4) hole.threePutt = false;
            touch();
          },
          display: (v) => (v === 0 ? '–' : String(v)),
          refreshers,
        }),
        tpBtn,
      ));
      refreshers.push(refreshRow);
      refreshRow();
    });
    root.append(card);

    const stats = h('div', { class: 'live-stats' });
    const refreshStats = () => {
      const played = rec.data.holes.filter((x) => x.strokes > 0);
      const total = played.reduce((a, x) => a + x.strokes, 0);
      const vsPar = total - played.length * 2;
      const ud = played.filter((x) => x.strokes <= 2).length;
      stats.replaceChildren(
        h('div', { class: 'live-stat' }, h('div', { class: 'v' }, String(total)), h('div', { class: 'k' }, 'Strokes')),
        h('div', { class: 'live-stat' }, h('div', { class: 'v' }, played.length ? (vsPar > 0 ? `+${vsPar}` : String(vsPar)) : '–'), h('div', { class: 'k' }, 'vs par')),
        h('div', { class: 'live-stat' }, h('div', { class: 'v' }, `${ud}/6`), h('div', { class: 'k' }, 'Up & downs')),
      );
    };
    refreshStats();
    refreshers.push(refreshStats);
    root.append(stats);
  }

  root.append(validationEl);

  // --- actions
  const completeDrill = async () => {
    if (drill.sum && drill.sum.exact) {
      const s = drill.sum.keys.reduce((a, k) => a + (rec.data[k] || 0), 0);
      if (s !== drill.sum.max) {
        validationEl.textContent = `Record all ${drill.sum.max} ${drill.sum.unit} to complete this drill (${s} so far).`;
        return;
      }
    }
    rec.status = 'complete';
    rec.touched = true;
    buzz();
    await saveSession(session);
    advance();
  };

  const skipDrill = async () => {
    rec.status = 'skipped';
    await saveSession(session);
    advance();
  };

  const advance = () => {
    if (editing && idx >= t.drills.length - 1) { exitEditing(); return; }
    setIndex(session, editing, idx + 1);
  };

  root.append(h('div', { class: 'drill-actions' },
    h('button', { class: 'btn btn-primary', onclick: completeDrill },
      rec.status === 'complete' ? 'Save & Continue' : 'Complete Drill  ✓'),
    h('button', { class: 'btn btn-secondary', onclick: skipDrill }, 'Skip Drill'),
    h('div', { class: 'nav-row' },
      h('button', { class: 'btn btn-secondary', disabled: idx === 0 ? '' : null, onclick: () => setIndex(session, editing, idx - 1) }, '‹ Previous'),
      h('button', { class: 'btn btn-secondary', onclick: advance },
        idx >= t.drills.length - 1 ? (editing ? 'Done' : 'Summary ›') : 'Next ›'),
    ),
    editing
      ? h('button', { class: 'btn btn-ghost', onclick: exitEditing }, 'Done editing')
      : h('button', { class: 'btn btn-ghost', style: 'color: var(--danger);', onclick: () => discardSession(session) }, 'Discard session…'),
  ));

  return root;
}

async function discardSession(session) {
  const ok = await confirmSheet({
    title: 'Discard this session?',
    message: 'All results recorded in this session will be deleted. This cannot be undone.',
    confirmLabel: 'Discard',
  });
  if (!ok) return;
  await db.deleteSession(session.id);
  state.session = null;
  render();
}

// ---------------------------------------------------------------- steppers & segments

function makeStepper({ get, set, canInc, display, refreshers }) {
  const val = h('div', { class: 'step-val' });
  const dec = h('button', { class: 'step-btn', 'aria-label': 'Decrease' }, '−');
  const inc = h('button', { class: 'step-btn', 'aria-label': 'Increase' }, '+');
  const refresh = () => {
    const v = get();
    val.textContent = display ? display(v) : String(v);
    dec.disabled = v <= 0;
    inc.disabled = !canInc();
  };
  const change = (delta) => {
    const v = get();
    if (delta > 0 && !canInc()) return;
    if (delta < 0 && v <= 0) return;
    set(v + delta);
    buzz();
    val.classList.remove('bump');
    void val.offsetWidth;
    val.classList.add('bump');
  };
  // tap + press-and-hold repeat
  for (const [btn, delta] of [[dec, -1], [inc, +1]]) {
    let holdT = null, repT = null, held = false;
    btn.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      held = false;
      change(delta);
      holdT = setTimeout(() => {
        held = true;
        repT = setInterval(() => change(delta), 130);
      }, 500);
    });
    const stop = () => { clearTimeout(holdT); clearInterval(repT); };
    btn.addEventListener('pointerup', stop);
    btn.addEventListener('pointercancel', stop);
    btn.addEventListener('pointerleave', stop);
    btn.addEventListener('click', (e) => { if (held) e.preventDefault(); });
    btn.addEventListener('contextmenu', (e) => e.preventDefault());
  }
  refreshers.push(refresh);
  refresh();
  return h('div', { class: 'stepper' }, dec, val, inc);
}

function makeStepperCard({ label, hint, of, get, set, canInc, refreshers }) {
  const wrappedGet = get;
  const stepperEl = makeStepper({
    get: wrappedGet,
    set,
    canInc,
    display: (v) => String(v),
    refreshers,
  });
  if (of) {
    const valEl = stepperEl.querySelector('.step-val');
    const origRefresh = refreshers[refreshers.length - 1];
    refreshers[refreshers.length - 1] = () => {
      origRefresh();
      valEl.replaceChildren(String(wrappedGet()), h('span', { class: 'of' }, ` /${of}`));
    };
    refreshers[refreshers.length - 1]();
  }
  return h('div', { class: 'card stepper-card' },
    h('div', { class: 'info' }, h('div', { class: 'name' }, label), hint ? h('div', { class: 'hint' }, hint) : null),
    stepperEl,
  );
}

function makeSegmentCard({ label, options, get, set, refreshers }) {
  const grid = h('div', { class: 'seg-grid' + (options.length % 3 === 0 ? ' cols-3' : '') });
  const refresh = () => {
    for (const b of grid.children) b.classList.toggle('selected', b.dataset.v === get());
  };
  for (const opt of options) {
    grid.append(h('button', {
      class: 'seg-btn', 'data-v': opt,
      onclick: () => { set(get() === opt ? null : opt); buzz(); },
    }, opt));
  }
  refreshers.push(refresh);
  refresh();
  return h('div', { class: 'card' }, h('p', { class: 'field-label' }, label), grid);
}

// ---------------------------------------------------------------- summary

function summaryRows(rows) {
  return h('dl', { class: 'summary-rows' },
    rows.filter(Boolean).map(([k, v]) => h('div', { class: 'summary-row' },
      h('dt', {}, k),
      h('dd', {}, v == null ? h('span', { class: 'skip' }, '—') : String(v)),
    )),
  );
}

function sectionCard(title, drillRec, rows) {
  if (!drillRec || (drillRec.status !== 'complete' && !drillRec.touched)) {
    return h('div', { class: 'card summary-section' },
      h('h3', {}, title),
      h('p', { class: 'sub', style: 'margin:0;' }, drillRec && drillRec.status === 'skipped' ? 'Skipped' : 'Not recorded'),
    );
  }
  return h('div', { class: 'card summary-section' }, h('h3', {}, title), summaryRows(rows));
}

function buildSummaryCards(session, mode) {
  const m = computeMetrics(session);
  const p = (x) => (x == null ? null : `${x}%`);
  const cards = [];

  cards.push(h('div', { class: 'card summary-section' },
    h('h3', {}, mode === 'live' ? 'Session' : session.location || DEFAULT_LOCATION),
    summaryRows([
      ['Location', session.location || DEFAULT_LOCATION],
      ['Date', `${fmtDate(session.startedAt)} · ${fmtTime(session.startedAt)}`],
      ['Duration', mode === 'live' ? `${elapsedMin(session.startedAt)} min so far` : fmtDuration(session.durationMin)],
    ]),
  ));

  cards.push(sectionCard('Lag putting', session.drills.lag, [
    ['Score', m.lagScore == null ? null : `${m.lagScore}/36 · ${m.lagPct}%`],
    ['Outside 3 ft', m.lagOutside3 == null ? null : `${m.lagOutside3}/18`],
    ['Inside 3 ft', p(m.lagInside3Pct)],
    ['Three-putts', m.lagThreePutts == null ? null : `${m.lagThreePutts} · ${m.lagThreePuttPct}%`],
    ['Miss tendency', m.lagMiss],
  ]));

  cards.push(sectionCard('Short putts', session.drills.short, [
    ['4 ft', m.makes4 == null ? null : `${m.makes4}/10 · ${m.make4Pct}%`],
    ['5 ft', m.makes5 == null ? null : `${m.makes5}/10 · ${m.make5Pct}%`],
    ['6 ft', m.makes6 == null ? null : `${m.makes6}/10 · ${m.make6Pct}%`],
    ['Combined', p(m.shortCombinedPct)],
  ]));

  cards.push(sectionCard('Start line', session.drills.gate, [
    ['Through gate', m.gateOK == null ? null : `${m.gateOK}/20 · ${m.gatePct}%`],
    ['Missed left', m.gateLeft == null ? null : `${m.gateLeft} · ${m.gateLeftPct}%`],
    ['Missed right', m.gateRight == null ? null : `${m.gateRight} · ${m.gateRightPct}%`],
  ]));

  cards.push(sectionCard('Chipping', session.drills.chip, [
    ['Inside 3 ft', m.chipInside3 == null ? null : `${m.chipInside3}/10 · ${m.chipInside3Pct}%`],
    ['3–6 ft', m.chip3to6 == null ? null : `${m.chip3to6}/10`],
    ['Outside 6 ft', m.chipOutside6 == null ? null : `${m.chipOutside6}/10 · ${m.chipOutside6Pct}%`],
    ['Inside 6 ft', p(m.chipInside6Pct)],
    ['Typical miss', m.chipMiss],
  ]));

  cards.push(sectionCard('Up-and-down game', session.drills.updown, [
    ['Total strokes', m.udTotal == null ? null : `${m.udTotal} (${m.udVsPar > 0 ? '+' : ''}${m.udVsPar} vs par 12)`],
    ['Up-and-downs', m.udUpDowns == null ? null : `${m.udUpDowns}/6 · ${m.udPct}%`],
    ['Three-putts', m.udThreePutts],
  ]));

  return cards;
}

async function buildComparisonCard(session) {
  const all = await db.getAllSessions();
  const prev = all.find((s) => s.status === 'complete' && s.id !== session.id && s.startedAt < session.startedAt);
  if (!prev) return null;
  const rows = compareSessions(session, prev);
  if (!rows.length) return null;
  const verdictText = { better: 'Better than last session', worse: 'Worse than last session', same: 'No meaningful change' };
  return h('div', { class: 'card summary-section' },
    h('h3', {}, 'Compared with last session'),
    h('div', {}, rows.map((r) => h('div', { class: 'compare-row' },
      h('span', {}, r.label, ' ', h('span', { style: 'color: var(--muted); font-size: 13px;' }, `${r.prev}% → ${r.cur}%`)),
      h('span', { class: `compare-verdict ${r.verdict}` }, verdictText[r.verdict]),
    ))),
  );
}

let noteSaveTimer = null;

function renderSummary(session, mode) {
  const root = h('div', {});
  root.append(
    h('div', { class: 'drill-header' },
      h('div', { class: 'drill-progress' },
        h('span', { class: 'label' }, 'Session Summary'),
        h('button', { class: 'back-btn', onclick: () => setIndex(session, false, getTemplate(session.templateId).drills.length - 1) }, '‹ Back to drills'),
      ),
    ),
  );

  const cardsHolder = h('div', {});
  cardsHolder.append(...buildSummaryCards(session, mode));
  root.append(cardsHolder);

  buildComparisonCard(session).then((card) => { if (card) root.insertBefore(card, noteCard); });

  const noteInput = h('textarea', {
    class: 'text-input', placeholder: 'e.g. 6-foot putts, downhill chips…',
    oninput: (e) => {
      session.hardestNote = e.target.value;
      clearTimeout(noteSaveTimer);
      noteSaveTimer = setTimeout(() => saveSession(session), 250);
    },
  });
  noteInput.value = session.hardestNote || '';
  const noteCard = h('div', { class: 'card summary-section' },
    h('h3', {}, 'What felt hardest?'),
    noteInput,
  );
  root.append(noteCard);

  const copyBtn = h('button', {
    class: 'btn btn-secondary',
    onclick: async () => {
      clearTimeout(noteSaveTimer);
      await saveSession(session);
      const ok = await copyText(buildSummaryText(session));
      toast(ok ? 'Copied — paste into ChatGPT' : 'Copy failed');
      buzz();
    },
  }, '📋  Copy for ChatGPT');

  const actions = h('div', { class: 'drill-actions' },
    h('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        clearTimeout(noteSaveTimer);
        session.status = 'complete';
        session.completedAt = new Date().toISOString();
        session.durationMin = Math.min(elapsedMin(session.startedAt), 24 * 60);
        await saveSession(session);
        state.session = null;
        buzz();
        toast('Session saved ✓');
        render();
      },
    }, 'Finish Session  ✓'),
    copyBtn,
  );
  if (navigator.share) {
    actions.append(h('button', {
      class: 'btn btn-secondary',
      onclick: async () => {
        clearTimeout(noteSaveTimer);
        await saveSession(session);
        try { await navigator.share({ text: buildSummaryText(session) }); } catch { /* cancelled */ }
      },
    }, 'Share…'));
  }
  actions.append(h('button', { class: 'btn btn-ghost', style: 'color: var(--danger);', onclick: () => discardSession(session) }, 'Discard session…'));
  root.append(actions);
  return root;
}

// ---------------------------------------------------------------- history

async function renderHistoryList() {
  const root = h('div', {});
  root.append(h('div', { class: 'page-title' }, 'History'));
  const all = (await db.getAllSessions()).filter((s) => s.status === 'complete');
  if (!all.length) {
    root.append(h('div', { class: 'empty-state' },
      h('div', { class: 'big' }, '🏌️'),
      h('div', {}, 'No sessions yet.'), h('div', {}, 'Finish a practice session and it will show up here.'),
    ));
    return root;
  }
  for (const s of all) {
    const m = computeMetrics(s);
    const pills = [];
    if (m.lagScore != null) pills.push(h('div', { class: 'stat-pill' }, h('span', {}, 'Lag '), `${m.lagScore}/36`));
    if (m.shortCombinedPct != null) pills.push(h('div', { class: 'stat-pill' }, h('span', {}, 'Short putts '), `${m.shortCombinedPct}%`));
    if (m.udPct != null) pills.push(h('div', { class: 'stat-pill' }, h('span', {}, 'Up & down '), `${m.udPct}%`));
    if (!pills.length) pills.push(h('div', { class: 'stat-pill' }, h('span', {}, 'No results recorded')));
    root.append(h('button', {
      class: 'card session-card',
      onclick: () => { state.historyId = s.id; render(); },
    },
      h('div', { class: 'top' },
        h('span', { class: 'date' }, fmtDate(s.startedAt)),
        h('span', { class: 'loc' }, s.location || DEFAULT_LOCATION),
      ),
      h('div', { class: 'stats' }, pills),
    ));
  }
  return root;
}

async function renderHistoryDetail(id) {
  const session = await db.getSession(id);
  if (!session) { state.historyId = null; return renderHistoryList(); }
  const root = h('div', {});
  root.append(h('button', { class: 'back-btn', onclick: () => { state.historyId = null; render(); } }, '‹ History'));
  root.append(h('div', { class: 'page-title' }, fmtDate(session.startedAt)));

  root.append(...buildSummaryCards(session, 'detail'));
  const cmp = await buildComparisonCard(session);
  if (cmp) root.append(cmp);

  if (session.hardestNote) {
    root.append(h('div', { class: 'card summary-section' },
      h('h3', {}, 'What felt hardest?'),
      h('p', { style: 'margin:0; color: var(--ink-2);' }, session.hardestNote),
    ));
  }

  const actions = h('div', { class: 'drill-actions' },
    h('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        const ok = await copyText(buildSummaryText(session));
        toast(ok ? 'Copied — paste into ChatGPT' : 'Copy failed');
      },
    }, '📋  Copy for ChatGPT'),
    h('button', {
      class: 'btn btn-secondary',
      onclick: () => { state.editSession = session; state.editIndex = 0; render(); },
    }, 'Edit Results'),
  );
  if (navigator.share) {
    actions.append(h('button', {
      class: 'btn btn-secondary',
      onclick: async () => { try { await navigator.share({ text: buildSummaryText(session) }); } catch { /* cancelled */ } },
    }, 'Share…'));
  }
  actions.append(h('button', {
    class: 'btn btn-danger',
    onclick: async () => {
      const ok = await confirmSheet({
        title: 'Delete this session?',
        message: `${fmtDate(session.startedAt)} at ${session.location || DEFAULT_LOCATION} will be permanently deleted.`,
      });
      if (!ok) return;
      await db.deleteSession(session.id);
      state.historyId = null;
      toast('Session deleted');
      render();
    },
  }, 'Delete Session'));
  root.append(actions);
  return root;
}

// ---------------------------------------------------------------- progress

async function renderProgress() {
  const root = h('div', {});
  root.append(h('div', { class: 'page-title' }, 'Progress'));

  const completed = (await db.getAllSessions())
    .filter((s) => s.status === 'complete')
    .sort((a, b) => (a.startedAt < b.startedAt ? -1 : 1));

  if (!completed.length) {
    root.append(h('div', { class: 'empty-state' },
      h('div', { class: 'big' }, '📈'),
      h('div', {}, 'No data yet.'), h('div', {}, 'Trends appear once you finish a session.'),
    ));
    return root;
  }

  const recent = completed.slice(-10);
  const metricsBySession = recent.map((s) => ({
    label: new Date(s.startedAt).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' }),
    m: computeMetrics(s),
  }));

  root.append(h('p', { class: 'sub', style: 'margin: -6px 2px 14px; color: var(--muted); font-size: 14px;' },
    recent.length === 1 ? 'Current baseline from your first session.' : `Last ${recent.length} sessions.`));

  let any = false;
  for (const metric of PROGRESS_METRICS) {
    const points = metricsBySession
      .filter((x) => x.m[metric.key] != null)
      .map((x) => ({ label: x.label, value: x.m[metric.key] }));
    if (!points.length) continue;
    any = true;

    const latest = points[points.length - 1].value;
    const head = h('div', { class: 'head' },
      h('span', { class: 'name' }, metric.label),
      h('span', { class: 'latest' }, `${latest}%`),
    );
    if (points.length > 1) {
      const prev = points[points.length - 2].value;
      const delta = latest - prev;
      const improved = delta === 0 ? null : (delta > 0) === metric.higherBetter;
      head.lastChild.append(h('span', {
        class: 'delta ' + (delta === 0 ? 'flat' : improved ? 'up' : 'down'),
      }, delta === 0 ? '·' : `${delta > 0 ? '▲' : '▼'} ${Math.abs(delta)}`));
    }

    const card = h('div', { class: 'card metric-card' }, head);
    if (points.length === 1) {
      card.append(h('div', { class: 'baseline-note' }, 'Baseline — a trend line appears after your next session.'));
    } else {
      renderTrendChart(card, points, { label: metric.label });
    }
    root.append(card);
  }

  if (!any) {
    root.append(h('div', { class: 'empty-state' }, h('div', {}, 'No recorded drill results yet.')));
  }
  return root;
}

// ---------------------------------------------------------------- init

for (const b of document.querySelectorAll('.tab')) {
  b.addEventListener('click', () => {
    const tab = b.dataset.tab;
    if (state.tab === tab && tab === 'history') { state.historyId = null; state.editSession = null; }
    state.tab = tab;
    render();
  });
}

async function init() {
  db.requestPersistence();
  state.locations = await db.getPref('locations', [DEFAULT_LOCATION]);
  state.installHintDismissed = await db.getPref('installHintDismissed', false);
  state.session = await db.getActiveSession();
  state.startLocation = state.locations[0] || DEFAULT_LOCATION;
  render();
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

init();
