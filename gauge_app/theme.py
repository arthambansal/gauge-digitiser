"""
theme.py - the app's visual identity: a restored analogue instrument cabinet.

Palette: cream dial-face, brass trim, oxblood accent, bottle-green readout window.
Type: Fraunces (headings), DM Sans (text), DM Mono (numbers). The base colours and
fonts are set in .streamlit/config.toml; this file adds the custom pieces
(masthead, readout window, filmstrip, gallery) on top.
"""

import streamlit as st

CREAM = "#F4EBD9"
PAPER = "#FBF5E9"
BRASS = "#B08D57"
BRASS_PALE = "#CDB98F"
OXBLOOD = "#7A1F1F"
BOTTLE = "#24392F"
INK = "#2B261F"
MUTED = "#6E6352"

# Status colours, tuned to sit with the palette (not pure traffic-light colours)
# "LOW" = a reading exists but its confidence is below the threshold (no alert is raised)
STATUS_COLOURS = {"GREEN": "#4E9C6E", "AMBER": "#D99A2B", "RED": "#C2443B", "LOW": "#9A8F7C", None: "#8A8070"}
STATUS_WORDS = {"GREEN": "Within range", "AMBER": "Near limit", "RED": "Out of range", "LOW": "Low confidence",
                None: "No reading"}

# The same colours in OpenCV's BGR order, for drawing on images
BGR = {"brass": (87, 141, 176), "oxblood": (31, 31, 122), "cream": (217, 235, 244), "bottle": (47, 57, 36)}

