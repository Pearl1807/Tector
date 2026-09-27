"""Collects a balanced real/AI image set from Hugging Face datasets by reading parquet row groups
remotely (no full dataset download).

Sources:
  - TheKernel01/Tiny-GenImage: real photos + ADM, BigGAN, GLIDE, Midjourney, SD1.4/1.5, VQDM, Wukong
  - TheKernel01/140k-Real-and-Fake-Faces: real faces (FFHQ) + StyleGAN faces

Usage: python collect_data.py train|test <out_dir>
Files are saved as "real__<source>__<n>.jpg" / "ai__<source>__<n>.jpg" for extract_features.py.
"""
import collections
import io
import os
import random
import sys

import pyarrow.parquet as pq
from huggingface_hub import HfFileSystem
from PIL import Image

GEN = ["Real", "ADM", "BigGAN", "GLIDE", "Midjourney", "SD14", "SD15", "VQDM", "Wukong"]
REAL_MULTIPLIER = 4  # GenImage has 1 real class vs 8 generators; take 4x more real images to balance
fs = HfFileSystem()


def take(path, out_dir, prefix, per_class, gen_col=True, max_rgs=6):
    os.makedirs(out_dir, exist_ok=True)
    f = pq.ParquetFile(fs.open(path, block_size=8_000_000))
    cols = ["image", "label"] + (["generator"] if gen_col else [])
    classes = GEN if gen_col else ["Real", "StyleGAN"]

    def quota(key):
        return per_class * (REAL_MULTIPLIER if key == "Real" and gen_col else 1)

    counts = collections.Counter()
    for rg in range(min(max_rgs, f.num_row_groups)):
        rows = f.read_row_group(rg, columns=cols).to_pylist()
        random.shuffle(rows)
        for r in rows:
            key = GEN[r["generator"]] if gen_col else ("Real" if r["label"] == 0 else "StyleGAN")
            if counts[key] >= quota(key):
                continue
            im = Image.open(io.BytesIO(r["image"]["bytes"])).convert("RGB")
            if min(im.size) < 128:
                continue
            im.thumbnail((512, 512))
            kind = "real" if r["label"] == 0 else "ai"
            im.save(os.path.join(out_dir, f"{kind}__{prefix}-{key}__{counts[key]}.jpg"), quality=95)
            counts[key] += 1
        print(path.split("/")[-1], "row group", rg, dict(counts), flush=True)
        if all(counts[k] >= quota(k) for k in classes):
            break
    return counts


def main():
    split, out = sys.argv[1], sys.argv[2]
    random.seed(0)
    if split == "train":
        take("datasets/TheKernel01/Tiny-GenImage/data/train-00002-of-00014.parquet", out, "gi", 70)
        take("datasets/TheKernel01/140k-Real-and-Fake-Faces/data/train-00003-of-00006.parquet", out, "face", 300,
             gen_col=False, max_rgs=1)
    else:  # held-out test set comes from the datasets' validation splits
        take("datasets/TheKernel01/Tiny-GenImage/data/validation-00001-of-00004.parquet", out, "gi", 20)
        take("datasets/TheKernel01/140k-Real-and-Fake-Faces/data/validation-00000-of-00002.parquet", out, "face", 60,
             gen_col=False, max_rgs=1)
    print("total", len(os.listdir(out)))


if __name__ == "__main__":
    main()
