"""Small durable training coordinator. No torch dependency on the VPS."""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CLASSES = ["normal", "fire", "smoke"]
ARTIFACTS = {"model.pth", "result.json"}
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}
ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
LEASE = 90


class Invalid(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise Invalid("invalid identifier")
    return value


def finite(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise Invalid("numeric value out of range")
    return value


class Coordinator(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state, monitor_token, worker_token, handler=None):
        if min(len(monitor_token), len(worker_token)) < 24 or monitor_token == worker_token:
            raise ValueError("set different FOREST_ML_TOKEN and FOREST_ML_WORKER_TOKEN (at least 24 characters each)")
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True)
        self.tokens = {"monitor": monitor_token, "worker": worker_token}
        with self.db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS workers (id TEXT PRIMARY KEY, body TEXT NOT NULL, seen REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, body TEXT NOT NULL)")
        super().__init__(address, handler or Handler)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.state / "training.sqlite3", timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def jobs(self, db):
        jobs = [json.loads(row[0]) for row in db.execute("SELECT body FROM jobs ORDER BY rowid DESC")]
        for job in jobs:
            if job["status"] == "RUNNING" and time.time() - job["heartbeat_at"] > LEASE:
                job.update(status="FAILED", error="WORKER_LOST: PCとの通信が90秒以上ありません。自動再実行はしません。", finished_at=time.time())
                self.save(db, job)
        return jobs

    @staticmethod
    def save(db, job):
        db.execute("UPDATE jobs SET body=? WHERE id=?", (json.dumps(job, allow_nan=False), job["id"]))

    @staticmethod
    def public(job):
        return {k: v for k, v in job.items() if k not in {"lease", "heartbeat_at"}}


class Handler(BaseHTTPRequestHandler):
    server_version = "FOREST-ML/1"

    def log_message(self, fmt, *args):
        # Never log tokens or request bodies.
        pass

    def reply(self, body, status=200):
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def body(self, limit=128_000):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise Invalid("invalid content length")
        if not 0 < size <= limit:
            raise Invalid("request size out of range", 413)
        data = self.rfile.read(size)
        if len(data) != size:
            raise Invalid("incomplete body")
        return data

    def payload(self):
        try:
            body = json.loads(self.body())
        except (ValueError, UnicodeError):
            raise Invalid("invalid JSON")
        if not isinstance(body, dict):
            raise Invalid("JSON object required")
        return body

    def route(self):
        path = self.path.split("?")[0].strip("/").split("/")
        role = "worker" if path[0] == "worker" else "monitor"
        given = self.headers.get("Authorization", "")
        if not hmac.compare_digest(given.encode(), ("Bearer " + self.server.tokens[role]).encode()):
            raise Invalid("学習サービスの認証が必要です。", 401)
        method = self.command
        if path == ["state"] and method == "GET":
            with self.server.db() as db:
                jobs = self.server.jobs(db)
                workers = []
                for body, seen in db.execute("SELECT body,seen FROM workers"):
                    worker = json.loads(body)
                    worker.update(last_seen_at=seen, online=time.time()-seen < 20)
                    workers.append(worker)
            return self.reply({"workers": workers, "jobs": [self.server.public(j) for j in jobs], "classes": CLASSES})
        if path == ["jobs"] and method == "POST":
            data = self.payload()
            request = identifier(data.get("request_id"))
            worker_id = identifier(data.get("worker_id"))
            kind = data.get("kind")
            if kind not in {"smoke_test", "image_classification"}:
                raise Invalid("unknown training kind")
            epochs = finite(data.get("epochs"), 1, 100)
            if not isinstance(epochs, int):
                raise Invalid("epochs must be an integer")
            lr = finite(data.get("learning_rate"), 0.00001, 0.1)
            dataset_id = identifier(data.get("dataset_id", "synthetic"))
            with self.server.db() as db:
                db.execute("BEGIN IMMEDIATE")
                old = db.execute("SELECT body FROM jobs WHERE request_id=?", (request,)).fetchone()
                if old:
                    old = json.loads(old[0])
                    if any(old[k] != v for k, v in {"worker_id": worker_id, "kind": kind, "epochs": epochs, "learning_rate": lr, "dataset_id": dataset_id}.items()):
                        raise Invalid("request_id already used with different settings", 409)
                    return self.reply(self.server.public(old))
                row = db.execute("SELECT body,seen FROM workers WHERE id=?", (worker_id,)).fetchone()
                if not row or time.time()-row[1] > 20:
                    raise Invalid("PCがオフラインです。ワーカーを起動してください。", 409)
                if kind == "image_classification":
                    datasets = json.loads(row[0])["datasets"]
                    dataset = next((d for d in datasets if d["id"] == dataset_id and d.get("ready")), None)
                    if not dataset:
                        raise Invalid("学習・検証画像を準備したデータセットを選択してください。", 409)
                else:
                    if dataset_id != "synthetic":
                        raise Invalid("smoke test requires synthetic dataset")
                    dataset = None
                if any(j["worker_id"] == worker_id and j["status"] not in TERMINAL for j in self.server.jobs(db)):
                    raise Invalid("このPCには実行中または待機中の学習があります。", 409)
                job = dict(id=uuid.uuid4().hex, request_id=request, worker_id=worker_id, kind=kind,
                           dataset_id=dataset_id, dataset_fingerprint=dataset["fingerprint"] if dataset else None,
                           epochs=epochs, learning_rate=lr, status="QUEUED", created_at=time.time(),
                           metrics=[], logs=["学習依頼を受け付けました。"], artifacts={}, cancel_requested=False)
                db.execute("INSERT INTO jobs VALUES (?,?,?)", (job["id"], request, json.dumps(job)))
            return self.reply(self.server.public(job), 201)
        if path == ["worker", "heartbeat"] and method == "POST":
            data = self.payload()
            worker_id = identifier(data.get("id"))
            gpu = str(data.get("device", ""))[:150]
            datasets = data.get("datasets", [])
            if not isinstance(datasets, list) or len(datasets) > 20:
                raise Invalid("invalid datasets")
            for ds in datasets:
                if not isinstance(ds, dict):
                    raise Invalid("invalid dataset")
                identifier(ds.get("id"))
                if len(json.dumps(ds)) > 4000:
                    raise Invalid("dataset metadata too large")
                if ds.get("classes") != CLASSES or not re.fullmatch(r"[0-9a-f]{64}", ds.get("fingerprint", "")):
                    raise Invalid("invalid dataset classes or fingerprint")
            safe = dict(id=worker_id, device=gpu, datasets=datasets)
            with self.server.db() as db:
                db.execute("INSERT OR REPLACE INTO workers VALUES (?,?,?)", (worker_id, json.dumps(safe), time.time()))
            return self.reply({"ok": True})
        if path == ["worker", "claim"] and method == "POST":
            worker_id = identifier(self.payload().get("worker_id"))
            with self.server.db() as db:
                db.execute("BEGIN IMMEDIATE")
                jobs = self.server.jobs(db)
                if any(j["status"] == "RUNNING" and j["worker_id"] == worker_id for j in jobs):
                    return self.reply({"job": None})
                for job in reversed(jobs):
                    if job["status"] == "QUEUED" and job["worker_id"] == worker_id:
                        job.update(status="RUNNING", started_at=time.time(), heartbeat_at=time.time(), lease=secrets.token_urlsafe(32))
                        self.server.save(db, job)
                        return self.reply({"job": job})
            return self.reply({"job": None})
        if len(path) == 3 and path[0] == "jobs" and path[2] == "cancel" and method == "POST":
            with self.server.db() as db:
                db.execute("BEGIN IMMEDIATE")
                job = self.find(db, path[1])
                if job["status"] not in TERMINAL:
                    job["cancel_requested"] = True
                    if job["status"] == "QUEUED":
                        job.update(status="CANCELLED", finished_at=time.time())
                    self.server.save(db, job)
            return self.reply(self.server.public(job))
        if len(path) == 4 and path[0] == "worker" and path[1] == "jobs":
            with self.server.db() as db:
                db.execute("BEGIN IMMEDIATE")
                job = self.find(db, path[2])
                if job["status"] != "RUNNING" or not hmac.compare_digest(self.headers.get("X-Job-Lease", ""), job.get("lease", "")):
                    raise Invalid("job lease expired", 409)
                job["heartbeat_at"] = time.time()
                if path[3] == "event" and method == "POST":
                    data = self.payload()
                    if "metric" in data:
                        m = data["metric"]
                        if not isinstance(m, dict):
                            raise Invalid("invalid metric")
                        epoch = finite(m.get("epoch"), 1, job["epochs"])
                        if not isinstance(epoch, int) or epoch != len(job["metrics"])+1:
                            raise Invalid("epochs must be sequential")
                        metric = {"epoch": epoch, "train_loss": finite(m.get("train_loss"), 0, 1e8),
                                  "val_loss": finite(m.get("val_loss"), 0, 1e8), "val_accuracy": finite(m.get("val_accuracy"), 0, 1)}
                        job["metrics"].append(metric)
                    if "message" in data:
                        job["logs"] = (job["logs"]+[str(data["message"])[:1500]])[-200:]
                    status = data.get("status")
                    if status:
                        if status not in TERMINAL:
                            raise Invalid("invalid job status")
                        if job["cancel_requested"]:
                            status = "CANCELLED"
                        if status == "COMPLETED" and (set(job["artifacts"]) != ARTIFACTS or len(job["metrics"]) != job["epochs"]):
                            raise Invalid("verified artifacts and all epoch metrics required", 409)
                        job.update(status=status, finished_at=time.time())
                        if status == "FAILED":
                            job["error"] = str(data.get("message", "学習に失敗しました。"))[:1500]
                    self.server.save(db, job)
                    return self.reply({"cancel_requested": job["cancel_requested"], "status": job["status"]})
        if len(path) == 5 and path[:2] == ["worker", "jobs"] and path[3] == "artifacts" and method == "PUT":
            name = path[4]
            if name not in ARTIFACTS:
                raise Invalid("unknown artifact")
            content = self.body(64 * 1024 * 1024 if name == "model.pth" else 128_000)
            digest = hashlib.sha256(content).hexdigest()
            if not hmac.compare_digest(digest, self.headers.get("X-Content-SHA256", "")):
                raise Invalid("artifact checksum mismatch")
            with self.server.db() as db:
                db.execute("BEGIN IMMEDIATE")
                job = self.find(db, path[2])
                if job["status"] != "RUNNING" or job["cancel_requested"] or not hmac.compare_digest(self.headers.get("X-Job-Lease", ""), job.get("lease", "")):
                    raise Invalid("job not accepting artifacts", 409)
                if name == "model.pth" and "result.json" in job["artifacts"] and digest != job["artifacts"]["model.pth"]["sha256"]:
                    raise Invalid("model cannot change after result verification", 409)
                if name == "result.json":
                    try:
                        result = json.loads(content)
                    except (ValueError, UnicodeError):
                        raise Invalid("invalid result JSON")
                    if not isinstance(result, dict) or result.get("model_sha256") != job["artifacts"].get("model.pth", {}).get("sha256"):
                        raise Invalid("result model checksum does not match uploaded model")
                    if result.get("job_id") != job["id"] or result.get("classes") != CLASSES or result.get("kind") != job["kind"]:
                        raise Invalid("result does not match job")
                    # Validate only the fixed public report; never store arbitrary remote fields.
                    matrix = result.get("confusion_matrix")
                    if not isinstance(matrix, list) or len(matrix) != 3 or any(not isinstance(r, list) or len(r) != 3 or any(type(v) is not int or not 0 <= v <= 1e7 for v in r) for r in matrix):
                        raise Invalid("invalid confusion matrix")
                    total = sum(map(sum, matrix))
                    accuracy = finite(result.get("val_accuracy"), 0, 1)
                    if not total or not job["metrics"] or abs(sum(matrix[i][i] for i in range(3))/total-accuracy) > 1e-8 or abs(job["metrics"][-1]["val_accuracy"]-accuracy) > 1e-8:
                        raise Invalid("result accuracy does not match metrics and confusion matrix")
                    job["result"] = dict(confusion_matrix=matrix, classes=CLASSES,
                                         val_accuracy=accuracy,
                                         training_device=str(result.get("training_device"))[:150],
                                         synthetic=job["kind"] == "smoke_test")
                directory = self.server.state / "artifacts" / job["id"]
                directory.mkdir(parents=True, exist_ok=True)
                temp = directory / (name+".tmp")
                temp.write_bytes(content)
                temp.replace(directory / name)
                job["artifacts"][name] = {"sha256": digest, "bytes": len(content)}
                self.server.save(db, job)
            return self.reply({"sha256": digest, "bytes": len(content)})
        if len(path) == 4 and path[0] == "jobs" and path[2] == "artifacts" and method == "GET":
            with self.server.db() as db:
                job = self.find(db, path[1])
            name = path[3]
            if job["status"] != "COMPLETED" or name not in job["artifacts"] or name not in ARTIFACTS:
                raise Invalid("artifact not available", 404)
            content = (self.server.state / "artifacts" / job["id"] / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{job["id"]}-{name}"')
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return
        raise Invalid("not found", 404)

    def find(self, db, job_id):
        identifier(job_id)
        self.server.jobs(db)
        row = db.execute("SELECT body FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise Invalid("job not found", 404)
        return json.loads(row[0])

    def handle_request(self):
        try:
            self.route()
        except Invalid as err:
            self.reply({"error": str(err)}, err.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.reply({"error": "学習サービス内部でエラーが発生しました。"}, 500)

    do_GET = do_POST = do_PUT = handle_request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--state", default=".ml-state")
    args = parser.parse_args()
    server = Coordinator((args.host, args.port), args.state, os.environ.get("FOREST_ML_TOKEN", ""), os.environ.get("FOREST_ML_WORKER_TOKEN", ""))
    print(f"FOREST_ML_READY {server.server_address}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
