"""Deck schema: every slide the AI or the editor can produce is normalised here.

`normalize_deck(raw, strict=False)` is the only entry point. Lenient mode (AI output)
truncates and degrades; strict mode (export from the editor) rejects over-long text so
users are told instead of silently losing words.
"""
import re

LAYOUTS = ['cover', 'agenda', 'section', 'content', 'two_column', 'stats', 'chart',
           'timeline', 'table', 'quote', 'image', 'image_text', 'closing']
CHART_TYPES = ['column', 'bar', 'line', 'pie', 'doughnut']
TRANSITIONS = ['fade', 'push', 'wipe', 'none']

MAX_SLIDES = 40
TITLE_MAX = 140
BULLET_MAX = 220
BULLETS_MAX = 6
SUBTITLE_MAX = 120
TAKEAWAY_MAX = 160
NOTES_MAX = 1500
QUOTE_MAX = 300
AUTHOR_MAX = 80
STATS_RANGE = (2, 4)
STEPS_RANGE = (3, 6)
COLUMN_BULLETS_MAX = 5
TABLE_COLS_MAX = 6
TABLE_ROWS_MAX = 8
CELL_MAX = 60
CHART_CATEGORIES_MAX = 12
CHART_SERIES_MAX = 4
IMAGE_MAX_CHARS = 8_000_000  # base64 text, roughly 6 MB of picture

IMAGE_PREFIXES = ('data:image/png;base64,', 'data:image/jpeg;base64,')

LIMITS = {  # sent to the browser so the editor and server agree
    'title': TITLE_MAX, 'bullet': BULLET_MAX, 'bullets': BULLETS_MAX, 'subtitle': SUBTITLE_MAX,
    'takeaway': TAKEAWAY_MAX, 'notes': NOTES_MAX, 'quote': QUOTE_MAX, 'author': AUTHOR_MAX,
    'stats': list(STATS_RANGE), 'steps': list(STEPS_RANGE), 'columnBullets': COLUMN_BULLETS_MAX,
    'tableCols': TABLE_COLS_MAX, 'tableRows': TABLE_ROWS_MAX, 'cell': CELL_MAX,
    'categories': CHART_CATEGORIES_MAX, 'series': CHART_SERIES_MAX, 'slides': MAX_SLIDES,
}


def _text(value, limit, strict, what):
    if value is None:
        return ''
    if not isinstance(value, (str, int, float)):
        if strict:
            raise ValueError(f'{what} must be text.')
        return ''
    value = re.sub(r'[ \t]+', ' ', str(value)).strip()
    if len(value) > limit:
        if strict:
            raise ValueError(f'{what} must be {limit} characters or fewer.')
        value = value[:limit - 1].rstrip() + '…'
    return value


def _lines(value, count, limit, strict, what):
    if isinstance(value, str):
        value = [v for v in value.split('\n')]
    if not isinstance(value, list):
        return []
    out = [_text(v, limit, strict, what) for v in value]
    out = [v for v in out if v]
    if len(out) > count:
        if strict:
            raise ValueError(f'Use up to {count} items per list ({what}).')
        out = out[:count]
    return out


def _number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = re.sub(r'[^0-9.\-]', '', v.replace(',', ''))
        try:
            return float(s) if s not in ('', '-', '.') else None
        except ValueError:
            return None
    return None


def _chart(raw, strict):
    if not isinstance(raw, dict):
        return None
    ctype = raw.get('type') if raw.get('type') in CHART_TYPES else 'column'
    cats = raw.get('categories')
    series = raw.get('series')
    if not isinstance(cats, list) or not isinstance(series, list):
        return None
    cats = [_text(c, 40, strict, 'Chart category') for c in cats][:CHART_CATEGORIES_MAX]
    out = []
    for s in series[:CHART_SERIES_MAX]:
        if not isinstance(s, dict) or not isinstance(s.get('values'), list):
            continue
        vals = [_number(v) for v in s['values']][:len(cats)]
        vals += [None] * (len(cats) - len(vals))
        if any(v is not None for v in vals):
            out.append({'name': _text(s.get('name'), 40, strict, 'Series name') or f'Series {len(out) + 1}', 'values': vals})
    if len(cats) < 2 or not out:
        return None
    if ctype in ('pie', 'doughnut'):
        out = out[:1]
    return {'type': ctype, 'categories': cats, 'series': out, 'unit': _text(raw.get('unit'), 8, strict, 'Chart unit'),
            'title': _text(raw.get('title'), 80, strict, 'Chart title')}


def _stats(raw, strict):
    if not isinstance(raw, list):
        return []
    out = []
    for s in raw[:STATS_RANGE[1]]:
        if isinstance(s, dict):
            item = {'value': _text(s.get('value'), 14, strict, 'Stat value'), 'label': _text(s.get('label'), 60, strict, 'Stat label'),
                    'note': _text(s.get('note'), 100, strict, 'Stat note')}
            if item['value']:
                out.append(item)
    return out


