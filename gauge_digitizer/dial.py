"""
dial.py - Stage 2: find the circular dial face -> centre (cx, cy) and radius r.

Primary method : Hough Circle Transform.
Fallback       : largest roughly-circular contour + minimum enclosing circle.
"""

import math

import cv2
import numpy as np


def detect_dial_hough(blurred, param1=100, param2=40, min_radius_frac=0.25, max_radius_frac=0.5):
    """
    Hough Circle Transform (OpenCV's HOUGH_GRADIENT method).

    How it works: Canny edges are found first (param1 = upper Canny threshold).
    Each edge pixel then "votes" for possible circle centres along its gradient
    direction. Centres that collect at least param2 votes are accepted.

    param1          : Canny upper threshold used internally (higher = only strong edges).
    param2          : accumulator threshold (higher = fewer, more certain circles).
    min/max_radius_frac : allowed radius as a fraction of the smaller image side.
                      WHY: a gauge usually fills a good part of the frame, so this
                      rejects small circles like the needle hub or screws.

    Returns (cx, cy, r) or None.
    """
    h, w = blurred.shape[:2]
    side = min(h, w)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,               # accumulator resolution = image resolution / 1.2
        minDist=side / 4,     # circles closer than this are treated as duplicates
        param1=param1,
        param2=param2,
        minRadius=int(min_radius_frac * side),
        maxRadius=int(max_radius_frac * side),
    )
    if circles is None:
        return None

    circles = circles[0]  # shape (N, 3); OpenCV sorts by accumulator votes, strongest first
    cx, cy, r = circles[0]
    # A dial often produces two concentric circles (bezel outside, face inside).
    # Among circles sharing the best centre, we keep the SMALLER one = the face edge,
    # because the scale and needle live inside the face, not on the bezel.
    for (x, y, rad) in circles[1:]:
        if math.hypot(x - cx, y - cy) < 0.1 * r and rad < r:
            r = rad
    return float(cx), float(cy), float(r)


def detect_dial_contour(blurred, min_radius_frac=0.25):
    """
    Fallback when Hough finds nothing (e.g. strong glare breaks the rim edge).

    1. Otsu threshold splits the image into light / dark regions automatically.
    2. A morphological CLOSE fills small gaps (text, ticks) in the face region.
    3. For each external contour we compute circularity = 4*pi*area / perimeter^2
       (1.0 for a perfect circle) and keep the largest contour that is round enough.
    4. minEnclosingCircle gives its centre and radius.
    """
    h, w = blurred.shape[:2]
    side = min(h, w)
    best = None
    # Try both polarities: light face on dark background, and the opposite
    for flag in (cv2.THRESH_BINARY, cv2.THRESH_BINARY_INV):
        _, binary = cv2.threshold(blurred, 0, 255, flag + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            perimeter = cv2.arcLength(c, True)
            if perimeter == 0:
                continue
            circularity = 4 * math.pi * area / (perimeter ** 2)
            (x, y), rad = cv2.minEnclosingCircle(c)
            if circularity < 0.6 or rad < min_radius_frac * side or rad > 0.6 * side:
                continue
            if best is None or area > best[0]:
                best = (area, float(x), float(y), float(rad))
    if best is None:
        return None
    return best[1], best[2], best[3]


def find_pivot_candidates(blurred, dial, search_frac=0.4, max_hubs=8):
    """
    Find possible needle pivots (the small round hub cap) near the dial centre.

    WHY: the needle rotates about its pivot, not necessarily about the centre of
    the circle Hough found. With a tilted camera (the dial becomes an ellipse), a
    bezel cut off by the frame, or an old gauge, the two can be 20-50 px apart,
    which skews every angle. The hub cap is itself a small circle, so we run a
    second, small Hough Circle Transform in a window of +-0.4 r around the dial centre.

    Other small circles can also be found near the centre (a letter "o" in a logo,
    a screw), so we return SEVERAL candidates; needle.choose_pivot_and_needle()
    then keeps the one the needle's line actually passes through.

    Returns a list of (x, y) candidates: the dial centre first (fallback), then up
    to `max_hubs` small circles, strongest first.
    """
    cx, cy, r = dial
    candidates = [(cx, cy)]
    h, w = blurred.shape[:2]
    half = search_frac * r
    x0, y0 = int(max(cx - half, 0)), int(max(cy - half, 0))
    x1, y1 = int(min(cx + half, w)), int(min(cy + half, h))
    window = blurred[y0:y1, x0:x1]
    if window.size == 0:
        return candidates
    circles = cv2.HoughCircles(window, cv2.HOUGH_GRADIENT, dp=1, minDist=0.05 * r,
                               param1=100, param2=20,
                               minRadius=max(3, int(0.03 * r)), maxRadius=int(0.12 * r))
    if circles is not None:
        for x, y, _ in circles.reshape(-1, 3)[:max_hubs]:
            candidates.append((float(x + x0), float(y + y0)))
    return candidates


def detect_dial(blurred, param1=100, param2=40, min_radius_frac=0.25, max_radius_frac=0.5):
    """
    Try Hough first, then the contour fallback.
    Returns (dial, method) where dial is (cx, cy, r) or None, and method is a string for display.
    """
    dial = detect_dial_hough(blurred, param1, param2, min_radius_frac, max_radius_frac)
    if dial is not None:
        return dial, "hough"
    dial = detect_dial_contour(blurred, min_radius_frac)
    if dial is not None:
        return dial, "contour-fallback"
    return None, "not found"
