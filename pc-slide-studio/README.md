# PC Slide Studio

Self-hosted PowerPoint creator with the supplied Prima Power template and OpenRouter free models. No hosted service is required except OpenRouter for AI generation. All CSS and JavaScript are included locally.

## Run with Docker

1. Extract this folder on your server.
2. Copy `.env.example` to `.env` and insert your OpenRouter API key there.
3. Run `docker compose up -d --build` from this folder.
4. Open `http://YOUR-SERVER-IP:8085`.

Change `8085` in compose.yaml if another app uses that port. For use behind a reverse proxy, proxy to port 8085. Keep this on a trusted network or configure authentication on your reverse proxy before exposing it publicly; the app itself has no login. All users share the server's API key and quota. Never put the key in the frontend or commit `.env`.

## Run without Docker

Use Python 3.12 or newer. Create and activate a virtual environment, then run:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY='your-key'
gunicorn --bind 0.0.0.0:8085 --workers 2 --threads 4 --timeout 330 app:app
```

The environment variable must be set in the same shell or service environment that starts the app. `python app.py` is available for local development on port 8080.

## Use

1. Pick a **presentation style**. Each one shows an example of the slides it produces and tunes the AI for that audience (project update, executive summary, customer presentation, proposal, training, technical review, general).
2. Upload source material (PDF, DOCX, PPTX, XLS, XLSX, ODT, ODS, HTML, RTF, TXT, MD, CSV, TSV, JSON) and/or pictures (PNG, JPG, WEBP), or paste notes. Spreadsheet tables become text, one row per line with cells separated by " | ".
3. Choose a model and generate the draft. Pictures, drawings and short or scanned PDFs are shown to the AI when "Let the AI see pictures" is on, and it can place them on slides.
4. Edit every slide (text, figures, chart data, steps, tables, speaker notes), change layouts, reorder, duplicate, then download the PowerPoint. Save/open JSON drafts to continue later; the browser also keeps an unsaved draft.

The sample button lets you test editing and export without an API key.

## Slide types

Cover, Agenda, Section, Content, Two columns, Key figures (stats), Chart (column, bar, line, pie, doughnut), Timeline, Table, Quote, Image, Image + text, Closing.

Charts and tables are native PowerPoint objects, so they stay editable in PowerPoint (right-click, Edit Data). Slides can carry a one-sentence takeaway bar and speaker notes. Image slides are for pictures and drawings; PDF pages can be added as pictures with **Add PDF pages as image slides** (first 20 pages, 150 dpi).

Deck options: slide transition (Fade, Push, Wipe, None) and **Animate content**. Cards, charts, timeline steps and bullets fade in one after another automatically when the slideshow reaches the slide. Turn animation off for a static deck.

## AI models

Free OpenRouter models only. The list lives in `ai.py` (`MODELS`): Auto (OpenRouter's free router), Gemma 4 31B, Nemotron Nano 12B VL, Nemotron 3 Super 120B. Models marked "sees images" receive pictures; if a text-only model is chosen and pictures are attached, Auto is used for that request. If a model is busy, unavailable or returns unusable output, the app falls back to Auto before giving up. Only ids ending in `:free` (or the free router) are ever sent, so the app cannot spend credit. Free availability changes on OpenRouter: if a model is retired, edit `MODELS`.

The AI is told never to invent numbers: stats, charts and tables are only used for figures that appear in the source. Always review facts before sharing.

## Template and export

The original Prima Power template is in `templates/prima-power.pptx` and is not modified. The exporter (`builder.py`) opens a copy, removes its two sample slides, and builds each slide from the template's layouts (cover, standard, blue section, closing), keeping masters, theme, logos and backgrounds. Content layers (cards, figures, charts, timelines, tables) are drawn on top in the template's brand colours. Fonts: install Barlow on computers that open the deck, otherwise PowerPoint substitutes a font.

Text sizes are chosen by estimating fit, not by PowerPoint, so review the exported file for text overflow before sharing. Animations and transitions are written as standard PowerPoint XML and check out structurally, but have been verified in LibreOffice rather than every PowerPoint version.

## Code layout

- `app.py` Flask routes only.
- `extract.py` source files to text and pictures.
- `ai.py` OpenRouter client, model list, prompt, fallback and JSON repair.
- `styles.py` the presentation styles and their example decks.
- `schema.py` deck schema, limits and normalisation (lenient for AI output, strict for export).
- `builder.py` the PowerPoint exporter; `anim.py` transitions and animations.
- `make_examples.py` regenerates `static/examples/*.jpg` (needs LibreOffice and poppler); run it after changing layouts or styles.
- `static/` the web page (`index.html`, `app.css`, `app.js`).

## Limits

Uploads 30 MB per request, PDFs 200 pages, source text 160,000 characters, up to 8 pictures sent to the AI, decks up to 40 slides. Images inside source documents are only sent when "Let the AI see pictures" is on. Scanned PDFs are read by vision models rather than OCR. Files and drafts are processed in server memory and not saved; the AI request sends extracted text and pictures through OpenRouter to the selected provider.

## Verification

`python test_app.py` checks every layout exports with a consistent package, native charts, tables, notes, transitions and animation targets, strict and lenient validation, mocked OpenRouter generation (fallbacks, picture prompts, free-model enforcement) and source extraction.

## App color standard

The interface uses the supplied `static/midnight-template.css`: Midnight Electric with beige/tan. Dark navy surrounds, cyan primary actions, amber highlights, tan secondary text, and a white slide editing surface. Reuse this stylesheet for other pjcroft web tools. PowerPoint exports keep the Prima Power template branding.
