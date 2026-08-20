from __future__ import annotations

import csv
import math
import re
from html import escape
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
RUNS_DIR = ROOT_DIR / "MASS_COMPUTATION" / "runs"
PLOTS_DIR = RUNS_DIR / "plots"
SCENARIO = "1"
HYDROLOGIES = ("T3", "T10", "T30", "T50")
REFERENCE_PROBABILITY = 1e-4
PHASE_PROBABILITY_BINS = [
    ("P 1e-1", 1e-1, 1.000000000001),
    ("P 1e-2", 1e-2, 1e-1),
    ("P 1e-3", 1e-3, 1e-2),
    ("P 1e-4", 1e-4, 1e-3),
]

OUTFALLS = [
    "Fensterstollen",
    "Entw_Stollen",
    "Brunnmuehle(Teich)",
    "TWT_Portail_Est_61+665",
]

MEASURED_FLOW_REFERENCES_M3S = {
    "Fensterstollen": [
        ("measured min", 0.0),
        ("measured mean", 0.31),
        ("measured max", 2.0),
    ],
    "Entw_Stollen": [
        ("measured min", 0.0),
        ("measured mean", 0.03265),
        ("measured max", 0.127),
    ],
    "Brunnmuehle(Teich)": [
        ("measured min", 0.0),
        ("measured mean", 0.15644),
        ("measured max", 0.441),
    ],
}


def main() -> int:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    generated_paths: list[Path] = []

    for hydrology in HYDROLOGIES:
        csv_path = (
            RUNS_DIR
            / f"scenario{SCENARIO}"
            / hydrology
            / f"{hydrology}_mass_simulations_results.csv"
        )
        if not csv_path.exists():
            print(f"[SKIP] CSV introuvable: {csv_path}")
            continue

        rows = read_result_rows(csv_path)
        html = render_all_phases_page(hydrology, rows)
        output_path = PLOTS_DIR / f"{SCENARIO}_{hydrology}_All_debits_vs_probability.html"
        output_path.write_text(html, encoding="utf-8")
        generated_paths.append(output_path)
        print(f"[OK] {output_path}")

        phase_html = render_phase_probability_page(hydrology, rows)
        phase_output_path = (
            PLOTS_DIR / f"{SCENARIO}_{hydrology}_All_debits_by_phase_probability.html"
        )
        phase_output_path.write_text(phase_html, encoding="utf-8")
        generated_paths.append(phase_output_path)
        print(f"[OK] {phase_output_path}")

    if not generated_paths:
        print("Aucun HTML genere.")
        return 1

    return 0


def read_result_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def render_all_phases_page(hydrology: str, rows: list[dict[str, str]]) -> str:
    chart_blocks = [
        render_envelope_svg(rows, outfall, hydrology)
        for outfall in OUTFALLS
    ]
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="fr">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>Scenario {SCENARIO} {escape(hydrology)} - all phases</title>",
            "<style>",
            "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f5;color:#202124}",
            "h1{font-size:24px;margin:0 0 6px}",
            ".subtitle{font-size:14px;color:#5f6368;margin:0 0 18px}",
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:18px}",
            ".chart{background:#fff;border:1px solid #ddd;border-radius:6px;padding:14px}",
            ".title{font-weight:600;margin:0 0 8px}",
            "svg{width:100%;height:auto;display:block}",
            ".axis{stroke:#555;stroke-width:1}",
            ".gridline{stroke:#e3e3e3;stroke-width:1}",
            ".whisker{stroke:#1f6fbd;stroke-width:1.8}",
            ".whisker-cap{stroke:#1f6fbd;stroke-width:1.8}",
            ".box{fill:#7aa6d8;fill-opacity:.34;stroke:#1f6fbd;stroke-width:1.5}",
            ".box-median{stroke:#114b82;stroke-width:2.3}",
            ".reference-flow{stroke:#1f6fbd;stroke-width:2}",
            ".reference-probability{stroke:#1f6fbd;stroke-width:1.8;stroke-dasharray:6 5}",
            ".measured-min{stroke:#2e7d32;stroke-width:1.6;stroke-dasharray:2 4}",
            ".measured-mean{stroke:#2e7d32;stroke-width:2.2;stroke-dasharray:8 5}",
            ".measured-max{stroke:#2e7d32;stroke-width:1.8}",
            ".reference-label{fill:#1f6fbd;font-size:13px;font-weight:600}",
            ".measured-label{fill:#2e7d32;font-size:13px;font-weight:600}",
            ".label{fill:#555;font-size:13px}",
            ".legend{fill:#555;font-size:13px}",
            ".empty{color:#777;font-size:13px}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>Scenario {SCENARIO} - {escape(hydrology)} - all phases</h1>",
            '<p class="subtitle">Whisker plots of simulated maximum discharges versus combination probability, all phases combined.</p>',
            '<div class="grid">',
            *chart_blocks,
            "</div>",
            "</body>",
            "</html>",
        ]
    )


