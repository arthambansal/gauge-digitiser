"""
explain.py - a plain-language account of how THIS reading was obtained.

Built only from values the pipeline already returns (dial, pivot, line
candidates, needle angle, calibration), so it always matches what happened.
"""

import math

from gauge_app.readout import format_value


def explain_reading(result, value, unit, status, safe_low, safe_high, margin):
    """Return a list of HTML strings, one per step."""
    steps = []
    rim, dial, needle = result.get("rim"), result.get("dial"), result.get("needle")
    stage3 = next((k for k in result["stages"] if k.startswith("3.")), "")

    if rim is None:
        return ["<b>Finding the dial failed.</b> No circle of a plausible size was found, so nothing else could run. "
                "Try a photo where the gauge fills more of the frame."]
    cx, cy, r = rim
    method = "the Hough Circle Transform" if "hough" in stage3 else "the contour fallback (Hough found no circle)"
    steps.append(f"<b>Find the dial.</b> The photo was shrunk to 640 px wide, turned grey and lightly blurred. "
                 f"Then {method} found the dial face: centre <code>({cx:.0f}, {cy:.0f})</code>, radius <code>{r:.0f} px</code>.")

    px, py, _ = dial
    offset = math.hypot(px - cx, py - cy)
    if offset > 1:
        steps.append(f"<b>Find the pivot.</b> A second, small circle search found the needle's hub cap "
                     f"<code>{offset:.0f} px</code> from the circle's centre. Angles are measured from the hub, "
                     f"because that is what the needle actually turns about.")
    else:
        steps.append("<b>Find the pivot.</b> No hub cap was found on the needle's line, so the circle's centre is used.")

    if needle is None:
        steps.append("<b>Find the needle.</b> Canny edges and the Hough line search found no line that starts near the "
                     "pivot, reaches far out and runs along something solid. No reading is possible.")
        return steps
    steps.append(f"<b>Find the needle.</b> Canny edge detection, then a Hough line search, gave straight-line "
                 f"candidates. Lines were kept only if they point at the pivot, start near it and reach far out. "
                 f"That removes tick marks and printed numbers. The most solid, longest line won "
                 f"(confidence <code>{result['confidence'] * 100:.0f}%</code>).")

    angle = result["angle"]
    steps.append(f"<b>Measure the angle.</b> From the pivot to the needle tip: <code>{angle:.1f}°</code>, counted "
                 f"clockwise from straight down (6 o'clock = 0°, 9 o'clock = 90°, 12 o'clock = 180°).")

    cal = result.get("calibration")
    if cal is not None and value is not None:
        span = cal.values[-1] - cal.values[0]
        if cal.mode == "manual":
            sweep = cal.rel_angles[-1]
            rel = cal.relative_angle(angle)
            steps.append(f"<b>Convert to a number.</b> The scale runs from <code>{format_value(cal.values[0], span)}</code> at "
                         f"<code>{cal.start_angle:.1f}°</code> to <code>{format_value(cal.values[-1], span)}</code>, "
                         f"<code>{sweep:.1f}°</code> further round. The needle is <code>{rel:.1f}°</code> past the start, "
                         f"so the reading is {format_value(cal.values[0], span)} + {rel:.1f} / {sweep:.1f} × "
                         f"{format_value(span, span)} = <b>{format_value(value, span)} {unit}</b>.")
        else:
            labels = ", ".join(f"{v:g}" for v in cal.info.get("labels", []))
            kind = "evenly spaced, so a straight line was fitted" if cal.mode == "auto-linear" else \
                "unevenly spaced (a non-linear scale), so the reading is interpolated between neighbouring numbers"
            steps.append(f"<b>Convert to a number.</b> OCR read the printed numbers <code>{labels}</code> and their "
                         f"positions. They are {kind}. Result: <b>{format_value(value, span)} {unit}</b>.")

    if value is not None and status is not None:
        band = margin * (safe_high - safe_low)
        why = {"GREEN": f"inside the safe range and more than {band:.3g} {unit} from either limit",
               "AMBER": f"inside the safe range but within {band:.3g} {unit} of a limit",
               "RED": "outside the safe range"}[status]
        steps.append(f"<b>Check the limits.</b> Safe range {safe_low:.4g}–{safe_high:.4g} {unit}: the reading is {why}.")
    return steps
