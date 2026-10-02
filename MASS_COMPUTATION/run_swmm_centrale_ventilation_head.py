from __future__ import annotations

import argparse
import csv
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from run_swmm_centrale_ventilation_discharge import (
    CVConfig,
    CVConnection,
    distance,
    find_named_row,
    parse_cv_scenarios,
    read_coordinate_table,
    recompute_sections_local,
    upsert_conduit,
    upsert_row,
    validate_coordinate_table,
)
from run_swmm_mass_computation import (
    Hydrology,
    configure_inflow,
    configure_simulation_window,
    format_row,
    import_optional,
    parse_optional_float,
    read_object_series,
    read_sections,
    resolve_node_attribute,
    run_swmm,
    section_body_range,
    stable_node_peak,
    unlink_with_retries,
    write_results_csv,
    write_text_with_retries,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
MASS_DIR = Path(__file__).resolve().parent
DEFAULT_SCENARIOS = MASS_DIR / "scenarios_CentraleVentilation.txt"
DEFAULT_COORDINATES = ROOT_DIR / "260508_Coord_nodes_SWMM.xlsx"
DEFAULT_BASE_INP = ROOT_DIR / "SWMM_Twannbach.inp"
DEFAULT_OUTPUT_DIR = MASS_DIR / "runs" / "CV_scenario_2"
RESULTS_CSV = "CV_scenario_2_hydraulic_head_results.csv"
CV_SCENARIO = "CV_scenario_2"


@dataclass(frozen=True)
class CVHeadCase:
    index: int
    hydrology: str
    hydrology_flow_m3s: float
    connection: CVConnection
    connection_length: float
    combined_probability: float | None


@dataclass(frozen=True)
class CVHeadRunResult:
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

    cases = build_cases(config, coordinates)
    if args.limit is not None:
        cases = cases[: args.limit]

    print(f"{len(cases)} simulations CentraleVentilation head preparees.")
    if args.dry_run:
        for case in cases[:10]:
            print(
                f"  {case.hydrology} {case.connection.variant} "
                f"({case.connection.name}) L={case.connection_length:.1f} m"
            )
        if len(cases) > 10:
            print(f"  ... {len(cases) - 10} autres simulations")
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    workers = max(1, args.workers)
    if workers == 1:
        for case in cases:
            result = run_cv_head_case(
                case,
                len(cases),
                config,
                args.base_inp,
                args.output_dir,
                args.engine,
            )
            print(result.message)
            if result.row is not None:
                rows.append(result.row)
    else:
        print(f"Execution parallele: {workers} workers.")
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(
                    run_cv_head_case,
                    case,
                    len(cases),
                    config,
                    args.base_inp,
                    args.output_dir,
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
    results_path = args.output_dir / RESULTS_CSV
    rows = merge_with_existing_hydrologies(results_path, rows)
    write_results_csv(results_path, rows)
    print(f"CSV ecrit: {results_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Simule les charges hydrauliques a CentraleVentilation_1C depuis "
            "SWMM_Twannbach.inp, sans reprendre les scenarios 1_8a."
        )
    )
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--coordinates", type=Path, default=DEFAULT_COORDINATES)
    parser.add_argument("--base-inp", type=Path, default=DEFAULT_BASE_INP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--engine", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def build_cases(
    config: CVConfig,
    coordinates: dict[str, tuple[float, float]],
) -> list[CVHeadCase]:
    cases: list[CVHeadCase] = []
    index = 1
    for hydrology in config.hydrologies.values():
        for connection in config.connections:
            cases.append(
                CVHeadCase(
                    index=index,
                    hydrology=hydrology.name,
                    hydrology_flow_m3s=hydrology.flow_m3s,
                    connection=connection,
                    connection_length=(
                        0.0
                        if connection.no_connection
                        else distance(
                            coordinates[config.control_node],
                            coordinates[str(connection.target)],
                        )
                    ),
                    combined_probability=connection.probability,
                )
            )
            index += 1
    return cases


def run_cv_head_case(
    case: CVHeadCase,
    total: int,
    config: CVConfig,
    base_inp: Path,
    output_dir: Path,
    engine: str | None,
) -> CVHeadRunResult:
    simulation_id = f"cv2_head_{case.index:05d}"
    case_dir = (
        output_dir
        / case.hydrology
        / f"{case.connection.variant}_{case.connection.name}"
    )
    inp_path = case_dir / f"{simulation_id}.inp"
    rpt_path = case_dir / f"{simulation_id}.rpt"
    out_path = case_dir / f"{simulation_id}.out"

    write_cv_head_inp(base_inp, inp_path, config, case)
    unlink_with_retries(rpt_path)
    unlink_with_retries(out_path)
    run_swmm(inp_path, rpt_path, out_path, engine)

    depth = read_stable_node_depth(out_path, config.control_node)
    head = config.control_elevation + depth
    row: dict[str, object] = {
        "simulation_id": simulation_id,
        "hydrology": case.hydrology,
        "cv_scenario": CV_SCENARIO,
        "base_inp": str(base_inp),
        "connection_variant": case.connection.variant,
        "connection_name": case.connection.name,
        "connection_target": "" if case.connection.target is None else case.connection.target,
        "connection_probability": f"{case.connection.probability:.12g}",
        "combined_probability": (
            "" if case.combined_probability is None else f"{case.combined_probability:.12g}"
        ),
        "case_directory": str(case_dir),
        "connection_length_m": f"{case.connection_length:.6g}",
        "connection_diameter_m": f"{case.connection.diameter:.6g}",
        "connection_roughness": f"{case.connection.roughness:.6g}",
        "junction_elevation_m": f"{config.control_elevation:.6g}",
        "max_stable_depth_m": f"{depth:.6g}",
        "max_stable_hydraulic_head_m": f"{head:.6g}",
    }
    message = (
        f"[{case.index}/{total}] {simulation_id}: {case.hydrology} "
        f"+ {case.connection.variant} ({case.connection.name}) H={head:.3f} m"
    )
    return CVHeadRunResult(case.index, total, simulation_id, message, row)


def write_cv_head_inp(
    base_inp: Path,
    destination_inp: Path,
    config: CVConfig,
    case: CVHeadCase,
) -> None:
    lines, sections = read_sections(base_inp)
    sections = configure_simulation_window(lines, sections)
    sections = configure_inflow(
        lines,
        sections,
        Hydrology(
            name=case.hydrology,
            constant_flow_m3s=case.hydrology_flow_m3s,
        ),
    )
    sections = upsert_junction(
        lines,
        sections,
        config.control_node,
        elevation=config.control_elevation,
        max_depth=config.control_max_depth,
    )
    sections = remove_outfall_if_present(lines, sections, config.control_node)
    if not case.connection.no_connection:
        sections = upsert_conduit(
            lines,
            sections,
            case.connection,
            config.control_node,
            case.connection_length,
        )
    destination_inp.parent.mkdir(parents=True, exist_ok=True)
    write_text_with_retries(
        destination_inp,
        "\r\n".join(lines) + "\r\n",
        encoding="mbcs",
    )


def upsert_junction(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    node: str,
    elevation: float,
    max_depth: float,
) -> dict[str, tuple[int, int]]:
    row = format_row([node, f"{elevation:.9g}", f"{max_depth:.9g}", 0, 0, 0])
    try:
        row_index = find_named_row(lines, sections, "JUNCTIONS", node)
    except KeyError:
        _, end = section_body_range(sections, "JUNCTIONS")
        lines.insert(end, row)
        return recompute_sections_local(lines)
    lines[row_index] = row
    return sections


def remove_outfall_if_present(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    node: str,
) -> dict[str, tuple[int, int]]:
    try:
        row_index = find_named_row(lines, sections, "OUTFALLS", node)
    except KeyError:
        return sections
    del lines[row_index]
    return recompute_sections_local(lines)


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


def read_stable_node_depth(out_path: Path, node: str) -> float:
    records = read_single_node_depth(out_path, node)
    return stable_node_peak(node, records)


def read_single_node_depth(out_path: Path, node: str):
    ep_output = import_optional("epaswmm.output")
    if ep_output is not None:
        out = ep_output.Output(str(out_path))
        node_names = set(out.get_element_names(ep_output.ElementType.NODE))
        if node not in node_names:
            raise KeyError(f"Node absent du fichier .out: {node}")
        series = out.get_node_timeseries(node, ep_output.NodeAttribute.INVERT_DEPTH)
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
        depth_attribute = resolve_node_attribute(
            shared_enum,
            ("INVERT_DEPTH", "DEPTH", "depth"),
            "INVERT_DEPTH",
        )
        return read_object_series(out, "node", node, depth_attribute)
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
