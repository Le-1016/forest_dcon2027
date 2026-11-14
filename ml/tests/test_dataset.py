from pathlib import Path
import tempfile
import unittest

from forest_ml.dataset import CLASSES, inventory


class DatasetTests(unittest.TestCase):
    def test_missing_classes_and_train_validation_leakage(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(inventory(folder,"fire-smoke")[0]["ready"])
            for split in ("train","val"):
                for cls in CLASSES:
                    path = Path(folder)/split/cls/"sample.png"
                    path.parent.mkdir(parents=True)
                    path.write_bytes((split+cls).encode())
            meta, _ = inventory(folder,"fire-smoke")
            self.assertTrue(meta["ready"])
            (Path(folder)/"val/fire/sample.png").write_bytes((Path(folder)/"train/fire/sample.png").read_bytes())
            changed,_ = inventory(folder,"fire-smoke")
            self.assertFalse(changed["ready"])
            self.assertNotEqual(meta["fingerprint"],changed["fingerprint"])


if __name__ == "__main__":
    unittest.main()
