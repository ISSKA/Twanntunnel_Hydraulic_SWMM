from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

from openpyxl import load_workbook


BASE_STATIONS_DIR = Path(
    r"O:\Projets en cours\SCIENCE\SP_Twann_tunnel\1_Data\0_MESURES_STATIONS"
)
OUTPUT_DIR = Path(
    r"O:\Projets en cours\SCIENCE\Sci.387_N05TWT_Appui_ISSKA_GG\1_PRODUCTION\SWMM\CALIBRATION"
)
FLOW_OUTPUT_FILE = OUTPUT_DIR / "TW_Calibration_Flow_m3s.txt"
LEVEL_OUTPUT_FILE = OUTPUT_DIR / "TW_Calibration_Level_depth.txt"
INP_FILE = Path(r"D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM\SWMM_Twannbach.inp")
MEASURES_2016_DIR = Path(
    r"O:\Projets en cours\SCIENCE\SP_Twann_tunnel\Sci291_Investigations_Avant_projet\2016\5_Mesures"
)
SONDIERSTOLLEN_FILE = MEASURES_2016_DIR / "Sondes_Sondierstollen_2016-2017.xlsx"
NODE_ALIASES = {
    "SS1": "Sondierstollen",
}


def parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        # Excel serial date, including the 1900 leap-year compatibility offset.
        return datetime(1899, 12, 30) + timedelta(days=float(value))

    text = str(value).strip()
    for fmt in (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    return None


def parse_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace("'", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def round_to_nearest_hour(date_time: datetime) -> datetime:
    rounded = date_time + timedelta(minutes=30)
    return rounded.replace(minute=0, second=0, microsecond=0)


def add_point(
    series: OrderedDict[str, dict[datetime, list[float]]],
    station: str,
    date_time: datetime,
    value: float,
) -> None:
    if station not in series:
        series[station] = defaultdict(list)
    series[station][round_to_nearest_hour(date_time)].append(value)


def iter_sheet_values(
    workbook_path: Path,
    sheet_name: str | int,
    date_column: int,
    value_column: int,
) -> Iterable[tuple[datetime, float]]:
    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        if isinstance(sheet_name, int):
            worksheet = workbook.worksheets[sheet_name]
        else:
            worksheet = workbook[sheet_name]

        max_column = max(date_column, value_column)
        for row in worksheet.iter_rows(min_row=2, max_col=max_column, values_only=True):
            date_time = parse_datetime(row[date_column - 1])
            value = parse_float(row[value_column - 1])
            if date_time is not None and value is not None:
                yield date_time, value
    finally:
        workbook.close()


def add_excel_series(
    series: OrderedDict[str, dict[datetime, list[float]]],
    workbook_path: Path,
    station: str,
    date_column: int,
    value_column: int,
    convert_value: Callable[[float], float],
    sheet_name: str | int = 0,
) -> None:
    for date_time, raw_value in iter_sheet_values(
        workbook_path, sheet_name, date_column, value_column
    ):
        add_point(series, station, date_time, convert_value(raw_value))


def read_swmm_node_elevations(inp_file: Path) -> dict[str, float]:
    elevations: dict[str, float] = {}
    section = ""

    for line in inp_file.read_text(encoding="cp1252").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[]")
            continue
        if section not in {"JUNCTIONS", "OUTFALLS"}:
            continue
        if not stripped or stripped.startswith(";"):
            continue

        parts = stripped.split()
        if len(parts) >= 2:
            elevations[parts[0]] = float(parts[1])

    return elevations


def node_elevation(elevations: dict[str, float], station: str) -> float:
    node_name = NODE_ALIASES.get(station, station)
    try:
        return elevations[node_name]
    except KeyError as exc:
        raise KeyError(
            f"Altitude du noeud {node_name!r} introuvable dans {INP_FILE} "
            f"pour la station {station!r}"
        ) from exc


def hourly_average(
    series: OrderedDict[str, dict[datetime, list[float]]],
    station: str,
    hour: datetime,
) -> float | None:
    if station not in series or hour not in series[station]:
        return None

    values = series[station][hour]
    return sum(values) / len(values)


def twannbach_oben_level_to_flow(level: float) -> float:
    flow_lps = (
        113759.0 * level**5
        - 182008.0 * level**4
        + 104604.0 * level**3
        - 20741.0 * level**2
        + 1430.1 * level
    )
    return flow_lps / 1000.0


def add_wasserhooliloch_flow(
    flow_series: OrderedDict[str, dict[datetime, list[float]]],
    derived_inputs: OrderedDict[str, dict[datetime, list[float]]],
) -> None:
    target_station = "Hooliloch_L"

    for hour in sorted(derived_inputs["Twannbach_Unten"]):
        q_unten = hourly_average(derived_inputs, "Twannbach_Unten", hour)
        q_oben = hourly_average(derived_inputs, "Twannbach_Oben", hour)
        q_fenster = hourly_average(derived_inputs, "Fensterstollen", hour)

        if q_unten is None or q_oben is None or q_fenster is None:
            continue

        q_wasserhooliloch = q_unten - (q_oben + q_fenster)
        if q_wasserhooliloch < 0:
            continue

        add_point(flow_series, target_station, hour, q_wasserhooliloch)


def find_schuettstein_file() -> Path:
    matches = sorted(
        list(MEASURES_2016_DIR.glob("Sondes_Schutstein_Gischeren.xlsx"))
        + list(MEASURES_2016_DIR.glob("Sonde_Sch*tstein.xlsx"))
    )
    if not matches:
        raise FileNotFoundError(
            f"Fichier Sonde_Sch*tstein.xlsx introuvable dans {MEASURES_2016_DIR}"
        )
    return matches[0]


def format_number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def write_calibration_file(
    output_file: Path, series: OrderedDict[str, dict[datetime, list[float]]]
) -> None:
    lines = ["; Calibration files"]

    for station, hourly_values in series.items():
        lines.append(station)
        for hour in sorted(hourly_values):
            values = hourly_values[hour]
            average = sum(values) / len(values)
            lines.append(
                "\t".join(
                    (
                        "",
                        hour.strftime("%m/%d/%Y"),
                        hour.strftime("%H:%M:%S"),
                        format_number(average),
                    )
                )
            )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines) + "\n", encoding="cp1252")


