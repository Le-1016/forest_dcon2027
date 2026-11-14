"""GPU PC pulls bounded jobs over an authenticated HTTP connection. Never executes remote code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .dataset import inventory
from .trainer import Cancelled, train


class Client:
    def __init__(self, base, token):
        self.base, self.token = base.rstrip("/"), token
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Invalid server URL")
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, data, method="POST", lease=None, binary=False):
        body = data if binary else json.dumps(data).encode()
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/octet-stream" if binary else "application/json"}
        if lease:
            headers["X-Job-Lease"] = lease
        if binary:
            headers["X-Content-SHA256"] = hashlib.sha256(body).hexdigest()
        req = urllib.request.Request(self.base+"/"+path, body, headers, method=method)
        with self.opener.open(req, timeout=30) as response:
            return json.load(response)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def run(args):
    import torch
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU unavailable. GPUを確認してください。CPUテスト時のみ --device cpu を指定できます。")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", args.worker_id):
        raise ValueError("invalid worker id")
    datasets = {}
    for pair in args.dataset:
        key, path = pair.split("=", 1)
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", key) or key == "synthetic":
            raise ValueError("invalid dataset id")
        datasets[key] = Path(path).resolve()
    token = os.environ.get("FOREST_ML_WORKER_TOKEN", "")
    if args.ssh_session:
        from .ssh_bridge import SSH_MARKER
        if urllib.parse.urlsplit(args.server).hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("--ssh-session requires a local SSH forward")
        token = SSH_MARKER
    if len(token) < 24:
        raise ValueError("Set FOREST_ML_WORKER_TOKEN")
    client = Client(args.server, token)
    device = torch.cuda.get_device_name(0) if args.device == "cuda" else "CPU (test)"
    metadata = [inventory(path, key)[0] for key, path in datasets.items()]
    print(f"WORKER_READY | {args.worker_id} | {device}", flush=True)

    def heartbeat():
        client.request("worker/heartbeat", dict(id=args.worker_id, device=device, datasets=metadata))

    while True:
        metadata = [inventory(path, key)[0] for key, path in datasets.items()]
        try:
            heartbeat()
            job = client.request("worker/claim", {"worker_id": args.worker_id})["job"]
        except (OSError, ValueError) as error:
            print(f"接続待ち: {type(error).__name__}", flush=True)
            if args.once:
                raise
            time.sleep(5)
            continue
        if not job:
            if args.once:
                return
            time.sleep(5)
            continue
        # Only the two built-in trainers exist; no user-supplied paths, modules or commands.
        if not re.fullmatch(r"[0-9a-f]{32}", job["id"]) or job["kind"] not in {"smoke_test", "image_classification"}:
            raise ValueError("Invalid job")
        print("JOB_STARTED: " + job["id"], flush=True)
        stopped, cancelled = threading.Event(), threading.Event()
        last_contact = [time.monotonic()]

        def emit(**data):
            response = client.request(f"worker/jobs/{job['id']}/event", data, lease=job["lease"])
            last_contact[0] = time.monotonic()
            if response["cancel_requested"]:
                cancelled.set()
            if "message" in data:
                print(data["message"], flush=True)
            return response

        def pulse():
            while not stopped.wait(4):
                try:
                    heartbeat()
                    emit()
                except urllib.error.HTTPError as error:
                    if error.code in (401, 409):
                        cancelled.set()
                    elif time.monotonic()-last_contact[0] > 45:
                        cancelled.set()
                except OSError:
                    if time.monotonic()-last_contact[0] > 45:
                        cancelled.set()

        thread = threading.Thread(target=pulse, daemon=True)
        thread.start()
        try:
            if job["kind"] == "image_classification" and job["dataset_id"] not in datasets:
                raise ValueError("Dataset is not approved on this PC")
            folder = train(job, datasets.get(job["dataset_id"]), Path(args.output)/job["id"], args.device, emit, cancelled.is_set)
            if cancelled.is_set():
                raise Cancelled()
            for name in ("model.pth", "result.json"):
                content = (folder / name).read_bytes()
                result = client.request(f"worker/jobs/{job['id']}/artifacts/{name}", content, method="PUT", lease=job["lease"], binary=True)
                if result["sha256"] != hashlib.sha256(content).hexdigest():
                    raise ValueError("Transfer checksum mismatch")
            emit(status="COMPLETED", message="モデルの再読込・SHA-256照合・結果返却を完了しました。")
            print("TRANSFER_VERIFIED | JOB_COMPLETED: " + job["id"], flush=True)
        except (Cancelled, KeyboardInterrupt):
            try:
                emit(status="CANCELLED", message="学習を停止しました。")
            except OSError:
                pass
        except Exception as error:
            try:
                emit(status="FAILED", message=f"{type(error).__name__}: {str(error)[:1200]}")
            except OSError:
                pass
            print(f"JOB_FAILED: {type(error).__name__}", flush=True)
        finally:
            stopped.set()
            thread.join(timeout=2)
        if args.once:
            return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True, help="e.g. http://127.0.0.1:8081/api/ml")
    parser.add_argument("--worker-id", default="forest-gpu-pc")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--dataset", action="append", default=[], metavar="ID=FOLDER")
    parser.add_argument("--output", default=".ml-runs")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--ssh-session",action="store_true",help="use a local SSH forward to the VPS private bridge; no server secrets on the PC")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
