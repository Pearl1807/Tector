# Tector: 90-second demo video

About 210 spoken words, which fits 90 seconds at a calm pace. Detections take about 5 seconds, and the
narration is written to cover that wait.

## Set up (10 minutes before recording)

1. **Wake the Space.** Open https://huggingface.co/spaces/Miration/Tector, click the "AI face" example
   and wait for the red verdict. Leave this tab open.
2. **Clean the screen.** Close other windows and silence notifications from other apps. Do Not Disturb
   can stay off: Tector shows its own card either way.
3. **Start Tector once** (double-click `Start Tector.bat`), open `demo\video\1 AI boy.jpg`, and check
   that the red card appears. Then close the Photos app and the Tector window, so you can start fresh
   on camera.
4. Open File Explorer at `HACKATHON` (where `Start Tector.bat` is). Keep `demo\video` ready.
5. **Keep the mouse away from the bottom-right corner.** Hovering over the card pauses its countdown.
6. Turn the volume up, so the alert sound is recorded too.

## Record

1. Press **Win + Shift + R** (Snipping Tool) and select the **whole screen**.
2. Turn the **microphone on** in the Snipping Tool bar, if your version shows that option. Otherwise
   record silently and add your voice afterwards in Clipchamp (built into Windows 11).
3. Click **Start**, perform the script below, then click **Stop**. The video is saved under
   `Videos\Screen Recordings`.
4. Trim the start and end in Clipchamp or the Photos app if needed. Keep it at 90 seconds or less.

Don't use **Win + Alt + R** (Xbox Game Bar): it records a single window and misses the Tector card.

## Script

| Time | On screen | Say |
|---|---|---|
| 0:00-0:12 | Slide 2 of the deck full screen (the two faces) | "One of these two people doesn't exist. The woman on the left was made by AI. Most of us can't tell, and we scroll past pictures like this every day." |
| 0:12-0:22 | Double-click `Start Tector.bat`. The blue "Watching your screen" card appears. Minimise the black console window | "Tector warns you when a picture on your screen is likely AI-generated. Once it's running, it checks the window you're looking at every second, in whatever app you use." |
| 0:22-0:42 | Open `demo\video\1 AI boy.jpg`, full screen. Wait for the **red card** | "Here's a photo of a boy, opened in the Photos app. After a few seconds, Tector flags it: very likely AI-generated. The alert shows exactly which picture it means, and it never blocks anything. You decide what to do." |
| 0:42-0:55 | Press **→** to `2 AI dog.jpg`. The card updates to the dog | "Next picture: a dog made with Stable Diffusion. The same alert updates, instead of piling up new ones." |
| 0:55-1:05 | Press **→** to `3 real photo.jpg`. No alert | "And a real photo? Nothing. Tector stays quiet." |
| 1:05-1:22 | Switch to the browser tab with the web app. Click the **"AI butterfly (Midjourney)"** example, then **"Real photo: swans"** | "Anyone can try the same detector on our web app. When we tested popular detectors on Hugging Face, the best scored 56 percent. So we trained our own on top of CLIP: 91 percent on images it had never seen." |
| 1:22-1:30 | Back to slide 1 of the deck (title) | "It's not perfect: video is our next step. But Tector warns you at the moment it matters. Tector." |

## If something goes wrong while recording

- **The red card is slow** (more than 10 s): keep talking; the first check after start-up can be
  slower. If it doesn't come, stop and record again.
- **A grey "Not protected" card appears:** the Wi-Fi or the Space dropped. Refresh the web app tab until
  it works, then record again.
- **You stumble over a line:** keep going and trim afterwards, or record the voice separately in Clipchamp.

## Share it

Upload to **YouTube as Unlisted**, or to Google Drive with **Share → Anyone with the link → Viewer**,
and put the link in your submission.
