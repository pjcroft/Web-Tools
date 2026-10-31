"""Turn uploaded files into text for the AI plus pictures the AI (and slides) can use."""
import base64
import html as html_lib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree as E

MAX_AI_IMAGES = 8          # pictures sent to a vision model per request
MAX_PDF_PAGES = 200
AI_IMAGE_SIDE = 1400       # long side in pixels for pictures sent to the model
SLIDE_IMAGE_SIDE = 2000
MAX_SHEET_ROWS = 5000
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
TEXT_EXTS = ('.txt', '.md', '.csv', '.tsv', '.json')
ACCEPTED = ('.pdf', '.docx', '.pptx', '.xls', '.xlsx', '.odt', '.ods', '.html', '.htm', '.rtf') + TEXT_EXTS + IMAGE_EXTS
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
SUPPORTED_MESSAGE = 'Use PDF, Word, PowerPoint, Excel, OpenDocument, HTML, RTF, text or image (PNG, JPG, WEBP) files.'


@dataclass
class Source:
    text: str = ''
    images: list = field(default_factory=list)   # [{'label': str, 'data_url': str}]


def xml_parse(b):
    return E.fromstring(b, E.XMLParser(resolve_entities=False, no_network=True))


def check_zip(z):
    if sum(i.file_size for i in z.infolist()) > 100 * 1024 * 1024:
        raise ValueError('Expanded document is too large.')


def to_data_url(image, side, quality=84, force_png=False):
    """Resize a PIL image and return a PNG/JPEG data URL (PNG only when it needs transparency or is requested)."""
    from PIL import Image
    image.load()
    image.thumbnail((side, side), Image.LANCZOS)
    buf = io.BytesIO()
    if force_png or image.mode in ('RGBA', 'LA', 'P'):
        image.save(buf, format='PNG')
        mime = 'png'
    else:
        image.convert('RGB').save(buf, format='JPEG', quality=quality)
        mime = 'jpeg'
    return f'data:image/{mime};base64,' + base64.b64encode(buf.getvalue()).decode()


def image_from_bytes(data, label, side=SLIDE_IMAGE_SIDE):
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data))
        return {'label': label, 'data_url': to_data_url(im, side)}
    except Exception:
        raise ValueError(f'{label} is not a readable image.')


