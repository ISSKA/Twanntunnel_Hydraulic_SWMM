from __future__ import annotations

import argparse
import csv
import importlib
import itertools
import math
import re
import shutil
import subprocess
import sys
from html import escape
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BASE_INP = ROOT_DIR / "SWMM_Twannbach.inp"
DEFAULT_SCENARIOS = Path(__file__).with_name("scenarios.txt")
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("runs")
DEFAULT_SWMM_ENGINE: Path | None = None
# Exemple si tu veux lancer depuis Spyder sans argument:
# DEFAULT_SWMM_ENGINE = Path(r"C:\Program Files\EPA SWMM 5.2.4\swmm5.exe")

INPUT_TIMESERIES_NAME = "Real_disch_as_input"
INPUT_NODE = "Amont_C"
SECONDARY_INPUT_TIMESERIES_NAME = "Real_disch_as_input_conduit_48"
SECONDARY_INPUT_LINK = "48"
SECONDARY_INPUT_FRACTION = 0.05
SIMULATION_START = datetime(2000, 1, 1, 0, 0)
SIMULATION_END = datetime(2000, 1, 2, 0, 0)
REPORT_STEP = "01:00:00"
FIXED_AMONT_FLOW_M3S = 14.7


@dataclass(frozen=True)
class Hydrology:
    name: str
    timeseries_file: Path | None = None
    constant_flow_m3s: float | None = None


DEFAULT_HYDROLOGIES = {
    "Q14_7": Hydrology(name="Q14_7", constant_flow_m3s=FIXED_AMONT_FLOW_M3S),
}

RESULT_LINKS = ["ALL"]
RESULT_OUTFALLS = [
    "Fensterstollen",
    "Entw_Stollen",
    "Brunnmuehle(Teich)",
    "TWT_Portail_Est_61+665",
]
STABLE_WINDOW_HOURS = 4
MIN_POINTS_NEAR_PEAK = 3
NEAR_PEAK_RATIO = 0.95
FLOODING_MIN_RATE_M3S = 0.01
FLOODING_MIN_CONSECUTIVE_STEPS = 4
FLOODING_MIN_HOURS = 6.0
MIN_COMBINATION_PROBABILITY = 1e-4


@dataclass(frozen=True)
class Action:
    command: str
    values: dict[str, str]
    source_line: int


@dataclass
class Variant:
    name: str
    actions: list[Action] = field(default_factory=list)
    probability: float | None = None


@dataclass
class Phase:
    name: str
    actions: list[Action] = field(default_factory=list)
    variants: list[Variant] = field(default_factory=list)


@dataclass
class Scenario:
    name: str
    phases: list[Phase] = field(default_factory=list)
    stop_after_phase: str | None = None
    combine_variants_within_phase: bool = False


@dataclass(frozen=True)
class SimulationCase:
    scenario: str
    phase: str
    variant_path: tuple[str, ...]
    combination_probability: float | None
    hydrology: str
    actions: tuple[Action, ...]
    hydrology_config: Hydrology

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


@dataclass(frozen=True)
class CaseRunResult:
    index: int
    simulation_id: str
    row: dict[str, object] | None
    messages: tuple[str, ...]


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
    skip_next_value = False

    for index, token in enumerate(tokens):
        if skip_next_value:
            skip_next_value = False
            continue

        if "=" in token:
            key, value = token.split("=", 1)
            normalized_key = key.strip().lower().replace("-", "_")
            if value == "" and index + 1 < len(tokens) and "=" not in tokens[index + 1]:
                value = tokens[index + 1]
                skip_next_value = True
            values[normalized_key] = value.strip().strip('"')
        else:
            positional.append(token.strip().strip('"'))

    if positional:
        values["_positional"] = "|".join(positional)
    if not values:
        raise ValueError(f"Ligne {source_line}: action sans parametres.")
    return values


def results_csv_name(hydrologies: dict[str, Hydrology]) -> str:
    if len(hydrologies) == 1:
        hydrology = next(iter(hydrologies.values()))
        if hydrology.constant_flow_m3s is not None:
            return f"{slugify(hydrology.name)}_mass_simulations_results.csv"
        return f"{slugify(hydrology.name)}_mass_simulations_results.csv"
    return "mass_simulations_results.csv"


def parse_scenarios(path: Path) -> tuple[list[Scenario], dict[str, Hydrology]]:
    scenarios: list[Scenario] = []
    hydrologies = dict(DEFAULT_HYDROLOGIES)
    explicit_hydrologies_declared = False
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
                if not explicit_hydrologies_declared:
                    hydrologies = {}
                    explicit_hydrologies_declared = True
                hydrologies[rest[0]] = Hydrology(
                    name=rest[0],
                    timeseries_file=resolve_path(" ".join(rest[1:]), path.parent),
                )
                continue

            if keyword in {"constant_flow", "constant_inflow", "debit_constant"}:
                if len(rest) < 2:
                    raise ValueError(
                        f"Ligne {line_number}: utiliser 'constant_flow nom debit_m3s'."
                    )
                if not explicit_hydrologies_declared:
                    hydrologies = {}
                    explicit_hydrologies_declared = True
                hydrologies[rest[0]] = Hydrology(
                    name=rest[0],
                    constant_flow_m3s=float(rest[1]),
                )
                continue

            if keyword == "stop_after_phase":
                if current_scenario is None:
                    raise ValueError(
                        f"Ligne {line_number}: stop_after_phase avant scenario."
                    )
                if not rest:
                    raise ValueError(
                        f"Ligne {line_number}: nom de phase manquant."
                    )
                current_scenario.stop_after_phase = " ".join(rest)
                continue

            if keyword in {
                "combine_variants_within_phase",
                "combine_phase_variants",
                "combiner_variantes_phase",
            }:
                if current_scenario is None:
                    raise ValueError(
                        f"Ligne {line_number}: combine_variants_within_phase avant scenario."
                    )
                value = rest[0].lower() if rest else "yes"
                current_scenario.combine_variants_within_phase = value in {
                    "1",
                    "true",
                    "yes",
                    "oui",
                    "on",
                }
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

            if keyword in {"prob", "probability", "probabilite"} or keyword.startswith("prob="):
                if current_variant is None:
                    raise ValueError(
                        f"Ligne {line_number}: probabilite declaree hors variante."
                    )
                values = parse_key_values(tokens, line_number)
                if "prob" not in values:
                    raise ValueError(
                        f"Ligne {line_number}: utiliser prob=<valeur entre 0 et 1>."
                    )
                current_variant.probability = parse_probability(
                    values["prob"],
                    f"variante {current_variant.name}",
                )
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
    probability: float | None = 1.0


