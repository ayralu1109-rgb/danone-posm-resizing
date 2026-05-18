"""
template/element_layout.py
===========================
Element positioning rules (Dynamic Anchor-based Layout)

Public interface
----------------
compute_layout(trim_w_px, trim_h_px, trim_offset_x, trim_offset_y,
               element_sizes, can_canvas_x, can_canvas_y) -> dict[str, dict]

UpscaleError  — raised when any element would need to be enlarged.

Rules implemented
-----------------
All coordinates are **absolute canvas pixels** (origin = top-left of the
SVG viewBox / cropped bg.png), so the caller can write them directly into
SVG <image> x/y attributes.

Four-step layout logic (derived from 7 training images, 330-960mm):

  Step 1 — Element 2 (标题):  primary visual anchor
    - Width = 85% Trim W
    - X: horizontally CENTERED on trim center axis
    - Y: 13% from Trim top (calibrated from training set; was 9% — too high)

  Step 2 — Element 1 (顶部联合 logo):  title companion node
    - Width = 50% of Element 2 width  (Opus analysis: median ~47%, was 60% — too wide)
    - X: horizontally CENTERED on trim center axis (same axis as Element 2)
    - Y: immediately above Element 2; gap = title_h / 50
      (was title_h / 9 — looked ~2× too far because Element 2 PNG has ≈8.8%
      "soft padding" at its top.  Visual gap = formula gap + PNG top padding;
      th2/50 ≈ 2% th2, plus 8.8% padding gives ≈10.8% visual gap, which matches
      the inter-line spacing measured inside Element 2 PNG (10.4%).)
      Floor at 2% Trim H to prevent clipping.

  Step 3 — Bottom Bar group (Elements 3 + 4):  grouped + centered
    (2026-05-18 final rule after user confirmation)

    Height rule for Element 4:
      h4 = th3 × EL3_FINEPRINT_RATIO
      where EL3_FINEPRINT_RATIO = fineprint_ink_bbox / PNG_total_h = 432/727 ≈ 0.594
      (fineprint ink spans y=[287..719) out of 727px total in 3脚注.png)
      w4 is back-calculated from h4 and Element 4's PNG aspect ratio.

    Group layout:
      Group = [Element 3 (78% W)] [INNER_GAP (2% W)] [Element 4]
      Group is horizontally CENTERED within the trim area.

    Group vertical position (symmetry rule):
      group_bottom = trim_bottom − top_logo_margin
      where top_logo_margin = y1 − trim_top  (Element 1 top → trim top)
      i.e. bottom clearance equals top logo clearance → visual balance.

  Step 4 — Element 6 (原装进口 icon):  auxiliary stamp, can-relative
    - Width = 15% Trim W  (Opus: median ~14%; was 22% — too large; must be < el4)
    - X: 3% from Trim left edge
    - Y: center = trim_top + can_trim_y × 0.73
      (was 0.61; Opus 训练集主样本均值 0.72-0.76，原值导致印章偏高)

    Collision avoidance (can body protection zone):
      A virtual bounding rectangle is derived from the known can-center position
      (CAN_TARGET_X=31.1%, CAN_TARGET_Y=63.8% of canvas) and empirical half-extents
      measured from training thumbnails (2026-05-18):
        protect_left = can_cx − 0.16 × canvas_w  (can body left edge)
        protect_top  = can_cy − 0.24 × canvas_h  (can body top, below lid)
      If Element 6 overlaps this zone:
        1st: move UP until seal bottom clears protect_top (floor = title bottom)
        2nd: if floor prevents full upward shift, also move LEFT so seal right
             clears protect_left  (clamped to trim left edge as last resort)
      This ensures the stamp never obscures the product label / branding area.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class UpscaleError(ValueError):
    """
    Raised when a computed target width would equal or exceed the element's
    original pixel width — which would mean upscaling.
    """

    def __init__(self, element_name: str, original_w: int, target_w: int) -> None:
        self.element_name = element_name
        self.original_w   = original_w
        self.target_w     = target_w
        super().__init__(
            f"元素 '{element_name}' 需放大：原始 {original_w} px < 目标 {target_w} px"
        )


def _px(value: float) -> int:
    """Round a float pixel value to the nearest integer (坐标强制取整)."""
    return int(round(value))


def _check_upscale(name: str, original_w: int, target_w: int) -> None:
    """Raise UpscaleError if target_w > original_w."""
    if target_w > original_w:
        raise UpscaleError(name, original_w, target_w)


def _scaled_h(orig_w: int, orig_h: int, target_w: int) -> int:
    """Compute display height preserving aspect ratio."""
    return _px(orig_h * target_w / orig_w)


def _scaled_w(orig_w: int, orig_h: int, target_h: int) -> int:
    """Compute display width preserving aspect ratio (inverse of _scaled_h)."""
    return _px(orig_w * target_h / orig_h)


def compute_layout(
    trim_w_px: int,
    trim_h_px: int,
    trim_offset_x: int,
    trim_offset_y: int,
    element_sizes: Dict[str, Tuple[int, int]],
    can_canvas_x: int = 0,
    can_canvas_y: int = 0,
) -> Dict[str, Dict[str, int]]:
    """
    Compute absolute SVG coordinates and display dimensions for each element.

    Parameters
    ----------
    trim_w_px, trim_h_px : int
        成品框 dimensions in canvas pixels.
    trim_offset_x, trim_offset_y : int
        Top-left corner of 成品框 in canvas coordinates.
    element_sizes : dict
        {filename: (orig_w_px, orig_h_px)} for every element PNG.
    can_canvas_x, can_canvas_y : int
        Can geometric centre in canvas pixel coordinates, as returned by
        bg_crop.get_can_canvas_pos().  Used to position Element 6 relative
        to the actual product position on screen.
    """
    W  = trim_w_px
    H  = trim_h_px
    ox = trim_offset_x
    oy = trim_offset_y

    # Can centre expressed in trim-relative coordinates
    can_trim_y = can_canvas_y - oy   # distance from trim top to can centre

    # ------------------------------------------------------------------
    # Can-body protection zone  (internal only — NOT written to SVG)
    # Empirical constants from training thumbnail analysis (2026-05-18):
    #   425mm×575mm thumb (800×1082px): can body left ≈ 16.3% canvas_w
    #   can_cx at CAN_TARGET_X=31.1%  →  half-width ≈ 14.8%;  using 0.16 (safe)
    #   can body top ≈ 40% canvas_h,  can_cy at 63.8%  →  offset ≈ 23.8%;  using 0.24
    # ------------------------------------------------------------------
    CAN_PROTECT_HALF_W  = 0.16   # half-width of can body as fraction of canvas_w
    CAN_PROTECT_TOP_OFF = 0.24   # distance above can_cy to can body top, in canvas_h
    AVOIDANCE_GAP       = 0.01   # breathing room when bumping against a boundary (trim fraction)

    # canvas size estimated from trim + equal bleed on both sides
    canvas_w = W + 2 * ox
    canvas_h = H + 2 * oy

    protect_left = can_canvas_x - round(canvas_w * CAN_PROTECT_HALF_W)
    protect_top  = can_canvas_y - round(canvas_h * CAN_PROTECT_TOP_OFF)

    layout: Dict[str, Dict[str, int]] = {}

    # ------------------------------------------------------------------
    # Step 1 — 标题 (Element 2)：主锚点，水平居中
    # ------------------------------------------------------------------
    el_name = "2标题无蒙版.png"
    ow, oh = element_sizes[el_name]
    tw2 = _px(W * 0.85)
    _check_upscale(el_name, ow, tw2)
    th2 = _scaled_h(ow, oh, tw2)
    x2 = ox + _px((W - tw2) / 2)
    y2 = oy + _px(H * 0.13)        # 距成品框顶部 13%（训练集校准，原值 9% 偏高）
    layout[el_name] = {"x": x2, "y": y2, "w": tw2, "h": th2}

    # ------------------------------------------------------------------
    # Step 2 — 顶部联合 Logo (Element 1)：标题伴生，同中轴，紧贴标题上方
    # ------------------------------------------------------------------
    el_name = "1顶部联合 logo.png"
    ow, oh = element_sizes[el_name]
    tw1 = _px(tw2 * 0.50)          # Opus calibration: ~47% median, was 0.60 (too wide)
    _check_upscale(el_name, ow, tw1)
    th1 = _scaled_h(ow, oh, tw1)
    x1 = ox + _px((W - tw1) / 2)
    # gap = th2 / 50 ≈ 2% th2；加上标题 PNG 顶部 8.8% 软 padding，视觉 gap ≈ 10.8%
    # 与标题三行字行间距 (10.4% th2) 匹配。原值 th2/9 视觉太远。
    gap_logo_title = _px(th2 / 50)
    y1 = y2 - th1 - gap_logo_title
    y1 = max(y1, oy + _px(H * 0.02))           # 防出界：距顶部至少 2%
    layout[el_name] = {"x": x1, "y": y1, "w": tw1, "h": th1}

    # ------------------------------------------------------------------
    # Step 3 — 底部组 (Elements 3 + 4)：整组居中，上下对称留白
    #
    #   尺寸规则：
    #     h4 = th3 × EL3_FINEPRINT_RATIO  (fineprint ink bbox / PNG总高)
    #     w4 由 h4 和 el4 PNG 宽高比反推
    #   组合规则：
    #     Group = [el3] [INNER_GAP] [el4]，整组水平居中于成品框
    #   垂直规则（对称）：
    #     group_bottom = trim_bottom − top_logo_margin
    #     top_logo_margin = y1 − trim_top（元素 1 顶边距成品框顶的距离）
    # ------------------------------------------------------------------
    # fineprint ink 范围在 3脚注.png 中：y=[287..719) / 727px = 432/727
    EL3_FINEPRINT_RATIO = 432 / 727  # ≈ 0.594
    INNER_GAP_RATIO     = 0.02       # 元素 3 右缘 ↔ 元素 4 左缘间距（2% W）
    # group 总宽 ≈ 标题宽 × 1.02（group 比标题略宽，训练集目测一致）
    GROUP_TO_TITLE_RATIO = 1.02

    ow3, oh3 = element_sizes["3脚注.png"]
    ow4, oh4 = element_sizes["4右下角 logo.png"]

    inner_gap = _px(W * INNER_GAP_RATIO)

    # tw4 / tw3 是常数（由两个 PNG 的宽高比和 fineprint 比例共同决定）：
    #   th3 = tw3 × (oh3/ow3)
    #   th4 = th3 × EL3_FINEPRINT_RATIO
    #   tw4 = th4 × (ow4/oh4)
    #   → tw4 = tw3 × (oh3/ow3) × EL3_FINEPRINT_RATIO × (ow4/oh4)
    el3_to_el4_w_ratio = (oh3 / ow3) * EL3_FINEPRINT_RATIO * (ow4 / oh4)

    # 反解 tw3：tw3 + inner_gap + tw3 × K = group_target_w
    group_target_w = _px(tw2 * GROUP_TO_TITLE_RATIO)
    tw3 = _px((group_target_w - inner_gap) / (1 + el3_to_el4_w_ratio))
    _check_upscale("3脚注.png", ow3, tw3)
    th3 = _scaled_h(ow3, oh3, tw3)

    # 元素 4 尺寸由 fineprint ink 高度 → 宽高比反推
    th4 = _px(th3 * EL3_FINEPRINT_RATIO)
    tw4 = _scaled_w(ow4, oh4, th4)
    _check_upscale("4右下角 logo.png", ow4, tw4)

    # Group 尺寸与水平居中
    inner_gap = _px(W * INNER_GAP_RATIO)
    group_w   = tw3 + inner_gap + tw4
    group_x   = ox + _px((W - group_w) / 2)

    # Group 垂直位置：底部留白 = 顶部 logo 离成品框顶的距离（上下对称）
    top_logo_margin = y1 - oy           # 元素 1 顶边到成品框顶的像素距离
    group_bottom    = oy + H - top_logo_margin

    x3 = group_x
    y3 = group_bottom - th3
    layout["3脚注.png"] = {"x": x3, "y": y3, "w": tw3, "h": th3}

    x4 = group_x + tw3 + inner_gap
    y4 = group_bottom - th4
    layout["4右下角 logo.png"] = {"x": x4, "y": y4, "w": tw4, "h": th4}

    # ------------------------------------------------------------------
    # Step 4 — 原装进口 Icon (Element 6)：辅助印章，罐心相对定位
    #   中心 Y = 成品框顶 + (罐心 trim-Y) × 0.73
    #   (训练集主样本均值 0.72-0.76；原值 0.61 偏高，2026-05-18 校准)
    # ------------------------------------------------------------------
    el_name = "6原装进口.png"
    ow, oh = element_sizes[el_name]
    tw6 = _px(W * 0.15)                           # Opus: median ~14%; was 22% (too large, must be < el4)
    _check_upscale(el_name, ow, tw6)
    th6 = _scaled_h(ow, oh, tw6)
    x6 = ox + _px(W * 0.03)

    if can_trim_y > 0:
        icon_center_y = oy + _px(can_trim_y * 0.73)
    else:
        icon_center_y = oy + _px(H * 0.47)        # fallback（未传罐心时，对应 0.73×H ≈ 47%）

    y6 = icon_center_y - th6 // 2

    # ------------------------------------------------------------------
    # Collision avoidance — can body protection zone
    #
    # Collision criterion:
    #   X: seal CENTER x enters the can body  (seal_cx > protect_left)
    #      Training images show the seal's right edge legitimately overlaps
    #      the can edge (~5% canvas_w), but the seal centre stays outside.
    #      Using centre instead of right edge prevents false positives on
    #      standard-width canvases.
    #   Y: seal bottom dips below the can body top (label area)
    #      (protect_top = can_cy − 0.24·canvas_h ≈ lid/body boundary)
    #
    # Avoidance (two-stage):
    #   Stage 1: push UP so seal bottom clears protect_top.
    #            Floor = title bottom (y2 + th2) to avoid overlapping title.
    #   Stage 2: if floor clamped the upward shift and seal still overlaps,
    #            also push LEFT so seal right edge clears protect_left.
    #            Hard floor: trim left edge (ox).
    # ------------------------------------------------------------------
    avoidance_gap_h = _px(H * AVOIDANCE_GAP)
    avoidance_gap_w = _px(W * AVOIDANCE_GAP)

    seal_cx     = x6 + tw6 // 2   # seal centre X
    seal_bottom = y6 + th6

    x_overlap = seal_cx     > protect_left
    y_overlap = seal_bottom > protect_top

    if x_overlap and y_overlap:
        # Stage 1: move UP
        title_bottom  = y2 + th2           # bottom edge of title element
        y6_ideal      = protect_top - th6 - avoidance_gap_h
        y6_new        = max(y6_ideal, title_bottom + avoidance_gap_h)

        logger.debug(
            "[El6 avoidance] canvas %dx%d px — default y6=%d → ideal_up=%d → clamped y6=%d  "
            "(protect_top=%d, title_bottom=%d)",
            canvas_w, canvas_h, y6, y6_ideal, y6_new, protect_top, title_bottom,
        )

        y6 = y6_new

        # Stage 2: if upward shift was clamped and centre still overlaps, move LEFT
        if (y6 + th6) > protect_top and (x6 + tw6 // 2) > protect_left:
            x6_ideal = protect_left - tw6 - avoidance_gap_w
            x6_new   = max(x6_ideal, ox)   # hard floor: trim left edge
            logger.debug(
                "[El6 avoidance] stage-2 left shift: x6 %d → %d  (protect_left=%d)",
                x6, x6_new, protect_left,
            )
            x6 = x6_new

    layout[el_name] = {"x": x6, "y": y6, "w": tw6, "h": th6}

    return layout
