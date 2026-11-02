# Gauge Digitizer

Reads an analogue dial gauge (pressure gauge, thermometer, tyre gauge…) from a photo or camera using
**classical computer vision only** (no deep learning), turns the needle position into a number, and flags it
green / amber / red against a safe range. Mini project for Foundations of Computer Vision (CSE 3176), MIT Manipal.

```
image → preprocess → Hough circle (dial) → hub pivot → Canny + Hough lines (needle) → atan2 angle
      → calibration (manual, click-to-calibrate, or Tesseract OCR of the printed scale) → value
      → GREEN / AMBER / RED (+ per-session history and alerts)
```

Non-technical guide with screenshots: **`FEATURES_GUIDE.docx`**. Viva preparation: **`VIVA_NOTES.md`**.

## Features

- **Read a gauge** from the built-in **sample gallery** (6 synthetic + 12 real photos, with true values),
  an **uploaded photo**, or a **camera snapshot** (works online and on phones).
- **Instrument readout**: big reading, status lamp, scale bar showing the alarm zones and a pointer, confidence.
- **Annotated / original / side-by-side** image views.
- **Calibration**: manual fields, an **angle grid** overlay, **click-to-calibrate** (click the first and last tick),
  **automatic OCR** calibration, and saving/loading calibrations (in the session, or as a JSON file).
- **Alarm limits**: safe range, amber margin, and a minimum confidence below which readings never raise alarms.
- **How it was read**: a filmstrip of the pipeline stages. **Explain this reading**: the same steps in words,
  with this image's numbers.
- **Result card**: a downloadable PNG of the annotated gauge with the reading, status and time.
- **Batch**: read many photos at once → table with thumbnails → CSV.
- **History**: every reading this session, a trend chart with the safe band, out-of-range events, CSV export.
- **Live camera** (local only): continuous webcam reading, median-smoothed.

## Project layout

| Path | What it is |
|---|---|
| `gauge_digitizer/` | **The computer vision.** `preprocess`, `dial` (Hough circles + hub candidates), `needle` (Canny + Hough lines, pivot choice, confidence), `calibrate` (manual + OCR), `alerts`, `utils`, `pipeline.read_gauge()` |
| `gauge_app/` | **The user interface only.** `theme` (CSS), `readout`, `gallery`, `clickcal`, `history`, `batch`, `card`, `explain`, `live` |
| `app.py` | Streamlit entry point: arranges the screen, calls `read_gauge()` |
| `.streamlit/config.toml` | Theme: colours and fonts (Fraunces, DM Sans, DM Mono) |
| `assets/` | Gallery images (`assets/gallery/` + `gallery.csv`), fonts for the result card (OFL), app icon |
| `samples/` | 12 labelled real photos (Wikimedia Commons; `SOURCES.md` = licences and how they were labelled) |
| `make_synthetic.py` | Synthetic gauges with known values; `--realistic` adds arcs, dual scales, dark faces; `--video` a demo clip |
| `evaluate.py` / `tune.py` | Accuracy measurement / parameter grid search → `results/` |
| `requirements.txt`, `packages.txt` | Python packages (pinned) and system packages (Tesseract) for deployment |

