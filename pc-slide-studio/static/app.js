'use strict';
/* PC Slide Studio front end. The server (schema.py) is the authority on limits; this file keeps the editor friendly. */
const $ = s => document.querySelector(s);
const state = { deck: null, cfg: null, styleId: null, countTouched: false };
const LABELS = { cover: 'Cover', agenda: 'Agenda', section: 'Section', content: 'Content', two_column: 'Two columns', stats: 'Key figures',
  chart: 'Chart', timeline: 'Timeline', table: 'Table', quote: 'Quote', image: 'Image', image_text: 'Image + text', closing: 'Closing' };
const ACCENTS = ['#0089cf', '#003862', '#f58220', '#2a5cab', '#a5a5a5', '#f04e2a'];
const DRAFT_KEY = 'pc-slide-studio-draft';

const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const lines = t => t.split('\n').map(x => x.trim()).filter(Boolean);
const cells = line => line.split('|').map(x => x.trim());
const msg = (t, error = false) => { $('#status').textContent = t; $('#status').className = error ? 'error' : ''; };
function el(tag, props = {}, ...kids) {
  const e = Object.assign(document.createElement(tag), props);
  kids.flat().forEach(k => e.append(k));
  return e;
}
function download(blob, name) {
  const u = URL.createObjectURL(blob);
  const a = el('a', { href: u, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 3000);
}

/* ---------- defaults so every layout always has something to edit ---------- */
const DEFAULTS = {
  stats: () => [1, 2, 3].map(() => ({ value: '00', label: 'Label', note: '' })),
  steps: () => [1, 2, 3].map(i => ({ title: 'Step ' + i, text: '' })),
  columns: () => [{ title: 'Left', bullets: [] }, { title: 'Right', bullets: [] }],
  chart: () => ({ type: 'column', categories: ['A', 'B', 'C'], series: [{ name: 'Series 1', values: [10, 20, 30] }], unit: '', title: '' }),
  table: () => ({ header: ['Column 1', 'Column 2'], rows: [['', '']] }),
};
function ensure(s) {
  s.title ??= ''; s.subtitle ??= ''; s.takeaway ??= ''; s.notes ??= ''; s.bullets ??= [];
  const L = s.layout;
  if (L === 'stats' && !(s.stats && s.stats.length)) s.stats = DEFAULTS.stats();
  if (L === 'timeline' && !(s.steps && s.steps.length)) s.steps = DEFAULTS.steps();
  if (L === 'two_column' && !(s.columns && s.columns.length === 2)) s.columns = DEFAULTS.columns();
  if (L === 'chart' && !s.chart) s.chart = DEFAULTS.chart();
  if (L === 'table' && !s.table) s.table = DEFAULTS.table();
  if (L === 'quote') { s.quote ??= s.title || ''; s.author ??= ''; }
  return s;
}

/* ---------- text <-> structure converters ---------- */
const statsToText = a => a.map(x => [x.value, x.label, x.note].join(' | ')).join('\n');
const textToStats = t => lines(t).map(l => { const c = cells(l); return { value: c[0] || '', label: c[1] || '', note: c[2] || '' }; });
const stepsToText = a => a.map(x => [x.title, x.text].join(' | ')).join('\n');
const textToSteps = t => lines(t).map(l => { const c = cells(l); return { title: c[0] || '', text: c.slice(1).join(' | ') }; });
const tableToText = t => [t.header, ...t.rows].map(r => r.join(' | ')).join('\n');
function textToTable(t) {
  const rows = lines(t).map(cells);
  const header = rows.shift() || ['Column 1'];
  return { header, rows: rows.map(r => header.map((_, i) => r[i] || '')) };
}
function chartToText(c) {
  const head = ['Category', ...c.series.map(s => s.name)].join(' | ');
  return [head, ...c.categories.map((cat, i) => [cat, ...c.series.map(s => s.values[i] ?? '')].join(' | '))].join('\n');
}
function textToChart(t, prev) {
  const rows = lines(t).map(cells);
  const head = rows.shift() || ['Category', 'Series 1'];
  const num = v => { const n = parseFloat(String(v).replace(/[^0-9.\-]/g, '')); return Number.isFinite(n) ? n : null; };
  return { ...prev, categories: rows.map(r => r[0] || ''), series: head.slice(1).map((name, i) => ({ name, values: rows.map(r => num(r[i + 1])) })) };
}

/* ---------- mini preview (an approximation, not a PowerPoint render) ---------- */
function chartSvg(ch) {
  const n = ch.categories.length, vals = ch.series.map(s => s.values.map(v => v ?? 0));
  const max = Math.max(1, ...vals.flat());
  const color = i => ACCENTS[i % ACCENTS.length];
  if (ch.type === 'pie' || ch.type === 'doughnut') {
    const v = vals[0] || [], sum = v.reduce((a, b) => a + b, 0) || 1;
    let ang = -Math.PI / 2, out = '';
    v.forEach((x, i) => {
      const a2 = ang + 2 * Math.PI * x / sum, large = a2 - ang > Math.PI ? 1 : 0;
      const p = (a, r) => `${28 + r * Math.cos(a)},${28 + r * Math.sin(a)}`;
      out += `<path d="M28,28 L${p(ang, 24)} A24,24 0 ${large} 1 ${p(a2, 24)} Z" fill="${color(i)}" stroke="#fff" stroke-width=".6"/>`;
      ang = a2;
    });
    if (ch.type === 'doughnut') out += '<circle cx="28" cy="28" r="12" fill="#fff"/>';
    return `<svg viewBox="0 0 56 56" preserveAspectRatio="xMidYMid meet">${out}</svg>`;
  }
  const W = 100, H = 52, step = W / Math.max(1, n);
  let out = `<line x1="0" x2="${W}" y1="${H}" y2="${H}" stroke="#b9c7d6" stroke-width=".4"/>`;
  if (ch.type === 'line') {
    vals.forEach((v, si) => {
      const pts = v.map((x, i) => `${step * (i + .5)},${H - 4 - x / max * (H - 10)}`);
      out += `<polyline points="${pts.join(' ')}" fill="none" stroke="${color(si)}" stroke-width="1.2"/>` + pts.map(p => `<circle cx="${p.split(',')[0]}" cy="${p.split(',')[1]}" r="1.2" fill="${color(si)}"/>`).join('');
    });
  } else if (ch.type === 'bar') {
    const bh = (H - 2) / Math.max(1, n);
    (vals[0] || []).forEach((x, i) => { out += `<rect x="0" y="${i * bh + bh * .15}" width="${x / max * (W - 4)}" height="${bh * .7}" fill="${color(0)}"/>`; });
  } else {
    const k = vals.length, bw = step * .8 / k;
    vals.forEach((v, si) => v.forEach((x, i) => { const h = x / max * (H - 8); out += `<rect x="${step * i + step * .1 + si * bw}" y="${H - h}" width="${bw * .92}" height="${h}" fill="${color(si)}"/>`; }));
  }
  return `<svg viewBox="0 0 ${W} ${H + 2}" preserveAspectRatio="none">${out}</svg>`;
}
const li = a => '<ul>' + (a || []).slice(0, 6).map(b => `<li>${esc(b)}</li>`).join('') + '</ul>';
function previewHtml(s) {
  const L = s.layout, take = s.takeaway ? `<div class="take">${esc(s.takeaway)}</div>` : '';
  const head = `<div class="logo">Prima Power</div><div class="pt">${esc(s.title)}</div>`;
  if (L === 'cover') return ['pv dark', `<div class="big">EVOLVE BY INTEGRATION<div class="bar"></div><div style="font-size:3.4cqw">${esc(s.title)}</div><div class="sub">${esc(s.subtitle)}</div></div>`];
  if (L === 'section') return ['pv dark', `<div class="big">${esc(s.title)}<div class="bar"></div><div class="sub">EVOLVE BY INTEGRATION</div></div>`];
  if (L === 'quote') return ['pv dark', `<div class="big" style="font-size:3.6cqw;font-weight:500">“${esc(s.quote)}”<div class="sub" style="color:#f58220;font-weight:700">${s.author ? '— ' + esc(s.author) : ''}</div></div>`];
  if (L === 'closing') return ['pv dark', '<div class="big" style="left:0;right:0;text-align:center;top:38%">THANK YOU<div class="bar" style="margin:2cqw auto"></div></div>'];
  let body = '';
  if (L === 'content') body = `<div class="c ac">${li(s.bullets)}</div>`;
  else if (L === 'agenda') body = '<div class="ag">' + (s.bullets || []).slice(0, 8).map((b, i) => `<div><i>${i + 1}</i>${esc(b)}</div>`).join('') + '</div>';
  else if (L === 'two_column') body = (s.columns || []).map((c, i) => `<div class="c hd ${i ? 'b2' : ''}"><h4>${esc(c.title)}</h4><div>${li(c.bullets)}</div></div>`).join('');
  else if (L === 'stats') body = (s.stats || []).map((x, i) => `<div class="c tp" style="--a:${ACCENTS[i % 4]}"><div class="num">${esc(x.value)}</div><div class="lbl">${esc(x.label)}</div><div class="nt">${esc(x.note)}</div></div>`).join('');
  else if (L === 'timeline') body = '<div class="tl">' + (s.steps || []).map((x, i) => `<div style="--a:${ACCENTS[i % 2]}"><i>${i + 1}</i><div class="c tp"><b>${esc(x.title)}</b><div class="nt">${esc(x.text)}</div></div></div>`).join('') + '</div>';
  else if (L === 'table' && s.table) body = `<table><tr>${s.table.header.map(h => `<th>${esc(h)}</th>`).join('')}</tr>${s.table.rows.slice(0, 7).map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</table>`;
  else if (L === 'chart' && s.chart) body = `<div class="c" style="flex:2">${chartSvg(s.chart)}</div>` + (s.bullets.length ? `<div class="c navy" style="flex:1">${li(s.bullets)}</div>` : '');
  else if (L === 'image') body = `<div class="c" style="display:flex;flex-direction:column;gap:1cqw">${s.image ? `<img src="${esc(s.image)}" alt="" style="min-height:0;flex:1">` : ''}${s.subtitle ? `<div class="cap">${esc(s.subtitle)}</div>` : ''}</div>`;
  else if (L === 'image_text') body = `<div class="c" style="flex:1.3;display:flex">${s.image ? `<img src="${esc(s.image)}" alt="">` : ''}</div><div class="c ac" style="flex:1">${li(s.bullets)}</div>`;
  return ['pv', `${head}${take}<div class="body">${body}</div>`];
}
function drawPreview(host, s) {
  const [cls, html] = previewHtml(s);
  host.className = cls;
  host.innerHTML = '<div class="in">' + html + '</div>';
}

/* ---------- slide editor ---------- */
const field = (label, input) => el('label', { textContent: label }, input);
function textInput(value, max, on) {
  const i = el('input', { value, maxLength: max });
  i.oninput = () => on(i.value);
  return i;
}
function area(value, on, rows = 4, mono = false) {
  const a = el('textarea', { value, rows, className: mono ? 'mono' : '' });
  a.oninput = () => on(a.value);
  return a;
}
function pickImage(on) {
  const f = el('input', { type: 'file', accept: '.png,.jpg,.jpeg,.webp' });
  f.onchange = async e => { if (e.target.files[0]) on(await readImage(e.target.files[0])); };
  return f;
}
function readImage(file) {   // downscale in the browser so uploads stay small
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file), img = new Image();
    img.onload = () => {
      const k = Math.min(1, 2000 / Math.max(img.width, img.height)), c = el('canvas', { width: Math.round(img.width * k), height: Math.round(img.height * k) });
      const ctx = c.getContext('2d');
      if (file.type !== 'image/png') { ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height); }
      ctx.drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      resolve(file.type === 'image/png' ? c.toDataURL('image/png') : c.toDataURL('image/jpeg', .88));
    };
    img.onerror = () => reject(new Error('Could not read that picture.'));
    img.src = url;
  });
}

