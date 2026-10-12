import json,tempfile,threading,unittest,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from anthropic_relay import ModelRelay

class RelayTest(unittest.TestCase):
 def setUp(self):
  self.calls=[]
  calls=self.calls
  class Provider(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):
    data=self.rfile.read(int(self.headers['Content-Length']))
    calls.append({'data':data,'key':self.headers.get('x-api-key'),'ua':self.headers.get('User-Agent')})
    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
    for event in [
     {'type':'message_start','message':{'id':'test-response','model':'claude-opus-5-5','usage':{'input_tokens':3,'cache_creation_input_tokens':10,'cache_read_input_tokens':50}}},
     {'type':'message_delta','delta':{'stop_reason':'end_turn'},'usage':{'output_tokens':4}},
     {'type':'message_stop'}]:self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode());self.wfile.flush()
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Provider)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.temp=tempfile.TemporaryDirectory()
  self.relay=ModelRelay(f'http://127.0.0.1:{self.server.server_address[1]}','provider-test-key','claude-opus-5-5',self.temp.name,bind='127.0.0.1');self.relay.start()
 def tearDown(self):
  self.relay.close();self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def request(self,body,token=None):
  return urllib.request.Request(f'http://127.0.0.1:{self.relay.port}/v1/messages',data=body,headers={'Content-Type':'application/json','x-api-key':self.relay.token if token is None else token})
 def test_exact_body_and_host_credential_with_complete_usage(self):
  body=b'{"model":"claude-opus-5-5", "stream":true,"messages":[{"role":"user","content":"test input"}]}'
  with urllib.request.urlopen(self.request(body),timeout=5) as r:
   data=r.read();self.assertIn(b'message_stop',data)
  self.relay.close()
  self.relay.close=lambda:None
  self.assertEqual(self.calls[0]['data'],body)
  self.assertEqual(self.calls[0]['key'],'provider-test-key')
  self.assertEqual(self.calls[0]['ua'],'Mozilla/5.0')
  self.assertNotIn(b'provider-test-key',data)
  receipt=json.loads(next(Path(self.temp.name).glob('*.json')).read_text())
  self.assertTrue(receipt['stream_complete'])
  self.assertEqual(receipt['usage']['cache_read_input_tokens'],50)
  self.assertEqual(receipt['usage']['output_tokens'],4)
 def test_wrong_model_does_not_call_provider(self):
  with self.assertRaises(urllib.error.HTTPError) as err:
   urllib.request.urlopen(self.request(b'{"model":"another-model"}'),timeout=5)
  self.assertEqual(err.exception.code,400);self.assertEqual(self.calls,[])
 def test_invalid_job_token_does_not_call_provider(self):
  with self.assertRaises(urllib.error.HTTPError) as err:
   urllib.request.urlopen(self.request(b'{"model":"claude-opus-5-5"}','wrong-token'),timeout=5)
  self.assertEqual(err.exception.code,401);self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
