"""
template/element_layout.py
===========================
Element positioning rules  (MD Sections 5.2 & 5.3)

Public interface
----------------
compute_layout(trim_w_px, trim_h_px, trim_offset_x, trim_offset_y,
               element_sizes) -> dict[str, dict]

UpscaleError  — raised when any element would need to be enlarged.

Rules implemented
-----------------
All coordinates are **absolute canvas pixels** (origin = top-left of the
SVG viewBox / cropped bg.png), so the caller can write them directly into
SVG <image> x/y attributes.

Percentage midpoints used (from the ranges in Section 5.2):

  Element 1 顶部联合 logo : w=60% W, top=4% H,  anchor=top-center
  Element 2 标题文字       : w=90% W, top=12.5% H, left=2.5% W, anchor=left-top
  Element 6 原装进口       : w=27.5% W, center=41.5% H, left=3% W, anchor=left-center
  Element 3 脚注           : w=85% W, bottom_gap=5.5% H, left=2.5% W, anchor=left-bottom
  Element 4 右下角 logo    : w=17.5% W, right_gap=2.5% W, bottom=elem3 bottom, anchor=right-bottom

The "禁止放大" rule (Section 5.4):
  If any element's computed target width  >= its original pixel width, an
  UpscaleError is raised immediately (before any layout dict is returned).
  The Processing Engine catches this and skips the whole city row.
"""

from __future__ import annotations

from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Layout rules table
# Each rule is keyed by the element's filename (with .png extension).
# Percentages are the midpoints of the ranges given in Section 5.2.
# ---------------------------------------------------------------------------
_RULES: Dict[str, dict] = {
    "1顶部联合 logo.png": {
        "anchor":      "top-center",
        "w_pct":       0.60,     # (55+65)/2
        "v_top_pct":   0.04,     # (3+5)/2
    },
    "2标题无蒙版.png": {
        "anchor":      "left-top",
        "w_pct":       0.90,     # (85+95)/2
        "v_top_pct":   0.125,    # (10+15)/2
        "h_left_pct":  0.025,    # (2+3)/2
    },
    "6原装进口.png": {
        "anchor":      "left-center",
        "w_pct":       0.275,    # (25+30)/2
        "v_center_pct": 0.415,   # (38+45)/2
        "h_left_pct":  0.03,     # (2+4)/2
    },
    "3脚注.png": {
        "anchor":      "left-bottom",
        "w_pct":       0.85,     # (80+90)/2
        "v_bottom_pct": 0.055,   # (4+7)/2
        "h_left_pct":  0.025,    # (2+3)/2
    },
    "4右下角 logo.png": {
        "anchor":      "right-bottom",
        "w_pct":       0.175,    # (15+20)/2
        "h_right_pct": 0.025,    # (2+3)/2
        # vertical: bottom edge aligned with element 3  (resolved at runtime)
    },
}