function editor(s, changed, rerender) {
  const f = el('div', { className: 'fields' });
  const L = s.layout, add = (...n) => f.append(...n);
  const title = (lbl = 'Slide title') => add(field(lbl, textInput(s.title, 140, v => { s.title = v; changed(); })));
  const bullets = (lbl, key = 'bullets', host = s) => add(field(lbl, area((host[key] || []).join('\n'), v => { host[key] = lines(v); changed(); })));
  const take = () => add(field('Takeaway (one sentence shown in a bar at the bottom)', textInput(s.takeaway, 160, v => { s.takeaway = v; changed(); })));
  if (L === 'quote') {
    add(field('Quote', area(s.quote, v => { s.quote = v; s.title = v.slice(0, 140); changed(); }, 3)), field('Author', textInput(s.author, 80, v => { s.author = v; changed(); })));
  } else if (L === 'closing') {
    add(el('p', { className: 'note', textContent: 'Uses the original THANK YOU closing slide. Its wording is fixed by the template.' }));
  } else {
    title(L === 'cover' ? 'Presentation title' : 'Slide title');
    if (L === 'cover') add(field('Subtitle (audience, date, context)', textInput(s.subtitle, 120, v => { s.subtitle = v; changed(); })));
    if (L === 'content' || L === 'image_text') bullets('Bullets · one per line (up to 6). Write “Lead — detail” to bold the lead');
    if (L === 'agenda') bullets('Agenda items · one per line (up to 8)');
    if (L === 'two_column') s.columns.forEach((c, i) => {
      add(field(`Column ${i + 1} heading`, textInput(c.title, 50, v => { c.title = v; changed(); })));
      bullets(`Column ${i + 1} bullets · one per line`, 'bullets', c);
    });
    if (L === 'stats') add(field('Figures · one per line: value | label | note (2 to 4)', area(statsToText(s.stats), v => { s.stats = textToStats(v); changed(); }, 4, true)));
    if (L === 'timeline') add(field('Steps · one per line: title | detail (3 to 6)', area(stepsToText(s.steps), v => { s.steps = textToSteps(v); changed(); }, 5, true)));
    if (L === 'table') add(field('Table · one row per line, cells separated by |. First line is the header', area(tableToText(s.table), v => { s.table = textToTable(v); changed(); }, 6, true)));
    if (L === 'chart') {
      const type = el('select', {}, ['column', 'bar', 'line', 'pie', 'doughnut'].map(t => el('option', { value: t, textContent: t[0].toUpperCase() + t.slice(1) })));
      type.value = s.chart.type; type.onchange = () => { s.chart.type = type.value; changed(); };
      add(el('div', { className: 'row' }, field('Chart type', type), field('Unit (e.g. %, h, €)', textInput(s.chart.unit || '', 8, v => { s.chart.unit = v; changed(); })), field('Chart title (optional)', textInput(s.chart.title || '', 80, v => { s.chart.title = v; changed(); }))));
      add(field('Data · first line = series names. Then: category | value | value', area(chartToText(s.chart), v => { s.chart = textToChart(v, s.chart); changed(); }, 6, true)));
      bullets('Key points beside the chart · one per line (optional)');
    }
    if (L === 'image' || L === 'image_text') {
      if (L === 'image') add(field('Caption (optional)', textInput(s.subtitle, 120, v => { s.subtitle = v; changed(); })));
      if (s.image) add(el('img', { src: s.image, className: 'thumb', alt: 'Slide picture' }));
      add(field(s.image ? 'Replace picture' : 'Picture', pickImage(d => { s.image = d; rerender(); })));
    }
    if (['two_column', 'stats', 'chart', 'timeline', 'table', 'image', 'image_text'].includes(L)) take();
  }
  add(el('details', {}, el('summary', { textContent: 'Speaker notes' }), area(s.notes, v => { s.notes = v; changed(); }, 3)));
  return f;
}

