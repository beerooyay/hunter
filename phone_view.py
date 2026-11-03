"""Read-only Wi-Fi view of the local control room. No mutation proxy."""
import json,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_POST(self):self.send_error(403,'read-only Wi-Fi view; use the Mac to control hunters')
    def do_GET(self):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8767'+self.path,timeout=20) as r:
                data=r.read();ctype=r.headers.get('Content-Type','application/json')
                if self.path=='/control/status':
                    s=json.loads(data);s.pop('token',None);s['readonly']=True;data=json.dumps(s).encode()
                self.send_response(200);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
                if r.headers.get('X-File-Size'):self.send_header('X-File-Size',r.headers['X-File-Size'])
                self.end_headers();self.wfile.write(data)
        except (OSError,ValueError):self.send_error(503,'local control room unavailable')
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8768),Handler).serve_forever()
