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
  2. 2标题无蒙版.png
  3. 6原装进口.png
  4. 1顶部联合 logo.png
  5. 3脚注.png
  6. 4右下角 logo.png
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
        "2标题无蒙版.png",
        "6原装进口.png",
        "1顶部联合 logo.png",
        "3脚注.png",
        "4右下角 logo.png",
    ]
