"""
needle.py - Stage 3: find the needle inside the dial.

Canny edges (masked to the dial) -> probabilistic Hough line segments ->
filter out segments that cannot be the needle -> score the rest -> pick the best.
"""

import math

import cv2
import numpy as np

from gauge_digitizer.utils import angle_of_point, angle_difference, circular_mean, distance_point_to_line, point_at_angle


def dial_mask(shape, dial, radius_frac=0.9):
    """
    White disc covering the inside of the dial, black elsewhere.
    WHY: anything outside the dial (bezel, background, other objects) can only
    produce false lines, so we ignore it completely.
    """
    cx, cy, r = dial
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.circle(mask, (int(cx), int(cy)), int(radius_frac * r), 255, -1)
    return mask


def detect_edges(blurred, dial, canny_low=50, canny_high=150):
    """
    Canny edge detector, restricted to the dial.
    canny_low / canny_high are the hysteresis thresholds: gradients above
    canny_high are definite edges; between the two they are kept only if they
    connect to a definite edge. This keeps long continuous edges (the needle's
    sides) and drops isolated noisy pixels.
    """
    edges = cv2.Canny(blurred, canny_low, canny_high)
    return cv2.bitwise_and(edges, edges, mask=dial_mask(blurred.shape, dial))


def segment_contrast(gray, line, face_level, offset=3):
    """
    How different (in brightness) the pixels next to a segment are from the dial face.

    A Hough segment from Canny lies ON the border of an object, so we sample two
    thin strips: one 'offset' pixels to the left of the segment and one to the right.
    For the needle, one strip lies on the solid needle body -> big difference from
    the face. For a false line through text or across plain face, both strips are
    mostly face -> small difference. We keep the side with the bigger difference.

    We use the 25th PERCENTILE of the differences, not the mean. WHY: it is only
    high if at least 75% of the strip differs from the face, i.e. the line runs
    along a SOLID body (a needle). A line that crosses a few dark letters or ticks
    has a high mean but a low 25th percentile. On a real tyre-gauge photo this
    stopped a line through printed text from beating the true (short) needle.
    """
    x1, y1, x2, y2 = line
    h, w = gray.shape[:2]
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return 0.0
    nx, ny = -(y2 - y1) / length, (x2 - x1) / length  # unit vector perpendicular to the segment
    best = 0.0
    for side in (+1, -1):
        samples = []
        for t in np.linspace(0.1, 0.9, 15):
            x = x1 + t * (x2 - x1) + side * offset * nx
            y = y1 + t * (y2 - y1) + side * offset * ny
            xi, yi = int(round(x)), int(round(y))
            if 0 <= xi < w and 0 <= yi < h:
                samples.append(abs(face_level - float(gray[yi, xi])))
        if samples:
            best = max(best, float(np.percentile(samples, 25)))
    return best


def find_line_candidates(edges, dial, hough_threshold=30, min_length_frac=0.3, max_gap=10):
    """
    Probabilistic Hough Line Transform: returns line SEGMENTS (x1, y1, x2, y2).
    hough_threshold : minimum votes for a segment (higher = fewer, stronger lines).
    min_length_frac : shortest accepted segment, as a fraction of the dial radius.
    max_gap         : gaps up to this many pixels are bridged into one segment
                      (the needle's edge may be broken by the hub or glare).
    """
    r = dial[2]
    lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi / 180, threshold=hough_threshold,
                            minLineLength=int(min_length_frac * r), maxLineGap=max_gap)
    if lines is None:
        return []
    # reshape(-1, 4): OpenCV 4 returns shape (N, 1, 4), OpenCV 5 returns (N, 4)
    return [tuple(map(float, l)) for l in lines.reshape(-1, 4)]


def filter_and_score(lines, gray, dial, max_centre_dist_frac=0.12,
                     max_near_end_frac=0.4, min_far_end_frac=0.45):
    """
    Keep only segments that look like a needle, and give each a score.

    A needle segment must:
      1. point at the centre  -> the infinite line passes within
         max_centre_dist_frac * r of the centre (the needle pivots there).
      2. start near the centre -> its nearer end is within max_near_end_frac * r.
         Tick marks also point at the centre but start out near the rim, so this rejects them.
      3. reach far out         -> its farther end is beyond min_far_end_frac * r.
         Numerals, short text strokes and the needle's tail are rejected here.
    Score = segment length * segment contrast (long + strongly different from the face = needle).
    """
    cx, cy, r = dial
    # Typical face brightness: median of a ring between needle hub and ticks
    ring = cv2.bitwise_xor(dial_mask(gray.shape, dial, 0.7), dial_mask(gray.shape, dial, 0.3))
    face_level = float(np.median(gray[ring > 0]))

    accepted, rejected = [], []
    for (x1, y1, x2, y2) in lines:
        d1 = math.hypot(x1 - cx, y1 - cy)
        d2 = math.hypot(x2 - cx, y2 - cy)
        near, far = min(d1, d2), max(d1, d2)
        centre_dist = distance_point_to_line(cx, cy, x1, y1, x2, y2)

        if centre_dist > max_centre_dist_frac * r or near > max_near_end_frac * r or far < min_far_end_frac * r:
            rejected.append((x1, y1, x2, y2))
            continue

        # The TIP is the end farther from the centre (the tail end is the near one)
        tip = (x1, y1) if d1 > d2 else (x2, y2)
        angle = angle_of_point(cx, cy, tip[0], tip[1])
        contrast = segment_contrast(gray, (x1, y1, x2, y2), face_level)
        length = math.hypot(x2 - x1, y2 - y1)
        accepted.append({"line": (x1, y1, x2, y2), "tip": tip, "angle": angle,
                         "length": length, "contrast": contrast, "score": length * contrast})
    return accepted, rejected


