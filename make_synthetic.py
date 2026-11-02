"""
make_synthetic.py - draws artificial gauge images with a KNOWN needle value.

Because we choose the needle value ourselves, every image comes with exact
ground truth, which lets evaluate.py measure the pipeline's error.

Each gauge is drawn with OpenCV primitives (circles, lines, polygons, text)
and then optionally degraded with: Gaussian noise, blur, uneven lighting,
a glare spot, or a small perspective tilt (camera not facing the dial squarely).

Usage:
    python make_synthetic.py              # writes synthetic/*.png + synthetic/ground_truth.csv
    python make_synthetic.py --count 120
"""

import argparse
import csv
import math
import os

import cv2
import numpy as np

from gauge_digitizer.utils import point_at_angle

# The gauge styles we generate. "labels" are the printed numbers on the dial.
# scale_type "linear": angle is proportional to value.
# scale_type "sqrt":   angle is proportional to sqrt(value) -> labels are NOT evenly
#                      spaced (like square-root flow meters). Used to test non-linear OCR calibration.
GAUGE_STYLES = [
    {"name": "psi100", "min": 0, "max": 100, "labels": [0, 20, 40, 60, 80, 100], "scale_type": "linear"},
    {"name": "bar10", "min": 0, "max": 10, "labels": [0, 2, 4, 6, 8, 10], "scale_type": "linear"},
    {"name": "temp160", "min": 0, "max": 160, "labels": [0, 40, 80, 120, 160], "scale_type": "linear"},
    {"name": "flow100", "min": 0, "max": 100, "labels": [0, 10, 25, 50, 75, 100], "scale_type": "sqrt"},
]

MIN_ANGLE = 45.0   # angle of the scale minimum (see utils.py for the convention)
SWEEP = 270.0      # total angle from min to max

VARIANTS = ["clean", "noise", "blur", "dark", "gradient", "glare", "tilt"]


def value_to_angle(value, style, min_angle=None, sweep=None):
    """Where on the dial a value sits, according to the style's scale type.
    min_angle / sweep default to the style's own values, else 45 / 270."""
    min_angle = style.get("min_angle", MIN_ANGLE) if min_angle is None else min_angle
    sweep = style.get("sweep", SWEEP) if sweep is None else sweep
    t = (value - style["min"]) / (style["max"] - style["min"])  # 0..1
    if style["scale_type"] == "sqrt":
        t = math.sqrt(max(t, 0.0))
    return min_angle + t * sweep


FONT_FILES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",          # macOS
    "C:/Windows/Fonts/arialbd.ttf",                               # Windows
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",       # Linux
]


def draw_labels(img, style, cx, cy, r, ink, labels=None, radius=0.60, size=0.12, positions=None):
    """
    Print the scale numbers, upright, centred at `radius` * r.
    We use a real TrueType font through Pillow because OpenCV's built-in Hershey
    font draws a slashed zero, which looks nothing like the digits on real gauges
    (Tesseract reads it as '4'). Falls back to Hershey if no font file is found.
    labels / positions: the texts and the main-scale values where they sit
    (used for the second scale); by default the style's own labels.
    """
    from PIL import Image, ImageDraw, ImageFont

    labels = style["labels"] if labels is None else labels
    positions = labels if positions is None else positions
    font_path = next((p for p in FONT_FILES if os.path.exists(p)), None)
    if font_path is None:
        for lab, pos in zip(labels, positions):
            tx, ty = point_at_angle(cx, cy, value_to_angle(pos, style), radius * r)
            cv2.putText(img, str(lab), (int(tx - 0.08 * r), int(ty + 0.04 * r)),
                        cv2.FONT_HERSHEY_SIMPLEX, size * r / 43, ink, 2, cv2.LINE_AA)
        return img

    font = ImageFont.truetype(font_path, int(size * r))
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    for lab, pos in zip(labels, positions):
        tx, ty = point_at_angle(cx, cy, value_to_angle(pos, style), radius * r)
        draw.text((tx, ty), str(lab), font=font, fill=ink[::-1], anchor="mm")  # "mm" = centred
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def random_look(rng):
    """
    Random 'realistic' features seen on the real photos in samples/:
    a printed scale arc, a second scale in other units, a dark face with white
    print, and needles of different lengths.
    """
    return {"arc": rng.random() < 0.6, "second_scale": rng.random() < 0.35,
            "dark_face": rng.random() < 0.25, "needle_len": float(rng.uniform(0.55, 0.85))}


