---
title: Tector
emoji: 🔍
colorFrom: indigo
colorTo: red
sdk: gradio
sdk_version: 6.28.0
app_file: app.py
pinned: false
license: apache-2.0
short_description: Detect AI-generated images on your screen
---

# 🔍 Tector

**Tector warns you when a picture on your screen is likely AI-generated.**

A small Windows program checks the window you're looking at. Because it reads the screen rather than
connecting to a particular website, it isn't tied to one platform: it works the same in a browser, the
Photos app or a desktop app. When a picture is likely AI-generated, an alert card appears.
A web app lets anyone upload an image to check it.

**What we've tested:** still images, with 91% accuracy on 340 held-out images (see below). We tested the
screen watcher on photos opened in the Photos app, pictures in Chrome, and page layouts we built to mimic
TikTok and Pinterest, but not systematically on the live platforms. **Video is experimental:** it's checked
frame by frame, and on modern AI video (Google Veo 3) it caught only 1 of 8 clips.

- **Live web app:** https://huggingface.co/spaces/Miration/Tector
- **Detector:** our own classifier, trained during the hackathon (91% accuracy on held-out images)

## How it works

```
 Your screen ──► Desktop watcher (agent/watcher.py)
                   1. screenshots the active window every few seconds
                   2. finds the picture/video areas (skips toolbars, text, icons)
                   3. sends only those crops ──────────────► Tector detector on Hugging Face (app.py)
                                                               CLIP ViT-L/14 features
                                                               + our trained classifier
                   4. Windows notification  ◄────────────── probability each crop is AI-generated
```

**Why crop to the media?** Sending the whole window confused the detector: a real photo inside a web page
scored 92% AI, and a small AI image scored only 30%. Cropping to just the picture fixed both.

**Fast, focused checks.** When there is a main picture or video on screen (a photo you opened, a playing
video), only that is checked, so an alert appears about 4-6 seconds after it shows up. Otherwise up to 4
thumbnails are checked, and each must reach 90% (instead of 70%) to keep false alarms low in grids.

**One card, always up to date.** The alert card appears instantly. If you move to another AI picture or
video while it is showing, the same card updates with the new picture instead of stacking a second one.
It never takes focus from the app you are using, and a video that keeps playing updates it quietly.

## Our detector

We first benchmarked the most popular AI-image detectors on Hugging Face. On a broad test set the best one
reached only **56%**. It recognised Stable Diffusion and Midjourney images but missed most other generators,
and a deepfake model flagged real faces as fake. So we trained our own, following the UnivFD approach
(*Ojha et al., "Towards Universal Fake Image Detectors", CVPR 2023*):

1. Extract image features with [CLIP ViT-L/14](https://huggingface.co/openai/clip-vit-large-patch14), kept frozen.
2. Train a logistic-regression classifier on those features.

**Training data:** 1,370 images. Real photos and faces, plus 8 generators (Midjourney, Stable Diffusion,
ADM, GLIDE, VQDM, Wukong, BigGAN, StyleGAN faces) from
[Tiny-GenImage](https://huggingface.co/datasets/TheKernel01/Tiny-GenImage) and
[140k Real and Fake Faces](https://huggingface.co/datasets/TheKernel01/140k-Real-and-Fake-Faces).

**Results on 340 held-out images** (from the datasets' validation splits, never seen in training):

| | Best off-the-shelf model | **Tector** |
|---|---|---|
| Overall accuracy | 56% | **91%** |
| Real faces correctly passed | 55/60 | **59/60** |
| AI faces (StyleGAN) caught | 4/60 | **57/60** |
| BigGAN / VQDM / GLIDE caught | 0/20, 0/20, 5/20 | **20/20, 19/20, 19/20** |
| Midjourney caught | 16/20 | 12/20 |

**Known limitations:** Video is checked frame by frame with the image model, and it has not been trained on AI video yet: on 8 Google Veo 3 clips it flagged only 1. `training/collect_video_frames.py` gathers Veo 3, Kling and real stock-footage frames for that next training round. Midjourney is the weakest image generator. About 5% of real photos score above the 70% alert
level. Results are probabilities, not proof.

## Project structure

| Path | What it is |
|---|---|
| `app.py` | Web app + API (Gradio), deployed on Hugging Face Spaces |
| `tector_head.npz` | Our trained classifier weights |
| `agent/watcher.py` | Windows desktop watcher with notifications |
| `agent/banner.py` | Tector's alert card: thumbnail of the flagged picture, confidence meter, shown even over full-screen apps |
| `Start Tector.bat` | Double-click launcher for the watcher |
| `training/collect_data.py` | Builds the training/test sets from Hugging Face datasets |
| `training/extract_features.py` | Computes CLIP ViT-L/14 features |
| `training/train_classifier.py` | Trains the classifier and reports held-out accuracy |

## Running it

**Desktop watcher (Windows, Python 3.10+):**
```
python -m venv .venv
.venv\Scripts\pip install -r agent\requirements.txt
.venv\Scripts\python agent\watcher.py --space Miration/Tector
```
Or double-click `Start Tector.bat` after the install. Options: `--interval 1` (seconds between checks),
`--threshold 0.8` (alert level).

**Web app locally:**
```
pip install -r requirements.txt gradio
python app.py
```

**Reproduce the training:**
```
pip install -r training/requirements.txt
python training/collect_data.py train data/train
python training/collect_data.py test data/test
python training/extract_features.py data/train train.npz
python training/extract_features.py data/test test.npz
python training/train_classifier.py train.npz test.npz tector_head.npz
```

## Privacy

The watcher sends only the cropped picture/video areas, and only when the screen changes, to the Tector
Space for analysis. Tector itself keeps no copies or logs of what it sees. A fully on-device version
(running the model locally) is the natural next step.

## Built with

Hugging Face (Spaces, Transformers, Datasets, Hub), OpenAI CLIP, scikit-learn, Gradio, OpenCV, mss, winotify.
