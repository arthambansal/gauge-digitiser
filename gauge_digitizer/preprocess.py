"""
preprocess.py - Stage 1: prepare the frame for feature detection.

Steps: resize -> grayscale -> (optional CLAHE) -> Gaussian blur.
"""

import cv2


def resize_to_width(image, target_width=640):
    """
    Resize so the image is target_width pixels wide (aspect ratio kept).
    WHY: Hough parameters (radius limits, line lengths) are in pixels.
    Working at one fixed size means the same parameters work for a 4K photo
    and a 640x480 webcam frame, and it keeps processing fast.
    """
    h, w = image.shape[:2]
    scale = target_width / float(w)
    # INTER_AREA is the recommended interpolation when shrinking (it averages pixels, no aliasing)
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return cv2.resize(image, (target_width, int(round(h * scale))), interpolation=interp)


def to_grayscale(image_bgr):
    """
    WHY: dial and needle detection only need brightness, not colour.
    One channel instead of three = simpler maths and 3x less data.
    """
    if image_bgr.ndim == 2:
        return image_bgr
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)


def apply_clahe(gray, clip_limit=2.0, tile_size=8):
    """
    CLAHE = Contrast Limited Adaptive Histogram Equalisation.
    WHY: plain histogram equalisation uses ONE mapping for the whole image, so a
    dark corner and a bright glare patch cannot both be fixed. CLAHE equalises
    each small tile separately (adaptive) and limits how much contrast can be
    boosted (clip limit) so noise is not amplified too much.
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    return clahe.apply(gray)


def gaussian_blur(gray, kernel_size=5):
    """
    WHY: Canny and Hough are sensitive to pixel noise - every noisy pixel can
    become a false edge. A Gaussian blur is a low-pass filter that removes this
    high-frequency noise while keeping large structures (dial rim, needle).
    The kernel size must be odd.
    """
    k = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
    return cv2.GaussianBlur(gray, (k, k), 0)


def preprocess(image_bgr, target_width=640, use_clahe=False, blur_kernel=5):
    """
    Run the whole preprocessing stage.
    Returns (resized_colour, gray, blurred) - the colour image is kept for drawing the overlay.
    """
    resized = resize_to_width(image_bgr, target_width)
    gray = to_grayscale(resized)
    if use_clahe:
        gray = apply_clahe(gray)
    blurred = gaussian_blur(gray, blur_kernel)
    return resized, gray, blurred