def main() -> None:
    series_by_metric: OrderedDict[
        str, OrderedDict[str, dict[datetime, list[float]]]
    ] = OrderedDict(
        (
            ("Flow", OrderedDict()),
            ("Level", OrderedDict()),
        )
    )
    derived_inputs: OrderedDict[str, dict[datetime, list[float]]] = OrderedDict()
    node_elevations = read_swmm_node_elevations(INP_FILE)

    hourly_stations = (
        ("Brunnmuehle_Quelle", "Brunn_Teich_L", "Flow", 0.001),
        ("Entwaesserungstollen", "Entw_Sto_L", "Flow", 0.001),
        ("Fensterstollen", "Fenster_L", "Flow", 0.001),
        ("Wasserhooliloch_Sonde_2", "Holiloch_sonde", "Level", 1.0),
    )

    for source_station, target_station, metric, factor in hourly_stations:
        workbook_path = (
            BASE_STATIONS_DIR
            / source_station
            / f"{source_station}_hour_avrg.xlsx"
        )
        elevation = node_elevation(node_elevations, target_station) if metric == "Level" else 0.0
        add_excel_series(
            series_by_metric[metric],
            workbook_path,
            target_station,
            date_column=1,
            value_column=2,
            convert_value=lambda value, factor=factor, elevation=elevation: value
            * factor
            - elevation,
        )
        if source_station == "Fensterstollen":
            add_excel_series(
                derived_inputs,
                workbook_path,
                "Fensterstollen",
                date_column=1,
                value_column=2,
                convert_value=lambda value, factor=factor: value * factor,
            )

    add_excel_series(
        derived_inputs,
        BASE_STATIONS_DIR / "Twannbach_Unten" / "Twannbach_Unten_hour_avrg.xlsx",
        "Twannbach_Unten",
        date_column=1,
        value_column=2,
        convert_value=lambda value: value,
    )
    add_excel_series(
        derived_inputs,
        BASE_STATIONS_DIR / "Twannbach_Oben" / "Twannbach_Oben_hour_avrg.xlsx",
        "Twannbach_Oben",
        date_column=1,
        value_column=2,
        convert_value=twannbach_oben_level_to_flow,
    )
    add_wasserhooliloch_flow(series_by_metric["Flow"], derived_inputs)

    mbar_to_meter = 1.0 / 98.0665
    sondierstollen_sheets = {
        "SS1": (2, 3, 443.0),
        "SS4": (3, 5, 442.0),
        "SS5": (9, 11, 438.9),
        "SS6": (3, 5, 442.0),
    }

    for station, (date_column, value_column, altitude) in sondierstollen_sheets.items():
        elevation = node_elevation(node_elevations, station)
        add_excel_series(
            series_by_metric["Level"],
            SONDIERSTOLLEN_FILE,
            station,
            date_column=date_column,
            value_column=value_column,
            convert_value=lambda value, altitude=altitude, elevation=elevation: altitude
            + value * mbar_to_meter
            - elevation,
            sheet_name=station,
        )

    schuettstein_file = find_schuettstein_file()
    schuettstein_elevation = node_elevation(node_elevations, "SondeSchuettstein")
    add_excel_series(
        series_by_metric["Level"],
        schuettstein_file,
        "SondeSchuettstein",
        date_column=3,
        value_column=9,
        convert_value=lambda value: value - schuettstein_elevation,
    )
    gischeren_elevation = node_elevation(node_elevations, "SondeGischeren")
    add_excel_series(
        series_by_metric["Level"],
        schuettstein_file,
        "SondeGischeren",
        date_column=14,
        value_column=15,
        convert_value=lambda value: value - gischeren_elevation,
    )

    write_calibration_file(FLOW_OUTPUT_FILE, series_by_metric["Flow"])
    write_calibration_file(LEVEL_OUTPUT_FILE, series_by_metric["Level"])

    for metric, series in series_by_metric.items():
        for station, hourly_values in series.items():
            print(f"{metric} - {station}: {len(hourly_values)} valeurs horaires")
    print(f"Fichier debits ecrit: {FLOW_OUTPUT_FILE}")
    print(f"Fichier hauteurs ecrit: {LEVEL_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
