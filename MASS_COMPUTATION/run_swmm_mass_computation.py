from __future__ import annotations

import argparse
import csv
import importlib
import math
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BASE_INP = ROOT_DIR / "SWMM_Twannbach.inp"
DEFAULT_SCENARIOS = Path(__file__).with_name("scenarios.txt")
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("runs")

INPUT_TIMESERIES_NAME = "Real_disch_as_input"
DEFAULT_HYDROLOGIES = {
    "seche": Path(__file__).with_name("timeseries") / "seche.dat",
    "normale": Path(__file__).with_name("timeseries") / "normale.dat",
    "hautes_eaux": Path(__file__).with_name("timeseries") / "hautes_eaux.dat",
}

RESULT_LINKS = ["ALL"]
STABLE_WINDOW_HOURS = 4
MIN_POINTS_NEAR_PEAK = 3
NEAR_PEAK_RATIO = 0.95


@dataclass(frozen=True)
class Action:
    command: str
    values: dict[str, str]
    source_line: int


@dataclass
class Variant:
    name: str
    actions: list[Action] = field(default_factory=list)


@dataclass
class Phase:
    name: str
    actions: list[Action] = field(default_factory=list)
    variants: list[Variant] = field(default_factory=list)


@dataclass
class Scenario:
    name: str
    phases: list[Phase] = field(default_factory=list)


@dataclass(frozen=True)
class SimulationCase:
    scenario: str
    phase: str
    variant_path: tuple[str, ...]
    hydrology: str
    actions: tuple[Action, ...]
    timeseries_file: Path

    @property
    def variant(self) -> str:
        return "__".join(self.variant_path) if self.variant_path else "base"

    @property
    def slug(self) -> str:
        return slugify("_".join([self.scenario, self.phase, self.variant, self.hydrology]))


@dataclass(frozen=True)
class StablePeak:
    link: str
    peak_flow: float
    peak_time: datetime | None
    window_start: datetime | None
    window_end: datetime | None
    points_near_peak: int
    raw_peak_flow: float


def slugify(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip())
    return re.sub(r"_+", "_", text).strip("_") or "simulation"


def strip_comment(line: str) -> str:
    for marker in ("#", ";"):
        index = line.find(marker)
        if index >= 0:
            line = line[:index]
    return line.strip()


def parse_key_values(tokens: list[str], source_line: int) -> dict[str, str]:
    values: dict[str, str] = {}
    positional: list[str] = []

    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            values[key.strip().lower().replace("-", "_")] = value.strip().strip('"')
        else:
            positional.append(token.strip().strip('"'))

    if positional:
        values["_positional"] = "|".join(positional)
    if not values:
        raise ValueError(f"Ligne {source_line}: action sans parametres.")
    return values


def parse_scenarios(path: Path) -> tuple[list[Scenario], dict[str, Path]]:
    scenarios: list[Scenario] = []
    hydrologies = dict(DEFAULT_HYDROLOGIES)
    current_scenario: Scenario | None = None
    current_phase: Phase | None = None
    current_variant: Variant | None = None

    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = strip_comment(raw_line)
            if not line:
                continue

            tokens = line.split()
            keyword = tokens[0].lower().rstrip(":")
            rest = tokens[1:]

            if keyword in {"timeseries", "hydrology", "hydrologie"}:
                if len(rest) < 2:
                    raise ValueError(
                        f"Ligne {line_number}: utiliser 'timeseries nom chemin'."
                    )
                hydrologies[rest[0]] = resolve_path(" ".join(rest[1:]), path.parent)
                continue

            if keyword == "scenario":
                if not rest:
                    raise ValueError(f"Ligne {line_number}: nom de scenario manquant.")
                current_scenario = Scenario(name=" ".join(rest))
                scenarios.append(current_scenario)
                current_phase = None
                current_variant = None
                continue

            if keyword == "phase":
                if current_scenario is None:
                    raise ValueError(f"Ligne {line_number}: phase avant scenario.")
                if not rest:
                    raise ValueError(f"Ligne {line_number}: nom de phase manquant.")
                current_phase = Phase(name=" ".join(rest))
                current_scenario.phases.append(current_phase)
                current_variant = None
                continue

            if keyword == "variant":
                if current_phase is None:
                    raise ValueError(f"Ligne {line_number}: variante avant phase.")
                if not rest:
                    raise ValueError(f"Ligne {line_number}: nom de variante manquant.")
                current_variant = Variant(name=" ".join(rest))
                current_phase.variants.append(current_variant)
                continue

            if current_phase is None:
                raise ValueError(
                    f"Ligne {line_number}: action '{tokens[0]}' avant phase."
                )

            action = Action(
                command=keyword,
                values=parse_key_values(rest, line_number),
                source_line=line_number,
            )
            if current_variant is None:
                current_phase.actions.append(action)
            else:
                current_variant.actions.append(action)

    return scenarios, hydrologies


