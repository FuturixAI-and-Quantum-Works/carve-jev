from __future__ import annotations

import html
import json
from pathlib import Path

import brand
from brand import (
    BLUE,
    BODY,
    FONT,
    HAZE,
    INK,
    INK_DEEP,
    LIME,
    LINE,
    MONO,
    MUTED,
    PAPER,
    SKY,
    TRACK,
    WHITE,
)

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
DATA_PATH = ROOT / "artifacts" / "decision1-model-comparison.json"
FAMILY_DATA_PATH = ROOT / "artifacts" / "carve-family-by-task.json"

WIDTH = 1200
LEFT = 260
RIGHT = 1080
TOP = 192
ROW_HEIGHT = 45
BAR_HEIGHT = 24

SKY_GRADIENT = (
    '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#b9d0e5"/>'
    '<stop offset="0.55" stop-color="#e4edf4"/>'
    '<stop offset="1" stop-color="#f8f8f8"/></linearGradient>'
)
CARD_SHADOW = (
    '<filter id="lift" x="-10%" y="-10%" width="120%" height="130%">'
    '<feDropShadow dx="0" dy="14" stdDeviation="14" flood-color="#263738" flood-opacity="0.14"/>'
    "</filter>"
)
SKYLINE = (
    (0, 46, 70),
    (52, 30, 112),
    (88, 54, 84),
    (148, 34, 150),
    (188, 60, 96),
    (254, 38, 186),
    (298, 70, 120),
    (374, 44, 160),
    (424, 62, 104),
    (492, 36, 138),
    (534, 66, 82),
    (606, 40, 120),
)


def svg_text(
    x: float,
    y: float,
    value: str,
    *,
    size: float,
    color: str,
    weight: int = 400,
    anchor: str = "start",
    spacing: float = 0,
    family: str = FONT,
) -> str:
    tracking = f' letter-spacing="{spacing}"' if spacing else ""
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}"{tracking}>'
        f"{html.escape(value)}</text>"
    )


def write_svg(name: str, parts: list[str]) -> None:
    (ASSETS / name).write_text("\n".join([*parts, "</svg>"]) + "\n", encoding="utf-8")


def skyline(x: float, bottom: float, scale: float = 1.0) -> str:
    """Hazy city silhouette that echoes the futurixai.com hero photograph."""
    back = "".join(
        f'<rect x="{x + bx * scale + 18:.1f}" y="{bottom - bh * scale * 1.18:.1f}" '
        f'width="{bw * scale:.1f}" height="{bh * scale * 1.18:.1f}"/>'
        for bx, bw, bh in SKYLINE
    )
    front = "".join(
        f'<rect x="{x + bx * scale:.1f}" y="{bottom - bh * scale:.1f}" '
        f'width="{bw * scale:.1f}" height="{bh * scale:.1f}"/>'
        for bx, bw, bh in SKYLINE
    )
    return f'<g fill="{BLUE}" opacity="0.10">{back}</g><g fill="{BLUE}" opacity="0.14">{front}</g>'


def chip(x: float, y: float, width: float, label: str, *, size: float = 13) -> str:
    height = size * 2.5
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{height / 2}" '
        f'fill="{WHITE}" stroke="{LINE}"/>'
        f'<circle cx="{x + height / 2}" cy="{y + height / 2}" r="{size * 0.3}" fill="{LIME}" '
        f'stroke="{INK}" stroke-width="1"/>'
        + svg_text(
            x + height - 2,
            y + height / 2 + size * 0.36,
            label,
            size=size,
            color=INK,
            weight=500,
        )
    )


def brand_tag(right: float, y: float, *, color: str = INK) -> str:
    """Right-aligned "F FuturixAI" lockup whose baseline sits at y + 15."""
    word_width = brand.wordmark_width("FuturixAI", 14)
    glyph_height = 20
    start = right - word_width - 10 - brand.f_glyph_width(glyph_height)
    return brand.f_glyph(start, y - 1, glyph_height, color) + brand.wordmark(
        "FuturixAI", right - word_width, y + 15, 14, color
    )