def render_phase_probability_page(hydrology: str, rows: list[dict[str, str]]) -> str:
    chart_blocks = [
        render_phase_probability_svg(rows, outfall, hydrology)
        for outfall in OUTFALLS
    ]
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="fr">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>Scenario {SCENARIO} {escape(hydrology)} - phases and probability classes</title>",
            "<style>",
            "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f5;color:#202124}",
            "h1{font-size:24px;margin:0 0 6px}",
            ".subtitle{font-size:14px;color:#5f6368;margin:0 0 18px}",
            ".grid{display:grid;grid-template-columns:1fr;gap:18px}",
            ".chart{background:#fff;border:1px solid #ddd;border-radius:6px;padding:14px;overflow-x:auto}",
            ".title{font-weight:600;margin:0 0 8px}",
            "svg{width:100%;min-width:980px;height:auto;display:block}",
            ".axis{stroke:#555;stroke-width:1}",
            ".gridline{stroke:#e3e3e3;stroke-width:1}",
            ".phase-separator{stroke:#c9c9c9;stroke-width:1;stroke-dasharray:3 5}",
            ".whisker{stroke:#1f6fbd;stroke-width:1.7}",
            ".whisker-cap{stroke:#1f6fbd;stroke-width:1.7}",
            ".box{fill:#7aa6d8;fill-opacity:.38;stroke:#1f6fbd;stroke-width:1.4}",
            ".box-median{stroke:#114b82;stroke-width:2.2}",
            ".bin-0{fill:#f4a3c4;fill-opacity:.62;stroke:#c13e79}",
            ".bin-1{fill:#b7a0e8;fill-opacity:.62;stroke:#6f48b8}",
            ".bin-2{fill:#f2d45c;fill-opacity:.72;stroke:#a98200}",
            ".bin-3{fill:#c9cdd3;fill-opacity:.70;stroke:#6f737a}",
            ".measured-min{stroke:#2e7d32;stroke-width:1.6;stroke-dasharray:2 4}",
            ".measured-mean{stroke:#2e7d32;stroke-width:2.2;stroke-dasharray:8 5}",
            ".measured-max{stroke:#2e7d32;stroke-width:1.8}",
            ".measured-label{fill:#2e7d32;font-size:13px;font-weight:600}",
            ".label{fill:#555;font-size:13px}",
            ".phase-label{fill:#333;font-size:13px;font-weight:600}",
            ".legend{fill:#555;font-size:13px}",
            ".empty{color:#777;font-size:13px}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>Scenario {SCENARIO} - {escape(hydrology)} - phases and probability classes</h1>",
            '<p class="subtitle">For each phase/sub-phase, four whisker plots summarize discharges by probability decade.</p>',
            '<div class="grid">',
            *chart_blocks,
            "</div>",
            "</body>",
            "</html>",
        ]
    )


