"""
app.py - Streamlit front end for the Analogue Gauge Digitizer.

Run with:   streamlit run app.py

This file only arranges the screen. All computer vision lives in gauge_digitizer/
(read_gauge() runs the whole pipeline); the UI pieces live in gauge_app/.

Views:
  Read a gauge : sample gallery / upload a photo / browser camera snapshot
  Batch        : many photos at once -> results table + CSV
  History      : every reading this session, trend chart, alerts, CSV export
  Live camera  : continuous reading with the detected lines drawn on the live video
                 (browser camera via WebRTC, works online; local webcam / video file when run locally)
"""

import dataclasses
import io
import json
import os

import cv2
import numpy as np
import streamlit as st

from gauge_digitizer.alerts import classify_reading
from gauge_digitizer.calibrate import calibration_from_min_max, tesseract_available
from gauge_digitizer.pipeline import Settings, read_gauge
from gauge_digitizer.utils import draw_angle_grid, draw_overlay
from gauge_app import clickcal, history
from gauge_app.batch import read_batch
from gauge_app.card import make_result_card
from gauge_app.explain import explain_reading
from gauge_app.gallery import gallery_grid, load_gallery
from gauge_app.readout import details_html, format_value, readout_html
from gauge_app.theme import BGR, inject_css, label, masthead

st.set_page_config(page_title="Gauge Digitizer", page_icon="assets/icon.png", layout="wide")
inject_css()

# Streamlit Community Cloud runs apps from /mount/src. There is no webcam on that server.
ON_CLOUD = os.path.exists("/mount/src")
OCR_OK = tesseract_available()

STAGE_NOTES = {  # one plain sentence per pipeline stage, shown under the filmstrip thumbnails
    "1": "grey image", "2": "blurred: removes noise", "3": "dial circle + hub (red)",
    "4": "edges inside the dial", "5": "line candidates (green kept)", "6": "numbers read by OCR"}


# ------------------------------------------------------------------ session state
def init_state():
    ss = st.session_state
    if "ready" in ss:
        return
    first = load_gallery()[0]
    ss.update(ready=True, view="Read a gauge", source="Sample gauges", sample_id=first["id"], gallery_open=False,
              cal_mode="Manual", margin_pct=10, min_conf=0.3, show_grid=False, image_view="Annotated",
              profiles={}, history=[])
    load_calibration(first["calibration"], into=ss)


def load_calibration(cal, into=None):
    """Put a calibration (scale min/max, start angle, sweep, unit) into the sidebar fields."""
    target = into if into is not None else st.session_state.setdefault("pending", {})
    lo, hi = float(cal["scale_min"]), float(cal["scale_max"])
    target.update(cal_min=lo, cal_max=hi, cal_min_angle=round(float(cal["min_angle"]) % 360, 1),
                  cal_sweep=round(float(cal["sweep"]), 1), cal_unit=cal.get("unit", ""),
                  safe_range=(lo + 0.1 * (hi - lo), lo + 0.8 * (hi - lo)), safe_scale=(lo, hi))


def keep_selected(key, default):
    """A segmented control returns None if its selected option is clicked again; restore a choice
    before the widget is drawn (Streamlit does not allow changing it afterwards)."""
    if not st.session_state.get(key):
        st.session_state[key] = default


def apply_pending():
    """
    Widget values can only be changed BEFORE the widget is drawn in a run. Buttons further
    down the page (gallery, click-to-calibrate) therefore store their changes in 'pending'
    and re-run; the changes are applied here, at the top of the next run.
    """
    pending = st.session_state.pop("pending", None)
    if pending:
        st.session_state.update(pending)


