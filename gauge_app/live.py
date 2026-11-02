"""
live.py - continuous live reading from a camera.

Two ways to get frames:

1. BROWSER CAMERA (works online, on phones, and locally). The visitor's browser captures the
   camera and streams it to the server over WebRTC (streamlit-webrtc). For every frame the server
   runs the same read_gauge() pipeline, draws the dial, pivot and needle on the frame, and sends
   the annotated video back, so you see the detected lines live. The readout beside it updates
   from the same readings.

2. THIS COMPUTER / VIDEO FILE (local only). An OpenCV capture loop on a camera attached to the
   machine running the app, or a video file such as synthetic/sweep.mp4 for demos.

A deployed server has no camera of its own, so (2) is hidden online; (1) is the one that works there.
"""

import threading
import time

import cv2
import streamlit as st

from gauge_digitizer.alerts import classify_reading
from gauge_digitizer.pipeline import read_gauge
from gauge_digitizer.utils import AMBER, GREEN, GREY, RED, ReadingSmoother, draw_overlay
from gauge_app import history
from gauge_app.readout import details_html, readout_html
from gauge_app.theme import BGR, label

try:  # optional: without these packages the app still works, just without the browser camera
    import av
    from streamlit_webrtc import VideoProcessorBase, WebRtcMode, webrtc_streamer
    WEBRTC_OK = True
except ImportError:
    WEBRTC_OK = False
    VideoProcessorBase = object

