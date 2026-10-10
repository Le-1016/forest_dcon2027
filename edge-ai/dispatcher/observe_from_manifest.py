import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INFER = ROOT / "edge-ai" / "dispatcher" / "infer_from_manifest.py"


def main():
    parser = argparse.ArgumentParser(
        description="Verified FOREST inference to Observation API"
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument(
        "--api",
        default="http://127.0.0.1:18080/observations",
    )
    parser.add_argument("--mission-id")
    parser.add_argument("--area-id")
    parser.add_argument("--site-id")
    parser.add_argument("--drone-id")
    parser.add_argument("--parent-observation-id")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--altitude", type=float)
    parser.add_argument("--camera-angle", type=float)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()

    completed = subprocess.run(
        [
            sys.executable,
            str(INFER),
            "--manifest",
            args.manifest,
            "--image",
            args.image,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    inference = json.loads(completed.stdout)

    observation = {
        "mission_id": args.mission_id,
        "area_id": args.area_id,
        "site_id": args.site_id,
        "drone_id": args.drone_id,
        "parent_observation_id": args.parent_observation_id,
        "lat": args.lat,
        "lon": args.lon,
        "altitude": args.altitude,
        "camera_angle": args.camera_angle,
        "image_path": args.image,
        "class": inference["class"],
        "confidence": inference["confidence"],
        "ai_model": inference["ai_model"],
    }

    provenance = {
        "ai_model": inference["ai_model"],
        "model_version": inference["model_version"],
        "model_git_commit": inference["model_git_commit"],
        "dataset_id": inference["dataset_id"],
    }

    print("MODEL_PROVENANCE")
    print(json.dumps(provenance, indent=2))

    print("OBSERVATION_PAYLOAD")
    print(json.dumps(observation, indent=2))

    if not args.send:
        print("DRY_RUN: no HTTP request sent; database unchanged")
        return

    body = json.dumps(observation).encode("utf-8")
    request = urllib.request.Request(
        args.api,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            print("OBSERVATION_RESULT")
            print(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Observation API returned HTTP {exc.code}: {error_body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not connect to Observation API: {exc.reason}"
        ) from exc


if __name__ == "__main__":
    main()