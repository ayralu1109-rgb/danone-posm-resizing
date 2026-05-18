"""
template package
================
Exposes the three public functions that constitute one Template.

The Processing Engine in main.py imports exclusively from this package —
it never accesses the individual submodules directly.  Swapping to a
different Template means replacing this package wholesale.

Public API
----------
crop_bg(bg_src_path, canvas_w_px, canvas_h_px, output_path) -> str
    Content-driven viewport crop of the master BG.
    Computes a viewport ≥ CONTENT_REF (960×1110mm), anchors it to the
    can centre, crops, resizes to canvas if needed, saves at 200 DPI.
    (bg_crop.py)

compute_layout(trim_w_px, trim_h_px, trim_offset_x, trim_offset_y,
               element_sizes) -> dict
    Compute absolute SVG coordinates for each element.  (element_layout.py)

UpscaleError
    Exception raised by compute_layout when an element would need
    upscaling.  (element_layout.py)

get_element_render_order() -> list[str]
    Ordered element filenames (bottom → top), excluding bg and 成品框.
    (layer_order.py)
"""

from .bg_crop import crop_bg, get_can_canvas_pos
from .element_layout import UpscaleError, compute_layout
from .layer_order import get_element_render_order

__all__ = [
    "crop_bg",
    "get_can_canvas_pos",
    "compute_layout",
    "UpscaleError",
    "get_element_render_order",
]
