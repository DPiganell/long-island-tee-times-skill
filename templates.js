// Practice template registry.
//
// A template is pure data: an ordered list of drills, each declaring its input
// fields, optional sum constraints, and live derived stats. The UI renders any
// template from this shape, so adding a new practice type (putting-only, wedge
// distance control, driving range, ...) means adding an entry here — no app
// rewrites.
//
// Drill kinds:
//   'info'  — instructions only, no recorded score
//   'form'  — a list of fields: {type:'stepper'|'segment'}
//   'holes' — n score-entry rows (strokes + optional three-putt flag)

export const DEFAULT_LOCATION = 'Spy Ring';

export function pct(n, den) {
  if (n == null || !den) return null;
  return Math.round((n / den) * 100);
}

const num = (v) => (typeof v === 'number' ? v : 0);

export const TEMPLATES = {
  'putting-chipping-v1': {
    id: 'putting-chipping-v1',
    name: 'Putting + Chipping',
    tagline: 'Target: about 70–75 minutes · 6 drills',
    drills: [
      {
        id: 'speed',
        name: 'Speed Calibration',
        minutes: 5,
        kind: 'info',
        instructions: [
          'Hit putts toward the fringe — not a hole — from about 20, 30, and 40 feet.',
          'The only objective is to learn the speed of the greens today. No score.',
        ],
      },
      {
        id: 'lag',
        name: 'Lag Putting',
        minutes: 15,
        priority: true,
        kind: 'form',
        instructions: [
          'Hit 3 balls from 20 ft, 3 from 30 ft, 3 from 40 ft. Repeat the sequence twice — 18 first putts total.',
          'Score each first putt: inside 18 in = 2 pts, 18 in–3 ft = 1 pt, outside 3 ft = 0 pts.',
          'Finish every ball into the hole so three-putts get counted.',
        ],
        fields: [
          { key: 'lagScore', label: 'Lag score', hint: 'Points out of 36', type: 'stepper', min: 0, max: 36, of: 36 },
          { key: 'outside3', label: 'Outside 3 ft', hint: 'First putts out of 18', type: 'stepper', min: 0, max: 18, of: 18 },
          { key: 'threePutts', label: 'Three-putts', hint: 'Total for the drill', type: 'stepper', min: 0, max: 18 },
          { key: 'missTendency', label: 'Miss tendency', type: 'segment', options: ['Short', 'Long', 'Both', 'No clear tendency'] },
        ],
        live: (d) => [
          { k: 'Lag score', v: fmtPct(pct(num(d.lagScore), 36)) },
          { k: 'Inside 3 ft', v: fmtPct(pct(18 - num(d.outside3), 18)) },
          { k: '3-putt rate', v: fmtPct(pct(num(d.threePutts), 18)) },
        ],
      },
      {
        id: 'short',
        name: 'Short Putts',
        minutes: 15,
        kind: 'form',
        instructions: [
          'Hit 10 putts from 4 ft, 10 from 5 ft, and 10 from 6 ft.',
          'Change your location around the hole as you go so the break varies.',
        ],
        fields: [
          { key: 'makes4', label: '4-foot makes', hint: 'Out of 10', type: 'stepper', min: 0, max: 10, of: 10 },
          { key: 'makes5', label: '5-foot makes', hint: 'Out of 10', type: 'stepper', min: 0, max: 10, of: 10 },
          { key: 'makes6', label: '6-foot makes', hint: 'Out of 10', type: 'stepper', min: 0, max: 10, of: 10 },
        ],
        live: (d) => [
          { k: '4 ft', v: fmtPct(pct(num(d.makes4), 10)) },
          { k: '5 ft', v: fmtPct(pct(num(d.makes5), 10)) },
          { k: '6 ft', v: fmtPct(pct(num(d.makes6), 10)) },
          { k: 'Combined', v: fmtPct(pct(num(d.makes4) + num(d.makes5) + num(d.makes6), 30)) },
        ],
      },
      {
        id: 'gate',
        name: 'Start-Line Gate',
        minutes: 10,
        kind: 'form',
        instructions: [
          'Find a relatively straight 5-foot putt.',
          'Place two tees 12–18 inches in front of the ball, a gate slightly wider than the ball.',
          'Hit 20 putts. What matters is starting the ball through the gate, not holing every putt.',
        ],
        fields: [
          { key: 'gateOK', label: 'Through the gate', hint: 'Out of 20', type: 'stepper', min: 0, max: 20, of: 20 },
          { key: 'missLeft', label: 'Missed left', type: 'stepper', min: 0, max: 20 },
          { key: 'missRight', label: 'Missed right', type: 'stepper', min: 0, max: 20 },
        ],
        sum: { keys: ['gateOK', 'missLeft', 'missRight'], max: 20, unit: 'putts' },
        live: (d) => [
          { k: 'Gate', v: fmtPct(pct(num(d.gateOK), 20)) },
          { k: 'Left', v: fmtPct(pct(num(d.missLeft), 20)) },
          { k: 'Right', v: fmtPct(pct(num(d.missRight), 20)) },
        ],
      },
      {
        id: 'chip',
        name: 'Chipping Proximity',
        minutes: 10,
        kind: 'form',
        instructions: [
          'Hit 10 ordinary greenside chips from about 10–20 yards total.',
          'Change the lie or location every few balls — don’t repeat the exact same shot.',
        ],
        fields: [
          { key: 'inside3', label: 'Inside 3 ft', type: 'stepper', min: 0, max: 10 },
          { key: 'from3to6', label: '3–6 ft', type: 'stepper', min: 0, max: 10 },
          { key: 'outside6', label: 'Outside 6 ft', type: 'stepper', min: 0, max: 10 },
          { key: 'missTendency', label: 'Typical miss', type: 'segment', options: ['Short', 'Long', 'Left', 'Right', 'Mixed', 'No clear tendency'] },
        ],
        sum: { keys: ['inside3', 'from3to6', 'outside6'], max: 10, exact: true, unit: 'chips' },
        live: (d) => [
          { k: 'Inside 3 ft', v: fmtPct(pct(num(d.inside3), 10)) },
          { k: 'Inside 6 ft', v: fmtPct(pct(num(d.inside3) + num(d.from3to6), 10)) },
          { k: 'Outside 6 ft', v: fmtPct(pct(num(d.outside6), 10)) },
        ],
      },
      {
        id: 'updown',
        name: 'Up-and-Down Game',
        minutes: 15,
        kind: 'holes',
        holes: 6,
        par: 2,
        instructions: [
          'Play 6 simulated holes around the green. Each hole: pick a new chipping spot, chip on with one ball, then putt out.',
          'Par is 2 for every hole (chip + one putt). Enter total strokes per hole.',
        ],
      },
    ],
  },
};

