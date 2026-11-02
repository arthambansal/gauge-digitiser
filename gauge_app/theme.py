"""
theme.py - the app's visual identity: a restored analogue instrument cabinet.

Palette: cream paper, brass trim, oxblood accent, bottle-green instrument panels.
Type: Fraunces (headings), DM Sans (text), DM Mono (numbers). Base colours and fonts are in
.streamlit/config.toml; this file adds what config can't: paper grain, the hero header,
the brass bezel around the gauge photo, motion (entrance, hover, needle, count-up) and the
dark control-panel sidebar. Motion is switched off for visitors who ask for reduced motion.
"""

import math

import streamlit as st

CREAM = "#F4EBD9"
PAPER = "#FBF5E9"
BRASS = "#B08D57"
BRASS_PALE = "#CDB98F"
OXBLOOD = "#7A1F1F"
BOTTLE = "#24392F"
INK = "#2B261F"
MUTED = "#6E6352"

# "LOW" = a reading exists but its confidence is below the threshold (no alert is raised)
STATUS_COLOURS = {"GREEN": "#4E9C6E", "AMBER": "#D99A2B", "RED": "#C2443B", "LOW": "#9A8F7C", None: "#8A8070"}
STATUS_WORDS = {"GREEN": "Within range", "AMBER": "Near limit", "RED": "Out of range", "LOW": "Low confidence",
                None: "No reading"}

# The same colours in OpenCV's BGR order, for drawing on images
BGR = {"brass": (87, 141, 176), "oxblood": (31, 31, 122), "cream": (217, 235, 244), "bottle": (47, 57, 36)}


def polar(cx, cy, r, deg):
    """Point at angle `deg` (clockwise from 12 o'clock) and distance r from (cx, cy)."""
    a = math.radians(deg)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def arc_path(cx, cy, r, deg0, deg1):
    """SVG path for an arc from deg0 to deg1 (clockwise from 12 o'clock)."""
    x0, y0 = polar(cx, cy, r, deg0)
    x1, y1 = polar(cx, cy, r, deg1)
    large = 1 if abs(deg1 - deg0) > 180 else 0
    return f"M {x0:.2f} {y0:.2f} A {r} {r} 0 {large} 1 {x1:.2f} {y1:.2f}"


def _emblem_svg():
    """The little brass dial in the header. Its needle sways by itself (CSS), like a live gauge."""
    ticks = []
    for i in range(28):
        a = -135 + i * 10
        major = i % 3 == 0
        x0, y0 = polar(100, 100, 70, a)
        x1, y1 = polar(100, 100, 61 if major else 65, a)
        ticks.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
                     f'stroke="#2B261F" stroke-width="{2.4 if major else 1.1}" stroke-linecap="round"/>')
    zones = "".join(f'<path d="{arc_path(100, 100, 52, a, b)}" stroke="{c}" stroke-width="5" fill="none"/>'
                    for a, b, c in ((-135, 20, "#4E9C6E"), (24, 78, "#D99A2B"), (82, 135, "#C2443B")))
    return (
        '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Animated dial gauge">'
        '<defs>'
        '<linearGradient id="gdEmBrass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#EAD39F"/>'
        '<stop offset=".45" stop-color="#B08D57"/><stop offset="1" stop-color="#7C5E2E"/></linearGradient>'
        '<radialGradient id="gdEmFace" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#FFF9EB"/>'
        '<stop offset="1" stop-color="#E9DBBC"/></radialGradient>'
        '<linearGradient id="gdEmGlare" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '</defs>'
        '<circle cx="100" cy="100" r="97" fill="url(#gdEmBrass)"/>'
        '<circle cx="100" cy="100" r="88" fill="#2B261F"/>'
        '<circle cx="100" cy="100" r="82" fill="url(#gdEmFace)"/>'
        + zones + "".join(ticks) +
        '<g class="gd-emblem-needle"><polygon points="100,36 103.6,100 100,116 96.4,100" fill="#7A1F1F"/></g>'
        '<circle cx="100" cy="100" r="9" fill="url(#gdEmBrass)"/><circle cx="100" cy="100" r="3" fill="#2B261F"/>'
        '<path d="M 28 82 A 76 76 0 0 1 118 26 L 100 60 Z" fill="url(#gdEmGlare)" opacity=".5"/>'
        '</svg>')