STATUS_BGR = {"GREEN": GREEN, "AMBER": AMBER, "RED": RED, "LOW": GREY, None: GREY}
MIN_INTERVAL = 0.10          # run the pipeline at most ~10 times a second; in between, redraw the last result
# A STUN server lets the browser and server find each other through home routers. Some strict networks
# (campus / corporate) block this kind of traffic and would need a TURN relay, which this app doesn't have.
RTC_CONFIG = {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
CAMERA_CONSTRAINTS = {"video": {"width": {"ideal": 640}, "height": {"ideal": 480}, "frameRate": {"ideal": 24},
                                "facingMode": {"ideal": "environment"}},  # phones: prefer the back camera
                      "audio": False}


class GaugeVideoProcessor(VideoProcessorBase):
    """
    Runs in a background thread inside streamlit-webrtc. recv() is called for the latest frame
    (older frames are dropped if we are slow, so latency doesn't build up).
    The page's main thread reads the results through snapshot() and sends settings via configure().
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.cfg = None
        self.smoother = ReadingSmoother(7)
        self.last_draw = None          # what to draw on frames between pipeline runs
        self.last_run = 0.0
        self.reads = 0
        self.t0 = time.time()
        self.snap = {"seq": 0, "value": None, "raw": None, "status": None, "confidence": 0.0, "angle": None, "rate": 0.0}

    # ---- called from the page (main thread)
    def configure(self, cfg):
        with self.lock:
            self.cfg = cfg
            if self.smoother.values.maxlen != cfg["window"]:
                self.smoother = ReadingSmoother(cfg["window"])

    def snapshot(self):
        with self.lock:
            return dict(self.snap)

    # ---- called for every video frame (worker thread)
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        h, w = img.shape[:2]
        if w != 640:                    # the pipeline works at 640 px wide; keep the output size constant too
            img = cv2.resize(img, (640, int(round(h * 640 / w))), interpolation=cv2.INTER_AREA)
        with self.lock:
            cfg = self.cfg
        if cfg is not None and time.time() - self.last_run >= MIN_INTERVAL:
            self._read(img, cfg)
        if self.last_draw is not None:
            d = self.last_draw
            img = draw_overlay(img, dial=d["dial"], needle=d["needle"], text=d["text"], colour=d["colour"],
                               rim=d["rim"], circle_colour=BGR["brass"], needle_colour=BGR["oxblood"])
        return av.VideoFrame.from_ndarray(img, format="bgr24")

    def _read(self, img, cfg):
        res = read_gauge(img, cfg["settings"], cfg["calibration"], False)
        self.last_run = time.time()
        self.reads += 1
        trusted = res["value"] is not None and res["confidence"] >= cfg["min_conf"]
        with self.lock:
            value = self.smoother.add(res["value"] if trusted else None)
            status = classify_reading(value, cfg["safe_low"], cfg["safe_high"], cfg["margin"])
            shown = "LOW" if (res["value"] is not None and not trusted) else status
            self.snap = {"seq": self.snap["seq"] + 1, "value": value, "raw": res["value"], "status": shown,
                         "confidence": res["confidence"], "angle": res["angle"],
                         "rate": self.reads / max(self.last_run - self.t0, 1e-6)}
        if res["dial"] is None:
            self.last_draw = None
            return
        text = "no needle" if res["needle"] is None else (f"{value:.1f} {cfg['unit']}".strip() if value is not None else "...")
        self.last_draw = {"dial": res["dial"], "rim": res["rim"], "needle": res["needle"], "text": text,
                          "colour": STATUS_BGR[shown]}


def _panel_html(snap, cfg):
    html = readout_html(snap["value"], cfg["unit"], snap["status"], cfg["scale_min"], cfg["scale_max"],
                        cfg["safe_low"], cfg["safe_high"], cfg["margin"], live=True)
    raw = "–" if snap["raw"] is None else f"{snap['raw']:.2f}"
    rows = [("Readings per second", f"{snap['rate']:.1f}"), ("This frame (raw)", raw),
            ("Confidence", f"{snap['confidence'] * 100:.0f}%")]
    return html + details_html(rows)


def browser_live(cfg):
    st.markdown("Allow the camera when your browser asks, then press **Start camera**. Hold the gauge so it fills most of "
                "the picture. The **brass circle** is the dial the app found and the **red line** is the needle it is "
                "reading. The number is the median of the last few readings, so one bad frame doesn't make it jump.")
    window = st.slider("Smoothing (frames)", 1, 30, 7, key="live_window")
    left, right = st.container(key="livehero").columns([7, 4], gap="large")
    with left:
        with st.container(key="livecam"):
            ctx = webrtc_streamer(
                key="gauge-live", mode=WebRtcMode.SENDRECV, rtc_configuration=RTC_CONFIG,
                media_stream_constraints=CAMERA_CONSTRAINTS, video_processor_factory=GaugeVideoProcessor,
                async_processing=True, video_html_attrs={"style": {"width": "100%", "border-radius": "6px"},
                                                         "controls": False, "autoPlay": True, "muted": True},
                translations={"start": "Start camera", "stop": "Stop", "select_device": "Select camera",
                              "device_ask_permission": "Allow camera access", "device_not_available": "No camera found"})
    panel = right.empty()
    cfg = {**cfg, "window": window}

    if not ctx.state.playing:
        panel.markdown(readout_html(None, cfg["unit"], None, cfg["scale_min"], cfg["scale_max"], cfg["safe_low"],
                                    cfg["safe_high"], cfg["margin"], live=True)
                       + details_html([("Status", "waiting for the camera")],
                                      "Press <b>Start camera</b>. If nothing happens, check that the browser is allowed "
                                      "to use the camera, and that no other app is using it."), unsafe_allow_html=True)
        return

    shown_seq, last_logged = -1, 0.0
    while ctx.state.playing:
        proc = ctx.video_processor
        if proc is None:
            time.sleep(0.1)
            continue
        proc.configure(cfg)
        snap = proc.snapshot()
        if snap["seq"] != shown_seq:                     # only redraw the panel when there is a new reading
            shown_seq = snap["seq"]
            panel.markdown(_panel_html(snap, cfg), unsafe_allow_html=True)
            if snap["value"] is not None and snap["status"] in ("GREEN", "AMBER", "RED") and time.time() - last_logged > 1.0:
                last_logged = time.time()
                history.add_reading("live camera", snap["value"], cfg["unit"], snap["status"], snap["confidence"],
                                    snap["angle"] or 0.0)
        time.sleep(0.12)


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
        if WEBRTC_OK:
            browser_live(cfg)
        else:
            st.warning("The browser camera needs the `streamlit-webrtc` package (`pip install streamlit-webrtc`). "
                       "Use **Read a gauge → Camera** for single photos in the meantime.")
    else:
        local_loop(cfg)
