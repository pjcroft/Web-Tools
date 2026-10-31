import base64
import io
import json
import os
import posixpath
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

from lxml import etree as E

import ai
from app import app
from builder import make_pptx
from extract import extract, extract_source
from schema import LAYOUTS, normalize_deck
from styles import STYLES

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
BASIC = {'title': 'Test & export', 'slides': [{'layout': 'cover', 'title': 'Customer & project'}, {'layout': 'section', 'title': 'Site readiness'},
         {'layout': 'content', 'title': 'Readiness checklist', 'bullets': ['Foundation ready', 'Power available']}, {'layout': 'closing', 'title': 'THANK YOU'}]}
EVERY = {'title': 'Every layout', 'slides': [
    {'layout': 'cover', 'title': 'Cover', 'subtitle': 'Sub'}, {'layout': 'agenda', 'title': 'Agenda', 'bullets': ['One', 'Two', 'Three']},
    {'layout': 'section', 'title': 'Section'}, {'layout': 'content', 'title': 'Content', 'bullets': ['Lead — detail', 'Plain']},
    {'layout': 'two_column', 'title': 'Two', 'columns': [{'title': 'L', 'bullets': ['a']}, {'title': 'R', 'bullets': ['b']}], 'takeaway': 'So what'},
    {'layout': 'stats', 'title': 'Stats', 'stats': [{'value': '1', 'label': 'a'}, {'value': '2', 'label': 'b', 'note': 'n'}]},
    {'layout': 'chart', 'title': 'Chart', 'chart': {'type': 'column', 'categories': ['A', 'B'], 'series': [{'name': 'S', 'values': [1, 2]}], 'unit': '%'}, 'bullets': ['k']},
    {'layout': 'chart', 'title': 'Pie', 'chart': {'type': 'pie', 'categories': ['A', 'B'], 'series': [{'name': 'S', 'values': [1, 2]}]}},
    {'layout': 'chart', 'title': 'Line', 'chart': {'type': 'line', 'categories': ['A', 'B', 'C'], 'series': [{'name': 'S', 'values': [1, 2, 3]}, {'name': 'T', 'values': [3, 2, 1]}]}},
    {'layout': 'chart', 'title': 'Bar', 'chart': {'type': 'bar', 'categories': ['A', 'B'], 'series': [{'name': 'S', 'values': [1, 2]}]}},
    {'layout': 'chart', 'title': 'Doughnut', 'chart': {'type': 'doughnut', 'categories': ['A', 'B'], 'series': [{'name': 'S', 'values': [1, 2]}]}},
    {'layout': 'timeline', 'title': 'Timeline', 'steps': [{'title': 'a', 'text': 'x'}, {'title': 'b', 'text': 'y'}, {'title': 'c', 'text': 'z'}]},
    {'layout': 'table', 'title': 'Table', 'table': {'header': ['A', 'B'], 'rows': [['1', '2'], ['3', '4']]}},
    {'layout': 'quote', 'quote': 'A quote', 'author': 'Someone'},
    {'layout': 'image', 'title': 'Image', 'image': PNG, 'subtitle': 'cap'}, {'layout': 'image_text', 'title': 'Both', 'image': PNG, 'bullets': ['x']},
    {'layout': 'closing', 'title': 'THANK YOU', 'notes': 'Speaker notes here'}]}


def urlopen_result(deck, model='test-free'):
    return io.BytesIO(json.dumps({'model': model, 'choices': [{'message': {'content': json.dumps(deck)}}]}).encode())


def http_error(code):
    return urllib.error.HTTPError('https://openrouter.ai', code, 'err', {}, io.BytesIO(b'{}'))


class FakeFile:
    def __init__(self, name, data):
        self.filename, self._d = name, data

    def read(self):
        return self._d


def xml(b):
    return E.fromstring(b)


