# Doc Diff

Compare two versions of a PDF, PowerPoint, Word or Excel file, entirely in the browser (nothing is uploaded).

- **PDF**: visual overlay, side by side and swipe views, per-page change boxes, and a word-level text diff.
- **PowerPoint**: slides matched by content (inserted, moved or edited slides are handled), with text, notes, image, chart and shape-position changes.
- **Word**: paragraph and table-row changes with inline word highlights.
- **Excel**: changed cells (values and formulas) per sheet, plus added and removed sheets.

Static files only. `vendor/` holds local copies of pdf.js 3.11.174 and JSZip 3.10.1, so there are no CDN calls.
Deploy by rsyncing this folder to the web root; it is served at `/pdf-diff/`.