def build_banner() -> None:
    width, height = 1200, 340
    parts = [
        brand.svg_open(
            width,
            height,
            "CARVE by FuturixAI",
            "CARVE, an open-source Jev-like model family from FuturixAI",
            defs=(
                SKY_GRADIENT
                + CARD_SHADOW
                + f'<clipPath id="frame"><rect width="{width}" height="{height}" rx="28"/>'
                "</clipPath>"
            ),
        ),
        '<g clip-path="url(#frame)">',
        f'<rect width="{width}" height="{height}" fill="url(#sky)"/>',
        skyline(560, height, 1.05),
        "</g>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="27.5" '
        f'fill="none" stroke="{LINE}"/>',
        brand.f_glyph(80, 42, 24, INK),
        brand.wordmark("FuturixAI", 80 + brand.f_glyph_width(24) + 10, 61, 15, INK),
        f'<rect x="970" y="38" width="150" height="34" rx="17" fill="{LIME}"/>',
        svg_text(1045, 60, "Open Source ↗", size=15, color=INK, weight=600, anchor="middle"),
        brand.carve_mark(80, 102, 84),
        brand.wordmark("CARVE", 186, 178, 64, INK),
        svg_text(80, 224, "Open-source Jev-like model family", size=27, color=INK, weight=500),
        svg_text(
            80,
            252,
            "CANDIDATE-ALIGNED READOUT VIA VOCABULARY EVIDENCE",
            size=12.5,
            color=BODY,
            weight=500,
            spacing=1.8,
        ),
        chip(80, 276, 176, "One-token decisions"),
        chip(268, 276, 150, "Typed responses"),
        chip(430, 276, 196, "Raw probability level"),
        f'<rect x="720" y="92" width="400" height="208" rx="22" fill="{WHITE}" '
        f'stroke="{LINE}" filter="url(#lift)"/>',
        svg_text(
            746,
            124,
            "ONE TOKEN · CANDIDATE LETTERS ONLY",
            size=11,
            color=MUTED,
            weight=600,
            spacing=1.4,
        ),
    ]
    rows = (("A", 0.62), ("B", 0.21), ("C", 0.12), ("D", 0.05))
    for index, (letter, share) in enumerate(rows):
        cy = 156 + index * 32
        picked = index == 0
        parts.extend(
            [
                f'<circle cx="758" cy="{cy}" r="11" fill="{LIME if picked else TRACK}"'
                + (f' stroke="{INK}" stroke-width="1.2"' if picked else "")
                + "/>",
                svg_text(
                    758,
                    cy + 4.5,
                    letter,
                    size=13,
                    color=INK if picked else MUTED,
                    weight=700,
                    anchor="middle",
                ),
                f'<rect x="782" y="{cy - 6}" width="260" height="12" rx="6" fill="{TRACK}"/>',
                f'<rect x="782" y="{cy - 6}" width="{260 * share:.1f}" height="12" rx="6" '
                f'fill="{INK if picked else HAZE}"/>',
                svg_text(
                    1094,
                    cy + 4.5,
                    f"{share * 100:.0f}%",
                    size=13,
                    color=INK if picked else MUTED,
                    weight=600,
                    anchor="end",
                ),
            ]
        )
    parts.extend(
        [
            svg_text(746, 292, "Illustrative readout", size=11.5, color=MUTED, weight=500),
            svg_text(
                1094,
                292,
                "→ Choice: A",
                size=12.5,
                color=INK,
                weight=600,
                anchor="end",
                family=MONO,
            ),
            svg_text(
                1120,
                326,
                "QWEN3.8 / VLLM",
                size=12,
                color=BODY,
                weight=500,
                anchor="end",
                family=MONO,
                spacing=1,
            ),
        ]
    )
    write_svg("carve-banner.svg", parts)


