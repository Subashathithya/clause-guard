"""Generate the ClauseGuard app icon set (no image libraries required).

The icon is the ClauseGuard mark: an indigo gradient tile with a white
shield outline and a white check. Every size the PWA and the Android build
need is rendered from the same description, so the set always matches:

    public/logo192.png           192x192  rounded tile ("any" purpose)
    public/logo512.png           512x512  rounded tile ("any" purpose)
    public/logo512-maskable.png  512x512  full bleed, glyph inside the safe zone
    public/apple-touch-icon.png  180x180  opaque tile for iOS home screen
    public/favicon.ico           32x32   multi-size icon container

Usage (from the ``frontend`` directory)::

    python scripts/generate_icons.py

The script only uses the standard library, so it runs anywhere Python does.
"""
from __future__ import annotations

import math
import os
import pathlib
import struct
import zlib

# --------------------------------------------------------------------------- #
# Brand colours (match src/styles/tokens.css)
# --------------------------------------------------------------------------- #
GRADIENT_FROM = (79, 70, 229)    # --brand-600
GRADIENT_TO = (129, 140, 248)    # --brand-400
WHITE = (255, 255, 255)

SS = 3  # supersampling factor per axis


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def rounded_rect_inside(x: float, y: float, size: float, radius: float) -> bool:
    """True when (x, y) is inside a rounded square of ``size``."""
    if x < 0 or y < 0 or x > size or y > size:
        return False
    cx = min(max(x, radius), size - radius)
    cy = min(max(y, radius), size - radius)
    dx = x - cx
    dy = y - cy
    return dx * dx + dy * dy <= radius * radius


def quadratic(p0, p1, p2, t):
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
    return x, y


def flatten_quadratic(p0, p1, p2, steps: int = 20) -> list[tuple[float, float]]:
    return [quadratic(p0, p1, p2, i / steps) for i in range(steps + 1)]


def distance_to_segment(px, py, ax, ay, bx, by) -> float:
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def rounded_rect_distance(x: float, y: float, size: float, radius: float) -> float:
    """Signed distance to a rounded square (negative inside)."""
    half = size / 2
    qx = abs(x - half) - (half - radius)
    qy = abs(y - half) - (half - radius)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    return outside + min(max(qx, qy), 0.0) - radius


# --------------------------------------------------------------------------- #
# The mark
# --------------------------------------------------------------------------- #
def shield_path(cx: float, cy: float, width: float, height: float) -> list[tuple[float, float]]:
    """Shield outline as a flattened polyline (top edge, right side, tip, left)."""
    hw = width / 2
    top = cy - height / 2
    shoulder = top + height * 0.42
    tip = top + height
    right = flatten_quadratic((cx + hw, shoulder), (cx + hw, top + height * 0.80), (cx, tip))
    left = flatten_quadratic((cx - hw, shoulder), (cx - hw, top + height * 0.80), (cx, tip))
    path = [(cx - hw, top), (cx + hw, top)]
    path += right
    path += list(reversed(left))
    return path


def check_path(cx: float, cy: float, width: float, height: float) -> list[tuple[float, float]]:
    return [
        (cx - width * 0.26, cy - height * 0.02),
        (cx - width * 0.08, cy + height * 0.16),
        (cx + width * 0.27, cy - height * 0.24),
    ]


def gradient_at(x: float, y: float, size: float) -> tuple[float, float, float]:
    """Diagonal brand gradient from top-left to bottom-right."""
    t = max(0.0, min(1.0, (x / size + y / size) / 2))
    return tuple(
        GRADIENT_FROM[i] + (GRADIENT_TO[i] - GRADIENT_FROM[i]) * t for i in range(3)
    )


def render_icon(
    size: int,
    *,
    rounded: bool = True,
    glyph_scale: float = 1.0,
    opaque: bool = False,
    glyph_only: bool = False,
) -> list[list[tuple[int, int, int, int]]]:
    """Render the icon and return RGBA rows (top row first).

    Coverage is computed from signed distances, which antialiases both the
    tile corners and the strokes without supersampling the whole canvas.

    ``glyph_only`` draws the white mark on a transparent background — that is
    the Android adaptive-icon foreground.
    """
    radius = size * 0.225
    glyph_w = size * 0.50 * glyph_scale
    glyph_h = size * 0.58 * glyph_scale
    stroke = size * 0.072 * max(glyph_scale, 0.85)
    half_stroke = stroke / 2
    cx = cy = size / 2

    shield = shield_path(cx, cy, glyph_w, glyph_h)
    check = check_path(cx, cy, glyph_w, glyph_h)

    segments: list[tuple[float, float, float, float]] = []
    for points in (shield, check):
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            segments.append((ax, ay, bx, by))
    # Per-segment bounds (grown by the stroke) keep the inner loop tiny.
    bounds = [
        (
            min(ax, bx) - half_stroke - 1,
            max(ax, bx) + half_stroke + 1,
            min(ay, by) - half_stroke - 1,
            max(ay, by) + half_stroke + 1,
        )
        for ax, ay, bx, by in segments
    ]

    rows: list[list[tuple[int, int, int, int]]] = []

    for py in range(size):
        y = py + 0.5
        row: list[tuple[int, int, int, int]] = []
        for px in range(size):
            x = px + 0.5

            if rounded:
                tile = 0.5 - rounded_rect_distance(x, y, size, radius)
                tile = max(0.0, min(1.0, tile))
            else:
                tile = 1.0

            if glyph_only:
                tile = 1.0  # the adaptive foreground is transparent

            if tile <= 0.0:
                row.append((0, 0, 0, 0))
                continue

            best = float("inf")
            for (ax, ay, bx, by), (minx, maxx, miny, maxy) in zip(segments, bounds):
                if x < minx or x > maxx or y < miny or y > maxy:
                    continue
                d = distance_to_segment(x, y, ax, ay, bx, by)
                if d < best:
                    best = d

            cover = 0.0
            if best != float("inf"):
                cover = max(0.0, min(1.0, half_stroke + 0.5 - best))

            if glyph_only:
                # Only the mark: white strokes on transparency.
                alpha = cover * tile
                row.append((WHITE[0], WHITE[1], WHITE[2], int(round(alpha * 255))))
                continue

            gr, gg, gb = gradient_at(x, y, size)
            r = gr + (WHITE[0] - gr) * cover
            g = gg + (WHITE[1] - gg) * cover
            b = gb + (WHITE[2] - gb) * cover

            alpha = 1.0 if opaque else tile
            row.append(
                (
                    int(round(r)),
                    int(round(g)),
                    int(round(b)),
                    int(round(alpha * 255)),
                )
            )
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# PNG / ICO writers
# --------------------------------------------------------------------------- #
def write_png(path: str, rows: list[list[tuple[int, int, int, int]]]) -> None:
    height = len(rows)
    width = len(rows[0])
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter type: none
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)
    print(f"  {os.path.basename(path):26} {width}x{height}")