export function getTemplate(id) {
  return TEMPLATES[id] || TEMPLATES['putting-chipping-v1'];
}

function fmtPct(p) {
  return p == null ? '–' : p + '%';
}

// ---------- Sessions ----------

export function newSession(templateId, location) {
  const t = getTemplate(templateId);
  const drills = {};
  for (const d of t.drills) {
    drills[d.id] = { status: 'pending', touched: false, data: initDrillData(d) };
  }
  return {
    id: 's-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8),
    templateId: t.id,
    status: 'active',
    startedAt: new Date().toISOString(),
    completedAt: null,
    durationMin: null,
    location: location || DEFAULT_LOCATION,
    currentDrillIndex: 0,
    hardestNote: '',
    drills,
  };
}

export function initDrillData(drill) {
  if (drill.kind === 'form') {
    const data = {};
    for (const f of drill.fields) data[f.key] = f.type === 'stepper' ? 0 : null;
    return data;
  }
  if (drill.kind === 'holes') {
    return { holes: Array.from({ length: drill.holes }, () => ({ strokes: 0, threePutt: false })) };
  }
  return {};
}

// Data for a drill if it has anything worth reading (completed, or touched).
export function drillData(session, drillId) {
  const d = session.drills[drillId];
  if (!d) return null;
  if (d.status === 'complete' || d.touched) return d.data;
  return null;
}

// ---------- Metrics ----------
// One flat object per session; null where a drill has no data. Used by the
// summary, history cards, progress charts, and comparisons.

export function computeMetrics(session) {
  const m = {};
  const lag = drillData(session, 'lag');
  if (lag) {
    m.lagScore = num(lag.lagScore);
    m.lagPct = pct(m.lagScore, 36);
    m.lagOutside3 = num(lag.outside3);
    m.lagInside3Pct = pct(18 - m.lagOutside3, 18);
    m.lagThreePutts = num(lag.threePutts);
    m.lagThreePuttPct = pct(m.lagThreePutts, 18);
    m.lagMiss = lag.missTendency || null;
  }
  const sp = drillData(session, 'short');
  if (sp) {
    m.makes4 = num(sp.makes4); m.make4Pct = pct(m.makes4, 10);
    m.makes5 = num(sp.makes5); m.make5Pct = pct(m.makes5, 10);
    m.makes6 = num(sp.makes6); m.make6Pct = pct(m.makes6, 10);
    m.shortCombinedPct = pct(m.makes4 + m.makes5 + m.makes6, 30);
  }
  const gate = drillData(session, 'gate');
  if (gate) {
    m.gateOK = num(gate.gateOK); m.gatePct = pct(m.gateOK, 20);
    m.gateLeft = num(gate.missLeft); m.gateLeftPct = pct(m.gateLeft, 20);
    m.gateRight = num(gate.missRight); m.gateRightPct = pct(m.gateRight, 20);
  }
  const chip = drillData(session, 'chip');
  if (chip) {
    m.chipInside3 = num(chip.inside3); m.chipInside3Pct = pct(m.chipInside3, 10);
    m.chip3to6 = num(chip.from3to6);
    m.chipOutside6 = num(chip.outside6); m.chipOutside6Pct = pct(m.chipOutside6, 10);
    m.chipInside6Pct = pct(m.chipInside3 + m.chip3to6, 10);
    m.chipMiss = chip.missTendency || null;
  }
  const ud = drillData(session, 'updown');
  if (ud) {
    const holes = ud.holes.filter((h) => h.strokes > 0);
    if (holes.length) {
      m.udHolesPlayed = holes.length;
      m.udTotal = holes.reduce((a, h) => a + h.strokes, 0);
      m.udVsPar = m.udTotal - holes.length * 2;
      m.udUpDowns = holes.filter((h) => h.strokes <= 2).length;
      m.udPct = pct(m.udUpDowns, 6);
      m.udThreePutts = holes.filter((h) => h.threePutt).length;
    }
  }
  return m;
}

