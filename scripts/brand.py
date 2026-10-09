"""FuturixAI brand tokens and reusable SVG fragments for the README assets.

Colors, typography, and the F glyph come from https://www.futurixai.com.
"""

from __future__ import annotations

from brand_glyphs import WORDMARKS

INK = "#303030"
INK_DEEP = "#263738"
MUTED = "#8d8d8d"
BODY = "#4d5461"
BLUE = "#4983b5"
SKY = "#82b3dd"
HAZE = "#aabcca"
LIME = "#d3f072"
LIME_DEEP = "#c3e55f"
PAPER = "#f8f8f8"
WHITE = "#ffffff"
LINE = "#e5e7ea"
TRACK = "#eef1f3"
TILE = "#08090A"

FONT = "'DM Sans', 'Hanken Grotesk', Inter, ui-sans-serif, system-ui, -apple-system, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, monospace"

_F_GLYPH_WIDTH = 30.4
_F_GLYPH_HEIGHT = 35.4
_F_GLYPH_PATHS = (
    "M16.0469 16.8496V17.0252L21.3086 22.994H30.429V16.8496H16.0469Z",
    "M0 0.443359V9.74776L6.05104 16.6822L0 16.9455V23.0021H11.4882L22.2748 "
    "35.3788H29.9921L30.1675 35.1154L0 0.443359Z",
    "M1.22656 0L6.66373 6.23219L30.4294 6.49553V0.35111L1.22656 0Z",
)


def f_glyph(x: float, y: float, height: float, fill: str) -> str:
    """The FuturixAI "F" glyph with its top-left corner at (x, y)."""
    scale = height / _F_GLYPH_HEIGHT
    paths = "".join(f'<path d="{d}"/>' for d in _F_GLYPH_PATHS)
    return f'<g transform="translate({x} {y}) scale({scale:.4f})" fill="{fill}">{paths}</g>'


def f_glyph_width(height: float) -> float:
    return _F_GLYPH_WIDTH * height / _F_GLYPH_HEIGHT


def wordmark(name: str, x: float, baseline: float, cap_height: float, fill: str) -> str:
    d, _, cap = WORDMARKS[name]
    scale = cap_height / cap
    return f'<path transform="translate({x} {baseline}) scale({scale:.4f})" d="{d}" fill="{fill}"/>'


def wordmark_width(name: str, cap_height: float) -> float:
    _, width, cap = WORDMARKS[name]
    return width * cap_height / cap


def carve_mark(
    x: float, y: float, size: float, *, ring: str = WHITE, tile: str | None = TILE
) -> str:
    """CARVE mark: an open "C" ring whose gap holds the single selected token."""
    scale = size / 64
    parts = []
    if tile:
        parts.append(f'<rect width="64" height="64" rx="15" fill="{tile}"/>')
    parts.extend(
        [
            f'<circle cx="31" cy="32" r="16" fill="none" stroke="{ring}" stroke-width="6.5" '
            'stroke-linecap="round" stroke-dasharray="77 23.5" transform="rotate(38 31 32)"/>',
            f'<circle cx="47.5" cy="32" r="5.2" fill="{LIME}"/>',
        ]
    )
    return f'<g transform="translate({x} {y}) scale({scale:.4f})">{"".join(parts)}</g>'


def svg_open(width: int, height: int, title: str, desc: str, *, defs: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{title}</title><desc id="desc">{desc}</desc>'
        f"<defs>{defs}</defs>"
    )
