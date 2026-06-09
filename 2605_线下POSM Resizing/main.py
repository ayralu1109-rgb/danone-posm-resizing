"""
main.py  —  POSM Auto-Layout Processing Engine
===============================================
Orchestrates the full Step 1–6 pipeline described in MD Section 4.

Template used:  template/  (bg_crop + element_layout + layer_order)
The Processing Engine only calls the template's public interface; it
never reaches into template internals.

Usage
-----
Run from the project directory:
    python main.py

Outputs land in:  output/<city>_<size>mm/  (staging) and
                  output/<city>_<size>mm.zip  (final delivery)

Dependencies
------------
    pip install Pillow openpyxl
Standard library:  xml.etree.ElementTree, zipfile, shutil, pathlib, logging
"""

from __future__ import annotations

import logging
import shutil
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import openpyxl
from PIL import Image

# bg2000*2000.png is ~248 M pixels (15748×15748), which exceeds Pillow's
# default decompression-bomb limit (178 M px).  We raise the limit here
# because the source is a trusted local asset, not untrusted user input.
Image.MAX_IMAGE_PIXELS = None

# Template public interface — the only import from the template package
from template import (
    UpscaleError,
    compute_layout,
    crop_bg,
    get_can_canvas_pos,
    get_element_render_order,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Project root = directory containing this script
PROJECT_ROOT = Path(__file__).parent.resolve()

# Master BG: use the 2000×2000mm extended version.
# bg1167*1179.png is too small to cover the content-driven Viewport for
# portrait canvases (≤570mm height requires a ~1302mm tall Viewport).
# bg2000*2000.png has sufficient coverage on all sides.
BG_DIR = PROJECT_ROOT / "bg+bg扩展"
BG_FILENAME = "bg2000*2000.png"          # actual filename on disk
BG_PATH = BG_DIR / BG_FILENAME

# Element PNG source folder
ELEMENTS_DIR = PROJECT_ROOT / "png元素"

# Specification Excel
EXCEL_PATH = PROJECT_ROOT / "TS_【MR】APZA Y26 Q2 广东社区媒体.xlsx"

# Output directory (created at runtime)
OUTPUT_DIR = PROJECT_ROOT / "output"

# DPI and mm→px conversion (Section 4 / 7)
DPI = 200
MM_TO_PX: float = DPI / 25.4           # ≈ 7.874 px/mm

# SVG XML namespaces
SVG_NS   = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

# 成品框 stroke style
TRIM_STROKE_COLOR = "red"
TRIM_STROKE_WIDTH = "3"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CitySpec:
    """Parsed specification for one city row from the Excel file."""
    city:         str
    canvas_w_mm:  float
    canvas_h_mm:  float
    trim_w_mm:    float
    trim_h_mm:    float

    @property
    def canvas_w_px(self) -> int:
        return _mm2px(self.canvas_w_mm)

    @property
    def canvas_h_px(self) -> int:
        return _mm2px(self.canvas_h_mm)

    @property
    def trim_w_px(self) -> int:
        return _mm2px(self.trim_w_mm)

    @property
    def trim_h_px(self) -> int:
        return _mm2px(self.trim_h_mm)

    @property
    def size_tag(self) -> str:
        """Safe filesystem-friendly size string, e.g. '420x570mm'."""
        w = int(round(self.canvas_w_mm))
        h = int(round(self.canvas_h_mm))
        return f"{w}x{h}mm"

    @property
    def slug(self) -> str:
        """Filename stem used for SVG, ZIP, and staging directory."""
        return f"{self.city}_{self.size_tag}"


@dataclass
class ExceptionRecord:
    """One entry in the exception / skip list."""
    city:       str
    canvas_mm:  str
    trim_mm:    str
    reason:     str


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _mm2px(mm: float) -> int:
    """Convert millimetres to pixels (200 DPI, round-to-nearest)."""
    return int(round(mm * MM_TO_PX))


def _parse_size(raw: str) -> Tuple[float, float]:
    """
    Parse a size string like '420*570' into (width_mm, height_mm).
    Returns (larger, smaller) so the caller decides which is canvas / trim.
    Actually returns in the order they appear in the cell (w*h).
    """
    raw = str(raw).strip()
    parts = raw.replace("×", "*").replace("x", "*").split("*")
    if len(parts) != 2:
        raise ValueError(f"Cannot parse size string: {raw!r}")
    return float(parts[0]), float(parts[1])


def _load_element_sizes(elements_dir: Path) -> Dict[str, Tuple[int, int]]:
    """
    Open every element PNG and read its pixel dimensions.
    Returns {filename: (width_px, height_px)}.
    Master BG is NOT included here.
    """
    sizes: Dict[str, Tuple[int, int]] = {}
    for png in elements_dir.glob("*.png"):
        with Image.open(png) as img:
            sizes[png.name] = img.size          # (width, height)
    return sizes


def _bg_px_size(bg_path: Path) -> Tuple[int, int]:
    """Return (width_px, height_px) of the master BG without loading all pixels."""
    with Image.open(bg_path) as img:
        return img.size


# ---------------------------------------------------------------------------
# Step 1: Parse Excel  → list[CitySpec]
# ---------------------------------------------------------------------------

def parse_excel(excel_path: Path) -> List[CitySpec]:
    """
    Read the specification Excel and return one CitySpec per data row.

    Expected columns (0-indexed after skipping the header):
        A = 城市
        B = 画面尺寸 宽*高 (mm)   ← larger value = canvas
        C = 可视尺寸 宽*高 (mm)   ← smaller value = trim / 成品框

    Rows where any required cell is empty are silently skipped.
    """
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active

    specs: List[CitySpec] = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        city_val, canvas_val, trim_val = (row[0], row[1], row[2])

        if not city_val or not canvas_val or not trim_val:
            logging.debug("Row %d skipped (empty cell)", row_idx)
            continue

        city = str(city_val).strip()
        canvas_w_mm, canvas_h_mm = _parse_size(str(canvas_val))
        trim_w_mm,   trim_h_mm   = _parse_size(str(trim_val))

        specs.append(CitySpec(
            city=city,
            canvas_w_mm=canvas_w_mm,
            canvas_h_mm=canvas_h_mm,
            trim_w_mm=trim_w_mm,
            trim_h_mm=trim_h_mm,
        ))

    logging.info("Parsed %d city specs from Excel", len(specs))
    return specs


# ---------------------------------------------------------------------------
# Step 5: Build SVG  → str (UTF-8 XML text)
# ---------------------------------------------------------------------------

def build_svg(
    canvas_w: int,
    canvas_h: int,
    canvas_w_mm: float,
    canvas_h_mm: float,
    trim_x: int,
    trim_y: int,
    trim_w: int,
    trim_h: int,
    layout: Dict[str, Dict[str, int]],
    render_order: List[str],
) -> str:
    """
    Construct the SVG document and return it as a UTF-8 string.

    Layer stack (bottom → top):
      1. bg.png
      2–6. elements in render_order
      7. <g id="成品框">

    All <image> elements use relative ``href="./assets/..."`` paths.
    Both ``href`` (SVG 1.1+) and ``xlink:href`` (legacy Illustrator compat)
    are written for each image.

    Physical dimensions fix:
      SVG width/height are set in mm (e.g. "420mm") so that Illustrator opens
      the file at the correct physical size.  A viewBox in pixel coordinates
      (0 0 W_px H_px) maps the internal 200-DPI pixel grid to the mm artboard.
      Element coordinates are unitless pixel values resolved through the viewBox.
      This is the only structure confirmed to work correctly in Illustrator:
      viewBox numbers must NOT equal the mm dimension values, otherwise
      Illustrator creates a square artboard using width for both dimensions.
    """
    ET.register_namespace("",      SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)

    def _tag(name: str) -> str:
        return f"{{{SVG_NS}}}{name}"

    def _xl(name: str) -> str:
        return f"{{{XLINK_NS}}}{name}"

    # SVG coordinate strategy — pt-based viewBox:
    #
    # Illustrator applies two different interpretations to SVG coordinates:
    #   • <rect> / vector shapes  → honour the viewBox coordinate mapping
    #   • <image> (linked PNG)    → treat x/y/w/h directly as pt values,
    #                               ignoring viewBox
    #
    # By using a pt-based viewBox (1 user-unit = 1pt) the two interpretations
    # converge: the viewBox maps pt → mm correctly, AND Illustrator's direct
    # pt reading also places the image at the right physical position.
    #
    # Formula:  1 px (at 200 DPI) = 1/200 inch = 72/200 pt = 0.36 pt
    #   canvas_w_pt = canvas_w_mm × (72/25.4)
    #   element_pt  = element_px  × (72/200)  [= px × canvas_w_pt/canvas_w_px]
    #
    # PNG assets stay at 200 DPI — no metadata change needed.

    MM_TO_PT = 72.0 / 25.4                    # ≈ 2.8346 pt/mm
    canvas_w_pt = canvas_w_mm * MM_TO_PT
    canvas_h_pt = canvas_h_mm * MM_TO_PT
    px_to_pt    = canvas_w_pt / canvas_w       # ≈ 0.36 pt/px  (200 DPI → pt)

    def _pt(val: int | float) -> str:
        """Pixel value → pt coordinate string for both <image> and <rect>."""
        return f"{val * px_to_pt:.4f}"

    root = ET.Element(_tag("svg"), {
        "width":   f"{canvas_w_mm:.4f}mm",
        "height":  f"{canvas_h_mm:.4f}mm",
        "viewBox": f"0 0 {canvas_w_pt:.4f} {canvas_h_pt:.4f}",
    })

    def _add_image(parent: ET.Element, href: str, x: int, y: int,
                   w: int, h: int) -> ET.Element:
        el = ET.SubElement(parent, _tag("image"), {
            "x":      _pt(x),
            "y":      _pt(y),
            "width":  _pt(w),
            "height": _pt(h),
            "preserveAspectRatio": "none",
            "href":   href,          # SVG 1.1 / SVG 2
        })
        el.set(_xl("href"), href)    # legacy xlink:href for Illustrator CS/CC
        return el

    # Layer 1 – background (full canvas, no offset needed: crop is exact)
    _add_image(root, "./assets/bg.png", 0, 0, canvas_w, canvas_h)

    # Layers 2–6 – elements
    for filename in render_order:
        info = layout[filename]
        _add_image(root, f"./assets/{filename}",
                   info["x"], info["y"], info["w"], info["h"])

    # Layer 7 – 成品框 (topmost, vector rect, red stroke, no fill)
    trim_group = ET.SubElement(root, _tag("g"), {"id": "成品框"})
    ET.SubElement(trim_group, _tag("rect"), {
        "x":      _pt(trim_x),
        "y":      _pt(trim_y),
        "width":  _pt(trim_w),
        "height": _pt(trim_h),
        "fill":         "none",
        "stroke":       TRIM_STROKE_COLOR,
        "stroke-width": f"{float(TRIM_STROKE_WIDTH) * px_to_pt:.4f}",
    })

    ET.indent(root, space="  ")
    svg_body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + svg_body


# ---------------------------------------------------------------------------
# Per-city pipeline  (Steps 2–6)
# ---------------------------------------------------------------------------

def process_city(
    spec: CitySpec,
    bg_path: Path,
    elements_dir: Path,
    element_sizes: Dict[str, Tuple[int, int]],
    output_dir: Path,
) -> None:
    """
    Run the full pipeline for one city and produce a deliverable ZIP.

    Raises
    ------
    ValueError
        If the canvas exceeds the master BG dimensions, or if the canvas is
        landscape orientation (width ≥ height).  Landscape layouts require a
        separate layout pattern (horizontal_banner_v1) which is not yet
        implemented — see T-12 in POC_miniprd.md.
    UpscaleError
        If any element requires upscaling (Section 5.4).
    """
    logging.info("[%s] Processing %s ...", spec.city, spec.slug)

    # --- Guard: reject canvases below minimum short-edge threshold ---
    # Business constraint: real POSM sizes have a short edge of at least 150mm.
    # Below this threshold the layout proportions break down (title/stamp overlap
    # and other artefacts cannot be gracefully recovered).
    MIN_MM = 150.0
    for label, val in [
        ("画面宽度", spec.canvas_w_mm), ("画面高度", spec.canvas_h_mm),
        ("可视宽度", spec.trim_w_mm),   ("可视高度", spec.trim_h_mm),
    ]:
        if val < MIN_MM:
            raise ValueError(f"{label} {val:.0f}mm 过小，最小允许值为 {MIN_MM:.0f}mm。")
    if spec.trim_w_mm >= spec.trim_h_mm:
        raise ValueError(
            f"可视尺寸必须是竖版（高 > 宽），当前 {spec.trim_w_mm:.0f}×{spec.trim_h_mm:.0f}mm。"
        )

    # --- PoC guard: reject landscape / square canvases ---
    # The current layout rules (element_layout.py) were calibrated exclusively
    # on portrait training images (W/H 0.59–0.86).  A landscape canvas causes
    # the title element to fill >57% of the canvas height, making the output
    # visually broken.  Horizontal banner support is tracked as T-12.
    if spec.canvas_w_mm >= spec.canvas_h_mm:
        raise ValueError(
            f"横版 / 方形画布暂不支持（{spec.canvas_w_mm:.0f}×{spec.canvas_h_mm:.0f}mm，"
            f"W/H={spec.canvas_w_mm/spec.canvas_h_mm:.2f}）。"
            "横版排版规则尚未实现，详见 POC_miniprd.md T-12。"
        )

    # Staging directory for this city
    stage_dir   = output_dir / spec.slug
    assets_dir  = stage_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 2: Center-crop background ---
    bg_out = assets_dir / "bg.png"
    crop_bg(
        bg_src_path=str(bg_path),
        canvas_w_px=spec.canvas_w_px,
        canvas_h_px=spec.canvas_h_px,
        output_path=str(bg_out),
    )
    logging.info("[%s] BG cropped → %s", spec.city, bg_out.name)

    # --- Step 3: Compute 成品框 offset (centered within canvas) ---
    trim_offset_x = (spec.canvas_w_px - spec.trim_w_px) // 2
    trim_offset_y = (spec.canvas_h_px - spec.trim_h_px) // 2

    # --- Step 4a: Compute element layout (raises UpscaleError if needed) ---
    can_cx, can_cy = get_can_canvas_pos(spec.canvas_w_px, spec.canvas_h_px)
    layout = compute_layout(
        trim_w_px=spec.trim_w_px,
        trim_h_px=spec.trim_h_px,
        trim_offset_x=trim_offset_x,
        trim_offset_y=trim_offset_y,
        element_sizes=element_sizes,
        can_canvas_x=can_cx,
        can_canvas_y=can_cy,
    )

    # --- Step 4b: Copy element PNGs to assets/ (no pixel modification) ---
    for filename in layout:
        src = elements_dir / filename
        dst = assets_dir / filename
        shutil.copy2(str(src), str(dst))
        logging.info("[%s]  Copied %s", spec.city, filename)

    # --- Step 5: Build SVG ---
    render_order = get_element_render_order()
    svg_text = build_svg(
        canvas_w=spec.canvas_w_px,
        canvas_h=spec.canvas_h_px,
        canvas_w_mm=spec.canvas_w_mm,
        canvas_h_mm=spec.canvas_h_mm,
        trim_x=trim_offset_x,
        trim_y=trim_offset_y,
        trim_w=spec.trim_w_px,
        trim_h=spec.trim_h_px,
        layout=layout,
        render_order=render_order,
    )

    svg_filename = f"{spec.slug}.svg"
    svg_path = stage_dir / svg_filename
    svg_path.write_text(svg_text, encoding="utf-8")
    logging.info("[%s] SVG written → %s", spec.city, svg_filename)

    # --- Step 6: Package ZIP ---
    zip_path = output_dir / f"{spec.slug}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # SVG at ZIP root
        zf.write(svg_path, arcname=svg_filename)
        # assets/ folder contents
        for asset in sorted(assets_dir.iterdir()):
            zf.write(asset, arcname=f"assets/{asset.name}")

    logging.info("[%s] ZIP packaged → %s", spec.city, zip_path.name)


# ---------------------------------------------------------------------------
# Exception reporting
# ---------------------------------------------------------------------------

def report_exceptions(exceptions: List[ExceptionRecord]) -> None:
    """Print the exception summary after all cities have been processed."""
    if not exceptions:
        logging.info("✅  All cities processed successfully — no exceptions.")
        return

    print("\n" + "=" * 60)
    print(f"⚠️   异常清单  ({len(exceptions)} 行跳过)")
    print("=" * 60)
    for rec in exceptions:
        print(f"  城市    : {rec.city}")
        print(f"  画面尺寸: {rec.canvas_mm}")
        print(f"  可视尺寸: {rec.trim_mm}")
        print(f"  原因    : {rec.reason}")
        print("-" * 60)
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # Verify required paths exist
    if not BG_PATH.exists():
        raise FileNotFoundError(f"Master BG not found: {BG_PATH}")
    if not ELEMENTS_DIR.exists():
        raise FileNotFoundError(f"Elements directory not found: {ELEMENTS_DIR}")
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel spec not found: {EXCEL_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Pre-load BG dimensions (used for over-size check in crop_bg)
    bg_w_px, bg_h_px = _bg_px_size(BG_PATH)
    logging.info("Master BG: %d × %d px  (%s)", bg_w_px, bg_h_px, BG_PATH.name)

    # Pre-load all element sizes (read once, reused for every city)
    element_sizes = _load_element_sizes(ELEMENTS_DIR)
    logging.info("Element sizes loaded: %s", list(element_sizes.keys()))

    # Parse Excel
    specs = parse_excel(EXCEL_PATH)

    exceptions: List[ExceptionRecord] = []

    for spec in specs:
        canvas_mm_str = f"{spec.canvas_w_mm}×{spec.canvas_h_mm}mm"
        trim_mm_str   = f"{spec.trim_w_mm}×{spec.trim_h_mm}mm"

        try:
            process_city(
                spec=spec,
                bg_path=BG_PATH,
                elements_dir=ELEMENTS_DIR,
                element_sizes=element_sizes,
                output_dir=OUTPUT_DIR,
            )

        except ValueError as exc:
            # Canvas exceeds master BG or other size error
            reason = str(exc)
            logging.warning("[%s] SKIPPED — %s", spec.city, reason)
            exceptions.append(ExceptionRecord(
                city=spec.city,
                canvas_mm=canvas_mm_str,
                trim_mm=trim_mm_str,
                reason=reason,
            ))

        except UpscaleError as exc:
            reason = (
                f"元素 '{exc.element_name}' 需放大："
                f"原始 {exc.original_w} px < 目标 {exc.target_w} px"
            )
            logging.warning("[%s] SKIPPED — %s", spec.city, reason)
            exceptions.append(ExceptionRecord(
                city=spec.city,
                canvas_mm=canvas_mm_str,
                trim_mm=trim_mm_str,
                reason=reason,
            ))

        except Exception as exc:
            # Unexpected error — log and continue
            reason = f"未预期错误：{type(exc).__name__}: {exc}"
            logging.error("[%s] SKIPPED — %s", spec.city, reason)
            exceptions.append(ExceptionRecord(
                city=spec.city,
                canvas_mm=canvas_mm_str,
                trim_mm=trim_mm_str,
                reason=reason,
            ))

    report_exceptions(exceptions)
    logging.info("Done.  Output: %s", OUTPUT_DIR)


if __name__ == "__main__":
    main()
