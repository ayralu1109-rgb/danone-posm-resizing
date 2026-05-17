"""
template/bg_crop.py
===================
Background scaling-and-crop logic  (PRD Section 5.1.1)

Core concept
------------
  Viewport = canvas (fixed, never changes).

  To put the can + Helix inside the viewport we scale the master BG:

    scale = canvas_w / CONTENT_REF_W

  i.e. the 960 mm content-reference width maps exactly to the canvas width.

  The crop region extracted from the master BG is therefore:

    crop_w = CONTENT_REF_W_PX          (always 960 mm worth of pixels)
    crop_h = canvas_h_px / scale
           = canvas_h_px * CONTENT_REF_W_PX / canvas_w_px
           (pure canvas aspect-ratio derivation — no separate CONTENT_REF_H)

  The crop is anchored so that the can centre lands at
  (CAN_TARGET_X × crop_w,  CAN_TARGET_Y × crop_h),
  then resized (Lanczos) to (canvas_w_px × canvas_h_px).

  Equivalent mental model:
    "Shrink master BG by `scale`, then crop the canvas-sized viewport
     so the can sits at the target position."

Public API
----------
  crop_bg(bg_src_path, canvas_w_px, canvas_h_px, output_path) -> str
"""

from __future__ import annotations

import os

from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_DPI = 200
MM_TO_PX: float = SOURCE_DPI / 25.4   # ≈ 7.874 px / mm

# Content reference width — the physical width of 5罐子+背景+helix+买点.png,
# representing the minimum horizontal span that must be visible (罐子 + Helix + 买点).
CONTENT_REF_W_MM = 960.0
CONTENT_REF_W_PX = round(CONTENT_REF_W_MM * MM_TO_PX)   # ≈ 7559 px

# How much of the canvas width the content reference should occupy.
# Derived from training-set measurement (6 formats, 330–960mm wide):
#   left margin ≈ 5.6%,  right margin ≈ 7.3%  →  content fills ≈ 87%
# Crop region is therefore wider than the content reference by 1/0.87 ≈ 1.15×,
# which adds natural breathing room at both edges.
CONTENT_FILL_RATIO = 0.87

# Can geometric centre in the master BG (bg2000*2000.png, 200 DPI)
CAN_CX = 6568   # px  (≈ 834 mm from left)
CAN_CY = 9183   # px  (≈ 1166 mm from top)

# Target position of the can centre inside the crop region (fractions)
CAN_TARGET_X = 0.311   # 31.1 % from crop left   (can left-of-centre)
CAN_TARGET_Y = 0.638   # 63.8 % from crop top    (can slightly below centre)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def crop_bg(
    bg_src_path: str,
    canvas_w_px: int,
    canvas_h_px: int,
    output_path: str,
) -> str:
    """
    Scale-and-crop the master background to produce a canvas-sized bg.png.

    Steps
    -----
    1. Compute crop region dimensions:
         crop_w = CONTENT_REF_W_PX
         crop_h = round(canvas_h_px * CONTENT_REF_W_PX / canvas_w_px)

    2. Anchor the crop so the can centre lands at
       (CAN_TARGET_X × crop_w,  CAN_TARGET_Y × crop_h).

    3. Crop that rectangle from the master BG.

    4. Resize (Lanczos) to (canvas_w_px × canvas_h_px).

    5. Save with dpi=(SOURCE_DPI, SOURCE_DPI) metadata.

    Parameters
    ----------
    bg_src_path : str
        Path to the master BG PNG.
    canvas_w_px : int
        Target canvas width in pixels.
    canvas_h_px : int
        Target canvas height in pixels.
    output_path : str
        Destination path for the cropped bg.png.

    Returns
    -------
    str
        output_path on success.

    Raises
    ------
    ValueError
        - Master BG smaller than the required crop region.
        - Anchor-positioned crop box falls outside BG bounds.
    """
    with Image.open(bg_src_path) as img:
        bg_w, bg_h = img.size

        # --- Step 1: crop region size ---
        # Content reference fills CONTENT_FILL_RATIO of canvas width,
        # so the crop is wider by 1/FILL_RATIO, leaving natural margins.
        crop_w = round(CONTENT_REF_W_PX / CONTENT_FILL_RATIO)
        crop_h = round(canvas_h_px * crop_w / canvas_w_px)

        # --- Guard: master BG must be at least as large as the crop region ---
        if crop_w > bg_w or crop_h > bg_h:
            raise ValueError(
                f"主底图尺寸 ({bg_w}×{bg_h} px) 小于裁切区 "
                f"({crop_w}×{crop_h} px)。请使用更大的主底图。"
            )

        # --- Step 2: anchor positioning ---
        left   = CAN_CX - round(crop_w * CAN_TARGET_X)
        top    = CAN_CY - round(crop_h * CAN_TARGET_Y)
        right  = left + crop_w
        bottom = top  + crop_h

        # --- Guard: crop box must stay within BG bounds ---
        if left < 0 or top < 0 or right > bg_w or bottom > bg_h:
            raise ValueError(
                f"锚点裁切框 ({left}, {top}, {right}, {bottom}) "
                f"超出主底图边界 (0, 0, {bg_w}, {bg_h})。"
                f"请检查 CAN_CX/CAN_CY 或使用更大的主底图。"
            )

        # --- Step 3 & 4: crop → resize to canvas ---
        output_img = (
            img.crop((left, top, right, bottom))
               .resize((canvas_w_px, canvas_h_px), Image.LANCZOS)
        )

        # --- Step 5: save ---
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        output_img.save(output_path, format="PNG", dpi=(SOURCE_DPI, SOURCE_DPI))

    return output_path
