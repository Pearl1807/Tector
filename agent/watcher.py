"""Tector desktop watcher: runs in the background, checks what's on screen, and notifies the
user when the active window appears to be showing AI-generated or deepfaked media.

Usage:
    python watcher.py --space <username>/<space-name> [--interval 1] [--threshold 0.7]
"""
import argparse
import ctypes
import ctypes.wintypes
import os
import subprocess
import tempfile
import time
import winreg
from xml.sax.saxutils import escape

import cv2
import mss
import numpy as np
from gradio_client import Client, handle_file
from PIL import Image, ImageChops, ImageStat

from banner import CARD_TITLE, Notifier

APP_ID = "Tector"
LOG_PATH = os.path.join(tempfile.gettempdir(), "tector.log")
OWN_WINDOWS = {CARD_TITLE, "tk"}  # our alert card: never scan it
MAX_SIDE = 512  # crops are downscaled before upload; the model only looks at 224px, and big uploads lag (4-11s vs 3.5s)
CHANGE_THRESHOLD = 4.0  # mean pixel difference (0-255) that counts as "screen changed"
SOURCE_QUIET = 30  # an AI video still playing in the same spot re-alerts quietly (no sound) for this long
IMAGE_MEMORY = 600  # seconds we remember an image we already alerted on, so scrolling back doesn't re-alert
MAX_REGIONS = 6  # media areas found per screen
MAX_GRID_CHECK = 4  # thumbnails checked per screen when there is no main picture (each adds time)
SURE_THRESHOLD = 0.85  # "Very likely" at or above this, "Possibly" below
GRID_THRESHOLD = 0.9  # alert bar for thumbnails among several pictures (1.4% false alarms per picture vs 5% at 0.7)
MAIN_MEDIA_FRACTION = 0.12  # a picture covering this much of the window is what the user is looking at
MAIN_MEDIA_DOMINANCE = 2.5  # ...or one this many times bigger than any other picture on screen
MIN_MEDIA_SIDE = 160  # px; smaller pictures (icons, avatars) are ignored
MIN_MEDIA_FRACTION = 0.03  # of the window area
MAX_FLAT_FRACTION = 0.35  # regions flatter than this are UI/text, not media

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()  # so window coordinates match real screen pixels


