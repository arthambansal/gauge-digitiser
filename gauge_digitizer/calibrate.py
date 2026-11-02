"""
calibrate.py - Stage 5: convert a needle ANGLE into a gauge VALUE.

A Calibration stores a list of (angle, value) reference points:
  * Manual mode   : two points from the user (e.g. min value at 45 deg, max at 315 deg).
  * Automatic mode: points found by OCR - each printed scale number and its angle.

Linear scale     -> straight-line fit through the points (value = a * angle + b).
Non-linear scale -> lookup table, with linear interpolation between neighbouring points.
"""

import functools
import math
import re
from dataclasses import dataclass, field

import cv2
import numpy as np

from gauge_digitizer.utils import angle_of_point


@dataclass
class Calibration:
    mode: str                 # "manual", "auto-linear" or "auto-table"
    start_angle: float        # angle of the first reference point (scale start)
    rel_angles: list          # reference angles measured clockwise FROM start_angle (0, ..., span)
    values: list              # gauge values at those angles
    slope: float = 0.0        # for linear modes: value units per degree
    intercept: float = 0.0
    info: dict = field(default_factory=dict)  # extra details to show the user
    wrap_at: float = None     # relative angle beyond which a needle counts as "below the start"

    def relative_angle(self, angle):
        """
        Angle measured clockwise from the scale start, handling wrap-around.
        A needle slightly ANTI-clockwise of the start (e.g. resting below zero) would
        give ~350 deg; we turn that into a small negative angle instead.
        The dead zone (between scale max and scale min) is split in half: the half
        after the max is "past max", the half before the min is "below min".
          * manual mode: the full sweep is known, so the dead zone is known.
          * auto mode with the expected range known: wrap_at was computed from where the
            scale min and max must lie (see auto_calibration).
          * otherwise: only the 30 deg just before the first label counts as "below min".
        """
        rel = (angle - self.start_angle) % 360.0
        if self.wrap_at is not None:
            wrap_at = self.wrap_at
        elif self.mode == "manual":
            span = self.rel_angles[-1]
            wrap_at = span + (360.0 - span) / 2
        else:
            wrap_at = 330.0
        if rel > wrap_at:
            rel -= 360.0
        return rel

    def value_to_rel_angle(self, value):
        """Inverse mapping: where (relative angle) a value sits, extending the end segments."""
        if self.mode != "auto-table":
            return (value - self.intercept) / self.slope
        a, v = self.rel_angles, self.values
        if value < v[0]:
            return a[0] + (value - v[0]) * (a[1] - a[0]) / (v[1] - v[0])
        if value > v[-1]:
            return a[-1] + (value - v[-1]) * (a[-1] - a[-2]) / (v[-1] - v[-2])
        return float(np.interp(value, v, a))

    def angle_to_value(self, angle):
        rel = self.relative_angle(angle)
        if self.mode == "auto-table":
            return self.table_lookup(rel)
        return self.slope * rel + self.intercept

    def table_lookup(self, rel):
        """
        Piecewise-linear lookup between neighbouring OCR'd reference points.
        Beyond the first/last point we EXTEND the end segment's slope instead of
        clipping. WHY: the needle often hides the last printed number; clipping would
        then freeze every high reading at the last number that OCR could read.
        """
        a, v = self.rel_angles, self.values
        if rel < a[0]:
            return v[0] + (rel - a[0]) * (v[1] - v[0]) / (a[1] - a[0])
        if rel > a[-1]:
            return v[-1] + (rel - a[-1]) * (v[-1] - v[-2]) / (a[-1] - a[-2])
        return float(np.interp(rel, a, v))


# ---------------------------------------------------------------- manual mode

def manual_calibration(angle1, value1, angle2, value2):
    """
    Two reference points, e.g. (45 deg, 0 psi) and (315 deg, 100 psi).
    The scale runs CLOCKWISE from point 1 to point 2 (true for almost all gauges).
    """
    span = (angle2 - angle1) % 360.0
    if span == 0:
        raise ValueError("The two reference angles must be different.")
    slope = (value2 - value1) / span
    return Calibration(mode="manual", start_angle=angle1 % 360.0, rel_angles=[0.0, span],
                       values=[value1, value2], slope=slope, intercept=value1)


