import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "edge-ai" / "datasets"

DATASET_PATHS = {
    "forest-smoke-v0": REPO_ROOT / "edge-ai" / "data",
}


def load_manifest(dataset_id: str) -> dict:
    manifest_path = MANIFEST_DIR / f"{dataset_id}.json"

    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"dataset manifest not found: {manifest_path}"
        )

    with manifest_path.open("r", encoding="utf-8-sig") as f:
        manifest = json.load(f)

    if manifest.get("schema_version") != 1:
        raise ValueError(
            f"unsupported dataset schema_version: "
            f"{manifest.get('schema_version')}"
        )

    if manifest.get("dataset_id") != dataset_id:
        raise ValueError(
            f"dataset_id mismatch: expected {dataset_id}, "
            f"got {manifest.get('dataset_id')}"
        )

    if manifest.get("task") != "image_classification":
        raise ValueError(
            f"unsupported dataset task: {manifest.get('task')}"
        )

    classes = manifest.get("classes")
    if (
        not isinstance(classes, list)
        or len(classes) < 2
        or any(not isinstance(name, str) or not name.strip() for name in classes)
        or len(classes) != len(set(classes))
    ):
        raise ValueError(
            "dataset manifest classes must contain at least two "
            "unique non-empty strings"
        )

    splits = manifest.get("splits")
    if not isinstance(splits, dict):
        raise ValueError("dataset manifest splits must be an object")

    return manifest


def resolve_dataset(dataset_id: str) -> Path:
    manifest = load_manifest(dataset_id)

    try:
        path = DATASET_PATHS[dataset_id]
    except KeyError as exc:
        raise ValueError(
            f"dataset path not configured: {dataset_id}"
        ) from exc

    if not path.exists():
        raise FileNotFoundError(
            f"dataset not found: {path}"
        )

    splits = manifest.get("splits", {})
    train_name = splits.get("train")
    val_name = splits.get("validation")

    if not train_name or not val_name:
        raise ValueError(
            "dataset manifest must define train and validation splits"
        )

    train_dir = path / train_name
    val_dir = path / val_name

    if not train_dir.is_dir():
        raise FileNotFoundError(
            f"train directory not found: {train_dir}"
        )

    if not val_dir.is_dir():
        raise FileNotFoundError(
            f"validation directory not found: {val_dir}"
        )

    expected_classes = sorted(manifest["classes"])
    train_classes = sorted(
        entry.name for entry in train_dir.iterdir() if entry.is_dir()
    )
    val_classes = sorted(
        entry.name for entry in val_dir.iterdir() if entry.is_dir()
    )

    if train_classes != expected_classes:
        raise ValueError(
            f"train classes do not match manifest: "
            f"expected={expected_classes}, actual={train_classes}"
        )

    if val_classes != expected_classes:
        raise ValueError(
            f"validation classes do not match manifest: "
            f"expected={expected_classes}, actual={val_classes}"
        )

    return path


def main():
    dataset_id = "forest-smoke-v0"
    manifest = load_manifest(dataset_id)
    path = resolve_dataset(dataset_id)

    print(f"DATASET_ID={dataset_id}")
    print(f"DATASET_TASK={manifest['task']}")
    print(f"DATASET_STATUS={manifest['status']}")
    print(f"DATASET_PATH={path}")
    print("DATASET_READY")


if __name__ == "__main__":
    main()
