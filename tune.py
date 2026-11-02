"""
tune.py - choose the pipeline parameters by grid search ("training" without deep learning).

There is no learning in the neural-network sense. Instead we try every combination
of a few candidate values for the main parameters, measure the needle-angle error
on a TRAINING set with known answers, and keep the best combination.

  training set   : synthetic_realistic/ (140 synthetic gauges, exact ground truth)
  validation set : samples/ (12 real photos) - never used to choose, only to check

Keeping the real photos out of the search is what makes their score an honest
estimate: if we tuned on them, we would just be fitting these 12 photos.

Objective: mean angle error with each error capped at 30 deg, and a missed needle
counted as 30 deg. The cap stops one wild failure from dominating the average.

Usage:  python tune.py            (about 5-10 minutes)
Output: results/tuning.csv - every combination with its train and validation scores
"""

import csv
import itertools
import os
import time

import cv2
import numpy as np
import pandas as pd

from gauge_digitizer.pipeline import Settings, read_gauge
from gauge_digitizer.utils import angle_difference
from make_synthetic import value_to_angle

CAP_DEG = 30.0

# Candidate values (the defaults in pipeline.Settings are among them)
GRID = {
    "blur_kernel": [3, 5, 7],
    "canny": [(30, 100), (50, 150), (80, 200)],
    "line_threshold": [20, 30, 45],
    "min_line_frac": [0.25, 0.3, 0.4],
}


def load_set(folder, labels_file):
    """Images with their true needle angle."""
    items = []
    with open(os.path.join(folder, labels_file), newline="") as f:
        for lab in csv.DictReader(f):
            style = {"min": float(lab["scale_min"]), "max": float(lab["scale_max"]),
                     "scale_type": lab.get("scale_type") or "linear"}
            true_angle = value_to_angle(float(lab["true_value"]), style,
                                        float(lab["min_angle"]), float(lab["sweep"]))
            items.append((cv2.imread(os.path.join(folder, lab["filename"])), true_angle))
    return items


def score(items, settings):
    """Capped mean angle error (deg) and the fraction of needles found."""
    errors, found = [], 0
    for image, true_angle in items:
        res = read_gauge(image, settings)
        if res["needle"] is None:
            errors.append(CAP_DEG)
        else:
            found += 1
            errors.append(min(angle_difference(res["angle"], true_angle), CAP_DEG))
    return float(np.mean(errors)), found / len(items)


def main():
    train = load_set("synthetic_realistic", "ground_truth.csv")
    val = load_set("samples", "labels.csv")
    rows = []
    combos = list(itertools.product(*GRID.values()))
    t0 = time.time()
    for i, (blur, (lo, hi), votes, min_len) in enumerate(combos, 1):
        s = Settings(blur_kernel=blur, canny_low=lo, canny_high=hi, line_threshold=votes, min_line_frac=min_len)
        train_err, train_found = score(train, s)
        val_err, val_found = score(val, s)
        rows.append({"blur_kernel": blur, "canny_low": lo, "canny_high": hi, "line_threshold": votes,
                     "min_line_frac": min_len, "train_err_deg": round(train_err, 3),
                     "train_found": round(train_found, 3), "val_err_deg": round(val_err, 3),
                     "val_found": round(val_found, 3)})
        print(f"[{i}/{len(combos)}] {rows[-1]}  ({time.time() - t0:.0f}s)", flush=True)

    df = pd.DataFrame(rows).sort_values("train_err_deg")
    os.makedirs("results", exist_ok=True)
    df.to_csv("results/tuning.csv", index=False)

    d = Settings()
    is_default = ((df.blur_kernel == d.blur_kernel) & (df.canny_low == d.canny_low) & (df.canny_high == d.canny_high)
                  & (df.line_threshold == d.line_threshold) & (df.min_line_frac == d.min_line_frac))
    print("\nBest 5 on the TRAINING set (synthetic_realistic):")
    print(df.head(5).to_string(index=False))
    print("\nCurrent defaults:")
    print(df[is_default].to_string(index=False))


if __name__ == "__main__":
    main()
