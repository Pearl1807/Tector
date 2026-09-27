"""Tests for the desktop watcher's screen logic. Run with: python -m pytest tests

Pages are drawn in code (a "photo" is random texture, UI and text sit on flat backgrounds),
so the tests need no network, no model and no dataset files.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
import watcher  # noqa: E402

rng = np.random.default_rng(0)


def photo(w, h):
    """Stands in for a photo or video frame: textured everywhere."""
    noise = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    return Image.fromarray(noise).filter(ImageFilter.GaussianBlur(1))


def page(size=(1600, 900), bg="white"):
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, size[0], 70], fill=(225, 225, 230))  # toolbar
    for y in range(120, size[1] - 40, 24):  # lines of text
        d.text((40, y), "Some article text that is not a picture " * 2, fill=(40, 40, 40))
    return img


def overlap(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix)


def test_text_only_page_has_no_media():
    assert watcher.media_regions(page()) == []


def test_finds_picture_on_a_web_page():
    img = page()
    img.paste(photo(500, 350), (900, 200))
    boxes = watcher.media_regions(img)
    assert len(boxes) == 1
    assert overlap(boxes[0], (900, 200, 1400, 550)) > 0.9


def test_caption_under_picture_is_trimmed():
    img = Image.new("RGB", (1600, 900), "white")
    img.paste(photo(300, 300), (400, 200))
    ImageDraw.Draw(img).text((404, 506), "Saved pin title", fill="black")
    box = watcher.media_regions(img)[0]
    assert box[3] <= 510  # the box stops at the picture, not the caption below it


def test_small_icons_are_ignored():
    img = page()
    for i in range(6):
        img.paste(photo(64, 64), (40 + i * 80, 820))
    assert watcher.media_regions(img) == []


def test_photos_app_main_picture_vs_filmstrip():
    img = Image.new("RGB", (1600, 900), (32, 32, 32))
    img.paste(photo(900, 560), (350, 60))
    for i in range(5):
        img.paste(photo(250, 175), (90 + i * 290, 700))
    boxes = watcher.media_regions(img)
    main = [b for b in boxes if watcher.is_main_media(b, img, boxes)]
    assert len(boxes) == 6 and len(main) == 1
    assert overlap(main[0], (350, 60, 1250, 620)) > 0.9


def test_grid_of_similar_pictures_has_no_main_picture():
    img = Image.new("RGB", (1600, 900), "white")
    for i in range(6):
        img.paste(photo(229, 300), (90 + i * 245, 120))
    boxes = watcher.media_regions(img)
    assert len(boxes) == 6
    assert not any(watcher.is_main_media(b, img, boxes) for b in boxes)


def test_fingerprint_recognises_same_picture_after_rescaling():
    pic = photo(400, 300).resize((80, 60)).resize((400, 300))  # smooth-ish, like a real photo
    alerted = [(watcher.fingerprint(pic), 0.0)]
    assert watcher.already_alerted(watcher.fingerprint(pic.resize((200, 150))), alerted, now=10.0)


def test_fingerprint_tells_different_pictures_apart():
    a = photo(400, 300).resize((80, 60)).resize((400, 300))
    b = photo(400, 300).resize((80, 60)).resize((400, 300))
    assert not watcher.already_alerted(watcher.fingerprint(b), [(watcher.fingerprint(a), 0.0)], now=10.0)


def test_alert_memory_expires():
    pic = photo(400, 300)
    alerted = [(watcher.fingerprint(pic), 0.0)]
    assert not watcher.already_alerted(watcher.fingerprint(pic), alerted, now=watcher.IMAGE_MEMORY + 1)


def test_screen_change_detection():
    a = page()
    assert not watcher.changed(a, a.copy())
    b = a.copy()
    b.paste(photo(800, 500), (400, 200))
    assert watcher.changed(a, b)