def pick_needle(candidates, dial, cluster_deg=6.0):
    """
    Choose the best candidate, then average it with candidates at almost the
    same angle. WHY: the needle has two long sides, so Canny + Hough usually give
    two (or more) parallel segments. Averaging them gives the needle's centre line
    instead of one of its edges.
    """
    if not candidates:
        return None
    best = max(candidates, key=lambda c: c["score"])
    if best["contrast"] < 15:  # nothing stands out from the face -> no real needle found
        return None
    group = [c for c in candidates if angle_difference(c["angle"], best["angle"]) <= cluster_deg]
    angle = circular_mean([c["angle"] for c in group], weights=[c["score"] for c in group])
    cx, cy, r = dial
    tip_dist = max(math.hypot(c["tip"][0] - cx, c["tip"][1] - cy) for c in group)

    # Confidence: how clearly the needle beats the strongest candidate pointing ELSEWHERE.
    # 1.0 = no competitor at all; near 0 = a different direction scored almost as well.
    others = [c["score"] for c in candidates if angle_difference(c["angle"], best["angle"]) > cluster_deg]
    confidence = 1.0 - (max(others) / best["score"] if others else 0.0)
    return {"angle": angle, "tip": point_at_angle(cx, cy, angle, tip_dist), "score": best["score"],
            "num_segments": len(group), "line": best["line"], "confidence": confidence}


def detect_needle(blurred, gray, dial, canny_low=50, canny_high=150, hough_threshold=30,
                  min_length_frac=0.3, max_gap=10):
    """
    Run the whole needle stage. Returns a dict with the needle (or None) and
    the intermediate results needed for the 'pipeline stages' display.
    """
    edges = detect_edges(blurred, dial, canny_low, canny_high)
    lines = find_line_candidates(edges, dial, hough_threshold, min_length_frac, max_gap)
    accepted, rejected = filter_and_score(lines, gray, dial)
    needle = pick_needle(accepted, dial)
    return {"needle": needle, "edges": edges, "accepted": accepted, "rejected": rejected}


def choose_pivot_and_needle(blurred, gray, rim, candidates, canny_low=50, canny_high=150,
                            hough_threshold=30, min_length_frac=0.3, max_gap=10):
    """
    Pick the needle pivot from several candidate centres (see dial.find_pivot_candidates).

    1. Detect the needle using each candidate as the centre; keep the most
       convincing needle (highest score).
    2. The needle is a straight bar that turns about its pivot, so its line must
       pass THROUGH the pivot: choose the candidate closest to that line.
    3. Measure the final needle angle from that pivot.

    Returns (needle detection dict, (px, py)).
    """
    r = rim[2]
    params = (canny_low, canny_high, hough_threshold, min_length_frac, max_gap)
    best, best_centre = None, None
    for (px, py) in candidates:
        nd = detect_needle(blurred, gray, (px, py, r), *params)
        if nd["needle"] is not None and (best is None or nd["needle"]["score"] > best["needle"]["score"]):
            best, best_centre = nd, (px, py)
    if best is None:  # no needle with any centre: report the result for the plain dial centre
        return detect_needle(blurred, gray, (candidates[0][0], candidates[0][1], r), *params), candidates[0]

    x1, y1, x2, y2 = best["needle"]["line"]
    pivot = candidates[0]  # fallback: the plain dial centre
    hubs = candidates[1:]
    if hubs:
        # A real hub cap is preferred over the plain circle centre (which may also happen to lie
        # on the needle's line, just further along it) - but only if the line really passes through it.
        nearest = min(hubs, key=lambda p: distance_point_to_line(p[0], p[1], x1, y1, x2, y2))
        if distance_point_to_line(nearest[0], nearest[1], x1, y1, x2, y2) < 0.05 * r:
            pivot = nearest
    final = detect_needle(blurred, gray, (pivot[0], pivot[1], r), *params)
    if final["needle"] is None:  # very rare: the needle fails the filters from this centre
        return best, best_centre
    return final, pivot