def render_envelope_svg(rows: list[dict[str, str]], outfall: str, hydrology: str) -> str:
    q_key = f"qmax_{slugify(outfall)}_m3s"
    points: list[tuple[float, float, str, str]] = []
    for row in rows:
        probability = parse_optional_float(row.get("combination_probability"))
        flow = parse_optional_float(row.get(q_key))
        if probability is None or probability <= 0 or flow is None:
            continue
        phase = row.get("phase", "") or ""
        label = row.get("variant_combination", "") or ""
        points.append((probability, flow, phase, label))

    title = escape(outfall)
    if not points:
        return (
            '<section class="chart">'
            f'<p class="title">{title}</p>'
            '<p class="empty">No point with available probability and discharge.</p>'
            "</section>"
        )

    width = 760
    height = 440
    left = 82
    right = 28
    top = 28
    bottom = 68
    plot_width = width - left - right
    plot_height = height - top - bottom

    log_probabilities = [math.log10(probability) for probability, _, _, _ in points]
    reference_log = math.log10(REFERENCE_PROBABILITY)
    min_log_x = min(min(log_probabilities), reference_log)
    max_log_x = max(max(log_probabilities), reference_log)
    if min_log_x == max_log_x:
        min_log_x -= 0.5
        max_log_x += 0.5

    max_y = max(flow for _, flow, _, _ in points)
    for _, value in MEASURED_FLOW_REFERENCES_M3S.get(outfall, []):
        max_y = max(max_y, value)
    max_y = max(max_y, 1e-12) * 1.04

    def x_scale(probability: float) -> float:
        return left + (
            (math.log10(probability) - min_log_x) / (max_log_x - min_log_x)
        ) * plot_width

    def x_scale_log(log_value: float) -> float:
        return left + ((log_value - min_log_x) / (max_log_x - min_log_x)) * plot_width

    def y_scale(value: float) -> float:
        return top + plot_height - value / max_y * plot_height

    grid_elements = render_grid(
        left,
        top,
        plot_width,
        plot_height,
        width,
        height,
        min_log_x,
        max_log_x,
        max_y,
        x_scale,
        y_scale,
    )
    whisker_bins = build_probability_whiskers(points, min_log_x, max_log_x)
    whisker_elements = render_whiskers(whisker_bins, x_scale_log, y_scale)
    reference_elements = render_reference_elements(
        points,
        left,
        top,
        plot_width,
        plot_height,
        x_scale,
        y_scale,
    )
    measured_elements = render_measured_references(
        outfall,
        left,
        top,
        plot_width,
        plot_height,
        y_scale,
    )
    return "\n".join(
        [
            '<section class="chart">',
            f'<p class="title">{title}</p>',
            f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{title}">',
            *grid_elements,
            *whisker_elements,
            *measured_elements,
            f'<line class="axis" x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}"/>',
            f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}"/>',
            *reference_elements,
            f'<text class="label" x="{left + plot_width / 2:.1f}" y="{height - 10}" text-anchor="middle">Combination probability (log10)</text>',
            f'<text class="label" x="18" y="{top + plot_height / 2:.1f}" transform="rotate(-90 18 {top + plot_height / 2:.1f})" text-anchor="middle">Qmax (m3/s)</text>',
            '<text class="legend" x="{:.1f}" y="{:.1f}">box: Q1-Q3 | center: median | whiskers: min-max</text>'.format(left, top - 8),
            f'<title>{escape(hydrology)} - {title}</title>',
            "</svg>",
            "</section>",
        ]
    )


