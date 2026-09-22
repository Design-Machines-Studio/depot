"""Offline transport proof: only a loopback HTTP server and fixture credentials."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]/'plugins/openrouter'
RUNNER = ROOT/'skills/openrouter-delegate/references/openrouter-decisions.sh'
REQUEST = {'model':'typesafe/jev-1.13','state':{'title':'Synthetic fixture title'},'questions':{
    'fit':{'type':'choice','instructions':'Classify the title.', 'criteria':{'yes':'Related','no':'Unrelated'}}}}
RESPONSE = {'answers':{'fit':{'type':'choice','choice':'yes','confidence':0.8,
    'probabilities':{'yes':0.9,'no':0.1}}},'usage':{'input_tokens':12,'output_tokens':3}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_POST(self):
        self.server.calls.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
        time.sleep(self.server.delay)
        self.send_response(self.server.status)
        if self.server.status == 302:
            self.send_header('Location',f'http://127.0.0.1:{self.server.server_port}/leak')
        self.end_headers()
        try: self.wfile.write(json.dumps(self.server.response).encode())
        except BrokenPipeError: pass


class DecisionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.calls=[]; self.server.status=200; self.server.delay=0
        self.server.response=copy.deepcopy(RESPONSE)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def invoke(self, body=None, timeout=3, env=None):
        environment = {k:v for k,v in os.environ.items() if not k.startswith('OPENROUTER_')}
        environment.update(OPENROUTER_API_KEY='test',
            OPENROUTER_DECISIONS_ENDPOINT=f'http://127.0.0.1:{self.server.server_port}/api/alpha/decisions')
        environment.update(env or {})
        receipt=self.directory/'receipt.json'
        result=subprocess.run(['bash',str(RUNNER),'--receipt',str(receipt),'--timeout',str(timeout)],
            input=json.dumps(REQUEST if body is None else body),text=True,capture_output=True,env=environment,timeout=6)
        return result,json.loads(receipt.read_text()) if receipt.exists() else None

    def test_success_exact_body_and_unknown_provenance(self):
        result,receipt=self.invoke()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.server.calls,[('/api/alpha/decisions',REQUEST)])
        self.assertEqual(receipt['outcome'],'success')
        self.assertIsNone(receipt['servingProvider'])
        self.assertIsNone(receipt['responseModel'])
        self.assertEqual(len(receipt['requestEnvelopeSha256']),64)
        self.assertEqual((self.directory/'receipt.json').stat().st_mode & 0o777,0o600)
        self.assertNotIn('Synthetic fixture title',json.dumps(receipt))

    def test_reported_provenance(self):
        self.server.response.update(model=REQUEST['model'],provider='TypeSafe',id='gen-fixture-1')
        result,receipt=self.invoke()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(receipt['generationId'],'gen-fixture-1')
        self.assertEqual(receipt['servingProviderProvenance'],'response')

    def test_http_failure_no_leak_no_retry(self):
        self.server.status=429; self.server.response={'error':'SECRET_ECHO_SENTINEL'}
        result,receipt=self.invoke()
        self.assertEqual(result.returncode,1)
        self.assertEqual(len(self.server.calls),1)
        self.assertNotIn('SECRET_ECHO_SENTINEL',result.stdout+result.stderr+json.dumps(receipt))
        self.assertEqual(receipt['httpStatus'],429)

    def test_redirect_not_followed(self):
        self.server.status=302
        result,receipt=self.invoke()
        self.assertEqual(result.returncode,1)
        self.assertEqual(len(self.server.calls),1)

    def test_timeout_no_retry(self):
        self.server.delay=2
        result,receipt=self.invoke(timeout=1)
        self.assertEqual(result.returncode,28)
        self.assertEqual(receipt['failureKind'],'timeout')
        self.assertEqual(len(self.server.calls),1)

    def test_bad_model_sends_nothing(self):
        body=copy.deepcopy(REQUEST);body['model']='anthropic/anything'
        result,receipt=self.invoke(body)
        self.assertEqual(result.returncode,2)
        self.assertFalse(self.server.calls)

    def test_oversize_sends_nothing(self):
        body=copy.deepcopy(REQUEST);body['state']='x'*33000
        result,_=self.invoke(body)
        self.assertEqual(result.returncode,2)
        self.assertFalse(self.server.calls)

    def test_invalid_distribution(self):
        self.server.response['answers']['fit']['probabilities']['yes']=0.1
        result,receipt=self.invoke()
        self.assertEqual(result.returncode,2)
        self.assertEqual(result.stdout,'')

    def test_unexpected_model(self):
        self.server.response['model']='other/model'
        result,_=self.invoke()
        self.assertEqual(result.returncode,2)

    def test_no_receipt_overwrite_or_symlink(self):
        original=self.directory/'original';original.write_text('preserve')
        (self.directory/'receipt.json').symlink_to(original)
        # invoke parses receipt, so call directly for this deliberately non-JSON file.
        result=subprocess.run(['bash',str(RUNNER),'--receipt',str(self.directory/'receipt.json')],
            input=json.dumps(REQUEST),text=True,capture_output=True,
            env={**os.environ,'OPENROUTER_API_KEY':'test'},timeout=6)
        self.assertEqual(result.returncode,2)
        self.assertEqual(original.read_text(),'preserve')
        self.assertFalse(self.server.calls)

    def test_unsafe_endpoint_refused(self):
        result,receipt=self.invoke(env={'OPENROUTER_DECISIONS_ENDPOINT':'http://example.com'})
        self.assertEqual(result.returncode,2)
        self.assertIsNone(receipt)
        self.assertFalse(self.server.calls)

    def test_privacy_requirement_not_silently_ignored(self):
        result,receipt=self.invoke(env={'OPENROUTER_ZDR':'1'})
        self.assertEqual(result.returncode,2)
        self.assertIsNone(receipt)
        self.assertFalse(self.server.calls)

    def test_key_file_policy(self):
        key=self.directory/'key';key.write_text('test\n');key.chmod(0o600)
        result,_=self.invoke(env={'OPENROUTER_API_KEY':'','OPENROUTER_API_KEY_FILE':str(key)})
        self.assertEqual(result.returncode,0,result.stderr)

    def test_insecure_key_file_refused(self):
        key=self.directory/'key';key.write_text('test\n');key.chmod(0o644)
        result,_=self.invoke(env={'OPENROUTER_API_KEY':'','OPENROUTER_API_KEY_FILE':str(key)})
        self.assertEqual(result.returncode,1)
        self.assertFalse(self.server.calls)

    def test_noul_and_score(self):
        body=copy.deepcopy(REQUEST)
        body['questions']={'yes':{'type':'noul','instructions':'Related?',
            'criteria':{'true':'Related','false':'Unrelated'}},
            'level':{'type':'score','instructions':'How much?', 'criteria':['Little','Much']}}
        self.server.response['answers']={'yes':{'type':'noul','noul':0.8},
            'level':{'type':'score','score':0.8,'confidence':0.7,'probabilities':{'0':0.2,'1':0.8},
                     'legend':{'0':'Little','1':'Much'}}}
        result,_=self.invoke(body)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
