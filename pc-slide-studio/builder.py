"""Build the .pptx: the original Prima Power template (masters, backgrounds, logos, fonts) with designed
content layers on top. Charts and tables are native PowerPoint objects, so they stay editable."""
import base64
import copy
import datetime
import io
import re
import zipfile
from pathlib import Path

from lxml import etree as E
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

import anim
from schema import normalize_deck

TEMPLATE = Path(__file__).parent / 'templates' / 'prima-power.pptx'
FONT = 'Barlow'

# Prima Power brand colours (from the template theme)
NAVY, BLUE, ORANGE, ROYAL, GREY, LIGHT, RED = '003862', '0089CF', 'F58220', '2A5CAA', '636466', 'E6E6E6', 'F04E2A'
INK, WHITE, PALE, SOFT = '1B2A3A', 'FFFFFF', 'EAF4FB', 'F3F6F9'
ACCENTS = [BLUE, NAVY, ORANGE, ROYAL, 'A5A5A5', RED]

# Content canvas on the "Slide Standard" layout (the logo sits above it, so the full width is usable)
COLUMN_ROWS = 6
X0, W = 911225, 10_369_550
Y0, Y1 = 1_480_000, 6_150_000
BANNER_H = 560_000

LAYOUT_NAMES = {'cover': 'Cover Slide', 'section': 'Section Cover Blu', 'quote': 'Section Cover Blu', 'closing': 'Slide Finale'}
STANDARD = 'Slide Standard'


def rgb(h):
    return RGBColor.from_string(h)


# ---------------------------------------------------------------- text fitting

def lines_for(text, width, pt, bold=False):
    cpl = max(4, int((width / 12700) / (pt * (0.55 if bold else 0.51))))
    return max(1, -(-int(len(text) * 1.06) // cpl))


def fit(texts, width, height, max_pt, min_pt, bold=False, spacing=1.22, gap_pt=0, indent=0):
    """Largest font size (pt) at which the texts are estimated to fit the box."""
    texts = [t for t in texts if t is not None] or ['']
    for pt in range(max_pt, min_pt - 1, -1):
        used = sum(lines_for(t, width - indent, pt, bold) for t in texts) * pt * spacing + gap_pt * (len(texts) - 1)
        if used * 12700 <= height:
            return pt
    return min_pt


# ---------------------------------------------------------------- low level shape helpers

def _effects(shape, shadow):
    sp_pr = shape._element.spPr
    for old in sp_pr.findall(qn('a:effectLst')):
        sp_pr.remove(old)
    xml = ('<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:outerShdw blurRad="152400" dist="38100" dir="5400000" '
           'algn="t" rotWithShape="0"><a:srgbClr val="003862"><a:alpha val="20000"/></a:srgbClr></a:outerShdw></a:effectLst>') if shadow else \
        '<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>'
    sp_pr.append(E.fromstring(xml))


def rect(shapes, x, y, w, h, fill, shadow=False, radius=None, line=None):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    s = shapes.add_shape(kind, Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)))
    if radius:
        s.adjustments[0] = radius
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(0.75)
    else:
        s.line.fill.background()
    _effects(s, shadow)
    return s


def oval(shapes, x, y, d, fill, text='', size=18, color=WHITE):
    s = shapes.add_shape(MSO_SHAPE.OVAL, Emu(int(x)), Emu(int(y)), Emu(int(d)), Emu(int(d)))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    s.line.color.rgb = rgb(WHITE)
    s.line.width = Pt(3)
    _effects(s, True)
    if text:
        tf = s.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        fill_paragraphs(tf, [text], size=size, color=color, bold=True, align='c')
    return s


def card(shapes, x, y, w, h, accent=None, top=False):
    """White raised card with an optional coloured edge strip (left, or top when top=True)."""
    c = rect(shapes, x, y, w, h, WHITE, shadow=True, radius=0.025)
    if accent:
        if top:
            rect(shapes, x, y, w, 80_000, accent)
        else:
            rect(shapes, x, y, 80_000, h, accent)
    return c


