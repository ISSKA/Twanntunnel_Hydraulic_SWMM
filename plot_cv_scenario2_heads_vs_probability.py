from __future__ import annotations

import csv
import math
from html import escape
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
RUNS_DIR = ROOT_DIR / "MASS_COMPUTATION" / "runs"
PLOTS_DIR = RUNS_DIR / "plots"
CSV_PATH = RUNS_DIR / "CV_scenario_2" / "CV_scenario_2_hydraulic_head_results.csv"
SCENARIO = "2"
CV_SCENARIO = "CV1"
HYDROLOGIES = ("T3", "T10", "T30", "T50")
REFERENCE_HEAD_M = 454.0

PROBABILITY_BINS = [
    ("P 1e-1", 1e-1, 1.000000000001, "#d64f8c", "#a83268"),
    ("P 1e-2", 1e-2, 1e-1, "#8b6fd1", "#5f43a7"),
    ("P 1e-3", 1e-3, 1e-2, "#f0cf57", "#9c7a00"),
    ("P 1e-4", 1e-4, 1e-3, "#c9cdd3", "#6f737a"),
]


def main() -> int:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV introuvable: {CSV_PATH}")

    rows = read_rows(CSV_PATH)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    generated_paths: list[Path] = []
    for hydrology in HYDROLOGIES:
        hydrology_rows = [row for row in rows if row.get("hydrology") == hydrology]
        html = render_page(hydrology, hydrology_rows)
        output_path = (
            PLOTS_DIR / f"{SCENARIO}_{CV_SCENARIO}_{hydrology}_All_heads_vs_probability.html"
        )
        output_path.write_text(html, encoding="utf-8")
        generated_paths.append(output_path)
        print(f"[OK] {output_path} ({len(hydrology_rows)} lignes)")

    return 0 if generated_paths else 1


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def render_page(hydrology: str, rows: list[dict[str, str]]) -> str:
    chart = render_heads_svg(hydrology, rows)
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="fr">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>Scenario {SCENARIO} {CV_SCENARIO} {escape(hydrology)} - heads</title>",
            "<style>",
            "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f5;color:#202124}",
            "h1{font-size:24px;margin:0 0 6px}",
            ".subtitle{font-size:15px;color:#5f6368;margin:0 0 18px}",
            ".chart{background:#fff;border:1px solid #ddd;border-radius:6px;padding:14px;max-width:1120px}",
            "svg{width:100%;height:auto;display:block}",
            ".axis{stroke:#555;stroke-width:1}",
            ".gridline{stroke:#e3e3e3;stroke-width:1}",
            ".whisker{stroke:#1f6fbd;stroke-width:1.8}",
            ".whisker-cap{stroke:#1f6fbd;stroke-width:1.8}",
            ".box{fill-opacity:.68;stroke-width:1.5}",
            ".box-median{stroke:#1f2937;stroke-width:2.5}",
            ".residual-line{stroke:#4b5563;stroke-width:2;stroke-dasharray:7 5}",
            ".residual-label{fill:#374151;font-size:15px;font-weight:600}",
            ".label{fill:#555;font-size:15px}",
            ".axis-title{fill:#333;font-size:16px;font-weight:600}",
            ".legend{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0 0;font-size:15px;color:#333}",
            ".legend-item{display:inline-flex;align-items:center;gap:6px}",
            ".legend-swatch{width:12px;height:12px;border-radius:2px;display:inline-block}",
            ".empty{color:#777;font-size:14px}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>Scenario {SCENARIO} - {CV_SCENARIO} - {escape(hydrology)}</h1>",
            '<p class="subtitle">Whisker plots of hydraulic head at CentraleVentilation_1C by combined probability class.</p>',
            '<section class="chart">',
            chart,
            render_legend(),
            "</section>",
            "</body>",
            "</html>",
        ]
    )


