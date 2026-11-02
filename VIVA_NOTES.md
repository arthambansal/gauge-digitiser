# Viva Notes – Analogue Gauge Digitizer

All numbers below were measured with `python evaluate.py`:
- 140 synthetic images with exact ground truth;
- 12 real Wikimedia Commons photos whose labels were read by eye (0.8–3.3 %FS label uncertainty, see `samples/labels.csv`).
Twelve photos is a small set. Say so if asked, and don't present real-photo numbers as precise.

---

## Stage 1 – Preprocessing (`preprocess.py`)

**What:** resize to 640 px wide → grayscale → optional CLAHE → Gaussian blur (5×5).

**Why each step:**
- *Resize:* Hough parameters are in pixels (radius limits, line lengths). A fixed working size means
  the same parameters work for any camera, and processing stays fast (~4 ms per frame without OCR).
- *Grayscale:* the geometry only needs intensity; one channel instead of three.
- *CLAHE:* equalises contrast per small tile (adaptive) with a clip limit, so a dark corner and a bright
  area can both be fixed without boosting noise. Off by default; turn on for uneven light.
- *Gaussian blur:* a low-pass filter. Canny and Hough react to every noisy pixel; blurring removes
  high-frequency noise but keeps big structures (rim, needle).

**Parameters:** `width` (640), `blur_kernel` (odd, 5), CLAHE `clipLimit` 2.0 and 8×8 tiles.

**Limitations:** blur also softens thin needles; a large kernel can merge the needle with ticks.

---

## Stage 2 – Dial detection (`dial.py`)

**What:** `cv2.HoughCircles` (HOUGH_GRADIENT). If it finds nothing, a fallback: Otsu threshold →
morphological close → contours → keep the largest contour with circularity
`4πA/P² ≥ 0.6` → `minEnclosingCircle`.

**Why Hough circles:** the dial is the largest circle in the frame. Hough voting still works when the
rim is partly hidden (by the needle, glare or a hand), because the remaining edge pixels still vote for the same centre.

**How it works:** Canny edges are computed internally. Each edge pixel votes along its gradient direction
for possible centres; a peak in the accumulator gives a centre, then the best radius is found.

**Parameters:**
- `dp = 1.2`: the accumulator is 1/1.2 of the image resolution (coarser, so faster and more tolerant).
- `minDist = side/4`: centres closer than this count as duplicates.
- `param1` (100): Canny upper threshold.
- `param2` (40): votes needed. Lower means more circles (including false ones).
- `min/max radius` (0.25–0.5 of the smaller side): rejects the hub, screws, and circles that are too big.
- When two concentric circles are found (bezel and face), we keep the smaller one, i.e. the face.

**Stage 2b – needle pivot (`find_pivot_candidates` + `needle.choose_pivot_and_needle`):**
1. A second, small Hough Circle Transform (window ±0.4 r around the dial centre, radius 0.03–0.12 r) finds up to
   8 small circles. These are hub-cap candidates; the plain dial centre is kept as a fallback.
2. The needle is detected using each candidate as the centre, and the most convincing needle is kept.
3. The needle is a straight bar turning about its pivot, so **its line must pass through the pivot**. The hub
   candidate closest to that line (within 0.05 r) becomes the pivot. If there is none, the dial centre is used.

All angles are then measured from this pivot. WHY: with camera tilt, a bezel cut off by the frame, or an old
eccentric gauge, the circle centre and the pivot can be 20–50 px apart.
- Measured: on synthetic tilted images the worst angle error fell from 8.3° to 1.3°.
- Step 3 matters: picking simply the strongest small circle chose a logo letter on the Budenberg photo (12.3° error).
  Checking against the needle line fixed it (1.1°).

**Limitations:** a tilted camera turns the circle into an ellipse, so the radius is slightly off.
Gauges with square bezels or very low rim contrast may need the contour fallback.

---

## Stage 3 – Needle detection (`needle.py`)

**What:** Canny edges masked to 0.9 r of the dial → `cv2.HoughLinesP` → filter → score → choose.

