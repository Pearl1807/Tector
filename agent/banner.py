"""Tector's own alert banner: an always-on-top pop-up in the bottom-right corner.

Windows hides notification banners while a full-screen app is open (TikTok, YouTube, photo viewers),
which is exactly when Tector needs to be seen, so the watcher shows this banner as well.
Usage: python banner.py "<headline>" "<message>"
"""
import ctypes
import sys
import tkinter as tk

SHOW_MS = 8000
WIDTH, HEIGHT, MARGIN = 420, 120, 24
BG, ACCENT, TEXT, SUBTEXT = "#1f1f23", "#ef4444", "#ffffff", "#c9c9d1"


def main():
    headline, message = sys.argv[1], sys.argv[2]
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp text on high-DPI screens
    except (AttributeError, OSError):
        pass

    root = tk.Tk()
    root.overrideredirect(True)  # no title bar
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.97)
    root.configure(bg=ACCENT)

    scale = root.winfo_fpixels("1i") / 96
    w, h, m = int(WIDTH * scale), int(HEIGHT * scale), int(MARGIN * scale)
    x = root.winfo_screenwidth() - w - m
    y = root.winfo_screenheight() - h - m - int(48 * scale)  # stay above the taskbar
    root.geometry(f"{w}x{h}+{x}+{y}")

    card = tk.Frame(root, bg=BG)
    card.place(x=int(6 * scale), y=0, relwidth=1, relheight=1)  # red strip on the left edge
    title_row = tk.Frame(card, bg=BG)
    title_row.pack(fill="x", padx=16, pady=(14, 2))
    tk.Label(title_row, text="⚠", bg=BG, fg=ACCENT, font=("Segoe UI Symbol", 16)).pack(side="left")
    tk.Label(title_row, text=headline, bg=BG, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(side="left", padx=(8, 0))
    tk.Label(card, text=message, bg=BG, fg=SUBTEXT, font=("Segoe UI", 10), anchor="w", justify="left",
             wraplength=w - int(40 * scale)).pack(fill="x", padx=16)
    tk.Label(card, text="Tector", bg=BG, fg=ACCENT, font=("Segoe UI Semibold", 9),
             anchor="e").pack(fill="x", padx=16, side="bottom", pady=(0, 8))

    for widget in (root, card, *card.winfo_children(), *title_row.winfo_children()):
        widget.bind("<Button-1>", lambda _e: root.destroy())
    root.after(SHOW_MS, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
