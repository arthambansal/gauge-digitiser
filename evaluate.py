"""
evaluate.py - measure the pipeline's accuracy against ground truth.

Synthetic set (synthetic/ground_truth.csv, made by make_synthetic.py):
  * angle error     : detected needle angle vs. true angle (pure CV accuracy, no calibration)
  * manual error    : reading with manual min/max calibration vs. true value
                      (linear gauges only - a 2-point linear calibration cannot describe
                       a non-linear scale, so it would be unfair to score it there)
  * auto (OCR) error: reading with automatic OCR calibration vs. true value (the manual min/max is
                      passed as the units check, as in the app); if OCR fails
                      the image is counted as an OCR failure (the app would fall back to manual)
  Errors are reported as a PERCENTAGE OF FULL SCALE: |reading - truth| / (max - min) * 100.

Real photos (samples/labels.csv, optional - see README for the format):
  same measurements, using the min/max/angles you enter for each photo.

Outputs:
  results/results_synthetic.csv, results/results_samples.csv  - one row per image
  results/summary.csv                                         - per-variant summary
"""

import csv
import os
import time

import cv2
import numpy as np
import pandas as pd

from gauge_digitizer.calibrate import calibration_from_min_max
from gauge_digitizer.pipeline import Settings, read_gauge
from gauge_digitizer.utils import angle_difference
from make_synthetic import value_to_angle

RESULTS_DIR = "results"


def pct_full_scale(reading, truth, scale_min, scale_max):
    if reading is None:
        return None
    return abs(reading - truth) / (scale_max - scale_min) * 100.0


def evaluate_image(path, truth, scale_min, scale_max, min_angle, sweep, scale_type="linear", settings=None):
    """Run manual + auto calibration on one image and return a result row."""
    image = cv2.imread(path)
    manual = calibration_from_min_max(scale_min, scale_max, min_angle, sweep)

    t0 = time.time()
    res = read_gauge(image, settings, manual, auto_calibrate=False)
    elapsed_ms = (time.time() - t0) * 1000

    row = {
        "filename": os.path.basename(path), "true_value": truth, "scale_type": scale_type,
        "dial_found": res["dial"] is not None, "needle_found": res["needle"] is not None,
        "detected_angle": None, "true_angle": None, "angle_err_deg": None,
        "manual_value": None, "manual_err_pct": None,
        "auto_ok": False, "auto_mode": None, "auto_value": None, "auto_err_pct": None,
        "time_ms_no_ocr": round(elapsed_ms, 1),
    }
    if res["needle"] is None:
        return row

    style = {"min": scale_min, "max": scale_max, "scale_type": scale_type}
    true_angle = value_to_angle(truth, style, min_angle, sweep)
    row["detected_angle"] = round(res["angle"], 2)
    row["true_angle"] = round(true_angle % 360, 2)
    row["angle_err_deg"] = round(angle_difference(res["angle"], true_angle), 2)

    if scale_type == "linear":
        row["manual_value"] = round(res["value"], 3)
        row["manual_err_pct"] = round(pct_full_scale(res["value"], truth, scale_min, scale_max), 3)

    # As in the app: the manual min/max is passed as the fallback and as the units check for OCR
    auto = read_gauge(image, settings, manual, auto_calibrate=True)
    if auto["calibration"].mode.startswith("auto") and auto["value"] is not None:
        row["auto_ok"] = True
        row["auto_mode"] = auto["calibration"].mode
        row["auto_value"] = round(auto["value"], 3)
        row["auto_err_pct"] = round(pct_full_scale(auto["value"], truth, scale_min, scale_max), 3)
    return row


def evaluate_folder(folder, labels_file, settings=None):
    path = os.path.join(folder, labels_file)
    if not os.path.exists(path):
        return None
    rows = []
    with open(path, newline="") as f:
        for lab in csv.DictReader(f):
            image_path = os.path.join(folder, lab["filename"])
            if not os.path.exists(image_path):
                print(f"  missing image: {image_path}")
                continue
            row = evaluate_image(image_path, float(lab["true_value"]), float(lab["scale_min"]),
                                 float(lab["scale_max"]), float(lab.get("min_angle") or 45),
                                 float(lab.get("sweep") or 270), lab.get("scale_type") or "linear", settings)
            row["variant"] = lab.get("variant", "real")
            rows.append(row)
    return pd.DataFrame(rows)


def summarise(df, group_col="variant"):
    """Per-group and overall statistics."""
    def stats(g):
        return pd.Series({
            "images": len(g),
            "needle_found_%": 100 * g["needle_found"].mean(),
            "angle_err_mean_deg": g["angle_err_deg"].mean(),
            "manual_err_mean_%FS": g["manual_err_pct"].mean(),
            "manual_err_median_%FS": g["manual_err_pct"].median(),
            "manual_err_max_%FS": g["manual_err_pct"].max(),
            "ocr_success_%": 100 * g["auto_ok"].mean(),
            "auto_err_mean_%FS": g["auto_err_pct"].mean(),
            "auto_err_median_%FS": g["auto_err_pct"].median(),
            "auto_err_max_%FS": g["auto_err_pct"].max(),
        })
    per_group = df.groupby(group_col).apply(stats, include_groups=False)
    per_group.loc["ALL"] = stats(df)
    return per_group.round(2)


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    settings = Settings()
    summaries = []

    for name, folder, labels in [("synthetic", "synthetic", "ground_truth.csv"),
                                 ("synthetic_realistic", "synthetic_realistic", "ground_truth.csv"),
                                 ("samples", "samples", "labels.csv")]:
        print(f"\n=== {name} ===")
        df = evaluate_folder(folder, labels, settings)
        if df is None or df.empty:
            print(f"  no {folder}/{labels} found - skipped")
            continue
        df = df.astype({"angle_err_deg": float, "manual_err_pct": float, "auto_err_pct": float})
        df.to_csv(os.path.join(RESULTS_DIR, f"results_{name}.csv"), index=False)
        summary = summarise(df)
        summary.insert(0, "dataset", name)
        summaries.append(summary)
        with pd.option_context("display.width", 200, "display.max_columns", 20):
            print(summary)
        print(f"  mean processing time per frame (no OCR): {df['time_ms_no_ocr'].mean():.1f} ms")

    if summaries:
        pd.concat(summaries).to_csv(os.path.join(RESULTS_DIR, "summary.csv"))
        print(f"\nSaved per-image results and summary.csv to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
