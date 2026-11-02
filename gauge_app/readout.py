"""
readout.py - the instrument readout shown next to the gauge.

A bottle-green panel with an analogue dial: coloured alarm zones (red / amber / green from
the safe range), tick marks with numbers, a needle that sweeps and settles with a little
overshoot, and the reading in large mono digits that count up. The status colour is part
of the panel itself (top rule, lamp, glow), not a separate coloured box.

The motion is pure CSS (see theme.py). The needle's angle and the number are passed as CSS
variables; when they change, the browser animates between the old and new values. The HTML
is built as ONE line with no blank lines, because a blank line would end a markdown HTML block.
"""

import html

from gauge_app.theme import STATUS_COLOURS, STATUS_WORDS, arc_path, polar

CX, CY, R = 150, 135, 112      # dial centre and radius in the SVG's own units
START, END = -125.0, 125.0     # the scale sweeps 250 degrees, clockwise from 12 o'clock


def decimals_for(span):
    """Sensible number of decimals for the gauge's range (0-4000 psi vs 0-3 bar)."""
    return 0 if span >= 500 else 1 if span >= 20 else 2


def format_value(value, span):
    if value is None:
        return "– – –"
    return f"{value:.{decimals_for(span)}f}"


def tick_label(v):
    """Short scale numbers for the dial face: 0, 25, 2.5, 0.75 (3 significant figures, no trailing zeros)."""
    return f"{float(f'{v:.3g}'):g}"


def _angle(value, lo, span):
    """Needle angle for a value. Allowed to go slightly past either end, like a real needle."""
    frac = max(-0.05, min(1.05, (value - lo) / span))
    return START + frac * (END - START)


def dial_svg(value, lo, hi, safe_low, safe_high, margin):
    span = (hi - lo) or 1.0

    def theta(v):
        return START + max(0.0, min(1.0, (v - lo) / span)) * (END - START)

    band = margin * (safe_high - safe_low)
    zones = [(lo, safe_low, STATUS_COLOURS["RED"]), (safe_low, safe_low + band, STATUS_COLOURS["AMBER"]),
             (safe_low + band, safe_high - band, STATUS_COLOURS["GREEN"]),
             (safe_high - band, safe_high, STATUS_COLOURS["AMBER"]), (safe_high, hi, STATUS_COLOURS["RED"])]
    parts = [f'<path class="gd-track" d="{arc_path(CX, CY, R, START, END)}"/>']
    for a, b, colour in zones:
        if b > a:
            parts.append(f'<path class="gd-zone" stroke="{colour}" d="{arc_path(CX, CY, R, theta(a), theta(b))}"/>')
    parts.append(f'<path d="{arc_path(CX, CY, R - 22, START, END)}" fill="none" stroke="rgba(205,185,143,.35)" stroke-width="1"/>')

    for i in range(21):                       # a tick every 5 % of the scale, a number every 25 %
        angle = START + i * (END - START) / 20
        major = i % 5 == 0
        x0, y0 = polar(CX, CY, R - 25, angle)
        x1, y1 = polar(CX, CY, R - (37 if major else 31), angle)
        parts.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#CDB98F" '
                     f'stroke-width="{1.8 if major else 1}" opacity="{1 if major else .6}"/>')
        if major:
            tx, ty = polar(CX, CY, R - 53, angle)
            parts.append(f'<text x="{tx:.1f}" y="{ty + 3.5:.1f}" text-anchor="middle" font-family="DM Mono, monospace" '
                         f'font-size="10" fill="#CDB98F">{tick_label(lo + i / 20 * span)}</text>')

    rest = value is None                          # no reading: needle parked at the start, dimmed
    angle = START if rest else _angle(value, lo, span)
    dim = ' opacity=".35"' if rest else ""
    needle = (f'<g class="gd-needle" style="--a:{angle:.2f}deg;--from:{START - 6}deg">'
              f'<polygon points="150,31 154.4,135 150,155 145.6,135" fill="url(#gdNeedle)"{dim}/>'
              f'<line x1="150" y1="36" x2="150" y2="128" stroke="rgba(255,255,255,.6)" stroke-width=".9"/></g>')
    return ('<svg viewBox="0 0 300 214" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="analogue dial">'
            '<defs><linearGradient id="gdNeedle" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFF4D6"/>'
            '<stop offset="1" stop-color="#E0A63A"/></linearGradient>'
            '<radialGradient id="gdHub" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="#F3E0B0"/>'
            '<stop offset=".5" stop-color="#B08D57"/><stop offset="1" stop-color="#6B4F25"/></radialGradient>'
            '<linearGradient id="gdGlare" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".06"/>'
            '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>'
            + "".join(parts) + needle +
            '<circle cx="150" cy="135" r="10" fill="url(#gdHub)" stroke="rgba(0,0,0,.4)" stroke-width="1"/>'
            '<circle cx="150" cy="135" r="3" fill="#24392F"/>'
            '<ellipse cx="108" cy="62" rx="92" ry="34" transform="rotate(-24 108 62)" fill="url(#gdGlare)" pointer-events="none"/>'
            '</svg>')


def _number_html(value, unit, span):
    """The reading. Counters animate it; the plain text is the fallback and what screen readers get."""
    unit_html = f'<span class="gd-unit">{html.escape(unit or "")}</span>'
    if value is None:
        return f'<div class="gd-value">– – –{unit_html}</div>'
    d = decimals_for(span)
    scaled = round(abs(value) * 10 ** d)           # the number as an integer: 76.1 -> 761
    sign = "−" if value < 0 and scaled > 0 else ""
    text = f"{abs(value):.{d}f}"
    return (f'<div class="gd-value gd-count gd-d{d}" style="--t:{scaled};--p:{10 ** d}" role="img" '
            f'aria-label="{sign}{text} {html.escape(unit or "")}">{sign}<span class="gd-fallback">{text}</span>'
            f'<span class="gd-int"></span><span class="gd-dot">.</span><span class="gd-frac"></span>{unit_html}</div>')


def readout_html(value, unit, status, lo, hi, safe_low, safe_high, margin, live=False):
    """live=True: no entrance animation and a quicker needle, because the panel updates every frame."""
    span = hi - lo
    classes = "gd-readout" + (" gd-live" if live else "") + f" gd-s-{(status or 'none').lower()}"
    band = margin * (safe_high - safe_low)
    return (f'<div class="{classes}" style="--status:{STATUS_COLOURS[status]};--dur:{".22s" if live else "1.1s"}">'
            f'<div class="gd-head"><span class="gd-k">Reading</span>'
            f'<span class="gd-k gd-k-status"><span class="gd-lamp"></span>{STATUS_WORDS[status]}</span></div>'
            f'<div class="gd-dial">{dial_svg(value, lo, hi, safe_low, safe_high, margin)}</div>'
            f'{_number_html(value, unit, span)}'
            f'<div class="gd-safe">safe {format_value(safe_low, span)} – {format_value(safe_high, span)}'
            f' · amber within {format_value(band, span)}</div></div>')


def details_html(rows, note=None):
    """Label ....... value rows (dotted leaders), like an instrument data plate."""
    body = "".join(f'<div class="gd-row"><span class="k">{html.escape(k)}</span><span class="fill"></span>'
                   f'<span class="v">{v}</span></div>' for k, v in rows)
    note_html = f'<div class="gd-note">{note}</div>' if note else ""
    return f'<div class="gd-details">{body}</div>{note_html}'
