"""Baseline 3-class image classifier. Not a certified fire alarm or detector."""
import hashlib
import json
from pathlib import Path
import random

from .dataset import CLASSES, inventory
from .model import build_model


class Cancelled(Exception):
    pass


def train(job, dataset_root, output, device, emit, cancelled):
    import numpy as np
    from PIL import Image, ImageOps
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset, TensorDataset

    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    # Small baseline avoids downloading pretrained weights and runs offline.
    torch.set_num_threads(2)
    model = build_model().to(device)
    synthetic = job["kind"] == "smoke_test"

    class Images(Dataset):
        def __init__(self, split, records):
            self.items = [(path, cls) for path, digest, s, cls in records if s == split]

        def __len__(self):
            return len(self.items)

        def __getitem__(self, index):
            path, cls = self.items[index]
            with Image.open(Path(dataset_root) / path) as image:
                image = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (96, 96))
                array = np.array(image, dtype=np.float32) / 255.0
            return torch.from_numpy(array).permute(2, 0, 1), CLASSES.index(cls)

    def fixture(seed):
        generator = torch.Generator().manual_seed(seed)
        labels = torch.arange(3).repeat_interleave(16)
        # Deliberately artificial colored images: only pipeline validation.
        x = torch.rand((48, 3, 96, 96), generator=generator) * 0.15
        for i, label in enumerate(labels):
            x[i, int(label)] += 0.7
        return TensorDataset(x, labels)

    if synthetic:
        training, validation = fixture(42), fixture(43)
        fingerprint = None
    else:
        meta, records = inventory(dataset_root, job["dataset_id"])
        if not meta["ready"]:
            raise ValueError("Dataset invalid: " + "; ".join(meta["errors"]))
        fingerprint = meta["fingerprint"]
        if fingerprint != job["dataset_fingerprint"]:
            raise ValueError("Dataset changed after training request; refresh dataset and create a new job")
        training, validation = Images("train", records), Images("val", records)
    train_loader = DataLoader(training, batch_size=16, shuffle=True, num_workers=0)
    val_loader = DataLoader(validation, batch_size=16, shuffle=False, num_workers=0)
    optimizer = torch.optim.Adam(model.parameters(), lr=job["learning_rate"])
    criterion = nn.CrossEntropyLoss()
    emit(message=f"{device} / train={len(training)} / val={len(validation)} / {'合成データの接続テスト' if synthetic else '火災・煙・通常の画像分類'}")
    history = []
    for epoch in range(1, job["epochs"]+1):
        model.train()
        total = 0.0
        for images, labels in train_loader:
            if cancelled():
                raise Cancelled()
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), labels)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss")
            loss.backward()
            optimizer.step()
            total += loss.item() * len(labels)
        model.eval()
        val_loss, correct = 0.0, 0
        matrix = torch.zeros((3, 3), dtype=torch.int64)
        with torch.inference_mode():
            for images, labels in val_loader:
                if cancelled():
                    raise Cancelled()
                logits = model(images.to(device))
                val_loss += criterion(logits, labels.to(device)).item() * len(labels)
                predictions = logits.argmax(1).cpu()
                correct += int((predictions == labels).sum())
                for actual, prediction in zip(labels, predictions):
                    matrix[int(actual), int(prediction)] += 1
        metric = dict(epoch=epoch, train_loss=total/len(training), val_loss=val_loss/len(validation), val_accuracy=correct/len(validation))
        history.append(metric)
        emit(metric=metric, message=f"epoch {epoch}/{job['epochs']} loss={metric['train_loss']:.5f} val_accuracy={metric['val_accuracy']:.1%}")
    if cancelled():
        raise Cancelled()
    # Abort if the dataset was edited while training, rather than publishing a misleading fingerprint.
    if not synthetic and inventory(dataset_root, job["dataset_id"])[0]["fingerprint"] != fingerprint:
        raise ValueError("Dataset changed during training")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    model_file = output / "model.pth"
    state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
    torch.save(dict(state_dict=state, architecture="forest_cnn_v1", classes=CLASSES, image_size=96,
                    preprocessing="EXIF transpose, RGB, center-crop resize, float32 / 255", synthetic=synthetic), model_file)
    # Reload tensors only; do not execute pickle objects from untrusted uploads.
    reloaded = torch.load(model_file, map_location="cpu", weights_only=True)
    cpu_model = model.to("cpu")
    cpu_model.load_state_dict(reloaded["state_dict"])
    cpu_model.eval()
    if not torch.isfinite(cpu_model(torch.zeros(1, 3, 96, 96))).all():
        raise ValueError("Reload validation failed")
    result = dict(job_id=job["id"], kind=job["kind"], classes=CLASSES, architecture="forest_cnn_v1",
                  synthetic=synthetic, dataset_fingerprint=fingerprint, training_device=str(device),
                  pytorch=torch.__version__, cuda=torch.version.cuda, history=history,
                  val_accuracy=history[-1]["val_accuracy"], confusion_matrix=matrix.tolist(),
                  model_sha256=hashlib.sha256(model_file.read_bytes()).hexdigest(), reload_verified=True)
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return output
