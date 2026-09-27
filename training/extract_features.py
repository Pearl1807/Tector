"""Turns a folder of images into CLIP ViT-L/14 features for training Tector's classifier.

Image files must be named "real__<source>__<n>.jpg" or "ai__<source>__<n>.jpg".
Usage: python extract_features.py <image_dir> <out.npz> [--augment]
"""
import argparse
import io
import os
import random
import time

import numpy as np
import torch
from PIL import Image
from transformers import CLIPImageProcessor, CLIPVisionModel

CLIP_MODEL = "openai/clip-vit-large-patch14"


def screen_like(img, rng):
    """Mimics what the desktop watcher sees: downscaled and re-compressed."""
    scale = rng.uniform(0.5, 1.0)
    img = img.resize((max(64, int(img.width * scale)), max(64, int(img.height * scale))), Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=rng.randint(60, 95))
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir")
    parser.add_argument("out")
    parser.add_argument("--augment", action="store_true", help="add one screen-like copy per image")
    args = parser.parse_args()

    torch.set_num_threads(os.cpu_count())
    processor = CLIPImageProcessor.from_pretrained(CLIP_MODEL)
    model = CLIPVisionModel.from_pretrained(CLIP_MODEL).eval()
    rng = random.Random(0)

    names = sorted(os.listdir(args.image_dir))
    samples = []
    for name in names:
        img = Image.open(os.path.join(args.image_dir, name)).convert("RGB")
        samples.append((name, img))
        if args.augment:
            samples.append((name + "#aug", screen_like(img, rng)))

    feats, t0 = [], time.time()
    for i in range(0, len(samples), 16):
        batch = [img for _, img in samples[i:i + 16]]
        with torch.no_grad():
            out = model(**processor(images=batch, return_tensors="pt"))
        feats.append(out.pooler_output.numpy())
        done = i + len(batch)
        print(f"{done}/{len(samples)}  ({done / (time.time() - t0):.1f} img/s)", flush=True)

    np.savez(
        args.out,
        X=np.concatenate(feats).astype(np.float32),
        y=np.array([n.startswith("ai__") for n, _ in samples], dtype=np.int64),
        names=np.array([n for n, _ in samples]),
    )
    print("saved", args.out)


if __name__ == "__main__":
    main()
