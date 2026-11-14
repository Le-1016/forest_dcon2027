"""Optional private SSH entry point. Server credentials never leave the VPS.

Bind to loopback only and forward this port over SSH. This is not a public gateway.
"""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

SSH_MARKER = "forest-via-private-ssh-transport"


class Bridge(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def forward(self):
        host = urlsplit("http://"+self.headers.get("Host", "")).hostname
        origin = self.headers.get("Origin")
        if host not in {"127.0.0.1", "localhost"} or (origin and urlsplit(origin).hostname not in {"127.0.0.1", "localhost"}):
            self.send_error(403)
            return
        if not self.path.startswith("/") or self.path.startswith("//"):
            self.send_error(400)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 64*1024*1024:
                self.send_error(413)
                return
            body = self.rfile.read(length) if length else None
            headers = {k:v for k,v in self.headers.items() if k.lower() in {"content-type", "x-job-lease", "x-content-sha256"}}
            if self.path.startswith("/api/ml/"):
                # Marker prevents cross-origin form requests. It is deliberately not a secret.
                if self.headers.get("Authorization") != "Bearer "+SSH_MARKER:
                    self.send_error(401)
                    return
                role = "FOREST_ML_WORKER_TOKEN" if self.path.startswith("/api/ml/worker/") else "FOREST_ML_TOKEN"
                headers["Authorization"] = "Bearer "+self.server.credentials[role]
            connection = http.client.HTTPConnection("127.0.0.1",self.server.upstream_port,timeout=40)
            try:
                connection.request(self.command,self.path,body,headers)
                response = connection.getresponse()
                content = response.read(65*1024*1024)
                mime = response.getheader("Content-Type", "application/octet-stream")
                if "text/html" in mime and self.path.split("?")[0] in {"/", "/monitor.html"}:
                    # Only the loopback-only monitor gets the public transport marker, never the VPS tokens.
                    bootstrap = f"<script>sessionStorage.setItem('forest.ml.token','{SSH_MARKER}');</script>".encode()
                    content = content.replace(b"</head>",bootstrap+b"</head>",1)
                self.send_response(response.status)
                self.send_header("Content-Type",mime)
                if response.getheader("Content-Disposition"):
                    self.send_header("Content-Disposition",response.getheader("Content-Disposition"))
                self.send_header("Content-Length",str(len(content)))
                self.send_header("Cache-Control","no-store")
                self.send_header("X-Content-Type-Options","nosniff")
                self.send_header("X-FOREST-Transport","private-ssh")
                self.end_headers()
                self.wfile.write(content)
            finally:
                connection.close()
        except (OSError, ValueError):
            self.send_error(502,"FOREST upstream unavailable")

    do_GET = do_POST = do_PUT = forward


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=18090)
    parser.add_argument("--upstream-port",type=int,default=8081)
    parser.add_argument("--secret-file",required=True)
    args=parser.parse_args()
    credentials={}
    for line in Path(args.secret_file).read_text(encoding="utf-8").splitlines():
        if line.startswith(("FOREST_ML_TOKEN=","FOREST_ML_WORKER_TOKEN=")):
            key,value=line.split("=",1);credentials[key]=value
    if min(len(credentials.get(k,"")) for k in ("FOREST_ML_TOKEN","FOREST_ML_WORKER_TOKEN")) < 24:
        raise ValueError("Invalid ML server credentials")
    server=ThreadingHTTPServer(("127.0.0.1",args.port),Bridge)
    server.credentials=credentials
    server.upstream_port=args.upstream_port
    print(f"FOREST_PRIVATE_SSH_READY 127.0.0.1:{args.port}",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=="__main__":
    main()
