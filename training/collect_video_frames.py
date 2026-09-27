"""Collects video frames for training/testing Tector on AI video, reading archives remotely
(only the needed videos are downloaded).

  AI:   34data/gen-videos-veo3  (Google Veo 3)    -> train + test (different videos)
        34data/gen-videos-kling (Kling)            -> test only, a generator never seen in training
  Real: LanguageBind/Open-Sora-Plan-v1.1.0 mixkit stock footage (HD, cinematic, like AI video)

Usage: python collect_video_frames.py <out_dir>
Writes <out_dir>/train/*.jpg and <out_dir>/test/*.jpg named "<ai|real>__<source>__<video>_f<k>.jpg".
"""
import os
import random
import sys
import tarfile
import tempfile
import zipfile

import cv2
from huggingface_hub import HfFileSystem
from PIL import Image

MIXKIT = ["Airplane", "Baby", "Birds", "Cats", "Dogs", "Drive", "Family", "Fish", "House", "Monkey",
          "Motocycle", "Pets", "Reptiles", "Shark", "Taxi", "Trains", "Truck", "Wildlife"]
MAX_REAL_MB = 25
fs = HfFileSystem()


def save_frames(video_bytes, out_dir, prefix, n_frames):
    """Saves n evenly spaced frames, downscaled to 512px like the desktop watcher sends them."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
    cap = cv2.VideoCapture(tmp.name)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    saved = 0
    for k in range(n_frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (k + 0.5) / n_frames))
        ok, frame = cap.read()
        if not ok:
            continue
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img.thumbnail((512, 512))
        img.save(os.path.join(out_dir, f"{prefix}_f{k}.jpg"), quality=90)
        saved += 1
    cap.release()
    os.unlink(tmp.name)
    return saved


def from_zip(repo_file, picks, out_dir, source, n_frames):
    z = zipfile.ZipFile(fs.open(repo_file, block_size=1_000_000))
    videos = sorted((i for i in z.infolist() if i.filename.lower().endswith(".mp4")), key=lambda i: i.filename)
    if isinstance(picks, int):  # a number: that many random videos
        picks = random.sample(range(len(videos)), min(picks, len(videos)))
    for idx in picks:
        save_frames(z.read(videos[idx]), out_dir, f"ai__{source}__v{idx:03d}", n_frames)
    print(source, "videos:", len(picks), flush=True)


def real_videos(category, count):
    """First `count` small videos from a mixkit tar, reading only their headers and data."""
    tar = tarfile.open(fileobj=fs.open(f"datasets/LanguageBind/Open-Sora-Plan-v1.1.0/all_mixkit/{category}.tar",
                                       block_size=256_000), mode="r:")
    found = []
    for member in tar:
        if member.isfile() and member.name.lower().endswith(".mp4") and member.size < MAX_REAL_MB * 1e6:
            found.append(tar.extractfile(member).read())
            if len(found) == count:
                break
    return found


def main():
    out = sys.argv[1]
    train_dir, test_dir = os.path.join(out, "train"), os.path.join(out, "test")
    os.makedirs(train_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)
    random.seed(0)

    veo = "datasets/34data/gen-videos-veo3/data_001.zip"
    order = random.sample(range(314), 85)
    from_zip(veo, order[:60], train_dir, "veo3", 4)
    from_zip(veo, order[60:], test_dir, "veo3", 5)
    from_zip("datasets/34data/gen-videos-kling/data_001.zip", 15, test_dir, "kling", 5)

    for category in MIXKIT:
        try:
            videos = real_videos(category, 6)
        except Exception as e:  # a few archives are empty or unreadable
            print(category, "skipped:", e)
            continue
        for i, data in enumerate(videos):
            split, n = (train_dir, 4) if i < 4 else (test_dir, 5)
            save_frames(data, split, f"real__mixkit-{category}__v{i}", n)
        print(category, "real videos:", len(videos), flush=True)
    print("train frames:", len(os.listdir(train_dir)), "| test frames:", len(os.listdir(test_dir)))


if __name__ == "__main__":
    main()