def render_heads_svg(hydrology: str, rows: list[dict[str, str]]) -> str:
    values_by_bin: dict[int, list[float]] = {index: [] for index in range(len(PROBABILITY_BINS))}
    residual_heads: list[float] = []
    residual_probabilities: list[float] = []

    for row in rows:
        probability = parse_optional_float(row.get("combined_probability"))
        head = parse_optional_float(row.get("max_stable_hydraulic_head_m"))
        if probability is None or probability <= 0 or head is None:
            continue
        if row.get("connection_variant") == "1_1C_0":
            residual_heads.append(head)
            residual_probabilities.append(probability)
            continue
        for bin_index, (_, lower, upper, _, _) in enumerate(PROBABILITY_BINS):
            if lower <= probability < upper:
                values_by_bin[bin_index].append(head)
                break

    whiskers = build_whiskers(values_by_bin)
    residual_reference = build_residual_reference(residual_heads, residual_probabilities)
    if not whiskers and residual_reference is None:
        return (
            f'<p class="empty">Aucune donnee disponible pour {escape(hydrology)} dans '
            f"{escape(str(CSV_PATH))}.</p>"
        )

    width = 980
    height = 540
    left = 90
    right = 36
    top = 34
    bottom = 78
    plot_width = width - left - right
    plot_height = height - top - bottom

    y_values = [float(item["minimum"]) for item in whiskers] + [
        float(item["maximum"]) for item in whiskers
    ]
    if residual_reference is not None:
        y_values.append(float(residual_reference["head"]))
    else:
        y_values.append(REFERENCE_HEAD_M)

    min_y = min(y_values)
    max_y = max(y_values)
    if min_y == max_y:
        padding = max(0.5, abs(min_y) * 0.001)
        min_y -= padding
        max_y += padding
    else:
        padding = (max_y - min_y) * 0.06
        min_y -= padding
        max_y += padding

    def x_scale_bin(bin_index: int) -> float:
        if len(PROBABILITY_BINS) == 1:
            return left + plot_width / 2
        return left + (bin_index + 0.5) / len(PROBABILITY_BINS) * plot_width

    def y_scale(value: float) -> float:
        return top + plot_height - ((value - min_y) / (max_y - min_y)) * plot_height

    elements: list[str] = []
    elements.extend(render_grid(left, top, plot_width, plot_height, min_y, max_y, y_scale))
    elements.extend(render_probability_axis(left, top, plot_width, plot_height))
    if residual_reference is not None:
        elements.extend(render_residual_reference(residual_reference, left, top, plot_width, plot_height, y_scale))
    elements.extend(render_whiskers(whiskers, x_scale_bin, y_scale))

    elements.extend(
        [
            f'<line class="axis" x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}"/>',
            f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}"/>',
            f'<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 24}" text-anchor="middle">Combined probability class</text>',
            f'<text class="axis-title" transform="translate(24 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">Hydraulic head (m a.s.l.)</text>',
            f'<text class="label" x="{left:.1f}" y="{top - 12:.1f}">box: quartiles | center: median | whiskers: min-max</text>',
        ]
    )

    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Hydraulic head whisker plots by probability class for {escape(hydrology)}">'
        + "".join(elements)
        + "</svg>"
    )


def build_residual_reference(
    residual_heads: list[float],
    residual_probabilities: list[float],
) -> dict[str, float] | None:
    if not residual_heads:
        return None
    return {
        "head": quantile(sorted(residual_heads), 0.50),
        "minimum_head": min(residual_heads),
        "maximum_head": max(residual_heads),
        "minimum_probability": min(residual_probabilities),
        "maximum_probability": max(residual_probabilities),
        "count": float(len(residual_heads)),
    }


def render_residual_reference(
    reference: dict[str, float],
    left: int,
    top: int,
    plot_width: int,
    plot_height: int,
    y_scale,
) -> list[str]:
    y = y_scale(float(reference["head"]))
    label_y = max(top + 16, min(top + plot_height - 8, y - 10))
    tooltip = escape(
        "1_1C_0 - no connection\n"
        f"n={int(reference['count'])}\n"
        f"H median={reference['head']:.6g} m a.s.l.\n"
        f"H range=[{reference['minimum_head']:.6g}, {reference['maximum_head']:.6g}] m a.s.l.\n"
        f"P combined=[{reference['minimum_probability']:.3g}, {reference['maximum_probability']:.3g}]"
    )
    return [
        (
            f'<line class="residual-line" x1="{left:.1f}" y1="{y:.1f}" '
            f'x2="{left + plot_width:.1f}" y2="{y:.1f}">'
            f"<title>{tooltip}</title></line>"
        ),
        (
            f'<text class="residual-label" x="{left + 8:.1f}" '
            f'y="{label_y:.1f}" text-anchor="start">'
            f"1_1C_0 no connection - H={reference['head']:.2f} m"
            f"<title>{tooltip}</title></text>"
        ),
    ]


def build_whiskers(values_by_bin: dict[int, list[float]]) -> list[dict[str, object]]:
    whiskers: list[dict[str, object]] = []
    for bin_index, values in values_by_bin.items():
        if not values:
            continue
        values = sorted(values)
        label, lower, upper, fill, stroke = PROBABILITY_BINS[bin_index]
        whiskers.append(
            {
                "bin_index": bin_index,
                "label": label,
                "lower_probability": lower,
                "upper_probability": upper,
                "fill": fill,
                "stroke": stroke,
                "minimum": values[0],
                "q1": quantile(values, 0.25),
                "median": quantile(values, 0.50),
                "q3": quantile(values, 0.75),
                "maximum": values[-1],
                "count": len(values),
            }
        )
    return whiskers


