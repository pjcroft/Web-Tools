import io, os, json, zipfile, unittest, posixpath
from unittest.mock import patch
from app import app, make_pptx, xml, NS, REL, extract
DECK={'title':'Test & export','slides':[{'layout':'cover','title':'Customer & project','bullets':[]},{'layout':'section','title':'Site readiness','bullets':[]},{'layout':'content','title':'Readiness checklist','bullets':['Foundation ready','Power available']},{'layout':'closing','title':'THANK YOU','bullets':[]}]}
class Tests(unittest.TestCase):
 def setUp(self):self.client=app.test_client()
 def test_export_package(self):
  with zipfile.ZipFile(make_pptx(DECK)) as z:
   self.assertIsNone(z.testzip()); r=xml(z.read('ppt/presentation.xml'));self.assertEqual(len(r.find('p:sldIdLst',NS)),4)
   content=xml(z.read('ppt/slides/slide3.xml'));self.assertIn('Foundation ready',content.xpath('//a:t/text()',namespaces=NS))
   for n in z.namelist():
    if n.endswith('.rels'):
     parent=posixpath.dirname(posixpath.dirname(n))
     for rel in xml(z.read(n)):
      if rel.get('TargetMode')=='External':continue
      target=rel.get('Target');dest=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(parent,target))
      self.assertIn(dest,z.namelist(),(n,dest))
 def test_export_route(self):
  r=self.client.post('/api/export',json=DECK);self.assertEqual(r.status_code,200);self.assertTrue(r.data.startswith(b'PK'))
 def test_reject_invalid(self):
  self.assertEqual(self.client.post('/api/export',json={'slides':[]}).status_code,400)
  bad={'slides':[{'layout':'content','title':'x','bullets':['x'*221]}]};self.assertEqual(self.client.post('/api/export',json=bad).status_code,400)
 def test_missing_key(self):
  with patch.dict(os.environ,{'OPENROUTER_API_KEY':''}):self.assertEqual(self.client.post('/api/draft').status_code,503)
 def test_generation(self):
  response=io.BytesIO(json.dumps({'model':'test-free','choices':[{'message':{'content':json.dumps(DECK)}}]}).encode())
  with patch.dict(os.environ,{'OPENROUTER_API_KEY':'test'}),patch('urllib.request.urlopen',return_value=response) as call:
   r=self.client.post('/api/draft',data={'files':(io.BytesIO(b'Foundation ready'),'notes.txt'),'count':'4'})
   self.assertEqual(r.status_code,200);self.assertEqual(r.json['deck'],DECK)
   req=call.call_args.args[0];payload=json.loads(req.data);self.assertEqual(payload['model'],'openrouter/free');self.assertIn('Foundation ready',payload['messages'][1]['content'])
 def test_new_upload_types(self):
  class F:
   def __init__(self, name, data): self.filename=name; self._d=data
   def read(self): return self._d
  self.assertIn('hello', extract(F('n.json', b'{"hello": "world"}')))
  self.assertIn('a', extract(F('n.tsv', b'a\tb\n')))
  self.assertIn('Hello', extract(F('n.html', b'<h1>Hello</h1><p>World</p>')))
  from openpyxl import Workbook
  wb = Workbook(); ws = wb.active; ws.title = 'Plan'; ws.append(['Task', 'Status']); ws.append(['Foundations', 'Ready'])
  buf = io.BytesIO(); wb.save(buf)
  out = extract(F('n.xlsx', buf.getvalue()))
  self.assertIn('SHEET: Plan', out); self.assertIn('Foundations | Ready', out)
 def test_image_slide_export(self):
  png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
  deck = {'title': 'T', 'slides': [{'layout': 'cover', 'title': 'T', 'bullets': []}, {'layout': 'image', 'title': 'Layout drawing', 'bullets': [], 'image': png}]}
  r = self.client.post('/api/export', json=deck); self.assertEqual(r.status_code, 200)
  with zipfile.ZipFile(io.BytesIO(r.data)) as z:
   names = z.namelist(); self.assertTrue(any(n.startswith('ppt/media/image') for n in names), names)
   slide2 = z.read('ppt/slides/slide2.xml').decode()
   self.assertIn('p:pic', slide2); self.assertIn('rIdImg', slide2)
   self.assertIn('Layout drawing', z.read('ppt/slides/slide2.xml').decode())
 def test_pdf_images_route(self):
  import fitz
  doc = fitz.open(); page = doc.new_page(width=842, height=595); page.draw_rect(fitz.Rect(100, 100, 400, 300))
  buf = io.BytesIO(); doc.save(buf)
  r = self.client.post('/api/pdf-images', data={'file': (io.BytesIO(buf.getvalue()), 'drawing.pdf')})
  self.assertEqual(r.status_code, 200)
  self.assertEqual(r.json['total'], 1); self.assertEqual(len(r.json['pages']), 1)
  img = r.json['pages'][0]['image']; self.assertTrue(img.startswith('data:image/png;base64,'))
  import base64 as _b
  self.assertTrue(_b.b64decode(img.split(',', 1)[1]).startswith(b'\x89PNG'))
 def test_home(self):self.assertEqual(self.client.get('/').status_code,200)
if __name__=='__main__': unittest.main()
