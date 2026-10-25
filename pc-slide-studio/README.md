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
gunicorn --bind 0.0.0.0:8085 --workers 2 --threads 4 --timeout 240 app:app
```

The environment variable must be set in the same shell or service environment that starts the app. `python app.py` is available for local development on port 8080.

## Use

Upload PDF, DOCX, PPTX, XLS, XLSX, ODT, ODS, HTML, RTF, TXT, MD, CSV, TSV or JSON source material, or paste notes. Spreadsheet and OpenDocument tables are extracted as text, one row per line with cells separated by " | ". Set a title, purpose and target slide count. Generate the draft, edit titles and bullet points, change layouts and reorder slides, then download the PowerPoint. Save/open JSON drafts to continue later. The sample button lets you test editing and export without an API key.

## Image slides

Drawings and layouts often have no extractable text, so text generation alone cannot use them. Use **Add PDF pages as image slides** to render PDF pages as pictures (up to the first 20 pages, 150 dpi) and add each as an image slide, or **Add image slide** to add a PNG/JPEG directly. Image slides have an editable title shown above the picture; bullets are not shown on them. The picture is embedded in the exported PowerPoint, resized to at most 2000 pixels on its long side. The AI models are text-only, so image slides are visual only — the AI does not describe the picture.

The default model is `openrouter/free`. Nemotron 3 Super Free is also selectable. The app requests JSON output and validates it. It never switches to paid models. Free model availability and quotas depend on OpenRouter. Invalid AI output can require another generation attempt. The requested slide count is a target, not a guarantee.

## Template and export

The original template is included at `templates/prima-power.pptx`. The exporter reuses its cover, standard content, blue section and closing layouts, slide masters, theme and embedded media. Text remains editable. The outdated fixed cover date is removed from the generated copy. The original uploaded template is unchanged. The template's Barlow font should be installed on computers opening the deck for the closest match; otherwise the viewer may substitute fonts.

The source template contains two sample slides; these are replaced rather than included in the output. Closing slides use the original fixed THANK YOU artwork and wording. Only content slides display bullets. Draft cards are text editors rather than exact visual previews. Review exported slides in PowerPoint for text fit before sharing.

## Current scope

Text extraction and text-based slide generation. Uploaded images, diagrams and tables are not automatically recreated as slide visuals. PDF scans need OCR first. Images inside source documents are not sent to the AI. DOCX table values are extracted as text. Uploads are limited to 30 MB per request, PDFs to 200 pages, source text to 160,000 characters, and final decks to 40 slides. Up to six bullets per content slide are supported, with 220 characters per bullet. Use shorter bullets for better fit.

Files and drafts are processed in server memory and are not intentionally saved to disk or a database. The AI request sends extracted text through OpenRouter to its selected provider. Your browser retains a current draft only while the page stays open unless you download it. Server/proxy request buffering and logs follow your hosting configuration.

## Verification

`python test_app.py` checks export structure and slide layout relationships, editable text, input rejection, source extraction, and a mocked OpenRouter generation. Live AI generation requires your configured key and has not been exercised with your account.

## App color standard

The interface uses the supplied `static/midnight-template.css`: Midnight Electric with beige/tan. Dark navy surrounds, cyan primary actions, amber highlights, tan secondary text, and a white slide editing surface. Reuse this stylesheet for other pjcroft web tools. PowerPoint exports keep the Prima Power template branding.
