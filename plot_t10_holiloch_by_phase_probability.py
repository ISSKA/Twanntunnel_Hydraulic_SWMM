from __future__ import annotations

from pathlib import Path

import plot_all_phase_probability_envelopes as phase_plots
from MASS_COMPUTATION.run_swmm_mass_computation import (
    dict_series_to_records,
    import_optional,
    read_object_series,
    resolve_node_attribute,
    stable_node_peak,
)


ROOT_DIR = Path(__file__).resolve().parent
HYDROLOGY = "T10"
OUTFALL = "Holiloch"
CSV_PATH = (
    ROOT_DIR
    / "MASS_COMPUTATION"
    / "runs"
    / "scenario1"
    / HYDROLOGY
    / f"{HYDROLOGY}_mass_simulations_results.csv"
)
OUTPUT_PATH = (
    ROOT_DIR
    / "MASS_COMPUTATION"
    / "runs"
    / "plots"
    / f"1_{HYDROLOGY}_{OUTFALL}_debits_by_phase_probability.html"
)


def main() -> int:
    rows = phase_plots.read_result_rows(CSV_PATH)
    holiloch_rows = add_holiloch_outfall_flows(rows)

    original_outfalls = phase_plots.OUTFALLS
    try:
        phase_plots.OUTFALLS = [OUTFALL]
        html = phase_plots.render_phase_probability_page(HYDROLOGY, holiloch_rows)
    finally:
        phase_plots.OUTFALLS = original_outfalls

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"[OK] {OUTPUT_PATH}")
    return 0


def add_holiloch_outfall_flows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    q_key = f"qmax_{phase_plots.slugify(OUTFALL)}_m3s"
    updated_rows: list[dict[str, str]] = []
    total = len(rows)

    for index, row in enumerate(rows, start=1):
        row = dict(row)
        case_directory = Path(row["case_directory"])
        simulation_id = row["simulation_id"]
        out_path = case_directory / f"{simulation_id}.out"

        records = read_single_node_total_inflow(out_path, OUTFALL)
        stable_flow = stable_node_peak(OUTFALL, records)
        row[q_key] = f"{stable_flow:.6g}"
        updated_rows.append(row)

        if index % 500 == 0 or index == total:
            print(f"  {index}/{total} resultats Holiloch lus")

    return updated_rows


def read_single_node_total_inflow(out_path: Path, node: str):
    ep_output = import_optional("epaswmm.output")
    if ep_output is not None:
        out = ep_output.Output(str(out_path))
        node_names = set(out.get_element_names(ep_output.ElementType.NODE))
        if node not in node_names:
            raise KeyError(f"Node absent du fichier .out: {node}")
        return dict_series_to_records(
            out.get_node_timeseries(node, ep_output.NodeAttribute.TOTAL_INFLOW)
        )

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


if __name__ == "__main__":
    raise SystemExit(main())
