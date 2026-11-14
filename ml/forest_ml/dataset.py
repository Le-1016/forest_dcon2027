"""Fixed train/val folders. Fingerprints guard against accidental data changes."""
import hashlib
import json
from pathlib import Path

CLASSES = ["normal", "fire", "smoke"]
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def inventory(root, dataset_id):
    root = Path(root).resolve()
    counts = {s: {c: 0 for c in CLASSES} for s in ("train", "val")}
    records, seen, errors = [], {}, []
    for split in counts:
        for cls in CLASSES:
            folder = root / split / cls
            if not folder.is_dir():
                errors.append(f"{split}/{cls} がありません")
                continue
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                    continue
                if not path.resolve().is_relative_to(root):
                    raise ValueError("Dataset symlink leaves approved folder")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest in seen:
                    errors.append(f"同じ画像の重複: {path.relative_to(root)} / {seen[digest]}")
                seen[digest] = str(path.relative_to(root))
                counts[split][cls] += 1
                records.append((str(path.relative_to(root)), digest, split, cls))
            if not counts[split][cls]:
                errors.append(f"{split}/{cls} に画像が必要です")
    fingerprint = hashlib.sha256(json.dumps(records, ensure_ascii=False).encode()).hexdigest()
    metadata = dict(id=dataset_id, classes=CLASSES, counts=counts, fingerprint=fingerprint,
                    ready=not errors, errors=errors[:8], image_count=len(records))
    return metadata, records
