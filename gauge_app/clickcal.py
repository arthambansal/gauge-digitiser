"""
clickcal.py - click-to-calibrate: click the first and last tick of the scale on the image.

Each click is turned into an angle with the SAME function the pipeline uses for the
needle (utils.angle_of_point, measured from the detected pivot):
    first click  -> start angle of the scale (where the minimum value is)
    second click -> end angle; sweep = (end - start) mod 360, going clockwise
The scale's min / max VALUES are still typed in the sidebar - a click gives a
position, not a number.
"""

import cv2
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates

from gauge_digitizer.utils import angle_of_point, draw_angle_grid, point_at_angle
from gauge_app.theme import BGR


def _state():
    if "clickcal" not in st.session_state:
        st.session_state.clickcal = {"active": False, "first": None, "last_click": None}
    return st.session_state.clickcal


def start():
    st.session_state.clickcal = {"active": True, "first": None, "last_click": None}


def cancel():
    st.session_state.clickcal = {"active": False, "first": None, "last_click": None}


def is_active():
    return _state()["active"]


def calibration_canvas(result):
    """
    Show the clickable image. Returns (min_angle, sweep) once both ticks are clicked, else None.
    """
    state = _state()
    cx, cy, r = result["dial"]
    canvas = draw_angle_grid(result["colour"], result["dial"])
    if state["first"] is not None:  # show where the first click landed
        x, y = point_at_angle(cx, cy, state["first"], 0.9 * r)
        cv2.line(canvas, (int(cx), int(cy)), (int(x), int(y)), BGR["oxblood"], 3, cv2.LINE_AA)
        cv2.circle(canvas, (int(x), int(y)), 9, BGR["oxblood"], 3, cv2.LINE_AA)

    step = "1 of 2 — click the FIRST tick of the scale (the minimum, e.g. 0)" if state["first"] is None \
        else "2 of 2 — now click the LAST tick of the scale (the maximum)"
    st.markdown(f'<p class="gd-label">Calibrate · step {step}</p>', unsafe_allow_html=True)
    click = streamlit_image_coordinates(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB), width="stretch",
                                        key="clickcal_canvas", cursor="crosshair")
    if st.button("Cancel calibration", key="clickcal_cancel"):
        cancel()
        st.rerun()

    # The component returns the last click on every re-run: only act on a NEW click
    if not click or click.get("unix_time") == state["last_click"]:
        return None
    state["last_click"] = click.get("unix_time")
    scale = canvas.shape[1] / click["width"]  # displayed size -> working-image pixels
    angle = angle_of_point(cx, cy, click["x"] * scale, click["y"] * scale)
    if state["first"] is None:
        state["first"] = angle
        st.rerun()
    first = state["first"]
    cancel()
    return first, (angle - first) % 360.0
