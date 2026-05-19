"""
template/layer_order.py
========================
Layer rendering order definition  (MD Section 5.5)

Public interface
----------------
get_element_render_order() -> list[str]

Returns the ordered list of element filenames (bottom → top), **excluding**
the background (bg.png) and the 成品框 group — those two are handled
unconditionally by the Processing Engine as the first and last layers.

Full layer stack (Section 5.5):
  1. bg.png              ← Processing Engine writes this first
  2. title.png
  3. imported.png
  4. top_logo.png
  5. footnote.png
  6. corner_logo.png
  7. <g id="成品框">     ← Processing Engine writes this last
"""

from __future__ import annotations

from typing import List


def get_element_render_order() -> List[str]:
    """
    Return element filenames in SVG render order (bottom-most first).

    The returned list covers only the five element layers.
    The caller is responsible for prepending the background and
    appending the 成品框 group.

    Returns
    -------
    list[str]
        Filenames with ``.png`` extension, matching the keys used in
        ``compute_layout()`` and the filenames copied into ``assets/``.
    """
    return [
        "title.png",
        "imported.png",
        "top_logo.png",
        "footnote.png",
        "corner_logo.png",
    ]
