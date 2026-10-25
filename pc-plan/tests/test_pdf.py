import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".runtime/python"))
try:
    from pdf_export import export_pdf
    from pypdf import PdfReader

    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, "Install ReportLab and pypdf for PDF checks")
class PdfTests(unittest.TestCase):
    def test_paginated_landscape_contains_every_task(self):
        tasks = [
            {
                "id": i,
                "name": f"Activity {i:03d}",
                "level": 0,
                "kind": "task",
                "duration": 2,
                "start": "2026-10-01",
                "finish": "2026-10-02",
                "owner": "Owner",
                "deps": ([i - 1] if i > 1 else []),
                "color": "#387f78",
            }
            for i in range(1, 91)
        ]
        settings = {
            "start": "2026-10-01",
            "end": "2026-11-30",
            "scale": "week",
            "paper": "a3",
            "orientation": "landscape",
            "columns": ["duration", "start", "finish"],
            "mono": False,
            "milestoneDates": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "test.pdf"
            pages = export_pdf({"name": "Layout verification", "tasks": tasks}, settings, output)
            reader = PdfReader(output)
            self.assertEqual(pages, len(reader.pages))
            self.assertGreater(pages, 1)
            content = "".join(p.extract_text() for p in reader.pages)
            for t in tasks:
                self.assertIn(t["name"], content)
            self.assertIn(f"Page {pages} of {pages}", content)
            self.assertGreater(
                float(reader.pages[0].mediabox.width), float(reader.pages[0].mediabox.height)
            )

    def test_horizontal_pagination_and_portrait(self):
        tasks = [
            {
                "id": 1,
                "name": "Approval",
                "level": 0,
                "kind": "milestone",
                "duration": 0,
                "start": "2026-10-01",
                "finish": "2026-10-01",
                "owner": "",
                "deps": [],
                "color": "#387f78",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "test.pdf"
            pages = export_pdf(
                {"name": "Long timeline", "tasks": tasks},
                {
                    "start": "2026-10-01",
                    "end": "2026-12-31",
                    "scale": "day",
                    "paper": "a4",
                    "orientation": "portrait",
                    "columns": ["start"],
                    "mono": True,
                },
                output,
            )
            self.assertGreater(pages, 1)
            r = PdfReader(output)
            self.assertLess(float(r.pages[0].mediabox.width), float(r.pages[0].mediabox.height))

    def test_tabloid_and_legal_have_requested_dimensions(self):
        tasks = [
            {
                "id": 1,
                "name": "Activity",
                "level": 0,
                "kind": "task",
                "duration": 1,
                "start": "2026-10-01",
                "finish": "2026-10-01",
                "owner": "",
                "deps": [],
                "color": "#387f78",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for paper, expected in (("tabloid", (1224, 792)), ("legal", (1008, 612))):
                output = Path(tmp) / f"{paper}.pdf"
                export_pdf(
                    {"name": paper, "tasks": tasks},
                    {
                        "start": "2026-10-01",
                        "end": "2026-10-02",
                        "scale": "day",
                        "paper": paper,
                        "orientation": "landscape",
                        "columns": [],
                    },
                    output,
                )
                page = PdfReader(output).pages[0]
                self.assertEqual(
                    (round(float(page.mediabox.width)), round(float(page.mediabox.height))),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