def register_app_id():
    """Windows silently drops toasts from unregistered app IDs, so register ours (per-user, no admin)."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{APP_ID}") as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_ID)
        winreg.SetValueEx(key, "ShowInSettings", 0, winreg.REG_DWORD, 1)


def active_window():
    """Returns (title, (left, top, right, bottom)) of the foreground window, or (title, None)."""
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    rect = ctypes.wintypes.RECT()
    if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return buf.value, None
    box = (rect.left, rect.top, rect.right, rect.bottom)
    if box[2] - box[0] < 200 or box[3] - box[1] < 200:  # minimised or tiny window
        return buf.value, None
    return buf.value, box


def capture(sct):
    """Screenshot of the active window (falls back to the primary monitor)."""
    title, box = active_window()
    mon = sct.monitors[1]
    if box:
        region = {"left": box[0], "top": box[1], "width": box[2] - box[0], "height": box[3] - box[1]}
    else:
        region = mon
    shot = sct.grab(region)
    return title or "Screen", Image.frombytes("RGB", shot.size, shot.rgb)


def trim_flat_edges(std, box):
    """Shrinks a box while its outer rows/columns are mostly flat, e.g. a caption under a Pinterest pin."""
    x0, y0, x1, y1 = box
    flat = std <= 1
    while y1 - y0 > MIN_MEDIA_SIDE and flat[y1 - 1, x0:x1].mean() > 0.5:
        y1 -= 1
    while y1 - y0 > MIN_MEDIA_SIDE and flat[y0, x0:x1].mean() > 0.5:
        y0 += 1
    while x1 - x0 > MIN_MEDIA_SIDE and flat[y0:y1, x1 - 1].mean() > 0.5:
        x1 -= 1
    while x1 - x0 > MIN_MEDIA_SIDE and flat[y0:y1, x0].mean() > 0.5:
        x0 += 1
    return x0, y0, x1, y1


def media_regions(img):
    """Finds the picture/video areas in a screenshot, largest first.

    The detector was trained on clean single images; toolbars, text and other page content
    around a picture skew its score badly, so we only send the media itself.
    UI and text areas sit on flat backgrounds, photos and video frames have texture everywhere.
    """
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    mean = cv2.blur(gray, (5, 5))
    std = np.sqrt(np.maximum(cv2.blur(gray * gray, (5, 5)) - mean * mean, 0))
    busy = (std > 2).astype(np.uint8)
    busy = cv2.morphologyEx(busy, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    busy = cv2.morphologyEx(busy, cv2.MORPH_OPEN, np.ones((31, 31), np.uint8))  # drop thin text lines
    contours, _ = cv2.findContours(busy, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = MIN_MEDIA_FRACTION * img.width * img.height
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < MIN_MEDIA_SIDE or h < MIN_MEDIA_SIDE or w * h < min_area:
            continue
        flat = (std[y:y + h, x:x + w] <= 1).mean()  # text blocks are mostly flat background
        if flat < MAX_FLAT_FRACTION:
            box = trim_flat_edges(std, (x, y, x + w, y + h))
            if box[2] - box[0] >= MIN_MEDIA_SIDE and box[3] - box[1] >= MIN_MEDIA_SIDE:
                boxes.append(box)
    boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    return boxes[:MAX_REGIONS]


def check_regions(client, img, boxes, tmp_dir):
    """Sends all media areas to the Space in one request; returns [(AI probability, crop, box), ...]."""
    crops, paths = [], []
    for i, box in enumerate(boxes):
        crop = img.crop(box)
        crop.thumbnail((MAX_SIDE, MAX_SIDE))
        path = os.path.join(tmp_dir, f"tector_region_{i}.jpg")
        crop.save(path, quality=90)
        crops.append(crop)
        paths.append(handle_file(path))
    probs = client.predict(paths, api_name="/detect_batch")["probs"]
    return list(zip(probs, crops, boxes))


def box_area(box):
    return (box[2] - box[0]) * (box[3] - box[1])


def is_main_media(box, img, boxes):
    """The picture/video the user is actually looking at, as opposed to thumbnails in a grid or filmstrip:
    the only one, a big one, or one much bigger than everything else (e.g. Photos app with its filmstrip)."""
    if len(boxes) == 1 or box_area(box) >= MAIN_MEDIA_FRACTION * img.width * img.height:
        return True
    areas = sorted((box_area(b) for b in boxes), reverse=True)
    return box_area(box) == areas[0] and areas[0] >= MAIN_MEDIA_DOMINANCE * areas[1]


def say(msg):
    """Prints to the console and appends to %TEMP%\\tector.log, so a session can be reviewed afterwards."""
    print(msg, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def fingerprint(img):
    """Tiny perceptual hash: the same picture gives (nearly) the same bits even after scrolling/rescaling."""
    small = np.asarray(img.convert("L").resize((8, 8), Image.BILINEAR), dtype=np.float32)
    return small > small.mean()


def already_alerted(fp, alerted, now):
    return any(now - t < IMAGE_MEMORY and np.count_nonzero(fp != old) <= 6 for old, t in alerted)


def changed(prev, img):
    if prev is None:
        return True
    a = prev.convert("L").resize((64, 36))
    b = img.convert("L").resize((64, 36))
    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0] > CHANGE_THRESHOLD


def record_in_notification_center(title, message):
    """Adds a silent entry to the Windows notification centre (no pop-up) so alerts keep a history."""
    xml = (f'<toast><visual><binding template="ToastGeneric"><text>{escape(title)}</text>'
           f'<text>{escape(message)}</text></binding></visual><audio silent="true"/></toast>')
    script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml(@'
{xml}
'@)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$toast.SuppressPopup = $true
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{APP_ID}').Show($toast)
"""
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                     creationflags=subprocess.CREATE_NO_WINDOW)