def build_social_preview() -> None:
    width, height = 1280, 640
    parts = [
        brand.svg_open(
            width,
            height,
            "CARVE by FuturixAI",
            "CARVE, an open-source Jev-like model family from FuturixAI",
            defs=SKY_GRADIENT
            + f'<clipPath id="frame"><rect width="{width}" height="{height}"/></clipPath>',
        ),
        '<g clip-path="url(#frame)">',
        f'<rect width="{width}" height="{height}" fill="url(#sky)"/>',
        skyline(520, height, 2.1),
        "</g>",
        brand.f_glyph(96, 80, 34, INK),
        brand.wordmark("FuturixAI", 96 + brand.f_glyph_width(34) + 14, 106, 21, INK),
        brand.carve_mark(96, 190, 128),
        brand.wordmark("CARVE", 262, 316, 96, INK),
        svg_text(96, 404, "Open-source Jev-like model family", size=42, color=INK, weight=500),
        svg_text(
            98,
            450,
            "CANDIDATE-ALIGNED READOUT VIA VOCABULARY EVIDENCE",
            size=18,
            color=BODY,
            weight=500,
            spacing=2.4,
        ),
        chip(96, 498, 258, "One-token decisions", size=19),
        chip(370, 498, 218, "Typed responses", size=19),
        chip(604, 498, 284, "Raw probability level", size=19),
    ]
    write_svg("social-preview.svg", parts)


def build_logos() -> None:
    mark_size = 96
    caps = 54
    word = brand.wordmark_width("CARVE", caps)
    width = int(mark_size + 26 + word + 8)
    height = 128
    for suffix, ink, ring, tile, muted in (
        ("", INK, WHITE, brand.TILE, MUTED),
        ("-dark", WHITE, WHITE, "#1b1d1f", "#b4bcc4"),
    ):
        parts = [
            brand.svg_open(
                width,
                height,
                "CARVE by FuturixAI",
                "CARVE logo: an open C ring holding the single selected token",
            ),
            brand.carve_mark(0, 8, mark_size, ring=ring, tile=tile),
            brand.wordmark("CARVE", mark_size + 26, 62, caps, ink),
            brand.f_glyph(mark_size + 28, 84, 18, muted),
            brand.wordmark(
                "FuturixAI", mark_size + 28 + brand.f_glyph_width(18) + 9, 98, 12.5, muted
            ),
        ]
        write_svg(f"carve-logo{suffix}.svg", parts)

    write_svg(
        "carve-mark.svg",
        [
            brand.svg_open(
                256, 256, "CARVE mark", "CARVE mark: an open C ring holding the selected token"
            ),
            brand.carve_mark(0, 0, 256),
        ],
    )


def chart_header(width: int, height: int, title: str, subtitle: str, title_size: int) -> list[str]:
    return [
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="27.5" '
        f'fill="{WHITE}" stroke="{LINE}"/>',
        svg_text(60, 64, title, size=title_size, color=INK, weight=700),
        svg_text(60, 98, subtitle, size=18, color=MUTED),
    ]