def write_ico(path: str, rows: list[list[tuple[int, int, int, int]]]) -> None:
    """Write a single-image .ico that embeds a PNG (supported since Windows Vista)."""
    tmp = os.path.join(os.path.dirname(path), "_icon_tmp.png")
    write_png(tmp, rows)
    with open(tmp, "rb") as fh:
        png_bytes = fh.read()
    os.remove(tmp)

    size = len(rows)
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack(
        "<BBBBHHII",
        size if size < 256 else 0,
        size if size < 256 else 0,
        0,
        0,
        1,
        32,
        len(png_bytes),
        22,
    )
    with open(path, "wb") as fh:
        fh.write(header + entry + png_bytes)
    print(f"  {os.path.basename(path):26} {size}x{size}")


# --------------------------------------------------------------------------- #
def write_android_icons(root: Path) -> None:
    """Write the Android launcher icons from the same mark.

    The legacy square icons carry the full gradient tile; the adaptive-icon
    foreground carries the white mark on transparency, so the launcher can
    mask it to any shape.
    """
    densities = {
        "mdpi": 48,
        "hdpi": 72,
        "xhdpi": 96,
        "xxhdpi": 144,
        "xxxhdpi": 192,
        "ldpi": 36,
    }
    res = root / "android" / "app" / "src" / "main" / "res"
    for folder, size in densities.items():
        target = res / f"mipmap-{folder}"
        target.mkdir(parents=True, exist_ok=True)
        write_png(str(target / "ic_launcher.png"), render_icon(size, rounded=True))
        write_png(str(target / "ic_launcher_round.png"), render_icon(size, rounded=True))
        # Adaptive foreground: the mark only, inside the 66% safe zone.
        write_png(
            str(target / "ic_launcher_foreground.png"),
            render_icon(size, rounded=False, glyph_scale=0.62, glyph_only=True),
        )


def write_store_assets(root: Path) -> None:
    """Write the app-store and adaptive-icon sources.

    ``icon-only`` is the full tile, ``icon-foreground`` is the mark on
    transparency (for the Android adaptive icon) and ``play-icon-512`` is the
    Play Store listing icon.
    """
    assets = root / "assets"
    write_png(str(assets / "icon-only.png"), render_icon(1024, rounded=False, opaque=True))
    write_png(
        str(assets / "icon-foreground.png"),
        render_icon(1024, rounded=False, glyph_scale=0.62, glyph_only=True),
    )
    write_png(str(assets / "play-icon-512.png"), render_icon(512, rounded=False, opaque=True))


# --------------------------------------------------------------------------- #
def main() -> None:
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")
    root = os.path.abspath(root)
    print("Rendering ClauseGuard icons...")

    write_png(os.path.join(root, "logo192.png"), render_icon(192, rounded=True))
    write_png(os.path.join(root, "logo512.png"), render_icon(512, rounded=True))

    # Maskable: full bleed, glyph well inside the safe zone (80% of the tile).
    write_png(
        os.path.join(root, "logo512-maskable.png"),
        render_icon(512, rounded=False, glyph_scale=0.72, opaque=True),
    )

    # iOS home screen: iOS applies its own mask, so the tile is opaque.
    write_png(
        os.path.join(root, "apple-touch-icon.png"),
        render_icon(180, rounded=False, glyph_scale=0.78, opaque=True),
    )

    write_ico(os.path.join(root, "favicon.ico"), render_icon(32, rounded=True))

    android_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    print("Rendering Android launcher icons...")
    write_android_icons(pathlib.Path(android_root))
    print("Rendering store assets...")
    write_store_assets(pathlib.Path(android_root))
    print("Done.")


if __name__ == "__main__":
    main()
