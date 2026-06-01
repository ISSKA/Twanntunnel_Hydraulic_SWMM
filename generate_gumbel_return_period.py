from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from pathlib import Path


INPUT_FILE = Path(
    r"O:\Projets en cours\SCIENCE\Sci.387_N05TWT_Appui_ISSKA_GG\1_PRODUCTION\SWMM\INPUT\Discharge_Input_SWMM.txt"
)
OUTPUT_HTML = INPUT_FILE.with_name("Discharge_Input_SWMM_Gumbel.html")
OUTPUT_CSV = INPUT_FILE.with_name("Discharge_Input_SWMM_Gumbel_values.csv")

TARGET_RETURN_PERIODS = [0.5, 1, 2, 3, 5, 10, 30, 100]
EULER_GAMMA = 0.5772156649015329


@dataclass(frozen=True)
class FlowRecord:
    date: datetime
    flow: float


@dataclass(frozen=True)
class EmpiricalPoint:
    rank: int
    year: int
    date: datetime
    flow: float
    return_period: float


@dataclass(frozen=True)
class LinearFit:
    intercept: float
    slope: float

    def predict(self, x: float) -> float:
        return self.intercept + self.slope * x


def read_timeseries(path: Path) -> list[FlowRecord]:
    records: list[FlowRecord] = []

    with path.open("r", encoding="mbcs") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue

            date_text, time_text, value_text = line.split(maxsplit=2)
            date = datetime.strptime(f"{date_text} {time_text}", "%m/%d/%Y %H:%M")
            records.append(FlowRecord(date=date, flow=float(value_text)))

    return sorted(records, key=lambda record: record.date)


def annual_maxima(records: list[FlowRecord]) -> list[FlowRecord]:
    by_year: dict[int, FlowRecord] = {}

    for record in records:
        current = by_year.get(record.date.year)
        if current is None or record.flow > current.flow:
            by_year[record.date.year] = record

    return sorted(by_year.values(), key=lambda record: record.flow, reverse=True)


def empirical_points(maxima: list[FlowRecord]) -> list[EmpiricalPoint]:
    count = len(maxima)
    points: list[EmpiricalPoint] = []

    for rank, record in enumerate(maxima, start=1):
        # Gringorten exceedance plotting position; rank 1 is the largest annual maximum.
        exceedance_probability = (rank - 0.44) / (count + 0.12)
        return_period = 1.0 / exceedance_probability
        points.append(
            EmpiricalPoint(
                rank=rank,
                year=record.date.year,
                date=record.date,
                flow=record.flow,
                return_period=return_period,
            )
        )

    return points


