import argparse
import json
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

from model import build_model


def main():
    parser = argparse.ArgumentParser(
        description="Run FOREST Edge AI image inference"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for FOREST Edge AI inference")

    device = torch.device("cuda:0")

    checkpoint = torch.load(
        args.model,
        map_location=device,
        weights_only=True,
    )

    classes = checkpoint["classes"]
    image_size = checkpoint["image_size"]

    model = build_model(
        num_classes=len(classes),
        pretrained=False,
    ).to(device)

    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    image = Image.open(Path(args.image)).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(tensor)
        probabilities = torch.softmax(logits, dim=1)
        confidence, index = probabilities.max(dim=1)

    result = {
        "class": classes[index.item()],
        "confidence": confidence.item(),
        "ai_model": "forest-edge-mobilenet-v0.1",
        "device": str(device),
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()