def render_phase_probability_svg(
    rows: list[dict[str, str]],
    outfall: str,
    hydrology: str,
) -> str:
    q_key = f"qmax_{slugify(outfall)}_m3s"
    phase_values: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        phase = row.get("phase", "") or ""
        probability = parse_optional_float(row.get("combination_probability"))
        flow = parse_optional_float(row.get(q_key))
        if not phase or probability is None or probability <= 0 or flow is None:
            continue
        phase_values.setdefault(phase, []).append((probability, flow))

    title = escape(outfall)
    if not phase_values:
        return (
            '<section class="chart">'
            f'<p class="title">{title}</p>'
            '<p class="empty">No point with available phase, probability and discharge.</p>'
            "</section>"
        )

    phases = sorted(phase_values, key=phase_sort_key)
    whiskers = build_phase_probability_whiskers(phase_values, phases)
    if not whiskers:
        return (
            '<section class="chart">'
            f'<p class="title">{title}</p>'
            '<p class="empty">No probability class contains data.</p>'
            "</section>"
        )

    width = max(980, 130 + len(phases) * 92)
    height = 500
    left = 82
    right = 28
    top = 34
    bottom = 112
    plot_width = width - left - right
    plot_height = height - top - bottom
    phase_step = plot_width / max(1, len(phases))

    max_y = max(item["maximum"] for item in whiskers)
    for _, value in MEASURED_FLOW_REFERENCES_M3S.get(outfall, []):
        max_y = max(max_y, value)
    max_y = max(max_y, 1e-12) * 1.04

    def phase_center(index: int) -> float:
        return left + phase_step * (index + 0.5)

    def y_scale(value: float) -> float:
        return top + plot_height - value / max_y * plot_height

    grid_elements = render_phase_grid(
        phases,
        left,
        top,
        plot_width,
        plot_height,
        width,
        height,
        phase_step,
        max_y,
        y_scale,
    )
    measured_elements = render_measured_references(
        outfall,
        left,
        top,
        plot_width,
        plot_height,
        y_scale,
    )
    whisker_elements = render_phase_whiskers(whiskers, phase_center, y_scale)
    legend_elements = render_phase_probability_legend(left, top)

    return "\n".join(
        [
            '<section class="chart">',
            f'<p class="title">{title}</p>',
            f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{title}">',
            *grid_elements,
            *measured_elements,
            f'<line class="axis" x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}"/>',
            f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}"/>',
            *whisker_elements,
            *legend_elements,
            f'<text class="label" x="{left + plot_width / 2:.1f}" y="{height - 12}" text-anchor="middle">Phase / sub-phase</text>',
            f'<text class="label" x="18" y="{top + plot_height / 2:.1f}" transform="rotate(-90 18 {top + plot_height / 2:.1f})" text-anchor="middle">Qmax (m3/s)</text>',
            f'<title>{escape(hydrology)} - {title}</title>',
            "</svg>",
            "</section>",
        ]
    )


def render_grid(
    left: float,
    top: float,
    plot_width: float,
    plot_height: float,
    width: float,
    height: float,
    min_log_x: float,
    max_log_x: float,
    max_y: float,
    x_scale,
    y_scale,
) -> list[str]:
    elements: list[str] = []
    for x_value in log_ticks(min_log_x, max_log_x):
        x = x_scale(x_value)
        elements.append(
            f'<line class="gridline" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}"/>'
        )
        elements.append(
            f'<text class="label" x="{x:.1f}" y="{height - 28}" text-anchor="middle">{format_probability_tick(x_value)}</text>'
        )

    for tick in range(6):
        y_value = max_y * tick / 5
        y = y_scale(y_value)
        elements.append(
            f'<line class="gridline" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>'
        )
        elements.append(
            f'<text class="label" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{y_value:.3g}</text>'
        )
    return elements


def render_phase_grid(
    phases: list[str],
    left: float,
    top: float,
    plot_width: float,
    plot_height: float,
    width: float,
    height: float,
    phase_step: float,
    max_y: float,
    y_scale,
) -> list[str]:
    elements: list[str] = []
    for tick in range(6):
        y_value = max_y * tick / 5
        y = y_scale(y_value)
        elements.append(
            f'<line class="gridline" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>'
        )
        elements.append(
            f'<text class="label" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{y_value:.3g}</text>'
        )

    for index, phase in enumerate(phases):
        center = left + phase_step * (index + 0.5)
        if index > 0:
            separator_x = left + phase_step * index
            elements.append(
                f'<line class="phase-separator" x1="{separator_x:.1f}" y1="{top}" '
                f'x2="{separator_x:.1f}" y2="{top + plot_height}"/>'
            )
        elements.append(
            f'<text class="phase-label" x="{center:.1f}" y="{height - 74}" '
            f'text-anchor="middle">{escape(format_phase_label(phase))}</text>'
        )
    return elements


