"""
alerts.py - Stage 6: compare the reading with a safe range and log breaches.

GREEN : inside the safe range, away from the limits.
AMBER : inside the safe range but within `margin` (default 10%) of the range
        width from either limit -> "approaching the limit, keep an eye on it".
RED   : outside the safe range -> logged to a CSV file with a timestamp.
"""

import csv
import os
from datetime import datetime

GREEN, AMBER, RED = "GREEN", "AMBER", "RED"

LOG_COLUMNS = ["timestamp", "reading", "safe_low", "safe_high", "source"]


def classify_reading(value, safe_low, safe_high, margin=0.10):
    """Return GREEN / AMBER / RED for one reading."""
    if value is None:
        return None
    if value < safe_low or value > safe_high:
        return RED
    band = margin * (safe_high - safe_low)  # e.g. 10% of the safe range width
    if value < safe_low + band or value > safe_high - band:
        return AMBER
    return GREEN


class AlertLogger:
    """
    Writes RED events to a CSV file.

    We log an EVENT when the status CHANGES into RED, not every RED frame.
    WHY: in live mode we process ~10+ frames per second; logging every frame
    would write hundreds of identical rows for one breach. One row per breach
    (plus its timestamp) is what an operator actually wants to see.
    """

    def __init__(self, path="alerts_log.csv"):
        self.path = path
        self.last_status = None

    def update(self, value, status, safe_low, safe_high, source="image"):
        """Call once per reading. Returns True if a new RED event was logged."""
        logged = False
        if status == RED and self.last_status != RED:
            self._write_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                             round(value, 3), safe_low, safe_high, source])
            logged = True
        if status is not None:
            self.last_status = status
        return logged

    def _write_row(self, row):
        new_file = not os.path.exists(self.path)
        with open(self.path, "a", newline="") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(LOG_COLUMNS)
            writer.writerow(row)

    def read_log(self):
        """All logged events as a list of dicts (newest last)."""
        if not os.path.exists(self.path):
            return []
        with open(self.path, newline="") as f:
            return list(csv.DictReader(f))

    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        self.last_status = None
