"""
card.py - a shareable PNG "result card": annotated gauge + reading, status, time.

Drawn with Pillow using the app's fonts (assets/fonts, SIL Open Font Licence), so
it looks like the app. Falls back to Pillow's default font if a file is missing.
"""

import io
import os
from datetime import datetime

import cv2
from PIL import Image, ImageDraw, ImageFont

from gauge_app.readout import format_value
from gauge_app.theme import STATUS_COLOURS, STATUS_WORDS

FONT_DIR = "assets/fonts"
W, H = 1200, 630  # the usual link-preview size, so the card looks right when shared in chats


def _font(name, size, weight=None):
    path = os.path.join(FONT_DIR, name)
    try:
        font = ImageFont.truetype(path, size)
        if weight is not None:  # variable fonts (DM Sans, Fraunces): choose the weight
            try:
                font.set_variation_by_axes(_axes(font, weight, size))
            except (OSError, ValueError):
                pass
        return font
    except OSError:
        return ImageFont.load_default(size)


def _axes(font, weight, size):
    """Values for a variable font's axes: optical size follows the text size, weight as asked."""
    values = []
    for axis in font.get_variation_axes():
        name = axis["name"] if isinstance(axis["name"], str) else axis["name"].decode()
        if name.lower().startswith("weight"):
            values.append(weight)
        elif name.lower().startswith("optical"):
            values.append(min(max(size, axis["minimum"]), axis["maximum"]))
        else:
            values.append(axis["default"])
    return values


def _hex(colour):
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def make_result_card(annotated_bgr, value, unit, status, confidence, angle, source, span):
    """Return PNG bytes."""
    card = Image.new("RGB", (W, H), _hex("#F4EBD9"))
    d = ImageDraw.Draw(card)
    brass, ink, muted, bottle = _hex("#B08D57"), _hex("#2B261F"), _hex("#6E6352"), _hex("#24392F")

    # Left: the annotated gauge in a brass frame
    img = Image.fromarray(cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB))
    img.thumbnail((620, 540))
    ix, iy = 48, (H - img.height) // 2
    d.rectangle([ix - 9, iy - 9, ix + img.width + 8, iy + img.height + 8], outline=brass, width=2)
    card.paste(img, (ix, iy))

    # Right: the readout window
    rx = ix + 620 + 50
    d.text((rx, 52), "GAUGE DIGITIZER", font=_font("DMMono-Regular.ttf", 18), fill=brass)
    d.line([(rx, 84), (W - 48, 84)], fill=brass, width=1)
    d.line([(rx, 89), (W - 48, 89)], fill=brass, width=1)

    d.rounded_rectangle([rx, 118, W - 48, 330], radius=6, fill=bottle)
    d.rectangle([rx, 118, rx + 8, 330], fill=_hex(STATUS_COLOURS[status]))
    d.text((rx + 32, 136), "READING", font=_font("DMMono-Regular.ttf", 17), fill=_hex("#CDB98F"))
    number = format_value(value, span)
    big = _font("DMMono-Medium.ttf", 96)
    d.text((rx + 30, 160), number, font=big, fill=_hex("#F4EBD9"))
    nx = rx + 30 + d.textlength(number, font=big) + 12
    d.text((nx, 222), unit or "", font=_font("DMMono-Regular.ttf", 28), fill=_hex("#CDB98F"))
    lamp = _hex(STATUS_COLOURS[status])
    d.ellipse([rx + 32, 289, rx + 50, 307], fill=lamp)
    d.text((rx + 62, 284), STATUS_WORDS[status], font=_font("DMSans.ttf", 24, weight=600), fill=_hex("#F4EBD9"))

    rows = [("Time", datetime.now().strftime("%d %b %Y, %H:%M")), ("Source", source[:30]),
            ("Needle angle", f"{angle:.1f}°"), ("Confidence", f"{confidence * 100:.0f}%")]
    y = 362
    label_font, value_font = _font("DMSans.ttf", 20, weight=400), _font("DMMono-Regular.ttf", 20)
    for k, v in rows:
        d.text((rx, y), k, font=label_font, fill=muted)
        d.text((W - 48 - d.textlength(v, font=value_font), y), v, font=value_font, fill=ink)
        for dx in range(int(rx), W - 48, 6):  # dotted rule
            d.point((dx, y + 34), fill=brass)
        y += 46

    d.text((rx, H - 60), "Read by classical computer vision", font=_font("DMSans.ttf", 15, weight=500), fill=muted)
    d.text((rx, H - 38), "Hough circles · Canny edges · Hough lines", font=_font("DMMono-Regular.ttf", 14), fill=brass)

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    return buf.getvalue()