def build_probability_whiskers(
    points: list[tuple[float, float, str, str]],
    min_log_x: float,
    max_log_x: float,
) -> list[tuple[float, float, float, float, float, float, int, float, float]]:
    if max_log_x == min_log_x:
        return []

    min_exponent = math.floor(min_log_x)
    max_exponent = math.floor(max_log_x)
    bins: dict[tuple[int, int], list[float]] = {}
    for probability, flow, _, _ in points:
        exponent = math.floor(math.log10(probability))
        normalized = probability / (10**exponent)
        mantissa = min(9, max(1, int(math.floor(normalized + 1e-12))))
        if min_exponent <= exponent <= max_exponent:
            bins.setdefault((exponent, mantissa), []).append(flow)

    whiskers: list[tuple[float, float, float, float, float, float, int, float, float]] = []
    for exponent in range(min_exponent, max_exponent + 1):
        for mantissa in range(1, 10):
            values = bins.get((exponent, mantissa), [])
            if not values:
                continue
            lower_probability = mantissa * 10**exponent
            upper_probability = (mantissa + 1) * 10**exponent
            center_probability = math.sqrt(lower_probability * upper_probability)
            center_log = math.log10(center_probability)
            if center_log < min_log_x or center_log > max_log_x:
                continue
            values = sorted(values)
            whiskers.append(
                (
                    center_log,
                    values[0],
                    quantile(values, 0.25),
                    quantile(values, 0.50),
                    quantile(values, 0.75),
                    values[-1],
                    len(values),
                    lower_probability,
                    upper_probability,
                )
            )
    return whiskers


def build_phase_probability_whiskers(
    phase_values: dict[str, list[tuple[float, float]]],
    phases: list[str],
) -> list[dict[str, object]]:
    whiskers: list[dict[str, object]] = []
    for phase_index, phase in enumerate(phases):
        values_by_bin: dict[int, list[float]] = {
            index: [] for index in range(len(PHASE_PROBABILITY_BINS))
        }
        for probability, flow in phase_values.get(phase, []):
            for bin_index, (_, lower, upper) in enumerate(PHASE_PROBABILITY_BINS):
                if lower <= probability < upper:
                    values_by_bin[bin_index].append(flow)
                    break

        for bin_index, values in values_by_bin.items():
            if not values:
                continue
            values = sorted(values)
            label, lower, upper = PHASE_PROBABILITY_BINS[bin_index]
            whiskers.append(
                {
                    "phase": phase,
                    "phase_index": phase_index,
                    "bin_index": bin_index,
                    "label": label,
                    "lower_probability": lower,
                    "upper_probability": upper,
                    "minimum": values[0],
                    "q1": quantile(values, 0.25),
                    "median": quantile(values, 0.50),
                    "q3": quantile(values, 0.75),
                    "maximum": values[-1],
                    "count": len(values),
                }
            )
    return whiskers


def render_whiskers(
    whiskers: list[tuple[float, float, float, float, float, float, int, float, float]],
    x_scale_log,
    y_scale,
) -> list[str]:
    if not whiskers:
        return []

    elements: list[str] = []
    for (
        center_log,
        minimum,
        q1,
        median_value,
        q3,
        maximum,
        count,
        lower_probability,
        upper_probability,
    ) in whiskers:
        x = x_scale_log(center_log)
        y_min = y_scale(minimum)
        y_q1 = y_scale(q1)
        y_median = y_scale(median_value)
        y_q3 = y_scale(q3)
        y_max = y_scale(maximum)
        box_top = min(y_q1, y_q3)
        box_height = max(2.0, abs(y_q3 - y_q1))
        half_width = 4.4
        cap_half_width = 7.0
        tooltip = escape(
            "Probability bin: "
            f"[{lower_probability:.2g}, {upper_probability:.2g})\n"
            f"n={count}\n"
            f"min={minimum:.6g} m3/s\n"
            f"Q1={q1:.6g} m3/s\n"
            f"median={median_value:.6g} m3/s\n"
            f"Q3={q3:.6g} m3/s\n"
            f"max={maximum:.6g} m3/s"
        )
        elements.extend(
            [
                (
                    f'<line class="whisker" x1="{x:.1f}" y1="{y_max:.1f}" '
                    f'x2="{x:.1f}" y2="{y_min:.1f}"><title>{tooltip}</title></line>'
                ),
                (
                    f'<line class="whisker-cap" x1="{x - cap_half_width:.1f}" y1="{y_max:.1f}" '
                    f'x2="{x + cap_half_width:.1f}" y2="{y_max:.1f}"><title>{tooltip}</title></line>'
                ),
                (
                    f'<line class="whisker-cap" x1="{x - cap_half_width:.1f}" y1="{y_min:.1f}" '
                    f'x2="{x + cap_half_width:.1f}" y2="{y_min:.1f}"><title>{tooltip}</title></line>'
                ),
                (
                    f'<rect class="box" x="{x - half_width:.1f}" y="{box_top:.1f}" '
                    f'width="{2 * half_width:.1f}" height="{box_height:.1f}"><title>{tooltip}</title></rect>'
                ),
                (
                    f'<line class="box-median" x1="{x - cap_half_width:.1f}" y1="{y_median:.1f}" '
                    f'x2="{x + cap_half_width:.1f}" y2="{y_median:.1f}"><title>{tooltip}</title></line>'
                ),
            ]
        )
    return elements