# ------------------------------------------------------------------ sidebar
def sidebar():
    ss = st.session_state
    sb = st.sidebar
    sb.markdown("### Calibration")
    modes = ["Manual", "Automatic (OCR)"]
    if not OCR_OK:
        ss.cal_mode = "Manual"
    keep_selected("cal_mode", "Manual")
    sb.segmented_control("Calibration mode", modes, key="cal_mode", disabled=not OCR_OK,
                         label_visibility="collapsed")
    if not OCR_OK:
        sb.caption("Automatic calibration needs the Tesseract OCR program, which isn't installed here. "
                   "Manual calibration works fully.")
    elif ss.cal_mode == "Automatic (OCR)":
        sb.caption("Reads the printed numbers on the dial. The range below is used as a units check and as "
                   "the fallback if OCR fails.")

    c1, c2 = sb.columns(2)
    c1.number_input("Scale min", key="cal_min", format="%g")
    c2.number_input("Scale max", key="cal_max", format="%g")
    c1.number_input("Start angle °", key="cal_min_angle", min_value=0.0, max_value=359.9, step=1.0, format="%.1f")
    c2.number_input("Sweep °", key="cal_sweep", min_value=10.0, max_value=359.0, step=1.0, format="%.1f")
    sb.text_input("Unit", key="cal_unit", placeholder="psi, bar, °C …")
    sb.caption("Angles are measured clockwise from straight down: 9 o'clock = 90°, 12 o'clock = 180°.")
    sb.button("Click to calibrate", on_click=clickcal.start, width="stretch", key="clickcal_sidebar",
              disabled=ss.view != "Read a gauge",
              help="Click the first and last tick of the scale on the image.")

    with sb.expander("Saved gauges"):
        name = st.text_input("Name this calibration", placeholder="e.g. boiler gauge")
        if st.button("Save", disabled=not name):
            ss.profiles[name] = current_calibration_dict()
            st.toast(f"Saved “{name}”")
        if ss.profiles:
            choice = st.selectbox("Load", list(ss.profiles), index=None, placeholder="Choose a saved gauge")
            if choice and st.button("Load selected"):
                load_calibration(ss.profiles[choice])
                st.rerun()
        st.download_button("Download calibration (.json)", json.dumps(current_calibration_dict(), indent=2),
                           file_name="gauge_calibration.json", mime="application/json", width="stretch")
        up = st.file_uploader("Load a calibration file", type=["json"], key="profile_upload")
        if up is not None and ss.get("profile_loaded") != up.file_id:
            try:
                load_calibration(json.loads(up.getvalue()))
                ss.profile_loaded = up.file_id
                st.rerun()
            except (ValueError, KeyError):
                st.error("That file isn't a calibration saved by this app.")

    sb.markdown("### Alarm limits")
    lo, hi = float(ss.cal_min), float(ss.cal_max)
    if hi <= lo:
        sb.error("Scale max must be larger than scale min.")
        hi = lo + 1.0
    span = hi - lo
    sr = ss.get("safe_range")
    # When the scale itself changes, the old safe range means nothing: start again at 10-80 % of the scale.
    # (Streamlit would otherwise reset a slider whose limits changed to the full range.)
    if ss.get("safe_scale") != (lo, hi) or not sr or sr[0] < lo or sr[1] > hi or sr[0] >= sr[1]:
        ss.safe_range = (lo + 0.1 * span, lo + 0.8 * span)
        ss.safe_scale = (lo, hi)
    sb.slider("Safe range", lo, hi, key="safe_range", step=span / 200)
    sb.slider("Warn when within … of a limit (%)", 0, 30, key="margin_pct",
              help="AMBER when the reading is inside the safe range but this close to a limit "
                   "(as a % of the safe range width).")
    sb.slider("Ignore readings below confidence", 0.0, 1.0, key="min_conf", step=0.05,
              help="Low-confidence readings are shown, but they don't raise alerts or go into the live average.")

    sb.markdown("### Display")
    sb.toggle("Angle grid on the image", key="show_grid",
              help="Spokes every 10° from the needle's pivot, for reading tick angles.")

    s = Settings()  # defaults come from the pipeline itself
    with sb.expander("Computer-vision settings"):
        st.caption("Defaults were chosen by a grid search (tune.py). Change them to see what each stage does.")
        s.use_clahe = st.toggle("Even out lighting (CLAHE)", value=s.use_clahe)
        s.blur_kernel = st.slider("Blur kernel", 1, 15, s.blur_kernel, step=2)
        s.circle_param2 = st.slider("Dial: circle votes", 10, 150, s.circle_param2)
        s.min_radius_frac, s.max_radius_frac = st.slider("Dial: radius range (× image)", 0.05, 0.8,
                                                         (s.min_radius_frac, s.max_radius_frac))
        s.canny_low, s.canny_high = st.slider("Needle: Canny thresholds", 0, 400, (s.canny_low, s.canny_high))
        s.line_threshold = st.slider("Needle: line votes", 5, 150, s.line_threshold)
        s.min_line_frac = st.slider("Needle: min length (× radius)", 0.1, 0.9, s.min_line_frac)
        s.use_pivot = st.toggle("Find the needle's hub (pivot)", value=s.use_pivot)

    sb.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    sb.caption("Sample photos: Wikimedia Commons, see samples/SOURCES.md. Fonts: Fraunces, DM Sans, DM Mono (OFL).")

    safe_low, safe_high = ss.safe_range
    return {"settings": s, "calibration": calibration_from_min_max(lo, hi, ss.cal_min_angle, ss.cal_sweep),
            "auto": ss.cal_mode == "Automatic (OCR)", "unit": ss.cal_unit.strip(), "scale_min": lo, "scale_max": hi,
            "safe_low": safe_low, "safe_high": safe_high, "margin": ss.margin_pct / 100, "min_conf": ss.min_conf,
            "on_cloud": ON_CLOUD}


