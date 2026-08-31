// Small single-series trend chart (SVG, no dependencies).
// Percent domain fixed at 0–100, hairline grid, 2px line, tappable >=8px
// markers with a value tooltip, latest point always direct-labeled.

const NS = 'http://www.w3.org/2000/svg';

function el(name, attrs, parent) {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}

// points: [{label: 'Aug 12', value: 72}], oldest -> newest
export function renderTrendChart(container, points, opts = {}) {
  const W = 320, H = 96;
  const PAD = { l: 8, r: 34, t: 16, b: 18 };
  const svg = el('svg', {
    viewBox: `0 0 ${W} ${H}`,
    role: 'img',
    'aria-label': `${opts.label || 'Trend'}: ` + points.map((p) => `${p.label} ${p.value}%`).join(', '),
  });
  container.appendChild(svg);

  const iw = W - PAD.l - PAD.r;
  const ih = H - PAD.t - PAD.b;
  const x = (i) => PAD.l + (points.length === 1 ? iw / 2 : (i / (points.length - 1)) * iw);
  const y = (v) => PAD.t + ih - (Math.max(0, Math.min(100, v)) / 100) * ih;

  // Grid: 0 / 50 / 100
  for (const g of [0, 50, 100]) {
    el('line', {
      x1: PAD.l, x2: PAD.l + iw, y1: y(g), y2: y(g),
      stroke: 'var(--grid)', 'stroke-width': g === 0 ? 1.5 : 1,
      'stroke-dasharray': g === 50 ? '3 3' : 'none',
    }, svg);
  }
  el('text', { x: PAD.l + iw + 4, y: y(100) + 3, class: 'axis-txt' }, svg).textContent = '100';
  el('text', { x: PAD.l + iw + 4, y: y(0) + 3, class: 'axis-txt' }, svg).textContent = '0';

  // Line
  if (points.length > 1) {
    const d = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
    el('path', { d, fill: 'none', stroke: 'var(--chart)', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
  }

  // Tooltip (one, repositioned on tap)
  const tip = el('g', { visibility: 'hidden', 'pointer-events': 'none' }, svg);
  const tipBg = el('rect', { rx: 5, fill: 'var(--ink)', opacity: 0.92 }, tip);
  const tipTx = el('text', { class: 'tip-txt', 'text-anchor': 'middle' }, tip);

  const showTip = (i) => {
    const p = points[i];
    tipTx.textContent = `${p.label} · ${p.value}%`;
    const w = tipTx.textContent.length * 5.6 + 12;
    let cx = Math.max(PAD.l + w / 2, Math.min(W - w / 2 - 2, x(i)));
    const above = y(p.value) > 30;
    const ty = above ? y(p.value) - 12 : y(p.value) + 22;
    tipBg.setAttribute('x', cx - w / 2);
    tipBg.setAttribute('y', ty - 11);
    tipBg.setAttribute('width', w);
    tipBg.setAttribute('height', 16);
    tipTx.setAttribute('x', cx);
    tipTx.setAttribute('y', ty + 1);
    tip.setAttribute('visibility', 'visible');
    clearTimeout(tip._t);
    tip._t = setTimeout(() => tip.setAttribute('visibility', 'hidden'), 2200);
  };

  // Markers
  points.forEach((p, i) => {
    const last = i === points.length - 1;
    el('circle', {
      cx: x(i), cy: y(p.value), r: last ? 5 : 4,
      fill: last ? 'var(--chart)' : 'var(--surface)',
      stroke: 'var(--chart)', 'stroke-width': 2,
    }, svg);
    // generous invisible hit target
    const hit = el('circle', { cx: x(i), cy: y(p.value), r: 14, fill: 'transparent' }, svg);
    hit.addEventListener('pointerdown', () => showTip(i), { passive: true });
  });

  // Direct label on the latest point
  const lastI = points.length - 1;
  const lp = points[lastI];
  el('text', {
    x: Math.min(x(lastI), PAD.l + iw - 6),
    y: y(lp.value) > 28 ? y(lp.value) - 9 : y(lp.value) + 16,
    class: 'point-label',
    'text-anchor': lastI === 0 ? 'middle' : 'end',
  }, svg).textContent = lp.value + '%';

  // First/last x labels
  const xl = el('text', { x: PAD.l, y: H - 4, class: 'axis-txt', 'text-anchor': 'start' }, svg);
  xl.textContent = points[0].label;
  if (points.length > 1) {
    const xr = el('text', { x: PAD.l + iw, y: H - 4, class: 'axis-txt', 'text-anchor': 'end' }, svg);
    xr.textContent = points[lastI].label;
  }

  // Inline text styles (kept with the chart so it is self-contained)
  const style = el('style', {}, svg);
  style.textContent = `
    .axis-txt { font: 600 8.5px -apple-system, system-ui, sans-serif; fill: var(--muted); font-variant-numeric: tabular-nums; }
    .point-label { font: 800 11px -apple-system, system-ui, sans-serif; fill: var(--ink); font-variant-numeric: tabular-nums; }
    .tip-txt { font: 700 9.5px -apple-system, system-ui, sans-serif; fill: var(--bg); }
  `;
  return svg;
}
