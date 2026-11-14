"""Local training monitor without PostgreSQL; binds only to loopback."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
import webbrowser

from .server import Coordinator, Handler, Invalid

ROOT = Path(__file__).resolve().parents[2] / "forest"
HTML = '''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FOREST 機械学習</title><link rel="stylesheet" href="/css/app.css"><link rel="stylesheet" href="/css/training.css"></head><body><aside><a class="brand" href="/">♠ FOREST<span>機械学習モニター</span></a><p>火災 / 煙 / 通常</p><p class="muted">ローカル起動<br>実際の学習結果を表示</p></aside><div class="workspace"><header>LOCAL / MACHINE LEARNING</header><main><h1>機械学習</h1><div id="ml-root"></div></main></div><script type="module">import {mountTraining} from '/js/training.js';mountTraining(document.querySelector('#ml-root'));</script></body></html>'''


class LocalHandler(Handler):
    def route(self):
        if self.path.startswith("/api/ml/"):
            self.path = self.path[len("/api/ml"):]
            return super().route()
        path = self.path.split("?")[0]
        if self.command != "GET":
            raise Invalid("not found",404)
        if path == "/":
            content, mime = HTML.encode(), "text/html; charset=utf-8"
        else:
            # Deliberately serve only frontend assets; never the repository or local secrets.
            file = (ROOT / path.lstrip("/")).resolve()
            if not file.is_relative_to(ROOT.resolve()) or path.split("/")[1] not in {"js","css","assets"} or not file.is_file():
                raise Invalid("not found",404)
            content, mime = file.read_bytes(), mimetypes.guess_type(str(file))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(content)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--state",default=".ml-state")
    parser.add_argument("--with-worker",action="store_true",help="also start the GPU PC worker")
    parser.add_argument("--dataset",action="append",default=[],metavar="ID=FOLDER")
    parser.add_argument("--open-browser",action="store_true")
    args = parser.parse_args()
    folder = Path(args.state)
    folder.mkdir(parents=True,exist_ok=True)
    credentials = folder / "local-tokens.json"
    if not credentials.exists():
        credentials.write_text(json.dumps({"monitor":secrets.token_urlsafe(32),"worker":secrets.token_urlsafe(32)}),encoding="utf-8")
        credentials.chmod(0o600)
    tokens = json.loads(credentials.read_text(encoding="utf-8"))
    server = Coordinator(("127.0.0.1",args.port),folder,tokens["monitor"],tokens["worker"],LocalHandler)
    print(f"FOREST_LOCAL_READY http://127.0.0.1:{server.server_port}/",flush=True)
    print(f"認証キーは {credentials.resolve()} の monitor を使用してください。",flush=True)
    process = None
    if args.with_worker:
        command = [sys.executable,"-m","forest_ml.worker","--server",f"http://127.0.0.1:{server.server_port}/api/ml","--output",str(folder/"runs")]
        for dataset in args.dataset:
            command.extend(["--dataset",dataset])
        process = subprocess.Popen(command,cwd=Path(__file__).resolve().parents[1],env=dict(os.environ,FOREST_ML_WORKER_TOKEN=tokens["worker"]))
    if args.open_browser:
        webbrowser.open(f"http://127.0.0.1:{server.server_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        server.server_close()


if __name__ == "__main__":
    main()
