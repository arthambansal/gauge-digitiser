"""
live.py - continuous live reading from a camera, with the detected lines drawn on the live video.

Two sources:

1. BROWSER CAMERA (works online, on phones, and locally). gauge_app/livecam.py shows the camera in the
   browser and sends small snapshots to the server; every snapshot is read by the same read_gauge()
   pipeline; the dial circle, needle and reading come back and are drawn on top of the video, and the
   dial readout beside it updates from the same reading.

2. THIS COMPUTER / VIDEO FILE (local only). An OpenCV capture loop on a camera attached to the machine
   running the app, or a video file such as synthetic/sweep.mp4 for demos.

A deployed server has no camera of its own, so (2) is hidden online.
"""

import base64
import time

import cv2
import numpy as np
import streamlit as st

from gauge_digitizer.alerts import classify_reading
from gauge_digitizer.pipeline import read_gauge
from gauge_digitizer.utils import ReadingSmoother, draw_overlay
from gauge_app import history
from gauge_app.livecam import camera
from gauge_app.readout import details_html, readout_html
from gauge_app.theme import BGR, STATUS_COLOURS, label


def _on_running():
    """The browser started or stopped the camera."""
    ss = st.session_state
    state = ss.get("gauge_cam") or {}
    if not state.get("running"):
        ss.live_overlay, ss.live_snap = None, None
        if "live_smoother" in ss:
            ss.live_smoother.reset()


