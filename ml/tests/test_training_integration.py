"""Explicit opt-in real PyTorch tests; generated fixtures are NOT fire-detection evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

from forest_ml.dataset import CLASSES, inventory
from forest_ml.server import Coordinator


@unittest.skipUnless(os.environ.get("FOREST_ML_INTEGRATION") == "1", "set FOREST_ML_INTEGRATION=1 for real training")
class TrainingIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.monitor, self.worker = "m"*32, "w"*32
        self.server = Coordinator(("127.0.0.1",0),self.folder/"state",self.monitor,self.worker)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_port}"
        self.datasets=self.folder/"images"
        import numpy as np
        from PIL import Image
        rng=np.random.default_rng(1234)
        for split,count in (("train",4),("val",2)):
            for channel,cls in enumerate(CLASSES):
                directory=self.datasets/split/cls
                directory.mkdir(parents=True)
                for i in range(count):
                    image=rng.integers(0,30,(64,64,3),dtype=np.uint8)
                    image[:,:,channel]+=180
                    Image.fromarray(image).save(directory/f"{i}.png")
        self.metadata=inventory(self.datasets,"fixture")[0]
        self.call("worker/heartbeat",dict(id="test-pc",device="integration",datasets=[self.metadata]),self.worker)

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.temp.cleanup()

    def call(self,path,body=None,token=None):
        request=urllib.request.Request(self.base+"/"+path,None if body is None else json.dumps(body).encode(),{"Authorization":"Bearer "+(token or self.monitor)})
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    def worker_process(self):
        env=dict(os.environ,FOREST_ML_WORKER_TOKEN=self.worker,PYTHONUTF8="1")
        return subprocess.Popen([sys.executable,"-m","forest_ml.worker","--server",self.base,"--worker-id","test-pc","--dataset",f"fixture={self.datasets}","--device",os.environ.get("FOREST_ML_TEST_DEVICE","cpu"),"--output",str(self.folder/"output"),"--once"],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8")

    def test_real_image_folder_train_export_reload_and_transfer(self):
        job=self.call("jobs",dict(request_id="image-test",worker_id="test-pc",kind="image_classification",dataset_id="fixture",epochs=2,learning_rate=.001))
        process=self.worker_process()
        output,_=process.communicate(timeout=90)
        self.assertEqual(process.returncode,0,output)
        completed=self.call("state")["jobs"][0]
        self.assertEqual(completed["status"],"COMPLETED",output+json.dumps(completed))
        self.assertEqual(len(completed["metrics"]),2)
        self.assertEqual(sum(map(sum,completed["result"]["confusion_matrix"])),6)
        artifact=self.folder/"output"/job["id"]
        result=json.loads((artifact/"result.json").read_text(encoding="utf-8"))
        self.assertTrue(result["reload_verified"])
        self.assertEqual(result["model_sha256"],hashlib.sha256((artifact/"model.pth").read_bytes()).hexdigest())
        self.assertEqual(result["dataset_fingerprint"],self.metadata["fingerprint"])
        prediction=subprocess.run([sys.executable,"-m","forest_ml.predict","--model",str(artifact/"model.pth"),"--image",str(self.datasets/"val/fire/0.png")],capture_output=True,env=dict(os.environ,PYTHONUTF8="1"),text=True,encoding="utf-8",timeout=30)
        self.assertEqual(prediction.returncode,0,prediction.stderr)
        self.assertAlmostEqual(sum(json.loads(prediction.stdout)["probabilities"].values()),1,places=5)

    def test_real_worker_stops_on_cancellation(self):
        job=self.call("jobs",dict(request_id="stop-test",worker_id="test-pc",kind="smoke_test",dataset_id="synthetic",epochs=100,learning_rate=.001))
        process=self.worker_process()
        try:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if self.call("state")["jobs"][0]["status"]=="RUNNING":
                    break
                time.sleep(.1)
            self.call(f"jobs/{job['id']}/cancel",{})
            output,_=process.communicate(timeout=30)
            self.assertEqual(process.returncode,0,output)
            stopped=self.call("state")["jobs"][0]
            self.assertEqual(stopped["status"],"CANCELLED",output+json.dumps(stopped))
            self.assertEqual(stopped["artifacts"],{})
        finally:
            if process.poll() is None:
                process.kill();process.communicate()


if __name__=="__main__":
    unittest.main()
