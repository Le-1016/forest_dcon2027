"""Run the exported baseline classifier on one image. Does not control devices."""
import argparse
import json

from .dataset import CLASSES
from .model import build_model


def main():
    import numpy as np
    import torch
    from PIL import Image, ImageOps
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",required=True)
    parser.add_argument("--image",required=True)
    args=parser.parse_args()
    checkpoint=torch.load(args.model,map_location="cpu",weights_only=True)
    if checkpoint.get("architecture")!="forest_cnn_v1" or checkpoint.get("classes")!=CLASSES:
        raise ValueError("Unsupported FOREST model")
    model=build_model()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    with Image.open(args.image) as image:
        image=ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"),(96,96))
        tensor=torch.from_numpy(np.array(image,dtype=np.float32)/255).permute(2,0,1).unsqueeze(0)
    with torch.inference_mode():
        probabilities=model(tensor).softmax(1)[0].tolist()
    result={"class":CLASSES[max(range(3),key=probabilities.__getitem__)],"probabilities":dict(zip(CLASSES,probabilities)),
            "synthetic_model":bool(checkpoint.get("synthetic")),"note":"画像分類の試作モデル。位置検出・警報・飛行指示は行いません。"}
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