def resolve_path(text: str, base_dir: Path) -> Path:
    path = Path(text.strip().strip('"'))
    if not path.is_absolute():
        path = base_dir / path
    return path


@dataclass(frozen=True)
class VariantCombination:
    names: tuple[str, ...]
    actions: tuple[Action, ...]


def build_cases(
    scenarios: list[Scenario],
    hydrologies: dict[str, Path],
    final_phase_only: bool = False,
) -> list[SimulationCase]:
    cases: list[SimulationCase] = []

    for scenario in scenarios:
        combinations = [VariantCombination(names=(), actions=())]
        for phase_index, phase in enumerate(scenario.phases):
            variants = phase.variants or [Variant(name="base")]
            next_combinations: list[VariantCombination] = []

            for combination in combinations:
                for variant in variants:
                    next_combinations.append(
                        VariantCombination(
                            names=(*combination.names, f"{phase.name}-{variant.name}"),
                            actions=(
                                *combination.actions,
                                *phase.actions,
                                *variant.actions,
                            ),
                        )
            )

            combinations = next_combinations
            is_last_phase = phase_index == len(scenario.phases) - 1
            if final_phase_only and not is_last_phase:
                continue

            for combination in combinations:
                for hydrology_name, timeseries_file in hydrologies.items():
                    cases.append(
                        SimulationCase(
                            scenario=scenario.name,
                            phase=phase.name,
                            variant_path=combination.names,
                            hydrology=hydrology_name,
                            actions=combination.actions,
                            timeseries_file=timeseries_file,
                        )
                    )

    return cases


def read_sections(inp_file: Path) -> tuple[list[str], dict[str, tuple[int, int]]]:
    lines = inp_file.read_text(encoding="mbcs").splitlines()
    sections: dict[str, tuple[int, int]] = {}
    current_name: str | None = None
    current_start: int | None = None

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

    return lines, sections


def section_body_range(sections: dict[str, tuple[int, int]], name: str) -> tuple[int, int]:
    if name not in sections:
        raise KeyError(f"Section [{name}] absente du fichier .inp.")
    start, end = sections[name]
    return start + 1, end


def split_data_line(line: str) -> list[str]:
    return line.split()


def find_named_row(lines: list[str], sections: dict[str, tuple[int, int]], section: str, name: str) -> int:
    start, end = section_body_range(sections, section)
    for index in range(start, end):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith(";"):
            continue
        tokens = split_data_line(stripped)
        if tokens and tokens[0] == name:
            return index
    raise KeyError(f"Element '{name}' introuvable dans [{section}].")


def replace_token(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    section: str,
    name: str,
    token_index: int,
    value: str,
) -> None:
    row_index = find_named_row(lines, sections, section, name)
    tokens = split_data_line(lines[row_index])
    if len(tokens) <= token_index:
        raise ValueError(
            f"Ligne {row_index + 1}: impossible de modifier le champ {token_index}."
        )
    tokens[token_index] = value
    lines[row_index] = format_row(tokens)


def append_to_section(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    section: str,
    row: str,
) -> dict[str, tuple[int, int]]:
    _, end = section_body_range(sections, section)
    lines.insert(end, row)
    return recompute_sections(lines)


def recompute_sections(lines: list[str]) -> dict[str, tuple[int, int]]:
    sections: dict[str, tuple[int, int]] = {}
    current_name: str | None = None
    current_start: int | None = None

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


def format_row(tokens: Iterable[object]) -> str:
    return " ".join(str(token) for token in tokens)


def get_value(action: Action, *names: str, required: bool = True, default: str | None = None) -> str | None:
    for name in names:
        value = action.values.get(name.lower().replace("-", "_"))
        if value is not None:
            return value

    positional = action.values.get("_positional")
    if positional:
        parts = positional.split("|")
        for name in names:
            if name.startswith("_"):
                index = int(name[1:])
                if index < len(parts):
                    return parts[index]

    if required:
        raise ValueError(
            f"Ligne {action.source_line}: parametre manquant parmi {', '.join(names)}."
        )
    return default