def multiply_probabilities(*probabilities: float | None) -> float | None:
    result = 1.0
    for probability in probabilities:
        if probability is None:
            return None
        result *= probability
    return result


def parse_probability(value: str, context: str) -> float:
    probability = float(value)
    if probability < 0 or probability > 1:
        raise ValueError(
            f"Probabilite hors intervalle [0, 1] pour {context}: {probability}"
        )
    return probability


def variant_probability(variant: Variant) -> float | None:
    if variant.probability is not None:
        return variant.probability

    values = [
        action.values["prob"]
        for action in variant.actions
        if "prob" in action.values
    ]
    if not values:
        return None

    return parse_probability(values[0], f"variante {variant.name}")


def phase_subset_probability(
    selected_variants: tuple[Variant, ...],
    action_variants: list[Variant],
) -> float | None:
    selected_names = {variant.name for variant in selected_variants}
    probability = 1.0
    for variant in action_variants:
        variant_prob = variant_probability(variant)
        if variant_prob is None:
            return None
        if variant.name in selected_names:
            probability *= variant_prob
        else:
            probability *= 1.0 - variant_prob
    return probability


def phase_variant_alternatives(phase: Phase, combine_within_phase: bool) -> list[VariantCombination]:
    variants = phase.variants or [Variant(name="base")]

    if not combine_within_phase or len(variants) <= 1:
        return [
            VariantCombination(
                names=(f"{phase.name}-{variant.name}",),
                actions=(*phase.actions, *variant.actions),
                probability=variant_probability(variant),
            )
            for variant in variants
        ]

    alternatives: list[VariantCombination] = []
    base_variants = [variant for variant in variants if not variant.actions]
    action_variants = [variant for variant in variants if variant.actions]

    for base_variant in base_variants:
        base_probability = variant_probability(base_variant)
        alternatives.append(
            VariantCombination(
                names=(f"{phase.name}-{base_variant.name}",),
                actions=tuple(phase.actions),
                probability=(
                    base_probability
                    if base_probability is not None
                    else phase_subset_probability(tuple(), action_variants)
                ),
            )
        )

    for subset_size in range(1, len(action_variants) + 1):
        for subset in itertools.combinations(action_variants, subset_size):
            alternatives.append(
                VariantCombination(
                    names=(
                        f"{phase.name}-" + "+".join(variant.name for variant in subset),
                    ),
                    actions=(
                        *phase.actions,
                        *itertools.chain.from_iterable(
                            variant.actions for variant in subset
                        ),
                    ),
                    probability=phase_subset_probability(subset, action_variants),
                )
            )
    return alternatives


def count_phase_alternatives(phase: Phase, combine_within_phase: bool) -> int:
    variant_count = len(phase.variants) if phase.variants else 1
    if combine_within_phase and variant_count > 1:
        base_variant_count = sum(1 for variant in phase.variants if not variant.actions)
        action_variant_count = variant_count - base_variant_count
        return base_variant_count + 2**action_variant_count - 1
    return variant_count


def estimate_case_count(
    scenarios: list[Scenario],
    hydrologies: dict[str, Hydrology],
    final_phase_only: bool = False,
    min_combination_probability: float | None = MIN_COMBINATION_PROBABILITY,
) -> int:
    total = 0
    hydrology_count = len(hydrologies)
    for scenario in scenarios:
        combinations = [VariantCombination(names=(), actions=(), probability=1.0)]
        phases = selected_phases(scenario)
        for phase_index, phase in enumerate(phases):
            phase_alternatives = phase_variant_alternatives(
                phase,
                scenario.combine_variants_within_phase,
            )
            next_combinations = combine_variant_paths(combinations, phase_alternatives)
            combinations = filter_combinations_by_probability(
                next_combinations,
                min_combination_probability,
            )
            is_last_phase = phase_index == len(phases) - 1
            if final_phase_only and not is_last_phase:
                continue
            total += len(combinations) * hydrology_count
            if not combinations:
                break
    return total


def build_cases(
    scenarios: list[Scenario],
    hydrologies: dict[str, Hydrology],
    final_phase_only: bool = False,
    min_combination_probability: float | None = MIN_COMBINATION_PROBABILITY,
) -> list[SimulationCase]:
    cases: list[SimulationCase] = []

    for scenario in scenarios:
        combinations = [VariantCombination(names=(), actions=(), probability=1.0)]
        phases = selected_phases(scenario)
        for phase_index, phase in enumerate(phases):
            phase_alternatives = phase_variant_alternatives(
                phase,
                scenario.combine_variants_within_phase,
            )
            next_combinations = combine_variant_paths(combinations, phase_alternatives)
            combinations = filter_combinations_by_probability(
                next_combinations,
                min_combination_probability,
            )
            is_last_phase = phase_index == len(phases) - 1
            if final_phase_only and not is_last_phase:
                continue

            for combination in combinations:
                for hydrology_name, hydrology in hydrologies.items():
                    cases.append(
                        SimulationCase(
                            scenario=scenario.name,
                            phase=phase.name,
                            variant_path=combination.names,
                            combination_probability=combination.probability,
                            hydrology=hydrology_name,
                            actions=combination.actions,
                            hydrology_config=hydrology,
                        )
                    )

            if not combinations:
                break

    return cases


def combine_variant_paths(
    combinations: list[VariantCombination],
    phase_alternatives: list[VariantCombination],
) -> list[VariantCombination]:
    next_combinations: list[VariantCombination] = []
    for combination in combinations:
        for phase_alternative in phase_alternatives:
            next_combinations.append(
                VariantCombination(
                    names=(*combination.names, *phase_alternative.names),
                    actions=(
                        *combination.actions,
                        *phase_alternative.actions,
                    ),
                    probability=multiply_probabilities(
                        combination.probability,
                        phase_alternative.probability,
                    ),
                )
            )
    return next_combinations