function render() {
  const host = $('#slides'), deck = state.deck;
  host.replaceChildren();
  deck.slides.forEach((s, i) => {
    ensure(s);
    const card = el('div', { className: 'slide' });
    const prev = el('div');
    const changed = () => { drawPreview(prev, s); persist(); };
    const sel = el('select', { 'aria-label': 'Slide layout' }, state.cfg.layouts.map(v => el('option', { value: v, textContent: LABELS[v] || v })));
    sel.value = s.layout;
    sel.onchange = () => { s.layout = sel.value; ensure(s); render(); };
    const move = (d) => () => { const j = i + d; if (j < 0 || j >= deck.slides.length) return; [deck.slides[i], deck.slides[j]] = [deck.slides[j], deck.slides[i]]; render(); };
    const btn = (t, fn, label) => el('button', { className: 'secondary', textContent: t, onclick: fn, title: label, 'aria-label': label });
    card.append(el('div', { className: 'slide-head' }, el('b', { textContent: String(i + 1).padStart(2, '0') }), sel, el('span', { className: 'sp' }),
      btn('↑', move(-1), 'Move up'), btn('↓', move(1), 'Move down'),
      btn('Duplicate', () => { if (deck.slides.length < state.cfg.limits.slides) { deck.slides.splice(i + 1, 0, structuredClone(s)); render(); } }, 'Duplicate slide'),
      btn('Remove', () => { if (deck.slides.length > 1) { deck.slides.splice(i, 1); render(); } }, 'Remove slide')));
    card.append(el('div', { className: 'slide-body' }, editor(s, changed, render), prev));
    drawPreview(prev, s);
    host.append(card);
  });
  $('#save').disabled = $('#export').disabled = false;
  $('#addrow').hidden = $('#deckopts').hidden = false;
  $('#counter').textContent = deck.slides.length + ' slides';
  $('#deck-title').value = deck.title || '';
  $('#transition').value = deck.transition || 'fade';
  $('#animations').checked = deck.animations !== false;
  persist();
}
function setDeck(d) {
  state.deck = { title: d.title || '', transition: d.transition || 'fade', animations: d.animations !== false, slides: d.slides.map(s => ensure({ ...s })) };
  render();
}
function persist() {
  try { localStorage.setItem(DRAFT_KEY, JSON.stringify(state.deck)); } catch (e) { /* too large or blocked: the Save draft button still works */ }
}

