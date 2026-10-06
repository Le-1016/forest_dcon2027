import argparse
import json
import subprocess
import sys
from pathlib import Path

from datasets import load_manifest, resolve_dataset
from job_v1 import ForestEdgeTrainJob


REPO_ROOT = Path(__file__).resolve().parents[2]
TRAIN_SCRIPT = REPO_ROOT / "edge-ai" / "src" / "train.py"


def load_job(path: Path) -> ForestEdgeTrainJob:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    job = ForestEdgeTrainJob(**data)
    job.validate()
    return job


def main():
    parser = argparse.ArgumentParser(
        description="Run a FOREST GPU training job"
    )
    parser.add_argument("--job", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the training command without running it",
    )
    args = parser.parse_args()

    job = load_job(Path(args.job))
    manifest = load_manifest(job.dataset_id)
    dataset_path = resolve_dataset(job.dataset_id)

    command = [
        sys.executable,
        str(TRAIN_SCRIPT),
        "--data",
        str(dataset_path),
        "--dataset-id",
        job.dataset_id,
        "--dataset-task",
        manifest["task"],
        "--output",
        args.output,
        "--epochs",
        str(job.epochs),
        "--batch-size",
        str(job.batch_size),
        "--image-size",
        str(job.image_size),
    ]

    if job.pretrained:
        command.append("--pretrained")

    print(f"JOB_TYPE={job.job_type}")
    print(f"GIT_COMMIT={job.git_commit}")
    print(f"DATASET_ID={job.dataset_id}")
    print(f"DATASET_TASK={manifest['task']}")
    print("TRAIN_COMMAND")
    print(subprocess.list2cmdline(command))

    if args.dry_run:
        print("DRY_RUN_OK")
        return

    subprocess.run(command, check=True)
    print("JOB_COMPLETE")


if __name__ == "__main__":
    main()