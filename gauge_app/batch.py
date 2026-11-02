"""
batch.py - read many gauge photos in one go and tabulate the results.

All photos use the calibration currently set in the sidebar (so they should be
photos of the same kind of gauge), or OCR per photo if Automatic is chosen.
"""

import base64

import cv2
import numpy as np
import pandas as pd

from gauge_digitizer.alerts import classify_reading
from gauge_digitizer.pipeline import read_gauge
from gauge_digitizer.utils import draw_overlay


def _thumb_data_uri(bgr, width=140):
    """Small JPEG as a data: URI, so the results table can show thumbnails."""
    h, w = bgr.shape[:2]
    small = cv2.resize(bgr, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def read_batch(files, settings, calibration, auto, safe_low, safe_high, margin, min_conf=0.0, progress=None):
    """files: Streamlit UploadedFile objects. Returns a DataFrame (one row per photo).
    Readings below min_conf get status LOW CONFIDENCE instead of an alarm status, as on the Read page."""
    rows = []
    for i, f in enumerate(files):
        image = cv2.imdecode(np.frombuffer(f.getvalue(), np.uint8), cv2.IMREAD_COLOR)
        row = {"photo": None, "file": f.name, "reading": None, "status": "NO READING",
               "confidence": None, "needle_angle": None, "calibration": "", "message": ""}
        if image is None:
            row["message"] = "Not an image the app can open"
        else:
            res = read_gauge(image, settings, calibration, auto)
            shown = res["overlay"] if res["needle"] is None else draw_overlay(
                res["colour"], res["dial"], res["needle"], rim=res["rim"])
            row["photo"] = _thumb_data_uri(shown)
            row["calibration"] = res["calibration"].mode if res["calibration"] is not None else ""
            row["message"] = " ".join(res["messages"])
            if res["value"] is not None:
                status = classify_reading(res["value"], safe_low, safe_high, margin)
                row.update(reading=round(res["value"], 3),
                           status=status if res["confidence"] >= min_conf else "LOW CONFIDENCE",
                           confidence=round(res["confidence"], 2), needle_angle=round(res["angle"], 1))
        rows.append(row)
        if progress is not None:
            progress(i + 1, len(files), f.name)
    return pd.DataFrame(rows)
