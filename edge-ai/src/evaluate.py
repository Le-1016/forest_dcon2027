import argparse
import json
from pathlib import Path

import sys

import torch

from dataset import build_dataloaders
from model import build_model

DISPATCHER_DIR = Path(__file__).resolve().parents[1] / "dispatcher"
if str(DISPATCHER_DIR) not in sys.path:
    sys.path.insert(0, str(DISPATCHER_DIR))

from datasets import load_manifest, resolve_dataset


def calculate_metrics(confusion_matrix):
    num_classes = len(confusion_matrix)
    total = sum(sum(row) for row in confusion_matrix)
    correct = sum(confusion_matrix[i][i] for i in range(num_classes))

    per_class = []
    for i in range(num_classes):
        tp = confusion_matrix[i][i]
        fp = sum(confusion_matrix[r][i] for r in range(num_classes)) - tp
        fn = sum(confusion_matrix[i]) - tp
        support = sum(confusion_matrix[i])

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        per_class.append({
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        })

    macro = {
        "precision": sum(x["precision"] for x in per_class) / num_classes,
        "recall": sum(x["recall"] for x in per_class) / num_classes,
        "f1": sum(x["f1"] for x in per_class) / num_classes,
    }

    return correct / total if total else 0.0, per_class, macro


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate FOREST Edge AI image classifier"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for FOREST Edge AI evaluation")

    device = torch.device("cuda:0")

    manifest = load_manifest(args.dataset_id)
    dataset_path = resolve_dataset(args.dataset_id)

    requested_data = Path(args.data).resolve()
    if requested_data != dataset_path.resolve():
        raise ValueError(
            f"dataset path mismatch: "
            f"manifest={dataset_path.resolve()}, requested={requested_data}"
        )

    checkpoint = torch.load(
        args.model,
        map_location=device,
        weights_only=True,
    )

    classes = checkpoint["classes"]
    architecture = checkpoint["architecture"]
    image_size = checkpoint["image_size"]

    if architecture != "mobilenet_v3_small":
        raise ValueError(f"unsupported architecture: {architecture}")

    _, val_loader, dataset_classes = build_dataloaders(
        dataset_path,
        batch_size=args.batch_size,
        image_size=image_size,
    )

    if dataset_classes != classes:
        raise ValueError(
            f"model/dataset class mismatch: "
            f"model={classes}, dataset={dataset_classes}"
        )

    model = build_model(
        num_classes=len(classes),
        pretrained=False,
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    matrix = [
        [0 for _ in classes]
        for _ in classes
    ]

    with torch.no_grad():
        for images, labels in val_loader:
            images = images.to(device, non_blocking=True)
            outputs = model(images)
            predictions = outputs.argmax(dim=1).cpu()
            labels = labels.cpu()

            for actual, predicted in zip(labels.tolist(), predictions.tolist()):
                matrix[actual][predicted] += 1

    accuracy, per_class_values, macro = calculate_metrics(matrix)

    class_metrics = {
        name: values
        for name, values in zip(classes, per_class_values)
    }

    result = {
        "dataset_id": args.dataset_id,
        "dataset_task": manifest["task"],
        "architecture": architecture,
        "classes": classes,
        "image_size": image_size,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0),
        "validation_images": len(val_loader.dataset),
        "accuracy": accuracy,
        "confusion_matrix": matrix,
        "per_class": class_metrics,
        "macro_avg": macro,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    print("FOREST Model Evaluation", flush=True)
    print(f"Dataset: {args.dataset_id}", flush=True)
    print(f"Validation images: {len(val_loader.dataset)}", flush=True)
    print(f"Accuracy: {accuracy:.4f}", flush=True)
    print(f"Evaluation: {output_path}", flush=True)
    print("EVALUATION_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
