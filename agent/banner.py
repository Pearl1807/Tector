"""Tector's alert card: a branded, always-on-top pop-up in the bottom-right corner.

It shows over full-screen apps (where Windows hides its own notification banners), includes a
thumbnail of the flagged picture, and a confidence meter instead of a raw percentage.

Usage:
    python banner.py --kind alert|possible|info --title "<headline>" --message "<text>" [--image <path>]
"""
import argparse
import ctypes
import os
import queue
import tempfile
import threading
import time
import tkinter as tk
import traceback
import winsound

from PIL import Image, ImageDraw, ImageFont, ImageTk

SHOW_MS = 8000
MAX_HOVER_MS = 12000
W, H = 440, 132  # logical size; scaled for the screen's DPI
PAD, THUMB = 16, 100
PANEL = PAD * 2 + THUMB  # solid colour panel on the left that holds the thumbnail
SS = 2  # supersampling factor for smooth shapes

# Solid colours only (no gradients): a dark body, and one strong colour per alert level
BG = (28, 28, 31)
BORDER = (46, 46, 51)
TEXT = (246, 246, 247)
SUBTEXT = (165, 165, 172)
KINDS = {
    "alert": {"accent": (229, 72, 77), "on_accent": (255, 255, 255), "label": "High confidence"},
    "possible": {"accent": (247, 170, 40), "on_accent": (40, 24, 0), "label": "Medium confidence"},
    "info": {"accent": (79, 124, 255), "on_accent": (255, 255, 255), "label": ""},
    "offline": {"accent": (113, 113, 122), "on_accent": (255, 255, 255), "label": "Not protected"},
}
FONTS = r"C:\Windows\Fonts"
LOG_PATH = os.path.join(tempfile.gettempdir(), "tector_banner.log")
CARD_TITLE = "Tector alert"