CSS = f"""
<style>
/* ---------- page frame ---------- */
[data-testid="stDecoration"] {{ display: none; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1240px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}

/* ---------- masthead ---------- */
.gd-masthead {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem;
               border-bottom: 3px double {BRASS}; padding-bottom: .55rem; margin-bottom: 1.4rem; }}
.gd-eyebrow {{ font-family: 'DM Mono', monospace; font-size: .72rem; letter-spacing: .18em;
              text-transform: uppercase; color: {BRASS}; margin: 0 0 .15rem 0; }}
.gd-title {{ font-family: 'Fraunces', serif; font-weight: 600; font-size: clamp(2rem, 4.2vw, 2.9rem);
            line-height: 1; color: {INK}; margin: 0; }}
.gd-masthead-note {{ font-family: 'DM Mono', monospace; font-size: .74rem; color: {MUTED};
                    text-align: right; line-height: 1.5; }}

/* ---------- main navigation: engraved tab labels, not buttons ---------- */
.st-key-view {{ margin-bottom: .6rem; }}
.st-key-view [data-testid="stButtonGroup"] > div {{ gap: .4rem 1.9rem !important; flex-wrap: wrap; }}
.st-key-view button {{ background: transparent !important; border: none !important; border-radius: 0 !important;
                      border-bottom: 2px solid transparent !important; padding: .15rem 0 .3rem 0 !important;
                      min-height: 0 !important; box-shadow: none !important; }}
.st-key-view button p {{ font-family: 'Fraunces', serif !important; font-size: 1.12rem !important;
                        font-weight: 500 !important; color: {MUTED}; }}
.st-key-view button[aria-checked="true"] {{ border-bottom-color: {OXBLOOD} !important; }}
.st-key-view button[aria-checked="true"] p {{ color: {OXBLOOD}; }}
.st-key-view button:hover p {{ color: {INK}; }}

/* secondary switches (source, image view): small mono labels */
.st-key-source button p, .st-key-image_view button p, .st-key-cal_mode button p {{
    font-family: 'DM Mono', monospace !important; font-size: .78rem !important; letter-spacing: .02em; }}

/* ---------- section labels ---------- */
.gd-label {{ font-family: 'DM Mono', monospace; font-size: .7rem; letter-spacing: .16em;
            text-transform: uppercase; color: {MUTED}; margin: 0 0 .4rem 0; }}

/* ---------- the readout window (bottle green, like an instrument display) ---------- */
.gd-readout {{ background: {BOTTLE}; color: {CREAM}; border-radius: 4px; padding: 1.15rem 1.3rem 1.05rem 1.3rem;
              border-left: 7px solid var(--status); box-shadow: inset 0 0 0 1px rgba(176,141,87,.45); }}
.gd-readout .gd-k {{ font-family: 'DM Mono', monospace; font-size: .68rem; letter-spacing: .18em;
                    text-transform: uppercase; color: {BRASS_PALE}; }}
.gd-value {{ font-family: 'DM Mono', monospace; font-weight: 500; font-size: clamp(3rem, 6vw, 4.6rem);
            line-height: 1.02; letter-spacing: -0.03em; margin: .25rem 0 .1rem 0; color: {CREAM}; }}
.gd-unit {{ font-family: 'DM Mono', monospace; font-size: 1.05rem; color: {BRASS_PALE}; margin-left: .35rem;
           letter-spacing: .02em; }}
.gd-status {{ display: flex; align-items: center; gap: .55rem; font-family: 'DM Sans', sans-serif;
             font-weight: 600; font-size: .95rem; margin: .35rem 0 .7rem 0; color: {CREAM}; }}
.gd-lamp {{ width: .78rem; height: .78rem; border-radius: 50%; background: var(--status);
           box-shadow: 0 0 0 3px rgba(0,0,0,.25), 0 0 12px var(--status); }}
.gd-scale svg {{ width: 100%; height: auto; display: block; }}
.gd-scale-ends {{ display: flex; justify-content: space-between; font-family: 'DM Mono', monospace;
                 font-size: .72rem; color: {BRASS_PALE}; margin-top: .15rem; }}

/* ---------- details list under the readout ---------- */
.gd-details {{ margin: .9rem 0 0 0; font-size: .9rem; }}
.gd-row {{ display: flex; align-items: baseline; gap: .5rem; padding: .32rem 0; border-bottom: 1px dotted {BRASS_PALE}; }}
.gd-row .k {{ color: {MUTED}; white-space: nowrap; }}
.gd-row .fill {{ flex: 1; }}
.gd-row .v {{ font-family: 'DM Mono', monospace; color: {INK}; text-align: right; }}
.gd-note {{ font-size: .82rem; color: {MUTED}; margin-top: .55rem; line-height: 1.45; }}

/* ---------- hero image frame ---------- */
[data-testid="stImage"] img {{ border-radius: 3px; }}
.gd-hero-caption {{ font-family: 'DM Mono', monospace; font-size: .74rem; color: {MUTED}; margin-top: .35rem; }}

/* ---------- filmstrip captions ---------- */
.gd-stage {{ font-family: 'DM Mono', monospace; font-size: .7rem; color: {MUTED}; line-height: 1.3; margin-top: .2rem; }}
.gd-stage b {{ color: {OXBLOOD}; font-weight: 500; }}

/* ---------- gallery ---------- */
.gd-card-title {{ font-family: 'Fraunces', serif; font-weight: 500; font-size: 1rem; line-height: 1.2;
                 margin: .3rem 0 .1rem 0; min-height: 2.4em; }}
.gd-card-note {{ font-size: .78rem; color: {MUTED}; line-height: 1.35; height: 2.7em; overflow: hidden; }}

/* ---------- explain panel ---------- */
.gd-explain ol {{ padding-left: 1.2rem; }}
.gd-explain li {{ margin-bottom: .55rem; line-height: 1.5; }}
.gd-explain code {{ background: transparent; color: {OXBLOOD}; padding: 0; }}

/* ---------- buttons: quieter than default ---------- */
.stButton button, .stDownloadButton button {{ font-weight: 500; letter-spacing: .01em; }}

/* ---------- sidebar headings ---------- */
[data-testid="stSidebar"] h3 {{ font-size: 1.05rem; margin-top: .6rem; border-bottom: 1px solid {BRASS_PALE};
                               padding-bottom: .25rem; }}

/* ---------- phones ---------- */
@media (max-width: 640px) {{
  .block-container {{ padding-top: 3.6rem; padding-left: 1rem; padding-right: 1rem; }}
  .gd-masthead {{ flex-direction: column; align-items: flex-start; }}
  .gd-masthead-note {{ display: none; }}
  /* the reading matters most on a phone: show the readout column above the image */
  .st-key-hero [data-testid="stHorizontalBlock"]:not([data-testid="stColumn"] [data-testid="stHorizontalBlock"]) {{
      flex-direction: column-reverse; }}
  .gd-readout {{ padding: .9rem 1rem; }}
}}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def masthead(note_html=""):
    st.markdown(
        f"""<div class="gd-masthead">
              <div><p class="gd-eyebrow">Analogue dial reader · classical CV</p>
                   <h1 class="gd-title">Gauge Digitizer</h1></div>
              <div class="gd-masthead-note">{note_html}</div>
            </div>""",
        unsafe_allow_html=True)


def label(text):
    st.markdown(f'<p class="gd-label">{text}</p>', unsafe_allow_html=True)