def render_whiskers(whiskers: list[dict[str, object]], x_scale_bin, y_scale) -> list[str]:
    elements: list[str] = []
    for item in whiskers:
        bin_index = int(item["bin_index"])
        x = x_scale_bin(bin_index)
        minimum = float(item["minimum"])
        q1 = float(item["q1"])
        median_value = float(item["median"])
        q3 = float(item["q3"])
        maximum = float(item["maximum"])
        y_min = y_scale(minimum)
        y_q1 = y_scale(q1)
        y_median = y_scale(median_value)
        y_q3 = y_scale(q3)
        y_max = y_scale(maximum)
        box_top = min(y_q1, y_q3)
        box_height = max(2.0, abs(y_q3 - y_q1))
        half_width = 28.0
        cap_half_width = 36.0
        tooltip = escape(
            f"Probability class: {item['label']} "
            f"[{float(item['lower_probability']):.0e}, {float(item['upper_probability']):.0e})\n"
            f"n={item['count']}\n"
            f"min={minimum:.6g} m a.s.l.\n"
            f"Q1={q1:.6g} m a.s.l.\n"
            f"median={median_value:.6g} m a.s.l.\n"
            f"Q3={q3:.6g} m a.s.l.\n"
            f"max={maximum:.6g} m a.s.l."
        )
        elements.extend(
            [
                (
                    f'<line class="whisker" x1="{x:.1f}" y1="{y_max:.1f}" '
                    f'x2="{x:.1f}" y2="{y_min:.1f}" stroke="{item["stroke"]}">'
                    f"<title>{tooltip}</title></line>"
                ),
                (
                    f'<line class="whisker-cap" x1="{x - cap_half_width:.1f}" y1="{y_max:.1f}" '
                    f'x2="{x + cap_half_width:.1f}" y2="{y_max:.1f}" stroke="{item["stroke"]}">'
                    f"<title>{tooltip}</title></line>"
                ),
                (
                    f'<line class="whisker-cap" x1="{x - cap_half_width:.1f}" y1="{y_min:.1f}" '
                    f'x2="{x + cap_half_width:.1f}" y2="{y_min:.1f}" stroke="{item["stroke"]}">'
                    f"<title>{tooltip}</title></line>"
                ),
                (
                    f'<rect class="box" x="{x - half_width:.1f}" y="{box_top:.1f}" '
                    f'width="{2 * half_width:.1f}" height="{box_height:.1f}" '
                    f'fill="{item["fill"]}" stroke="{item["stroke"]}">'
                    f"<title>{tooltip}</title></rect>"
                ),
                (
                    f'<line class="box-median" x1="{x - cap_half_width:.1f}" y1="{y_median:.1f}" '
                    f'x2="{x + cap_half_width:.1f}" y2="{y_median:.1f}">'
                    f"<title>{tooltip}</title></line>"
                ),
            ]
        )
    return elements


def render_grid(
    left: int,
    top: int,
    plot_width: int,
    plot_height: int,
    min_y: float,
    max_y: float,
    y_scale,
) -> list[str]:
    elements: list[str] = []
    y_ticks = nice_ticks(min_y, max_y, 6)
    for value in y_ticks:
        y = y_scale(value)
        if top <= y <= top + plot_height:
            elements.append(
                f'<line class="gridline" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>'
            )
            elements.append(
                f'<text class="label" x="{left - 10}" y="{y + 4:.1f}" text-anchor="end">{value:.2f}</text>'
            )
    return elements


def render_probability_axis(
    left: int,
    top: int,
    plot_width: int,
    plot_height: int,
) -> list[str]:
    elements: list[str] = []
    for bin_index, (label, lower, upper, _, _) in enumerate(PROBABILITY_BINS):
        x = left + (bin_index + 0.5) / len(PROBABILITY_BINS) * plot_width
        boundary_x = left + bin_index / len(PROBABILITY_BINS) * plot_width
        if bin_index > 0:
            elements.append(
                f'<line class="gridline" x1="{boundary_x:.1f}" y1="{top}" x2="{boundary_x:.1f}" y2="{top + plot_height}"/>'
            )
        elements.append(
            f'<text class="label" x="{x:.1f}" y="{top + plot_height + 26}" text-anchor="middle">{escape(label)}</text>'
        )
        elements.append(
            f'<text class="label" x="{x:.1f}" y="{top + plot_height + 46}" text-anchor="middle">[{lower:.0e}, {upper:.0e})</text>'
        )
    return elements


def render_legend() -> str:
    items = []
    for label, lower, upper, fill, _ in PROBABILITY_BINS:
        items.append(
            '<span class="legend-item">'
            f'<span class="legend-swatch" style="background:{fill}"></span>'
            f"{escape(label)} [{lower:.0e}, {upper:.0e})</span>"
        )
    return '<div class="legend">' + "".join(items) + "</div>"


def nice_ticks(min_value: float, max_value: float, count: int) -> list[float]:
    if count <= 1 or min_value == max_value:
        return [min_value]
    raw_step = (max_value - min_value) / (count - 1)
    magnitude = 10 ** math.floor(math.log10(abs(raw_step)))
    residual = raw_step / magnitude
    if residual >= 5:
        nice_step = 5 * magnitude
    elif residual >= 2:
        nice_step = 2 * magnitude
    else:
        nice_step = magnitude
    start = math.floor(min_value / nice_step) * nice_step
    end = math.ceil(max_value / nice_step) * nice_step
    ticks = []
    value = start
    while value <= end + nice_step * 0.5:
        ticks.append(value)
        value += nice_step
    return ticks


def parse_optional_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("quantile() requires at least one value")
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return values[lower_index]
    lower_value = values[lower_index]
    upper_value = values[upper_index]
    return lower_value + (upper_value - lower_value) * (position - lower_index)


if __name__ == "__main__":
    raise SystemExit(main())