**Filters (why each exists):**
1. *The line passes within 0.12 r of the pivot.* The needle turns about the pivot. Text strokes don't point there.
2. *The near end is within 0.4 r of the centre.* Tick marks also point at the centre, but start near the rim.
3. *The far end is beyond 0.45 r.* Rejects numerals, short strokes, and the needle's tail.
4. *Score = length × contrast.* Contrast = brightness difference between the face and a thin strip just beside the
   segment. A Canny segment lies on the needle's border, so one side of it is the solid needle body.
   We take the **25th percentile** of the differences along the strip, not the mean. It is high only if at least
   75% of the strip differs from the face, i.e. the line runs along a *solid* body. A line crossing a few dark
   letters has a high mean but a low 25th percentile. This fixed the tyre-gauge photo, where a line through
   printed text had beaten the short red needle (79 %FS → 3.3 %FS).
   The best score wins. Candidates within 6° of it (the needle's two sides) are averaged with a
   circular mean, so we get the centre line rather than one edge.
5. *The tip is the end farther from the centre.* This resolves the 180° ambiguity (the tail is short).
6. *Second pass:* if nothing passes, retry once with relaxed thresholds (lines 0.66× as long and 0.66× as many votes).
   This finds short needles measured against a large bezel radius (the VDO photo). It is only a fallback: run on
   every image, relaxed thresholds let in more false lines.
7. *Confidence* = 1 − (best score in a *different* direction) / (best score). 1.0 means no competitor. It is halved
   if the second pass was needed. In the app, readings below the confidence threshold don't trigger alerts or feed
   the live smoothing.

**Parameters:** `canny_low/high` (50/150, hysteresis thresholds), `line_threshold` (30 votes),
`min_line_frac` (0.3 r), `max_line_gap` (10 px: bridges gaps caused by the hub or glare).

**Measured:** synthetic: found 140/140, mean angle error 0.37° (tilt 0.63°, max 1.3°). Realistic synthetic: 140/140,
0.51°. Real photos: **12/12, mean 4.3°**, worst 9.5°. Part of the real-photo error is my own labelling: the tyre gauge's
scale fit had a 10° residual.

**How parameters were chosen (`tune.py`):** a grid search over 81 combinations of blur kernel, Canny thresholds,
Hough votes and minimum line length. It was trained on 140 realistic synthetic gauges and checked on the 12 real
photos, which the search never saw. All combinations were within about 1° on synthetic data. The best one beat the
defaults by only 0.04° there but was worse on real photos (6.6° vs 4.3°), and the two scores were uncorrelated
(r = −0.07). So I kept the defaults. Lesson: synthetic data is useful for testing the logic, but the next accuracy gain
has to come from more real labelled photos, not more tuning.

**Limitations:** curved or very wide needles; needle shadows; a needle exactly over a tick mark. Confidence could
not be validated, because the current data has no gross failures left; it would have flagged the original
tyre-gauge failure (23% confidence).

---

## Stage 4 – Angle calculation (`utils.angle_of_point`)

`angle = atan2(-dx, dy)` in degrees, mod 360, where `dx = x_tip − cx`, `dy = y_tip − cy`.

**Convention:** 0° = straight **down** (6 o'clock), increasing **clockwise**: 90° = 9 o'clock,
180° = 12 o'clock, 270° = 3 o'clock.

**Why this convention:** most gauges have their dead zone at the bottom, so the scale (e.g. 45° → 315°)
increases smoothly without crossing the 0/360 wrap point. Image y points downwards, which is why
the signs differ from the maths textbook `atan2(y, x)`.

**Why atan2 and not atan:** `atan(dy/dx)` only covers 180° and divides by zero for vertical needles.
`atan2` uses the signs of both arguments to give the full 360°.

---

## Stage 5 – Calibration (`calibrate.py`)

**Manual:** two reference points (angle₁, value₁) and (angle₂, value₂), or min/max with start
angle and sweep. `value = value₁ + (θ − angle₁) × (value₂ − value₁) / span`.
Wrap-around: a needle in the dead zone counts as "past max" in the half after the max, and as "below min"
in the half before the min.

**Automatic (OCR):**
1. Stretch the contrast inside the dial (`normalize`) and invert if the face is dark.
2. *Adaptive threshold*, so the ink becomes white. Adaptive (not global) because lighting varies across the dial.
3. Keep a ring from 0.3 r to 0.88 r. Remove connected components too large to be a digit (> 0.25 r):
   on real gauges the ticks are joined by a printed arc into one giant ring, and the needle is large too.
   Then, after dilation, remove components that touch the ring's outer edge (those are ticks).
4. *Dilation* joins the digits of one number into one blob. *Connected components* plus size filters
   give the candidate boxes.
5. Each box is enlarged to 60 px tall, Otsu-binarised and padded, then read with Tesseract:
   `--psm 7` (a single line) and a digit whitelist. Reads with confidence below 80 are dropped.
6. The angle of each number is the angle of its box centre (atan2, as for the needle).
7. *Consistency:* try each number as the scale start, and keep the longest chain whose values increase
   clockwise (longest increasing subsequence, dynamic programming). This removes misreads that
   break the order. At least 3 points are needed, otherwise we fall back to manual and tell the user.
8. *Linear or not:* for each pair of neighbouring labels, compute degrees per unit value. Its
   coefficient of variation (std/mean) is about 0.01 on linear scales and 0.4–0.8 on our square-root scale.
   If CV < 0.15 the scale counts as linear, and we fit a least-squares straight line (`np.polyfit`). Otherwise
   we use a lookup table with linear interpolation between neighbouring labels, extended
   with the end slope beyond the first and last label.
9. *Sanity checks:* reject the calibration (and fall back to manual) if the labels used span less than 90° of
   the dial (extrapolating is unreliable), or if the spacing CV is above 1.0 (labels from two scales mixed).
10. *Dual scales* (e.g. psi outside, bar inside), in three steps:
    - **One ring:** numbers of one scale sit at the same distance from the centre. So the OCR'd numbers are
      grouped by radius (±0.08 r), and only the ring with the most numbers is used (ties: taller text).
    - **Units check:** the scale min/max the user typed (the manual fallback) is passed in, and any number outside
      that range is ignored, e.g. "1600" kPa on a 0–160 bar gauge.
    - **Dead zone:** the OCR mapping is extended to where the scale min and max must lie, and the dead zone between
      them is split in half, exactly as in manual mode. Without this, a needle just below a missed "0" label was
      read as far past the end of the scale.
    On realistic synthetic dials with a second scale, these steps cut the worst OCR error from 1,919 %FS to 6.1 %FS.

**Measured:**
- *Synthetic:* OCR calibration succeeded on 96%. Mean error was 0.15 %FS on linear gauges and 3.8 %FS on the
  square-root gauge (median 1.9%, max 21%).
- *Realistic synthetic:* succeeded on 78%, mean 0.53 %FS, max 6.1 %FS.
- *Real photos:* **2 of 12** (USG 0.15 %FS, tyre gauge 4.3 %FS). The others fell back to manual. This is the weakest
  part of the project, so be upfront about it. Manual calibration with the angle grid is the recommended way.

**Limitations:** curved/rotated text, decorative fonts (e.g. "12⁰⁰⁰" with small zeros), labels
hidden by the needle, unit text ("bar", "×100"), and confident misreads that keep the order ("50" read as "90"). On a non-linear
scale, straight-line interpolation between sparse labels causes a few % FS error between labels.

---

## Stage 6 – Threshold alerting (`alerts.py`)

- **RED:** outside [low, high].
- **AMBER:** inside, but within 10% of the range width from either limit.
- **GREEN:** otherwise.

A RED event is logged (timestamp, reading, limits, source) **when the status changes into RED**, not on
every frame. Otherwise one breach would write hundreds of rows at 12 FPS.
In live mode the alert is based on the **median of the last N readings** (default 7). The median ignores
single-frame outliers, which a mean would not.

## Stage 7 – Output and the app

The annotated image shows the detected dial circle (brass), the pivot (dot) and the needle (oxblood line). The
reading appears in an instrument-style readout: the value, a status lamp, and a scale bar with the alarm zones.

**"How it was read"** shows the pipeline stages as a filmstrip: grey, blur, dial + hub candidates (grey) and chosen
pivot (red), Canny edges, line candidates (grey = rejected, green = accepted, red dot = needle tip), and OCR labels
(green = used, red = rejected). **"Explain this reading"** walks through the same steps in words, using only values
the pipeline returned.

**How the app is built** (in case you're asked about software design):
- **Separation.** All CV is in `gauge_digitizer/`; `pipeline.read_gauge()` is the single entry point. The interface is
  in `gauge_app/` + `app.py` and never does any image processing itself. `evaluate.py` calls the same `read_gauge()`,
  so the accuracy numbers describe exactly what the app does. The redesign didn't change them (re-checked: identical).
- **Caching.** Streamlit re-runs the whole script on every click. `st.cache_data` stores `read_gauge()` results per
  (image, settings, calibration), so moving an unrelated slider doesn't re-run the pipeline or the slow OCR.
- **Per-visitor state.** History, alerts and saved calibrations live in `st.session_state` (one per browser tab), not
  in a shared file. Otherwise every visitor of the online app would see everyone else's readings.
- **Click-to-calibrate.** A click on the image becomes an angle through the same `angle_of_point()` used for the needle,
  measured from the detected pivot. First click = start angle, second click: sweep = (end − start) mod 360.
- **Deployment.** Streamlit Community Cloud with `opencv-python-headless` (no GUI libraries needed on a server) and
  Tesseract from `packages.txt`. The live webcam loop can't work there (the server has no camera), so the online version
  uses `st.camera_input` (one browser photo at a time); the local version keeps the live loop.

---

## Overall measured results

| | Synthetic (140) | Realistic synthetic (140) | Real photos (12) |
|---|---|---|---|
| Needle found | 140 / 140 | 140 / 140 | 12 / 12 |
| Mean angle error | 0.37° (tilt 0.63°) | 0.51° | 4.3° (max 9.5°) |
| Manual calibration error | mean 0.14, max 0.49 %FS | mean 0.20, max 1.93 %FS | mean 1.56, max 3.41 %FS |
| OCR calibration success | 96% | 78% | 2 / 12 |
| OCR calibration error | 0.15 %FS linear; 3.8 %FS non-linear | mean 0.53, max 6.1 %FS | 0.15 and 4.3 %FS |
| Speed (pipeline, no OCR) | ~7 ms/frame | ~7 ms/frame | ~36 ms/frame (larger photos) |

Live view: 12.2 FPS on the demo video with the final pipeline (laptop, local). Webcam FPS not measured.

---

## 10 likely viva questions

**1. Why classical CV instead of a CNN/YOLO?**
The lab focuses on image-processing fundamentals. Classical methods also need no training data, run
in milliseconds on a CPU, and every step can be inspected and explained. The cost is that they rely on
assumptions (circular dial, straight needle) that a learned model could relax.

**2. Explain the Hough Circle Transform.**
Each edge pixel votes for circle centres lying along its gradient direction. Real centres gather many
votes and appear as peaks in the accumulator. OpenCV's HOUGH_GRADIENT uses the gradient direction to
avoid searching the full 3-D (x, y, r) space. `param2` is the vote threshold.

**3. What is the difference between `HoughLines` and `HoughLinesP`?**
`HoughLines` returns infinite lines (ρ, θ). `HoughLinesP` (probabilistic) samples edge points and returns
finite segments with endpoints. We need the endpoints to tell the tip from the tail, and to apply the
"near end close to the centre" filter.

**4. How do you stop tick marks being detected as the needle?**
Ticks also point at the centre, but they lie between 0.76 r and 0.92 r. Our filter requires the segment's near
end to be within 0.4 r of the centre and its far end beyond 0.45 r. Only the needle satisfies both.
Contrast scoring then prefers the solid needle body.

**5. Why Canny before Hough? What do the two thresholds do?**
Hough votes with edge pixels, so we need a thin, clean edge map. Canny gives 1-pixel-wide edges via
non-maximum suppression. Hysteresis keeps weak edges (between low and high) only when they connect to strong
edges (above high), so long needle edges survive and isolated noise is dropped.

**6. Why atan2, and what is your angle convention?**
atan2 returns the full −180°…180° range using both signs and has no division by zero. We measure clockwise from
straight down, so typical scales do not cross the 0/360 boundary.

**7. How does the system decide whether a scale is linear?**
It computes degrees per unit value between neighbouring OCR'd labels. If the scale is linear this ratio is
constant, so its coefficient of variation is small (< 0.15). We measured ~0.01 on linear gauges and
0.4–0.8 on the square-root gauge.

**8. What happens if OCR fails or misreads?**
Reads below 80% confidence are dropped. Labels must increase clockwise (longest increasing
subsequence), and at least 3 consistent labels are needed. Otherwise the app falls back to manual
calibration and shows the reason. The OCR stage image shows which labels were used, so the
operator can check them. Remaining risk: a confident misread that still fits the order.

**9. Why the median for smoothing, and what does it cost?**
A single bad frame (needle missed or a wrong line picked) is an outlier. The median of 7 readings ignores up to 3 of
them, while a mean would shift. The cost is lag: on a fast-moving needle the smoothed value trails the raw value
by a few frames.

**10. What are the main failure cases and how would you improve them?**
- Camera tilt: the pivot detection already handles most of it. Next would be fitting an ellipse (`cv2.fitEllipse`)
  and undoing the perspective with a homography before reading.
- Wrong-needle picks: already reduced by the solidity score. Next would be using the needle's colour as well as brightness.
- OCR on real gauges: unwrap the number ring with a polar transform so the digits are upright.
- Most of all: **collect more labelled real photos.** Tuning on synthetic data no longer improves real accuracy.

**Bonus – how did you "train" a classical system?**
There is no learning; the free parameters are chosen by grid search. `tune.py` tries 81 combinations, scores each
on synthetic gauges with exact answers (the training set), and checks the winner on real photos that were never
used for choosing (the validation set). Keeping the validation set separate is what makes its score honest.
Here it showed that the synthetic optimum did not transfer, so the defaults were kept.
- Glare: use polarised light or multiple exposures; CLAHE only partly helps.
- Non-linear scales with sparse labels: also read the minor ticks to get more calibration points.
- Real-world validation: our numbers are synthetic, so the next step is a labelled set of real photos.

**Bonus – why adaptive thresholding for the OCR step and Otsu for each crop?**
Over the whole dial, lighting varies, so each pixel is compared with its local mean (adaptive). Inside one small
number crop, lighting is roughly uniform and the histogram is bimodal (ink vs. face). Otsu picks the
threshold between those two peaks automatically.

**Bonus – how does live camera work online, and why not WebRTC?**
A deployed Streamlit app runs on a remote server, so `cv2.VideoCapture(0)` there opens the *server's* camera, which doesn't
exist. WebRTC (`streamlit-webrtc`) can stream the visitor's camera, but I tried it and it failed on Streamlit Cloud with
"connection failed": peer-to-peer video needs a TURN relay server on many networks, and I don't have one. So the browser
shows the camera itself (JavaScript `getUserMedia`) and sends a small JPEG snapshot to the server about 5 times a second over
the normal app connection. The server runs the same `read_gauge()` on it and returns the dial centre, radius, needle tip and
reading; the browser draws them on the live video. Only one snapshot is in flight at a time, so latency can't build up.
Cost: online it gives about 2–4 readings a second (round trip), versus about 10 locally; the drawn needle lags fast movement.
For a continuous webcam on the server's own machine, the OpenCV capture loop is kept as the local option.

**Bonus – what does "confidence" mean?**
`1 − (best competing score in a different direction) / (needle score)`. 1.0 means nothing else in the dial looked like
a needle; near 0 means another line was almost as convincing. It's halved if the needle was only found by the relaxed
second pass. Readings below the threshold are shown but never raise alarms. Example: a photo where the gauge was tiny
in the frame gave 2% confidence and a wrong line. The app showed it as "Low confidence" instead of a red alarm.