// Metrics charted on the Progress screen, in display order.
export const PROGRESS_METRICS = [
  { key: 'lagPct', label: 'Lag score', higherBetter: true },
  { key: 'lagInside3Pct', label: 'Lag putts inside 3 ft', higherBetter: true },
  { key: 'lagThreePuttPct', label: 'Three-putt rate', higherBetter: false },
  { key: 'make4Pct', label: '4-foot makes', higherBetter: true },
  { key: 'make5Pct', label: '5-foot makes', higherBetter: true },
  { key: 'make6Pct', label: '6-foot makes', higherBetter: true },
  { key: 'gatePct', label: 'Start-line gate', higherBetter: true },
  { key: 'chipInside3Pct', label: 'Chips inside 3 ft', higherBetter: true },
  { key: 'chipInside6Pct', label: 'Chips inside 6 ft', higherBetter: true },
  { key: 'udPct', label: 'Up-and-down rate', higherBetter: true },
];

// Metrics compared against the previous session in the summary.
export const COMPARE_METRICS = [
  { key: 'lagPct', label: 'Lag score', higherBetter: true },
  { key: 'lagInside3Pct', label: 'Lag inside 3 ft', higherBetter: true },
  { key: 'lagThreePuttPct', label: 'Three-putt rate', higherBetter: false },
  { key: 'shortCombinedPct', label: 'Short putts', higherBetter: true },
  { key: 'gatePct', label: 'Start-line gate', higherBetter: true },
  { key: 'chipInside6Pct', label: 'Chips inside 6 ft', higherBetter: true },
  { key: 'udPct', label: 'Up-and-downs', higherBetter: true },
];

// "No meaningful change" band, in percentage points.
const COMPARE_THRESHOLD = 3;

export function compareSessions(cur, prev) {
  if (!prev) return [];
  const a = computeMetrics(cur);
  const b = computeMetrics(prev);
  const rows = [];
  for (const c of COMPARE_METRICS) {
    if (a[c.key] == null || b[c.key] == null) continue;
    const delta = a[c.key] - b[c.key];
    let verdict = 'same';
    if (Math.abs(delta) >= COMPARE_THRESHOLD) {
      verdict = (delta > 0) === c.higherBetter ? 'better' : 'worse';
    }
    rows.push({ label: c.label, cur: a[c.key], prev: b[c.key], delta, verdict });
  }
  return rows;
}

// ---------- Formatting ----------

export function fmtDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

export function fmtDuration(min) {
  if (min == null) return null;
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${min % 60} min`;
}

// ---------- Plain-text summary ("Copy for ChatGPT") ----------

export function buildSummaryText(session) {
  const m = computeMetrics(session);
  const loc = (session.location || DEFAULT_LOCATION).toUpperCase();
  const date = fmtDate(session.startedAt);
  const v = (x) => (x == null ? '__' : String(x));
  const lines = [
    `${loc} PRACTICE — ${date}`,
    '',
    'Lag putting',
    `Score: ${v(m.lagScore)}/36`,
    `Outside 3 ft: ${v(m.lagOutside3)}/18`,
    `3-putts: ${v(m.lagThreePutts)}`,
    `Miss tendency: ${v(m.lagMiss)}`,
    '',
    'Short putts',
    `4 ft: ${v(m.makes4)}/10`,
    `5 ft: ${v(m.makes5)}/10`,
    `6 ft: ${v(m.makes6)}/10`,
    '',
    'Start line',
    `Gate: ${v(m.gateOK)}/20`,
    `Miss left: ${v(m.gateLeft)}`,
    `Miss right: ${v(m.gateRight)}`,
    '',
    'Chipping',
    `Inside 3 ft: ${v(m.chipInside3)}/10`,
    `3–6 ft: ${v(m.chip3to6)}/10`,
    `Outside 6 ft: ${v(m.chipOutside6)}/10`,
    `Typical miss: ${v(m.chipMiss)}`,
    '',
    'Up-and-down game',
    `Total strokes: ${v(m.udTotal)}`,
    `Up-and-downs: ${v(m.udUpDowns)}/6`,
    `3-putts: ${v(m.udThreePutts)}`,
    '',
    `What felt hardest: ${session.hardestNote ? session.hardestNote : '__'}`,
  ];
  return lines.join('\n');
}
