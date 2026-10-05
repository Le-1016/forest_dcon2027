import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn

from dataset import build_dataloaders
from model import build_model


def evaluate(model, loader, device):
    model.eval()
    correct = 0
    total = 0
    loss_sum = 0.0
    criterion = nn.CrossEntropyLoss()

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            outputs = model(images)
            loss = criterion(outputs, labels)

            loss_sum += loss.item() * images.size(0)
            correct += (outputs.argmax(dim=1) == labels).sum().item()
            total += images.size(0)

    return {
        "loss": loss_sum / total,
        "accuracy": correct / total,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Train FOREST Edge AI image classifier"
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--pretrained", action="store_true")
    args = parser.parse_args()

    if args.epochs < 1:
        raise ValueError("epochs must be at least 1")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for FOREST Edge AI training")

    device = torch.device("cuda:0")

    print("FOREST Edge AI training", flush=True)
    print("GPU:", torch.cuda.get_device_name(0), flush=True)

    train_loader, val_loader, classes = build_dataloaders(
        args.data,
        batch_size=args.batch_size,
        image_size=args.image_size,
    )

    print("Classes:", classes, flush=True)
    print("Train images:", len(train_loader.dataset), flush=True)
    print("Validation images:", len(val_loader.dataset), flush=True)

    model = build_model(
        num_classes=len(classes),
        pretrained=args.pretrained,
    ).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    history = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        total = 0

        for images, labels in train_loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)

            outputs = model(images)
            loss = criterion(outputs, labels)

            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            total += images.size(0)

        train_loss = running_loss / total
        validation = evaluate(model, val_loader, device)

        result = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": validation["loss"],
            "val_accuracy": validation["accuracy"],
        }
        history.append(result)

        print(
            f"epoch={epoch} "
            f"train_loss={train_loss:.4f} "
            f"val_loss={validation['loss']:.4f} "
            f"val_accuracy={validation['accuracy']:.4f}",
            flush=True,
        )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "model.pth"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "classes": classes,
            "architecture": "mobilenet_v3_small",
            "image_size": args.image_size,
        },
        model_path,
    )

    metadata = {
        "architecture": "mobilenet_v3_small",
        "classes": classes,
        "num_classes": len(classes),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "image_size": args.image_size,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0),
        "pytorch": torch.__version__,
        "final": history[-1],
        "history": history,
    }

    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print("TRAINING_COMPLETE", flush=True)
    print("Model:", model_path, flush=True)
    print("Metadata:", metadata_path, flush=True)


if __name__ == "__main__":
    main()