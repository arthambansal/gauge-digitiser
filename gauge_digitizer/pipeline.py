"""
pipeline.py - runs all stages in order on one image.

    preprocess -> detect dial -> detect needle -> angle -> calibrate -> (alerts in app)

Used by both app.py (GUI) and evaluate.py (testing), so the two always run the
exact same code.
"""

from dataclasses import dataclass

import cv2

from gauge_digitizer.calibrate import auto_calibration
from gauge_digitizer.dial import detect_dial, find_pivot_candidates
from gauge_digitizer.needle import choose_pivot_and_needle
from gauge_digitizer.preprocess import preprocess
from gauge_digitizer.utils import BLUE, GREEN, GREY, RED, draw_overlay


@dataclass
class Settings:
    """All tunable parameters in one place (the GUI sidebar edits these)."""
    width: int = 640               # working image width (pixels)
    use_clahe: bool = False
    blur_kernel: int = 5
    circle_param1: int = 100       # Hough circle: Canny upper threshold
    circle_param2: int = 40        # Hough circle: accumulator threshold
    min_radius_frac: float = 0.25  # dial radius limits (fraction of smaller image side)
    max_radius_frac: float = 0.5
    use_pivot: bool = True         # measure angles from the detected hub cap instead of the circle centre
    canny_low: int = 50            # needle edges
    canny_high: int = 150
    line_threshold: int = 30       # Hough line: votes needed
    min_line_frac: float = 0.3     # Hough line: min length (fraction of radius)
    max_line_gap: int = 10         # Hough line: max gap bridged (pixels)


