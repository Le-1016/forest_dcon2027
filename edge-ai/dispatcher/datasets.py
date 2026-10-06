from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

DATASETS = {
    "forest-smoke-v0": REPO_ROOT / "edge-ai" / "data",
}


def resolve_dataset(dataset_id: str) -> Path:
    try:
        path = DATASETS[dataset_id]
    except KeyError as exc:
        raise ValueError(
            f"unknown dataset_id: {dataset_id}"
        ) from exc

    if not path.exists():
        raise FileNotFoundError(
            f"dataset not found: {path}"
        )

    train_dir = path / "train"
    val_dir = path / "val"

    if not train_dir.is_dir():
        raise FileNotFoundError(
            f"train directory not found: {train_dir}"
        )

    if not val_dir.is_dir():
        raise FileNotFoundError(
            f"validation directory not found: {val_dir}"
        )

    return path


def main():
    dataset_id = "forest-smoke-v0"
    path = resolve_dataset(dataset_id)

    print(f"DATASET_ID={dataset_id}")
    print(f"DATASET_PATH={path}")
    print("DATASET_READY")


if __name__ == "__main__":
    main()