"""Stateless PC Plan WSGI service. No project database or durable user files."""
import base64
import io
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import BoundedSemaphore
from urllib.parse import urlsplit
from validation import validate
from project_xml import export_xml

ROOT = Path(__file__).resolve().parent
LIMIT = 42 * 1024 * 1024
JOBS = BoundedSemaphore(2)
ASSETS = {'/': ('app/index.html', 'text/html; charset=utf-8'), '/app.mjs': ('app/app.mjs', 'text/javascript'), '/schedule.mjs': ('app/schedule.mjs','text/javascript'), '/style.css': ('app/style.css','text/css'), '/pc-plan.svg': ('assets/fieldplan.svg','image/svg+xml')}


def application(env, start_response):
    def respond(body, mime='application/json', status=200, extra=()):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        headers = [('Content-Type',mime), ('Content-Length',str(len(body))), ('Cache-Control','no-store'), ('X-Content-Type-Options','nosniff'), ('Referrer-Policy','no-referrer'), ('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")]
        start_response(f"{status} { {200:'OK',400:'Bad Request',403:'Forbidden',404:'Not Found',405:'Method Not Allowed',413:'Payload Too Large',429:'Too Many Requests',500:'Internal Server Error'}.get(status, 'Error')}", headers + list(extra))
        return [body]
    path = env.get('PATH_INFO','/')
    method = env.get('REQUEST_METHOD','GET')
    if method == 'GET':
        if path == '/health': return respond({'ok':True})
        if path not in ASSETS: return respond({'error':'Not found'},status=404)
        file,mime=ASSETS[path]
        return respond((ROOT/file).read_bytes(),mime)
    if method != 'POST': return respond({'error':'Method not allowed'},status=405)
    # Custom header forces a browser CORS preflight for cross-origin calls; no CORS is allowed.
    if env.get('HTTP_X_PC_PLAN') != '1' or env.get('HTTP_SEC_FETCH_SITE') == 'cross-site':
        return respond({'error':'Open PC Plan directly to use this feature.'},status=403)
    if not env.get('CONTENT_TYPE','').startswith('application/json'):
        return respond({'error':'Expected JSON'},status=400)
    if path not in ('/api/import','/api/export','/api/preview','/api/xml'):
        return respond({'error':'Not found'},status=404)
    if not JOBS.acquire(blocking=False):
        return respond({'error':'Server is busy. Please try again shortly.'},status=429)
    try:
        length = int(env.get('CONTENT_LENGTH') or 0)
        if not 0 < length <= LIMIT: return respond({'error':'File or request is too large.'},status=413)
        payload = json.loads(env['wsgi.input'].read(length))
        if not isinstance(payload,dict): raise ValueError('Invalid request')
        if path == '/api/import':
            raw=base64.b64decode(payload['content'],validate=True)
            if len(raw)>30*1024*1024 or not raw.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
                raise ValueError('Choose a binary .mpp file smaller than 30 MB.')
            with tempfile.TemporaryDirectory(prefix='pc-plan-') as temp:
                source=Path(temp)/'input.mpp'; source.write_bytes(raw)
                result=subprocess.run([sys.executable,str(ROOT/'mpp_import.py'),str(source)],capture_output=True,text=True,timeout=90,cwd=ROOT)
                lines=[line for line in result.stdout.splitlines() if line.startswith('{')]
                if result.returncode or not lines: raise ValueError('Unable to import this MPP file.')
                imported=json.loads(lines[-1]); validate(imported['project'])
                return respond(imported)
        project=validate(payload['project'],scheduled=True)
        if not project['tasks']: raise ValueError('Add tasks before exporting.')
        if path == '/api/xml':
            return respond(export_xml(project),'application/xml; charset=utf-8',extra=[('Content-Disposition','attachment; filename="project.xml"')])
        settings=dict(payload['settings'])
        settings['maxPages'] = 40 if path == '/api/preview' else 150
        from pdf_export import export_pdf
        # Keep ReportLab rendering and shared font state serialized per process.
        with tempfile.TemporaryDirectory(prefix='pc-plan-') as temp:
            pdf=Path(temp)/'schedule.pdf'
            pages=export_pdf(project,settings,pdf)
            if pages>150: raise ValueError('Choose a shorter date range or fewer rows (maximum 150 PDF pages).')
            if path == '/api/export':
                name=''.join(c for c in project['name'] if c not in '/\\:*?"<>|')[:100] or 'schedule'
                return respond({'filename':name+'.pdf','content':base64.b64encode(pdf.read_bytes()).decode(),'pages':pages})
            if pages>40: raise ValueError('Preview is limited to 40 pages. Shorten the range or create the PDF directly.')
            result=subprocess.run(['pdftoppm','-png','-r','85',str(pdf),str(Path(temp)/'page')],capture_output=True,timeout=60)
            if result.returncode: raise ValueError('Could not render PDF preview.')
            images=sorted(Path(temp).glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))
            return respond({'pages':['data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode() for p in images]})
    except (ValueError,KeyError,TypeError,AttributeError,RecursionError,subprocess.TimeoutExpired) as exc:
        return respond({'error': 'Unable to process file or export settings: '+str(exc)[:200]},status=400)
    except Exception:
        logging.exception('PC Plan processing error')
        return respond({'error':'Unable to process this request.'},status=500)
    finally:
        JOBS.release()

if __name__=='__main__':
    from wsgiref.simple_server import make_server
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8080')))
    args,_=parser.parse_known_args()
    with make_server('0.0.0.0',args.port,application) as server:
        server.serve_forever()