def filter_combinations_by_probability(
    combinations: list[VariantCombination],
    min_probability: float | None,
) -> list[VariantCombination]:
    if min_probability is None or min_probability <= 0:
        return combinations
    return [
        combination
        for combination in combinations
        if combination.probability is not None
        and combination.probability > min_probability
    ]


def selected_phases(scenario: Scenario) -> list[Phase]:
    if scenario.stop_after_phase is None:
        return scenario.phases

    phases: list[Phase] = []
    for phase in scenario.phases:
        phases.append(phase)
        if phase.name == scenario.stop_after_phase:
            return phases

    raise ValueError(
        f"Phase stop_after_phase introuvable dans {scenario.name}: "
        f"{scenario.stop_after_phase}"
    )


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


def replace_token_in_first_existing_section(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    section_names: tuple[str, ...],
    name: str,
    token_index: int,
    value: str,
) -> None:
    for section in section_names:
        try:
            replace_token(lines, sections, section, name, token_index, value)
            return
        except KeyError:
            continue
    raise KeyError(
        f"Element '{name}' introuvable dans "
        + " ou ".join(f"[{section}]" for section in section_names)
        + "."
    )


def get_token(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    section: str,
    name: str,
    token_index: int,
) -> str:
    row_index = find_named_row(lines, sections, section, name)
    tokens = split_data_line(lines[row_index])
    if len(tokens) <= token_index:
        raise ValueError(
            f"Ligne {row_index + 1}: impossible de lire le champ {token_index}."
        )
    return tokens[token_index]


def set_section_value(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    section: str,
    key: str,
    value: str,
) -> dict[str, tuple[int, int]]:
    start, end = section_body_range(sections, section)
    for index in range(start, end):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith(";"):
            continue
        tokens = split_data_line(stripped)
        if tokens and tokens[0] == key:
            lines[index] = format_row([key, value])
            return sections

    lines.insert(end, format_row([key, value]))
    return recompute_sections(lines)


def append_to_section(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    section: str,
    row: str,
) -> dict[str, tuple[int, int]]:
    _, end = section_body_range(sections, section)
    lines.insert(end, row)
    return recompute_sections(lines)


