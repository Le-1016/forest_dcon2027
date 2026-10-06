import argparse
import json
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(
        description="Send FOREST Edge AI result to Observation API"
    )
    parser.add_argument("--api", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--mission-id")
    parser.add_argument("--area-id")
    parser.add_argument("--site-id")
    parser.add_argument("--drone-id")
    parser.add_argument("--parent-observation-id")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--altitude", type=float)
    parser.add_argument("--camera-angle", type=float)
    parser.add_argument("--image-path")
    args = parser.parse_args()

    with open(args.result, "r", encoding="utf-8-sig") as f:
        inference = json.load(f)

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
        "image_path": args.image_path,
        "class": inference["class"],
        "confidence": inference["confidence"],
        "ai_model": inference["ai_model"],
    }

    body = json.dumps(observation).encode("utf-8")

    request = urllib.request.Request(
        args.api,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Observation API returned HTTP {exc.code}: {error_body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not connect to Observation API: {exc.reason}"
        ) from exc

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()