def draw_gauge(value, style, size=(640, 480), rng=None, look=None):
    """
    Draw one gauge. Returns (image, (cx, cy, r)).
    look=None draws the original simple style; a dict from random_look() adds realistic features.
    """
    rng = rng or np.random.default_rng()
    look = look or {"arc": False, "second_scale": False, "dark_face": False, "needle_len": 0.80}
    w, h = size

    # Random plain background colour (a wall / panel behind the gauge)
    bg = rng.integers(60, 200, size=3).tolist()
    img = np.full((h, w, 3), bg, dtype=np.uint8)

    r = int(rng.uniform(0.32, 0.44) * min(w, h))
    cx = int(w / 2 + rng.uniform(-0.08, 0.08) * w)
    cy = int(h / 2 + rng.uniform(-0.05, 0.05) * h)

    # Bezel (thick dark rim) and face: white with black print, or dark with white print
    cv2.circle(img, (cx, cy), r + int(0.08 * r), (40, 40, 40), -1, cv2.LINE_AA)
    face = int(rng.integers(30, 60)) if look["dark_face"] else int(rng.integers(225, 256))
    cv2.circle(img, (cx, cy), r, (face, face, face), -1, cv2.LINE_AA)

    ink = (235, 235, 235) if look["dark_face"] else (25, 25, 25)

    if look["arc"]:
        # Printed arc joining the inner ends of the ticks. OpenCV measures ellipse angles
        # from the +x axis (clockwise on screen), which is our angle + 90 deg.
        start = value_to_angle(style["min"], style) + 90
        end = value_to_angle(style["max"], style) + 90
        cv2.ellipse(img, (cx, cy), (int(0.82 * r), int(0.82 * r)), 0, start, end, ink, 2, cv2.LINE_AA)

    # Minor ticks between labels, major ticks at labels
    labels = style["labels"]
    minor_step = (labels[1] - labels[0]) / 5.0
    v = style["min"]
    while v <= style["max"] + 1e-9:
        a = value_to_angle(v, style)
        p1 = point_at_angle(cx, cy, a, 0.82 * r)
        p2 = point_at_angle(cx, cy, a, 0.92 * r)
        cv2.line(img, tuple(map(int, p1)), tuple(map(int, p2)), ink, 1, cv2.LINE_AA)
        v += minor_step
    for lab in labels:
        a = value_to_angle(lab, style)
        p1 = point_at_angle(cx, cy, a, 0.76 * r)
        p2 = point_at_angle(cx, cy, a, 0.92 * r)
        cv2.line(img, tuple(map(int, p1)), tuple(map(int, p2)), ink, 3, cv2.LINE_AA)
    img = draw_labels(img, style, cx, cy, r, ink)

    if look["second_scale"]:
        # A smaller red scale in other units (x10, like kPa next to bar) on an inner ring.
        # Its numbers sit at different angles from the main labels - the case that
        # confuses OCR on real dual-scale gauges.
        red = (40, 40, 210)
        k = 10
        second = [int(v) for v in np.linspace(style["min"] * k, style["max"] * k, 5)]  # round numbers, e.g. 0, 400 ... 1600
        for u in second:
            a = value_to_angle(u / k, style)
            p1 = point_at_angle(cx, cy, a, 0.48 * r)
            p2 = point_at_angle(cx, cy, a, 0.53 * r)
            cv2.line(img, tuple(map(int, p1)), tuple(map(int, p2)), red, 2, cv2.LINE_AA)
        img = draw_labels(img, style, cx, cy, r, red, labels=second, radius=0.40, size=0.07,
                          positions=[u / k for u in second])

    # Needle: a thin tapered polygon from a short tail through the centre to the tip
    if look["dark_face"]:
        needle_colour = [(235, 235, 235), (0, 140, 255)][int(rng.integers(0, 2))]  # white or orange
    else:
        needle_colour = [(20, 20, 20), (30, 30, 200)][int(rng.integers(0, 2))]  # black or red (BGR)
    a = value_to_angle(value, style)
    tip = point_at_angle(cx, cy, a, look["needle_len"] * r)
    tail = point_at_angle(cx, cy, a + 180, 0.18 * r)
    half_w = 0.025 * r
    left = point_at_angle(cx, cy, a + 90, half_w)
    right = point_at_angle(cx, cy, a - 90, half_w)
    poly = np.array([tip, left, tail, right], dtype=np.int32)
    cv2.fillPoly(img, [poly], needle_colour, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), int(0.06 * r), (50, 50, 50), -1, cv2.LINE_AA)  # hub

    return img, (cx, cy, r)