def upsert_named_row(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    section: str,
    name: str,
    row: str,
) -> dict[str, tuple[int, int]]:
    try:
        row_index = find_named_row(lines, sections, section, name)
    except KeyError:
        return append_to_section(lines, sections, section, row)

    lines[row_index] = row
    return sections


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

    if command in {"set_junction_elevation", "junction_elevation", "invert_elev", "radier"}:
        node = get_value(action, "node", "junction", "_0")
        elevation = get_value(action, "elevation", "invert_elev", "radier", "_1")
        replace_token_in_first_existing_section(
            lines,
            sections,
            ("JUNCTIONS", "OUTFALLS"),
            node,
            1,
            str(elevation),
        )
        return sections

    if command in {"set_outfall_elevation", "outfall_elevation"}:
        outfall = get_value(action, "outfall", "node", "_0")
        elevation = get_value(action, "elevation", "invert_elev", "radier", "_1")
        replace_token(lines, sections, "OUTFALLS", outfall, 1, str(elevation))
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

        sections = upsert_named_row(
            lines,
            sections,
            "CONDUITS",
            name,
            format_row([name, from_node, to_node, length, roughness, in_offset, out_offset, 0, 0]),
        )
        sections = upsert_named_row(
            lines,
            sections,
            "XSECTIONS",
            name,
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


def configure_simulation_window(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
) -> dict[str, tuple[int, int]]:
    options = {
        "START_DATE": f"{SIMULATION_START:%m/%d/%Y}",
        "START_TIME": f"{SIMULATION_START:%H:%M:%S}",
        "REPORT_START_DATE": f"{SIMULATION_START:%m/%d/%Y}",
        "REPORT_START_TIME": f"{SIMULATION_START:%H:%M:%S}",
        "END_DATE": f"{SIMULATION_END:%m/%d/%Y}",
        "END_TIME": f"{SIMULATION_END:%H:%M:%S}",
        "REPORT_STEP": REPORT_STEP,
        "DRY_STEP": REPORT_STEP,
    }
    for key, value in options.items():
        sections = set_section_value(lines, sections, "OPTIONS", key, value)
    return sections


def configure_inflow(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    hydrology: Hydrology,
) -> dict[str, tuple[int, int]]:
    secondary_input_node = get_token(
        lines,
        sections,
        "CONDUITS",
        SECONDARY_INPUT_LINK,
        1,
    )
    active_nodes = {INPUT_NODE, secondary_input_node}
    disable_other_flow_inflows(lines, sections, active_nodes)
    set_inflow_row(lines, sections, INPUT_NODE, INPUT_TIMESERIES_NAME)
    if hydrology.constant_flow_m3s is not None:
        sections = set_constant_timeseries(
            lines,
            sections,
            INPUT_TIMESERIES_NAME,
            hydrology.constant_flow_m3s,
        )
        set_inflow_row(
            lines,
            sections,
            secondary_input_node,
            SECONDARY_INPUT_TIMESERIES_NAME,
        )
        return set_constant_timeseries(
            lines,
            sections,
            SECONDARY_INPUT_TIMESERIES_NAME,
            hydrology.constant_flow_m3s * SECONDARY_INPUT_FRACTION,
        )
    if hydrology.timeseries_file is None:
        raise ValueError(f"Hydrologie sans timeseries ni debit constant: {hydrology.name}")
    set_timeseries_file(lines, sections, INPUT_TIMESERIES_NAME, hydrology.timeseries_file)
    set_inflow_row(lines, sections, secondary_input_node, INPUT_TIMESERIES_NAME)
    scale_inflow_row(lines, sections, secondary_input_node, SECONDARY_INPUT_FRACTION)
    return sections


def set_inflow_row(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    node: str,
    timeseries_name: str,
) -> None:
    row_index = find_named_row(lines, sections, "INFLOWS", node)
    tokens = split_data_line(lines[row_index])
    while len(tokens) < 7:
        tokens.append("0")
    tokens[1] = "FLOW"
    tokens[2] = timeseries_name
    tokens[3] = "FLOW"
    tokens[4] = "1.0"
    tokens[5] = "1"
    tokens[6] = "0"
    lines[row_index] = format_row(tokens)


def scale_inflow_row(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    node: str,
    factor: float,
) -> None:
    row_index = find_named_row(lines, sections, "INFLOWS", node)
    tokens = split_data_line(lines[row_index])
    if len(tokens) < 5:
        raise ValueError(f"Ligne {row_index + 1}: ligne [INFLOWS] incomplete.")
    tokens[4] = f"{factor:.9g}"
    lines[row_index] = format_row(tokens)


def disable_other_flow_inflows(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    active_nodes: set[str],
) -> None:
    start, end = section_body_range(sections, "INFLOWS")
    for index in range(start, end):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith(";"):
            continue
        tokens = split_data_line(stripped)
        if len(tokens) < 2 or tokens[0] in active_nodes or tokens[1].upper() != "FLOW":
            continue
        while len(tokens) < 7:
            tokens.append("0")
        tokens[4] = "0"
        tokens[5] = "0"
        tokens[6] = "0"
        lines[index] = format_row(tokens)


def set_constant_timeseries(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    timeseries_name: str,
    flow_m3s: float,
) -> dict[str, tuple[int, int]]:
    start, end = section_body_range(sections, "TIMESERIES")
    kept: list[str] = []
    for index in range(start, end):
        stripped = lines[index].strip()
        tokens = split_data_line(stripped) if stripped else []
        if stripped and not stripped.startswith(";") and tokens and tokens[0] == timeseries_name:
            continue
        kept.append(lines[index])

    generated_rows = [
        format_row([timeseries_name, f"{date:%m/%d/%Y}", f"{date:%H:%M}", f"{flow_m3s:.9g}"])
        for date in iter_hours(SIMULATION_START, SIMULATION_END)
    ]
    lines[start:end] = [*kept, *generated_rows]
    return recompute_sections(lines)


def iter_hours(start: datetime, end: datetime):
    current = start
    while current <= end:
        yield current
        current += timedelta(hours=1)


def write_case_inp(
    base_inp: Path,
    case: SimulationCase,
    case_dir: Path,
    file_stem: str | None = None,
) -> Path:
    lines, sections = read_sections(base_inp)

    for action in case.actions:
        sections = apply_action(lines, sections, action)

    sections = configure_simulation_window(lines, sections)
    sections = configure_inflow(lines, sections, case.hydrology_config)

    case_dir.mkdir(parents=True, exist_ok=True)
    inp_path = case_dir / f"{file_stem or case.slug}.inp"
    inp_path.write_text("\r\n".join(lines) + "\r\n", encoding="mbcs")
    return inp_path


def run_swmm(inp_path: Path, rpt_path: Path, out_path: Path, engine: str | None = None) -> None:
    resolved_engine = resolve_engine(engine)
    if resolved_engine:
        run_swmm_executable(resolved_engine, inp_path, rpt_path, out_path)
        return

    for module_name in ("epaswmm.solver", "epaswmm", "epa_swmm"):
        module = import_optional(module_name)
        if module is not None and try_python_swmm_module(
            module,
            module_name,
            inp_path,
            rpt_path,
            out_path,
        ):
            return

    solver = import_optional("swmm.toolkit.solver")
    if solver is not None and hasattr(solver, "swmm_run"):
        result = solver.swmm_run(str(inp_path), str(rpt_path), str(out_path))
        if isinstance(result, int) and result != 0:
            raise RuntimeError(f"swmm.toolkit.solver.swmm_run a retourne {result}.")
        return

    raise RuntimeError(
        "Aucun moteur SWMM utilisable trouve dans cet environnement Python.\n"
        f"Python utilise: {sys.executable}\n"
        "Solutions possibles:\n"
        "  1. installer epaswmm/swmm-toolkit dans ce Python;\n"
        "  2. passer --engine chemin\\vers\\swmm5.exe;\n"
        "  3. renseigner DEFAULT_SWMM_ENGINE en haut du script."
    )


def resolve_engine(engine: str | None) -> str | None:
    if engine:
        return engine
    if DEFAULT_SWMM_ENGINE is not None:
        return str(DEFAULT_SWMM_ENGINE)
    found = shutil.which("swmm5") or shutil.which("swmm5.exe")
    return found


def run_swmm_executable(engine: str, inp_path: Path, rpt_path: Path, out_path: Path) -> None:
    completed = subprocess.run(
        [engine, str(inp_path), str(rpt_path), str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "SWMM a echoue via l'executable externe.\n"
            f"Engine: {engine}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )


def try_python_swmm_module(
    module,
    module_name: str,
    inp_path: Path,
    rpt_path: Path,
    out_path: Path,
) -> bool:
    for function_name in (
        "run_solver",
        "swmm_run",
        "swmm5_run",
        "run_swmm",
        "run",
        "simulate",
    ):
        function = getattr(module, function_name, None)
        if not callable(function):
            continue
        result = function(str(inp_path), str(rpt_path), str(out_path))
        if isinstance(result, int) and result != 0:
            raise RuntimeError(f"{module_name}.{function_name} a retourne {result}.")
        return True
    return False


def diagnose_swmm_environment() -> None:
    print(f"Python utilise: {sys.executable}")
    print(f"swmm5 dans PATH: {resolve_engine(None) or 'non trouve'}")
    for module_name in ("epaswmm.solver", "epaswmm.output", "epaswmm", "epa_swmm", "swmm.toolkit.solver", "swmm.toolkit.output"):
        module = import_optional(module_name)
        if module is None:
            print(f"{module_name}: non importable")
            continue
        callables = [
            name for name in ("run_solver", "swmm_run", "swmm5_run", "run_swmm", "run", "simulate")
            if callable(getattr(module, name, None))
        ]
        print(f"{module_name}: OK ; fonctions detectees: {', '.join(callables) or 'aucune connue'}")


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


def extract_simulation_summary(
    out_path: Path,
    outfalls: list[str],
    use_rpt_only: bool = False,
) -> tuple[dict[str, float], bool, list[str]]:
    if use_rpt_only:
        return parse_report_summary(out_path.with_suffix(".rpt"), outfalls)

    try:
        outfall_records, flooding_records = read_node_result_records(out_path, outfalls)
        outfall_maxima = {
            outfall: max((flow for _, flow in outfall_records.get(outfall, [])), default=0.0)
            for outfall in outfalls
        }
        flooding_nodes = sorted(
            node
            for node, records in flooding_records.items()
            if has_significant_flooding(records)
        )
        return outfall_maxima, bool(flooding_nodes), flooding_nodes
    except RuntimeError:
        rpt_path = out_path.with_suffix(".rpt")
        return parse_report_summary(rpt_path, outfalls)


def parse_report_summary(rpt_path: Path, outfalls: list[str]) -> tuple[dict[str, float], bool, list[str]]:
    if not rpt_path.exists():
        raise RuntimeError(f"Rapport SWMM introuvable pour extraction: {rpt_path}")

    lines = rpt_path.read_text(encoding="mbcs", errors="replace").splitlines()
    outfall_maxima = parse_node_inflow_summary(lines, outfalls)
    flooding_nodes = parse_node_flooding_summary(lines)
    missing = [outfall for outfall in outfalls if outfall not in outfall_maxima]
    if missing:
        raise RuntimeError(
            "Exutoires introuvables dans le Node Inflow Summary du .rpt: "
            + ", ".join(missing)
        )
    return outfall_maxima, bool(flooding_nodes), flooding_nodes


def parse_node_inflow_summary(lines: list[str], outfalls: list[str]) -> dict[str, float]:
    rows = report_table_rows(lines, "Node Inflow Summary")
    wanted = set(outfalls)
    maxima: dict[str, float] = {}
    for row in rows:
        tokens = row.split()
        if len(tokens) < 4 or tokens[0] not in wanted:
            continue
        maxima[tokens[0]] = parse_float(tokens[3])
    return maxima


def parse_node_flooding_summary(lines: list[str]) -> list[str]:
    rows = report_table_rows(lines, "Node Flooding Summary")
    flooding_nodes: list[str] = []
    for row in rows:
        tokens = row.split()
        if len(tokens) < 3:
            continue
        hours_flooded = parse_float(tokens[1], default=0.0)
        max_rate = parse_float(tokens[2], default=0.0)
        if hours_flooded >= FLOODING_MIN_HOURS and max_rate >= FLOODING_MIN_RATE_M3S:
            flooding_nodes.append(tokens[0])
    return flooding_nodes


def has_significant_flooding(records: list[tuple[datetime | None, float]]) -> bool:
    consecutive = 0
    for _, value in records:
        if value >= FLOODING_MIN_RATE_M3S:
            consecutive += 1
            if consecutive >= FLOODING_MIN_CONSECUTIVE_STEPS:
                return True
        else:
            consecutive = 0
    return False


def report_table_rows(lines: list[str], title: str) -> list[str]:
    title_index = next((index for index, line in enumerate(lines) if title in line), None)
    if title_index is None:
        return []

    rows: list[str] = []
    dash_count = 0
    for line in lines[title_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            if rows:
                break
            continue
        if set(stripped) == {"-"}:
            dash_count += 1
            if dash_count >= 2 and rows:
                break
            continue
        if dash_count < 2:
            continue
        if stripped.startswith("*"):
            break
        rows.append(stripped)
    return rows


def parse_float(text: str, default: float | None = None) -> float:
    try:
        return float(text)
    except ValueError:
        if default is not None:
            return default
        raise


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


def read_node_result_records(
    out_path: Path,
    outfalls: list[str],
) -> tuple[
    dict[str, list[tuple[datetime | None, float]]],
    dict[str, list[tuple[datetime | None, float]]],
]:
    ep_output = import_optional("epaswmm.output")
    if ep_output is not None:
        return read_node_result_records_epaswmm(out_path, outfalls, ep_output)

    output = import_optional("swmm.toolkit.output")
    shared_enum = import_optional("swmm.toolkit.shared_enum")
    if output is None:
        raise RuntimeError(
            "Lecture .out impossible: installer swmm-toolkit, ou remplacer "
            "read_node_result_records() par le lecteur epaswmm disponible localement."
        )

    out = output.Output(str(out_path))
    try:
        node_names = list(getattr(out, "nodes", []))
        missing = sorted(set(outfalls) - set(node_names))
        if missing:
            raise KeyError(f"Exutoires absents du fichier .out: {', '.join(missing)}")

        total_inflow_attribute = resolve_node_attribute(
            shared_enum,
            ("TOTAL_INFLOW", "TOTAL_INFLOW_RATE", "INFLOW", "flow"),
            "TOTAL_INFLOW",
        )
        flooding_attribute = resolve_node_attribute(
            shared_enum,
            ("FLOODING_LOSSES", "FLOODING", "OVERFLOW", "flooding_losses"),
            "FLOODING_LOSSES",
        )

        outfall_records = {
            outfall: read_object_series(out, "node", outfall, total_inflow_attribute)
            for outfall in outfalls
        }
        flooding_records = {
            node: read_object_series(out, "node", node, flooding_attribute)
            for node in node_names
        }
        return outfall_records, flooding_records
    finally:
        close = getattr(out, "close", None)
        if close is not None:
            close()


def read_node_result_records_epaswmm(
    out_path: Path,
    outfalls: list[str],
    ep_output,
) -> tuple[
    dict[str, list[tuple[datetime | None, float]]],
    dict[str, list[tuple[datetime | None, float]]],
]:
    out = ep_output.Output(str(out_path))
    node_names = list(out.get_element_names(ep_output.ElementType.NODE))
    missing = sorted(set(outfalls) - set(node_names))
    if missing:
        raise KeyError(f"Exutoires absents du fichier .out: {', '.join(missing)}")

    outfall_records = {
        outfall: dict_series_to_records(
            out.get_node_timeseries(outfall, ep_output.NodeAttribute.TOTAL_INFLOW)
        )
        for outfall in outfalls
    }
    flooding_records = {
        node: dict_series_to_records(
            out.get_node_timeseries(node, ep_output.NodeAttribute.FLOODING_LOSSES)
        )
        for node in node_names
    }
    return outfall_records, flooding_records


def dict_series_to_records(series) -> list[tuple[datetime | None, float]]:
    records: list[tuple[datetime | None, float]] = []
    iterable = series.items() if isinstance(series, dict) else enumerate(series)
    for key, value in iterable:
        date = key if isinstance(key, datetime) else None
        try:
            flow = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(flow):
            records.append((date, flow))
    return records


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


def resolve_node_attribute(shared_enum, candidates: tuple[str, ...], default: str):
    if shared_enum is None:
        return default
    node_attribute = getattr(shared_enum, "NodeAttribute", None)
    if node_attribute is None:
        return default
    for candidate in candidates:
        value = getattr(node_attribute, candidate, None)
        if value is not None:
            return value
    return default


def read_output_series(out, link: str, flow_attribute) -> list[tuple[datetime | None, float]]:
    return read_object_series(out, "link", link, flow_attribute)


def read_object_series(
    out,
    object_type: str,
    object_name: str,
    attribute,
) -> list[tuple[datetime | None, float]]:
    series = None
    errors: list[str] = []
    method_name = f"{object_type}_series"

    if hasattr(out, method_name):
        method = getattr(out, method_name)
        for args in ((object_name, attribute), (attribute, object_name)):
            try:
                series = method(*args)
                break
            except TypeError as exc:
                errors.append(str(exc))

    if series is None and hasattr(out, "get_part"):
        for args in (
            (object_type, object_name, attribute),
            (object_type.upper(), object_name, attribute),
        ):
            try:
                series = out.get_part(*args)
                break
            except TypeError as exc:
                errors.append(str(exc))

    if series is None:
        detail = " | ".join(errors)
        raise RuntimeError(
            f"API swmm-toolkit.output non reconnue pour les series {object_type}."
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


def write_phase_probability_plots(
    output_dir: Path,
    rows: list[dict[str, object]],
    outfalls: list[str],
    filename_prefix: str = "",
    title_prefix: str = "",
) -> list[Path]:
    if not rows:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    rows_by_phase: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        phase = str(row.get("phase", "unknown") or "unknown")
        rows_by_phase.setdefault(phase, []).append(row)

    plot_paths: list[Path] = []
    for phase, phase_rows in sorted(rows_by_phase.items()):
        html = render_phase_probability_plot(phase, phase_rows, outfalls, title_prefix)
        path = output_dir / plot_filename(filename_prefix, phase)
        path.write_text(html, encoding="utf-8")
        plot_paths.append(path)
    return plot_paths


def plot_filename(filename_prefix: str, phase: str) -> str:
    prefix = f"{filename_prefix}_" if filename_prefix else ""
    return f"{prefix}{phase_filename_part(phase)}_debits_vs_probability.html"


def scenario_filename_part(scenario: str) -> str:
    match = re.search(r"(\d+)$", scenario)
    return match.group(1) if match else slugify(scenario)


def phase_filename_part(phase: str) -> str:
    match = re.match(r"^\d+_(.+)$", phase)
    return slugify(match.group(1) if match else phase)


def render_phase_probability_plot(
    phase: str,
    rows: list[dict[str, object]],
    outfalls: list[str],
    title_prefix: str = "",
) -> str:
    chart_blocks = [
        render_probability_svg(phase, rows, outfall)
        for outfall in outfalls
    ]
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="fr">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>Debits vs probabilite - {escape(title_prefix + phase)}</title>",
            "<style>",
            "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f5;color:#202124}",
            "h1{font-size:22px;margin:0 0 18px}",
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:18px}",
            ".chart{background:#fff;border:1px solid #ddd;border-radius:6px;padding:14px}",
            ".title{font-weight:600;margin:0 0 8px}",
            "svg{width:100%;height:auto;display:block}",
            ".axis{stroke:#555;stroke-width:1}",
            ".gridline{stroke:#e3e3e3;stroke-width:1}",
            ".reference-flow{stroke:#1f6fbd;stroke-width:2}",
            ".reference-probability{stroke:#1f6fbd;stroke-width:1.8;stroke-dasharray:6 5}",
            ".reference-label{fill:#1f6fbd;font-size:11px;font-weight:600}",
            ".point{fill:#2468a8;fill-opacity:.72;stroke:#123b5f;stroke-width:.6}",
            ".point:hover{fill:#d24b2a;fill-opacity:1}",
            ".label{fill:#555;font-size:11px}",
            ".empty{color:#777;font-size:13px}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{escape(title_prefix)}Phase {escape(phase)} - debit maximum en fonction de la probabilite</h1>",
            '<div class="grid">',
            *chart_blocks,
            "</div>",
            "</body>",
            "</html>",
        ]
    )


def render_probability_svg(
    phase: str,
    rows: list[dict[str, object]],
    outfall: str,
) -> str:
    q_key = f"qmax_{slugify(outfall)}_m3s"
    points: list[tuple[float, float, str]] = []
    for row in rows:
        probability = parse_optional_float(row.get("combination_probability"))
        flow = parse_optional_float(row.get(q_key))
        if probability is None or probability <= 0 or flow is None:
            continue
        label = str(row.get("variant_combination", ""))
        points.append((probability, flow, label))

    title = escape(outfall)
    if not points:
        return (
            '<section class="chart">'
            f'<p class="title">{title}</p>'
            '<p class="empty">Aucun point avec probabilite et debit disponibles.</p>'
            "</section>"
        )

    width = 720
    height = 420
    left = 68
    right = 22
    top = 24
    bottom = 54
    plot_width = width - left - right
    plot_height = height - top - bottom
    log_probabilities = [math.log10(probability) for probability, _, _ in points]
    reference_probability = 1e-5
    reference_log_x = math.log10(reference_probability)
    min_log_x = min(*log_probabilities, reference_log_x)
    max_log_x = max(*log_probabilities, reference_log_x)
    max_y = max(flow for _, flow, _ in points)
    max_y = max(max_y, 1e-12)
    if min_log_x == max_log_x:
        min_log_x -= 0.5
        max_log_x += 0.5

    def x_scale(value: float) -> float:
        log_value = math.log10(value)
        return left + (log_value - min_log_x) / (max_log_x - min_log_x) * plot_width

    def y_scale(value: float) -> float:
        return top + plot_height - value / max_y * plot_height

    grid_lines: list[str] = []
    x_ticks = log_ticks(min_log_x, max_log_x)
    for x_value in x_ticks:
        x = x_scale(x_value)
        grid_lines.append(
            f'<line class="gridline" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}"/>'
        )
        grid_lines.append(
            f'<text class="label" x="{x:.1f}" y="{height - 24}" text-anchor="middle">{format_probability_tick(x_value)}</text>'
        )

    for tick in range(6):
        y_value = max_y * tick / 5
        y = y_scale(y_value)
        grid_lines.append(
            f'<line class="gridline" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>'
        )
        grid_lines.append(
            f'<text class="label" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{y_value:.3g}</text>'
        )

    highest_probability, flow_at_highest_probability, highest_probability_label = max(
        points,
        key=lambda item: item[0],
    )
    reference_flow_y = y_scale(flow_at_highest_probability)
    reference_probability_x = x_scale(reference_probability)
    reference_elements = [
        (
            f'<line class="reference-flow" x1="{left}" y1="{reference_flow_y:.1f}" '
            f'x2="{left + plot_width}" y2="{reference_flow_y:.1f}">'
            f'<title>Debit du cas le plus probable: '
            f'{escape(highest_probability_label)} ; '
            f'P={highest_probability:.6g} ; Qmax={flow_at_highest_probability:.6g} m3/s</title>'
            "</line>"
        ),
        (
            f'<text class="reference-label" x="{left + plot_width - 4}" '
            f'y="{max(top + 12, reference_flow_y - 5):.1f}" text-anchor="end">'
            f'Q a P max = {flow_at_highest_probability:.3g}'
            "</text>"
        ),
        (
            f'<line class="reference-probability" x1="{reference_probability_x:.1f}" '
            f'y1="{top}" x2="{reference_probability_x:.1f}" y2="{top + plot_height}">'
            f"<title>Probabilite de reference: {reference_probability:.0e}</title>"
            "</line>"
        ),
        (
            f'<text class="reference-label" x="{reference_probability_x + 4:.1f}" '
            f'y="{top + 14}" text-anchor="start">P=1e-5</text>'
        ),
    ]

    point_elements = []
    for probability, flow, label in sorted(points):
        x = x_scale(probability)
        y = y_scale(flow)
        tooltip = escape(f"{label}\nP={probability:.6g}\nQmax={flow:.6g} m3/s")
        point_elements.append(
            f'<circle class="point" cx="{x:.1f}" cy="{y:.1f}" r="3.4"><title>{tooltip}</title></circle>'
        )

    return "\n".join(
        [
            '<section class="chart">',
            f'<p class="title">{title}</p>',
            f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{title}">',
            *grid_lines,
            f'<line class="axis" x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}"/>',
            f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}"/>',
            *reference_elements,
            f'<text class="label" x="{left + plot_width / 2:.1f}" y="{height - 6}" text-anchor="middle">Probabilite de la combinaison (log10)</text>',
            f'<text class="label" x="14" y="{top + plot_height / 2:.1f}" transform="rotate(-90 14 {top + plot_height / 2:.1f})" text-anchor="middle">Qmax (m3/s)</text>',
            *point_elements,
            "</svg>",
            "</section>",
        ]
    )


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


def format_date(value: datetime | None) -> str:
    return "" if value is None else value.strftime("%Y-%m-%d %H:%M")


def simulation_id_for_index(index: int) -> str:
    return f"sim_{index:04d}"


def scenario_output_dir(output_dir: Path, scenario_name: str) -> Path:
    return output_dir / slugify(scenario_name)


def hydrology_output_dir(output_dir: Path, scenario_name: str, hydrology_name: str) -> Path:
    return scenario_output_dir(output_dir, scenario_name) / slugify(hydrology_name)


def phase_output_dir(output_dir: Path, case: SimulationCase) -> Path:
    return hydrology_output_dir(output_dir, case.scenario, case.hydrology) / slugify(case.phase)


def case_output_dir(output_dir: Path, case: SimulationCase, simulation_id: str) -> Path:
    return phase_output_dir(output_dir, case) / simulation_id


def write_results_by_scenario(
    output_dir: Path,
    rows: list[dict[str, object]],
    hydrologies: dict[str, Hydrology],
    outfalls: list[str],
) -> list[Path]:
    rows_by_group: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        scenario = str(row.get("scenario", "scenario") or "scenario")
        hydrology = str(row.get("hydrology", "hydrology") or "hydrology")
        rows_by_group.setdefault((scenario, hydrology), []).append(row)

    written_paths: list[Path] = []
    plots_dir = output_dir / "plots"
    for (scenario, hydrology), group_rows in sorted(rows_by_group.items()):
        group_dir = hydrology_output_dir(output_dir, scenario, hydrology)
        group_hydrologies = {hydrology: hydrologies[hydrology]} if hydrology in hydrologies else hydrologies
        results_path = group_dir / results_csv_name(group_hydrologies)
        write_results_csv(results_path, group_rows)
        written_paths.append(results_path)
        plot_prefix = f"{scenario_filename_part(scenario)}_{slugify(hydrology)}"
        plot_title_prefix = f"Scenario {scenario_filename_part(scenario)} - {hydrology} - "
        written_paths.extend(
            write_phase_probability_plots(
                plots_dir,
                group_rows,
                outfalls,
                filename_prefix=plot_prefix,
                title_prefix=plot_title_prefix,
            )
        )
    return written_paths


def run_case_task(
    index: int,
    total: int,
    case: SimulationCase,
    base_inp: Path,
    output_dir: Path,
    engine: str | None,
    outfalls: list[str],
    use_rpt_only: bool,
) -> CaseRunResult:
    simulation_id = simulation_id_for_index(index)
    case_dir = case_output_dir(output_dir, case, simulation_id)
    messages = [f"[{index}/{total}] {simulation_id}: {case.variant}"]

    inp_path = write_case_inp(base_inp, case, case_dir, simulation_id)
    rpt_path = case_dir / f"{simulation_id}.rpt"
    out_path = case_dir / f"{simulation_id}.out"

    run_swmm(inp_path, rpt_path, out_path, engine)
    outfall_maxima, has_flooding, flooding_nodes = extract_simulation_summary(
        out_path,
        outfalls,
        use_rpt_only=use_rpt_only,
    )
    if has_flooding:
        messages.append(
            "  WARNING flooding: "
            f"{len(flooding_nodes)} junction(s): {', '.join(flooding_nodes)}"
        )

    row: dict[str, object] = {
        "simulation_id": simulation_id,
        "case_directory": str(case_dir),
        "scenario": case.scenario,
        "phase": case.phase,
        "variant_combination": case.variant,
        "combination_probability": (
            "" if case.combination_probability is None else f"{case.combination_probability:.12g}"
        ),
        "hydrology": case.hydrology,
        "flooding_warning": "YES" if has_flooding else "NO",
        "flooding_nodes": ", ".join(flooding_nodes),
    }
    for outfall in outfalls:
        row[f"qmax_{slugify(outfall)}_m3s"] = f"{outfall_maxima[outfall]:.6g}"

    messages.append(
        "  "
        + " ; ".join(
            f"{outfall}={outfall_maxima[outfall]:.6g} m3/s"
            for outfall in outfalls
        )
    )
    return CaseRunResult(
        index=index,
        simulation_id=simulation_id,
        row=row,
        messages=tuple(messages),
    )


def print_case_result(result: CaseRunResult) -> None:
    for message in result.messages:
        print(message)


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
        "--outfalls",
        nargs="+",
        default=RESULT_OUTFALLS,
        help="Exutoires SWMM a extraire comme colonnes de debit maximum.",
    )
    parser.add_argument(
        "--final-phase-only",
        action="store_true",
        help=(
            "Ne lance que les combinaisons cumulees de la derniere phase. "
            "Avec combine_variants_within_phase yes, chaque phase genere 2^n - 1 branches."
        ),
    )
    parser.add_argument(
        "--all-phases",
        action="store_true",
        help=(
            "Conserve pour compatibilite: les phases intermediaires sont lancees par defaut."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Nombre de simulations SWMM a lancer en parallele. Exemple prudent: --workers 4.",
    )
    parser.add_argument(
        "--use-rpt-only",
        action="store_true",
        help="Lit les maxima et le flooding dans les rapports .rpt, sans ouvrir les fichiers .out.",
    )
    parser.add_argument(
        "--min-combination-probability",
        type=float,
        default=MIN_COMBINATION_PROBABILITY,
        help=(
            "Seuil strict de probabilite pour simuler une combinaison et la transmettre "
            "a la phase suivante. Utiliser 0 pour desactiver le filtrage."
        ),
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=100000,
        help=(
            "Nombre maximum de simulations autorise sans --allow-large-run. "
            "Garde-fou contre les explosions combinatoires."
        ),
    )
    parser.add_argument(
        "--allow-large-run",
        action="store_true",
        help="Autorise explicitement un lancement depassant --max-cases.",
    )
    parser.add_argument(
        "--diagnose-swmm",
        action="store_true",
        help="Affiche le Python utilise et les moteurs SWMM importables, sans lancer de simulation.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.diagnose_swmm:
        diagnose_swmm_environment()
        return 0

    scenarios, hydrologies = parse_scenarios(args.scenarios)
    final_phase_only = args.final_phase_only and not args.all_phases
    estimated_cases = estimate_case_count(
        scenarios,
        hydrologies,
        final_phase_only=final_phase_only,
        min_combination_probability=args.min_combination_probability,
    )
    if estimated_cases > args.max_cases and not args.allow_large_run:
        raise RuntimeError(
            f"{estimated_cases} simulations seraient generees. "
            "C'est probablement tres long avec les combinaisons intra-phase.\n"
            f"Pour lancer quand meme: ajouter --allow-large-run, ou augmenter --max-cases "
            f"(actuel: {args.max_cases})."
        )

    cases = build_cases(
        scenarios,
        hydrologies,
        final_phase_only=final_phase_only,
        min_combination_probability=args.min_combination_probability,
    )

    if not cases:
        print("Aucune simulation a lancer.")
        return 0

    missing_timeseries = [
        hydrology.timeseries_file
        for hydrology in hydrologies.values()
        if hydrology.timeseries_file is not None and not hydrology.timeseries_file.exists()
    ]
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

    workers = max(1, args.workers)
    rows: list[dict[str, object]] = []
    print(f"{len(cases)} simulations preparees.")
    if args.min_combination_probability > 0:
        print(
            "Filtre probabilite: "
            f"combination_probability > {args.min_combination_probability:g}."
        )
    if not args.dry_run and workers > 1:
        print(f"Execution parallele: {workers} workers.")
    if not args.dry_run and args.use_rpt_only:
        print("Extraction des resultats via .rpt uniquement.")

    if args.dry_run:
        for index, case in enumerate(cases, start=1):
            simulation_id = simulation_id_for_index(index)
            case_dir = case_output_dir(args.output_dir, case, simulation_id)
            print(f"[{index}/{len(cases)}] {simulation_id}: {case.variant}")
            inp_path = write_case_inp(args.base_inp, case, case_dir, simulation_id)
            print(f"  INP genere: {inp_path}")
    elif workers == 1:
        for index, case in enumerate(cases, start=1):
            result = run_case_task(
                index=index,
                total=len(cases),
                case=case,
                base_inp=args.base_inp,
                output_dir=args.output_dir,
                engine=args.engine,
                outfalls=args.outfalls,
                use_rpt_only=args.use_rpt_only,
            )
            print_case_result(result)
            if result.row is not None:
                rows.append(result.row)
    else:
        results: list[CaseRunResult] = []
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(
                    run_case_task,
                    index,
                    len(cases),
                    case,
                    args.base_inp,
                    args.output_dir,
                    args.engine,
                    args.outfalls,
                    args.use_rpt_only,
                )
                for index, case in enumerate(cases, start=1)
            ]
            for completed_count, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                results.append(result)
                print(
                    f"[done {completed_count}/{len(cases)}] "
                    f"{result.simulation_id}"
                )
                for message in result.messages[1:]:
                    print(message)

        for result in sorted(results, key=lambda item: item.index):
            if result.row is not None:
                rows.append(result.row)

    if rows:
        written_paths = write_results_by_scenario(
            args.output_dir,
            rows,
            hydrologies,
            args.outfalls,
        )
        print("Fichiers de synthese:")
        for path in written_paths:
            print(f"  - {path}")

    if args.dry_run:
        print("Dry-run termine: les .inp ont ete generes, SWMM n'a pas ete lance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
