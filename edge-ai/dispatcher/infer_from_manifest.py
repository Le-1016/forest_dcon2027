import argparse
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = ROOT / "edge-ai" / "dispatcher"
INFER = ROOT / "edge-ai" / "src" / "infer.py"

sys.path.insert(0, str(DISPATCHER))
from model_version import verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()

    with contextlib.redirect_stdout(io.StringIO()):
        verify(argparse.Namespace(manifest=str(manifest_path)))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    model_path = manifest_path.parent / manifest["files"]["model"]["filename"]

    completed = subprocess.run(
        [
            sys.executable,
            str(INFER),
            "--model",
            str(model_path),
            "--image",
            args.image,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    result["ai_model"] = manifest["model_id"]
    result["model_version"] = manifest["model_version"]
    result["model_git_commit"] = manifest["git_commit"]
    result["dataset_id"] = manifest["dataset_id"]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