def render_phase_whiskers(whiskers: list[dict[str, object]], phase_center, y_scale) -> list[str]:
    elements: list[str] = []
    offsets = [-18.0, -6.0, 6.0, 18.0]
    for item in whiskers:
        phase_index = int(item["phase_index"])
        bin_index = int(item["bin_index"])
        x = phase_center(phase_index) + offsets[bin_index]
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
        half_width = 4.2
        cap_half_width = 6.2
        css_class = f"box bin-{bin_index}"
        tooltip = escape(
            f"Phase: {item['phase']}\n"
            f"Probability class: {item['label']} "
            f"[{float(item['lower_probability']):.0e}, {float(item['upper_probability']):.0e})\n"
            f"n={item['count']}\n"
            f"min={minimum:.6g} m3/s\n"
            f"Q1={q1:.6g} m3/s\n"
            f"median={median_value:.6g} m3/s\n"
            f"Q3={q3:.6g} m3/s\n"
            f"max={maximum:.6g} m3/s"
        )
        elements.extend(
            [
                (
                    f'<line class="whisker" x1="{x:.1f}" y1="{y_max:.1f}" '
                    f'x2="{x:.1f}" y2="{y_min:.1f}"><title>{tooltip}</title></line>'
                ),
                (
                    f'<line class="whisker-cap" x1="{x - cap_half_width:.1f}" y1="{y_max:.1f}" '
                    f'x2="{x + cap_half_width:.1f}" y2="{y_max:.1f}"><title>{tooltip}</title></line>'
                ),
                (
                    f'<line class="whisker-cap" x1="{x - cap_half_width:.1f}" y1="{y_min:.1f}" '
                    f'x2="{x + cap_half_width:.1f}" y2="{y_min:.1f}"><title>{tooltip}</title></line>'
                ),
                (
                    f'<rect class="{css_class}" x="{x - half_width:.1f}" y="{box_top:.1f}" '
                    f'width="{2 * half_width:.1f}" height="{box_height:.1f}"><title>{tooltip}</title></rect>'
                ),
                (
                    f'<line class="box-median" x1="{x - cap_half_width:.1f}" y1="{y_median:.1f}" '
                    f'x2="{x + cap_half_width:.1f}" y2="{y_median:.1f}"><title>{tooltip}</title></line>'
                ),
            ]
        )
    return elements


def render_phase_probability_legend(left: float, top: float) -> list[str]:
    elements = [
        f'<text class="legend" x="{left:.1f}" y="{top - 14:.1f}">box: Q1-Q3 | center: median | whiskers: min-max</text>'
    ]
    legend_x = left + 365
    for bin_index, (label, lower, upper) in enumerate(PHASE_PROBABILITY_BINS):
        x = legend_x + bin_index * 82
        elements.append(
            f'<rect class="box bin-{bin_index}" x="{x:.1f}" y="{top - 25:.1f}" width="12" height="12"/>'
        )
        elements.append(
            f'<text class="legend" x="{x + 17:.1f}" y="{top - 14:.1f}">{escape(label)}</text>'
        )
    return elements


