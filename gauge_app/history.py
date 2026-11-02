"""
history.py - every reading taken in this browser session, for the History tab.

Stored in st.session_state, so each visitor has their own history (on a shared
online server, a file on disk would mix everyone's readings together). It
disappears when the tab is closed; the CSV download is how to keep it.
"""

from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from gauge_app.theme import STATUS_COLOURS

COLUMNS = ["time", "source", "reading", "unit", "status", "confidence", "needle_angle"]


def _rows():
    if "history" not in st.session_state:
        st.session_state.history = []
    return st.session_state.history


def add_reading(source, value, unit, status, confidence, angle):
    """
    Record a reading. Streamlit re-runs the whole script on every click, so the same
    image would otherwise be logged again and again: we skip a row identical to the
    previous one (same source and same value).
    """
    rows = _rows()
    if value is None:
        return False
    value = round(float(value), 4)
    if rows and rows[-1]["source"] == source and rows[-1]["reading"] == value and rows[-1]["status"] == status:
        return False
    rows.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "source": source,
                 "reading": value, "unit": unit, "status": status,
                 "confidence": round(float(confidence), 3), "needle_angle": round(float(angle), 2)})
    return True


def history_frame():
    return pd.DataFrame(_rows(), columns=COLUMNS)


def clear():
    st.session_state.history = []


def red_events(df):
    """Rows where the status CHANGED into RED (one row per breach, as in alerts.AlertLogger)."""
    if df.empty:
        return df
    previous = df["status"].shift(1)
    return df[(df["status"] == "RED") & (previous != "RED")]


def trend_chart(df, safe_low, safe_high):
    """Reading over time with the safe band shaded and points coloured by status."""
    data = df.reset_index().rename(columns={"index": "n"})
    data["n"] = data["n"] + 1
    band = alt.Chart(pd.DataFrame({"lo": [safe_low], "hi": [safe_high]})).mark_rect(
        color=STATUS_COLOURS["GREEN"], opacity=.12).encode(y="lo:Q", y2="hi:Q")
    line = alt.Chart(data).mark_line(color="#7A1F1F", strokeWidth=1.6).encode(
        x=alt.X("n:Q", title="reading #", axis=alt.Axis(tickMinStep=1)), y=alt.Y("reading:Q", title=None))
    points = alt.Chart(data).mark_circle(size=70, opacity=1).encode(
        x="n:Q", y="reading:Q",
        color=alt.Color("status:N", legend=None, scale=alt.Scale(
            domain=["GREEN", "AMBER", "RED"],
            range=[STATUS_COLOURS["GREEN"], STATUS_COLOURS["AMBER"], STATUS_COLOURS["RED"]])),
        tooltip=["time", "source", "reading", "unit", "status", "confidence"])
    return (band + line + points).properties(height=260).configure_view(strokeWidth=0).configure_axis(
        labelFont="DM Mono", titleFont="DM Sans", titleColor="#6E6352", titleFontWeight="normal",
        gridColor="#E2D3B5", domainColor="#CDB98F", labelColor="#6E6352")