def current_calibration_dict():
    ss = st.session_state
    return {"scale_min": ss.cal_min, "scale_max": ss.cal_max, "min_angle": ss.cal_min_angle,
            "sweep": ss.cal_sweep, "unit": ss.cal_unit}


# ------------------------------------------------------------------ pipeline (cached)
@st.cache_data(max_entries=64, show_spinner=False)
def run_pipeline(image_bytes, settings_tuple, cal_tuple, auto):
    """
    Cached wrapper around read_gauge(). Streamlit re-runs the script on every click; caching
    means moving an unrelated slider does not re-run the vision pipeline (or the slow OCR).
    """
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    settings = Settings(*settings_tuple)
    return read_gauge(image, settings, calibration_from_min_max(*cal_tuple), auto)


def read(image_bytes, cfg):
    cal = cfg["calibration"]
    cal_tuple = (cal.values[0], cal.values[-1], cal.start_angle, cal.rel_angles[-1])
    return run_pipeline(image_bytes, dataclasses.astuple(cfg["settings"]), cal_tuple, cfg["auto"])


def annotated(result, show_grid):
    base = draw_angle_grid(result["colour"], result["dial"]) if show_grid and result["dial"] else result["colour"]
    if result["dial"] is None:
        return result["overlay"]
    return draw_overlay(base, result["dial"], result["needle"], rim=result["rim"],
                        circle_colour=BGR["brass"], needle_colour=BGR["oxblood"])


# ------------------------------------------------------------------ view: read a gauge
def choose_image():
    """Returns (image bytes, source name, true value or None)."""
    ss = st.session_state
    keep_selected("source", "Sample gauges")
    st.segmented_control("Source", ["Sample gauges", "Upload a photo", "Camera"], key="source",
                         label_visibility="collapsed")
    source = ss.source

    if source == "Sample gauges":
        items = load_gallery()
        current = next((it for it in items if it["id"] == ss.sample_id), items[0])
        with st.expander(f"Sample gauges — showing “{current['title']}”", expanded=ss.gallery_open):
            st.caption("Synthetic gauges with exact answers, and real photos from Wikimedia Commons. "
                       "Choosing one also loads its calibration.")
            clicked = gallery_grid(items, current["id"])
            if clicked is not None:
                ss.pending = {"sample_id": clicked["id"], "gallery_open": False}
                load_calibration(clicked["calibration"])
                st.rerun()
        with open(current["path"], "rb") as f:
            return f.read(), current["title"], current["true_value"]

    if source == "Upload a photo":
        up = st.file_uploader("Photo of a gauge", type=["jpg", "jpeg", "png", "webp", "bmp"],
                              help="Face the gauge squarely, fill most of the frame, avoid reflections.")
        return (up.getvalue(), up.name, None) if up else (None, None, None)

    shot = st.camera_input("Point the camera at the gauge, fill the frame, then take a photo")
    return (shot.getvalue(), "camera snapshot", None) if shot else (None, None, None)


