"""PC Slide Studio: Flask routes. The work happens in extract, ai, schema and builder."""
import os
import re

from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

import ai
from builder import make_pptx
from extract import ACCEPTED, MAX_AI_IMAGES, extract, extract_source, render_pdf_pages
from schema import LAYOUTS, LIMITS, TRANSITIONS, normalize_deck
from styles import STYLE_BY_ID, public_styles, resolve_style

MAX_SOURCE_CHARS = 160_000

app = Flask(__name__, static_url_path='', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024


def flag(name, default=True):
    value = request.form.get(name)
    return default if value is None else value.lower() in ('1', 'true', 'on', 'yes')


@app.get('/')
def index():
    return app.send_static_file('index.html')


@app.get('/api/status')
def status():
    return jsonify(configured=bool(ai.api_key()), models=ai.public_models(), styles=public_styles(), layouts=LAYOUTS,
                   limits=LIMITS, transitions=TRANSITIONS, accepted=list(ACCEPTED), maxImages=MAX_AI_IMAGES)


@app.post('/api/draft')
def draft():
    key = ai.api_key()
    if not key:
        return jsonify(error='Set OPENROUTER_API_KEY on the server, then restart the app.'), 503
    want_images = flag('use_images')
    text, images, warnings = request.form.get('notes', ''), [], []
    for f in request.files.getlist('files'):
        src = extract_source(f, want_images)
        if src.text.strip():
            text += '\n\nSOURCE: ' + f.filename + '\n' + src.text
        images += [dict(im, label=im['label']) for im in src.images]
    if len(images) > MAX_AI_IMAGES:
        warnings.append(f'Only the first {MAX_AI_IMAGES} pictures were used.')
        images = images[:MAX_AI_IMAGES]
    if not text.strip() and not images:
        raise ValueError('Upload source material or enter notes first.')
    if len(text) > MAX_SOURCE_CHARS:
        raise ValueError('Source exceeds 160,000 characters. Please split it into smaller presentations.')
    style = resolve_style(request.form.get('style') or request.form.get('purpose', ''))
    try:
        count = max(3, min(30, int(request.form.get('count') or style['count'])))
    except ValueError:
        raise ValueError('Target slides must be a number.')
    form = {'title': request.form.get('title', ''), 'style': style['id'], 'count': count,
            'model': request.form.get('model') or ai.AUTO}
    try:
        deck, model, more = ai.generate(key, text, images if want_images else [], form)
    except ai.AIError as e:
        return jsonify(error=str(e)), e.status
    return jsonify(deck=deck, model=model, warnings=warnings + more)


@app.post('/api/pdf-images')
def pdf_images():
    f = request.files.get('file')
    if f is None or not f.filename.lower().endswith('.pdf'):
        return jsonify(error='Upload a PDF file.'), 400
    pages, total = render_pdf_pages(f.read())
    return jsonify(pages=pages, total=total, rendered=len(pages))


@app.post('/api/export')
def export():
    deck = request.get_json(silent=True)
    out = make_pptx(deck)
    name = re.sub(r'[^a-zA-Z0-9_-]+', '-', str(deck.get('title') or 'presentation'))[:80].strip('-') or 'presentation'
    return send_file(out, mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                     as_attachment=True, download_name=name + '.pptx')


@app.errorhandler(ValueError)
def invalid(e):
    return jsonify(error=str(e)), 400


@app.errorhandler(413)
def too_large(e):
    return jsonify(error='Uploads must total less than 30 MB.'), 413


@app.errorhandler(Exception)
def failure(e):
    if isinstance(e, HTTPException):
        return jsonify(error=e.description), e.code
    app.logger.error('Request failed: %s', type(e).__name__)
    return jsonify(error='Could not process this document. Check its format and try again.'), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8080')))
