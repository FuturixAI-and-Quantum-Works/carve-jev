from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "artifacts" / "decision1-model-comparison.json"
OUTPUT_PATH = ROOT / "assets" / "decision1-model-comparison.svg"

WIDTH = 1200
LEFT = 260
RIGHT = 1080
TOP = 170
ROW_HEIGHT = 45
BAR_HEIGHT = 25


def svg_text(
    x: float,
    y: float,
    value: str,
    *,
    size: int,
    color: str,
    weight: int = 400,
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" '
        'font-family="Inter, ui-sans-serif, system-ui, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">'
        f"{html.escape(value)}</text>"
    )


def main() -> None:
    report = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    results = report["results"]
    height = TOP + len(results) * ROW_HEIGHT + 120
    chart_width = RIGHT - LEFT

    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
            f'height="{height}" viewBox="0 0 {WIDTH} {height}" '
            'role="img" aria-labelledby="title desc">'
        ),
        '<title id="title">Decision 1.0 transfer-v9 model accuracy</title>',
        (
            '<desc id="desc">Accuracy comparison across CARVE, Jev, Kev, Lux, '
            "Qwen, Nox, Decider, Sol, Laya, Eos, and Kai.</desc>"
        ),
        f'<rect width="{WIDTH}" height="{height}" rx="28" fill="#0b1220"/>',
        svg_text(
            60,
            62,
            "Decision 1.0 transfer-v9",
            size=34,
            color="#f8fafc",
            weight=750,
        ),
        svg_text(
            60,
            98,
            "Accuracy on 1,046 clean, knowable test decisions",
            size=19,
            color="#94a3b8",
        ),
        '<circle cx="62" cy="132" r="7" fill="#22d3ee"/>',
        svg_text(78, 138, "CARVE measured", size=15, color="#cbd5e1"),
        '<circle cx="238" cy="132" r="7" fill="#818cf8"/>',
        svg_text(254, 138, "Jev published", size=15, color="#cbd5e1"),
        '<circle cx="392" cy="132" r="7" fill="#475569"/>',
        svg_text(408, 138, "Other published", size=15, color="#cbd5e1"),
    ]

    for tick in range(0, 101, 25):
        x = LEFT + chart_width * tick / 100
        parts.append(
            f'<line x1="{x}" y1="{TOP - 12}" x2="{x}" '
            f'y2="{TOP + len(results) * ROW_HEIGHT - 12}" '
            'stroke="#1e293b" stroke-width="1"/>'
        )
        parts.append(
            svg_text(
                x,
                TOP - 24,
                f"{tick}%",
                size=13,
                color="#64748b",
                anchor="middle",
            )
        )

    for index, row in enumerate(results):
        y = TOP + index * ROW_HEIGHT
        accuracy = float(row["accuracy"])
        model = str(row["model"])
        provenance = str(row["provenance"])
        if model.startswith("CARVE"):
            color = "#22d3ee"
            label_color = "#cffafe"
        elif model == "Jev":
            color = "#818cf8"
            label_color = "#e0e7ff"
        else:
            color = "#475569"
            label_color = "#cbd5e1"

        parts.extend(
            [
                svg_text(
                    LEFT - 18,
                    y + 18,
                    model,
                    size=16,
                    color=label_color,
                    weight=650 if provenance == "measured" or model == "Jev" else 450,
                    anchor="end",
                ),
                (
                    f'<rect x="{LEFT}" y="{y}" width="{chart_width}" '
                    f'height="{BAR_HEIGHT}" rx="6" fill="#111c2e"/>'
                ),
                (
                    f'<rect x="{LEFT}" y="{y}" width="{chart_width * accuracy:.1f}" '
                    f'height="{BAR_HEIGHT}" rx="6" fill="{color}"/>'
                ),
                svg_text(
                    LEFT + chart_width * accuracy + 12,
                    y + 18,
                    f"{accuracy * 100:.2f}%",
                    size=15,
                    color="#f8fafc",
                    weight=700,
                ),
            ]
        )

    footer_y = TOP + len(results) * ROW_HEIGHT + 35
    parts.extend(
        [
            f'<line x1="60" y1="{footer_y - 18}" x2="1140" y2="{footer_y - 18}" '
            'stroke="#1e293b" stroke-width="1"/>',
            svg_text(
                60,
                footer_y + 10,
                "CARVE: local measurement · Other rows: externally published Decision 1.0 results",
                size=15,
                color="#94a3b8",
            ),
            svg_text(
                60,
                footer_y + 38,
                (
                    "Accuracy comparison only; this is not a controlled latency "
                    "or hardware comparison."
                ),
                size=15,
                color="#64748b",
            ),
            "</svg>",
        ]
    )
    OUTPUT_PATH.write_text("\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