def read_page(cfg):
    ss = st.session_state
    image_bytes, source_name, truth = choose_image()
    if image_bytes is None:
        st.markdown('<div class="gd-note" style="margin-top:2rem">No image yet. Choose a sample gauge, upload a '
                    'photo, or take one with your camera.</div>', unsafe_allow_html=True)
        return

    with st.spinner("Reading the gauge…"):
        result = read(image_bytes, cfg)
    value, conf = result["value"], result["confidence"]
    status = classify_reading(value, cfg["safe_low"], cfg["safe_high"], cfg["margin"])
    trusted = value is not None and conf >= cfg["min_conf"]
    if trusted:
        history.add_reading(source_name, value, cfg["unit"], status, conf, result["angle"])

    left, right = st.container(key="hero").columns([7, 4], gap="large")  # readout goes first on phones (CSS)
    with left:
        if clickcal.is_active() and result["dial"] is not None:
            picked = clickcal.calibration_canvas(result)
            if picked is not None:
                ss.pending = {"cal_min_angle": round(picked[0], 1), "cal_sweep": round(max(picked[1], 10.0), 1),
                              "cal_mode": "Manual"}
                st.toast(f"Scale starts at {picked[0]:.1f}° and sweeps {picked[1]:.1f}°")
                st.rerun()
        else:
            keep_selected("image_view", "Annotated")
            st.segmented_control("Image view", ["Annotated", "Original", "Side by side"], key="image_view",
                                 label_visibility="collapsed")
            original = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            view = ss.image_view
            if view == "Original":
                st.image(original, channels="BGR", width="stretch")
            elif view == "Side by side":
                a, b = st.columns(2, gap="small")
                a.image(original, channels="BGR", width="stretch", caption="original")
                b.image(annotated(result, ss.show_grid), channels="BGR", width="stretch", caption="annotated")
            else:
                st.image(annotated(result, ss.show_grid), channels="BGR", width="stretch")
            st.markdown(f'<div class="gd-hero-caption">{source_name} · brass circle = dial, '
                        f'dot = pivot, red line = needle</div>', unsafe_allow_html=True)

    with right:
        shown_status = status if trusted or value is None else "LOW"
        st.markdown(readout_html(value, cfg["unit"], shown_status, cfg["scale_min"], cfg["scale_max"],
                                 cfg["safe_low"], cfg["safe_high"], cfg["margin"]), unsafe_allow_html=True)
        span = cfg["scale_max"] - cfg["scale_min"]
        cal = result["calibration"]
        cal_text = "manual" if cal is None or cal.mode == "manual" else \
            ("OCR, linear" if cal.mode == "auto-linear" else "OCR, non-linear")
        rows = [("Needle angle", "–" if result["angle"] is None else f"{result['angle']:.1f}°"),
                ("Confidence", f"{conf * 100:.0f}%" if value is not None else "–"),
                ("Calibration", cal_text)]
        if truth is not None and value is not None:
            rows.append(("True value", f"{format_value(truth, span)} {cfg['unit']}"))
            rows.append(("Error", f"{abs(value - truth) / span * 100:.2f}% of full scale"))
        notes = []
        if value is not None and not trusted:
            notes.append("Low confidence: another line in the image competes with the needle, so this reading "
                         "won't raise an alert. Check the needle line on the image.")
        notes += result["messages"]
        st.markdown(details_html(rows, "<br>".join(notes) if notes else None), unsafe_allow_html=True)

        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        b1.button("Click to calibrate", on_click=clickcal.start, width="stretch", key="clickcal_main",
                  disabled=result["dial"] is None)
        if value is not None:
            card = make_result_card(annotated(result, False), value, cfg["unit"], shown_status, conf,
                                    result["angle"], source_name, span)
            b2.download_button("Save result card", card, file_name="gauge_reading.png", mime="image/png",
                               width="stretch")

    with st.expander(f"How it was read — {len(result['stages'])} stages"):
        stages = list(result["stages"].items())
        cols = st.columns(len(stages), gap="small")
        for col, (name, img) in zip(cols, stages):
            number = name.split(".")[0]
            col.image(img, channels="BGR" if img.ndim == 3 else "RGB", width="stretch")
            col.markdown(f'<div class="gd-stage"><b>{number}</b> {STAGE_NOTES.get(number, name)}</div>',
                         unsafe_allow_html=True)
        st.caption("Hover a stage and press the expand icon to see it full size.")

    with st.expander("Explain this reading"):
        steps = explain_reading(result, value, cfg["unit"], status, cfg["safe_low"], cfg["safe_high"], cfg["margin"])
        st.markdown('<div class="gd-explain"><ol>' + "".join(f"<li>{s}</li>" for s in steps) + "</ol></div>",
                    unsafe_allow_html=True)