def apply_variant(img, variant, rng):
    """Degrade a clean image to imitate real-world capture problems."""
    out = img.astype(np.float32)
    h, w = img.shape[:2]

    if variant == "noise":
        out += rng.normal(0, rng.uniform(10, 20), out.shape)
    elif variant == "blur":
        k = int(rng.choice([5, 7, 9]))
        out = cv2.GaussianBlur(out, (k, k), 0)
    elif variant == "dark":
        out *= rng.uniform(0.35, 0.55)
    elif variant == "gradient":
        # Uneven lighting: brightness falls off from one side to the other
        ramp = np.linspace(rng.uniform(0.3, 0.5), 1.1, w, dtype=np.float32)
        if rng.random() < 0.5:
            ramp = ramp[::-1]
        out *= ramp[None, :, None]
    elif variant == "glare":
        # A bright soft ellipse, like a reflection on the gauge glass
        glare = np.zeros((h, w), np.float32)
        gx, gy = int(rng.uniform(0.3, 0.7) * w), int(rng.uniform(0.3, 0.7) * h)
        cv2.ellipse(glare, (gx, gy), (int(0.12 * w), int(0.06 * h)),
                    float(rng.uniform(0, 180)), 0, 360, 1.0, -1)
        glare = cv2.GaussianBlur(glare, (0, 0), 15)
        out += 200 * glare[:, :, None]
    elif variant == "tilt":
        # Perspective warp: squash one side as if the camera is off-axis (~10-20 deg)
        s = rng.uniform(0.06, 0.12) * w
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        if rng.random() < 0.5:
            dst = np.float32([[s, s * 0.5], [w, 0], [w, h], [s, h - s * 0.5]])
        else:
            dst = np.float32([[0, 0], [w - s, s * 0.5], [w - s, h - s * 0.5], [0, h]])
        M = cv2.getPerspectiveTransform(src, dst)
        out = cv2.warpPerspective(out, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    return np.clip(out, 0, 255).astype(np.uint8)


def make_sweep_video(path, seconds=12, fps=15, seed=7):
    """
    A video of one gauge whose needle sweeps 0 -> 100 -> 0 with camera noise.
    Used to test / demo live mode without a webcam (enter the file path as the
    camera source in the app). Watch the status go GREEN -> AMBER -> RED.
    """
    rng = np.random.default_rng(seed)
    style = GAUGE_STYLES[0]
    frames = seconds * fps
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 480))
    for i in range(frames):
        phase = i / (frames - 1)
        value = 100 * (1 - abs(2 * phase - 1))  # triangle wave 0 -> 100 -> 0
        img, _ = draw_gauge(value, style, rng=np.random.default_rng(seed))  # same gauge every frame
        img = apply_variant(img, "noise", rng)
        writer.write(img)
    writer.release()
    print(f"Wrote {path} ({frames} frames)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=140, help="number of images")
    parser.add_argument("--out", default="synthetic")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--video", action="store_true", help="also write synthetic/sweep.mp4 for live-mode demos")
    parser.add_argument("--realistic", action="store_true",
                        help="add scale arcs, second scales, dark faces, short needles and other scale "
                             "start angles (written to synthetic_realistic/ unless --out is given)")
    args = parser.parse_args()
    if args.realistic and args.out == "synthetic":
        args.out = "synthetic_realistic"

    rng = np.random.default_rng(args.seed)  # fixed seed -> same dataset every run
    os.makedirs(args.out, exist_ok=True)
    if args.video:
        make_sweep_video(os.path.join(args.out, "sweep.mp4"))

    rows = []
    for i in range(args.count):
        style = dict(GAUGE_STYLES[i % len(GAUGE_STYLES)])
        variant = VARIANTS[(i // len(GAUGE_STYLES)) % len(VARIANTS)]
        look = None
        if args.realistic:
            look = random_look(rng)
            # Most gauges start bottom-left, some start further round (like the WIKA 60 MPa photo)
            style["min_angle"] = float(rng.uniform(30, 60) if rng.random() < 0.7 else rng.uniform(80, 130))
            style["sweep"] = float(rng.uniform(240, 300))
        # Keep away from the exact ends so the needle is not hidden in the dead zone
        value = float(rng.uniform(style["min"] + 0.02 * (style["max"] - style["min"]),
                                  style["max"] - 0.02 * (style["max"] - style["min"])))
        img, _ = draw_gauge(value, style, rng=rng, look=look)
        img = apply_variant(img, variant, rng)

        name = f"syn_{i:03d}_{style['name']}_{variant}.png"
        cv2.imwrite(os.path.join(args.out, name), img)
        rows.append({
            "filename": name, "true_value": round(value, 3),
            "scale_min": style["min"], "scale_max": style["max"],
            "min_angle": round(style.get("min_angle", MIN_ANGLE), 2), "sweep": round(style.get("sweep", SWEEP), 2),
            "scale_type": style["scale_type"], "variant": variant,
            "labels": " ".join(str(x) for x in style["labels"]),
        })

    with open(os.path.join(args.out, "ground_truth.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} images + ground_truth.csv to {args.out}/")


if __name__ == "__main__":
    main()
