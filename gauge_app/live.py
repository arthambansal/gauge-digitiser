"""
live.py - continuous live reading from a camera attached to THIS computer.

Uses an OpenCV capture loop, so it only works when the app runs locally (on a
laptop with a webcam). On the online version the server has no camera; there the
'Camera' source on the Read page (the browser takes a photo) is used instead.
"""

import time

import cv2
import streamlit as st

from gauge_digitizer.alerts import classify_reading
from gauge_digitizer.pipeline import read_gauge
from gauge_digitizer.utils import ReadingSmoother, draw_overlay
from gauge_app import history
from gauge_app.readout import details_html, readout_html
from gauge_app.theme import BGR, label


def live_page(cfg):
    label("Live camera · runs on this computer only")
    st.markdown("Continuous reading from a webcam attached to the computer running the app. "
                "The reading is the **median of the last few frames**, so one bad frame does not make it jump.")
    c1, c2, c3 = st.columns([2, 2, 1])
    source = c1.text_input("Camera", "0", help="0 = built-in webcam, 1 = external camera, "
                                                "or a video file such as synthetic/sweep.mp4")
    window = c2.slider("Smoothing (frames)", 1, 30, 7)
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
            with readout_ph.container():
                st.markdown(readout_html(value, cfg["unit"], status, cfg["scale_min"], cfg["scale_max"],
                                         cfg["safe_low"], cfg["safe_high"], cfg["margin"]), unsafe_allow_html=True)
                raw = "–" if res["value"] is None else f"{res['value']:.2f}"
                st.markdown(details_html([("Frames per second", f"{frames / (time.time() - t0):.1f}"),
                                          ("This frame (raw)", raw),
                                          ("Confidence", f"{res['confidence'] * 100:.0f}%")]),
                            unsafe_allow_html=True)
    finally:
        cap.release()
