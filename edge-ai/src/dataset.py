from pathlib import Path

from torch.utils.data import DataLoader
from torchvision import datasets, transforms


def build_dataloaders(
    data_dir: str,
    batch_size: int = 16,
    image_size: int = 224,
):
    root = Path(data_dir)

    train_dir = root / "train"
    val_dir = root / "val"

    if not train_dir.is_dir():
        raise FileNotFoundError(f"train directory not found: {train_dir}")
    if not val_dir.is_dir():
        raise FileNotFoundError(f"val directory not found: {val_dir}")

    train_transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    val_transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    train_dataset = datasets.ImageFolder(train_dir, transform=train_transform)
    val_dataset = datasets.ImageFolder(val_dir, transform=val_transform)

    if train_dataset.classes != val_dataset.classes:
        raise ValueError(
            f"class mismatch: train={train_dataset.classes}, "
            f"val={val_dataset.classes}"
        )

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )

    return train_loader, val_loader, train_dataset.classes