def read_gauge(image_bgr, settings=None, calibration=None, auto_calibrate=False):
    """
    Read one gauge image.

    calibration    : a Calibration object (manual or a previously computed automatic one).
    auto_calibrate : if True, run OCR calibration on this image first; if OCR fails
                     we fall back to `calibration` and report why.

    Returns a dict with: value, angle, dial, needle, calibration, messages, stages (images).
    """
    s = settings or Settings()
    result = {"value": None, "angle": None, "confidence": 0.0, "dial": None, "rim": None, "needle": None,
              "calibration": calibration, "messages": [], "stages": {}, "ocr_debug": None}

    # Stage 1: preprocess
    colour, gray, blurred = preprocess(image_bgr, s.width, s.use_clahe, s.blur_kernel)
    result["colour"] = colour  # resized colour frame, used for drawing overlays
    result["stages"]["1. Grayscale" + (" + CLAHE" if s.use_clahe else "")] = gray
    result["stages"]["2. Gaussian blur"] = blurred

    # Stage 2: dial
    dial, method = detect_dial(blurred, s.circle_param1, s.circle_param2, s.min_radius_frac, s.max_radius_frac)
    if dial is None:
        result["messages"].append("Dial not found. Try lowering 'Circle accumulator threshold' or adjusting radius limits.")
        result["overlay"] = draw_overlay(colour, text="NO DIAL", colour=RED)
        return result
    if method != "hough":
        result["messages"].append("Hough circle failed; dial found with the contour fallback.")

    # Stage 2b + 3: needle pivot and needle. Candidate pivots = dial centre + small hub circles;
    # the chosen pivot is the one the needle's line passes through (see choose_pivot_and_needle).
    # From here on, `dial` = (pivot x, pivot y, dial radius): all angles are measured from the
    # pivot. The original circle is kept as `rim` for drawing.
    rim = dial
    candidates = find_pivot_candidates(blurred, rim) if s.use_pivot else [(rim[0], rim[1])]
    nd, (px, py) = choose_pivot_and_needle(blurred, gray, rim, candidates, s.canny_low, s.canny_high,
                                           s.line_threshold, s.min_line_frac, s.max_line_gap)
    if nd["needle"] is None:
        # Second pass with relaxed thresholds (shorter lines, fewer votes) - only when the normal pass
        # found nothing, e.g. a short needle on a dial whose detected radius is the large outer bezel.
        # Not used by default because relaxed thresholds also let more false lines through.
        nd, (px, py) = choose_pivot_and_needle(blurred, gray, rim, candidates, s.canny_low, s.canny_high,
                                               int(s.line_threshold * 0.66), s.min_line_frac * 0.66, s.max_line_gap)
        if nd["needle"] is not None:
            nd["needle"]["confidence"] *= 0.5  # relaxed thresholds -> trust the result less
            result["messages"].append("Needle found only with relaxed line thresholds - check the overlay.")
    dial = (px, py, rim[2])
    result["dial"], result["rim"] = dial, rim
    pivot_found = (px, py) != (rim[0], rim[1])
    circle_img = colour.copy()
    cv2.circle(circle_img, (int(rim[0]), int(rim[1])), int(rim[2]), BLUE, 2)
    cv2.circle(circle_img, (int(rim[0]), int(rim[1])), 4, BLUE, -1)
    for (hx, hy) in candidates[1:]:
        cv2.circle(circle_img, (int(hx), int(hy)), 6, GREY, 1)  # all hub candidates
    if pivot_found:
        cv2.circle(circle_img, (int(px), int(py)), 6, RED, 2)    # the chosen pivot
    result["stages"][f"3. Dial ({method}) + pivot" if pivot_found else f"3. Dial ({method})"] = circle_img
    result["stages"]["4. Canny edges (inside dial)"] = nd["edges"]
    result["stages"]["5. Line candidates"] = draw_candidates(colour, nd)
    needle = nd["needle"]
    if needle is None:
        result["messages"].append("Needle not found. Try lowering 'Line votes' or the Canny thresholds.")
        result["overlay"] = draw_overlay(colour, dial=dial, text="NO NEEDLE", colour=RED, rim=rim)
        return result
    result["needle"] = needle
    result["angle"] = needle["angle"]  # Stage 4: angle (computed with atan2 inside needle.py)
    result["confidence"] = needle["confidence"]

    # Stage 5: calibration
    if auto_calibrate:
        # The fallback (manual) calibration gives the expected scale range, used as a units check
        expected = (min(calibration.values), max(calibration.values)) if calibration is not None else None
        cal, debug = auto_calibration(gray, dial, expected_range=expected)
        result["ocr_debug"] = debug
        result["stages"]["6. OCR labels"] = draw_ocr(colour, dial, debug)
        if cal is not None:
            result["calibration"] = cal
        else:
            result["messages"].append("Auto-calibration failed: " + debug.get("reason", "unknown")
                                      + " Using manual calibration instead.")
    if result["calibration"] is not None:
        result["value"] = result["calibration"].angle_to_value(needle["angle"])

    result["overlay"] = draw_overlay(colour, dial=dial, needle=needle, rim=rim)
    return result


def draw_candidates(colour, nd):
    """Rejected Hough segments in grey, accepted in green, chosen needle tip as a red dot."""
    img = colour.copy()
    for (x1, y1, x2, y2) in nd["rejected"]:
        cv2.line(img, (int(x1), int(y1)), (int(x2), int(y2)), GREY, 1)
    for c in nd["accepted"]:
        x1, y1, x2, y2 = c["line"]
        cv2.line(img, (int(x1), int(y1)), (int(x2), int(y2)), GREEN, 2)
    if nd["needle"] is not None:
        tip = nd["needle"]["tip"]
        cv2.circle(img, (int(tip[0]), int(tip[1])), 6, RED, -1)
    return img


def draw_ocr(colour, dial, debug):
    """Boxes around candidate text blobs and the OCR'd values that were used."""
    img = colour.copy()
    used = {round(v, 3) for _, v in debug["used"]}
    for (x, y, w, h) in debug["boxes"]:
        cv2.rectangle(img, (x, y), (x + w, y + h), GREY, 1)
    for rd in debug["readings"]:
        x, y, w, h = rd["box"]
        ok = round(rd["value"], 3) in used
        cv2.rectangle(img, (x, y), (x + w, y + h), GREEN if ok else RED, 2)
        cv2.putText(img, f"{rd['value']:g}", (x, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    GREEN if ok else RED, 1, cv2.LINE_AA)
    return img
