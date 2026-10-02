from __future__ import annotations

import argparse
import csv
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from run_swmm_mass_computation import (
    format_row,
    import_optional,
    parse_optional_float,
    read_object_series,
    read_sections,
    resolve_node_attribute,
    run_swmm,
    section_body_range,
    split_data_line,
    stable_node_peak,
    unlink_with_retries,
    write_results_csv,
    write_text_with_retries,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
MASS_DIR = Path(__file__).resolve().parent
DEFAULT_SCENARIOS = MASS_DIR / "scenarios_CentraleVentilation.txt"
DEFAULT_COORDINATES = ROOT_DIR / "260508_Coord_nodes_SWMM.xlsx"
DEFAULT_SOURCE_RUNS = MASS_DIR / "runs" / "scenario1"
DEFAULT_OUTPUT_DIR = MASS_DIR / "runs" / "CV_scenario_1"
SOURCE_PHASE = "1_8a"
SOURCE_SCENARIO = "scenario1"
RESULTS_CSV = "CV_scenario_1_discharge_results.csv"


@dataclass(frozen=True)
class CVHydrology:
    name: str
    flow_m3s: float


@dataclass(frozen=True)
class CVConnection:
    variant: str
    name: str
    target: str | None
    probability: float
    roughness: float
    diameter: float
    shape: str
    no_connection: bool = False


@dataclass(frozen=True)
class CVConfig:
    source_scenario: str
    output_run_dir: str
    hydrologies: dict[str, CVHydrology]
    control_node: str
    control_elevation: float
    control_max_depth: float
    connections: list[CVConnection]


@dataclass(frozen=True)
class CVCase:
    index: int
    hydrology: str
    source_simulation_id: str
    source_case_dir: Path
    source_inp: Path
    base_variant_combination: str
    base_probability: float | None
    connection: CVConnection
    connection_length: float
    combined_probability: float | None


@dataclass(frozen=True)
class CVRunResult:
    index: int
    total: int
    simulation_id: str
    message: str
    row: dict[str, object] | None


def main() -> int:
    args = parse_args()
    config = parse_cv_scenarios(args.scenarios)
    coordinates = read_coordinate_table(args.coordinates)
    validate_coordinate_table(coordinates, config)
    source_runs = args.source_runs or MASS_DIR / "runs" / config.source_scenario
    output_dir = args.output_dir or MASS_DIR / "runs" / config.output_run_dir

    cases = build_cases(
        config=config,
        coordinates=coordinates,
        source_runs=source_runs,
        output_dir=output_dir,
    )
    if args.limit is not None:
        cases = cases[: args.limit]
    print(f"{len(cases)} simulations CentraleVentilation preparees.")
    if args.dry_run:
        for case in cases[:10]:
            print(
                f"  {case.hydrology} {case.source_simulation_id} "
                f"{case.connection.variant} ({case.connection.name}) "
                f"L={case.connection_length:.1f} m"
            )
        if len(cases) > 10:
            print(f"  ... {len(cases) - 10} autres simulations")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    workers = max(1, args.workers)
    if workers == 1:
        for case in cases:
            result = run_cv_case(case, len(cases), config, output_dir, args.engine)
            print(result.message)
            if result.row is not None:
                rows.append(result.row)
    else:
        print(f"Execution parallele: {workers} workers.")
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(
                    run_cv_case,
                    case,
                    len(cases),
                    config,
                    output_dir,
                    args.engine,
                )
                for case in cases
            ]
            for future in as_completed(futures):
                result = future.result()
                print(result.message)
                if result.row is not None:
                    rows.append(result.row)

    rows.sort(key=lambda row: int(str(row["simulation_id"]).split("_")[-1]))
    results_path = output_dir / RESULTS_CSV
    rows = merge_with_existing_hydrologies(results_path, rows)
    write_results_csv(results_path, rows)
    print(f"CSV ecrit: {results_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simule les debits a CentraleVentilation_1C depuis les runs 1_8a."
    )
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--coordinates", type=Path, default=DEFAULT_COORDINATES)
    parser.add_argument("--source-runs", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--engine", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def parse_cv_scenarios(path: Path) -> CVConfig:
    source_scenario = SOURCE_SCENARIO
    output_run_dir = DEFAULT_OUTPUT_DIR.name
    hydrologies: dict[str, CVHydrology] = {}
    control_node = "CentraleVentilation_1C"
    control_elevation = 454.0
    control_max_depth = 200.0
    default_roughness = 0.05
    default_diameter = 0.5
    default_shape = "CIRCULAR"
    connections: list[CVConnection] = []

    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = strip_comment(raw_line)
            if not line:
                continue
            tokens = line.split()
            keyword = tokens[0].lower()
            values = parse_key_values(tokens[1:])

            if keyword == "constant_flow":
                if len(tokens) < 3:
                    raise ValueError(f"Ligne {line_number}: constant_flow nom debit.")
                hydrologies[tokens[1]] = CVHydrology(tokens[1], float(tokens[2]))
            elif keyword == "source_scenario":
                if len(tokens) < 2:
                    raise ValueError(f"Ligne {line_number}: source_scenario nom requis.")
                source_scenario = tokens[1]
            elif keyword == "output_run_dir":
                if len(tokens) < 2:
                    raise ValueError(f"Ligne {line_number}: output_run_dir nom requis.")
                output_run_dir = tokens[1]
            elif keyword == "control_node":
                if len(tokens) < 2:
                    raise ValueError(f"Ligne {line_number}: control_node nom requis.")
                control_node = tokens[1]
                control_elevation = float(values.get("elevation", control_elevation))
                control_max_depth = float(values.get("max_depth", control_max_depth))
            elif keyword == "connection_defaults":
                default_roughness = float(values.get("roughness", default_roughness))
                default_diameter = float(values.get("diameter", default_diameter))
                default_shape = values.get("shape", default_shape)
            elif keyword == "connection":
                if len(tokens) < 2:
                    raise ValueError(f"Ligne {line_number}: connection nom requis.")
                connections.append(
                    build_connection(
                        line_number=line_number,
                        variant=values.get("variant", tokens[1]),
                        name=tokens[1],
                        values=values,
                        default_roughness=default_roughness,
                        default_diameter=default_diameter,
                        default_shape=default_shape,
                    )
                )
            elif keyword == "variant":
                if len(tokens) >= 3 and tokens[2].lower() == "no_connection":
                    values = parse_key_values(tokens[3:])
                    connections.append(
                        build_no_connection(
                            line_number=line_number,
                            variant=tokens[1],
                            values=values,
                        )
                    )
                elif len(tokens) < 4 or tokens[2].lower() != "connection":
                    raise ValueError(
                        f"Ligne {line_number}: format attendu: "
                        "variant <nom_variante> connection <nom_conduit> target=... prob=... "
                        "ou variant <nom_variante> no_connection prob=residual"
                    )
                else:
                    values = parse_key_values(tokens[4:])
                    connections.append(
                        build_connection(
                            line_number=line_number,
                            variant=tokens[1],
                            name=tokens[3],
                            values=values,
                            default_roughness=default_roughness,
                            default_diameter=default_diameter,
                            default_shape=default_shape,
                        )
                    )
            else:
                raise ValueError(f"Ligne {line_number}: mot-cle inconnu '{tokens[0]}'.")

    if not hydrologies:
        raise ValueError("Aucune hydrologie declaree dans scenarios_CentraleVentilation.txt.")
    if not connections:
        raise ValueError("Aucune connexion declaree dans scenarios_CentraleVentilation.txt.")

    return CVConfig(
        source_scenario=source_scenario,
        output_run_dir=output_run_dir,
        hydrologies=hydrologies,
        control_node=control_node,
        control_elevation=control_elevation,
        control_max_depth=control_max_depth,
        connections=resolve_residual_probabilities(connections),
    )


def build_connection(
    line_number: int,
    variant: str,
    name: str,
    values: dict[str, str],
    default_roughness: float,
    default_diameter: float,
    default_shape: str,
) -> CVConnection:
    target = values.get("target")
    probability = values.get("prob")
    if target is None or probability is None:
        raise ValueError(
            f"Ligne {line_number}: connection requiert target=... et prob=..."
        )
    return CVConnection(
        variant=variant,
        name=name,
        target=target,
        probability=float(probability),
        roughness=float(values.get("roughness", default_roughness)),
        diameter=float(values.get("diameter", default_diameter)),
        shape=values.get("shape", default_shape),
    )


def build_no_connection(
    line_number: int,
    variant: str,
    values: dict[str, str],
) -> CVConnection:
    probability = values.get("prob", "residual").lower()
    if probability == "residual":
        probability_value = math.nan
    else:
        probability_value = float(probability)
    return CVConnection(
        variant=variant,
        name="NO_CONNECTION",
        target=None,
        probability=probability_value,
        roughness=0.0,
        diameter=0.0,
        shape="",
        no_connection=True,
    )


def resolve_residual_probabilities(connections: list[CVConnection]) -> list[CVConnection]:
    explicit_probability = sum(
        connection.probability
        for connection in connections
        if not math.isnan(connection.probability)
    )
    residual_connections = [
        connection for connection in connections if math.isnan(connection.probability)
    ]
    if not residual_connections:
        return connections
    if len(residual_connections) > 1:
        raise ValueError("Une seule variante no_connection prob=residual est autorisee.")

    residual_probability = 1.0 - explicit_probability
    if residual_probability < -1e-12:
        raise ValueError(
            "La somme des probabilites de connexion CV depasse 1.0: "
            f"{explicit_probability:.12g}"
        )
    residual_probability = max(0.0, residual_probability)
    residual_connection = residual_connections[0]
    return [
        (
            CVConnection(
                variant=connection.variant,
                name=connection.name,
                target=connection.target,
                probability=residual_probability,
                roughness=connection.roughness,
                diameter=connection.diameter,
                shape=connection.shape,
                no_connection=connection.no_connection,
            )
            if connection is residual_connection
            else connection
        )
        for connection in connections
    ]


def strip_comment(line: str) -> str:
    for marker in ("#", ";"):
        index = line.find(marker)
        if index >= 0:
            line = line[:index]
    return line.strip()


def parse_key_values(tokens: Iterable[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        values[key.strip().lower().replace("-", "_")] = value.strip().strip('"')
    return values


def read_coordinate_table(path: Path) -> dict[str, tuple[float, float]]:
    df = pd.read_excel(path)
    required = {"Nodes", "X-Coord", "Y-Coord"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans {path}: {', '.join(sorted(missing))}")

    coordinates: dict[str, tuple[float, float]] = {}
    for _, row in df.iterrows():
        node = str(row["Nodes"]).strip()
        if not node or node.lower() == "nan":
            continue
        x = parse_optional_float(row["X-Coord"])
        y = parse_optional_float(row["Y-Coord"])
        if x is None or y is None:
            continue
        coordinates[node] = (x, y)
    return coordinates


def validate_coordinate_table(coordinates: dict[str, tuple[float, float]], config: CVConfig) -> None:
    required = {
        config.control_node,
        *(
            connection.target
            for connection in config.connections
            if connection.target is not None
        ),
    }
    missing = sorted(required - set(coordinates))
    if missing:
        raise KeyError(
            "Nodes absents du fichier de coordonnees: " + ", ".join(missing)
        )


def build_cases(
    config: CVConfig,
    coordinates: dict[str, tuple[float, float]],
    source_runs: Path,
    output_dir: Path,
) -> list[CVCase]:
    cases: list[CVCase] = []
    index = 1
    for hydrology in config.hydrologies:
        source_hydrology_dir = source_runs / hydrology
        csv_path = source_hydrology_dir / f"{hydrology}_mass_simulations_results.csv"
        source_phase_dir = source_hydrology_dir / SOURCE_PHASE
        if not csv_path.exists():
            print(f"[SKIP] CSV absent pour {hydrology}: {csv_path}")
            continue
        if not source_phase_dir.exists():
            print(f"[SKIP] Dossier source absent pour {hydrology}: {source_phase_dir}")
            continue

        rows = read_source_rows(csv_path, SOURCE_PHASE)
        for row in rows:
            source_simulation_id = row["simulation_id"]
            source_case_dir = source_phase_dir / source_simulation_id
            source_inp = source_case_dir / f"{source_simulation_id}.inp"
            if not source_inp.exists():
                print(f"[SKIP] INP source absent: {source_inp}")
                continue

            base_probability = parse_optional_float(row.get("combination_probability"))
            for connection in config.connections:
                combined_probability = (
                    None
                    if base_probability is None
                    else base_probability * connection.probability
                )
                cases.append(
                    CVCase(
                        index=index,
                        hydrology=hydrology,
                        source_simulation_id=source_simulation_id,
                        source_case_dir=source_case_dir,
                        source_inp=source_inp,
                        base_variant_combination=row.get("variant_combination", ""),
                        base_probability=base_probability,
                        connection=connection,
                        connection_length=(
                            0.0
                            if connection.no_connection
                            else distance(
                                coordinates[config.control_node],
                                coordinates[str(connection.target)],
                            )
                        ),
                        combined_probability=combined_probability,
                    )
                )
                index += 1
    return cases


def read_source_rows(csv_path: Path, phase: str) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    return [row for row in rows if row.get("phase") == phase]


def merge_with_existing_hydrologies(
    results_path: Path,
    new_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not results_path.exists() or not new_rows:
        return new_rows

    new_hydrologies = {str(row.get("hydrology", "")) for row in new_rows}
    with results_path.open("r", encoding="utf-8-sig", newline="") as handle:
        existing_rows = list(csv.DictReader(handle, delimiter=";"))

    kept_rows = [
        row
        for row in existing_rows
        if str(row.get("hydrology", "")) not in new_hydrologies
    ]
    merged_rows: list[dict[str, object]] = [*kept_rows, *new_rows]
    return sorted(
        merged_rows,
        key=lambda row: (
            str(row.get("hydrology", "")),
            int(str(row.get("simulation_id", "0")).split("_")[-1])
            if str(row.get("simulation_id", "")).split("_")[-1].isdigit()
            else 0,
        ),
    )


def distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(second[0] - first[0], second[1] - first[1])


def run_cv_case(
    case: CVCase,
    total: int,
    config: CVConfig,
    output_dir: Path,
    engine: str | None,
) -> CVRunResult:
    simulation_id = f"cv_sim_{case.index:05d}"
    case_dir = (
        output_dir
        / case.hydrology
        / SOURCE_PHASE
        / case.source_simulation_id
        / f"{case.connection.variant}_{case.connection.name}"
    )
    inp_path = case_dir / f"{simulation_id}.inp"
    rpt_path = case_dir / f"{simulation_id}.rpt"
    out_path = case_dir / f"{simulation_id}.out"

    if case.connection.no_connection:
        case_dir.mkdir(parents=True, exist_ok=True)
        discharge = 0.0
    else:
        write_cv_inp(case.source_inp, inp_path, config, case.connection, case.connection_length)
        unlink_with_retries(rpt_path)
        unlink_with_retries(out_path)
        run_swmm(inp_path, rpt_path, out_path, engine)
        discharge = read_stable_node_discharge(out_path, config.control_node)

    row: dict[str, object] = {
        "simulation_id": simulation_id,
        "hydrology": case.hydrology,
        "source_scenario": config.source_scenario,
        "source_phase": SOURCE_PHASE,
        "source_simulation_id": case.source_simulation_id,
        "source_case_directory": str(case.source_case_dir),
        "cv_case_directory": str(case_dir),
        "base_variant_combination": case.base_variant_combination,
        "base_combination_probability": (
            "" if case.base_probability is None else f"{case.base_probability:.12g}"
        ),
        "connection_variant": case.connection.variant,
        "connection_name": case.connection.name,
        "connection_target": "" if case.connection.target is None else case.connection.target,
        "connection_probability": f"{case.connection.probability:.12g}",
        "combined_probability": (
            "" if case.combined_probability is None else f"{case.combined_probability:.12g}"
        ),
        "connection_length_m": f"{case.connection_length:.6g}",
        "connection_diameter_m": f"{case.connection.diameter:.6g}",
        "connection_roughness": f"{case.connection.roughness:.6g}",
        "outfall_elevation_m": f"{config.control_elevation:.6g}",
        "max_stable_discharge_m3s": f"{discharge:.6g}",
    }
    message = (
        f"[{case.index}/{total}] {simulation_id}: {case.hydrology} "
        f"{case.source_simulation_id} + {case.connection.variant} "
        f"({case.connection.name}) "
        f"Q={discharge:.3f} m3/s"
    )
    return CVRunResult(case.index, total, simulation_id, message, row)


def write_cv_inp(
    source_inp: Path,
    destination_inp: Path,
    config: CVConfig,
    connection: CVConnection,
    connection_length: float,
) -> None:
    lines, sections = read_sections(source_inp)
    sections = convert_junction_to_outfall(
        lines,
        sections,
        config.control_node,
        elevation=config.control_elevation,
    )
    sections = upsert_conduit(lines, sections, connection, config.control_node, connection_length)
    destination_inp.parent.mkdir(parents=True, exist_ok=True)
    write_text_with_retries(
        destination_inp,
        "\r\n".join(lines) + "\r\n",
        encoding="mbcs",
    )


def convert_junction_to_outfall(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    node: str,
    elevation: float,
) -> dict[str, tuple[int, int]]:
    try:
        row_index = find_named_row(lines, sections, "JUNCTIONS", node)
    except KeyError:
        pass
    else:
        del lines[row_index]
        sections = recompute_sections_local(lines)

    outfall_row = format_row([node, f"{elevation:.9g}", "FREE", "", "NO", ""])
    return upsert_row(lines, sections, "OUTFALLS", node, outfall_row)


def upsert_conduit(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    connection: CVConnection,
    control_node: str,
    length: float,
) -> dict[str, tuple[int, int]]:
    sections = upsert_row(
        lines,
        sections,
        "CONDUITS",
        connection.name,
        format_row(
            [
                connection.name,
                control_node,
                connection.target,
                f"{max(length, 0.001):.9g}",
                f"{connection.roughness:.9g}",
                0,
                0,
                0,
                0,
            ]
        ),
    )
    sections = upsert_row(
        lines,
        sections,
        "XSECTIONS",
        connection.name,
        format_row([connection.name, connection.shape, f"{connection.diameter:.9g}", 0, 0, 0, 1]),
    )
    return sections


def upsert_row(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    section: str,
    name: str,
    row: str,
) -> dict[str, tuple[int, int]]:
    try:
        row_index = find_named_row(lines, sections, section, name)
    except KeyError:
        _, end = section_body_range(sections, section)
        lines.insert(end, row)
        return recompute_sections_local(lines)
    lines[row_index] = row
    return sections


def find_named_row(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    section: str,
    name: str,
) -> int:
    start, end = section_body_range(sections, section)
    for index in range(start, end):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith(";"):
            continue
        tokens = split_data_line(stripped)
        if tokens and tokens[0] == name:
            return index
    raise KeyError(name)


def recompute_sections_local(lines: list[str]) -> dict[str, tuple[int, int]]:
    sections: dict[str, tuple[int, int]] = {}
    current_name: str | None = None
    current_start: int | None = None
    import re

    for index, line in enumerate(lines):
        match = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if not match:
            continue
        if current_name is not None and current_start is not None:
            sections[current_name] = (current_start, index)
        current_name = match.group(1).strip().upper()
        current_start = index
    if current_name is not None and current_start is not None:
        sections[current_name] = (current_start, len(lines))
    return sections


def read_stable_node_discharge(out_path: Path, node: str) -> float:
    records = read_single_node_total_inflow(out_path, node)
    return stable_node_peak(node, records)


def read_single_node_total_inflow(out_path: Path, node: str):
    ep_output = import_optional("epaswmm.output")
    if ep_output is not None:
        out = ep_output.Output(str(out_path))
        node_names = set(out.get_element_names(ep_output.ElementType.NODE))
        if node not in node_names:
            raise KeyError(f"Node absent du fichier .out: {node}")
        series = out.get_node_timeseries(node, ep_output.NodeAttribute.TOTAL_INFLOW)
        return records_from_series(series)

    output = import_optional("swmm.toolkit.output")
    shared_enum = import_optional("swmm.toolkit.shared_enum")
    if output is None:
        raise RuntimeError("Lecture .out impossible: epaswmm.output ou swmm-toolkit requis.")

    out = output.Output(str(out_path))
    try:
        node_names = set(getattr(out, "nodes", []))
        if node not in node_names:
            raise KeyError(f"Node absent du fichier .out: {node}")
        total_inflow_attribute = resolve_node_attribute(
            shared_enum,
            ("TOTAL_INFLOW", "TOTAL_INFLOW_RATE", "INFLOW", "flow"),
            "TOTAL_INFLOW",
        )
        return read_object_series(out, "node", node, total_inflow_attribute)
    finally:
        close = getattr(out, "close", None)
        if close is not None:
            close()


def records_from_series(series) -> list[tuple[object | None, float]]:
    records = []
    iterable = series.items() if isinstance(series, dict) else enumerate(series)
    for key, value in iterable:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            records.append((key, number))
    return records


if __name__ == "__main__":
    raise SystemExit(main())