## Setup and run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
brew install tesseract              # optional: only for Automatic (OCR) calibration
streamlit run app.py                # http://localhost:8501
```
*Windows:* Tesseract from https://github.com/UB-Mannheim/tesseract/wiki (add it to PATH). *Linux:* `sudo apt install tesseract-ocr`.
Without Tesseract the app still works; Automatic mode is just disabled, with a message saying why.

Optional (testing / report numbers):
```bash
python make_synthetic.py --video       # synthetic/ test set + synthetic/sweep.mp4 for the live demo
python make_synthetic.py --realistic   # synthetic_realistic/ test set
python evaluate.py                     # → results/summary.csv
```
If you edit files in `gauge_digitizer/` or `gauge_app/` while Streamlit is running, **restart it**. It reloads
`app.py` but can keep old copies of imported modules.

## Demo script (about 3 minutes)

1. **Read a gauge → Sample gauges.** The default 0–100 psi gauge reads 76.1 (true 76.3). Point out the readout,
   the amber lamp ("near limit") and the scale bar.
2. Open **How it was read**: grey → blur → dial + hub → Canny edges → line candidates (green kept).
   Then **Explain this reading** for the arithmetic.
3. Pick **Flow meter (non-linear scale)** → switch the sidebar to **Automatic (OCR)**. It reads the printed numbers,
   detects an uneven scale ("OCR, non-linear") and gives 37.2 (true 36.5).
4. Pick **Fire-sprinkler gauge** (a real photo) → **Side by side**. Then **Click to calibrate** and click the 0 and
   300 ticks to show calibration from scratch.
5. Drag the **Safe range** so the reading turns red, then open **History**: the event is listed and can be exported.
6. **Live camera** (local): source `synthetic/sweep.mp4` → Start. The needle sweeps 0 → 100 and the lamp goes
   green → amber → red.

## Deploy to Streamlit Community Cloud

1. Create a GitHub repository and push this folder. `.gitignore` already leaves out the virtual environment, the
   regenerable `synthetic*/` folders (~63 MB), logs, and course documents (`*.docx` except the guide, `*.pdf`).
   ```bash
   git init && git add . && git commit -m "Gauge Digitizer"
   git branch -M main
   git remote add origin https://github.com/<you>/gauge-digitizer.git
   git push -u origin main
   ```
2. Go to https://share.streamlit.io → sign in with GitHub → **Create app** → **Deploy a public app from GitHub**.
3. Repository: your repo · Branch: `main` · Main file path: `app.py`.
4. **Advanced settings → Python version: 3.12** (all pinned packages have 3.12 wheels; this was checked).
5. **Deploy.** The first build takes a few minutes: `packages.txt` installs Tesseract, `requirements.txt` the Python packages.
6. Share the `…streamlit.app` URL.

### What works online, and what doesn't

| Feature | Online | On your own computer |
|---|---|---|
| Samples, upload, batch, history, result card, explain, click-to-calibrate | ✅ | ✅ |
| Camera **snapshot** (browser camera, phones included) | ✅ | ✅ |
| Automatic (OCR) calibration | ✅ (Tesseract from `packages.txt`) | ✅ if Tesseract is installed |
| **Live camera** (continuous) | ❌ hidden: the server has no camera | ✅ |
| History, saved calibrations | per browser tab, gone when closed (download CSV / JSON to keep) | same |

**Why snapshots online instead of live video.** A deployed Streamlit app runs on a remote server, so
`cv2.VideoCapture(0)` there finds no camera. Live video from the visitor's browser would need `streamlit-webrtc`.
That adds heavy native dependencies (`aiortc`, `av`) and often fails behind firewalls without a TURN server.
`st.camera_input` (one photo at a time) works reliably everywhere, including phones. The local live loop is kept
for laptop demos.

## Measured results (`python evaluate.py`)

Error = |reading − truth| as a percentage of full scale (%FS).
*Manual* = linear min/max calibration. *Auto* = OCR calibration, given the manual min/max as a units check
(as in the app). Auto is scored only where OCR succeeded; otherwise the app falls back to manual.

### Summary

| | Synthetic (140) | Realistic synthetic (140) | Real photos (12) |
|---|---|---|---|
| Needle found | 100% | 100% | **100%** |
| Mean needle-angle error | 0.37° | 0.51° | 4.3° |
| Manual: mean / max error | 0.14 / 0.49 %FS | 0.20 / 1.93 %FS | **1.56 / 3.41 %FS** |
| OCR calibration succeeded | 96% | 78% | 17% (2 of 12) |
| Auto: mean / max error | 1.08 / 20.6 %FS | 0.53 / 6.1 %FS | 2.2 / 4.3 %FS |
| Time per frame (no OCR) | 7 ms | 7 ms | 36 ms (larger photos) |

Manual errors on the two synthetic sets are scored on linear gauges only, because a 2-point linear calibration
cannot describe the square-root gauge. *Realistic synthetic* = `make_synthetic.py --realistic` (scale arcs,
second scales, dark faces, short needles, scales starting anywhere from 30° to 130°).

### Synthetic set by condition

| Condition | Needle found | Mean angle error | Manual: mean / max %FS | OCR success | Auto: mean / max %FS |
|---|---|---|---|---|---|
| clean | 100% | 0.32° | 0.13 / 0.44 | 100% | 2.24 / 20.60 |
| noise | 100% | 0.36° | 0.14 / 0.29 | 100% | 0.53 / 2.53 |
| blur | 100% | 0.28° | 0.11 / 0.28 | 80% | 1.29 / 14.43 |
| dark | 100% | 0.33° | 0.12 / 0.26 | 100% | 0.56 / 5.71 |
| uneven light | 100% | 0.35° | 0.14 / 0.31 | 100% | 1.60 / 17.00 |
| glare | 100% | 0.34° | 0.12 / 0.28 | 100% | 0.70 / 5.52 |
| tilt (10–20°) | 100% | 0.63° | 0.23 / 0.49 | 95% | 0.66 / 3.53 |

On linear gauges, OCR calibration averages 0.15 %FS error. On the square-root gauge it averages 3.8 %FS
(median 1.9). The remaining large errors there come from OCR misreads that still fit the increasing order
(e.g. "50" read as "90"), and from straight-line interpolation between sparse labels on a curved scale.

### Real photos: 12 Wikimedia Commons photos (`samples/`, sources in `samples/SOURCES.md`)

The labels were read by eye, and each has its own uncertainty of 0.8–3.3 %FS (see `samples/labels.csv`).
Errors smaller than that uncertainty are not meaningful. Seven of the twelve gauges are at rest (zero).

| Photo | Truth | Manual reading | Manual error %FS | Label uncertainty %FS | Note |
|---|---|---|---|---|---|
| sprinkler 0–300 psi | 110 | 109.2 | 0.27 | 1.0 | outdoor, two scales |
| USG 0–4000 psi | 850 | 860.9 | 0.27 | 0.8 | dial cut off by frame; OCR: 844.1 (0.15 %FS) |
| Budenberg 0–30 | 1.0 | 1.12 | 0.41 | 3.3 | old, eccentric gauge |
| WIKA 0–60 MPa | 0 | 0.38 | 0.64 | 0.8 | scale starts upper-left |
| manometer 0–15 | 0.4 | 0.29 | 0.73 | 2.7 | |
| wall gauge 0–60 psi | 22 | 21.2 | 1.38 | 2.5 | |
| WIKA 0–4000 psi | 0 | 55.5 | 1.39 | 1.5 | |
| Maximator 0–2500 bar | 870 | 920.9 | 2.04 | 1.0 | strongly tilted view |
| VDO 0–10 bar | 0 | 0.22 | 2.20 | 2.0 | white needle on black; found by the relaxed second pass |
| pool gauge 0–3 bar | 0 | 0.08 | 2.79 | 1.7 | |
| tyre gauge 0.5–4.5 bar | 0.4 | 0.53 | 3.25 | 2.5 | short red needle; OCR: 0.57 (4.3 %FS) |
| WIKA Minicheck 0–15 psi | 0 | 0.51 | 3.41 | 3.3 | bezel cut off by frame |

### How accuracy was improved (and measured)

Each change was kept only if it helped on the real photos without hurting the synthetic sets.

| Change | Why | Effect |
|---|---|---|
| **Needle pivot from the hub cap** (small Hough circle) | Circle centre ≠ pivot under tilt or a cut-off bezel | Synthetic worst angle error 8.3° → 1.3° |
| **Choose the hub the needle line passes through** | The strongest small circle was sometimes a logo letter | Budenberg 12.3° → 1.1° |
| **Needle "solidity" score** (25th percentile of contrast) | A line through text beat a short, solid needle | Tyre gauge 79 %FS → 3.3 %FS |
| **Wider hub window + relaxed second pass** | Some short needles or off-centre hubs were missed | Real needles found 10/12 → 12/12 |
| **OCR: remove the scale arc** before grouping digits | On real gauges, numbers touching the arc were lost | Candidate numbers per dial 3 → 7–25 |
| **OCR: one ring only + units check + dead-zone fix** | Dual scales gave calibrations in the wrong units | Realistic-synthetic OCR max error 1,919 → 6.1 %FS |
| **Reading confidence** | Low-confidence frames should not trigger alerts | Safety net (see limitations) |

**Parameter tuning (`tune.py`).** A grid search over 81 combinations of blur, Canny thresholds, Hough votes
and minimum line length, trained on realistic synthetic gauges and checked on the real photos (which the
search never sees). Results are in `results/tuning.csv`:
- Every combination scored about the same on synthetic data. The best beat the defaults by only 0.04°.
- The synthetic winner was *worse* on real photos (6.6° vs 4.3°).
- Synthetic and real scores were uncorrelated (r = −0.07).

So the defaults were kept. More synthetic tuning cannot improve real-world reading. **The way to improve
further is more labelled real photos.**

## Known limitations

- **Online:** no continuous live video (snapshots only); history and saved calibrations last only as long as the browser tab.
- **Small real test set.** 12 photos with labels read by eye. The real-photo numbers indicate performance;
  they are not precise accuracy figures.
- **Camera tilt.** The dial is modelled as a circle; an off-axis view makes it an ellipse. Detecting
  the needle pivot fixes most of the resulting centre error (synthetic tilt: 0.63° mean angle error), but
  strongly tilted real photos still show a few % FS error (Maximator: 2 %FS).
- **Confidence is not yet validated.** On the current data every reading is within 10°, so there are no
  gross failures for it to separate out. It would have flagged the original tyre-gauge failure (23%).
- **Glare / reflections** can hide the needle or the numbers. CLAHE helps with uneven light but not
  with saturated glare.
- **Unusual gauges.** Assumes one straight needle whose pivot is near the dial centre, a scale that increases
  clockwise, and numbers printed inside the tick ring. Multi-needle, eccentric-pivot, or
  anticlockwise gauges are not supported.
- **OCR** works on synthetic dials (96%, or 78% on the realistic set), but gave a calibration on only 2 of 12
  real photos. The causes: small or rotated digits, fonts like "12⁰⁰⁰", and numbers hidden by the needle.
  It needs the user's scale min/max as a units check. Confident misreads can still give a wrong calibration.
  The app always shows which numbers were used, and falls back to manual calibration when OCR fails or the
  sanity checks reject the result. **For real gauges, use manual calibration with the angle grid.**
- **Needle tail / shadow.** A strong needle shadow can be picked up as a second needle.
