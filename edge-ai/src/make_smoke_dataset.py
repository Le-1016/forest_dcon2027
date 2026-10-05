from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent / "data"


def make_image(path: Path, kind: str, index: int):
    image = Image.new("RGB", (224, 224), (40, 120, 50))
    draw = ImageDraw.Draw(image)

    if kind == "NORMAL":
        draw.ellipse((50, 40, 174, 190), fill=(35, 150 + index % 40, 55))
    else:
        draw.ellipse((50, 40, 174, 190), fill=(170 + index % 40, 120, 35))
        draw.ellipse((90, 80, 135, 130), fill=(210, 175, 50))

    image.save(path)


def main():
    for split, count in [("train", 20), ("val", 8)]:
        for class_name in ["NORMAL", "DISCOLORATION"]:
            directory = ROOT / split / class_name
            directory.mkdir(parents=True, exist_ok=True)

            for index in range(count):
                make_image(
                    directory / f"{class_name.lower()}_{index:03d}.png",
                    class_name,
                    index,
                )

    print("SMOKE_DATASET_READY")
    print(ROOT)


if __name__ == "__main__":
    main()