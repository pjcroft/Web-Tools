import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from web_server import application
from project_xml import export_xml

def project(name='Private plan'):
    return dict(format='linux-desktop-planner',version=1,name=name,start='2026-10-26',tasks=[dict(id=1,level=0,kind='task',name='Install & test',start='2026-10-26',finish='2026-10-27',duration=2,owner='Paul',deps=[],color='#387f78',mode='manual'),dict(id=2,level=0,kind='milestone',name='Sign off',start='2026-10-28',finish='2026-10-28',duration=0,owner='',deps=[1],color='#387f78',mode='auto')])

def call(path,payload=None,header=True):
    body=json.dumps(payload).encode() if payload is not None else b''
    env=dict(PATH_INFO=path,REQUEST_METHOD='POST' if payload is not None else 'GET',CONTENT_TYPE='application/json',CONTENT_LENGTH=str(len(body)),**{'wsgi.input':io.BytesIO(body)})
    if header: env['HTTP_X_PC_PLAN']='1'
    response={}
    def start(status,headers): response.update(status=status,headers=dict(headers))
    response['body']=b''.join(application(env,start))
    return response

class WebTests(unittest.TestCase):
    def test_sessions_have_no_project_endpoints(self):
        for path in ['/api/projects','/api/open','/api/save','/exports/a.pdf']:
            self.assertTrue(call(path)['status'].startswith('404'))
        self.assertTrue(call('/api/xml',{'project':project()},header=False)['status'].startswith('403'))
    def test_xml_preserves_ids_links_names_and_owners(self):
        r=call('/api/xml',{'project':project()}); self.assertTrue(r['status'].startswith('200'))
        root=ET.fromstring(r['body']); ns={'p':'http://schemas.microsoft.com/project'}
        self.assertEqual(root.find('p:Name',ns).text,'Private plan')
        self.assertEqual(root.find('p:Tasks/p:Task/p:Name',ns).text,'Install & test')
        self.assertEqual(root.find('p:Tasks/p:Task/p:PredecessorLink/p:PredecessorUID',ns).text,'1')
        self.assertEqual(root.find('p:Resources/p:Resource/p:Name',ns).text,'Paul')
        self.assertNotIn(b'Private plan', call('/api/xml',{'project':project('Other user')})['body'])
    def test_pdf_and_preview_cleanup(self):
        payload={'project':project(),'settings':dict(start='2026-10-26',end='2026-11-05',scale='week',paper='a4',orientation='landscape',columns=['duration','start','finish'],mono=False,milestoneDates=True)}
        original=tempfile.TemporaryDirectory
        with original() as temp:
            def directory(**kw): return original(dir=temp,**kw)
            with patch('web_server.tempfile.TemporaryDirectory',side_effect=directory):
                for path in ['/api/export','/api/preview']:
                    r=call(path,payload); self.assertTrue(r['status'].startswith('200'),r['body'])
                    result=json.loads(r['body'])
                    if path.endswith('export'): self.assertTrue(base64.b64decode(result['content']).startswith(b'%PDF'))
                    else: self.assertTrue(result['pages'][0].startswith('data:image/png;base64,'))
                    self.assertEqual(list(Path(temp).iterdir()),[])
    def test_invalid_input(self):
        p=project(); p['tasks'][0]['deps']=[2]
        self.assertTrue(call('/api/xml',{'project':p})['status'].startswith('400'))
        self.assertTrue(call('/api/import',{'content':'invalid'})['status'].startswith('400'))
