"""
readout.py - the instrument readout shown next to the gauge.

A bottle-green "display window" with the reading in large mono digits, the
status lamp, and a horizontal scale bar that shows the alarm zones
(red / amber / green) with a pointer at the current value. The status colour
also runs down the left edge of the window, so status is part of the readout
rather than a separate coloured box.
"""

import html

from gauge_app.theme import STATUS_COLOURS, STATUS_WORDS


def format_value(value, span):
    """Sensible number of decimals for the gauge's range (0-4000 psi vs 0-3 bar)."""
    if value is None:
        return "– – –"
    decimals = 0 if span >= 500 else 1 if span >= 20 else 2
    return f"{value:,.{decimals}f}"


def scale_bar_svg(value, lo, hi, safe_low, safe_high, margin):
    """Alarm zones along the scale, with a pointer at the reading."""
    width, x0, x1 = 300, 4, 296
    span = (hi - lo) or 1.0

    def x(v):
        return x0 + (min(max(v, lo), hi) - lo) / span * (x1 - x0)

    band = margin * (safe_high - safe_low)
    zones = [(lo, safe_low, STATUS_COLOURS["RED"]), (safe_low, safe_low + band, STATUS_COLOURS["AMBER"]),
             (safe_low + band, safe_high - band, STATUS_COLOURS["GREEN"]),
             (safe_high - band, safe_high, STATUS_COLOURS["AMBER"]), (safe_high, hi, STATUS_COLOURS["RED"])]
    rects = "".join(
        f'<rect x="{x(a):.1f}" y="15" width="{max(x(b) - x(a), 0):.1f}" height="7" fill="{c}" opacity=".85"/>'
        for a, b, c in zones if b > a)
    ticks = "".join(f'<line x1="{x0 + f * (x1 - x0):.1f}" y1="24" x2="{x0 + f * (x1 - x0):.1f}" y2="{30 if f in (0, .5, 1) else 27}" '
                    f'stroke="#CDB98F" stroke-width="1"/>' for f in (0, .25, .5, .75, 1))
    pointer = ""
    if value is not None:
        px = x(value)
        pointer = (f'<polygon points="{px - 6:.1f},3 {px + 6:.1f},3 {px:.1f},13" fill="#F4EBD9"/>'
                   f'<line x1="{px:.1f}" y1="12" x2="{px:.1f}" y2="23" stroke="#F4EBD9" stroke-width="2"/>')
    return (f'<svg viewBox="0 0 {width} 32" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="scale with alarm zones">{rects}{ticks}{pointer}</svg>')


def readout_html(value, unit, status, lo, hi, safe_low, safe_high, margin):
    colour = STATUS_COLOURS[status]
    unit = html.escape(unit or "")
    return f"""
<div class="gd-readout" style="--status:{colour}">
  <div class="gd-k">Reading</div>
  <div class="gd-value">{format_value(value, hi - lo)}<span class="gd-unit">{unit}</span></div>
  <div class="gd-status"><span class="gd-lamp"></span>{STATUS_WORDS[status]}</div>
  <div class="gd-scale">{scale_bar_svg(value, lo, hi, safe_low, safe_high, margin)}
    <div class="gd-scale-ends"><span>{format_value(lo, hi - lo)}</span>
      <span>safe {format_value(safe_low, hi - lo)}–{format_value(safe_high, hi - lo)}</span>
      <span>{format_value(hi, hi - lo)}</span></div>
  </div>
</div>"""


def details_html(rows, note=None):
    """Label ....... value rows (dotted leaders), like an instrument data plate."""
    body = "".join(f'<div class="gd-row"><span class="k">{html.escape(k)}</span><span class="fill"></span>'
                   f'<span class="v">{v}</span></div>' for k, v in rows)
    note_html = f'<div class="gd-note">{note}</div>' if note else ""
    return f'<div class="gd-details">{body}</div>{note_html}'
