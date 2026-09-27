"""Tector's alert card: a branded, always-on-top pop-up in the bottom-right corner.

It shows over full-screen apps (where Windows hides its own notification banners), includes a
thumbnail of the flagged picture, and a confidence meter instead of a raw percentage.

Usage:
    python banner.py --kind alert|possible|info --title "<headline>" --message "<text>" [--image <path>]
"""
import argparse
import ctypes
import tkinter as tk
import winsound

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

SHOW_MS = 8000
W, H = 460, 148  # logical size; scaled for the screen's DPI
PAD, THUMB = 16, 116
SS = 2  # supersampling factor for smooth shapes

BG = (18, 19, 26)
BORDER = (44, 46, 58)
TEXT = (244, 245, 250)
SUBTEXT = (170, 175, 190)
MUTED = (60, 63, 78)
KINDS = {
    "alert": {"accent": (255, 77, 94), "level": 5, "label": "Confidence: very high"},
    "possible": {"accent": (255, 176, 32), "level": 3, "label": "Confidence: moderate"},
    "info": {"accent": (45, 212, 191), "level": 0, "label": ""},
}
FONTS = r"C:\Windows\Fonts"


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
    """Tector's mark: a magnifying glass with a spark, drawn at high resolution then downsampled."""
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


def render_card(kind, title, message, image_path, scale):
    """Draws the static card with Pillow (anti-aliased text and shapes)."""
    k = KINDS[kind]
    accent = k["accent"]
    px = lambda v: int(round(v * scale))  # noqa: E731
    w, h = px(W), px(H)

    card = Image.new("RGB", (w, h), BG)
    # soft accent glow behind the thumbnail
    glow = Image.new("RGB", (w, h), BG)
    ImageDraw.Draw(glow).ellipse([px(-60), px(-60), px(160), px(160)], fill=tuple(int(c * 0.3) for c in accent))
    card = Image.blend(card, glow.filter(ImageFilter.GaussianBlur(px(55))), 0.7)
    d = ImageDraw.Draw(card)

    # thumbnail of the flagged picture (or a logo tile for info cards)
    tx, ty, ts = px(PAD), px(PAD), px(THUMB)
    if image_path:
        thumb = Image.open(image_path).convert("RGB")
        side = min(thumb.size)
        thumb = thumb.crop(((thumb.width - side) // 2, (thumb.height - side) // 2,
                            (thumb.width + side) // 2, (thumb.height + side) // 2)).resize((ts, ts), Image.LANCZOS)
    else:
        thumb = Image.new("RGB", (ts, ts), (28, 30, 40))
        mark = logo_mark(px(56), accent + (255,))
        thumb.paste(mark, ((ts - mark.width) // 2, (ts - mark.height) // 2), mark)
    ring = Image.new("RGB", (ts + px(4), ts + px(4)), accent)
    card.paste(ring, (tx - px(2), ty - px(2)), rounded_mask(ring.size, px(14)))
    card.paste(thumb, (tx, ty), rounded_mask((ts, ts), px(12)))

    # brand row
    x0 = tx + ts + px(18)
    mark = logo_mark(px(16), accent + (255,))
    card.paste(mark, (x0, px(18)), mark)
    brand_font = font("seguisb.ttf", px(11))
    bx = x0 + px(22)
    for ch in "TECTOR":  # letter-spaced wordmark
        d.text((bx, px(18)), ch, font=brand_font, fill=accent)
        bx += d.textlength(ch, font=brand_font) + px(2.5)

    # headline and message
    d.text((x0, px(38)), title, font=font("segoeuib.ttf", px(18)), fill=TEXT)
    msg_font = font("segoeui.ttf", px(12.5))
    for i, line in enumerate(wrap(d, message, msg_font, w - x0 - px(PAD))[:2]):
        d.text((x0, px(66) + i * px(18)), line, font=msg_font, fill=SUBTEXT)

    # confidence meter
    if k["level"]:
        my = px(113)
        for i in range(5):
            sx = x0 + i * px(26)
            d.rounded_rectangle([sx, my, sx + px(22), my + px(6)], px(3), fill=accent if i < k["level"] else MUTED)
        d.text((x0 + px(138), my - px(5)), k["label"], font=font("segoeui.ttf", px(11)), fill=SUBTEXT)

    # close button
    cx, cy, cr = w - px(22), px(22), px(5)
    d.line([cx - cr, cy - cr, cx + cr, cy + cr], fill=SUBTEXT, width=max(1, px(1.6)))
    d.line([cx - cr, cy + cr, cx + cr, cy - cr], fill=SUBTEXT, width=max(1, px(1.6)))

    d.rectangle([0, 0, w - 1, h - 1], outline=BORDER)
    return card


def round_window_corners(root):
    """Windows 11 rounded corners (ignored on Windows 10)."""
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except (AttributeError, OSError):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=KINDS, default="alert")
    parser.add_argument("--title", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--image")
    args = parser.parse_args()

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp rendering on high-DPI screens
    except (AttributeError, OSError):
        pass

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)
    scale = root.winfo_fpixels("1i") / 96
    px = lambda v: int(round(v * scale))  # noqa: E731
    w, h = px(W), px(H)

    photo = ImageTk.PhotoImage(render_card(args.kind, args.title, args.message, args.image, scale))
    canvas = tk.Canvas(root, width=w, height=h, highlightthickness=0, bd=0)
    canvas.pack()
    canvas.create_image(0, 0, image=photo, anchor="nw")
    accent = "#%02x%02x%02x" % KINDS[args.kind]["accent"]
    bar = canvas.create_rectangle(0, h - px(3), w, h, fill=accent, width=0)

    end_x = root.winfo_screenwidth() - w - px(24)
    y = root.winfo_screenheight() - h - px(72)  # above the taskbar
    start_x = end_x + px(60)
    root.geometry(f"{w}x{h}+{start_x}+{y}")
    root.update_idletasks()
    round_window_corners(root)

    state = {"left": SHOW_MS, "hover": False, "closing": False}

    def slide_in(step=0, steps=14):
        t = step / steps
        ease = 1 - (1 - t) ** 3
        root.geometry(f"+{int(start_x + (end_x - start_x) * ease)}+{y}")
        root.attributes("-alpha", 0.97 * ease)
        if step < steps:
            root.after(16, slide_in, step + 1)

    def close(step=0, steps=10):
        state["closing"] = True
        root.attributes("-alpha", 0.97 * (1 - step / steps))
        if step < steps:
            root.after(16, close, step + 1)
        else:
            root.destroy()

    def tick():
        if state["closing"]:
            return
        if not state["hover"]:
            state["left"] -= 50
        canvas.coords(bar, 0, h - px(3), w * max(0, state["left"]) / SHOW_MS, h)
        if state["left"] <= 0:
            close()
        else:
            root.after(50, tick)

    canvas.bind("<Enter>", lambda _e: state.update(hover=True))  # pause the countdown while hovered
    canvas.bind("<Leave>", lambda _e: state.update(hover=False))
    canvas.bind("<Button-1>", lambda _e: state["closing"] or close())

    if args.kind != "info":
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    slide_in()
    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
