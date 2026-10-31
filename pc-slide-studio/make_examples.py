"""Regenerate static/examples/<style>.jpg: a 2x2 contact sheet of a small sample deck per style.

The sheets are rendered by the real exporter (builder.make_pptx) and LibreOffice, so the preview in
the UI is genuine output. Run after changing layouts or styles:  python make_examples.py
Needs `soffice` (LibreOffice) and `pdftoppm` (poppler-utils) on the machine; the app itself does not.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from builder import make_pptx
from styles import STYLES

OUT = Path(__file__).parent / 'static' / 'examples'
TILE = 480  # px wide per slide


def render(style):
    deck = {'title': style['label'], 'slides': style['example'] + [{'layout': 'closing', 'title': 'THANK YOU'}]}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'deck.pptx').write_bytes(make_pptx(deck).read())
        subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', str(tmp), str(tmp / 'deck.pptx')], check=True, capture_output=True)
        subprocess.run(['pdftoppm', '-r', '60', '-png', str(tmp / 'deck.pdf'), str(tmp / 'p')], check=True)
        pages = [Image.open(p).convert('RGB') for p in sorted(tmp.glob('p-*.png'))][:4]
        pages = [p.resize((TILE, int(p.height * TILE / p.width)), Image.LANCZOS) for p in pages]
    w, h = pages[0].size
    gap = 8
    sheet = Image.new('RGB', (w * 2 + gap * 3, h * 2 + gap * 3), (17, 28, 48))
    for i, p in enumerate(pages):
        sheet.paste(p, (gap + (i % 2) * (w + gap), gap + (i // 2) * (h + gap)))
    return sheet


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    for style in STYLES:
        if only and style['id'] not in only:
            continue
        render(style).save(OUT / f"{style['id']}.jpg", quality=82, optimize=True)
        print('wrote', style['id'])