def build_model_comparison() -> None:
    report = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    results = report["results"]
    height = TOP + len(results) * ROW_HEIGHT + 120
    chart_width = RIGHT - LEFT

    parts = [
        brand.svg_open(
            WIDTH,
            height,
            "Decision 1.0 transfer-v9 model accuracy",
            "Accuracy comparison across CARVE, Jev, Kev, Lux, Qwen, Nox, Decider, Sol, Laya, "
            "Eos, and Kai.",
        ),
        *chart_header(
            WIDTH,
            height,
            "Decision 1.0 transfer-v9",
            "Accuracy on 1,046 clean, knowable test decisions",
            32,
        ),
        brand_tag(1140, 46),
        f'<circle cx="68" cy="134" r="7" fill="{BLUE}"/>',
        svg_text(84, 139, "CARVE measured", size=15, color=BODY),
        f'<circle cx="244" cy="134" r="7" fill="{INK}"/>',
        svg_text(260, 139, "Jev published", size=15, color=BODY),
        f'<circle cx="388" cy="134" r="7" fill="{HAZE}"/>',
        svg_text(404, 139, "Other published", size=15, color=BODY),
    ]

    for tick in range(0, 101, 25):
        x = LEFT + chart_width * tick / 100
        parts.append(
            f'<line x1="{x}" y1="{TOP - 12}" x2="{x}" y2="{TOP + len(results) * ROW_HEIGHT - 12}" '
            f'stroke="{LINE}" stroke-width="1" stroke-dasharray="3 5"/>'
        )
        parts.append(svg_text(x, TOP - 24, f"{tick}%", size=13, color=MUTED, anchor="middle"))

    for index, row in enumerate(results):
        y = TOP + index * ROW_HEIGHT
        accuracy = float(row["accuracy"])
        model = str(row["model"])
        provenance = str(row["provenance"])
        if model.startswith("CARVE"):
            color, label_color = BLUE, INK
        elif model == "Jev":
            color, label_color = INK, INK
        else:
            color, label_color = HAZE, BODY
        if model.startswith("CARVE"):
            parts.append(
                f'<rect x="40" y="{y - 11}" width="{WIDTH - 80}" height="{ROW_HEIGHT - 4}" '
                f'rx="12" fill="{PAPER}"/>'
            )

        parts.extend(
            [
                svg_text(
                    LEFT - 18,
                    y + 17,
                    model,
                    size=16,
                    color=label_color,
                    weight=700 if provenance == "measured" or model == "Jev" else 450,
                    anchor="end",
                ),
                f'<rect x="{LEFT}" y="{y}" width="{chart_width}" height="{BAR_HEIGHT}" '
                f'rx="{BAR_HEIGHT / 2}" fill="{TRACK}"/>',
                f'<rect x="{LEFT}" y="{y}" width="{chart_width * accuracy:.1f}" '
                f'height="{BAR_HEIGHT}" rx="{BAR_HEIGHT / 2}" fill="{color}"/>',
                svg_text(
                    LEFT + chart_width * accuracy + 12,
                    y + 17,
                    f"{accuracy * 100:.2f}%",
                    size=15,
                    color=INK,
                    weight=700,
                ),
            ]
        )

    footer_y = TOP + len(results) * ROW_HEIGHT + 35
    parts.extend(
        [
            f'<line x1="60" y1="{footer_y - 18}" x2="1140" y2="{footer_y - 18}" '
            f'stroke="{LINE}" stroke-width="1"/>',
            svg_text(
                60,
                footer_y + 10,
                "CARVE: local measurement · Other rows: externally published Decision 1.0 results",
                size=15,
                color=BODY,
            ),
            svg_text(
                60,
                footer_y + 38,
                "Accuracy comparison only; this is not a controlled latency "
                "or hardware comparison.",
                size=15,
                color=MUTED,
            ),
        ]
    )
    write_svg("decision1-model-comparison.svg", parts)