/* ---------- brief panel: styles, models, hints ---------- */
function chooseStyle(id) {
  const st = state.cfg.styles.find(x => x.id === id);
  if (!st) return;
  state.styleId = id;
  document.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-checked', String(c.dataset.id === id)));
  $('#style-img').src = st.image; $('#style-img').alt = `Example slides in the ${st.label} style`;
  $('#style-name').textContent = st.label; $('#style-blurb').textContent = st.blurb;
  $('#style-mix').textContent = 'Favours: ' + st.mix.replaceAll('_', ' ');
  $('#style-preview').hidden = false;
  if (!state.countTouched) $('#count').value = st.count;
}
function updateHints() {
  const m = state.cfg.models.find(x => x.id === $('#model').value);
  $('#model-note').textContent = m ? (m.vision ? '👁 Can read pictures. ' : 'Text only. ') + m.note : '';
  const hasPic = [...$('#files').files].some(f => /\.(png|jpe?g|webp|gif|pdf|docx|pptx)$/i.test(f.name));
  $('#image-hint').textContent = !$('#use-images').checked ? '' : hasPic && m && !m.vision
    ? 'This model cannot see pictures, so Auto will be used to read them.'
    : 'Drawings, photos and short PDFs are shown to the AI, which can place them on slides.';
}
async function init() {
  try {
    state.cfg = await (await fetch('api/status')).json();
  } catch (e) {
    $('#connection').textContent = 'Could not reach the server'; return;
  }
  const c = state.cfg;
  $('#connection').textContent = c.configured ? 'AI key configured · Free models only' : 'AI key not configured · Sample, editing and export still work';
  $('#style-chips').append(...c.styles.map(st => el('button', { type: 'button', className: 'chip', textContent: st.label, role: 'radio', 'aria-checked': 'false', onclick: () => chooseStyle(st.id) })));
  $('#style-chips').querySelectorAll('.chip').forEach((b, i) => { b.dataset.id = c.styles[i].id; });
  chooseStyle(c.styles[0].id);
  $('#model').append(...c.models.map(m => el('option', { value: m.id, textContent: m.label + (m.vision ? ' · sees images' : '') })));
  $('#transition').append(...c.transitions.map(t => el('option', { value: t, textContent: t === 'none' ? 'None' : t[0].toUpperCase() + t.slice(1) })));
  $('#add-layout').append(...c.layouts.filter(l => l !== 'cover' && l !== 'closing').map(l => el('option', { value: l, textContent: LABELS[l] || l })));
  $('#add-layout').value = 'content';
  $('#files').accept = c.accepted.join(',');
  updateHints();
  try {
    const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null');
    if (saved && saved.slides && saved.slides.length) {
      msg('You have an unsaved draft from earlier.');
      $('#status').append(' ', el('button', { className: 'secondary', type: 'button', textContent: 'Restore it', onclick: () => { setDeck(saved); msg('Draft restored.'); } }));
    }
  } catch (e) { /* ignore */ }
}

