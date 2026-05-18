"""
preview_render.py — Render the SVG output as a flat PNG preview.

Composes bg.png + element PNGs + trim rectangle into a single image at the
canvas resolution, then writes a downscaled thumbnail next to the SVG.
This is for visual verification only; the deliverable remains the SVG.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


def render_svg_to_png(svg_path: Path, thumb_max_side: int = 1400) -> Path:
    tree = ET.parse(svg_path)
    root = tree.getroot()
    vb = root.attrib["viewBox"].split()
    canvas_w, canvas_h = int(vb[2]), int(vb[3])
    base_dir = svg_path.parent

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))

    for img_el in root.iter(f"{{{SVG_NS}}}image"):
        href = img_el.attrib.get("href") or img_el.attrib.get(f"{{{XLINK_NS}}}href")
        if not href:
            continue
        src = (base_dir / href).resolve()
        x = int(float(img_el.attrib["x"]))
        y = int(float(img_el.attrib["y"]))
        w = int(float(img_el.attrib["width"]))
        h = int(float(img_el.attrib["height"]))
        with Image.open(src) as im:
            im = im.convert("RGBA").resize((max(1, w), max(1, h)), Image.LANCZOS)
            canvas.paste(im, (x, y), im)

    draw = ImageDraw.Draw(canvas)
    for rect_el in root.iter(f"{{{SVG_NS}}}rect"):
        rx = int(float(rect_el.attrib["x"]))
        ry = int(float(rect_el.attrib["y"]))
        rw = int(float(rect_el.attrib["width"]))
        rh = int(float(rect_el.attrib["height"]))
        stroke = rect_el.attrib.get("stroke", "red")
        sw = int(float(rect_el.attrib.get("stroke-width", "3")))
        sw_disp = max(sw, max(1, canvas_w // 1200))
        draw.rectangle([rx, ry, rx + rw, ry + rh], outline=stroke, width=sw_disp)

    canvas_rgb = Image.new("RGB", canvas.size, "white")
    canvas_rgb.paste(canvas, mask=canvas.split()[-1])

    scale = min(thumb_max_side / canvas_w, thumb_max_side / canvas_h, 1.0)
    if scale < 1.0:
        thumb_size = (int(canvas_w * scale), int(canvas_h * scale))
        thumb = canvas_rgb.resize(thumb_size, Image.LANCZOS)
    else:
        thumb = canvas_rgb

    out_path = svg_path.with_name(svg_path.stem + "_preview.png")
    thumb.save(out_path, "PNG", optimize=True)
    return out_path


def main(targets: list[Path]) -> None:
    for svg in targets:
        out = render_svg_to_png(svg)
        print(f"OK: {svg.relative_to(Path.cwd())} -> {out.relative_to(Path.cwd())}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    if len(sys.argv) > 1:
        svgs = [Path(p).resolve() for p in sys.argv[1:]]
    else:
        svgs = list((project_root / "output").glob("*/[!.]*.svg"))
    if not svgs:
        sys.exit("No SVGs found in output/")
    main(svgs)