# ------------------------------------------------------------------ view: batch
def batch_page(cfg):
    ss = st.session_state
    label("Batch · read many photos at once")
    st.markdown("Upload photos of the **same kind of gauge**. They all use the calibration in the sidebar"
                + (" (or OCR on each photo)." if cfg["auto"] else "."))
    files = st.file_uploader("Gauge photos", type=["jpg", "jpeg", "png", "webp", "bmp"], accept_multiple_files=True)
    if files and st.button(f"Read {len(files)} photo{'s' if len(files) > 1 else ''}", type="primary"):
        bar = st.progress(0.0)
        df = read_batch(files, cfg["settings"], cfg["calibration"], cfg["auto"], cfg["safe_low"],
                        cfg["safe_high"], cfg["margin"], cfg["min_conf"],
                        progress=lambda i, n, name: bar.progress(i / n, text=f"{i}/{n} · {name}"))
        bar.empty()
        df.insert(3, "unit", cfg["unit"])
        ss.batch_df = df
        for row in df.itertuples():
            if row.status in ("GREEN", "AMBER", "RED"):  # trusted readings only
                history.add_reading(row.file, row.reading, cfg["unit"], row.status, row.confidence, row.needle_angle)

    df = ss.get("batch_df")
    if df is None:
        return
    found = df["reading"].notna().sum()
    st.markdown(details_html([("Photos", str(len(df))), ("Read", str(found)),
                              ("Out of range", str((df["status"] == "RED").sum()))]), unsafe_allow_html=True)
    st.dataframe(df, hide_index=True, width="stretch", row_height=70, column_config={
        "photo": st.column_config.ImageColumn("photo", width="small"),
        "reading": st.column_config.NumberColumn("reading", format="%.3g"),
        "confidence": st.column_config.ProgressColumn("confidence", min_value=0, max_value=1, format="%.2f"),
        "message": st.column_config.TextColumn("notes", width="medium")})
    st.download_button("Download results (.csv)", df.drop(columns=["photo"]).to_csv(index=False),
                       file_name="gauge_batch_results.csv", mime="text/csv")


# ------------------------------------------------------------------ view: history
def history_page(cfg):
    label("History · this session")
    df = history.history_frame()
    if df.empty:
        st.markdown('<div class="gd-note">No readings yet. Every reading you take (sample, upload, camera, batch, '
                    'live) is listed here until you close the tab.</div>', unsafe_allow_html=True)
        return
    units = [u for u in df["unit"].unique()]
    if len(units) > 1:
        unit = st.segmented_control("Unit", units, default=units[-1], key="history_unit")
        shown = df[df["unit"] == (unit or units[-1])].reset_index(drop=True)
    else:
        shown = df
    st.altair_chart(history.trend_chart(shown, cfg["safe_low"], cfg["safe_high"]), width="stretch")
    st.caption("Shaded band = the current safe range in the sidebar.")

    st.dataframe(df.iloc[::-1], hide_index=True, width="stretch", column_config={
        "confidence": st.column_config.ProgressColumn("confidence", min_value=0, max_value=1, format="%.2f")})
    c1, c2 = st.columns([1, 1])
    c1.download_button("Download history (.csv)", df.to_csv(index=False), file_name="gauge_history.csv",
                       mime="text/csv", width="stretch")
    if c2.button("Clear history", width="stretch"):
        history.clear()
        st.rerun()

    red = history.red_events(df)
    label(f"Alerts · {len(red)} out-of-range event{'s' if len(red) != 1 else ''}")
    if red.empty:
        st.caption("None: a new row appears here each time a reading moves out of the safe range.")
    else:
        st.dataframe(red.iloc[::-1], hide_index=True, width="stretch")


# ------------------------------------------------------------------ main
def main():
    init_state()
    apply_pending()
    note = "Hough circles · Canny edges · Hough lines<br>no deep learning"
    masthead(note)

    views = ["Read a gauge", "Batch", "History", "Live camera"]
    keep_selected("view", "Read a gauge")
    st.segmented_control("View", views, key="view", label_visibility="collapsed")
    cfg = sidebar()

    view = st.session_state.view
    if view == "Batch":
        batch_page(cfg)
    elif view == "History":
        history_page(cfg)
    elif view == "Live camera":
        from gauge_app.live import live_page
        live_page(cfg)
    else:
        read_page(cfg)


main()
