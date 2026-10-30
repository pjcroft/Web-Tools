/* Office (PPTX / DOCX / XLSX) comparison for Doc Diff. Runs entirely in the browser using JSZip. */
const OFF = (() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
  const EXT = {pptx:'pptx',pptm:'pptx',docx:'docx',docm:'docx',xlsx:'xlsx',xlsm:'xlsx'};
  const st = {ext:null, p:{a:null,b:null}, name:{a:'',b:''}, items:[], sum:[], cur:0};

  const style = document.createElement('style');
  style.textContent = `
  body.office .vis{display:none!important}
  .dot.moved{background:#a78bfa}
  .od{max-width:980px;margin:0 auto;color:var(--text)}
  .od h2{margin:.1rem 0 .2rem;font-size:1.25rem;display:flex;gap:.7rem;align-items:center;flex-wrap:wrap}
  .od .sub{margin:0 0 1rem;color:var(--muted);font-size:.9rem}
  .od section{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin:0 0 1rem;overflow:hidden}
  .od section>h3{margin:0;padding:.55rem .9rem;font-size:.75rem;letter-spacing:.12em;text-transform:uppercase;color:var(--tan);border-bottom:1px solid var(--line);background:var(--panel2)}
  .od .r{padding:.45rem .9rem;font-size:.92rem;line-height:1.55;border-bottom:1px solid rgba(38,54,90,.5);word-break:break-word}
  .od .r:last-child{border-bottom:0}
  .od .r.add{background:rgba(22,163,74,.12)} .od .r.add:before{content:"+ ";color:#4ade80;font-weight:700}
  .od .r.rem{background:rgba(229,72,77,.12)} .od .r.rem:before{content:"− ";color:#ff8a8e;font-weight:700}
  .od .r.mod{background:rgba(245,158,11,.07)}
  .od .r.same{color:var(--muted)}
  .od .r.gap{color:var(--muted);font-size:.8rem;text-align:center;font-style:italic;background:rgba(255,255,255,.02)}
  .od .r.h1,.od .r.h2,.od .r.h3{font-weight:700;color:var(--text)} .od .r.h1{font-size:1.15rem}
  .od ins{background:rgba(22,163,74,.28);color:#86efac;text-decoration:none;border-radius:3px;padding:0 2px}
  .od del{background:rgba(229,72,77,.28);color:#fca5a5;border-radius:3px;padding:0 2px}
  .od .flash{animation:oflash 1.2s ease-out}
  @keyframes oflash{0%{box-shadow:0 0 0 3px var(--accent)}100%{box-shadow:0 0 0 0 transparent}}
  .od table{width:100%;border-collapse:collapse;font-size:.88rem}
  .od th{text-align:left;font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);padding:.45rem .8rem;border-bottom:1px solid var(--line)}
  .od td{padding:.4rem .8rem;border-bottom:1px solid rgba(38,54,90,.5);vertical-align:top;word-break:break-word}
  .od td.c{font-family:ui-monospace,Menlo,monospace;color:var(--accent);white-space:nowrap}
  .od code{font-family:ui-monospace,Menlo,monospace;font-size:.8rem;color:var(--muted)}
  .od .none{color:var(--muted);font-style:italic}
  .od .chips{display:flex;gap:.5rem;flex-wrap:wrap;padding:.6rem .9rem;font-size:.85rem}
  .od .chips span{border:1px solid var(--line);border-radius:999px;padding:.15rem .7rem;color:var(--muted)}
  .od .chips b{color:var(--text)}
  .sumbtn{margin:.7rem .9rem}
  `;
  document.head.appendChild(style);

  /* ---------- xml / zip helpers ---------- */
  const dom = t => new DOMParser().parseFromString(t, 'application/xml');
  const els = (n, l) => Array.from(n.getElementsByTagNameNS('*', l));
  const first = (n, l) => n.getElementsByTagNameNS('*', l)[0] || null;
  async function readXml(zip, path){ const f = zip.file(path); return f ? dom(await f.async('string')) : null; }
  function resolve(from, target){
    if(target.startsWith('/')) return target.slice(1);
    const parts = from.split('/').slice(0, -1);
    for(const seg of target.split('/')){ if(seg === '..') parts.pop(); else if(seg && seg !== '.') parts.push(seg); }
    return parts.join('/');
  }
  async function rels(zip, path){
    const dir = path.split('/').slice(0, -1).join('/'), name = path.split('/').pop();
    const d = await readXml(zip, (dir ? dir + '/' : '') + '_rels/' + name + '.rels'), m = {};
    if(d) for(const r of els(d, 'Relationship'))
      m[r.getAttribute('Id')] = {type: r.getAttribute('Type') || '', target: r.getAttribute('TargetMode') === 'External' ? null : resolve(path, r.getAttribute('Target'))};
    return m;
  }
  function ptext(p){
    let s = '';
    for(const e of p.getElementsByTagNameNS('*', '*')){
      const l = e.localName;
      if(l === 't') s += e.textContent; else if(l === 'tab' || l === 'br' || l === 'cr') s += ' ';
    }
    return s.replace(/\s+/g, ' ').trim();
  }
  function fnv(u8){ let h = 0x811c9dc5; for(let i = 0; i < u8.length; i++){ h ^= u8[i]; h = Math.imul(h, 0x01000193); } return (h >>> 0).toString(16) + '-' + u8.length; }
  async function hashPart(zip, path, cache){
    if(!path) return 'none';
    if(cache[path]) return cache[path];
    const f = zip.file(path); return cache[path] = f ? fnv(await f.async('uint8array')) : 'missing';
  }

  /* ---------- diff primitives ---------- */
  function lcsOps(a, b, eq = (x, y) => x === y){
    let s = 0; while(s < a.length && s < b.length && eq(a[s], b[s])) s++;
    let ea = a.length, eb = b.length;
    while(ea > s && eb > s && eq(a[ea - 1], b[eb - 1])){ ea--; eb--; }
    const ops = []; for(let i = 0; i < s; i++) ops.push(['=', a[i], b[i]]);
    const n = ea - s, m = eb - s;
    if(n * m > 4e7 || Math.min(n, m) > 65000){
      for(let i = 0; i < n; i++) ops.push(['-', a[s + i]]);
      for(let j = 0; j < m; j++) ops.push(['+', b[s + j]]);
    }else{
      const w = m + 1, L = new Uint16Array((n + 1) * w);
      for(let x = n - 1; x >= 0; x--) for(let y = m - 1; y >= 0; y--)
        L[x * w + y] = eq(a[s + x], b[s + y]) ? L[(x + 1) * w + y + 1] + 1 : Math.max(L[(x + 1) * w + y], L[x * w + y + 1]);
      let x = 0, y = 0;
      while(x < n && y < m){
        if(eq(a[s + x], b[s + y])){ ops.push(['=', a[s + x], b[s + y]]); x++; y++; }
        else if(L[(x + 1) * w + y] >= L[x * w + y + 1]) ops.push(['-', a[s + x++]]);
        else ops.push(['+', b[s + y++]]);
      }
      while(x < n) ops.push(['-', a[s + x++]]);
      while(y < m) ops.push(['+', b[s + y++]]);
    }
    for(let i = ea; i < a.length; i++) ops.push(['=', a[i], b[i - ea + eb]]);
    return ops;
  }
  const words = s => s.toLowerCase().split(/\s+/).filter(Boolean);
  function jac(A, B){
    if(!A.size && !B.size) return 1;
    let i = 0; for(const x of A) if(B.has(x)) i++;
    return i / (A.size + B.size - i);
  }
  // align two sequences, pairing nearby replaced items when similar enough
  function align(A, B, eq, sim, th){
    const ops = lcsOps(A, B, eq), rows = []; let i = 0;
    while(i < ops.length){
      if(ops[i][0] === '='){ rows.push({op:'=', a:ops[i][1], b:ops[i][2]}); i++; continue; }
      const D = [], I = [];
      while(i < ops.length && ops[i][0] !== '='){ (ops[i][0] === '-' ? D : I).push(ops[i][1]); i++; }
      let p = 0;
      for(const d of D){
        let hit = -1;
        for(let k = p; k < I.length; k++) if(sim(d, I[k]) >= th){ hit = k; break; }
        if(hit < 0){ rows.push({op:'-', a:d}); continue; }
        while(p < hit) rows.push({op:'+', b:I[p++]});
        rows.push({op:'~', a:d, b:I[p++]});
      }
      while(p < I.length) rows.push({op:'+', b:I[p++]});
    }
    return rows;
  }
  function wordDiff(a, b){
    const A = a.split(/\s+/).filter(Boolean), B = b.split(/\s+/).filter(Boolean);
    if(A.length > 3000 || B.length > 3000) return `<del>${esc(a)}</del> <ins>${esc(b)}</ins>`;
    const out = []; let del = [], ins = [];
    const flush = () => { if(del.length) out.push('<del>' + esc(del.join(' ')) + '</del>'); if(ins.length) out.push('<ins>' + esc(ins.join(' ')) + '</ins>'); del = []; ins = []; };
    for(const [op, x] of lcsOps(A, B)){
      if(op === '=') { flush(); out.push(esc(x)); } else if(op === '-') del.push(x); else ins.push(x);
    }
    flush(); return out.join(' ');
  }
  // paragraph level diff: paragraphs are strings or {t}
  const T = x => typeof x === 'string' ? x : x.t;
  function diffParas(A, B){
    const rows = align(A, B, (x, y) => T(x) === T(y), (x, y) => {
      const a = T(x), b = T(y), wa = words(a), wb = words(b), j = jac(new Set(wa), new Set(wb));
      return (wa.length <= 4 && wb.length <= 4 && j > 0) ? Math.max(j, .4) : j;
    }, .4);
    for(const r of rows) if(r.op === '~') r.html = wordDiff(T(r.a), T(r.b));
    return rows;
  }
  const changed = rows => rows.filter(r => r.op !== '=').length;
  function rowsHtml(rows, keep = 2){
    const out = []; let buf = [];
    const flush = () => {
      if(buf.length > keep * 2 + 1){
        buf.slice(0, keep).forEach(h => out.push(h));
        out.push(`<div class="r gap">… ${buf.length - keep * 2} unchanged …</div>`);
        buf.slice(-keep).forEach(h => out.push(h));
      }else buf.forEach(h => out.push(h));
      buf = [];
    };
    for(const r of rows){
      const h = r.op === '=' ? `<div class="r same">${esc(T(r.a))}</div>` : '';
      if(r.op === '='){ buf.push(h); continue; }
      flush();
      out.push(r.op === '+' ? `<div class="r add">${esc(T(r.b))}</div>` : r.op === '-' ? `<div class="r rem">${esc(T(r.a))}</div>` : `<div class="r mod">${r.html}</div>`);
    }
    flush(); return out.join('');
  }

  /* ---------- PPTX ---------- */
  async function parsePptx(zip){
    const pres = await readXml(zip, 'ppt/presentation.xml');
    if(!pres) throw new Error('This does not look like a PowerPoint file.');
    const prel = await rels(zip, 'ppt/presentation.xml'), cache = {}, slides = [];
    const ids = els(pres, 'sldId').map(e => e.getAttributeNS(R_NS, 'id'));
    for(const id of ids){
      const rel = prel[id]; if(!rel || !rel.target) continue;
      const doc = await readXml(zip, rel.target); if(!doc) continue;
      const srel = await rels(zip, rel.target), shapes = [], imgs = [], charts = [];
      const tree = first(doc, 'spTree');
      if(tree) for(const e of els(tree, '*')){
        const l = e.localName; if(l !== 'sp' && l !== 'pic' && l !== 'graphicFrame') continue;
        const c = first(e, 'cNvPr'), xf = first(e, 'xfrm');
        const off = xf && first(xf, 'off'), ex = xf && first(xf, 'ext');
        const geo = off && ex ? [+off.getAttribute('x'), +off.getAttribute('y'), +ex.getAttribute('cx'), +ex.getAttribute('cy')] : null;
        const paras = els(e, 'p').map(ptext).filter(Boolean);
        let hash = '';
        const blip = first(e, 'blip');
        if(l === 'pic' && blip){ const r = srel[blip.getAttributeNS(R_NS, 'embed')]; hash = await hashPart(zip, r && r.target, cache); imgs.push(hash); }
        const ch = first(e, 'chart');
        if(ch){ const r = srel[ch.getAttributeNS(R_NS, 'id')]; hash = await hashPart(zip, r && r.target, cache); charts.push(hash); }
        shapes.push({name: c ? c.getAttribute('name') : '', paras, geo, hash});
      }
      let notes = [];
      for(const r of Object.values(srel)) if(/\/notesSlide$/.test(r.type) && r.target){
        const nd = await readXml(zip, r.target);
        if(nd) for(const sp of els(nd, 'sp')){
          const ph = first(sp, 'ph'); if(ph && ph.getAttribute('type') === 'body') notes = notes.concat(els(sp, 'p').map(ptext).filter(Boolean));
        }
      }
      const paras = shapes.flatMap(s => s.paras), hidden = doc.documentElement.getAttribute('show') === '0';
      imgs.sort(); charts.sort();
      const s = {paras, notes, imgs, charts, shapes, hidden};
      s.sig = JSON.stringify([paras, imgs, charts, notes, hidden]);
      s.tok = new Set([...paras.flatMap(words), ...imgs.map(h => 'i:' + h), ...charts.map(h => 'c:' + h)]);
      s.idx = slides.length + 1;
      slides.push(s);
    }
    return {slides};
  }
  const EMPTY_SLIDE = {paras:[], notes:[], imgs:[], charts:[], shapes:[], hidden:false, sig:'', tok:new Set(), idx:0};
  function multiDiff(a, b){
    const c = {}; b.forEach(x => c[x] = (c[x] || 0) + 1); a.forEach(x => c[x] = (c[x] || 0) - 1);
    let add = 0, rem = 0; for(const v of Object.values(c)) v > 0 ? add += v : rem -= v;
    return {add, rem};
  }
  function slideDetail(a, b){
    a = a || EMPTY_SLIDE; b = b || EMPTY_SLIDE;
    const d = {text: diffParas(a.paras, b.paras), notes: diffParas(a.notes, b.notes), img: multiDiff(a.imgs, b.imgs), charts: multiDiff(a.charts, b.charts), moved: [], hidden: a.hidden !== b.hidden};
    const pool = a.shapes.slice();
    for(const s of b.shapes){
      const k = s.name + '\u0001' + s.paras.join('\u0002') + '\u0001' + s.hash;
      const j = pool.findIndex(x => x.name + '\u0001' + x.paras.join('\u0002') + '\u0001' + x.hash === k);
      if(j < 0) continue;
      const o = pool.splice(j, 1)[0];
      if(o.geo && s.geo && o.geo.some((v, i) => Math.abs(v - s.geo[i]) > 12700)) d.moved.push(s.name || '(unnamed shape)');
    }
    d.n = changed(d.text) + changed(d.notes) + d.img.add + d.img.rem + d.charts.add + d.charts.rem + d.moved.length + (d.hidden ? 1 : 0);
    return d;
  }
  function comparePptx(A, B){
    const rows = align(A.slides, B.slides, (x, y) => x.sig === y.sig, (x, y) => jac(x.tok, y.tok), .25);
    const rem = rows.filter(r => r.op === '-');
    for(const r of rows) if(r.op === '+'){
      const m = rem.find(x => !x.used && x.a.sig === r.b.sig);
      if(m){ m.used = true; r.op = 'moved'; r.a = m.a; }
    }
    // a slide that was both moved and edited shows up as one removal plus one addition: pair them up
    for(const r of rows) if(r.op === '+'){
      let best = null, bs = .5;
      for(const x of rem) if(!x.used){ const j = jac(x.a.tok, r.b.tok); if(j >= bs){ bs = j; best = x; } }
      if(best){ best.used = true; r.op = '~'; r.a = best.a; }
    }
    const items = [];
    for(const r of rows){
      if(r.op === '-' && r.used) continue;
      const detail = slideDetail(r.a, r.b);
      let kind = r.op === '=' ? 'same' : r.op === '~' ? 'changed' : r.op === '+' ? 'added' : r.op === '-' ? 'removed' : 'moved';
      if(kind === 'same' && detail.n) kind = 'changed';
      items.push({kind, a: r.a, b: r.b, detail});
    }
    return items;
  }
  const slideLabel = it => it.kind === 'added' ? `New slide ${it.b.idx}` : it.kind === 'removed' ? `Slide ${it.a.idx} removed`
    : (it.a.idx === it.b.idx ? `Slide ${it.b.idx}` : `Slide ${it.a.idx} → ${it.b.idx}`);
  const KIND = {same:'identical', changed:'Changed', added:'Added', removed:'Removed', moved:'Moved'};
  const KCLS = {same:'Modified', changed:'Modified', added:'Added', removed:'Removed', moved:'Modified'};
  function pptxMeta(it){
    if(it.kind === 'same') return 'identical';
    if(it.kind === 'added') return 'new slide';
    if(it.kind === 'removed') return 'removed';
    if(it.kind === 'moved') return 'moved' + (it.detail.n ? ' · ' + it.detail.n + ' edit' + (it.detail.n === 1 ? '' : 's') : '');
    return it.detail.n + ' change' + (it.detail.n === 1 ? '' : 's');
  }
  function pptxView(it){
    const d = it.detail, s = it.b || it.a;
    let h = `<div class="od"><h2>${esc(slideLabel(it))} <span class="k ${KCLS[it.kind]}">${KIND[it.kind]}</span></h2><p class="sub">${esc((s.paras[0] || '(no text)').slice(0, 140))}</p>`;
    if(it.kind === 'moved') h += `<section><h3>Position</h3><div class="r">Moved from slide ${it.a.idx} to slide ${it.b.idx}.</div></section>`;
    if(it.kind === 'same') h += `<section><div class="r same">No differences found in text, notes, images, charts or shape positions.</div></section>`;
    if(d.text.some(r => r.op !== '=') || it.kind === 'added' || it.kind === 'removed') h += `<section><h3>Slide text</h3>${rowsHtml(d.text) || '<div class="r none">No text on this slide.</div>'}</section>`;
    if(d.notes.some(r => r.op !== '=')) h += `<section><h3>Speaker notes</h3>${rowsHtml(d.notes)}</section>`;
    const o = [];
    if(d.img.rem) o.push(`${d.img.rem} image${d.img.rem === 1 ? '' : 's'} removed or replaced`);
    if(d.img.add) o.push(`${d.img.add} image${d.img.add === 1 ? '' : 's'} added or replaced`);
    if(d.charts.rem || d.charts.add) o.push('chart content changed');
    if(d.moved.length) o.push(`${d.moved.length} shape${d.moved.length === 1 ? '' : 's'} moved or resized: ${d.moved.slice(0, 6).map(esc).join(', ')}${d.moved.length > 6 ? '…' : ''}`);
    if(d.hidden) o.push('slide ' + ((it.b || EMPTY_SLIDE).hidden ? 'is now hidden' : 'is no longer hidden'));
    if(o.length) h += `<section><h3>Objects and layout</h3>${o.map(x => `<div class="r mod">${x}</div>`).join('')}</section>`;
    return h + '</div>';
  }
  function pptxSummary(items, A, B){
    const c = k => items.filter(i => i.kind === k).length;
    const lines = [`Slides: ${A.slides.length} in A, ${B.slides.length} in B`, `${c('changed')} changed · ${c('added')} added · ${c('removed')} removed · ${c('moved')} moved · ${c('same')} identical`, ''];
    for(const it of items) if(it.kind !== 'same'){
      const bits = [];
      if(it.kind === 'added' || it.kind === 'removed') bits.push(KIND[it.kind].toLowerCase());
      if(it.kind === 'moved') bits.push('moved');
      const d = it.detail, ed = changed(d.text);
      if(it.kind === 'changed' || it.kind === 'moved'){
        if(ed) bits.push(ed + ' text edit' + (ed === 1 ? '' : 's'));
        if(changed(d.notes)) bits.push('notes changed');
        if(d.img.add || d.img.rem) bits.push('image changes');
        if(d.charts.add || d.charts.rem) bits.push('chart changed');
        if(d.moved.length) bits.push(d.moved.length + ' shape(s) moved/resized');
        if(d.hidden) bits.push('visibility changed');
      }
      if(it.kind === 'added' || it.kind === 'removed'){ lines.push(`${slideLabel(it)}${(it.b || it.a).paras[0] ? ': "' + (it.b || it.a).paras[0].slice(0, 60) + '"' : ''}`); continue; }
      lines.push(`${slideLabel(it)}: ${bits.join(', ')}`);
    }
    return lines;
  }

  /* ---------- DOCX ---------- */
  async function parseDocx(zip){
    const doc = await readXml(zip, 'word/document.xml');
    if(!doc) throw new Error('This does not look like a Word file.');
    const body = first(doc, 'body'), paras = [];
    const add = (t, h) => { if(t) paras.push({t, h}); };
    for(const e of Array.from(body.children)){
      if(e.localName === 'p'){
        const ps = first(e, 'pStyle'), sty = ps ? (ps.getAttribute('w:val') || '') : '';
        const m = /^(?:Heading|heading)\s?(\d)/.exec(sty) || (/^Title$/i.test(sty) ? [0, 1] : null);
        add(ptext(e), m ? +m[1] : 0);
      }else if(e.localName === 'tbl'){
        for(const tr of els(e, 'tr')){
          const cells = Array.from(tr.children).filter(c => c.localName === 'tc').map(tc => els(tc, 'p').map(ptext).filter(Boolean).join(' '));
          if(cells.some(Boolean)) add('▦ ' + cells.join(' | '), 0);
        }
      }
    }
    return {paras, tracked: els(doc, 'ins').length + els(doc, 'del').length};
  }
  function compareDocx(A, B){
    const rows = diffParas(A.paras, B.paras); let n = 0, head = '';
    for(const r of rows){
      const p = r.b || r.a; if(p.h) head = p.t;
      if(r.op !== '='){ r.n = ++n; r.ctx = head; }
    }
    return rows;
  }
  function docxView(rows){
    const out = []; let buf = [];
    const cls = r => { const p = r.b || r.a; return p.h ? ' h' + Math.min(3, p.h) : ''; };
    const flush = () => {
      if(buf.length > 7){
        buf.slice(0, 3).forEach(x => out.push(x));
        out.push(`<div class="r gap">… ${buf.length - 6} unchanged paragraphs …</div>`);
        buf.slice(-3).forEach(x => out.push(x));
      }else buf.forEach(x => out.push(x));
      buf = [];
    };
    for(const r of rows){
      if(r.op === '='){ buf.push(`<div class="r same${cls(r)}">${esc(r.a.t)}</div>`); continue; }
      flush();
      const id = `id="chg-${r.n}"`;
      out.push(r.op === '+' ? `<div class="r add${cls(r)}" ${id}>${esc(r.b.t)}</div>` : r.op === '-' ? `<div class="r rem${cls(r)}" ${id}>${esc(r.a.t)}</div>` : `<div class="r mod${cls(r)}" ${id}>${r.html}</div>`);
    }
    flush();
    return `<div class="od"><h2>Document changes</h2><p class="sub">Unchanged passages are collapsed. Click a change on the left to jump to it.</p><section>${out.join('')}</section></div>`;
  }

  /* ---------- XLSX ---------- */
  const colNum = s => { let n = 0; for(const ch of s) n = n * 26 + ch.charCodeAt(0) - 64; return n; };
  async function parseXlsx(zip){
    const wb = await readXml(zip, 'xl/workbook.xml');
    if(!wb) throw new Error('This does not look like an Excel file.');
    const wrel = await rels(zip, 'xl/workbook.xml'), sst = [];
    const sd = await readXml(zip, 'xl/sharedStrings.xml');
    if(sd) for(const si of els(sd, 'si')) sst.push(els(si, 't').filter(t => t.parentNode.localName !== 'rPh').map(t => t.textContent).join(''));
    const sheets = [];
    for(const s of els(wb, 'sheet')){
      const rel = wrel[s.getAttributeNS(R_NS, 'id')]; if(!rel || !rel.target) continue;
      const d = await readXml(zip, rel.target), cells = new Map();
      if(d) for(const c of els(d, 'c')){
        const t = c.getAttribute('t'), v = first(c, 'v'), f = first(c, 'f'), is = first(c, 'is');
        let val = '';
        if(t === 's' && v) val = sst[+v.textContent] ?? '';
        else if(t === 'inlineStr' && is) val = els(is, 't').map(x => x.textContent).join('');
        else if(t === 'b' && v) val = v.textContent === '1' ? 'TRUE' : 'FALSE';
        else if(v) val = v.textContent;
        const fm = f ? f.textContent : '';
        if(val === '' && !fm) continue;
        cells.set(c.getAttribute('r'), {v: val, f: fm});
      }
      sheets.push({name: s.getAttribute('name'), state: s.getAttribute('state') || '', cells});
    }
    return {sheets};
  }
  const isNum = x => x !== '' && /^-?\d*\.?\d+(e[+-]?\d+)?$/i.test(x);
  const sameVal = (a, b) => a === b || (isNum(a) && isNum(b) && Math.abs(+a - +b) <= 1e-9 * Math.max(1, Math.abs(+a)));
  function compareXlsx(A, B){
    const mb = new Map(B.sheets.map(s => [s.name, s])), ma = new Map(A.sheets.map(s => [s.name, s])), items = [];
    const sortAddr = (x, y) => { const px = /^([A-Z]+)(\d+)$/.exec(x), py = /^([A-Z]+)(\d+)$/.exec(y); return (+px[2] - +py[2]) || (colNum(px[1]) - colNum(py[1])); };
    for(const sa of A.sheets){
      const sb = mb.get(sa.name);
      if(!sb){ items.push({name: sa.name, kind: 'removed', changes: [], counts: {add: 0, rem: sa.cells.size, mod: 0}}); continue; }
      const ch = [], cnt = {add: 0, rem: 0, mod: 0};
      for(const addr of new Set([...sa.cells.keys(), ...sb.cells.keys()])){
        const x = sa.cells.get(addr), y = sb.cells.get(addr);
        if(x && !y){ ch.push({addr, kind: 'Removed', x}); cnt.rem++; }
        else if(!x && y){ ch.push({addr, kind: 'Added', y}); cnt.add++; }
        else if(!sameVal(x.v, y.v)){ ch.push({addr, kind: 'Modified', x, y}); cnt.mod++; }
        else if(x.f !== y.f){ ch.push({addr, kind: 'Modified', x, y, fo: true}); cnt.mod++; }
      }
      ch.sort((p, q) => sortAddr(p.addr, q.addr));
      items.push({name: sa.name, kind: ch.length ? 'changed' : 'same', changes: ch, counts: cnt});
    }
    for(const sb of B.sheets) if(!ma.has(sb.name)) items.push({name: sb.name, kind: 'added', changes: [], counts: {add: sb.cells.size, rem: 0, mod: 0}});
    return items;
  }
  const xmeta = it => it.kind === 'same' ? 'identical' : it.kind === 'added' ? 'new sheet' : it.kind === 'removed' ? 'sheet removed' : it.changes.length + ' cell' + (it.changes.length === 1 ? '' : 's');
  function cellHtml(c){ return c ? `${esc(c.v)}${c.f ? `<br><code>=${esc(c.f)}</code>` : ''}` : '<span class="none">empty</span>'; }
  function xlsxView(it){
    let h = `<div class="od"><h2>${esc(it.name)} <span class="k ${KCLS[it.kind]}">${KIND[it.kind]}</span></h2>`;
    if(it.kind === 'added' || it.kind === 'removed'){
      return h + `<p class="sub">This sheet exists only in ${it.kind === 'added' ? 'B' : 'A'} (${it.counts.add + it.counts.rem} non-empty cells).</p></div>`;
    }
    if(!it.changes.length) return h + `<p class="sub">No differences in cell values or formulas.</p></div>`;
    const c = it.counts;
    h += `<p class="sub">${c.mod} modified · ${c.add} added · ${c.rem} removed cells. Number formats and styling are not compared.</p><section><table><thead><tr><th>Cell</th><th>Before (A)</th><th>After (B)</th><th></th></tr></thead><tbody>`;
    for(const x of it.changes.slice(0, 3000)) h += `<tr><td class="c">${x.addr}</td><td>${cellHtml(x.x)}</td><td>${cellHtml(x.y)}</td><td><span class="k ${x.kind}">${x.fo ? 'Formula' : x.kind}</span></td></tr>`;
    h += '</tbody></table>';
    if(it.changes.length > 3000) h += `<div class="r gap">Showing the first 3000 of ${it.changes.length} changes.</div>`;
    return h + '</section></div>';
  }

  /* ---------- UI glue ---------- */
  const NOUN = {pptx: 'Slides', docx: 'Changes', xlsx: 'Sheets'};
  function setSide(side, on){
    const S = side.toUpperCase();
    $('#name' + S).textContent = on ? st.name[side] : 'Drop a file or click to choose';
    $('#drop' + S).classList.toggle('has', !!on);
  }
  function reset(){ st.ext = null; st.p = {a: null, b: null}; st.name = {a: '', b: ''}; st.items = []; st.sum = []; }
  async function load(side, file, rawExt){
    const ext = EXT[rawExt];
    if(typeof S !== 'undefined' && S.kind !== 'office'){ S.run++; resetSides(); }
    S.kind = 'office';
    if(st.ext && st.ext !== ext){ const o = side === 'a' ? 'b' : 'a'; st.p[o] = null; st.name[o] = ''; setSide(o, false); }
    try{
      if(typeof JSZip === 'undefined') throw new Error('The Office reader (vendor/jszip.min.js) did not load.');
      const zip = await JSZip.loadAsync(await file.arrayBuffer());
      st.p[side] = ext === 'pptx' ? await parsePptx(zip) : ext === 'docx' ? await parseDocx(zip) : await parseXlsx(zip);
    }catch(e){
      alert('Could not read ' + file.name + ': ' + (e && e.message || e) + '\n\nPassword-protected or older formats (.ppt, .doc, .xls) are not supported. Save as .pptx, .docx or .xlsx and try again.');
      return;
    }
    st.ext = ext; st.name[side] = file.name; setSide(side, true);
    document.body.classList.add('office');
    $('#sideTitle').textContent = NOUN[ext];
    $('#onlyChanged').parentNode.style.display = ext === 'docx' ? 'none' : '';
    run();
  }
  function swap(){
    [st.p.a, st.p.b] = [st.p.b, st.p.a]; [st.name.a, st.name.b] = [st.name.b, st.name.a];
    setSide('a', st.p.a); setSide('b', st.p.b); run();
  }
  function run(){
    if(!st.p.a || !st.p.b){ $('#pages').innerHTML = ''; $('#pane').innerHTML = ''; return; }
    const A = st.p.a, B = st.p.b;
    $('#viewer').scrollTop = 0;
    if(st.ext === 'pptx'){ st.items = comparePptx(A, B); st.sum = pptxSummary(st.items, A, B); }
    else if(st.ext === 'docx'){
      const rows = compareDocx(A, B); st.rows = rows; st.items = rows.filter(r => r.op !== '=');
      const c = o => st.items.filter(r => r.op === o).length;
      st.sum = [`Paragraphs: ${A.paras.length} in A, ${B.paras.length} in B`, `${c('~')} modified · ${c('+')} added · ${c('-')} removed`];
      if(A.tracked || B.tracked) st.sum.push(`Note: tracked changes found (A: ${A.tracked}, B: ${B.tracked}). The comparison uses the accepted text.`);
      st.sum.push('', ...st.items.slice(0, 200).map(r => `${r.n}. ${r.op === '+' ? 'Added' : r.op === '-' ? 'Removed' : 'Modified'}: ${(T(r.b || r.a)).slice(0, 90)}`));
    }else{
      st.items = compareXlsx(A, B);
      const tot = st.items.reduce((n, i) => n + i.changes.length, 0);
      st.sum = [`Sheets: ${A.sheets.length} in A, ${B.sheets.length} in B`, `${tot} cell change${tot === 1 ? '' : 's'} across ${st.items.filter(i => i.kind === 'changed').length} sheet(s)`, ''];
      for(const i of st.items) if(i.kind !== 'same') st.sum.push(`${i.name}: ${i.kind === 'changed' ? i.counts.mod + ' modified, ' + i.counts.add + ' added, ' + i.counts.rem + ' removed' : i.kind === 'added' ? 'new sheet' : 'sheet removed'}`);
    }
    st.cur = 0;
    if(st.ext !== 'docx'){ const k = st.items.findIndex(i => i.kind !== 'same'); st.cur = k < 0 ? 0 : k; }
    render();
  }
  function render(){ renderList(); renderView(); renderPane(); }
  function renderList(){
    const box = $('#pages'); box.innerHTML = '';
    const only = $('#onlyChanged').checked && st.ext !== 'docx';
    st.items.forEach((it, i) => {
      if(only && it.kind === 'same') return;
      const d = document.createElement('div'); d.className = 'pg' + (i === st.cur ? ' sel' : '');
      let dot, label, meta;
      if(st.ext === 'pptx'){ dot = it.kind; label = slideLabel(it).replace(/^Slide /, '').replace(/^New slide /, '+').replace(/ removed$/, ' ✕'); meta = pptxMeta(it); }
      else if(st.ext === 'xlsx'){ dot = it.kind; label = it.name; meta = xmeta(it); }
      else { dot = it.op === '+' ? 'added' : it.op === '-' ? 'removed' : 'changed'; label = it.n; meta = (it.op === '+' ? 'added · ' : it.op === '-' ? 'removed · ' : '') + T(it.b || it.a).slice(0, 34); }
      d.innerHTML = `<span class="dot ${dot}"></span><span class="n" ${st.ext === 'xlsx' ? 'style="min-width:0;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"' : ''}>${esc(label)}</span><span class="meta">${esc(meta)}</span>`;
      d.onclick = () => { st.cur = i; if(st.ext === 'docx'){ renderList(); const e = document.getElementById('chg-' + it.n); if(e){ e.scrollIntoView({block: 'center', behavior: 'smooth'}); e.classList.remove('flash'); void e.offsetWidth; e.classList.add('flash'); } } else { renderList(); renderView(); $('#viewer').scrollTop = 0; } };
      box.appendChild(d);
    });
    if(!box.children.length) box.innerHTML = '<div class="note">' + (st.ext === 'docx' ? 'No differences found.' : 'Nothing to show.') + '</div>';
  }
  function renderView(){
    const v = $('#viewer'); v.classList.remove('hide-boxes');
    if(st.ext === 'docx'){ v.innerHTML = st.items.length ? docxView(st.rows) : '<div class="empty"><div><h2>No differences found</h2>The text of both documents is identical.</div></div>'; return; }
    const it = st.items[st.cur];
    v.innerHTML = it ? (st.ext === 'pptx' ? pptxView(it) : xlsxView(it)) : '<div class="empty"><div>Nothing to compare.</div></div>';
  }
  function renderPane(){
    $('.tabs').style.display = 'none';
    const p = $('#pane');
    p.innerHTML = `<div class="sumline"><b>Summary</b></div><div class="txt" style="white-space:pre-wrap"></div><button class="btn sumbtn">Copy summary</button>`;
    p.querySelector('.txt').textContent = st.sum.join('\n');
    const b = p.querySelector('button');
    b.onclick = async () => {
      const text = `Compare: ${st.name.a}  →  ${st.name.b}\n\n` + st.sum.join('\n');
      try{ await navigator.clipboard.writeText(text); b.textContent = 'Copied ✓'; }catch(e){ b.textContent = 'Copy failed. Select the text above instead.'; }
      setTimeout(() => b.textContent = 'Copy summary', 1800);
    };
  }
  return {load, swap, reset, render, active: () => st.ext !== null};
})();
