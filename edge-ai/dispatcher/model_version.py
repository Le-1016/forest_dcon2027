import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def validate_identifier(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise ValueError(f"invalid {name}: {value}")


def create(args):
    model = Path(args.model)
    metadata_path = Path(args.metadata)
    output = Path(args.output)

    if not model.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("model.pth or metadata.json not found")

    validate_identifier(args.model_id, "model_id")
    validate_identifier(args.version, "version")

    if not re.fullmatch(r"[0-9a-f]{40}", args.git_commit):
        raise ValueError("git_commit must be a full 40-character SHA")

    metadata = read_json(metadata_path)

    job = read_json(Path(args.job)) if args.job else None
    if job is not None:
        result = job.get("result", {})
        if job.get("status") != "COMPLETED":
            raise ValueError("job must be COMPLETED")
        if result.get("job_id") != job.get("id"):
            raise ValueError("job ID mismatch")
        if result.get("model_sha256") != sha256(model):
            raise ValueError("job model SHA256 mismatch")
        if result.get("metadata_sha256") != sha256(metadata_path):
            raise ValueError("job metadata SHA256 mismatch")
        if job.get("git_commit") != args.git_commit:
            raise ValueError("job git_commit mismatch")
        for key in ("git_commit", "dataset_id"):
            if result.get(key) != job.get(key):
                raise ValueError(f"job result mismatch: {key}")
        for key in ("epochs", "batch_size", "image_size"):
            if job.get(key) != metadata.get(key):
                raise ValueError(f"job metadata mismatch: {key}")
        if "dataset_id" in metadata and metadata["dataset_id"] != job["dataset_id"]:
            raise ValueError("dataset_id mismatch")
        metadata = dict(metadata)
        metadata.setdefault("dataset_id", job["dataset_id"])
        metadata.setdefault("dataset_task", "image_classification")

    required = ("dataset_id", "dataset_task", "architecture", "classes",
                "epochs", "batch_size", "image_size")
    for field in required:
        if field not in metadata:
            raise ValueError(f"missing metadata field: {field}")

    files = {
        "model": {
            "filename": model.name,
            "sha256": sha256(model),
        },
        "metadata": {
            "filename": metadata_path.name,
            "sha256": sha256(metadata_path),
        },
    }

    if job is not None:
        job_path = Path(args.job)
        if job_path.parent.resolve() != output.parent.resolve():
            raise ValueError("job and manifest must share a directory")
        files["job"] = {
            "filename": job_path.name,
            "sha256": sha256(job_path),
        }

    if args.evaluation:
        evaluation_path = Path(args.evaluation)
        if not evaluation_path.is_file():
            raise FileNotFoundError(evaluation_path)
        evaluation = read_json(evaluation_path)
        if evaluation.get("dataset_id") != metadata["dataset_id"]:
            raise ValueError("evaluation dataset_id mismatch")
        if evaluation.get("classes") != metadata["classes"]:
            raise ValueError("evaluation classes mismatch")
        if evaluation.get("architecture") != metadata["architecture"]:
            raise ValueError("evaluation architecture mismatch")
        files["evaluation"] = {
            "filename": evaluation_path.name,
            "sha256": sha256(evaluation_path),
        }

    if len({entry["filename"] for entry in files.values()}) != len(files):
        raise ValueError("artifact filenames must be unique")

    if any(Path(entry["filename"]).parent != Path(".") for entry in files.values()):
        raise ValueError("artifact filenames must not contain directories")

    if any(path.parent.resolve() != output.parent.resolve()
           for path in [model, metadata_path] +
           ([Path(args.evaluation)] if args.evaluation else [])):
        raise ValueError("all artifacts and manifest must share a directory")

    manifest = {
        "schema_version": 1,
        "model_id": args.model_id,
        "model_version": args.version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": args.git_commit,
        "dataset_id": metadata["dataset_id"],
        "dataset_task": metadata["dataset_task"],
        "architecture": metadata["architecture"],
        "classes": metadata["classes"],
        "training": {
            "epochs": metadata["epochs"],
            "batch_size": metadata["batch_size"],
            "image_size": metadata["image_size"],
        },
        "provenance": {
            "dataset_id_source": (
                "training_metadata" if "dataset_id" in read_json(metadata_path)
                else "dispatcher_job"
            ),
            "dataset_task_source": (
                "training_metadata" if "dataset_task" in read_json(metadata_path)
                else "legacy_compatibility_default"
            ),
        },
        "files": files,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("MODEL_MANIFEST_CREATED", output)


def verify(args):
    manifest_path = Path(args.manifest)
    manifest = read_json(manifest_path)

    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported model manifest schema")

    validate_identifier(manifest.get("model_id"), "model_id")
    validate_identifier(manifest.get("model_version"), "model_version")

    files = manifest.get("files")
    if not isinstance(files, dict) or not {"model", "metadata"} <= files.keys():
        raise ValueError("missing required model artifacts")

    for kind, entry in files.items():
        filename = entry["filename"]
        if Path(filename).name != filename or filename in (".", ".."):
            raise ValueError(f"unsafe artifact filename: {filename}")
        path = manifest_path.parent / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256(path)
        if actual != entry["sha256"]:
            raise ValueError(f"SHA256_MISMATCH: {kind}")

    job = None
    if "job" in files:
        job = read_json(manifest_path.parent / files["job"]["filename"])
        result = job.get("result", {})
        if job.get("status") != "COMPLETED":
            raise ValueError("job must be COMPLETED")
        if result.get("job_id") != job.get("id"):
            raise ValueError("job ID mismatch")
        if result.get("model_sha256") != files["model"]["sha256"]:
            raise ValueError("job model SHA256 mismatch")
        if result.get("metadata_sha256") != files["metadata"]["sha256"]:
            raise ValueError("job metadata SHA256 mismatch")
        if job.get("git_commit") != manifest["git_commit"]:
            raise ValueError("job git_commit mismatch")
        for key in ("git_commit", "dataset_id"):
            if result.get(key) != job.get(key):
                raise ValueError(f"job result mismatch: {key}")
        if job.get("dataset_id") != manifest["dataset_id"]:
            raise ValueError("job dataset_id mismatch")

    metadata = read_json(manifest_path.parent / files["metadata"]["filename"])
    for key in ("dataset_id", "dataset_task", "architecture", "classes"):
        expected = metadata.get(key)
        if expected is None and job is not None and key == "dataset_id":
            expected = job.get("dataset_id")
        if expected is None and job is not None and key == "dataset_task":
            expected = "image_classification"
        if manifest[key] != expected:
            raise ValueError(f"metadata mismatch: {key}")

    if "evaluation" in files:
        evaluation = read_json(manifest_path.parent / files["evaluation"]["filename"])
        for key in ("dataset_id", "architecture", "classes"):
            if manifest[key] != evaluation[key]:
                raise ValueError(f"evaluation mismatch: {key}")

    print("MODEL_MANIFEST_VERIFIED", manifest["model_id"], manifest["model_version"])


def main():
    parser = argparse.ArgumentParser(description="FOREST Model Version v1")
    sub = parser.add_subparsers(dest="command", required=True)

    create_parser = sub.add_parser("create")
    create_parser.add_argument("--model-id", required=True)
    create_parser.add_argument("--version", required=True)
    create_parser.add_argument("--git-commit", required=True)
    create_parser.add_argument("--model", required=True)
    create_parser.add_argument("--metadata", required=True)
    create_parser.add_argument("--evaluation")
    create_parser.add_argument("--job")
    create_parser.add_argument("--output", required=True)

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--manifest", required=True)

    args = parser.parse_args()
    if args.command == "create":
        create(args)
    else:
        verify(args)


if __name__ == "__main__":
    main()