_TOKENS = {"@CREAM@": CREAM, "@PAPER@": PAPER, "@BRASS@": BRASS, "@BRASSP@": BRASS_PALE, "@OXB@": OXBLOOD,
           "@BOTTLE@": BOTTLE, "@INK@": INK, "@MUTED@": MUTED}

CSS = """
<style>
@property --t { syntax: '<integer>'; inherits: true; initial-value: 0; }
@property --status { syntax: '<color>'; inherits: true; initial-value: #8A8070; }

/* ===================== page: paper, grain, warm light ===================== */
[data-testid="stApp"] {
  background:
    radial-gradient(1000px 520px at 8% -6%, rgba(255,248,228,.95), transparent 62%),
    radial-gradient(900px 640px at 108% 6%, rgba(176,141,87,.20), transparent 58%),
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .36  0 0 0 0 .27  0 0 0 0 .14  0 0 0 .10 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>"),
    @CREAM@;
  background-attachment: fixed, fixed, scroll, scroll;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display: none; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1240px; }
h1, h2, h3 { letter-spacing: -0.01em; }

/* ===================== motion primitives ===================== */
@keyframes gd-rise { from { opacity: 0; transform: translateY(18px); } }
@keyframes gd-fade { from { opacity: 0; } }
@keyframes gd-float { 50% { transform: translateY(-7px); } }
@keyframes gd-sway { 0% { transform: rotate(-96deg); } 30% { transform: rotate(38deg); } 46% { transform: rotate(22deg); }
                     68% { transform: rotate(104deg); } 100% { transform: rotate(-58deg); } }
@keyframes gd-sweep { from { transform: rotate(var(--from, -130deg)); } }
@keyframes gd-countup { from { --t: 0; } }
@keyframes gd-breathe { 50% { box-shadow: 0 0 0 3px rgba(0,0,0,.25), 0 0 22px var(--status); } }
@keyframes gd-alarm { 50% { box-shadow: 0 0 0 4px rgba(194,68,59,.5), 0 22px 40px -22px rgba(20,30,25,.8),
                              0 0 46px rgba(194,68,59,.45), inset 0 0 60px rgba(0,0,0,.35); } }
@keyframes gd-sheen { from { transform: translateX(-135%); } to { transform: translateX(135%); } }
@keyframes gd-sheen-hover { from { transform: translateX(-135%); } to { transform: translateX(135%); } }

[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > * {
  animation: gd-rise .75s cubic-bezier(.2,.7,.2,1) backwards;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:nth-child(2) { animation-delay: .07s; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:nth-child(3) { animation-delay: .14s; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:nth-child(4) { animation-delay: .21s; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:nth-child(5) { animation-delay: .28s; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:nth-child(6) { animation-delay: .35s; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:nth-child(n+7) { animation-delay: .42s; }

/* ===================== hero header ===================== */
.gd-hero { display: grid; grid-template-columns: 1fr auto; gap: 2rem; align-items: center;
           padding: .2rem 0 1.3rem 0; border-bottom: 3px double @BRASS@; margin-bottom: 1.2rem; }
.gd-eyebrow { font-family: 'DM Mono', monospace; font-size: .72rem; letter-spacing: .2em; text-transform: uppercase;
              color: @BRASS@; margin: 0 0 .25rem 0; animation: gd-rise .8s .05s cubic-bezier(.2,.7,.2,1) backwards; }
.gd-title { font-family: 'Fraunces', serif; font-weight: 600; font-size: clamp(2.5rem, 5.6vw, 4rem); line-height: .98;
            color: @INK@; margin: 0; text-shadow: 0 1px 0 rgba(255,255,255,.75), 0 -1px 0 rgba(43,38,31,.08);
            animation: gd-rise .9s .12s cubic-bezier(.2,.7,.2,1) backwards; }
.gd-tagline { max-width: 33rem; font-size: 1.04rem; line-height: 1.5; color: @MUTED@; margin: .8rem 0 1rem 0;
              animation: gd-rise .9s .22s cubic-bezier(.2,.7,.2,1) backwards; }
.gd-chips { display: flex; flex-wrap: wrap; gap: .5rem; animation: gd-rise .9s .32s cubic-bezier(.2,.7,.2,1) backwards; }
.gd-chip { font-family: 'DM Mono', monospace; font-size: .68rem; letter-spacing: .12em; text-transform: uppercase;
           padding: .3rem .65rem; border: 1px solid @BRASS@; border-radius: 2px; color: @OXB@;
           background: rgba(255,255,255,.4); box-shadow: 0 1px 0 rgba(255,255,255,.7) inset;
           transition: transform .2s, background .2s, box-shadow .2s; }
.gd-chip:hover { transform: translateY(-2px); background: rgba(255,255,255,.75); box-shadow: 0 6px 12px -6px rgba(122,31,31,.35); }
.gd-emblem { animation: gd-fade 1.2s .3s backwards; }
.gd-emblem svg { width: clamp(118px, 15vw, 188px); height: auto; display: block;
                 filter: drop-shadow(0 16px 20px rgba(43,38,31,.30)); animation: gd-float 7s ease-in-out infinite; }
.gd-emblem-needle { transform-origin: 100px 100px; animation: gd-sway 11s cubic-bezier(.45,.05,.4,1) infinite alternate; }

/* ===================== navigation: engraved labels with a growing underline ===================== */
.st-key-view { margin-bottom: .6rem; }
.st-key-view [data-testid="stButtonGroup"] > div { gap: .4rem 1.9rem !important; flex-wrap: wrap; }
.st-key-view button { background: transparent !important; border: none !important; border-radius: 0 !important;
                      padding: .15rem 0 .35rem 0 !important; min-height: 0 !important; box-shadow: none !important;
                      position: relative; }
.st-key-view button::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 2px;
                             background: @OXB@; transform: scaleX(0); transform-origin: left;
                             transition: transform .35s cubic-bezier(.2,.7,.2,1); }
.st-key-view button:hover::after { transform: scaleX(.45); background: @BRASS@; }
.st-key-view button[aria-checked="true"]::after { transform: scaleX(1); background: @OXB@; }
.st-key-view button p { font-family: 'Fraunces', serif !important; font-size: 1.14rem !important;
                        font-weight: 500 !important; color: @MUTED@; transition: color .25s; }
.st-key-view button[aria-checked="true"] p { color: @OXB@; }
.st-key-view button:hover p { color: @INK@; }
.st-key-source button p, .st-key-image_view button p, .st-key-cal_mode button p {
  font-family: 'DM Mono', monospace !important; font-size: .78rem !important; letter-spacing: .02em; }

/* ===================== section labels ===================== */
.gd-label { font-family: 'DM Mono', monospace; font-size: .7rem; letter-spacing: .16em; text-transform: uppercase;
            color: @MUTED@; margin: 0 0 .4rem 0; }

/* ===================== the instrument readout ===================== */
.gd-readout { --status: #8A8070; position: relative; overflow: hidden; container-type: inline-size; color: @CREAM@; border-radius: 12px;
  padding: 1rem 1.2rem 1.05rem 1.2rem; border: 1px solid rgba(176,141,87,.6);
  background: radial-gradient(120% 90% at 50% 0%, #34503F 0%, #24392F 46%, #18261F 100%);
  box-shadow: 0 0 0 4px rgba(176,141,87,.15), 0 22px 40px -22px rgba(20,30,25,.85),
              inset 0 1px 0 rgba(255,255,255,.09), inset 0 0 60px rgba(0,0,0,.35);
  transition: --status .6s ease; }
.gd-readout::before { content: ""; position: absolute; inset: 0; pointer-events: none;
  background: repeating-linear-gradient(0deg, rgba(255,255,255,.028) 0 1px, transparent 1px 3px); }
.gd-readout::after { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px; background: var(--status);
  box-shadow: 0 0 18px var(--status); }
.gd-s-red { animation: gd-alarm 1.5s ease-in-out infinite; }
.gd-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: .3rem .8rem;
           position: relative; z-index: 1; }
.gd-k { font-family: 'DM Mono', monospace; font-size: .68rem; letter-spacing: .18em; text-transform: uppercase; color: @BRASSP@; }
.gd-k-status { display: inline-flex; align-items: center; gap: .5rem; color: @CREAM@; letter-spacing: .08em;
               font-family: 'DM Sans', sans-serif; font-weight: 600; font-size: .82rem; text-transform: none;
               white-space: nowrap; }
.gd-lamp { width: .72rem; height: .72rem; border-radius: 50%; background: var(--status);
           box-shadow: 0 0 0 3px rgba(0,0,0,.25), 0 0 12px var(--status); animation: gd-breathe 3.2s ease-in-out infinite; }
.gd-s-red .gd-lamp, .gd-s-amber .gd-lamp { animation-duration: 1.3s; }
.gd-dial { position: relative; z-index: 1; width: 100%; max-width: 380px; margin: .15rem auto 0 auto; }
.gd-dial svg { width: 100%; height: auto; display: block; overflow: visible; }
.gd-track { fill: none; stroke: rgba(255,255,255,.07); stroke-width: 11; stroke-linecap: butt; }
.gd-zone { fill: none; stroke-width: 11; opacity: .92; }
.gd-needle { transform-origin: 150px 135px; transform: rotate(var(--a, -125deg));
             transition: transform var(--dur, 1.1s) cubic-bezier(.34,1.52,.5,1);
             animation: gd-sweep 1.6s .15s cubic-bezier(.34,1.35,.5,1) backwards;
             filter: drop-shadow(0 4px 4px rgba(0,0,0,.55)); }
.gd-value { position: relative; z-index: 1; font-family: 'DM Mono', monospace; font-weight: 500; text-align: center;
            font-size: clamp(1.9rem, 18cqi, 4.1rem); line-height: 1.05; white-space: nowrap; letter-spacing: -0.03em; margin: -.35rem 0 .1rem 0;
            color: #FFF8E8; text-shadow: 0 0 26px color-mix(in srgb, var(--status) 60%, transparent); }
.gd-unit { font-size: 1.05rem; color: @BRASSP@; margin-left: .4rem; letter-spacing: .02em; text-shadow: none; }
.gd-count { transition: --t var(--dur, 1.1s) cubic-bezier(.2,.8,.2,1);
            animation: gd-countup 1.4s .15s cubic-bezier(.2,.8,.2,1) backwards; }
.gd-count .gd-int, .gd-count .gd-frac, .gd-count .gd-dot { display: none; }
@supports (width: round(down, 1.5px, 1px)) {
  .gd-count .gd-fallback { display: none; }
  .gd-count .gd-int, .gd-count .gd-frac { display: inline; }
  .gd-count .gd-dot { display: inline; }
  .gd-count.gd-d0 .gd-dot, .gd-count.gd-d0 .gd-frac { display: none; }
  .gd-count .gd-int::before { counter-reset: gdi round(down, calc(var(--t) / var(--p)), 1); content: counter(gdi); }
  .gd-count .gd-frac::before { counter-reset: gdf calc(var(--t) - var(--p) * round(down, calc(var(--t) / var(--p)), 1));
                               content: counter(gdf); }
  .gd-count.gd-d2 .gd-frac::before { content: counter(gdf, decimal-leading-zero); }
}
.gd-live .gd-needle, .gd-live .gd-count { animation: none; }
.gd-safe { position: relative; z-index: 1; text-align: center; font-family: 'DM Mono', monospace; font-size: .72rem;
           color: @BRASSP@; letter-spacing: .04em; margin-top: .2rem; }

/* ===================== details list under the readout ===================== */
.gd-details { margin: .9rem 0 0 0; font-size: .9rem; }
.gd-row { display: flex; align-items: baseline; gap: .5rem; padding: .34rem 0; border-bottom: 1px dotted @BRASSP@; }
.gd-row .k { color: @MUTED@; white-space: nowrap; }
.gd-row .fill { flex: 1; }
.gd-row .v { font-family: 'DM Mono', monospace; color: @INK@; text-align: right; }
.gd-note { font-size: .82rem; color: @MUTED@; margin-top: .55rem; line-height: 1.45; }

/* ===================== gauge photo: brass bezel, screws, glass sheen ===================== */
.st-key-hero [data-testid="stImage"] { position: relative; overflow: hidden; padding: 17px; border-radius: 12px;
  background:
    radial-gradient(circle at 9px 9px, #46331A 0 1.6px, #A58144 2.2px 3.6px, transparent 4px),
    radial-gradient(circle at calc(100% - 9px) 9px, #46331A 0 1.6px, #A58144 2.2px 3.6px, transparent 4px),
    radial-gradient(circle at 9px calc(100% - 9px), #46331A 0 1.6px, #A58144 2.2px 3.6px, transparent 4px),
    radial-gradient(circle at calc(100% - 9px) calc(100% - 9px), #46331A 0 1.6px, #A58144 2.2px 3.6px, transparent 4px),
    linear-gradient(145deg, #E8D3A0 0%, #B08D57 36%, #8D6C39 68%, #CDAE72 100%);
  box-shadow: 0 28px 48px -26px rgba(43,38,31,.7), 0 2px 0 rgba(255,255,255,.55) inset, 0 -2px 0 rgba(60,40,10,.35) inset; }
.st-key-hero [data-testid="stImage"] img { display: block; width: 100%; border-radius: 4px; outline: 1px solid rgba(0,0,0,.5);
  outline-offset: -1px; box-shadow: 0 0 0 1px rgba(60,40,10,.5); }
.st-key-hero [data-testid="stImage"]::after { content: ""; position: absolute; inset: 17px; border-radius: 4px; pointer-events: none;
  background: linear-gradient(112deg, transparent 36%, rgba(255,255,255,.30) 46%, rgba(255,255,255,.07) 53%, transparent 60%);
  transform: translateX(-135%); animation: gd-sheen 1.9s .55s cubic-bezier(.3,.6,.3,1) 1 forwards; }
.st-key-hero [data-testid="stImage"]:hover::after { animation: gd-sheen-hover 1.1s ease-out 1 forwards; }
.gd-hero-caption { font-family: 'DM Mono', monospace; font-size: .74rem; color: @MUTED@; margin-top: .55rem; }

/* ===================== live camera: the same brass bezel around the video ===================== */
.st-key-livecam { padding: 17px; border-radius: 12px;
  background: linear-gradient(145deg, #E8D3A0 0%, #B08D57 36%, #8D6C39 68%, #CDAE72 100%);
  box-shadow: 0 28px 48px -26px rgba(43,38,31,.7), 0 2px 0 rgba(255,255,255,.55) inset, 0 -2px 0 rgba(60,40,10,.35) inset; }
.st-key-livecam iframe { border-radius: 4px; background: #1A2922; }

/* ===================== filmstrip, gallery, explain ===================== */
.gd-stage { font-family: 'DM Mono', monospace; font-size: .7rem; color: @MUTED@; line-height: 1.3; margin-top: .2rem; }
.gd-stage b { color: @OXB@; font-weight: 500; }
.gd-card-title { font-family: 'Fraunces', serif; font-weight: 500; font-size: 1rem; line-height: 1.2; margin: .35rem 0 .1rem 0; min-height: 2.4em; }
.gd-card-note { font-size: .78rem; color: @MUTED@; line-height: 1.35; height: 2.7em; overflow: hidden; }
[data-testid="stExpander"] [data-testid="stImage"] { overflow: hidden; border-radius: 6px;
  box-shadow: 0 8px 18px -12px rgba(43,38,31,.55); transition: box-shadow .35s; }
[data-testid="stExpander"] [data-testid="stImage"] img { transition: transform .6s cubic-bezier(.2,.7,.2,1); }
[data-testid="stExpander"] [data-testid="stColumn"]:hover [data-testid="stImage"] { box-shadow: 0 16px 28px -14px rgba(122,31,31,.55); }
[data-testid="stExpander"] [data-testid="stColumn"]:hover [data-testid="stImage"] img { transform: scale(1.07); }
.gd-explain ol { padding-left: 1.2rem; }
.gd-explain li { margin-bottom: .55rem; line-height: 1.5; }
.gd-explain code { background: transparent; color: @OXB@; padding: 0; }

/* ===================== controls: tactile buttons, glowing inputs ===================== */
.stButton button, .stDownloadButton button { font-weight: 500; letter-spacing: .01em;
  box-shadow: 0 1px 0 rgba(255,255,255,.7) inset, 0 2px 0 @BRASSP@, 0 5px 10px -6px rgba(43,38,31,.45);
  transition: transform .16s, box-shadow .22s, border-color .2s, background-color .2s; }
.stButton button:hover, .stDownloadButton button:hover { transform: translateY(-2px); border-color: @OXB@;
  box-shadow: 0 1px 0 rgba(255,255,255,.7) inset, 0 3px 0 @BRASS@, 0 12px 18px -8px rgba(122,31,31,.4); }
.stButton button:active, .stDownloadButton button:active { transform: translateY(1px);
  box-shadow: inset 0 2px 5px rgba(0,0,0,.2); }
[data-testid="stExpander"] { border-radius: 8px; box-shadow: 0 8px 20px -16px rgba(43,38,31,.5);
  background: rgba(255,255,255,.28); transition: box-shadow .3s, background .3s; }
[data-testid="stExpander"]:hover { box-shadow: 0 14px 26px -16px rgba(122,31,31,.45); background: rgba(255,255,255,.42); }
[data-testid="stFileUploaderDropzone"] { border: 1.6px dashed @BRASS@; background: rgba(255,255,255,.35);
  transition: background .3s, border-color .3s, box-shadow .3s; }
[data-testid="stFileUploaderDropzone"]:hover { background: rgba(255,255,255,.7); border-color: @OXB@;
  box-shadow: 0 0 0 5px rgba(176,141,87,.18); }
[data-testid="stCameraInput"] { padding: 10px; border-radius: 10px; background: linear-gradient(145deg, #E8D3A0, #B08D57 50%, #8D6C39);
  box-shadow: 0 20px 36px -22px rgba(43,38,31,.6); }
[data-testid="stDataFrame"] { border-radius: 8px; box-shadow: 0 10px 24px -18px rgba(43,38,31,.55); }

/* ===================== sidebar: dark control panel ===================== */
[data-testid="stSidebar"] { background: linear-gradient(185deg, #25382F 0%, #1A2922 100%);
  box-shadow: 10px 0 34px -16px rgba(0,0,0,.6), inset -1px 0 0 rgba(176,141,87,.55); }
[data-testid="stSidebar"] h3 { font-family: 'DM Mono', monospace !important; font-size: .72rem !important; letter-spacing: .22em;
  text-transform: uppercase; color: @BRASSP@ !important; margin-top: 1.1rem;
  border-bottom: 1px solid rgba(205,185,143,.28); padding-bottom: .4rem; }
[data-testid="stSidebar"] .stButton button, [data-testid="stSidebar"] .stDownloadButton button {
  background: rgba(255,255,255,.06); color: #F0E6D0; border-color: rgba(205,185,143,.4);
  box-shadow: 0 1px 0 rgba(255,255,255,.08) inset, 0 2px 0 rgba(0,0,0,.35); }
[data-testid="stSidebar"] .stButton button:hover, [data-testid="stSidebar"] .stDownloadButton button:hover {
  border-color: #E0A63A; color: #fff; background: rgba(224,166,58,.12);
  box-shadow: 0 1px 0 rgba(255,255,255,.1) inset, 0 3px 0 rgba(0,0,0,.4), 0 12px 18px -8px rgba(224,166,58,.35); }
[data-testid="stSidebar"] [data-testid="stExpander"] { background: rgba(255,255,255,.05); box-shadow: none;
  border-color: rgba(205,185,143,.3); }
[data-testid="stSidebar"] [data-testid="stExpander"]:hover { background: rgba(255,255,255,.09); box-shadow: none; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background: rgba(255,255,255,.05); }

/* ===================== phones ===================== */
@media (max-width: 640px) {
  .block-container { padding-top: 3.6rem; padding-left: 1rem; padding-right: 1rem; }
  .gd-hero { grid-template-columns: 1fr; gap: .8rem; }
  .gd-emblem, .gd-chips { display: none; }
  .gd-tagline { font-size: .96rem; }
  .gd-readout { padding: .85rem .9rem; }
  .st-key-hero [data-testid="stHorizontalBlock"]:not([data-testid="stColumn"] [data-testid="stHorizontalBlock"]) {
      flex-direction: column-reverse; }
  .st-key-hero [data-testid="stImage"] { padding: 12px; }
  .st-key-hero [data-testid="stImage"]::after { inset: 12px; }
}

/* ===================== reduced motion: show everything, move nothing ===================== */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
"""
for _token, _value in _TOKENS.items():
    CSS = CSS.replace(_token, _value)


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def masthead(note_html=""):
    """Hero header: eyebrow, title, tagline, chips, and a brass dial whose needle sways by itself."""
    st.markdown(
        '<div class="gd-hero"><div>'
        '<p class="gd-eyebrow">Analogue dial reader · classical CV</p>'
        '<h1 class="gd-title">Gauge Digitizer</h1>'
        '<p class="gd-tagline">Point a camera at any dial gauge. Get the number, whether it is safe, and a record of it, '
        'without a single neural network.</p>'
        '<div class="gd-chips"><span class="gd-chip">Hough circles</span><span class="gd-chip">Canny edges</span>'
        '<span class="gd-chip">Hough lines</span><span class="gd-chip">Tesseract OCR</span></div>'
        '</div><div class="gd-emblem">' + _emblem_svg() + '</div></div>',
        unsafe_allow_html=True)


def label(text):
    st.markdown(f'<p class="gd-label">{text}</p>', unsafe_allow_html=True)
