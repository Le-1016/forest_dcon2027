import concurrent.futures
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from forest_ml.server import Coordinator

MONITOR = "monitor-test-" + "x"*32
WORKER = "worker-test-" + "y"*32


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = Coordinator(("127.0.0.1", 0), self.temp.name, MONITOR, WORKER)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.call("worker/heartbeat", {"id":"pc", "device":"test", "datasets":[]}, token=WORKER)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path, body=None, token=MONITOR, method=None, lease=None, digest=None):
        encoded = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
        headers = {"Authorization":"Bearer " + token}
        if lease:
            headers["X-Job-Lease"] = lease
        if digest:
            headers["X-Content-SHA256"] = digest
        request = urllib.request.Request(self.base+"/"+path, encoded, headers, method=method)
        try:
            with urllib.request.urlopen(request) as response:
                data = response.read()
                return response.status, json.loads(data) if response.headers.get_content_type() == "application/json" else data
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def create(self, request="request_1", **kw):
        return self.call("jobs", dict(request_id=request, worker_id="pc", kind="smoke_test", dataset_id="synthetic", epochs=2, learning_rate=.001, **kw))

    def claim(self):
        return self.call("worker/claim", {"worker_id":"pc"}, token=WORKER)[1]["job"]

    def event(self, job, **data):
        return self.call(f"worker/jobs/{job['id']}/event", data, token=WORKER, lease=job["lease"])

    def test_auth_separation_and_no_leases_in_browser_response(self):
        self.assertEqual(self.call("state", token="")[0], 401)
        self.assertEqual(self.call("worker/claim", {"worker_id":"pc"})[0], 401)
        self.create()
        job = self.claim()
        self.assertTrue(job["lease"])
        state = self.call("state")[1]
        self.assertNotIn("lease", state["jobs"][0])

    def test_idempotency_and_single_claim_under_concurrency(self):
        status, job = self.create()
        self.assertEqual(status, 201)
        self.assertEqual(self.create()[1]["id"], job["id"])
        self.assertEqual(self.create("another")[0], 409)
        with concurrent.futures.ThreadPoolExecutor(4) as executor:
            claims = list(executor.map(lambda _: self.claim(), range(4)))
        self.assertEqual(sum(c is not None for c in claims), 1)

    def test_cancellation_and_expired_worker_fencing(self):
        self.create()
        job = self.claim()
        self.call(f"jobs/{job['id']}/cancel", {})
        self.assertTrue(self.event(job)[1]["cancel_requested"])
        self.assertEqual(self.event(job, status="CANCELLED")[0], 200)
        self.assertEqual(self.event(job, status="COMPLETED")[0], 409)
        self.create("second")
        job = self.claim()
        with self.server.db() as db:
            job["heartbeat_at"] = 0
            self.server.save(db, job)
        self.assertEqual(self.call("state")[1]["jobs"][0]["status"], "FAILED")
        self.assertEqual(self.event(job)[0], 409)

    def test_completion_requires_metrics_and_verified_artifacts(self):
        self.create()
        job = self.claim()
        self.assertEqual(self.event(job, status="COMPLETED")[0], 409)
        self.assertEqual(self.event(job, metric={"epoch":1,"train_loss":float('nan'),"val_loss":1,"val_accuracy":.5})[0], 400)
        for epoch in (1,2):
            self.assertEqual(self.event(job, metric={"epoch":epoch,"train_loss":1/epoch,"val_loss":.7,"val_accuracy":1})[0], 200)
        model = b"opaque model file, server never loads pickle"
        digest = hashlib.sha256(model).hexdigest()
        prefix = f"worker/jobs/{job['id']}/artifacts/"
        self.assertEqual(self.call(prefix+"model.pth", model, WORKER, "PUT", job["lease"], "0"*64)[0], 400)
        self.assertEqual(self.call(prefix+"model.pth", model, WORKER, "PUT", job["lease"], digest)[0], 200)
        result = json.dumps(dict(job_id=job["id"],kind="smoke_test",classes=["normal","fire","smoke"],model_sha256=digest,confusion_matrix=[[1,0,0],[0,1,0],[0,0,1]],val_accuracy=1,training_device="cpu")).encode()
        self.assertEqual(self.call(prefix+"result.json", result, WORKER, "PUT", job["lease"], hashlib.sha256(result).hexdigest())[0], 200)
        self.assertEqual(self.event(job,status="COMPLETED")[0], 200)
        self.assertEqual(self.call(f"jobs/{job['id']}/artifacts/model.pth")[1], model)

    def test_persistence_and_bad_inputs(self):
        self.create()
        second = Coordinator(("127.0.0.1", 0), self.temp.name, MONITOR, WORKER)
        with second.db() as db:
            self.assertEqual(len(second.jobs(db)), 1)
        second.server_close()
        self.assertEqual(self.call("jobs", ["bad"])[0],400)
        self.assertEqual(self.call("jobs", dict(request_id="bad",worker_id="../bad",kind="shell",epochs=1,learning_rate=.001))[0],400)


if __name__ == "__main__":
    unittest.main()
