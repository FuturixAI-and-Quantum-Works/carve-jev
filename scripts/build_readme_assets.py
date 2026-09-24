from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "artifacts" / "decision1-model-comparison.json"
OUTPUT_PATH = ROOT / "assets" / "decision1-model-comparison.svg"
FAMILY_DATA_PATH = ROOT / "artifacts" / "carve-family-by-task.json"
FAMILY_OUTPUT_PATH = ROOT / "assets" / "carve-family-by-task.svg"

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


def build_model_comparison() -> None:
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


def build_family_by_task() -> None:
    report = json.loads(FAMILY_DATA_PATH.read_text(encoding="utf-8"))
    tasks = report["tasks"]
    variants = report["variants"]
    width = 1400
    left = 310
    right = 1040
    top = 205
    row_height = 58
    height = top + len(tasks) * row_height + 150
    chart_width = right - left
    minimum_accuracy = 0.5
    colors = {
        "zs": "#60a5fa",
        "as": "#14b8a6",
        "fs1": "#818cf8",
        "fs2": "#22d3ee",
    }
    offsets = {"zs": -15, "as": -5, "fs1": 5, "fs2": 15}
    value_columns = {"zs": 1110, "as": 1180, "fs1": 1250, "fs2": 1320}

    def accuracy_x(value: float) -> float:
        return left + chart_width * (value - minimum_accuracy) / (1 - minimum_accuracy)

    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            'role="img" aria-labelledby="title desc">'
        ),
        '<title id="title">CARVE family accuracy by task</title>',
        (
            '<desc id="desc">Per-task accuracy for CARVE zero-shot, adaptive, '
            "one-shot, and two-shot profiles.</desc>"
        ),
        f'<rect width="{width}" height="{height}" rx="28" fill="#0b1220"/>',
        svg_text(
            60,
            58,
            "Where CARVE gains from demonstrations—and where it does not",
            size=30,
            color="#f8fafc",
            weight=750,
        ),
        svg_text(
            60,
            94,
            "Per-task accuracy across the open-source Jev-like CARVE model family",
            size=18,
            color="#94a3b8",
        ),
    ]

    legend_x = 62
    for variant in variants:
        variant_id = str(variant["id"])
        parts.extend(
            [
                (f'<circle cx="{legend_x}" cy="134" r="7" fill="{colors[variant_id]}"/>'),
                svg_text(
                    legend_x + 16,
                    140,
                    str(variant["name"]),
                    size=15,
                    color="#cbd5e1",
                ),
            ]
        )
        legend_x += 175

    parts.append(
        svg_text(
            1215,
            top - 54,
            "EXACT VALUES",
            size=12,
            color="#64748b",
            weight=700,
            anchor="middle",
        )
    )
    for variant in variants:
        variant_id = str(variant["id"])
        parts.append(
            svg_text(
                value_columns[variant_id],
                top - 25,
                variant_id.upper(),
                size=13,
                color=colors[variant_id],
                weight=700,
                anchor="middle",
            )
        )

    for tick in range(50, 101, 10):
        x = accuracy_x(tick / 100)
        parts.extend(
            [
                (
                    f'<line x1="{x}" y1="{top - 12}" x2="{x}" '
                    f'y2="{top + len(tasks) * row_height - 15}" '
                    'stroke="#1e293b" stroke-width="1"/>'
                ),
                svg_text(
                    x,
                    top - 25,
                    f"{tick}%",
                    size=13,
                    color="#64748b",
                    anchor="middle",
                ),
            ]
        )

    for index, task in enumerate(tasks):
        center_y = top + index * row_height
        values = [float(task[str(variant["id"])]) for variant in variants]
        low_x = accuracy_x(min(values))
        high_x = accuracy_x(max(values))
        if index % 2:
            parts.append(
                f'<rect x="48" y="{center_y - 25}" width="1304" height="50" rx="8" fill="#0e1728"/>'
            )
        parts.extend(
            [
                svg_text(
                    left - 20,
                    center_y + 5,
                    f"{task['name']} (n={task['n']})",
                    size=15,
                    color="#cbd5e1",
                    weight=550,
                    anchor="end",
                ),
                (
                    f'<line x1="{low_x}" y1="{center_y}" x2="{high_x}" '
                    f'y2="{center_y}" stroke="#334155" stroke-width="4" '
                    'stroke-linecap="round"/>'
                ),
            ]
        )
        for variant in variants:
            variant_id = str(variant["id"])
            value = float(task[variant_id])
            x = accuracy_x(value)
            parts.extend(
                [
                    (
                        f'<circle cx="{x}" cy="{center_y + offsets[variant_id]}" '
                        f'r="7" fill="{colors[variant_id]}" stroke="#0b1220" '
                        'stroke-width="2"/>'
                    ),
                    svg_text(
                        value_columns[variant_id],
                        center_y + offsets[variant_id] + 5,
                        f"{value * 100:.1f}",
                        size=13,
                        color=colors[variant_id],
                        weight=650,
                        anchor="middle",
                    ),
                ]
            )

    footer_y = top + len(tasks) * row_height + 28
    overall = report["overall"]
    parts.extend(
        [
            f'<line x1="60" y1="{footer_y - 18}" x2="1340" y2="{footer_y - 18}" '
            'stroke="#1e293b" stroke-width="1"/>',
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
                color="#cbd5e1",
                weight=650,
            ),
            svg_text(
                60,
                footer_y + 40,
                (
                    "Jev aggregate reference: 87.19% published. No Jev per-task "
                    "values were available in the cited source, so none are inferred."
                ),
                size=14,
                color="#64748b",
            ),
            "</svg>",
        ]
    )
    FAMILY_OUTPUT_PATH.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    build_model_comparison()
    build_family_by_task()


if __name__ == "__main__":
    main()