def _ppr(p, bullet, gap_pt, indent):
    """Hand-written paragraph properties in schema order (lnSpc, spcBef, bullet*)."""
    p_pr = p._p.get_or_add_pPr()
    for child in list(p_pr):
        p_pr.remove(child)
    a = 'http://schemas.openxmlformats.org/drawingml/2006/main'

    def sub(tag, **attrs):
        el = E.SubElement(p_pr, '{%s}%s' % (a, tag))
        for k, v in attrs.items():
            el.set(k, str(v))
        return el
    ln = sub('lnSpc')
    E.SubElement(ln, '{%s}spcPct' % a).set('val', '100000')
    sb = sub('spcBef')
    E.SubElement(sb, '{%s}spcPts' % a).set('val', str(int(gap_pt * 100)))
    if bullet:
        p_pr.set('marL', str(indent))
        p_pr.set('indent', str(-indent))
        clr = sub('buClr')
        E.SubElement(clr, '{%s}srgbClr' % a).set('val', ORANGE)
        sub('buSzPct', val='75000')
        sub('buFont', typeface='Arial')
        sub('buChar', char='■')
    else:
        p_pr.set('marL', '0')
        p_pr.set('indent', '0')
        sub('buNone')


LEAD = re.compile(r'^(.{3,48}?)(\s[—–]\s|:\s)(.+)$')


def fill_paragraphs(tf, paras, size=16, color=INK, bold=False, align='l', bullet=False, gap=0, italic=False, caps=False, lead=False):
    """paras: strings or dicts {'text', 'size', 'color', 'bold', 'caps', 'gap'} overriding the defaults."""
    tf.clear()
    for index, item in enumerate(paras):
        spec = item if isinstance(item, dict) else {'text': item}
        p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        sz = spec.get('size', size)
        _ppr(p, bullet and not spec.get('nobullet'), spec.get('gap', gap) if index else 0, int(sz * 12700 * 1.1))
        p.alignment = {'l': PP_ALIGN.LEFT, 'c': PP_ALIGN.CENTER, 'r': PP_ALIGN.RIGHT}[spec.get('align', align)]
        text = spec['text']
        parts = [(text, spec.get('bold', bold))]
        m = LEAD.match(text) if lead and not spec.get('bold') else None
        if m:
            parts = [(m.group(1) + (':' if m.group(2).strip() == ':' else ''), True), (' ' + m.group(3) if m.group(2).strip() == ':' else ' — ' + m.group(3), False)]
        for chunk, is_bold in parts:
            r = p.add_run()
            r.text = chunk
            f = r.font
            f.name, f.size, f.bold, f.italic = FONT, Pt(sz), is_bold, spec.get('italic', italic)
            f.color.rgb = rgb(spec.get('color', color))
            if spec.get('caps', caps):
                r._r.get_or_add_rPr().set('spc', '150')


