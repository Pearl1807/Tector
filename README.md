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

## Who it's for

- **Everyday social media users** scroll past hundreds of pictures a day. Nobody uploads each one to a
  checking website, so Tector checks the screen for them, at the moment they see the picture.
- **People targeted by fake profiles and scams.** AI-generated faces look like ordinary profile photos,
  and they are Tector's strongest category (57 of 60 caught, 59 of 60 real faces passed).
- **Journalists, moderators and fact-checkers** who want a quick first signal before verifying properly.

The value: a warning at the moment of viewing, in whatever app you use, showing *which* picture was
flagged, without uploading anything by hand.

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

## Testing & reliability

**Model accuracy.** 340 held-out images from the datasets' validation splits, never seen in training:
91% overall, broken down per generator above. We benchmarked six popular Hugging Face detectors first;
the best reached 56% on the same test set. We also measured how the alert level trades off false
alarms against missed AI images, and chose the levels from that:

| Alert level | Real images wrongly flagged | AI images caught | Used for |
|---|---|---|---|
| 70% | 5.0% | 84% | the main picture on screen |
| 85% | 2.1% | 74% | "Very likely" instead of "Possibly" |
| 90% | 1.4% | 66% | thumbnails in grids |

**End to end.** Every demo and example picture was checked on the live Space, both as a file and as it
looks when shown full screen. The watcher was tested on photos opened in the Photos app, pictures in
Chrome, and page layouts built to mimic TikTok, Pinterest and the Photos app.

**Automated tests.** `python -m pytest tests` runs 10 tests of the watcher's screen logic: finding
pictures on a page, trimming captions, ignoring icons, telling the main picture from a filmstrip or
grid, recognising a picture already alerted on, and detecting screen changes.

**Speed.** A check takes 4-7 s (down from 17-23 s, by sending only the main picture, downscaled to
512 px). The alert card appears 0.07 s after a detection.

**Cost.** The Space runs on Hugging Face's free CPU Basic hardware (Gradio Spaces need a Hugging Face
PRO account, $9/month), so there is no cost per check. Upgrading to 8 CPUs ($0.03/hour) would roughly
halve the delay. Training ran on a laptop CPU, with no GPU.

**Failure modes and fallbacks.**

| What goes wrong | What Tector does |
|---|---|
| No internet, or the Space is asleep or restarting | After 2 failed checks, a grey "Not protected" card warns the user; Tector keeps retrying, reconnects, and says "Protection is back on" |
| No connection at start-up | Warns instead of crashing, retries every 10 s |
| Windows hides notifications in full-screen apps | Tector shows its own always-on-top card |
| The same picture or a playing video keeps triggering | Pictures are remembered by fingerprint; a playing video updates the card quietly |
| A wrong answer | Alerts say "Very likely" or "Possibly", never a percentage, and never block anything |
| Modern AI video | Not solved: 1 of 8 Veo 3 clips caught. Marked experimental; training data pipeline written |

## Responsible AI & data

**Privacy.** The watcher only runs after the user starts it, and says so with a "Watching your screen"
card; closing the window stops it. It sends only the cropped picture (at most 512 px), and only when the
screen changes, never the whole screen. The Space deletes uploaded images within about two minutes
(`delete_cache`), never stores them and never uses them for training. The local log records scores
only, not window titles. The crops do leave the device, which is why an on-device version is our next
step.

**Consent.** The web app's example real photos contain no identifiable people. The demo faces are
either generated (StyleGAN, so no real person) or from the FFHQ research dataset.

**Bias.** We measured accuracy per generator and report where Tector is weaker: Midjourney (12 of 20)
and ordinary real photos (71 of 80 passed, against 79 of 80 for the off-the-shelf model). We did not
audit face results across skin tone, age or gender, and don't claim fairness there.

**Human oversight and safety.** Tector warns and never blocks, deletes or reports anything. The user
decides. Results are probabilities, not proof: treating a false alarm as proof could wrongly discredit
a real photo, so the wording stays cautious.

**Data and licences.** Training and test data: Tiny-GenImage (CC BY-NC-SA 4.0) and 140k Real and Fake
Faces (Creative Commons, see the dataset card), both non-commercial. The trained classifier should be
retrained on commercially licensed data before any commercial use. The Veo 3 and Kling video sets state
no licence, so we used a few clips only for evaluation and don't redistribute them. CLIP is MIT-licensed;
our code is Apache 2.0. The example images in `examples/` come from these datasets.

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
| `training/collect_video_frames.py` | Collects AI and real video frames for the next training round |
| `tests/test_watcher.py` | Automated tests of the watcher's screen logic |
| `examples/` | One-click example images for the web app |

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

## Built with

Hugging Face (Spaces, Transformers, Datasets, Hub), OpenAI CLIP, scikit-learn, Gradio, OpenCV, mss, pytest.
