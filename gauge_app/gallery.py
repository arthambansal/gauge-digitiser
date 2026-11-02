"""
gallery.py - built-in sample gauges, so visitors can try the app without a photo.

Two sources, each with a labels CSV giving the true value and the scale:
  assets/gallery/gallery.csv : synthetic gauges from make_synthetic.py
  samples/labels.csv         : 12 real photos from Wikimedia Commons (see samples/SOURCES.md)
"""

import os

import cv2
import pandas as pd
import streamlit as st

SOURCES = [("assets/gallery", "gallery.csv", "Synthetic"), ("samples", "labels.csv", "Photo")]


@st.cache_data
def load_gallery():
    """All sample gauges as a list of dicts (path, title, unit, scale, true value...)."""
    items = []
    for folder, csv_name, kind in SOURCES:
        path = os.path.join(folder, csv_name)
        if not os.path.exists(path):
            continue
        for row in pd.read_csv(path).to_dict("records"):
            image_path = os.path.join(folder, row["filename"])
            if not os.path.exists(image_path):
                continue
            items.append({
                "id": image_path, "path": image_path, "kind": kind,
                "title": row.get("title") or row["filename"], "unit": row.get("unit") or "",
                "note": row.get("note") if isinstance(row.get("note"), str) else "",
                "true_value": float(row["true_value"]),
                "calibration": {"scale_min": float(row["scale_min"]), "scale_max": float(row["scale_max"]),
                                "min_angle": float(row["min_angle"]), "sweep": float(row["sweep"]),
                                "unit": row.get("unit") or ""},
            })
    return items


@st.cache_data
def thumbnail(path, width=320):
    """Small RGB copy for the gallery grid, centre-cropped to 4:3 so all cards line up."""
    img = cv2.imread(path)
    h, w = img.shape[:2]
    if w / h > 4 / 3:   # too wide: trim the sides
        new_w = int(h * 4 / 3)
        img = img[:, (w - new_w) // 2:(w - new_w) // 2 + new_w]
    else:               # too tall: trim top and bottom
        new_h = int(w * 3 / 4)
        img = img[(h - new_h) // 2:(h - new_h) // 2 + new_h]
    h, w = img.shape[:2]
    img = cv2.resize(img, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def gallery_grid(items, selected_id, columns=4):
    """Thumbnail cards with a button each. Returns the item whose button was clicked, else None."""
    clicked = None
    for start in range(0, len(items), columns):
        cols = st.columns(columns, gap="medium")
        for col, item in zip(cols, items[start:start + columns]):
            with col:
                st.image(thumbnail(item["path"]), width="stretch")
                st.markdown(f'<div class="gd-card-title">{item["title"]}</div>'
                            f'<div class="gd-card-note">{item["kind"]} · {item["note"] or "&nbsp;"}</div>',
                            unsafe_allow_html=True)
                is_current = item["id"] == selected_id
                if st.button("Showing" if is_current else "Read this gauge", key="pick|" + item["id"],
                             disabled=is_current, width="stretch"):
                    clicked = item
    return clicked