def calibration_from_min_max(min_value, max_value, min_angle=45.0, sweep=270.0):
    """Common special case: min value at min_angle, max value 'sweep' degrees further clockwise."""
    return manual_calibration(min_angle, min_value, min_angle + sweep, max_value)


# ---------------------------------------------------------------- automatic (OCR) mode

def remove_large_components(binary, max_size):
    """
    Delete connected components whose bounding box is bigger than max_size pixels.
    WHY: on real gauges the tick marks are joined by a printed scale ARC, so ticks +
    arc form one huge ring-shaped component (the needle is another large one).
    If we dilated without removing them, every number touching that ring would
    merge into it and be lost. Single digits are always much smaller than this.
    """
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary)
    too_big = (np.maximum(stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT]) > max_size)
    too_big[0] = False  # label 0 is the background
    out = binary.copy()
    out[too_big[labels]] = 0
    return out


def find_text_blobs(gray, dial, inner_frac=0.3, outer_frac=0.88):
    """
    Find candidate number regions on the dial face using classical image processing:
      1. Adaptive threshold -> dark ink becomes white (works under uneven light,
         because each pixel is compared with its own neighbourhood mean).
      2. Keep only an annulus (ring) of the dial where numbers are printed;
         the hub/needle base (centre) and the bezel (outside) are removed.
         Then remove components too large to be a digit (scale arc, needle).
      3. Morphological DILATION joins the separate digits of one number ("1","0","0")
         into one blob.
      4. Connected components -> bounding boxes, filtered by size.
         Components touching the OUTER edge of the ring are rejected: those are tick
         marks, which continue past the ring, while printed numbers lie fully inside it.
    Returns a list of bounding boxes (x, y, w, h).
    """
    cx, cy, r = dial
    # Stretch the dial's brightness to the full 0-255 range so dark / low-contrast
    # images behave like normal ones for the threshold below.
    disc = np.zeros_like(gray)
    cv2.circle(disc, (int(cx), int(cy)), int(r), 255, -1)
    work = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX, mask=disc)
    # If the face is dark (light numbers), invert so that numbers are always dark-on-light
    face = float(np.median(work[disc > 0]))
    if face < 110:
        work = 255 - work

    block = int(0.15 * r) | 1  # adaptive threshold neighbourhood size (must be odd)
    binary = cv2.adaptiveThreshold(work, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, block, 15)

    ring = np.zeros_like(binary)
    cv2.circle(ring, (int(cx), int(cy)), int(outer_frac * r), 255, -1)
    cv2.circle(ring, (int(cx), int(cy)), int(inner_frac * r), 0, -1)
    binary = cv2.bitwise_and(binary, ring)
    binary = remove_large_components(binary, max_size=0.25 * r)

    k = max(3, int(0.035 * r))
    joined = cv2.dilate(binary, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k // 2 + 1)))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(joined)

    # Labels of components that reach the outer edge of the ring (= tick marks)
    edge_band = np.zeros_like(binary)
    cv2.circle(edge_band, (int(cx), int(cy)), int(outer_frac * r), 255, -1)
    cv2.circle(edge_band, (int(cx), int(cy)), int((outer_frac - 0.04) * r), 0, -1)
    touching_edge = set(np.unique(labels[(edge_band > 0) & (joined > 0)]).tolist())

    boxes = []
    for i in range(1, n):  # label 0 is the background
        if i in touching_edge:
            continue
        x, y, w, h, area = stats[i]
        # A printed number is small compared with the dial but not tiny
        if 0.04 * r <= h <= 0.22 * r and 0.03 * r <= w <= 0.4 * r and w < 4 * h:
            boxes.append((int(x), int(y), int(w), int(h)))
    return boxes, binary


@functools.lru_cache(maxsize=1)
def tesseract_available():
    """True if the Tesseract program can be run (it is a separate install from pytesseract)."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # pytesseract missing, or Tesseract not installed / not on PATH
        return False


def ocr_number(gray, box):
    """
    Read one number with Tesseract.
    The crop is enlarged (Tesseract works best with text ~30+ px tall),
    binarised with Otsu, and padded with a white border.
    --psm 7 = "treat the image as a single text line";
    the whitelist stops Tesseract from guessing letters.
    Returns (value, confidence) or None.
    """
    import pytesseract  # imported here so the rest of the project works without Tesseract

    x, y, w, h = box
    pad = 3
    crop = gray[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
    if crop.size == 0:
        return None
    scale = 60.0 / crop.shape[0]
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, crop = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if np.mean(crop) < 127:  # make sure the text is dark on a light background
        crop = 255 - crop
    crop = cv2.copyMakeBorder(crop, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)

    data = pytesseract.image_to_data(
        crop, config="--psm 7 -c tessedit_char_whitelist=0123456789.", output_type=pytesseract.Output.DICT)
    words = [(t, float(c)) for t, c in zip(data["text"], data["conf"]) if t.strip() and float(c) > 0]
    if not words:
        return None
    text = "".join(t for t, _ in words)
    if not re.fullmatch(r"\d+(\.\d+)?", text):
        return None
    conf = min(c for _, c in words)
    return float(text), conf


def longest_increasing(points):
    """
    Keep the longest run of points whose values strictly increase with angle.
    WHY: OCR sometimes misreads a number (e.g. '8' as '3') or reads a tick as '1'.
    On a real scale the values must increase as we go clockwise, so any point that
    breaks this order is probably a misread and is dropped.
    (Classic O(n^2) dynamic programming - fine for ~10 points.)
    """
    n = len(points)
    if n == 0:
        return []
    best_len = [1] * n
    prev = [-1] * n
    for i in range(n):
        for j in range(i):
            if points[j][1] < points[i][1] and best_len[j] + 1 > best_len[i]:
                best_len[i] = best_len[j] + 1
                prev[i] = j
    i = int(np.argmax(best_len))
    chain = []
    while i != -1:
        chain.append(points[i])
        i = prev[i]
    return chain[::-1]


def best_scale_order(points):
    """
    Find where the scale STARTS and which OCR points form the scale.

    We don't know in advance where the scale begins (usually bottom-left, but not
    always). So we try each OCR'd number as the start: measure every point's angle
    clockwise from it, and find the longest increasing chain. The correct start
    gives the longest chain, because going clockwise from the true start the values
    rise all the way round the scale.
    (We don't simply use "the biggest gap between labels = dead zone", because a
    label hidden by the needle can leave a gap bigger than the dead zone.)

    Returns (start_angle, chain) where chain is a list of (relative_angle, value).
    """
    best_start, best_chain = None, []
    for start_angle, _ in points:
        rel = sorted(((a - start_angle) % 360.0, v) for a, v in points)
        chain = longest_increasing(rel)
        if len(chain) > len(best_chain):
            best_start, best_chain = start_angle, chain
    return best_start, best_chain


def main_scale_ring(readings, ring_width=0.08):
    """
    Keep only the numbers printed on ONE ring - the main scale.
    WHY: many gauges have two scales (e.g. psi outside, bar inside). Each scale's
    numbers sit at the same distance from the centre, so we group the OCR'd numbers
    by radius and keep the group with the most numbers (ties: the taller text,
    because the main scale is printed larger). Mixing the two scales would give a
    calibration in the wrong units.
    """
    best, best_key = readings, None
    for ref in readings:
        group = [rd for rd in readings if abs(rd["radius"] - ref["radius"]) <= ring_width]
        key = (len(group), np.mean([rd["box"][3] for rd in group]))  # (count, mean text height)
        if best_key is None or key > best_key:
            best, best_key = group, key
    return best


def check_linearity(rel_angles, values, tolerance=0.15):
    """
    Decide if the scale is linear by checking how uniform the spacing is.
    For each pair of neighbouring labels we compute 'degrees per unit value'.
    On a linear scale this is the same everywhere, so its coefficient of
    variation (std / mean) is small. Returns (is_linear, cv).
    """
    deg_per_unit = np.diff(rel_angles) / np.diff(values)
    cv = float(np.std(deg_per_unit) / np.mean(deg_per_unit))
    return cv < tolerance, cv


def auto_calibration(gray, dial, min_points=3, min_conf=80, min_span_deg=90, max_spacing_cv=1.0,
                     expected_range=None):
    """
    Build a Calibration automatically from the printed numbers.
    min_conf: Tesseract confidence (0-100) below which a read is ignored. On our
    synthetic test set, correct reads scored ~96 (median) while most misreads
    (e.g. '75' read as '15') scored below 80.
    min_span_deg / max_spacing_cv: sanity checks on the final set of labels (see below).
    expected_range: (scale min, scale max) typed by the user, or None. Used as a UNITS
    check - on a dual-scale gauge (e.g. bar + kPa) OCR alone cannot tell which scale
    the user means - and to locate the dead zone (see the end of this function).
    Returns (calibration or None, debug dict). None means "fall back to manual".
    """
    cx, cy, r = dial
    boxes, binary = find_text_blobs(gray, dial)
    if not tesseract_available():
        return None, {"boxes": boxes, "binary": binary, "readings": [], "used": [],
                      "reason": "Tesseract OCR is not installed on this computer."}
    readings = []
    for box in boxes:
        result = ocr_number(gray, box)
        if result is None:
            continue
        value, conf = result
        if conf < min_conf:
            continue
        bx, by, bw, bh = box
        angle = angle_of_point(cx, cy, bx + bw / 2, by + bh / 2)
        radius = math.hypot(bx + bw / 2 - cx, by + bh / 2 - cy) / r
        readings.append({"box": box, "value": value, "conf": conf, "angle": angle, "radius": radius})

    debug = {"boxes": boxes, "binary": binary, "readings": readings, "used": []}
    if expected_range is not None:
        # Units check: drop numbers outside the user's scale range (+5%), e.g. "1600" kPa on a 0-160 bar gauge
        lo, hi = expected_range
        tol = 0.05 * (hi - lo)
        readings = [rd for rd in readings if lo - tol <= rd["value"] <= hi + tol]
    if len(readings) < min_points:
        debug["reason"] = f"OCR found only {len(readings)} numbers (need {min_points})."
        return None, debug

    ring = main_scale_ring(readings)
    start, chain = best_scale_order([(rd["angle"], rd["value"]) for rd in ring])
    debug["used"] = [((a + start) % 360.0, v) for a, v in chain]
    if len(chain) < min_points:
        debug["reason"] = f"Only {len(chain)} OCR numbers are in a consistent increasing order."
        return None, debug

    # Re-measure angles from the first USED point so the scale starts at 0 deg
    first = chain[0][0]
    rel_angles = [a - first for a, _ in chain]
    values = [v for _, v in chain]
    is_linear, cv = check_linearity(rel_angles, values)

    # Sanity checks - better to fall back to manual than to trust a bad calibration:
    if rel_angles[-1] < min_span_deg:
        # e.g. 3 neighbouring labels covering 50 deg: extrapolating to the rest of the dial is unreliable
        debug["reason"] = f"OCR labels cover only {rel_angles[-1]:.0f} deg of the dial (need {min_span_deg})."
        return None, debug
    if cv > max_spacing_cv:
        # spacing that varies this wildly is not a real scale - usually two scales (e.g. bar and psi) mixed up
        debug["reason"] = f"OCR labels are spaced inconsistently (CV {cv:.2f}); probably two scales mixed."
        return None, debug

    if is_linear:
        slope, intercept = np.polyfit(rel_angles, values, 1)  # least-squares straight line
        cal = Calibration("auto-linear", (start + first) % 360.0, rel_angles, values, float(slope), float(intercept))
    else:
        cal = Calibration("auto-table", (start + first) % 360.0, rel_angles, values)
    cal.info = {"spacing_cv": round(cv, 3), "num_points": len(chain), "labels": values}

    if expected_range is not None:
        # Where must the scale's min and max be? Extend the OCR mapping to them. The dead zone
        # lies between max and min (going clockwise); its midpoint is where "past max" ends and
        # "below min" begins - the same rule as manual mode. Without this, a needle just below a
        # missed "0" label would be read as far past the end of the scale.
        a_min = cal.value_to_rel_angle(expected_range[0])
        a_max = cal.value_to_rel_angle(expected_range[1])
        dead_zone = 360.0 - (a_max - a_min)
        if dead_zone <= 0:
            debug["reason"] = "The OCR scale does not fit the expected range in one turn of the dial."
            return None, debug
        cal.wrap_at = a_max + dead_zone / 2
    return cal, debug