def render_reference_elements(
    points: list[tuple[float, float, str, str]],
    left: float,
    top: float,
    plot_width: float,
    plot_height: float,
    x_scale,
    y_scale,
) -> list[str]:
    highest_probability, flow_at_highest_probability, phase, label = max(
        points,
        key=lambda item: item[0],
    )
    y = y_scale(flow_at_highest_probability)
    x = x_scale(REFERENCE_PROBABILITY)
    reference_label = format_probability_tick(REFERENCE_PROBABILITY)
    return [
        (
            f'<line class="reference-flow" x1="{left}" y1="{y:.1f}" '
            f'x2="{left + plot_width}" y2="{y:.1f}">'
            f'<title>Most probable case: phase={escape(phase)} ; {escape(label)} ; '
            f'P={highest_probability:.6g} ; Qmax={flow_at_highest_probability:.6g} m3/s</title>'
            "</line>"
        ),
        (
            f'<text class="reference-label" x="{left + plot_width - 4}" '
            f'y="{max(top + 14, y - 5):.1f}" text-anchor="end">'
            f'Q at P max = {flow_at_highest_probability:.3g}</text>'
        ),
        (
            f'<line class="reference-probability" x1="{x:.1f}" y1="{top}" '
            f'x2="{x:.1f}" y2="{top + plot_height}">'
            f"<title>Reference probability: {REFERENCE_PROBABILITY:.0e}</title></line>"
        ),
        (
            f'<text class="reference-label" x="{x + 4:.1f}" y="{top + 16}" '
            f'text-anchor="start">P={reference_label}</text>'
        ),
    ]


def render_measured_references(
    outfall: str,
    left: float,
    top: float,
    plot_width: float,
    plot_height: float,
    y_scale,
) -> list[str]:
    elements: list[str] = []
    for label, value in MEASURED_FLOW_REFERENCES_M3S.get(outfall, []):
        y = y_scale(value)
        if y < top or y > top + plot_height:
            continue
        css_class = {
            "measured min": "measured-min",
            "measured mean": "measured-mean",
            "measured max": "measured-max",
        }.get(label, "measured-mean")
        elements.append(
            f'<line class="{css_class}" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}">'
            f'<title>{escape(label)}: {value:.6g} m3/s</title></line>'
        )
        if value > 0:
            elements.append(
                f'<text class="measured-label" x="{left + 4}" y="{max(top + 14, y - 5):.1f}">'
                f'{escape(label)} = {value:.3g}</text>'
            )
    return elements


def log_ticks(min_log_x: float, max_log_x: float) -> list[float]:
    start = math.floor(min_log_x)
    end = math.ceil(max_log_x)
    ticks = [10**exponent for exponent in range(start, end + 1)]
    if len(ticks) >= 2:
        return ticks
    return [10 ** (min_log_x + (max_log_x - min_log_x) * tick / 4) for tick in range(5)]


def format_probability_tick(value: float) -> str:
    exponent = round(math.log10(value))
    if math.isclose(value, 10**exponent, rel_tol=1e-9, abs_tol=1e-15):
        return f"1e{exponent}"
    return f"{value:.2g}"


def parse_optional_float(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")


def phase_sort_key(phase: str) -> tuple[object, ...]:
    parts: list[object] = []
    for token in re.split(r"([0-9]+)", phase):
        if not token:
            continue
        parts.append(int(token) if token.isdigit() else token)
    return tuple(parts)


def format_phase_label(phase: str) -> str:
    match = re.match(r"^\d+_(.+)$", phase)
    return match.group(1) if match else phase


def median(values: list[float]) -> float:
    if not values:
        raise ValueError("median() requires at least one value")
    midpoint = len(values) // 2
    if len(values) % 2:
        return values[midpoint]
    return (values[midpoint - 1] + values[midpoint]) / 2


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("quantile() requires at least one value")
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return values[int(position)]
    lower_value = values[lower_index]
    upper_value = values[upper_index]
    return lower_value + (upper_value - lower_value) * (position - lower_index)


if __name__ == "__main__":
    raise SystemExit(main())