class UpscaleError(ValueError):
    """
    Raised when a computed target width would equal or exceed the element's
    original pixel width — which would mean upscaling, violating Section 5.4.

    Attributes
    ----------
    element_name : str
    original_w   : int   original pixel width of the element
    target_w     : int   computed display width that triggered the error
    """

    def __init__(self, element_name: str, original_w: int, target_w: int) -> None:
        self.element_name = element_name
        self.original_w   = original_w
        self.target_w     = target_w
        super().__init__(
            f"元素 '{element_name}' 需放大：原始 {original_w} px < 目标 {target_w} px"
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _px(value: float) -> int:
    """Round a float pixel value to the nearest integer (坐标强制取整)."""
    return int(round(value))


def _check_upscale(name: str, original_w: int, target_w: int) -> None:
    """Raise UpscaleError if target_w >= original_w."""
    if target_w >= original_w:
        raise UpscaleError(name, original_w, target_w)


def _scaled_h(orig_w: int, orig_h: int, target_w: int) -> int:
    """Compute display height preserving aspect ratio."""
    return _px(orig_h * target_w / orig_w)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_layout(
    trim_w_px: int,
    trim_h_px: int,
    trim_offset_x: int,
    trim_offset_y: int,
    element_sizes: Dict[str, Tuple[int, int]],
) -> Dict[str, Dict[str, int]]:
    """
    Compute absolute SVG coordinates and display dimensions for each element.

    All five elements must be present in *element_sizes*.

    Parameters
    ----------
    trim_w_px : int
        成品框 width in canvas pixels.
    trim_h_px : int
        成品框 height in canvas pixels.
    trim_offset_x : int
        X-coordinate of the 成品框's left edge within the canvas (px).
    trim_offset_y : int
        Y-coordinate of the 成品框's top edge within the canvas (px).
    element_sizes : dict
        ``{filename: (orig_w_px, orig_h_px)}`` for every element PNG.
        Keys must include the ``.png`` extension, e.g. ``"3脚注.png"``.

    Returns
    -------
    dict
        ``{filename: {"x": int, "y": int, "w": int, "h": int}}``
        where *x*, *y* are absolute canvas coordinates (top-left of the
        element bounding box) and *w*, *h* are display dimensions.

    Raises
    ------
    UpscaleError
        Immediately, for the first element found to require enlargement.
        The caller should catch this, skip the city, and record the reason.
    KeyError
        If a required element key is absent from *element_sizes*.
    """
    W  = trim_w_px
    H  = trim_h_px
    ox = trim_offset_x
    oy = trim_offset_y

    layout: Dict[str, Dict[str, int]] = {}

    # ------------------------------------------------------------------
    # 1. Element 2: 标题无蒙版  (left-top anchor)
    # ------------------------------------------------------------------
    r = _RULES["2标题无蒙版.png"]
    ow, oh = element_sizes["2标题无蒙版.png"]
    tw = _px(W * r["w_pct"])
    _check_upscale("2标题无蒙版.png", ow, tw)
    th = _scaled_h(ow, oh, tw)
    layout["2标题无蒙版.png"] = {
        "x": ox + _px(W * r["h_left_pct"]),
        "y": oy + _px(H * r["v_top_pct"]),
        "w": tw,
        "h": th,
    }

    # ------------------------------------------------------------------
    # 2. Element 6: 原装进口  (left-center anchor)
    # ------------------------------------------------------------------
    r = _RULES["6原装进口.png"]
    ow, oh = element_sizes["6原装进口.png"]
    tw = _px(W * r["w_pct"])
    _check_upscale("6原装进口.png", ow, tw)
    th = _scaled_h(ow, oh, tw)
    center_y = oy + _px(H * r["v_center_pct"])
    layout["6原装进口.png"] = {
        "x": ox + _px(W * r["h_left_pct"]),
        "y": center_y - th // 2,
        "w": tw,
        "h": th,
    }

    # ------------------------------------------------------------------
    # 3. Element 1: 顶部联合 logo  (top-center anchor)
    # ------------------------------------------------------------------
    r = _RULES["1顶部联合 logo.png"]
    ow, oh = element_sizes["1顶部联合 logo.png"]
    tw = _px(W * r["w_pct"])
    _check_upscale("1顶部联合 logo.png", ow, tw)
    th = _scaled_h(ow, oh, tw)
    layout["1顶部联合 logo.png"] = {
        "x": ox + _px((W - tw) / 2),   # horizontally centered
        "y": oy + _px(H * r["v_top_pct"]),
        "w": tw,
        "h": th,
    }

    # ------------------------------------------------------------------
    # 4. Element 3: 脚注  (left-bottom anchor)
    # ------------------------------------------------------------------
    r = _RULES["3脚注.png"]
    ow, oh = element_sizes["3脚注.png"]
    tw = _px(W * r["w_pct"])
    _check_upscale("3脚注.png", ow, tw)
    th = _scaled_h(ow, oh, tw)
    # bottom edge sits v_bottom_pct above the trim bottom edge
    bottom_y = oy + H - _px(H * r["v_bottom_pct"])
    elem3_y  = bottom_y - th
    layout["3脚注.png"] = {
        "x": ox + _px(W * r["h_left_pct"]),
        "y": elem3_y,
        "w": tw,
        "h": th,
    }
    elem3_bottom_abs = elem3_y + th  # absolute canvas y of element 3's bottom edge

    # ------------------------------------------------------------------
    # 5. Element 4: 右下角 logo  (right-bottom anchor, bottom = elem3 bottom)
    # ------------------------------------------------------------------
    r = _RULES["4右下角 logo.png"]
    ow, oh = element_sizes["4右下角 logo.png"]
    tw = _px(W * r["w_pct"])
    _check_upscale("4右下角 logo.png", ow, tw)
    th = _scaled_h(ow, oh, tw)
    # right edge sits h_right_pct inside the trim right edge
    right_x = ox + W - _px(W * r["h_right_pct"])
    layout["4右下角 logo.png"] = {
        "x": right_x - tw,
        "y": elem3_bottom_abs - th,  # bottom-aligned with element 3
        "w": tw,
        "h": th,
    }

    return layout