def build_family_by_task() -> None:
    report = json.loads(FAMILY_DATA_PATH.read_text(encoding="utf-8"))
    tasks = report["tasks"]
    variants = report["variants"]
    width = 1400
    left = 310
    right = 1040
    top = 238
    row_height = 58
    height = top + len(tasks) * row_height + 150
    chart_width = right - left
    minimum_accuracy = 0.5
    colors = {"zs": SKY, "as": BLUE, "fs1": INK_DEEP, "fs2": LIME}
    outlines = {"zs": WHITE, "as": WHITE, "fs1": WHITE, "fs2": INK}
    offsets = {"zs": -15, "as": -5, "fs1": 5, "fs2": 15}
    value_columns = {"zs": 1110, "as": 1180, "fs1": 1250, "fs2": 1320}

    def accuracy_x(value: float) -> float:
        return left + chart_width * (value - minimum_accuracy) / (1 - minimum_accuracy)

    def dot(cx: float, cy: float, variant_id: str, radius: float) -> str:
        return (
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{colors[variant_id]}" '
            f'stroke="{outlines[variant_id]}" stroke-width="{1.5 if variant_id == "fs2" else 2}"/>'
        )

    parts = [
        brand.svg_open(
            width,
            height,
            "CARVE family accuracy by task",
            "Per-task accuracy for CARVE zero-shot, adaptive, one-shot, and two-shot profiles.",
        ),
        *chart_header(
            width,
            height,
            "Where CARVE gains from demonstrations—and where it does not",
            "Per-task accuracy across the open-source Jev-like CARVE model family",
            30,
        ),
        brand_tag(1340, 46),
    ]

    legend_x = 68
    for variant in variants:
        variant_id = str(variant["id"])
        parts.extend(
            [
                dot(legend_x, 134, variant_id, 7),
                svg_text(legend_x + 16, 139, str(variant["name"]), size=15, color=BODY),
            ]
        )
        legend_x += 175

    parts.append(
        svg_text(
            1215,
            top - 78,
            "EXACT VALUES",
            size=12,
            color=MUTED,
            weight=700,
            anchor="middle",
            spacing=1.2,
        )
    )
    for variant in variants:
        variant_id = str(variant["id"])
        parts.append(
            svg_text(
                value_columns[variant_id],
                top - 46,
                variant_id.upper(),
                size=13,
                color=INK,
                weight=700,
                anchor="middle",
            )
        )

    for tick in range(50, 101, 10):
        x = accuracy_x(tick / 100)
        parts.extend(
            [
                f'<line x1="{x}" y1="{top - 36}" x2="{x}" '
                f'y2="{top + len(tasks) * row_height - 15}" stroke="{LINE}" '
                'stroke-width="1" stroke-dasharray="3 5"/>',
                svg_text(x, top - 46, f"{tick}%", size=13, color=MUTED, anchor="middle"),
            ]
        )

    for index, task in enumerate(tasks):
        center_y = top + index * row_height
        values = [float(task[str(variant["id"])]) for variant in variants]
        low_x = accuracy_x(min(values))
        high_x = accuracy_x(max(values))
        if index % 2 == 0:
            parts.append(
                f'<rect x="40" y="{center_y - 27}" width="1320" height="54" rx="12" '
                f'fill="{PAPER}"/>'
            )
        parts.extend(
            [
                svg_text(
                    left - 20,
                    center_y + 5,
                    f"{task['name']} (n={task['n']})",
                    size=15,
                    color=INK,
                    weight=500,
                    anchor="end",
                ),
                f'<line x1="{low_x}" y1="{center_y}" x2="{high_x}" y2="{center_y}" '
                f'stroke="{HAZE}" stroke-opacity="0.55" stroke-width="6" stroke-linecap="round"/>',
            ]
        )
        for variant in variants:
            variant_id = str(variant["id"])
            value = float(task[variant_id])
            parts.extend(
                [
                    dot(accuracy_x(value), center_y + offsets[variant_id], variant_id, 6.5),
                    svg_text(
                        value_columns[variant_id],
                        center_y + 5,
                        f"{value * 100:.1f}",
                        size=13,
                        color=INK,
                        weight=600,
                        anchor="middle",
                    ),
                ]
            )

    footer_y = top + len(tasks) * row_height + 28
    overall = report["overall"]
    parts.extend(
        [
            f'<line x1="60" y1="{footer_y - 18}" x2="1340" y2="{footer_y - 18}" '
            f'stroke="{LINE}" stroke-width="1"/>',
            svg_text(
                60,
                footer_y + 10,
                (
                    f"Overall: ZS {overall['zs'] * 100:.2f}% · "
                    f"AS {overall['as'] * 100:.2f}% · "
                    f"FS1 {overall['fs1'] * 100:.2f}% · "
                    f"FS2 {overall['fs2'] * 100:.2f}%"
                ),
                size=15,
                color=INK,
                weight=700,
            ),
            svg_text(
                60,
                footer_y + 40,
                (
                    "Jev aggregate reference: 87.19% published. No Jev per-task "
                    "values were available in the cited source, so none are inferred."
                ),
                size=14,
                color=MUTED,
            ),
        ]
    )
    write_svg("carve-family-by-task.svg", parts)


def main() -> None:
    build_banner()
    build_social_preview()
    build_logos()
    build_model_comparison()
    build_family_by_task()


if __name__ == "__main__":
    main()