def apply_action(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    action: Action,
) -> dict[str, tuple[int, int]]:
    command = action.command

    if command in {"set_diameter", "diameter", "diametre"}:
        link = get_value(action, "link", "conduit", "_0")
        diameter = get_value(action, "diameter", "diametre", "geom1", "_1")
        replace_token(lines, sections, "XSECTIONS", link, 2, str(diameter))
        return sections

    if command in {"set_roughness", "roughness", "rugosite"}:
        link = get_value(action, "link", "conduit", "_0")
        roughness = get_value(action, "roughness", "rugosite", "_1")
        replace_token(lines, sections, "CONDUITS", link, 4, str(roughness))
        return sections

    if command in {"set_length", "length", "longueur"}:
        link = get_value(action, "link", "conduit", "_0")
        length = get_value(action, "length", "longueur", "_1")
        replace_token(lines, sections, "CONDUITS", link, 3, str(length))
        return sections

    if command in {"add_conduit", "conduit"}:
        name = get_value(action, "name", "link", "_0")
        from_node = get_value(action, "from", "from_node", "upstream", "_1")
        to_node = get_value(action, "to", "to_node", "downstream", "_2")
        length = get_value(action, "length", "longueur", "_3", required=False, default="1")
        roughness = get_value(action, "roughness", "rugosite", "_4", required=False, default="0.01")
        diameter = get_value(action, "diameter", "diametre", "geom1", "_5", required=False, default="1")
        shape = get_value(action, "shape", "forme", required=False, default="CIRCULAR")
        in_offset = get_value(action, "in_offset", required=False, default="0")
        out_offset = get_value(action, "out_offset", required=False, default="0")

        sections = append_to_section(
            lines,
            sections,
            "CONDUITS",
            format_row([name, from_node, to_node, length, roughness, in_offset, out_offset, 0, 0]),
        )
        sections = append_to_section(
            lines,
            sections,
            "XSECTIONS",
            format_row([name, shape, diameter, 0, 0, 0, 1]),
        )
        return sections

    if command in {"add_junction", "junction", "node"}:
        name = get_value(action, "name", "node", "_0")
        elevation = get_value(action, "elevation", "radier", "_1")
        max_depth = get_value(action, "max_depth", "depth", required=False, default="100")
        init_depth = get_value(action, "init_depth", required=False, default="0")
        sur_depth = get_value(action, "sur_depth", required=False, default="0")
        aponded = get_value(action, "aponded", required=False, default="0")
        sections = append_to_section(
            lines,
            sections,
            "JUNCTIONS",
            format_row([name, elevation, max_depth, init_depth, sur_depth, aponded]),
        )

        x_coord = get_value(action, "x", required=False)
        y_coord = get_value(action, "y", required=False)
        if x_coord is not None and y_coord is not None:
            sections = append_to_section(
                lines,
                sections,
                "COORDINATES",
                format_row([name, x_coord, y_coord]),
            )
        return sections

    if command in {"disable_link", "remove_link", "supprimer_conduit"}:
        link = get_value(action, "link", "conduit", "_0")
        replace_token(lines, sections, "CONDUITS", link, 8, "0")
        replace_token(lines, sections, "XSECTIONS", link, 2, "0.001")
        return sections

    raise ValueError(f"Ligne {action.source_line}: action inconnue '{action.command}'.")


def set_timeseries_file(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    timeseries_name: str,
    timeseries_file: Path,
) -> None:
    row_index = find_named_row(lines, sections, "TIMESERIES", timeseries_name)
    lines[row_index] = f'{timeseries_name} FILE "{timeseries_file}"'


def write_case_inp(base_inp: Path, case: SimulationCase, case_dir: Path) -> Path:
    lines, sections = read_sections(base_inp)

    for action in case.actions:
        sections = apply_action(lines, sections, action)

    set_timeseries_file(lines, sections, INPUT_TIMESERIES_NAME, case.timeseries_file)

    case_dir.mkdir(parents=True, exist_ok=True)
    inp_path = case_dir / f"{case.slug}.inp"
    inp_path.write_text("\r\n".join(lines) + "\r\n", encoding="mbcs")
    return inp_path


