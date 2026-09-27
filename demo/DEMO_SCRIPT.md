# Tector demo script (about 3 minutes)

Every picture in this folder was checked on the live Tector Space, both as a file and as it looks
full screen. Use only these for the live demo.

| File | Tector says |
|---|---|
| `ai_face_woman.jpg`, `ai_face_boy.jpg` | Very likely AI (100%) |
| `ai_poodle_stable_diffusion.jpg` | Very likely AI (100%) |
| `ai_butterfly_midjourney.jpg` | Very likely AI (96%) |
| `real_face_woman.jpg`, `real_face_smiling.jpg`, `real_woman_hat.jpg` | Likely real (0%) |

## 10 minutes before

1. Open https://huggingface.co/spaces/Miration/Tector and analyse one picture, so the Space is awake.
2. Windows Settings → System → Notifications → Do not disturb: **off**.
3. Double-click `Start Tector.bat` and wait for the blue "Watching your screen" card.
4. Close other windows. Open this `demo` folder in File Explorer.
5. Do one full run-through of steps 2 and 3 below.
6. Record a screen video of a successful run as a backup in case the Wi-Fi fails. Use the Snipping Tool (Win + Shift + R), not Win + Alt + R: Game Bar records a single window and would miss the Tector card.

## 1. The problem (20 s)

"AI-generated faces and pictures now look completely real, and people share them without knowing."
Show `ai_face_woman.jpg` next to `real_face_woman.jpg`: "One of these people doesn't exist. Which one?"

## 2. The website (40 s)

Upload `real_face_woman.jpg` → green **Likely real**. Upload `ai_face_woman.jpg` → red **Likely AI-generated**.

## 3. The desktop app: the main feature (60 s)

"Nobody uploads every picture they see to a website, so Tector checks the screen for you. Because it reads the
screen, it works the same in a browser, the Photos app or any desktop app."

1. Open `ai_face_boy.jpg` in the Photos app, full screen. The Tector alert appears after about 5 seconds,
   with a thumbnail of the picture it flagged.
2. Press → to go to `ai_poodle_stable_diffusion.jpg` while the alert is still showing. The same alert
   updates to the new picture.
3. Go to `real_face_smiling.jpg`. No alert: real photos don't trigger it.

## 4. How we built it (40 s)

- "We tested the most popular AI detectors on Hugging Face. On a broad test set the best one scored 56%.
  It missed most generators and flagged real faces as fake."
- "So we trained our own: CLIP ViT-L/14 image features plus a classifier trained on real photos and
  8 AI generators. **91% on 340 images it had never seen**, and 59 out of 60 real faces correct."
- "The desktop app finds the picture or video on screen and crops it, so page layout doesn't confuse
  the model."

## 5. Be honest about the limits (20 s)

"It gives a probability, not proof. Midjourney is its weakest generator, and about 1 in 20 real
photos can score high. That's why the alert says 'Very likely' or 'Possibly' instead of a number."

## If a judge asks about video

"Tector checks video frame by frame, on the website and on screen. We tested it on videos from Google Veo 3, the newest
generator, and it caught only 1 of 8, because our model was trained on still images. Our next step is training on AI
video frames. We've already written the data pipeline for it." Don't demo video live.

## If a judge wants to try their own picture

Say yes, and set expectations first: "It's strongest on AI faces and Stable Diffusion, weaker on
Midjourney." A wrong answer after you've said that looks honest. A wrong answer after you've claimed
it always works looks bad.

## Next steps (if asked)

Run the model on the device (privacy, no internet needed), a phone version, and a browser extension.