def _steps(raw, strict):
    if not isinstance(raw, list):
        return []
    out = []
    for s in raw[:STEPS_RANGE[1]]:
        if isinstance(s, dict):
            item = {'title': _text(s.get('title'), 50, strict, 'Step title'), 'text': _text(s.get('text'), 140, strict, 'Step text')}
            if item['title'] or item['text']:
                out.append(item)
    return out


def _columns(raw, strict):
    if not isinstance(raw, list):
        return []
    out = []
    for c in raw[:2]:
        if isinstance(c, dict):
            out.append({'title': _text(c.get('title'), 50, strict, 'Column title'),
                        'bullets': _lines(c.get('bullets'), COLUMN_BULLETS_MAX, 140, strict, 'Column bullet')})
    return out if len(out) == 2 and any(c['bullets'] for c in out) else []


def _table(raw, strict):
    if not isinstance(raw, dict) or not isinstance(raw.get('header'), list) or not isinstance(raw.get('rows'), list):
        return None
    header = [_text(h, CELL_MAX, strict, 'Table cell') for h in raw['header']][:TABLE_COLS_MAX]
    if not header:
        return None
    rows = []
    for r in raw['rows'][:TABLE_ROWS_MAX]:
        if isinstance(r, list):
            row = [_text(c, CELL_MAX, strict, 'Table cell') for c in r][:len(header)]
            rows.append(row + [''] * (len(header) - len(row)))
    return {'header': header, 'rows': rows} if rows else None


def _image(slide, strict):
    img = slide.get('image', '')
    if not isinstance(img, str) or not img.startswith(IMAGE_PREFIXES):
        return ''
    if len(img) > IMAGE_MAX_CHARS:
        raise ValueError('Image slides must be under about 6 MB each.')
    return img


def _slide(raw, strict):
    if not isinstance(raw, dict):
        raise ValueError('Invalid slide.')
    layout = raw.get('layout')
    if layout not in LAYOUTS:
        if strict:
            raise ValueError('Invalid slide layout.')
        layout = 'content'
    s = {'layout': layout,
         'title': _text(raw.get('title'), TITLE_MAX, strict, 'Slide titles'),
         'subtitle': _text(raw.get('subtitle'), SUBTITLE_MAX, strict, 'Subtitle'),
         'takeaway': _text(raw.get('takeaway'), TAKEAWAY_MAX, strict, 'Takeaway'),
         'notes': _text(raw.get('notes'), NOTES_MAX, strict, 'Speaker notes'),
         'bullets': _lines(raw.get('bullets'), BULLETS_MAX, BULLET_MAX, strict, 'Bullets')}
    if layout == 'two_column':
        s['columns'] = _columns(raw.get('columns'), strict)
    elif layout == 'stats':
        s['stats'] = _stats(raw.get('stats'), strict)
    elif layout == 'chart':
        s['chart'] = _chart(raw.get('chart'), strict)
    elif layout == 'timeline':
        s['steps'] = _steps(raw.get('steps'), strict)
    elif layout == 'table':
        s['table'] = _table(raw.get('table'), strict)
    elif layout == 'quote':
        s['quote'] = _text(raw.get('quote') or raw.get('title'), QUOTE_MAX, strict, 'Quote')
        s['author'] = _text(raw.get('author'), AUTHOR_MAX, strict, 'Author')
    elif layout in ('image', 'image_text'):
        s['image'] = _image(raw, strict)
        if not s['image']:
            raise ValueError('Image slides need a PNG or JPEG image.')
    return _degrade(s)


def _degrade(s):
    """A slide whose structured data is missing becomes a plain content slide, so nothing breaks."""
    L = s['layout']
    if L == 'two_column' and len(s.get('columns', [])) != 2:
        s['layout'] = 'content'
    elif L == 'stats' and len(s.get('stats', [])) < STATS_RANGE[0]:
        s['bullets'] = s['bullets'] or [f"{x['value']} — {x['label']}".strip(' —') for x in s.get('stats', [])]
        s['layout'] = 'content'
    elif L == 'chart' and not s.get('chart'):
        s['layout'] = 'content'
    elif L == 'timeline' and len(s.get('steps', [])) < STEPS_RANGE[0]:
        s['bullets'] = s['bullets'] or [f"{x['title']}: {x['text']}".strip(': ') for x in s.get('steps', [])]
        s['layout'] = 'content'
    elif L == 'table' and not s.get('table'):
        s['layout'] = 'content'
    elif L == 'quote' and not s.get('quote'):
        s['layout'] = 'section'
    return s


def normalize_deck(raw, strict=False):
    if not isinstance(raw, dict) or not isinstance(raw.get('slides'), list) or not 1 <= len(raw['slides']) <= MAX_SLIDES:
        raise ValueError(f'Provide between 1 and {MAX_SLIDES} slides.')
    transition = raw.get('transition') if raw.get('transition') in TRANSITIONS else 'fade'
    return {'title': _text(raw.get('title'), TITLE_MAX, strict, 'Presentation title'),
            'animations': raw.get('animations') is not False,
            'transition': transition,
            'slides': [_slide(s, strict) for s in raw['slides']]}