def linear_fit(x_values: list[float], y_values: list[float]) -> LinearFit:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        raise ValueError("Regression impossible: nombre de points insuffisant.")

    count = len(x_values)
    sum_x = sum(x_values)
    sum_y = sum(y_values)
    sum_xx = sum(x * x for x in x_values)
    sum_xy = sum(x * y for x, y in zip(x_values, y_values))

    denominator = count * sum_xx - sum_x * sum_x
    if abs(denominator) < 1e-12:
        raise ValueError("Regression impossible: valeurs X degeneres.")

    slope = (count * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / count
    return LinearFit(intercept=intercept, slope=slope)


def sample_std(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def gumbel_flow(return_period: float, mean: float, std_dev: float) -> float | None:
    if return_period <= 1.0:
        return None

    alpha = std_dev * math.sqrt(6.0) / math.pi
    mode = mean - EULER_GAMMA * alpha
    probability = 1.0 - 1.0 / return_period
    reduced_variate = -math.log(-math.log(probability))
    return mode + alpha * reduced_variate


def occurrence_ranges(
    records: list[FlowRecord],
    threshold: float,
) -> list[tuple[datetime, datetime]]:
    exceedances = [record.date for record in records if record.flow >= threshold]
    if not exceedances:
        return []

    ranges: list[tuple[datetime, datetime]] = []
    start = exceedances[0]
    previous = exceedances[0]

    for current in exceedances[1:]:
        if current - previous > timedelta(hours=1, minutes=6):
            ranges.append((start, previous))
            start = current
        previous = current

    ranges.append((start, previous))
    return ranges


def format_ranges(ranges: list[tuple[datetime, datetime]]) -> str:
    return " ; ".join(
        f"{start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M}"
        for start, end in ranges
    )


def build_results(
    records: list[FlowRecord],
    points: list[EmpiricalPoint],
    mean: float,
    std_dev: float,
    log_fit: LinearFit,
    exp_fit: LinearFit,
) -> list[dict[str, object]]:
    max_measured_t = max(point.return_period for point in points)
    results: list[dict[str, object]] = []

    for target in TARGET_RETURN_PERIODS:
        gumbel_q = gumbel_flow(target, mean, std_dev)
        log_q = log_fit.predict(math.log(target))
        exp_q = math.exp(exp_fit.predict(math.log(target)))
        closest = min(points, key=lambda point: abs(point.return_period - target))
        is_measured = 1.0 <= target <= max_measured_t
        reference_q = gumbel_q if gumbel_q is not None else log_q
        ranges = occurrence_ranges(records, reference_q) if is_measured else []

        if target < 1.0:
            status = "non_standard"
        elif is_measured:
            status = "measured_range"
        else:
            status = "extrapolated"

        results.append(
            {
                "ReturnPeriodYears": target,
                "Status": status,
                "GumbelFlowM3s": gumbel_q,
                "LogFlowM3s": log_q,
                "ExpFlowM3s": exp_q,
                "ClosestObservedReturnPeriodYears": closest.return_period,
                "ClosestObservedFlowM3s": closest.flow,
                "ClosestObservedDate": closest.date,
                "OccurrenceRanges": format_ranges(ranges),
            }
        )

    return results


def write_csv(path: Path, results: list[dict[str, object]]) -> None:
    fieldnames = [
        "ReturnPeriodYears",
        "Status",
        "GumbelFlowM3s",
        "LogFlowM3s",
        "ExpFlowM3s",
        "ClosestObservedReturnPeriodYears",
        "ClosestObservedFlowM3s",
        "ClosestObservedDate",
        "OccurrenceRanges",
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for result in results:
            row = dict(result)
            row["GumbelFlowM3s"] = "" if row["GumbelFlowM3s"] is None else f"{row['GumbelFlowM3s']:.9f}"
            row["LogFlowM3s"] = f"{row['LogFlowM3s']:.9f}"
            row["ExpFlowM3s"] = f"{row['ExpFlowM3s']:.9f}"
            row["ClosestObservedReturnPeriodYears"] = f"{row['ClosestObservedReturnPeriodYears']:.3f}"
            row["ClosestObservedFlowM3s"] = f"{row['ClosestObservedFlowM3s']:.9f}"
            row["ClosestObservedDate"] = row["ClosestObservedDate"].strftime("%Y-%m-%d %H:%M")
            writer.writerow(row)


def svg_path(
    return_periods: list[float],
    predictor,
    x_position,
    y_position,
) -> str:
    points: list[str] = []
    for return_period in return_periods:
        flow = predictor(return_period)
        if flow is not None:
            points.append(f"{x_position(return_period):.2f} {y_position(flow):.2f}")
    return "M " + " L ".join(points)


def write_html(
    path: Path,
    input_file: Path,
    records: list[FlowRecord],
    points: list[EmpiricalPoint],
    results: list[dict[str, object]],
    mean: float,
    std_dev: float,
    log_fit: LinearFit,
    exp_fit: LinearFit,
) -> None:
    max_measured_t = max(point.return_period for point in points)

    dense_t = [
        math.exp(math.log(1.0) + (math.log(100.0) - math.log(1.0)) * index / 160)
        for index in range(161)
    ]
    plot_points = [(point.return_period, point.flow) for point in points]
    for return_period in dense_t:
        gumbel_q = gumbel_flow(return_period, mean, std_dev)
        if gumbel_q is not None:
            plot_points.append((return_period, gumbel_q))
        plot_points.append((return_period, log_fit.predict(math.log(return_period))))
        plot_points.append((return_period, math.exp(exp_fit.predict(math.log(return_period)))))

    min_t = 1.0
    max_t = 100.0
    min_q = max(0.0, min(flow for _, flow in plot_points) * 0.95)
    max_q = max(flow for _, flow in plot_points) * 1.05
    q_range = max(max_q - min_q, 0.000001)
    ln_min_t = math.log(min_t)
    ln_max_t = math.log(max_t)

    width = 1450
    height = 900
    left = 95
    right = 45
    top = 60
    bottom = 120
    plot_width = width - left - right
    plot_height = height - top - bottom

    def x_position(return_period: float) -> float:
        return left + ((math.log(return_period) - ln_min_t) / (ln_max_t - ln_min_t)) * plot_width

    def y_position(flow: float) -> float:
        return top + ((max_q - flow) / q_range) * plot_height

    gumbel_path = svg_path(
        dense_t,
        lambda t: gumbel_flow(t, mean, std_dev),
        x_position,
        y_position,
    )
    log_path = svg_path(
        dense_t,
        lambda t: log_fit.predict(math.log(t)),
        x_position,
        y_position,
    )
    exp_path = svg_path(
        dense_t,
        lambda t: math.exp(exp_fit.predict(math.log(t))),
        x_position,
        y_position,
    )

    empirical_points = "\n".join(
        f'<circle cx="{x_position(point.return_period):.2f}" cy="{y_position(point.flow):.2f}" '
        f'r="5.5" fill="#111827"><title>{point.date:%Y-%m-%d %H:%M}: '
        f'T={point.return_period:.2f} ans, Q={point.flow:.3f} m3/s</title></circle>'
        for point in points
    )

    x_ticks = "\n".join(
        f'<line x1="{x_position(t):.2f}" y1="{top}" x2="{x_position(t):.2f}" '
        f'y2="{top + plot_height}" stroke="#e5e7eb" />'
        f'<text x="{x_position(t):.2f}" y="{top + plot_height + 32}" text-anchor="middle">T{t:g}</text>'
        for t in [1, 2, 3, 5, 10, 30, 100]
    )
    y_ticks = "\n".join(
        f'<line x1="{left}" y1="{y_position(q):.2f}" x2="{left + plot_width}" '
        f'y2="{y_position(q):.2f}" stroke="#e5e7eb" />'
        f'<text x="{left - 12}" y="{y_position(q) + 4:.2f}" text-anchor="end">{q:.3f}</text>'
        for q in [min_q + q_range * index / 6 for index in range(7)]
    )
    target_lines = "\n".join(
        f'<line x1="{x_position(result["ReturnPeriodYears"]):.2f}" y1="{top}" '
        f'x2="{x_position(result["ReturnPeriodYears"]):.2f}" y2="{top + plot_height}" '
        f'stroke="#9ca3af" stroke-dasharray="4 5" />'
        for result in results
        if result["ReturnPeriodYears"] >= 1.0
    )

    result_row_parts: list[str] = []
    for result in results:
        gumbel = result["GumbelFlowM3s"]
        gumbel_text = "n/a" if gumbel is None else f"{gumbel:.3f}"
        result_row_parts.append(
            "<tr>"
            f"<td>T{result['ReturnPeriodYears']:g}</td>"
            f"<td>{result['Status']}</td>"
            f"<td>{gumbel_text}</td>"
            f"<td>{result['LogFlowM3s']:.3f}</td>"
            f"<td>{result['ExpFlowM3s']:.3f}</td>"
            f"<td>{result['ClosestObservedDate']:%Y-%m-%d %H:%M}</td>"
            f"<td>{escape(str(result['OccurrenceRanges']))}</td>"
            "</tr>"
        )
    result_rows = "\n".join(result_row_parts)

    annual_rows = "\n".join(
        f"<tr><td>{point.year}</td><td>{point.date:%Y-%m-%d %H:%M}</td>"
        f"<td>{point.flow:.3f}</td><td>{point.return_period:.3f}</td></tr>"
        for point in sorted(points, key=lambda point: point.year)
    )

    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Courbe Gumbel - Discharge Input SWMM</title>
<style>
body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: #172033; background: #f7f8fb; }}
main {{ max-width: 1560px; margin: 0 auto; padding: 28px 34px 44px; }}
h1 {{ margin: 0 0 8px; font-size: 24px; }}
h2 {{ margin: 28px 0 10px; font-size: 18px; }}
.meta {{ margin-bottom: 18px; line-height: 1.55; color: #4b5563; font-size: 14px; }}
.figure {{ background: white; border: 1px solid #d9dee8; border-radius: 8px; padding: 18px; }}
svg {{ width: 100%; height: auto; display: block; }}
text {{ font-size: 14px; fill: #374151; }}
.axis-title {{ font-size: 16px; font-weight: 700; fill: #172033; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 22px; align-items: center; margin-top: 14px; font-size: 14px; color: #374151; }}
.swatch {{ width: 34px; height: 4px; display: inline-block; margin-right: 8px; vertical-align: 3px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; background: white; border: 1px solid #d9dee8; }}
th, td {{ padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; font-size: 13px; vertical-align: top; }}
th {{ background: #eef2f7; }}
.note {{ margin-top: 12px; font-size: 13px; color: #4b5563; line-height: 1.5; }}
</style>
</head>
<body>
<main>
<h1>Courbe de Gumbel - Discharge_Input_SWMM</h1>
<div class="meta">
Fichier source: {escape(str(input_file))}<br>
Maxima annuels utilises: {len(points)}<br>
Moyenne des maxima annuels: {mean:.3f} m3/s; ecart-type: {std_dev:.3f} m3/s<br>
Temps de retour empirique maximal: {max_measured_t:.3f} ans
</div>
<div class="figure">
<svg viewBox="0 0 {width} {height}" role="img" aria-label="Courbe Gumbel des debits">
<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />
<g>
{x_ticks}
{y_ticks}
{target_lines}
<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#172033" stroke-width="1.2" />
<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#172033" stroke-width="1.2" />
<text class="axis-title" x="{left + plot_width / 2}" y="{height - 35}" text-anchor="middle">Temps de retour [annees] - axe logarithmique</text>
<text class="axis-title" x="24" y="{top + plot_height / 2}" transform="rotate(-90 24 {top + plot_height / 2})" text-anchor="middle">Debit [m3/s]</text>
</g>
<path d="{gumbel_path}" fill="none" stroke="#1f6feb" stroke-width="2.4" />
<path d="{log_path}" fill="none" stroke="#059669" stroke-width="2" stroke-dasharray="8 6" />
<path d="{exp_path}" fill="none" stroke="#dc2626" stroke-width="2" stroke-dasharray="3 5" />
<g>
{empirical_points}
</g>
</svg>
<div class="legend">
<span><span class="swatch" style="background:#111827; height:10px; border-radius:50%; width:10px"></span>Maxima annuels observes</span>
<span><span class="swatch" style="background:#1f6feb"></span>Gumbel</span>
<span><span class="swatch" style="background:#059669"></span>Extrapolation logarithmique</span>
<span><span class="swatch" style="background:#dc2626"></span>Extrapolation exponentielle</span>
</div>
</div>
<p class="note">T0.5 est non standard pour une analyse de maxima annuels avec definition classique T = 1 / P(exceedance annuelle). Les valeurs Gumbel ne sont donc calculees qu'a partir de T &gt; 1.</p>
<h2>Valeurs demandees</h2>
<table>
<thead><tr><th>Temps de retour</th><th>Statut</th><th>Gumbel Q [m3/s]</th><th>Log Q [m3/s]</th><th>Exp Q [m3/s]</th><th>Observation proche</th><th>Plages ou Q >= Q_Gumbel</th></tr></thead>
<tbody>
{result_rows}
</tbody>
</table>
<h2>Maxima annuels observes</h2>
<table>
<thead><tr><th>Annee</th><th>Date du maximum</th><th>Q max [m3/s]</th><th>T empirique [ans]</th></tr></thead>
<tbody>
{annual_rows}
</tbody>
</table>
</main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def main() -> None:
    records = read_timeseries(INPUT_FILE)
    if not records:
        raise RuntimeError(f"Aucune donnee lue dans {INPUT_FILE}")

    maxima = annual_maxima(records)
    if len(maxima) < 3:
        raise RuntimeError("Il faut au moins 3 maxima annuels pour ajuster une courbe.")

    points = empirical_points(maxima)
    flows = [record.flow for record in maxima]
    mean = sum(flows) / len(flows)
    std_dev = sample_std(flows)

    fit_points = [point for point in points if point.return_period > 1.0]
    log_t = [math.log(point.return_period) for point in fit_points]
    fit_q = [point.flow for point in fit_points]
    log_fit = linear_fit(log_t, fit_q)
    positive_fit_points = [point for point in fit_points if point.flow > 0]
    exp_fit = linear_fit(
        [math.log(point.return_period) for point in positive_fit_points],
        [math.log(point.flow) for point in positive_fit_points],
    )

    results = build_results(records, points, mean, std_dev, log_fit, exp_fit)
    write_csv(OUTPUT_CSV, results)
    write_html(OUTPUT_HTML, INPUT_FILE, records, points, results, mean, std_dev, log_fit, exp_fit)

    print(f"HTML: {OUTPUT_HTML}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"Maxima annuels: {len(points)}")
    print(f"Temps de retour empirique max: {max(point.return_period for point in points):.3f} ans")
    for result in results:
        gumbel = result["GumbelFlowM3s"]
        gumbel_text = "n/a" if gumbel is None else f"{gumbel:.3f}"
        print(
            f"T{result['ReturnPeriodYears']:g}: {result['Status']} | "
            f"Gumbel={gumbel_text} | "
            f"Log={result['LogFlowM3s']:.3f} | "
            f"Exp={result['ExpFlowM3s']:.3f}"
        )


if __name__ == "__main__":
    main()