def text(shapes, x, y, w, h, paras, anchor='t', **kw):
    tb = shapes.add_textbox(Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {'t': MSO_ANCHOR.TOP, 'm': MSO_ANCHOR.MIDDLE, 'b': MSO_ANCHOR.BOTTOM}[anchor]
    fill_paragraphs(tf, paras if isinstance(paras, list) else [paras], **kw)
    return tb


# ---------------------------------------------------------------- slide context

class Ctx:
    """Everything a renderer needs for one slide, plus the animation steps it records."""

    def __init__(self, slide, spec):
        self.slide, self.spec, self.steps = slide, spec, []
        self.top, self.bottom = Y0, Y1

    @property
    def area(self):
        return X0, self.top, W, self.bottom - self.top

    def step(self, shapes, effect='fade'):
        targets = []
        for s in shapes if isinstance(shapes, (list, tuple)) else [shapes]:
            targets.append((s.shape_id, None, _kind(s)))
        self.steps.append({'targets': targets, 'effect': effect})

    def para_steps(self, shape, count):
        for i in range(count):
            self.steps.append({'targets': [(shape.shape_id, i, 'sp')], 'effect': 'fade'})


def _kind(s):
    if getattr(s, 'has_chart', False) and s.has_chart:
        return 'chart'
    if s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
        return 'sp'
    if s.shape_type in (MSO_SHAPE_TYPE.TEXT_BOX, MSO_SHAPE_TYPE.PLACEHOLDER):
        return 'txt'
    return 'other'


def to_back(slide, shape):
    tree = slide.shapes._spTree
    tree.remove(shape._element)
    tree.insert(2, shape._element)


def drop_placeholders(slide):
    """Remove every placeholder except the title, so empty prompts never show in edit mode."""
    for ph in list(slide.placeholders):
        if ph.placeholder_format.type not in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
            ph._element.getparent().remove(ph._element)


def set_title(slide, title, max_pt=30, min_pt=20, width=9_000_000):
    t = slide.shapes.title
    if t is None:
        return None
    pt = fit([title], width, 700_000, max_pt, min_pt, bold=True, spacing=1.15)
    fill_paragraphs(t.text_frame, [title], size=pt, color=INK, bold=True)
    return t


def add_slide_number(slide, layout):
    for ph in layout.placeholders:
        if ph.placeholder_format.type == PP_PLACEHOLDER.SLIDE_NUMBER:
            el = copy.deepcopy(ph._element)
            ids = [int(i) for i in slide.shapes._spTree.xpath('.//p:cNvPr/@id')]
            el.nvSpPr.cNvPr.set('id', str(max(ids + [1]) + 1))
            slide.shapes._spTree.append(el)


def takeaway_banner(ctx):
    t = ctx.spec.get('takeaway')
    if not t:
        return
    y = Y1 - BANNER_H
    g = ctx.slide.shapes.add_group_shape()
    rect(g.shapes, X0, y, W, BANNER_H, NAVY, shadow=True, radius=0.08)
    rect(g.shapes, X0, y, 90_000, BANNER_H, ORANGE)
    pt = fit([t], W - 560_000, BANNER_H - 120_000, 18, 12, bold=True, spacing=1.15)
    text(g.shapes, X0 + 330_000, y, W - 560_000, BANNER_H, [t], anchor='m', size=pt, color=WHITE, bold=True)
    ctx.bottom = y - 170_000
    ctx._banner = g


def finish_banner(ctx):
    if getattr(ctx, '_banner', None) is not None:
        ctx.step(ctx._banner)


# ---------------------------------------------------------------- pictures

def picture_bytes(data_url):
    from PIL import Image
    raw = base64.b64decode(data_url.split(',', 1)[1])
    png = raw[:8] == b'\x89PNG\r\n\x1a\n'
    if not png and raw[:3] != b'\xff\xd8\xff':
        raise ValueError('Image slides need a PNG or JPEG image.')
    im = Image.open(io.BytesIO(raw))
    im.load()
    im.thumbnail((2000, 2000), Image.LANCZOS)
    buf = io.BytesIO()
    if png:
        im.save(buf, format='PNG')
    else:
        im.convert('RGB').save(buf, format='JPEG', quality=88)
    return buf.getvalue(), im.size


def add_picture_fit(shapes, data_url, x, y, w, h):
    data, (iw, ih) = picture_bytes(data_url)
    scale = min(w / iw, h / ih)
    pw, ph = int(iw * scale), int(ih * scale)
    return shapes.add_picture(io.BytesIO(data), Emu(int(x + (w - pw) / 2)), Emu(int(y + (h - ph) / 2)), Emu(pw), Emu(ph))


# ---------------------------------------------------------------- renderers

def render_cover(ctx):
    s, slide = ctx.spec, ctx.slide
    ph = slide.placeholders[1]
    title_pt = fit([s['title']], 6_300_000, 600_000, 24, 16, bold=True, spacing=1.15)
    paras = [{'text': s['title'], 'size': title_pt, 'bold': True, 'color': WHITE}]
    if s['subtitle']:
        paras.append({'text': s['subtitle'], 'size': 14, 'color': 'BFE3F7', 'gap': 4})
    ph.text_frame.word_wrap = True
    fill_paragraphs(ph.text_frame, paras)


def render_section(ctx):
    title = ctx.spec['title']
    t = ctx.slide.shapes.title
    pt = fit([title], 6_300_000, 1_500_000, 36, 20, bold=True, spacing=1.15)
    fill_paragraphs(t.text_frame, [title], size=pt, color=WHITE, bold=True)


def render_quote(ctx):
    s = ctx.spec
    q = '“' + s['quote'] + '”'
    pt = fit([q], 6_300_000, 1_450_000, 30, 16, spacing=1.2)
    paras = [{'text': q, 'size': pt, 'color': WHITE, 'bold': False}]
    if s['author']:
        paras.append({'text': '— ' + s['author'], 'size': 16, 'color': ORANGE, 'bold': True, 'gap': 10})
    fill_paragraphs(ctx.slide.shapes.title.text_frame, paras)


def render_content(ctx):
    s, slide = ctx.spec, ctx.slide
    bullets = s['bullets'] or ['']
    ph = next((p for p in slide.placeholders if p.placeholder_format.type == PP_PLACEHOLDER.BODY), None)
    pad = 420_000
    inner_w = W - 2 * pad
    pt = fit(bullets, inner_w, Y1 - Y0 - 2 * pad, 24, 15, gap_pt=14, indent=330_000)
    need = sum(lines_for(b, inner_w - 330_000, pt) for b in bullets) * pt * 1.22 + 14 * (len(bullets) - 1)
    h = max(2_300_000, min(Y1 - Y0, int(need * 12700) + 2 * pad))
    g = slide.shapes.add_group_shape()
    card(g.shapes, X0, Y0, W, h, accent=ORANGE)
    to_back(slide, g)
    ph.left, ph.top, ph.width, ph.height = Emu(X0 + pad), Emu(Y0 + pad), Emu(inner_w), Emu(h - 2 * pad)
    ph.text_frame.word_wrap = True
    ph.text_frame.auto_size = MSO_AUTO_SIZE.NONE
    ph.text_frame.vertical_anchor = MSO_ANCHOR.TOP
    fill_paragraphs(ph.text_frame, bullets, size=pt, bullet=True, gap=14, lead=True)
    ctx.step(g)
    ctx.para_steps(ph, len(bullets))


def render_agenda(ctx):
    items = ctx.spec['bullets'][:8] or ['']
    takeaway_banner(ctx)
    x, y, w, h = ctx.area
    cols = 1 if len(items) <= 4 else 2
    rows = -(-len(items) // cols)
    gap = 170_000
    cw = (w - gap * (cols - 1)) / cols
    rh = min(820_000, (h - gap * (rows - 1)) / rows)
    top = y + (h - (rh * rows + gap * (rows - 1))) / 2 if h > rh * rows else y
    for i, item in enumerate(items):
        cx = x + (i // rows) * (cw + gap)
        cy = top + (i % rows) * (rh + gap)
        g = ctx.slide.shapes.add_group_shape()
        card(g.shapes, cx, cy, cw, rh)
        d = min(rh - 220_000, 560_000)
        oval(g.shapes, cx + 200_000, cy + (rh - d) / 2, d, ACCENTS[i % 2], f'{i + 1:02d}', size=16)
        pt = fit([item], cw - d - 560_000, rh - 140_000, 22, 14, spacing=1.15)
        text(g.shapes, cx + d + 400_000, cy, cw - d - 560_000, rh, [item], anchor='m', size=pt, bold=True)
        ctx.step(g)
    finish_banner(ctx)


def bullet_block(shapes, x, y, w, h, items, max_pt=18, color=INK):
    pt = fit(items, w, h, max_pt, 12, gap_pt=9, indent=260_000)
    return text(shapes, x, y, w, h, items, size=pt, color=color, bullet=True, gap=9, lead=True)


def render_two_column(ctx):
    s = ctx.spec
    takeaway_banner(ctx)
    x, y, w, h = ctx.area
    gap = 260_000
    cw = (w - gap) / 2
    longest = [b for col in s['columns'] for b in col['bullets']] or ['']
    need = sum(lines_for(b, cw - 520_000 - 260_000, 18) for b in longest[:COLUMN_ROWS]) * 18 * 1.22 * 12700 / 2 + 1_000_000
    h = int(max(2_900_000, min(h, need * 1.5)))
    for i, col in enumerate(s['columns']):
        cx = x + i * (cw + gap)
        g = ctx.slide.shapes.add_group_shape()
        card(g.shapes, cx, y, cw, h)
        rect(g.shapes, cx, y, cw, 640_000, NAVY if i == 0 else BLUE)
        pt = fit([col['title']], cw - 440_000, 540_000, 22, 14, bold=True, spacing=1.1)
        text(g.shapes, cx + 260_000, y, cw - 440_000, 640_000, [col['title']], anchor='m', size=pt, color=WHITE, bold=True)
        bullet_block(g.shapes, cx + 260_000, y + 640_000 + 230_000, cw - 520_000, h - 640_000 - 430_000, col['bullets'] or [''])
        ctx.step(g)
    finish_banner(ctx)


def render_stats(ctx):
    items = ctx.spec['stats']
    takeaway_banner(ctx)
    x, y, w, h = ctx.area
    n = len(items)
    gap = 240_000
    cw = (w - gap * (n - 1)) / n
    ch = min(h, 3_000_000)
    cy = y + (h - ch) / 2
    for i, st in enumerate(items):
        cx = x + i * (cw + gap)
        accent = ACCENTS[i % 4]
        g = ctx.slide.shapes.add_group_shape()
        card(g.shapes, cx, cy, cw, ch, accent=accent, top=True)
        pad = 240_000
        vpt = fit([st['value']], cw - 2 * pad, 1_000_000, 58, 26, bold=True, spacing=1.05)
        text(g.shapes, cx + pad, cy + 330_000, cw - 2 * pad, 1_050_000, [st['value']], anchor='m', size=vpt, color=accent if accent != 'A5A5A5' else NAVY, bold=True)
        rect(g.shapes, cx + pad, cy + 1_480_000, 560_000, 36_000, ORANGE)
        lpt = fit([st['label']], cw - 2 * pad, 700_000, 20, 13, bold=True, spacing=1.15)
        text(g.shapes, cx + pad, cy + 1_650_000, cw - 2 * pad, 760_000, [st['label']], size=lpt, bold=True)
        if st['note']:
            npt = fit([st['note']], cw - 2 * pad, ch - 2_450_000, 16, 11, spacing=1.2)
            text(g.shapes, cx + pad, cy + 2_330_000, cw - 2 * pad, ch - 2_400_000, [st['note']], size=npt, color=GREY)
        ctx.step(g)
    finish_banner(ctx)


def render_timeline(ctx):
    steps = ctx.spec['steps']
    takeaway_banner(ctx)
    x, y, w, h = ctx.area
    n = len(steps)
    gap = 170_000
    cw = (w - gap * (n - 1)) / n
    d = 620_000
    card_top = y + d + 330_000
    ch = min(y + h - card_top, 2_000_000)
    block = (card_top - y) + ch
    y0 = y + max(0, (h - block) / 2)
    cy = y0 + d / 2
    line = ctx.slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Emu(int(x + cw / 2)), Emu(int(cy)), Emu(int(x + w - cw / 2)), Emu(int(cy)))
    line.line.color.rgb = rgb('B9C7D6')
    line.line.width = Pt(3)
    ctx.step(line, 'wipe')
    for i, st in enumerate(steps):
        cx = x + i * (cw + gap)
        accent = ORANGE if i == n - 1 else (BLUE if i % 2 == 0 else NAVY)
        g = ctx.slide.shapes.add_group_shape()
        oval(g.shapes, cx + cw / 2 - d / 2, y0, d, accent, str(i + 1), size=20)
        top = y0 + d + 330_000 - (card_top - y0 - d - 330_000) * 0
        card(g.shapes, cx, top, cw, ch, accent=accent, top=True)
        pad = 150_000
        tpt = fit([st['title']], cw - 2 * pad, 720_000, 18, 12, bold=True, spacing=1.12)
        text(g.shapes, cx + pad, top + 230_000, cw - 2 * pad, 760_000, [st['title']], size=tpt, color=NAVY, bold=True)
        if st['text']:
            bpt = fit([st['text']], cw - 2 * pad, ch - 1_000_000, 16, 11, spacing=1.2)
            text(g.shapes, cx + pad, top + 880_000, cw - 2 * pad, ch - 960_000, [st['text']], size=bpt, color=GREY)
        ctx.step(g)
    finish_banner(ctx)


def render_table(ctx):
    t = ctx.spec['table']
    takeaway_banner(ctx)
    x, y, w, h = ctx.area
    cols, rows = len(t['header']), len(t['rows']) + 1
    rh = int(min(680_000, h / rows))
    gf = ctx.slide.shapes.add_table(rows, cols, Emu(x), Emu(int(y)), Emu(w), Emu(rh * rows))
    tbl = gf.table
    tbl.first_row, tbl.horz_banding = True, False
    weights = [max(8, max(len(str(r[c])) for r in [t['header']] + t['rows'])) ** 0.8 for c in range(cols)]
    total = sum(weights)
    for c in range(cols):
        tbl.columns[c].width = Emu(int(w * weights[c] / total))
    for r in range(rows):
        tbl.rows[r].height = Emu(rh)
    pt = fit([max(sum(([t['header']] + t['rows']), []), key=len)], int(w / cols) - 240_000, rh - 100_000, 18, 11, spacing=1.15)
    num = re.compile(r'^[\s\-+$£€]*[\d.,]+\s*[%a-zA-Z$£€]{0,4}$')
    for r in range(rows):
        for c in range(cols):
            val = t['header'][c] if r == 0 else t['rows'][r - 1][c]
            cell = tbl.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(NAVY if r == 0 else (WHITE if r % 2 else SOFT))
            cell.margin_left = cell.margin_right = Emu(120_000)
            cell.margin_top = cell.margin_bottom = Emu(40_000)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            right = r > 0 and bool(num.match(val))
            fill_paragraphs(cell.text_frame, [val], size=pt + (1 if r == 0 else 0), color=WHITE if r == 0 else INK, bold=(r == 0 or c == 0), align='r' if right else 'l')
    ctx.step(gf, 'wipe')
    finish_banner(ctx)


def number_format(chart, unit):
    values = [v for s in chart['series'] for v in s['values'] if v is not None]
    base = '#,##0' if all(float(v).is_integer() for v in values) else '#,##0.0'
    if not unit:
        return base
    if unit in '$£€':
        return f'"{unit}"{base}'
    return f'{base}"{unit}"' if unit.startswith(('%', 'k', 'm', 'h', 'd', 'w')) or len(unit) <= 3 else f'{base}" {unit}"'


def render_chart(ctx):
    s = ctx.spec
    ch = s['chart']
    takeaway_banner(ctx)
    x, y, w, h = ctx.area
    insights = s['bullets']
    panel_w = 3_500_000 if insights else 0
    gap = 240_000 if insights else 0
    cw = w - panel_w - gap
    g = ctx.slide.shapes.add_group_shape()
    card(g.shapes, x, y, cw, h)
    top = 200_000
    if ch.get('title'):
        text(g.shapes, x + 300_000, y + 150_000, cw - 600_000, 360_000, [ch['title']], size=15, color=GREY, bold=True)
        top = 600_000
    ctx.step(g)
    kinds = {'column': XL_CHART_TYPE.COLUMN_CLUSTERED, 'bar': XL_CHART_TYPE.BAR_CLUSTERED, 'line': XL_CHART_TYPE.LINE_MARKERS,
             'pie': XL_CHART_TYPE.PIE, 'doughnut': XL_CHART_TYPE.DOUGHNUT}
    data = CategoryChartData()
    data.categories = ch['categories']
    for ser in ch['series']:
        data.add_series(ser['name'], ser['values'])
    frame = ctx.slide.shapes.add_chart(kinds[ch['type']], Emu(int(x + 150_000)), Emu(int(y + top)), Emu(int(cw - 300_000)), Emu(int(h - top - 150_000)), data)
    style_chart(frame.chart, ch)
    ctx.step(frame, 'wipe')
    if insights:
        px = x + cw + gap
        g2 = ctx.slide.shapes.add_group_shape()
        rect(g2.shapes, px, y, panel_w, h, NAVY, shadow=True, radius=0.025)
        rect(g2.shapes, px, y, panel_w, 80_000, ORANGE)
        text(g2.shapes, px + 280_000, y + 280_000, panel_w - 560_000, 300_000, ['KEY POINTS'], size=12, color=ORANGE, bold=True, caps=True)
        pt = fit(insights, panel_w - 560_000, h - 1_000_000, 20, 12, gap_pt=12, indent=260_000)
        text(g2.shapes, px + 280_000, y + 700_000, panel_w - 560_000, h - 900_000, insights, size=pt, color=WHITE, bullet=True, gap=12, lead=True)
        ctx.step(g2)
    finish_banner(ctx)


def style_chart(chart, ch):
    kind = ch['type']
    pie = kind in ('pie', 'doughnut')
    chart.has_title = False
    chart.font.size = Pt(13)
    chart.font.name = FONT
    chart.font.color.rgb = rgb(INK)
    many = len(ch['series']) * len(ch['categories']) > 18
    chart.has_legend = pie or len(ch['series']) > 1
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM if not pie else XL_LEGEND_POSITION.RIGHT
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(13)
    plot = chart.plots[0]
    fmt = number_format(ch, ch['unit'])
    if not many or pie:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.font.size = Pt(13)
        dl.font.bold = True
        if pie:
            dl.show_percentage, dl.show_value = True, False
            dl.number_format, dl.number_format_is_linked = '0%', False
            dl.font.color.rgb = rgb(WHITE if kind == 'doughnut' else INK)
            if kind == 'pie':
                dl.position = XL_LABEL_POSITION.OUTSIDE_END
        else:
            dl.number_format, dl.number_format_is_linked = fmt, False
            dl.position = XL_LABEL_POSITION.ABOVE if kind == 'line' else XL_LABEL_POSITION.OUTSIDE_END
    if pie:
        plot.vary_by_categories = True
        for i in range(len(ch['categories'])):
            pt = plot.series[0].points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = rgb(ACCENTS[i % len(ACCENTS)])
            pt.format.line.color.rgb = rgb(WHITE)
        return
    plot.vary_by_categories = False
    if kind in ('column', 'bar'):
        plot.gap_width = 55
        plot.overlap = -8 if len(ch['series']) > 1 else 0
    for i, ser in enumerate(plot.series):
        color = rgb(ACCENTS[i % len(ACCENTS)])
        if kind == 'line':
            ser.format.line.color.rgb = color
            ser.format.line.width = Pt(3.5)
            ser.smooth = False
            ser.marker.style = XL_MARKER_STYLE.CIRCLE
            ser.marker.size = 9
            ser.marker.format.fill.solid()
            ser.marker.format.fill.fore_color.rgb = color
            ser.marker.format.line.color.rgb = rgb(WHITE)
        else:
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = color
    cat, val = chart.category_axis, chart.value_axis
    cat.tick_labels.font.size = Pt(13)
    cat.format.line.color.rgb = rgb('B9C7D6')
    cat.has_major_gridlines = False
    if kind == 'bar':
        cat.reverse_order = True
        val.minimum_scale = 0
        val.visible = False
        val.has_major_gridlines = False
    else:
        val.tick_labels.font.size = Pt(12)
        if kind == 'column':
            val.minimum_scale = 0
            if ch['unit'] == '%' and all(v is None or v <= 100 for s in ch['series'] for v in s['values']):
                val.maximum_scale = 100
        val.tick_labels.font.color.rgb = rgb(GREY)
        val.tick_labels.number_format, val.tick_labels.number_format_is_linked = fmt, False
        val.format.line.fill.background()
        val.has_major_gridlines = True
        val.major_gridlines.format.line.color.rgb = rgb('E1E8EF')
        val.major_gridlines.format.line.width = Pt(0.75)


def render_image(ctx):
    s = ctx.spec
    caption = s['subtitle']
    takeaway_banner(ctx)
    x, y, w, h = ctx.area
    cap_h = 380_000 if caption else 0
    g = ctx.slide.shapes.add_group_shape()
    card(g.shapes, x, y, w, h)
    pad = 160_000
    add_picture_fit(g.shapes, s['image'], x + pad, y + pad, w - 2 * pad, h - 2 * pad - cap_h)
    if caption:
        text(g.shapes, x + pad, y + h - cap_h - pad + 60_000, w - 2 * pad, cap_h, [caption], anchor='m', size=14, color=GREY, italic=True, align='c')
    ctx.step(g)
    finish_banner(ctx)


def render_image_text(ctx):
    s = ctx.spec
    takeaway_banner(ctx)
    x, y, w, h = ctx.area
    gap = 240_000
    iw = w * 0.56
    g = ctx.slide.shapes.add_group_shape()
    card(g.shapes, x, y, iw, h)
    add_picture_fit(g.shapes, s['image'], x + 140_000, y + 140_000, iw - 280_000, h - 280_000)
    ctx.step(g)
    tx = x + iw + gap
    tw = w - iw - gap
    g2 = ctx.slide.shapes.add_group_shape()
    card(g2.shapes, tx, y, tw, h, accent=ORANGE)
    items = s['bullets'] or ['']
    bullet_block(g2.shapes, tx + 330_000, y + 300_000, tw - 560_000, h - 600_000, items, max_pt=20)
    ctx.step(g2)
    finish_banner(ctx)


RENDERERS = {
    'cover': render_cover, 'section': render_section, 'quote': render_quote, 'content': render_content, 'agenda': render_agenda,
    'two_column': render_two_column, 'stats': render_stats, 'timeline': render_timeline, 'table': render_table,
    'chart': render_chart, 'image': render_image, 'image_text': render_image_text, 'closing': lambda ctx: None,
}


# ---------------------------------------------------------------- deck assembly

def strip_template_slides(prs):
    ids = prs.slides._sldIdLst
    for sld in list(ids):
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)
    pres = prs.part._element
    for child in list(pres):
        if E.QName(child).localname in ('custShowLst', 'extLst'):   # sections reference the removed slides
            pres.remove(child)


def refresh_cover_date(prs):
    today = datetime.date.today().strftime('%d/%m/%Y')
    for layout in prs.slide_layouts:
        for el in layout._element.xpath('.//a:fld[@type="datetime1" or @type="datetime"]/a:t'):
            el.text = today


def make_pptx(deck):
    deck = normalize_deck(deck, strict=True)
    prs = Presentation(str(TEMPLATE))
    strip_template_slides(prs)
    refresh_cover_date(prs)
    layouts = {l.name: l for l in prs.slide_layouts}
    for n, spec in enumerate(deck['slides'], 1):
        layout = layouts[LAYOUT_NAMES.get(spec['layout'], STANDARD)]
        slide = prs.slides.add_slide(layout)
        ctx = Ctx(slide, spec)
        standard = layout.name == STANDARD
        if standard:
            set_title(slide, spec['title'] or ' ')
            if spec['layout'] != 'content':
                drop_placeholders(slide)
            add_slide_number(slide, layout)
        RENDERERS[spec['layout']](ctx)
        if spec['notes']:
            slide.notes_slide.notes_text_frame.text = spec['notes']
        if deck['transition'] != 'none':
            anim.set_transition(slide, deck['transition'])
        if deck['animations'] and ctx.steps:
            anim.add_build(slide, ctx.steps)
    prs.core_properties.title = deck['title'] or 'Presentation'
    prs.core_properties.author = 'PC Slide Studio'
    out = io.BytesIO()
    prs.save(out)
    out.seek(0)
    return out