def log(msg):
    """The card runs without a console, so problems are written here instead."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} [{os.getpid()}] {msg}\n")
    except OSError:
        pass


def font(name, size):
    try:
        return ImageFont.truetype(f"{FONTS}\\{name}", size)
    except OSError:
        return ImageFont.load_default(size)


def rounded_mask(size, radius):
    mask = Image.new("L", (size[0] * SS, size[1] * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *mask.size], radius * SS, fill=255)
    return mask.resize(size, Image.LANCZOS)


def logo_mark(size, accent):
    """Tector's mark: a magnifying glass, drawn at high resolution then downsampled."""
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(big * 0.34)
    cx = cy = int(big * 0.42)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent, width=int(big * 0.11))
    d.line([cx + r * 0.72, cy + r * 0.72, big * 0.93, big * 0.93], fill=accent, width=int(big * 0.14))
    s = int(big * 0.09)
    d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=accent)
    return img.resize((size, size), Image.LANCZOS)


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=fnt) <= width:
            line = test
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def render_card(kind, title, message, image, scale):
    """Draws the static card with Pillow (anti-aliased text and shapes)."""
    k = KINDS[kind]
    accent, on_accent = k["accent"], k["on_accent"]
    px = lambda v: int(round(v * scale))  # noqa: E731
    w, h = px(W), px(H)
    card = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(card)

    # solid colour panel with the flagged picture (or the Tector mark for info cards)
    d.rectangle([0, 0, px(PANEL), h], fill=accent)
    tx, ts = px(PAD), px(THUMB)
    ty = (h - ts) // 2
    if image is not None:
        thumb = (image if isinstance(image, Image.Image) else Image.open(image)).convert("RGB")
        side = min(thumb.size)
        thumb = thumb.crop(((thumb.width - side) // 2, (thumb.height - side) // 2,
                            (thumb.width + side) // 2, (thumb.height + side) // 2)).resize((ts, ts), Image.LANCZOS)
        card.paste(thumb, (tx, ty), rounded_mask((ts, ts), px(8)))
    else:
        mark = logo_mark(px(48), on_accent + (255,))
        card.paste(mark, (tx + (ts - mark.width) // 2, ty + (ts - mark.height) // 2), mark)

    # brand row: Tector mark in the accent colour + name
    x0 = px(PANEL + 16)
    mark = logo_mark(px(13), accent + (255,))
    card.paste(mark, (x0, px(16)), mark)
    d.text((x0 + px(18), px(13)), "Tector", font=font("seguisb.ttf", px(11.5)), fill=TEXT)

    d.text((x0, px(33)), title, font=font("seguisb.ttf", px(16)), fill=TEXT)
    msg_font = font("segoeui.ttf", px(12))
    for i, line in enumerate(wrap(d, message, msg_font, w - x0 - px(PAD))[:2]):
        d.text((x0, px(57) + i * px(17)), line, font=msg_font, fill=SUBTEXT)

    if k["label"]:  # confidence badge: solid pill in the alert colour
        chip_font = font("seguisb.ttf", px(10.5))
        cw = int(d.textlength(k["label"], font=chip_font)) + px(18)
        cy = px(100)
        d.rounded_rectangle([x0, cy, x0 + cw, cy + px(20)], px(10), fill=accent)
        d.text((x0 + px(9), cy + px(3)), k["label"], font=chip_font, fill=on_accent)

    # close button
    cx, cy, cr = w - px(20), px(20), px(4.5)
    d.line([cx - cr, cy - cr, cx + cr, cy + cr], fill=SUBTEXT, width=max(1, px(1.4)))
    d.line([cx - cr, cy + cr, cx + cr, cy - cr], fill=SUBTEXT, width=max(1, px(1.4)))

    d.rectangle([px(PANEL), 0, w - 1, h - 1], outline=BORDER)  # border around the dark body only
    return card


def style_window(win):
    """Windows 11 rounded corners, no taskbar button, and don't take focus when clicked."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(win.winfo_id())
        pref = ctypes.c_int(2)  # DWMWCP_ROUND (ignored on Windows 10)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x00000080
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    except (AttributeError, OSError):
        pass


def show_without_focus(win):
    """Shows the window on top without activating it (Tk's own deiconify would steal focus from a video)."""
    user32 = ctypes.windll.user32
    hwnd = user32.GetParent(win.winfo_id())
    SW_SHOWNOACTIVATE, HWND_TOPMOST = 4, -1
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)


class Card:
    """One on-screen card. A new alert while it is showing replaces its content instead of stacking."""

    def __init__(self, root, scale, on_closed):
        self.root, self.scale, self.on_closed = root, scale, on_closed
        px = self.px
        self.w, self.h = px(W), px(H)

        self.win = tk.Toplevel(root)
        self.win.withdraw()  # shown below without taking focus from the user's app
        self.win.title(CARD_TITLE)  # the watcher skips this window
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        self.canvas = tk.Canvas(self.win, width=self.w, height=self.h, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.image_item = self.canvas.create_image(0, 0, anchor="nw")
        self.bar = self.canvas.create_rectangle(0, self.h - px(3), self.w, self.h, width=0)

        self.end_x = root.winfo_screenwidth() - self.w - px(24)
        self.start_x = self.end_x + px(60)
        self.y = root.winfo_screenheight() - self.h - px(72)  # above the taskbar
        self.win.geometry(f"{self.w}x{self.h}+{self.start_x}+{self.y}")
        self.win.update_idletasks()
        style_window(self.win)
        show_without_focus(self.win)

        self.left, self.elapsed, self.hover, self.closing = SHOW_MS, 0, False, False
        self.canvas.bind("<Enter>", lambda _e: setattr(self, "hover", True))  # pause countdown on hover
        self.canvas.bind("<Leave>", lambda _e: setattr(self, "hover", False))
        self.canvas.bind("<Button-1>", lambda _e: self.close())
        self._slide_in()
        self._tick()

    def px(self, v):
        return int(round(v * self.scale))

    def set_content(self, kind, title, message, image):
        self.photo = ImageTk.PhotoImage(render_card(kind, title, message, image, self.scale))
        self.canvas.itemconfigure(self.image_item, image=self.photo)
        self.canvas.itemconfigure(self.bar, fill="#%02x%02x%02x" % KINDS[kind]["accent"])
        self.canvas.tag_raise(self.bar)
        self.left, self.elapsed = SHOW_MS, 0  # restart the countdown
        if self.closing:  # a new alert arrived while fading out: bring the card back
            self.closing = False
            self.win.attributes("-alpha", 0.97)
            self._tick()

    def _slide_in(self, step=0, steps=12):
        ease = 1 - (1 - step / steps) ** 3
        self.win.geometry(f"+{int(self.start_x + (self.end_x - self.start_x) * ease)}+{self.y}")
        self.win.attributes("-alpha", 0.97 * ease)
        if step < steps:
            self.win.after(15, self._slide_in, step + 1)

    def _tick(self):
        if self.closing:
            return
        self.elapsed += 50
        # Hovering pauses the countdown, but never for more than MAX_HOVER_MS (a mouse resting in the corner)
        if not self.hover or self.elapsed > SHOW_MS + MAX_HOVER_MS:
            self.left -= 50
        self.canvas.coords(self.bar, 0, self.h - self.px(3), self.w * max(0, self.left) / SHOW_MS, self.h)
        if self.left <= 0:
            self.close()
        else:
            self.win.after(50, self._tick)

    def close(self, step=0, steps=10):
        if step == 0 and self.closing:
            return
        self.closing = True
        if step < steps:
            self.win.attributes("-alpha", 0.97 * (1 - step / steps))
            self.win.after(16, self._continue_close, step + 1, steps)
        else:
            self.win.destroy()
            self.on_closed(self)

    def _continue_close(self, step, steps):
        if self.closing:  # cancelled if new content arrived meanwhile
            self.close(step, steps)


class Notifier:
    """Shows Tector's alert cards from a background Tk thread inside the watcher: no process start-up
    delay, and one card at a time that updates in place when something new is detected."""

    def __init__(self):
        self.requests = queue.Queue()
        self.card, self.card_key = None, None
        threading.Thread(target=self._run, daemon=True).start()

    def show(self, kind, title, message, image=None, key=None, sound=True):
        """Thread-safe. `key` identifies the source (e.g. app + screen position); while a card is up, an
        alert from the same source updates it silently, a different source updates it with a sound."""
        self.requests.put((kind, title, message, image, key, sound))

    def _run(self):
        user_app = ctypes.windll.user32.GetForegroundWindow()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.update()
        ctypes.windll.user32.SetForegroundWindow(user_app)  # creating Tk grabs focus; give it back
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.root.report_callback_exception = lambda *exc: log("error: " + "".join(traceback.format_exception(*exc)))
        self._poll()
        self.root.mainloop()

    def _poll(self):
        try:
            while True:
                self._present(*self.requests.get_nowait())
        except queue.Empty:
            pass
        self.root.after(30, self._poll)

    def _present(self, kind, title, message, image, key, sound):
        showing = self.card is not None and not self.card.closing
        if showing:
            sound = sound and key != self.card_key
        if self.card is None:
            self.card = Card(self.root, self.scale, self._closed)
        self.card.set_content(kind, title, message, image)
        self.card_key = key
        if sound and kind != "info":
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        log(f"{'updated' if showing else 'shown'} {kind}: {title}")

    def _closed(self, card):
        if self.card is card:
            self.card, self.card_key = None, None


def main():
    """Standalone demo: python banner.py --kind alert --title ... --message ... [--image path]"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=KINDS, default="alert")
    parser.add_argument("--title", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--image")
    args = parser.parse_args()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    notifier = Notifier()
    notifier.show(args.kind, args.title, args.message, args.image)
    time.sleep((SHOW_MS + MAX_HOVER_MS) / 1000 + 1)


if __name__ == "__main__":
    main()