def pdf_text_and_pages(data, want_images):
    import fitz
    doc = fitz.open(stream=data, filetype='pdf')
    if doc.page_count > MAX_PDF_PAGES:
        raise ValueError(f'PDFs must contain {MAX_PDF_PAGES} pages or fewer.')
    pages = [(p.get_text() or '') for p in doc]
    text = '\n'.join(pages)
    images = []
    avg = len(text.strip()) / max(1, doc.page_count)
    # Render pages when the PDF is short or mostly drawings/scans, so a vision model can see them.
    if want_images and (doc.page_count <= MAX_AI_IMAGES or avg < 400):
        from PIL import Image
        for i in range(min(doc.page_count, MAX_AI_IMAGES)):
            page = doc[i]
            zoom = AI_IMAGE_SIDE / max(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            im = Image.open(io.BytesIO(pix.tobytes('png')))
            images.append({'label': f'page {i + 1}', 'data_url': to_data_url(im, AI_IMAGE_SIDE)})
    return text, images


def docx_images(data, label):
    """Pictures embedded in a Word/PowerPoint file, skipping icons and logos."""
    from PIL import Image
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            if re.match(r'(word|ppt)/media/[^/]+\.(png|jpe?g)$', n, re.I):
                try:
                    im = Image.open(io.BytesIO(z.read(n)))
                    if im.width >= 300 and im.height >= 200:
                        out.append({'label': f'{label} image {len(out) + 1}', 'data_url': to_data_url(im, SLIDE_IMAGE_SIDE)})
                except Exception:
                    continue
            if len(out) >= 4:
                break
    return out


def spreadsheet_text(rows_by_sheet):
    parts = []
    for name, rows in rows_by_sheet:
        parts.append('SHEET: ' + name)
        count = 0
        for row in rows:
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                parts.append(' | '.join(cells))
                count += 1
                if count >= MAX_SHEET_ROWS:
                    break
    return '\n'.join(parts)


def strip_html(data):
    text = data.decode('utf-8-sig', errors='replace')
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    return html_lib.unescape(text)


def strip_rtf(data):
    text = data.decode('utf-8-sig', errors='replace')
    text = re.sub(r'\{\\fonttbl.*?\}', ' ', text, flags=re.S)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", lambda m: chr(int(m.group(0)[2:], 16)), text)
    text = re.sub(r'\\[a-zA-Z]+-?\d* ?', ' ', text)
    text = text.replace('{', ' ').replace('}', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def extract_source(file, want_images=True):
    """Read one uploaded file (anything with .filename and .read()) into a Source."""
    data = file.read()
    name = Path(file.filename or '').name
    ext = Path(name).suffix.lower()

    if ext in IMAGE_EXTS:
        return Source('', [image_from_bytes(data, name)])
    if ext == '.pdf':
        text, images = pdf_text_and_pages(data, want_images)
        if not text.strip() and not images:
            raise ValueError('This PDF has no readable text. Turn on “Let the AI see images” or paste OCR text.')
        if not text.strip():
            text = '(Scanned PDF with no text layer; see the page pictures.)'
        return Source(text, [dict(i, label=f'{name} {i["label"]}') for i in images])
    if ext == '.docx':
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            check_zip(z)
        from docx import Document
        d = Document(io.BytesIO(data))
        text = '\n'.join([p.text for p in d.paragraphs] + [' | '.join(c.text for c in row.cells) for t in d.tables for row in t.rows])
        return Source(text, docx_images(data, name) if want_images else [])
    if ext == '.pptx':
        z = zipfile.ZipFile(io.BytesIO(data))
        check_zip(z)
        names = sorted([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+.xml', n)], key=lambda n: int(re.search(r'(\d+)\.xml', n).group(1)))
        text = '\n'.join(' '.join(xml_parse(z.read(n)).xpath('//a:t/text()', namespaces=NS)) for n in names)
        return Source(text, docx_images(data, name) if want_images else [])
    if ext == '.xlsx':
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        return Source(spreadsheet_text((ws.title, ws.iter_rows(values_only=True)) for ws in wb.worksheets))
    if ext == '.xls':
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        return Source(spreadsheet_text((s.name, (s.row_values(r) for r in range(min(s.nrows, MAX_SHEET_ROWS)))) for s in wb.sheets()))
    if ext == '.odt':
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            check_zip(z)
            root = xml_parse(z.read('content.xml'))
        ns = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
        lines = [''.join(p.xpath('.//text()', namespaces=ns)).strip() for p in root.xpath('//text:p', namespaces=ns)]
        return Source('\n'.join(l for l in lines if l))
    if ext == '.ods':
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            check_zip(z)
            root = xml_parse(z.read('content.xml'))
        ns = {'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0', 'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
        rows = [[''.join(c.xpath('.//text()', namespaces=ns)).strip() for c in row.xpath('./table:table-cell', namespaces=ns)]
                for row in root.xpath('//table:table-row', namespaces=ns)]
        return Source(spreadsheet_text([('', rows)]).replace('SHEET: \n', ''))
    if ext in ('.html', '.htm'):
        return Source(strip_html(data))
    if ext == '.rtf':
        return Source(strip_rtf(data))
    if ext in TEXT_EXTS:
        return Source(data.decode('utf-8-sig'))
    raise ValueError(SUPPORTED_MESSAGE)


def extract(file):
    """Text only; kept for callers that do not care about pictures."""
    return extract_source(file, want_images=False).text


def render_pdf_pages(data, limit=20, dpi=150):
    """Whole pages as PNG data URLs for the 'PDF pages as image slides' button."""
    import fitz
    doc = fitz.open(stream=data, filetype='pdf')
    out = []
    for i in range(min(doc.page_count, limit)):
        pix = doc[i].get_pixmap(dpi=dpi)
        out.append({'page': i + 1, 'image': 'data:image/png;base64,' + base64.b64encode(pix.tobytes('png')).decode(),
                    'text_chars': len(doc[i].get_text() or '')})
    return out, doc.page_count