def notify(notifier, title, prob, crop, key, sound):
    # Plain words instead of a percentage: the score isn't a calibrated probability, and "93%" suggests
    # more precision than the model has.
    sure = prob >= SURE_THRESHOLD
    headline = "Very likely AI-generated" if sure else "Possibly AI-generated"
    app = title if len(title) <= 40 else title[:39] + "…"
    message = f"Seen in \"{app}\". Think twice before trusting or sharing it."
    notifier.show("alert" if sure else "possible", headline, message, image=crop.copy(), key=key, sound=sound)
    record_in_notification_center(f"⚠️ {headline}", message)


def source_key(title, box):
    """Identifies where a detection came from: same app and same spot on screen = same video/picture slot."""
    return title, tuple(v // 50 for v in box)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--space", required=True, help="Hugging Face Space id (user/name) or URL")
    parser.add_argument("--interval", type=float, default=1, help="seconds to wait between screen checks")
    parser.add_argument("--threshold", type=float, default=0.7, help="alert when AI probability >= this")
    parser.add_argument("--once", action="store_true", help="check the screen once and exit")
    args = parser.parse_args()

    register_app_id()
    notifier = Notifier()
    say(f"Connecting to {args.space} ...")
    client = Client(args.space, verbose=False)
    say(f"Watching your screen (alert at {args.threshold:.0%}). Ctrl+C to stop.")
    notifier.show("info", "Watching your screen", "You'll get an alert if AI-generated media shows up.")

    tmp_dir = tempfile.gettempdir()
    prev = None
    alerted = []  # (fingerprint, time) of pictures we already alerted on
    last_sound = {}  # source key -> time we last alerted with sound
    with mss.MSS() as sct:
        while True:
            try:
                title, img = capture(sct)
                if title not in OWN_WINDOWS and changed(prev, img):
                    prev = img
                    stamp, started = time.strftime("%H:%M:%S"), time.time()
                    boxes = media_regions(img)
                    main_boxes = [b for b in boxes if is_main_media(b, img, boxes)]
                    if boxes:
                        # Only the picture/video the user is looking at when there is one (fast), otherwise the
                        # biggest few thumbnails. Thumbnails each carry a small false-alarm chance, so they
                        # need a stricter bar.
                        to_check = main_boxes[:1] or boxes[:MAX_GRID_CHECK]
                        bar = args.threshold if main_boxes else max(args.threshold, GRID_THRESHOLD)
                        prob, crop, box = max(check_regions(client, img, to_check, tmp_dir), key=lambda r: r[0])
                        kind = "main picture" if main_boxes else f"best of {len(to_check)} thumbnails"
                        say(f"[{stamp}] {prob:.0%} AI ({kind}, {time.time() - started:.1f}s)  |  {title[:60]}")
                        if prob >= bar:
                            now, fp, key = time.time(), fingerprint(crop), source_key(title, box)
                            if already_alerted(fp, alerted, now):
                                say("           (already alerted for this picture)")
                            else:
                                alerted.append((fp, now))
                                # Same video/slot alerted recently -> update the card quietly; new source -> sound
                                sound = now - last_sound.get(key, 0) > SOURCE_QUIET
                                if sound:
                                    last_sound[key] = now
                                notify(notifier, title, prob, crop, key, sound)
                                say(f"           >>> alert shown{'' if sound else ' (quietly, same source)'}")
                    else:
                        say(f"[{stamp}] no pictures/video on screen  |  {title[:70]}")
            except KeyboardInterrupt:
                raise
            except Exception as e:  # keep running through network hiccups / Space restarts
                say(f"[{time.strftime('%H:%M:%S')}] check failed: {e}")
            if args.once:
                time.sleep(1)  # let the card appear before exiting
                break
            time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