/* ---------- actions ---------- */
$('#count').oninput = () => { state.countTouched = true; };
$('#model').onchange = $('#use-images').onchange = $('#files').onchange = updateHints;
$('#brief').onsubmit = async e => {
  e.preventDefault();
  const b = $('#generate');
  b.disabled = true;
  msg('Reading your material and drafting slides… This can take a few minutes with free models.');
  try {
    const fd = new FormData(e.target);
    fd.set('style', state.styleId);
    fd.set('use_images', $('#use-images').checked ? '1' : '0');
    const r = await fetch('api/draft', { method: 'POST', body: fd });
    const d = await r.json();
    if (!r.ok) throw Error(d.error || 'Generation failed');
    setDeck(d.deck);
    msg('Draft ready. Review all facts before exporting.\nModel: ' + d.model + (d.warnings && d.warnings.length ? '\n' + d.warnings.join('\n') : ''));
  } catch (err) { msg(err.message, true); } finally { b.disabled = false; }
};
$('#export').onclick = async () => {
  const b = $('#export');
  b.disabled = true;
  try {
    const r = await fetch('api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(state.deck) });
    if (!r.ok) throw Error((await r.json()).error);
    download(await r.blob(), (state.deck.title || 'presentation').replace(/[^a-z0-9_-]/gi, '-') + '.pptx');
    msg('PowerPoint downloaded. Transitions and animations play in slideshow mode.');
  } catch (err) { msg(err.message, true); } finally { b.disabled = false; }
};
$('#save').onclick = () => download(new Blob([JSON.stringify(state.deck, null, 2)], { type: 'application/json' }), 'pc-slide-draft.json');
$('#load').onclick = () => $('#draftfile').click();
$('#draftfile').onchange = async e => {
  try {
    const d = JSON.parse(await e.target.files[0].text());
    if (!Array.isArray(d.slides) || !d.slides.length || d.slides.length > state.cfg.limits.slides || d.slides.some(s => !s || !state.cfg.layouts.includes(s.layout))) throw Error('Invalid draft');
    setDeck(d);
    msg('Draft loaded.');
  } catch (err) { msg('Could not open this draft file.', true); }
  e.target.value = '';
};
$('#deck-title').oninput = e => { state.deck.title = e.target.value; persist(); };
$('#transition').onchange = e => { state.deck.transition = e.target.value; persist(); };
$('#animations').onchange = e => { state.deck.animations = e.target.checked; persist(); };
$('#add').onclick = () => {
  const slides = state.deck.slides;
  if (slides.length >= state.cfg.limits.slides) return msg('Maximum ' + state.cfg.limits.slides + ' slides.', true);
  const s = ensure({ layout: $('#add-layout').value, title: 'New slide' });
  const at = slides.length && slides[slides.length - 1].layout === 'closing' ? slides.length - 1 : slides.length;
  slides.splice(at, 0, s);
  render();
};
function ensureDeck() { if (!state.deck) state.deck = { title: 'Presentation', transition: 'fade', animations: true, slides: [] }; }
$('#addImage').onclick = () => $('#imagefile').click();
$('#imagefile').onchange = async e => {
  ensureDeck();
  try {
    for (const f of e.target.files) state.deck.slides.push(ensure({ layout: 'image', title: f.name.replace(/\.[^.]+$/, ''), image: await readImage(f) }));
    render();
  } catch (err) { msg(err.message, true); }
  e.target.value = '';
};
$('#addPdfPages').onclick = () => $('#pdffile').click();
$('#pdffile').onchange = async e => {
  const f = e.target.files[0];
  if (!f) return;
  msg('Rendering PDF pages as pictures…');
  try {
    const fd = new FormData();
    fd.append('file', f);
    const r = await fetch('api/pdf-images', { method: 'POST', body: fd });
    const d = await r.json();
    if (!r.ok) throw Error(d.error || 'Could not render PDF');
    ensureDeck();
    if (!state.deck.slides.length) state.deck.title = f.name.replace(/\.[^.]+$/, '');
    const base = f.name.replace(/\.[^.]+$/, '');
    d.pages.forEach(p => state.deck.slides.push(ensure({ layout: 'image', title: base + ' — page ' + p.page, image: p.image })));
    render();
    msg('Added ' + d.pages.length + ' image slide(s)' + (d.total > d.rendered ? ' (first ' + d.rendered + ' of ' + d.total + ' pages)' : '') + '. Edit the titles, reorder, then export.');
  } catch (err) { msg(err.message, true); }
  e.target.value = '';
};
$('#demo').onclick = () => {
  setDeck({ title: 'Installation project update', slides: [
    { layout: 'cover', title: 'Installation project update', subtitle: 'Sample content' },
    { layout: 'stats', title: 'Where we are', stats: [{ value: '78%', label: 'Mechanical complete', note: 'Example figure' }, { value: '14', label: 'Open punch items', note: 'Example figure' }, { value: '3 wks', label: 'To site acceptance', note: 'Example figure' }], takeaway: 'Example takeaway: replace with your own.' },
    { layout: 'chart', title: 'Progress by area', chart: { type: 'column', categories: ['Mechanical', 'Electrical', 'Software'], series: [{ name: 'Done', values: [78, 55, 30] }], unit: '%', title: '' }, bullets: ['Example: mechanical is furthest ahead'] },
    { layout: 'timeline', title: 'Milestones', steps: [{ title: 'Delivery', text: 'Example' }, { title: 'Mechanical', text: 'Example' }, { title: 'Electrical', text: 'Example' }, { title: 'Acceptance', text: 'Example' }] },
    { layout: 'content', title: 'Site readiness', bullets: ['Example: Confirm foundation readiness before delivery', 'Example: Review power and utilities with the site team'] },
    { layout: 'closing', title: 'THANK YOU' }] });
  msg('Sample content only. Replace it with your project details.');
};
init();