def run_swmm(inp_path: Path, rpt_path: Path, out_path: Path, engine: str | None = None) -> None:
    if engine:
        completed = subprocess.run(
            [engine, str(inp_path), str(rpt_path), str(out_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "SWMM a echoue via l'executable externe.\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        return

    epaswmm = import_optional("epaswmm")
    if epaswmm is not None:
        for function_name in ("swmm_run", "run"):
            function = getattr(epaswmm, function_name, None)
            if function is not None:
                result = function(str(inp_path), str(rpt_path), str(out_path))
                if isinstance(result, int) and result != 0:
                    raise RuntimeError(f"epaswmm.{function_name} a retourne {result}.")
                return

    solver = import_optional("swmm.toolkit.solver")
    if solver is not None and hasattr(solver, "swmm_run"):
        result = solver.swmm_run(str(inp_path), str(rpt_path), str(out_path))
        if isinstance(result, int) and result != 0:
            raise RuntimeError(f"swmm.toolkit.solver.swmm_run a retourne {result}.")
        return

    raise RuntimeError(
        "Aucun moteur SWMM Python trouve. Installer epaswmm/swmm-toolkit ou passer "
        "--engine chemin\\vers\\swmm5.exe."
    )


def import_optional(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def extract_stable_peaks(out_path: Path, links: list[str]) -> list[StablePeak]:
    records = read_link_flow_records(out_path, links)
    peaks: list[StablePeak] = []

    for link, values in sorted(records.items()):
        peak = stable_peak(link, values)
        if peak is not None:
            peaks.append(peak)

    return peaks


def read_link_flow_records(out_path: Path, links: list[str]) -> dict[str, list[tuple[datetime | None, float]]]:
    output = import_optional("swmm.toolkit.output")
    shared_enum = import_optional("swmm.toolkit.shared_enum")
    if output is None:
        raise RuntimeError(
            "Lecture .out impossible: installer swmm-toolkit, ou remplacer "
            "read_link_flow_records() par le lecteur epaswmm disponible localement."
        )

    out = output.Output(str(out_path))
    try:
        link_names = list(getattr(out, "links", []))
        selected = link_names if links == ["ALL"] else links
        missing = sorted(set(selected) - set(link_names))
        if missing:
            raise KeyError(f"Liens absents du fichier .out: {', '.join(missing)}")

        flow_attribute = resolve_flow_attribute(shared_enum)
        records: dict[str, list[tuple[datetime | None, float]]] = {}
        for link in selected:
            series = read_output_series(out, link, flow_attribute)
            records[link] = series
        return records
    finally:
        close = getattr(out, "close", None)
        if close is not None:
            close()


def resolve_flow_attribute(shared_enum):
    if shared_enum is None:
        return "FLOW"
    link_attribute = getattr(shared_enum, "LinkAttribute", None)
    if link_attribute is None:
        return "FLOW"
    for candidate in ("FLOW_RATE", "FLOW", "flow_rate"):
        value = getattr(link_attribute, candidate, None)
        if value is not None:
            return value
    return "FLOW"


def read_output_series(out, link: str, flow_attribute) -> list[tuple[datetime | None, float]]:
    series = None
    errors: list[str] = []

    if hasattr(out, "link_series"):
        for args in ((link, flow_attribute), (flow_attribute, link)):
            try:
                series = out.link_series(*args)
                break
            except TypeError as exc:
                errors.append(str(exc))

    if series is None and hasattr(out, "get_part"):
        for args in (("link", link, flow_attribute), ("LINK", link, flow_attribute)):
            try:
                series = out.get_part(*args)
                break
            except TypeError as exc:
                errors.append(str(exc))

    if series is None:
        detail = " | ".join(errors)
        raise RuntimeError(
            "API swmm-toolkit.output non reconnue pour les series de liens."
            + (f" Details: {detail}" if detail else "")
        )

    records: list[tuple[datetime | None, float]] = []
    if isinstance(series, dict):
        iterable = series.items()
    else:
        iterable = enumerate(series)

    for key, value in iterable:
        date = key if isinstance(key, datetime) else None
        try:
            flow = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(flow):
            records.append((date, flow))
    return records


def stable_peak(
    link: str,
    values: list[tuple[datetime | None, float]],
    window_hours: int = STABLE_WINDOW_HOURS,
    near_peak_ratio: float = NEAR_PEAK_RATIO,
    min_points_near_peak: int = MIN_POINTS_NEAR_PEAK,
) -> StablePeak | None:
    if not values:
        return None

    flows = [flow for _, flow in values]
    raw_peak = max(flows)
    if raw_peak <= 0:
        return StablePeak(link, 0.0, None, None, None, 0, raw_peak)

    window_size = max(1, min(window_hours, len(values)))
    best_index = 0
    best_mean = -math.inf

    for index in range(0, len(values) - window_size + 1):
        window = flows[index : index + window_size]
        near_count = sum(flow >= raw_peak * near_peak_ratio for flow in window)
        if near_count < min(min_points_near_peak, window_size):
            continue
        mean_flow = sum(window) / window_size
        if mean_flow > best_mean:
            best_mean = mean_flow
            best_index = index

    if best_mean == -math.inf:
        sorted_flows = sorted(flows)
        percentile_index = max(0, int(len(sorted_flows) * 0.99) - 1)
        best_mean = sorted_flows[percentile_index]
        best_index = flows.index(min(flows, key=lambda flow: abs(flow - best_mean)))

    window_values = values[best_index : best_index + window_size]
    stable_flow = max(flow for _, flow in window_values)
    peak_offset = max(range(len(window_values)), key=lambda offset: window_values[offset][1])
    peak_time = window_values[peak_offset][0]
    start_time = window_values[0][0]
    end_time = window_values[-1][0]
    points_near_peak = sum(flow >= raw_peak * near_peak_ratio for _, flow in window_values)

    return StablePeak(
        link=link,
        peak_flow=stable_flow,
        peak_time=peak_time,
        window_start=start_time,
        window_end=end_time,
        points_near_peak=points_near_peak,
        raw_peak_flow=raw_peak,
    )


def write_results_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def format_date(value: datetime | None) -> str:
    return "" if value is None else value.strftime("%Y-%m-%d %H:%M")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lance des simulations SWMM par scenario/phase/variante/hydrologie."
    )
    parser.add_argument("--base-inp", type=Path, default=DEFAULT_BASE_INP)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--engine",
        type=str,
        default=None,
        help="Chemin optionnel vers swmm5.exe si epaswmm/swmm-toolkit n'est pas disponible.",
    )
    parser.add_argument(
        "--links",
        nargs="+",
        default=RESULT_LINKS,
        help="Liens a extraire dans le .out, ou ALL.",
    )
    parser.add_argument(
        "--final-phase-only",
        action="store_true",
        help=(
            "Ne lance que les combinaisons de la derniere phase. "
            "Avec 8 phases et 3 variantes par phase: 3^8 cas, avant hydrologies."
        ),
    )
    parser.add_argument(
        "--all-phases",
        action="store_true",
        help=(
            "Lance aussi les combinaisons intermediaires de chaque phase "
            "(phase 1, phase 2, etc.)."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenarios, hydrologies = parse_scenarios(args.scenarios)
    cases = build_cases(
        scenarios,
        hydrologies,
        final_phase_only=args.final_phase_only or not args.all_phases,
    )

    if not cases:
        print("Aucune simulation a lancer.")
        return 0

    missing_timeseries = [path for path in hydrologies.values() if not path.exists()]
    if missing_timeseries and not args.dry_run:
        print("Timeseries manquantes:")
        for path in missing_timeseries:
            print(f"  - {path}")
        print("Adapter MASS_COMPUTATION/scenarios.txt avant de lancer les simulations.")
        return 2
    if missing_timeseries and args.dry_run:
        print("Timeseries manquantes ignorees en dry-run:")
        for path in missing_timeseries:
            print(f"  - {path}")

    rows: list[dict[str, object]] = []
    print(f"{len(cases)} simulations preparees.")

    for index, case in enumerate(cases, start=1):
        case_dir = args.output_dir / case.slug
        print(f"[{index}/{len(cases)}] {case.slug}")
        inp_path = write_case_inp(args.base_inp, case, case_dir)
        rpt_path = case_dir / f"{case.slug}.rpt"
        out_path = case_dir / f"{case.slug}.out"

        if args.dry_run:
            print(f"  INP genere: {inp_path}")
            continue

        run_swmm(inp_path, rpt_path, out_path, args.engine)
        peaks = extract_stable_peaks(out_path, args.links)

        for peak in peaks:
            row = {
                "scenario": case.scenario,
                "phase": case.phase,
                "variant": case.variant,
                "hydrology": case.hydrology,
                "link": peak.link,
                "stable_peak_m3s": f"{peak.peak_flow:.6g}",
                "raw_peak_m3s": f"{peak.raw_peak_flow:.6g}",
                "peak_time": format_date(peak.peak_time),
                "window_start": format_date(peak.window_start),
                "window_end": format_date(peak.window_end),
                "points_near_peak": peak.points_near_peak,
            }
            rows.append(row)
            print(
                "  "
                f"{peak.link}: Qmax stable={row['stable_peak_m3s']} m3/s "
                f"(brut={row['raw_peak_m3s']}, fenetre={row['window_start']} -> {row['window_end']})"
            )

    if rows:
        results_path = args.output_dir / "stable_peak_results.csv"
        write_results_csv(results_path, rows)
        print(f"Tableau provisoire: {results_path}")

    if args.dry_run:
        print("Dry-run termine: les .inp ont ete generes, SWMM n'a pas ete lance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