class Export(unittest.TestCase):
    def test_package_is_consistent(self):
        with zipfile.ZipFile(make_pptx(EVERY)) as z:
            self.assertIsNone(z.testzip())
            names = z.namelist()
            self.assertEqual(len(xml(z.read('ppt/presentation.xml')).find('p:sldIdLst', NS)), len(EVERY['slides']))
            for n in names:
                if n.endswith('.rels'):
                    parent = posixpath.dirname(posixpath.dirname(n))
                    for rel in xml(z.read(n)):
                        if rel.get('TargetMode') == 'External':
                            continue
                        t = rel.get('Target')
                        dest = t.lstrip('/') if t.startswith('/') else posixpath.normpath(posixpath.join(parent, t))
                        self.assertIn(dest, names, (n, dest))
            for n in names:
                if n.endswith('.xml') or n.endswith('.rels'):
                    xml(z.read(n))   # every part is well formed

    def test_template_sample_slides_are_gone(self):
        with zipfile.ZipFile(make_pptx(BASIC)) as z:
            slides = [n for n in z.namelist() if n.startswith('ppt/slides/slide')]
            self.assertEqual(len(slides), 4)
            self.assertNotIn('extLst', [E.QName(c).localname for c in xml(z.read('ppt/presentation.xml'))])

    def test_text_charts_notes_and_tables(self):
        with zipfile.ZipFile(make_pptx(EVERY)) as z:
            all_text = ' '.join(' '.join(xml(z.read(n)).xpath('//a:t/text()', namespaces=NS))
                                for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml'))
            for word in ('Cover', 'Agenda', 'detail', 'So what', 'A quote', 'cap', 'Timeline'):
                self.assertIn(word, all_text)
            self.assertEqual(len([n for n in z.namelist() if re_chart(n)]), 5)
            self.assertTrue(any('notesSlide' in n for n in z.namelist()))
            self.assertIn('<a:tbl>', ''.join(z.read(n).decode() for n in z.namelist() if n.startswith('ppt/slides/slide')))

    def test_every_slide_has_transition_and_builds(self):
        with zipfile.ZipFile(make_pptx(EVERY)) as z:
            for i in (4, 5, 6, 12):
                root = xml(z.read(f'ppt/slides/slide{i}.xml'))
                self.assertEqual([E.QName(c).localname for c in root][:3], ['cSld', 'clrMapOvr', 'transition'], i)
                self.assertIsNotNone(root.find('p:timing', NS), i)
                ids = set(root.xpath('//p:cNvPr/@id', namespaces=NS))
                for spid in root.xpath('//p:spTgt/@spid', namespaces=NS):
                    self.assertIn(spid, ids)          # animations only target shapes that exist
                cids = root.xpath('//p:timing//p:cTn/@id', namespaces=NS)
                self.assertEqual(len(cids), len(set(cids)))

    def test_animations_and_transitions_can_be_turned_off(self):
        deck = dict(EVERY, animations=False, transition='none')
        with zipfile.ZipFile(make_pptx(deck)) as z:
            body = ''.join(z.read(n).decode() for n in z.namelist() if n.startswith('ppt/slides/slide'))
            self.assertNotIn('<p:timing', body)
            self.assertNotIn('<p:transition', body)

    def test_no_empty_text_bodies(self):
        with zipfile.ZipFile(make_pptx(EVERY)) as z:
            for n in z.namelist():
                if n.startswith('ppt/slides/slide') and n.endswith('.xml'):
                    for body in xml(z.read(n)).xpath('//p:txBody', namespaces=NS):
                        self.assertTrue(body.findall('a:p', NS), n)   # a txBody without a paragraph makes PowerPoint repair the file

    def test_media_names_never_collide(self):
        deck = {'slides': [{'layout': 'image', 'title': str(i), 'image': PNG} for i in range(3)]}
        with zipfile.ZipFile(make_pptx(deck)) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(len(z.namelist()), len(set(z.namelist())))

    def test_every_style_example_exports(self):
        for style in STYLES:
            make_pptx({'title': style['label'], 'slides': style['example']})
            self.assertTrue((Path(__file__).parent / 'static' / 'examples' / f"{style['id']}.jpg").exists(), style['id'])


def re_chart(n):
    import re
    return re.fullmatch(r'ppt/charts/chart\d+\.xml', n)


class Schema(unittest.TestCase):
    def test_strict_rejects_long_text_and_bad_decks(self):
        with self.assertRaises(ValueError):
            normalize_deck({'slides': [{'layout': 'content', 'title': 'x', 'bullets': ['x' * 221]}]}, strict=True)
        with self.assertRaises(ValueError):
            normalize_deck({'slides': []})
        with self.assertRaises(ValueError):
            normalize_deck({'slides': [{'layout': 'bogus', 'title': 'x'}]}, strict=True)

    def test_lenient_truncates_and_degrades(self):
        d = normalize_deck({'slides': [{'layout': 'bogus', 'title': 't' * 500, 'bullets': ['b'] * 20},
                                       {'layout': 'chart', 'title': 'no data'}, {'layout': 'stats', 'title': 's', 'stats': [{'value': '1', 'label': 'only one'}]}]})
        self.assertEqual(d['slides'][0]['layout'], 'content')
        self.assertLessEqual(len(d['slides'][0]['title']), 140)
        self.assertEqual(len(d['slides'][0]['bullets']), 6)
        self.assertEqual([s['layout'] for s in d['slides'][1:]], ['content', 'content'])

    def test_chart_numbers_are_cleaned(self):
        d = normalize_deck({'slides': [{'layout': 'chart', 'title': 'c', 'chart': {'type': 'weird', 'categories': ['a', 'b'], 'series': [{'name': 'n', 'values': ['1,200', '45%']}]}}]})
        ch = d['slides'][0]['chart']
        self.assertEqual((ch['type'], ch['series'][0]['values']), ('column', [1200.0, 45.0]))

    def test_all_layouts_known(self):
        self.assertEqual(set(LAYOUTS), {s['layout'] for s in EVERY['slides']})


class Routes(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home_and_status(self):
        home = self.client.get('/')
        self.assertEqual(home.status_code, 200)
        home.close()
        s = self.client.get('/api/status').json
        ids = [m['id'] for m in s['models']]
        self.assertIn('google/gemma-4-31b-it:free', ids)
        self.assertTrue(all(i == ai.AUTO or i.endswith(':free') for i in ids))
        self.assertEqual({st['id'] for st in s['styles']}, {st['id'] for st in STYLES})

    def test_export_route_and_rejects(self):
        r = self.client.post('/api/export', json=BASIC)
        self.assertEqual((r.status_code, r.data[:2]), (200, b'PK'))
        self.assertEqual(self.client.post('/api/export', json={'slides': []}).status_code, 400)
        bad = {'slides': [{'layout': 'content', 'title': 'x', 'bullets': ['x' * 221]}]}
        self.assertEqual(self.client.post('/api/export', json=bad).status_code, 400)

    def test_missing_key(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': ''}):
            self.assertEqual(self.client.post('/api/draft').status_code, 503)

    def test_pdf_images_route(self):
        import fitz
        doc = fitz.open()
        doc.new_page(width=842, height=595).draw_rect(fitz.Rect(100, 100, 400, 300))
        buf = io.BytesIO()
        doc.save(buf)
        r = self.client.post('/api/pdf-images', data={'file': (io.BytesIO(buf.getvalue()), 'drawing.pdf')})
        self.assertEqual((r.status_code, r.json['total'], len(r.json['pages'])), (200, 1, 1))
        self.assertTrue(base64.b64decode(r.json['pages'][0]['image'].split(',', 1)[1]).startswith(b'\x89PNG'))


class Generation(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.env = patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test'})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def post(self, **extra):
        data = {'files': (io.BytesIO(b'Foundation ready'), 'notes.txt'), 'count': '4'}
        data.update(extra)
        return self.client.post('/api/draft', data=data)

    def test_generation_normalizes_and_frames_deck(self):
        with patch('urllib.request.urlopen', return_value=urlopen_result({'title': 'T', 'slides': [{'layout': 'content', 'title': 'Only', 'bullets': ['Foundation ready']}]})) as call:
            r = self.post()
        self.assertEqual(r.status_code, 200)
        self.assertEqual([s['layout'] for s in r.json['deck']['slides']], ['cover', 'content', 'closing'])
        payload = json.loads(call.call_args.args[0].data)
        self.assertEqual(payload['model'], 'openrouter/free')
        self.assertIn('Foundation ready', payload['messages'][1]['content'])
        self.assertIn('Project update', payload['messages'][0]['content'])

    def test_style_changes_the_prompt(self):
        with patch('urllib.request.urlopen', return_value=urlopen_result(BASIC)) as call:
            self.post(style='executive')
        self.assertIn('Executive summary', json.loads(call.call_args.args[0].data)['messages'][0]['content'])

    def test_legacy_purpose_value_still_works(self):
        with patch('urllib.request.urlopen', return_value=urlopen_result(BASIC)) as call:
            self.post(purpose='Training')
        self.assertIn('Training', json.loads(call.call_args.args[0].data)['messages'][0]['content'])

    def test_falls_back_to_auto_when_model_is_busy(self):
        with patch('urllib.request.urlopen', side_effect=[http_error(429), urlopen_result(BASIC, 'auto-picked')]) as call:
            r = self.post(model='nvidia/nemotron-3-super-120b-a12b:free')
        self.assertEqual((r.status_code, r.json['model']), (200, 'auto-picked'))
        self.assertEqual([json.loads(c.args[0].data)['model'] for c in call.call_args_list], ['nvidia/nemotron-3-super-120b-a12b:free', 'openrouter/free'])

    def test_retries_without_json_mode_when_unsupported(self):
        with patch('urllib.request.urlopen', side_effect=[http_error(400), urlopen_result(BASIC)]) as call:
            r = self.post()
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('response_format', json.loads(call.call_args_list[1].args[0].data))

    def test_busy_everywhere_reports_429(self):
        with patch('urllib.request.urlopen', side_effect=http_error(429)):
            self.assertEqual(self.post(model='nvidia/nemotron-3-super-120b-a12b:free').status_code, 429)

    def test_garbage_output_is_an_error_not_a_crash(self):
        bad = io.BytesIO(json.dumps({'choices': [{'message': {'content': 'sorry I cannot'}}]}).encode())
        with patch('urllib.request.urlopen', return_value=bad):
            self.assertEqual(self.post().status_code, 502)

    def test_rejects_models_that_are_not_free(self):
        self.assertEqual(self.post(model='openai/gpt-4o').status_code, 400)
        self.assertEqual(self.post(model='openai/gpt-oss-120b').status_code, 400)

    def test_pictures_reach_vision_models_and_are_placed_on_slides(self):
        deck = {'title': 'T', 'slides': [{'layout': 'cover', 'title': 'T'}, {'layout': 'image', 'title': 'Drawing', 'image_ref': 'IMG1'}, {'layout': 'closing', 'title': 'THANK YOU'}]}
        png = base64.b64decode(PNG.split(',', 1)[1])
        with patch('urllib.request.urlopen', return_value=urlopen_result(deck)) as call:
            r = self.client.post('/api/draft', data={'files': (io.BytesIO(png), 'plan.png'), 'model': 'google/gemma-4-31b-it:free', 'use_images': '1'})
        self.assertEqual(r.status_code, 200, r.json)
        payload = json.loads(call.call_args.args[0].data)
        parts = payload['messages'][1]['content']
        self.assertEqual([p['type'] for p in parts], ['text', 'text', 'image_url'])
        self.assertTrue(parts[2]['image_url']['url'].startswith('data:image/jpeg;base64,') or parts[2]['image_url']['url'].startswith('data:image/png;base64,'))
        slide = r.json['deck']['slides'][1]
        self.assertEqual(slide['layout'], 'image')
        self.assertTrue(slide['image'].startswith('data:image/'))
        make_pptx(r.json['deck'])

    def test_text_only_model_with_pictures_falls_back_to_auto(self):
        png = base64.b64decode(PNG.split(',', 1)[1])
        with patch('urllib.request.urlopen', return_value=urlopen_result(BASIC)) as call:
            r = self.client.post('/api/draft', data={'files': (io.BytesIO(png), 'plan.png'), 'model': 'nvidia/nemotron-3-super-120b-a12b:free'})
        self.assertEqual(json.loads(call.call_args.args[0].data)['model'], 'openrouter/free')
        self.assertTrue(any('cannot see pictures' in w for w in r.json['warnings']))

    def test_pictures_can_be_switched_off(self):
        png = base64.b64decode(PNG.split(',', 1)[1])
        with patch('urllib.request.urlopen', return_value=urlopen_result(BASIC)) as call:
            r = self.client.post('/api/draft', data={'files': (io.BytesIO(png), 'plan.png'), 'notes': 'Some notes', 'use_images': '0'})
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(json.loads(call.call_args.args[0].data)['messages'][1]['content'], str)

    def test_parse_json_tolerates_fences_and_trailing_commas(self):
        self.assertEqual(ai.parse_json('```json\n{"a": [1, 2,],}\n```'), {'a': [1, 2]})
        self.assertEqual(ai.parse_json('Here you go: {"a": 1} hope it helps'), {'a': 1})


class Extraction(unittest.TestCase):
    def test_text_types(self):
        self.assertIn('hello', extract(FakeFile('n.json', b'{"hello": "world"}')))
        self.assertIn('a', extract(FakeFile('n.tsv', b'a\tb\n')))
        self.assertIn('Hello', extract(FakeFile('n.html', b'<h1>Hello</h1><script>x()</script><p>World</p>')))
        self.assertNotIn('x()', extract(FakeFile('n.html', b'<h1>Hello</h1><script>x()</script>')))

    def test_spreadsheets(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = 'Plan'
        ws.append(['Task', 'Status'])
        ws.append(['Foundations', 'Ready'])
        buf = io.BytesIO()
        wb.save(buf)
        out = extract(FakeFile('n.xlsx', buf.getvalue()))
        self.assertIn('SHEET: Plan', out)
        self.assertIn('Foundations | Ready', out)

    def test_image_upload_becomes_a_picture_not_text(self):
        src = extract_source(FakeFile('plan.png', base64.b64decode(PNG.split(',', 1)[1])))
        self.assertEqual((src.text, len(src.images)), ('', 1))

    def test_drawing_pdf_is_rendered_for_the_ai(self):
        import fitz
        doc = fitz.open()
        doc.new_page(width=842, height=595).draw_rect(fitz.Rect(100, 100, 400, 300))
        buf = io.BytesIO()
        doc.save(buf)
        src = extract_source(FakeFile('drawing.pdf', buf.getvalue()))
        self.assertEqual(len(src.images), 1)
        with self.assertRaises(ValueError):
            extract_source(FakeFile('drawing.pdf', buf.getvalue()), want_images=False)

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            extract(FakeFile('x.exe', b'MZ'))


if __name__ == '__main__':
    unittest.main()
