"""
utils.py - small shared helpers: the angle convention, geometry and drawing.

ANGLE CONVENTION (used everywhere in this project)
-------------------------------------------------
Angles are in DEGREES, measured CLOCKWISE (as you look at the image)
starting from the 6 o'clock direction (straight DOWN from the dial centre).

        180 (12 o'clock)
          |
   90 ----+---- 270
 (9 o'clock) (3 o'clock)
          |
          0 (6 o'clock)

Why this convention? Most gauges have their "dead zone" (the gap with no
scale) at the bottom. Measuring from straight down means a typical scale
(e.g. min at 45 deg, max at 315 deg) increases smoothly from min to max
without jumping across the 0/360 wrap-around in the middle of the scale.
"""

import math
from collections import deque

import cv2
import numpy as np


def angle_of_point(cx, cy, x, y):
    """Angle (deg, clockwise from straight down) of point (x, y) seen from centre (cx, cy)."""
    dx = x - cx
    dy = y - cy  # image y grows DOWNWARDS
    # atan2(-dx, dy): "down" (dx=0, dy>0) gives 0, "left" (dx<0) gives +90, etc.
    return math.degrees(math.atan2(-dx, dy)) % 360.0


def point_at_angle(cx, cy, angle_deg, distance):
    """Inverse of angle_of_point: the (x, y) point at a given angle and distance from centre."""
    a = math.radians(angle_deg)
    x = cx - distance * math.sin(a)
    y = cy + distance * math.cos(a)
    return x, y


def circular_mean(angles_deg, weights=None):
    """
    Average of angles that respects wrap-around (e.g. mean of 359 and 1 is 0, not 180).
    We convert each angle to a unit vector, add the vectors, and take the angle of the sum.
    """
    angles = np.radians(np.asarray(angles_deg, dtype=float))
    if weights is None:
        weights = np.ones_like(angles)
    s = np.sum(weights * np.sin(angles))
    c = np.sum(weights * np.cos(angles))
    return math.degrees(math.atan2(s, c)) % 360.0


def angle_difference(a, b):
    """Smallest absolute difference between two angles in degrees (0..180)."""
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def distance_point_to_line(px, py, x1, y1, x2, y2):
    """Perpendicular distance from point P to the infinite line through (x1,y1)-(x2,y2)."""
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return math.hypot(px - x1, py - y1)
    # |cross product| / |line length| = height of the triangle = perpendicular distance
    return abs((x2 - x1) * (y1 - py) - (x1 - px) * (y2 - y1)) / length


# Colours in OpenCV's BGR order
GREEN = (0, 200, 0)
AMBER = (0, 170, 255)
RED = (0, 0, 255)
BLUE = (255, 120, 0)
GREY = (160, 160, 160)


def draw_overlay(image_bgr, dial=None, needle=None, text=None, colour=GREEN, rim=None,
                 circle_colour=BLUE, needle_colour=RED):
    """
    Draw the final result on a copy of the image:
    dial circle, needle pivot, needle line, and the digital reading as text.
    `dial` is (pivot x, pivot y, radius); `rim` is the detected circle (drawn if given).
    """
    out = image_bgr.copy()
    if dial is not None:
        cx, cy, r = dial
        rx, ry, rr = rim if rim is not None else dial
        cv2.circle(out, (int(rx), int(ry)), int(rr), circle_colour, 2, cv2.LINE_AA)
        cv2.circle(out, (int(cx), int(cy)), 4, circle_colour, -1, cv2.LINE_AA)
        if needle is not None:
            tip = needle["tip"]
            cv2.line(out, (int(cx), int(cy)), (int(tip[0]), int(tip[1])), needle_colour, 3, cv2.LINE_AA)
    if text:
        # Dark box behind the text so it is readable on any background
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        cv2.rectangle(out, (8, 8), (20 + tw, 24 + th), (30, 30, 30), -1)
        cv2.putText(out, text, (14, 16 + th), cv2.FONT_HERSHEY_SIMPLEX, 0.9, colour, 2, cv2.LINE_AA)
    return out


def draw_angle_grid(image_bgr, dial):
    """
    Spokes every 10 deg from the needle pivot, labelled every 30 deg, in our angle
    convention. Used for manual calibration: read the angle of the scale's first and
    last tick off the image and type them into 'Min angle' and the sweep.
    """
    out = image_bgr.copy()
    cx, cy, r = dial
    for a in range(0, 360, 10):
        end = point_at_angle(cx, cy, a, 1.05 * r)
        colour = RED if a % 30 == 0 else (255, 0, 255)
        cv2.line(out, (int(cx), int(cy)), (int(end[0]), int(end[1])), colour, 1, cv2.LINE_AA)
        if a % 30 == 0:
            tx, ty = point_at_angle(cx, cy, a, 0.45 * r)
            cv2.putText(out, str(a), (int(tx) - 12, int(ty) + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, RED, 2, cv2.LINE_AA)
    return out


class ReadingSmoother:
    """
    Smooths live readings using the MEDIAN of the last N values.
    Median (not mean) is used because a single bad frame (needle missed,
    a tick mark picked instead) produces an outlier, and the median ignores
    outliers while a mean would be dragged towards them.
    """

    def __init__(self, window=7):
        self.values = deque(maxlen=window)

    def add(self, value):
        if value is not None:
            self.values.append(value)
        return self.current()

    def current(self):
        if not self.values:
            return None
        return float(np.median(self.values))

    def reset(self):
        self.values.clear()
