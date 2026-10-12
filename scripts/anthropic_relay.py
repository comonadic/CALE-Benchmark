"""Authenticated per-job Anthropic relay; real provider credentials stay on the host."""
import hashlib,json,secrets,threading,time,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

class ModelRelay:
    def __init__(self,base,key,model,logs,port=0,bind='0.0.0.0'):
        self.base=base.rstrip('/');self.key=key;self.model=model
        self.token=secrets.token_urlsafe(32)
        self.logs=Path(logs);self.logs.mkdir(parents=True,exist_ok=True)
        self.lock=threading.Lock();self.counter=0
        relay=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def reply(self,status,data,content_type='application/json'):
                self.send_response(status);self.send_header('Content-Type',content_type)
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def do_GET(self):
                self.reply(200,b'{"status":"ready"}')
            def do_POST(self):
                if self.headers.get('x-api-key')!=relay.token and self.headers.get('Authorization')!='Bearer '+relay.token:
                    self.reply(401,b'{"error":{"type":"authentication_error","message":"Invalid job relay token"}}');return
                route=self.path.split('?',1)[0]
                if route not in ['/v1/messages','/v1/messages/count_tokens','/messages','/messages/count_tokens']:
                    self.reply(404,b'{"error":{"type":"invalid_request_error","message":"Unsupported relay route"}}');return
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<100*1024*1024:
                    self.reply(400,b'{"error":{"type":"invalid_request_error","message":"Invalid request length"}}');return
                data=self.rfile.read(length)
                try:body=json.loads(data)
                except ValueError:
                    self.reply(400,b'{"error":{"type":"invalid_request_error","message":"Expected JSON"}}');return
                if body.get('model')!=relay.model:
                    self.reply(400,b'{"error":{"type":"invalid_request_error","message":"Model differs from run policy"}}');return
                with relay.lock:relay.counter+=1;number=relay.counter
                receipt={'request_number':number,'started_at_unix':time.time(),'route':route,'requested_model':body['model'],'request_sha256':hashlib.sha256(data).hexdigest(),'request_bytes':len(data),'max_tokens':body.get('max_tokens'),'thinking':body.get('thinking'),'output_config':body.get('output_config'),'cache_control_blocks_scope':'messages-only','cache_control_blocks':sum(1 for m in body.get('messages',[]) for b in (m.get('content',[]) if isinstance(m.get('content'),list) else []) if isinstance(b,dict) and b.get('cache_control'))}
                endpoint=relay.base+(route[3:] if relay.base.endswith('/v1') and route.startswith('/v1') else route)
                headers={'Content-Type':'application/json','x-api-key':relay.key,'User-Agent':'Mozilla/5.0','anthropic-version':self.headers.get('anthropic-version','2023-06-01')}
                if self.headers.get('anthropic-beta'):headers['anthropic-beta']=self.headers['anthropic-beta']
                request=urllib.request.Request(endpoint,data=data,headers=headers)
                try:
                    try:response=urllib.request.urlopen(request,timeout=600)
                    except urllib.error.HTTPError as exc:response=exc
                    with response:
                        receipt['http_status']=response.status
                        media=response.headers.get('Content-Type','application/json')
                        if 'text/event-stream' not in media:
                            raw=response.read();self.reply(response.status,raw,media)
                            try:parsed=json.loads(raw);receipt.update(response_id=parsed.get('id'),model=parsed.get('model'),usage=parsed.get('usage'))
                            except ValueError:pass
                        else:
                            self.send_response(response.status);self.send_header('Content-Type',media);self.send_header('Connection','close');self.end_headers()
                            terminal=False
                            for line in response:
                                self.wfile.write(line);self.wfile.flush()
                                if line.startswith(b'data:'):
                                    try:event=json.loads(line[5:].strip())
                                    except ValueError:continue
                                    kind=event.get('type')
                                    if kind=='message_start':
                                        msg=event['message'];receipt.update(response_id=msg.get('id'),model=msg.get('model'),usage=msg.get('usage',{}))
                                    elif kind=='message_delta':
                                        receipt.setdefault('usage',{}).update(event.get('usage',{}));receipt['stop_reason']=event.get('delta',{}).get('stop_reason')
                                    elif kind=='message_stop':terminal=True;receipt['stream_complete']=True
                                    elif kind=='error':receipt['stream_error']=event.get('error',{}).get('type')
                                if terminal and not line.strip():break
                            self.close_connection=True
                except Exception as exc:
                    receipt['transport_error']=type(exc).__name__
                    if 'http_status' not in receipt:
                        self.reply(502,b'{"error":{"type":"api_error","message":"Host provider transport failed"}}')
                finally:
                    receipt['elapsed_seconds']=round(time.time()-receipt['started_at_unix'],3)
                    (relay.logs/f'{number:05d}.json').write_text(json.dumps(receipt,indent=2)+'\n')
        self.server=ThreadingHTTPServer((bind,port),Handler)
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
    @property
    def port(self):return self.server.server_address[1]
    def start(self):self.thread.start()
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
