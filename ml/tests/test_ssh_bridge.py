import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest

from forest_ml.ssh_bridge import Bridge, SSH_MARKER


class BridgeTests(unittest.TestCase):
    def test_loopback_forward_uses_server_credentials_and_blocks_other_origins(self):
        observed=[]

        class Upstream(BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append(self.headers.get('Authorization'))
                self.send_response(200)
                self.send_header('Content-Type','text/html' if self.path=='/' else 'application/json')
                self.end_headers()
                self.wfile.write(b'<head></head>' if self.path=='/' else b'{"ok":true}')

            def log_message(self,*args):
                pass

        upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        bridge=ThreadingHTTPServer(('127.0.0.1',0),Bridge)
        bridge.upstream_port=upstream.server_port
        bridge.credentials={'FOREST_ML_TOKEN':'vps-only-monitor','FOREST_ML_WORKER_TOKEN':'vps-only-worker'}
        threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (upstream,bridge)]
        for t in threads:t.start()

        def get(path,headers={}):
            connection=http.client.HTTPConnection('127.0.0.1',bridge.server_port)
            try:
                connection.request('GET',path,headers=headers)
                response=connection.getresponse()
                return response.status,response.read()
            finally:connection.close()

        try:
            self.assertEqual(get('/api/ml/state')[0],401)
            self.assertEqual(get('/api/ml/state',{'Authorization':'Bearer '+SSH_MARKER})[0],200)
            self.assertEqual(observed[-1],'Bearer vps-only-monitor')
            self.assertEqual(get('/api/ml/worker/anything',{'Authorization':'Bearer '+SSH_MARKER})[0],200)
            self.assertEqual(observed[-1],'Bearer vps-only-worker')
            self.assertEqual(get('/api/ml/state',{'Authorization':'Bearer '+SSH_MARKER,'Origin':'https://unrelated.example'})[0],403)
            self.assertEqual(get('/',{'Host':'unrelated.example'})[0],403)
            status,body=get('/')
            self.assertEqual(status,200)
            self.assertIn(SSH_MARKER.encode(),body)
            self.assertNotIn(b'vps-only',body)
        finally:
            for server in (upstream,bridge):server.shutdown();server.server_close()
            for thread in threads:thread.join()


if __name__=='__main__':
    unittest.main()