def _on_frame():
    """A new camera snapshot arrived: run the pipeline on it and store what to draw and show."""
    ss = st.session_state
    cfg = ss.get("live_cfg")
    frame = (ss.get("gauge_cam") or {}).get("frame")
    if not cfg or not frame:
        return
    t0 = time.time()
    img = cv2.imdecode(np.frombuffer(base64.b64decode(frame["jpeg"]), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        ss.live_overlay = {"ack": frame["seq"]}
        return
    res = read_gauge(img, cfg["settings"], cfg["calibration"], False)

    smoother = ss.get("live_smoother")
    if smoother is None or smoother.values.maxlen != cfg["window"]:
        smoother = ss.live_smoother = ReadingSmoother(cfg["window"])
    trusted = res["value"] is not None and res["confidence"] >= cfg["min_conf"]
    value = smoother.add(res["value"] if trusted else None)
    status = classify_reading(value, cfg["safe_low"], cfg["safe_high"], cfg["margin"])
    shown = "LOW" if (res["value"] is not None and not trusted) else status

    overlay = {"ack": frame["seq"], "w": frame["w"], "colour": STATUS_COLOURS[shown]}
    if res["dial"] is not None:
        overlay["dial"] = [round(float(v), 1) for v in res["dial"]]
        overlay["rim"] = [round(float(v), 1) for v in res["rim"]]
        if res["needle"] is not None:
            overlay["tip"] = [round(float(v), 1) for v in res["needle"]["tip"]]
            overlay["text"] = f"{value:.1f} {cfg['unit']}".strip() if value is not None else "..."
        else:
            overlay["text"] = "no needle"
    ss.live_overlay = overlay
    ss.live_snap = {"value": value, "raw": res["value"], "status": shown, "confidence": res["confidence"],
                    "angle": res["angle"], "ms": (time.time() - t0) * 1000}
    last = ss.get("live_last_logged", 0.0)
    if value is not None and shown in ("GREEN", "AMBER", "RED") and time.time() - last > 1.0:
        ss.live_last_logged = time.time()
        history.add_reading("live camera", value, cfg["unit"], shown, res["confidence"], res["angle"] or 0.0)


@st.fragment
def _browser_fragment():
    """Only this part of the page reruns for each camera snapshot, so the rest of the app stays still."""
    ss = st.session_state
    cfg = ss.live_cfg
    left, right = st.container(key="livehero").columns([7, 4], gap="large")
    with left:
        with st.container(key="livecam"):
            state = camera(key="gauge_cam", data=ss.get("live_overlay"), default={"frame": None, "running": False},
                           on_frame_change=_on_frame, on_running_change=_on_running)
    snap = ss.get("live_snap")
    if state.running and snap:
        html = readout_html(snap["value"], cfg["unit"], snap["status"], cfg["scale_min"], cfg["scale_max"],
                            cfg["safe_low"], cfg["safe_high"], cfg["margin"], live=True)
        raw = "–" if snap["raw"] is None else f"{snap['raw']:.2f}"
        html += details_html([("Analysis time per frame", f"{snap['ms']:.0f} ms"), ("This frame (raw)", raw),
                              ("Confidence", f"{snap['confidence'] * 100:.0f}%")])
    else:
        html = (readout_html(None, cfg["unit"], None, cfg["scale_min"], cfg["scale_max"], cfg["safe_low"],
                             cfg["safe_high"], cfg["margin"], live=True)
                + details_html([("Status", "camera running…" if state.running else "waiting for the camera")],
                               "" if state.running else "Press <b>Start camera</b> and allow camera access when your "
                               "browser asks."))
    right.markdown(html, unsafe_allow_html=True)


def browser_live(cfg):
    st.markdown("Press **Start camera** and allow access when your browser asks. Hold the gauge so it fills most of the "
                "picture. The **brass circle** is the dial the app found and the **red line** is the needle it is "
                "reading, drawn live on your video. The number is the median of the last few readings, so one bad "
                "frame doesn't make it jump. Each snapshot is analysed in memory and not stored.")
    window = st.slider("Smoothing (frames)", 1, 30, 7, key="live_window")
    st.session_state.live_cfg = {**cfg, "window": window}
    _browser_fragment()


def local_loop(cfg):
    """OpenCV capture loop: a camera attached to this computer, or a video file (local only)."""
    st.markdown("Reads a camera attached to the computer running the app, or a video file such as "
                "`synthetic/sweep.mp4` (a needle sweeping 0 → 100 → 0, handy for demos).")
    c1, c2, c3 = st.columns([2, 2, 1])
    source = c1.text_input("Camera index or video file", "0", help="0 = built-in webcam, 1 = external camera")
    window = c2.slider("Smoothing (frames)", 1, 30, 7, key="local_window")
    c3.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
    running = c3.toggle("Start", key="live_on")

    left, right = st.columns([7, 4], gap="large")
    frame_ph, readout_ph = left.empty(), right.empty()
    if not running:
        frame_ph.info("Press Start. On macOS, allow camera access for your terminal or VS Code the first time "
                      "(System Settings → Privacy & Security → Camera).")
        return

    is_file = not source.strip().isdigit()
    cap = cv2.VideoCapture(source.strip() if is_file else int(source))
    if not cap.isOpened():
        frame_ph.error(f"Could not open camera '{source}'.")
        return

    smoother = ReadingSmoother(window)
    frames, t0 = 0, time.time()
    try:
        while True:
            ok, frame = cap.read()
            if not ok and is_file:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop demo videos
                continue
            if not ok:
                frame_ph.error("The camera stopped sending frames.")
                break
            if is_file:
                time.sleep(1 / 15)  # play files at roughly real speed

            res = read_gauge(frame, cfg["settings"], cfg["calibration"], False)
            trusted = res["value"] is not None and res["confidence"] >= cfg["min_conf"]
            value = smoother.add(res["value"] if trusted else None)
            status = classify_reading(value, cfg["safe_low"], cfg["safe_high"], cfg["margin"])
            if value is not None and frames % 15 == 0:  # about once a second into the history
                history.add_reading("live camera", value, cfg["unit"], status, res["confidence"], res["angle"] or 0)

            frames += 1
            shown = res["overlay"] if res["needle"] is None else draw_overlay(
                res["colour"], res["dial"], res["needle"], rim=res["rim"],
                circle_colour=BGR["brass"], needle_colour=BGR["oxblood"])
            frame_ph.image(shown, channels="BGR", width="stretch")
            # One markdown element updated in place every frame, so the needle glides instead of re-sweeping
            raw = "–" if res["value"] is None else f"{res['value']:.2f}"
            readout_ph.markdown(
                readout_html(value, cfg["unit"], status, cfg["scale_min"], cfg["scale_max"], cfg["safe_low"],
                             cfg["safe_high"], cfg["margin"], live=True)
                + details_html([("Frames per second", f"{frames / (time.time() - t0):.1f}"),
                                ("This frame (raw)", raw), ("Confidence", f"{res['confidence'] * 100:.0f}%")]),
                unsafe_allow_html=True)
    finally:
        cap.release()


def live_page(cfg):
    label("Live camera")
    on_cloud = cfg.get("on_cloud", False)
    choice = "Browser camera"
    if not on_cloud:
        choice = st.segmented_control("Camera source", ["Browser camera", "This computer / video file"],
                                      default="Browser camera", key="live_source",
                                      label_visibility="collapsed") or "Browser camera"
    if choice == "Browser camera":
        browser_live(cfg)
    else:
        local_loop(cfg)
