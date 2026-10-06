import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run FOREST Edge AI inference and create an Observation"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--api", required=True)
    parser.add_argument("--mission-id")
    parser.add_argument("--area-id")
    parser.add_argument("--site-id")
    parser.add_argument("--drone-id")
    parser.add_argument("--parent-observation-id")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--altitude", type=float)
    parser.add_argument("--camera-angle", type=float)
    args = parser.parse_args()

    src_dir = Path(__file__).resolve().parent

    infer_command = [
        sys.executable,
        str(src_dir / "infer.py"),
        "--model",
        args.model,
        "--image",
        args.image,
    ]

    inference = subprocess.run(
        infer_command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    result = json.loads(inference.stdout)

    print("INFERENCE_RESULT")
    print(json.dumps(result, indent=2))

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        encoding="utf-8",
        delete=False,
    ) as temp:
        json.dump(result, temp)
        result_path = temp.name

    send_command = [
        sys.executable,
        str(src_dir / "send_observation.py"),
        "--api",
        args.api,
        "--result",
        result_path,
        "--image-path",
        args.image,
    ]

    optional_args = [
        ("--mission-id", args.mission_id),
        ("--area-id", args.area_id),
        ("--site-id", args.site_id),
        ("--drone-id", args.drone_id),
        ("--parent-observation-id", args.parent_observation_id),
        ("--lat", args.lat),
        ("--lon", args.lon),
        ("--altitude", args.altitude),
        ("--camera-angle", args.camera_angle),
    ]

    for name, value in optional_args:
        if value is not None:
            send_command.extend([name, str(value)])

    print("OBSERVATION_RESULT")

    try:
        subprocess.run(send_command, check=True)
    finally:
        Path(result_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()