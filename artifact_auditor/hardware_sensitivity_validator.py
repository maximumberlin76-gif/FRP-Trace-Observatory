"""Read-only validation for Hardware-Informed Sensitivity artifacts.

The validator covers the two exact schema identifiers registered for the
Hardware-Informed Sensitivity Qualification contour. It validates published
profile, scenario, ranking, qualification, and digest relations without
executing producers, reconstructing processor semantics, or treating the
results as physical-chip measurements.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations

from parsers.artifact_dispatch import (
    ArtifactClassification,
    DispatchedArtifact,
    RegistrationStatus,
)
from parsers.json_artifact import JsonValue, ParsedJsonArtifact
from schemas.registry import MeasurementContour

from .audit_report import CheckOutcome, SourceLocation, ValidationCategory
from .validation_core import ValidationCheckSpec


__all__ = [
    "HardwareSensitivityValidation",
    "HardwareSensitivityValidationError",
    "validate_hardware_sensitivity",
]


_PROFILE_SCHEMA = "frp.benchmark.hardware_sensitivity_cost_profile.v1"
_COMPARISON_SCHEMA = "frp.benchmark.hardware_sensitivity_comparison.v1"
_SCHEMAS = (_PROFILE_SCHEMA, _COMPARISON_SCHEMA)
_SUITE = "FRP Comparative Architecture Benchmark Suite"
_PROFILE_NAME = "literature_anchored_cmos45_sensitivity_v1"
_PROFILE_ROLE = "hardware_informed_sensitivity"
_PROFILE_STATUS = "reference_sensitivity_profile"
_BASELINE_PROFILE = "unit_event_cost_v1"
_BASELINE_RESULT = (
    "benchmarks/architecture_comparison/results/"
    "reference_comparison_seed_76.json"
)
_PROVENANCE_MAP = (
    "benchmarks/architecture_comparison/calibration/"
    "coefficient_provenance_map_v1.md"
)
_BENCHMARK_KIND = "hardware_informed_sensitivity_matrix"
_FRP_VERSION = "1.7.0"
_SCHEDULERS = frozenset({"7/1", "1/7"})
_QUALIFICATION_POLICY = "integrity_only_no_winner_assertions"
_SCENARIO_COST_UNIT = "normalized_32bit_add_equivalent"
_THERMAL_EQUATION = (
    "ambient + (temperature - ambient) * thermal_decay "
    "+ normalized_cycle_cost * thermal_gain"
)
_HEX = frozenset("0123456789abcdef")
_FLOAT_TOLERANCE = 1e-12


def _names(text: str) -> tuple[str, ...]:
    return tuple(text.split())


_SCENARIO_ORDER = _names("lower_bound nominal upper_bound")
_COST_CLASSES = _names(
    "encoded_bit_toggle clocked_state_bit register_write_bit "
    "comparison_event control_event queue_read queue_write lut_read_32 "
    "fixed_point_multiply_32x32 fixed_point_accumulate_64 "
    "fixed_point_add_32 fixed_point_compare_32"
)
_EVENT_FIELDS = _names(
    "encoded_bit_toggles clocked_state_bits register_write_bits "
    "comparison_events control_events queue_reads queue_writes lut_reads_32 "
    "fixed_point_multiplies_32x32 fixed_point_accumulates_64 "
    "fixed_point_adds_32 fixed_point_compares_32"
)
_EVENT_TO_COST = dict(zip(_EVENT_FIELDS, _COST_CLASSES, strict=True))
_ARCHITECTURE_ORDER = _names(
    "binary_synchronous_reference binary_clock_gated_reference "
    "direct_ternary_reference frp_v1_7_0_quantized_shadow"
)
_REFERENCE_ORDER = _names(
    "HOROWITZ_ISSCC_2014_32BIT_INT_ADD "
    "HOROWITZ_ISSCC_2014_32BIT_INT_MULT "
    "HOROWITZ_ISSCC_2014_8KB_CACHE_64BIT_ACCESS "
    "HOROWITZ_ISSCC_2014_LOCAL_MEMORY_HIERARCHY"
)
_PROFILE_ROOT_FIELDS = frozenset(
    _names(
        "schema suite_name profile_name profile_role profile_status "
        "baseline_profile baseline_result provenance_map "
        "normalization_reference reference_basis scenario_order "
        "coefficient_order coefficients scenario_vectors "
        "evaluation_contract validation_contract digest_contract "
        "cost_profile_sha256"
    )
)
_NORMALIZATION_FIELDS = frozenset(
    _names(
        "primitive normalized_weight reference_energy_value "
        "reference_energy_unit reference_technology_node_nm "
        "reference_voltage_v reference_key"
    )
)
_REFERENCE_FIELDS = frozenset(
    _names(
        "reference_key author title venue year pages doi primitive "
        "reference_energy_value reference_energy_unit technology_node_nm "
        "approximate role"
    )
)
_COEFFICIENT_FIELDS = frozenset(
    _names(
        "event_field cost_class lower_bound nominal_weight upper_bound "
        "basis_type reference_key reference source_value source_unit "
        "technology_node_nm voltage_v implementation_assumption "
        "derivation_rule uncertainty_class"
    )
)
_EVALUATION_FIELDS = frozenset(
    _names(
        "execute_architectures_once preserve_raw_event_traces "
        "apply_same_scenario_vector_to_all_architectures "
        "scenario_result_order thermal_profile winner_assertions"
    )
)
_VALIDATION_FIELDS = frozenset(
    _names(
        "required_cost_class_count require_exact_coefficient_order "
        "require_exact_scenario_order require_nonnegative_weights "
        "require_lower_le_nominal_le_upper "
        "require_provenance_for_every_coefficient "
        "require_same_workload_digest "
        "require_same_architecture_result_digests "
        "require_same_raw_event_traces "
        "require_semantic_completion_ratio require_semantic_output_match "
        "require_frp_actual_direct_events "
        "require_frp_reserved_state_events "
        "require_frp_queue_overflow_events "
        "require_frp_pending_route_count_final "
        "require_deterministic_profile_digest "
        "require_deterministic_package_digest "
        "require_byte_identical_repeated_generation winner_assertions"
    )
)
_DIGEST_CONTRACT_FIELDS = frozenset(
    _names("algorithm canonicalization excluded_field")
)
_COMPARISON_ROOT_FIELDS = frozenset(
    _names(
        "schema suite_name benchmark_kind frp_reference_version "
        "frp_scheduler architecture_order workload_profile workload_sha256 "
        "hardware_sensitivity_profile "
        "hardware_sensitivity_profile_sha256 profile_validation "
        "baseline_binding thermal_profile thermal_profile_sha256 "
        "raw_trace_ledger raw_trace_set_sha256 scenarios "
        "ranking_stability integrity qualification "
        "hardware_sensitivity_package_sha256"
    )
)
_WORKLOAD_FIELDS = frozenset(
    _names(
        "num_cells command_count seed issue_policy "
        "max_completion_cycles_per_command final_cooldown_cycles"
    )
)
_EMBEDDED_PROFILE_FIELDS = frozenset(
    _names(
        "schema profile_name profile_role profile_status "
        "cost_profile_sha256 baseline_profile baseline_result "
        "provenance_map normalization_reference scenario_order "
        "coefficient_order"
    )
)
_PROFILE_VALIDATION_FIELDS = frozenset(
    _names(
        "status schema profile_name coefficient_count scenario_order "
        "reference_count baseline_result provenance_map cost_profile_sha256"
    )
)
_BASELINE_BINDING_FIELDS = frozenset(
    _names(
        "status baseline_result baseline_schema baseline_workload_sha256 "
        "baseline_cost_profile baseline_comparison_package_sha256 "
        "architecture_result_sha256 checks current_execution"
    )
)
_BASELINE_CHECK_FIELDS = frozenset(
    _names(
        "schema_match architecture_order_match baseline_profile_match "
        "integrity_status_pass qualification_status_pass "
        "winner_assertions_empty comparison_package_digest_valid"
    )
)
_CURRENT_EXECUTION_CHECK_FIELDS = frozenset(
    _names(
        "same_workload_digest architecture_order_match "
        "architecture_result_digests_match"
    )
)
_EMBEDDED_THERMAL_FIELDS = frozenset(
    _names(
        "profile_name temperature_unit ambient_temperature_proxy "
        "thermal_decay thermal_gain"
    )
)
_RAW_LEDGER_FIELDS = frozenset(
    _names(
        "architecture_id architecture_name architecture_result_sha256 "
        "workload_sha256 processor_cycles raw_event_totals "
        "raw_event_totals_sha256 raw_event_trace_sha256 "
        "comparison_metrics architecture_specific_metrics"
    )
)
_RAW_FIELDS = frozenset(
    _EVENT_FIELDS
    + _names(
        "active_clocked_cycles logical_state_changes processor_cycles "
        "semantic_commands_completed semantic_commands_issued"
    )
)
_METRIC_FIELDS = frozenset(
    _names(
        "semantic_completion_ratio semantic_output_match completion_ticks "
        "mean_latency_ticks p95_latency_ticks maximum_latency_ticks "
        "throughput_commands_per_tick logical_state_changes "
        "encoded_bit_toggles processor_cycles active_clocked_cycles "
        "active_clock_fraction"
    )
)
_SPECIFIC_FIELDS = {
    "binary_synchronous_reference": frozenset({"direct_binary_switches"}),
    "binary_clock_gated_reference": frozenset(
        _names("clock_gate_active_fraction direct_binary_switches gated_cycles")
    ),
    "direct_ternary_reference": frozenset(
        _names("direct_opposite_polarity_changes gated_cycles neutral_state_exits")
    ),
    "frp_v1_7_0_quantized_shadow": frozenset(
        _names(
            "C_minus_P_final C_minus_P_final_q16 C_minus_P_min "
            "C_minus_P_min_q16 actual_direct_events "
            "fixed_point_thermal_sum_exact fixed_point_topology_sum_exact "
            "global_phase_coherence_final global_phase_coherence_final_q30 "
            "neutral_insertions neutral_routed_events neutralized_conflicts "
            "pending_route_count_final pending_route_peak "
            "prevented_direct_events queue_overflow_events "
            "requested_direct_events reserved_state_events"
        )
    ),
}
_FRP_INTEGER_SPECIFIC = frozenset(
    _names(
        "C_minus_P_final_q16 C_minus_P_min_q16 actual_direct_events "
        "global_phase_coherence_final_q30 neutral_insertions "
        "neutral_routed_events neutralized_conflicts "
        "pending_route_count_final pending_route_peak "
        "prevented_direct_events queue_overflow_events "
        "requested_direct_events reserved_state_events"
    )
)
_FRP_NUMBER_SPECIFIC = frozenset(
    _names("C_minus_P_final C_minus_P_min global_phase_coherence_final")
)
_FRP_BOOLEAN_SPECIFIC = frozenset(
    _names("fixed_point_thermal_sum_exact fixed_point_topology_sum_exact")
)
_SCENARIO_FIELDS = frozenset(
    _names(
        "scenario_id scenario_vector scenario_vector_sha256 cost_profile "
        "scenario_cost_profile_sha256 architectures comparison_matrix "
        "ranking integrity"
    )
)
_SCENARIO_COST_FIELDS = frozenset(_names("profile_name cost_unit costs"))
_SCENARIO_ARCHITECTURE_FIELDS = frozenset(
    _names(
        "architecture_id architecture_name architecture_result_sha256 "
        "workload_sha256 raw_event_trace_sha256 comparison_metrics "
        "normalized_cost thermal_proxy integrity"
    )
)
_NORMALIZED_COST_FIELDS = frozenset(
    _names(
        "profile_name cost_unit cost_profile_sha256 event_totals "
        "cost_contribution_totals peak_cycle_normalized_energy "
        "total_normalized_energy normalized_energy_per_completed_command "
        "cycle_normalized_energy_sha256"
    )
)
_THERMAL_RESULT_FIELDS = frozenset(
    _names(
        "profile_name temperature_unit thermal_profile_sha256 "
        "peak_temperature_proxy final_temperature_proxy "
        "temperature_proxy_trace_sha256"
    )
)
_ARCHITECTURE_INTEGRITY_FIELDS = frozenset(
    _names(
        "event_trace_closure cost_cycle_count_closure "
        "thermal_cycle_count_closure finite_numeric_values"
    )
)
_MATRIX_FIELDS = frozenset(
    _names(
        "architecture_id semantic_commands_issued "
        "semantic_commands_completed semantic_completion_ratio "
        "semantic_output_match completion_ticks mean_latency_ticks "
        "p95_latency_ticks maximum_latency_ticks "
        "throughput_commands_per_tick logical_state_changes "
        "encoded_bit_toggles processor_cycles active_clocked_cycles "
        "active_clock_fraction peak_cycle_normalized_energy "
        "total_normalized_energy normalized_energy_per_completed_command "
        "peak_temperature_proxy final_temperature_proxy"
    )
)
_SCENARIO_INTEGRITY_FIELDS = frozenset(
    _names(
        "architecture_order_match same_architecture_result_digests "
        "same_raw_event_trace_digests same_workload_digest "
        "same_cost_profile_digest same_thermal_profile_digest "
        "event_trace_closure cost_cycle_count_closure "
        "thermal_cycle_count_closure finite_numeric_values "
        "semantic_completion_ratio_one semantic_output_match_one"
    )
)
_RANKING_FIELDS = frozenset(
    _names("basis architecture_order ties_present rows")
)
_RANKING_ROW_FIELDS = frozenset(
    _names(
        "rank architecture_id total_normalized_energy "
        "normalized_energy_per_completed_command peak_temperature_proxy "
        "final_temperature_proxy"
    )
)
_RANKING_STABILITY_FIELDS = frozenset(
    _names(
        "ranking_basis scenario_rankings ranking_stable ranking_sensitive "
        "pairwise_stability"
    )
)
_PAIRWISE_FIELDS = frozenset(
    _names(
        "left_architecture_id right_architecture_id interpretation_basis "
        "scenario_relations classification"
    )
)
_PAIRWISE_CLASSIFICATIONS = frozenset(
    {
        "stable_lower_cost",
        "stable_higher_cost",
        "crosses_within_sensitivity_range",
    }
)
_TOP_INTEGRITY_FIELDS = frozenset(
    _names(
        "profile_validation_pass baseline_package_contract_pass "
        "current_execution_baseline_binding_pass architecture_order_match "
        "same_workload_digest architecture_result_digests_match_baseline "
        "scenario_order_match scenario_count_three "
        "all_scenario_integrity_pass "
        "same_architecture_result_digests_all_scenarios "
        "same_raw_event_trace_digests_all_scenarios "
        "same_thermal_profile_digest_all_scenarios "
        "scenario_vectors_exact scenario_cost_profiles_unique "
        "ranking_analysis_complete pairwise_analysis_complete "
        "finite_numeric_values winner_assertions_absent"
    )
)
_QUALIFICATION_FIELDS = frozenset(
    _names(
        "integrity_status_pass all_architectures_completed_workload "
        "semantic_completion_ratio_one_all semantic_output_match_one_all "
        "same_raw_traces_used_for_all_scenarios "
        "same_architecture_results_used_for_all_scenarios "
        "scenario_vectors_global_and_exact no_winner_assertions "
        "frp_actual_direct_events_zero frp_reserved_state_events_zero "
        "frp_queue_overflow_events_zero "
        "frp_pending_route_count_final_zero "
        "frp_requested_direct_events_equal_prevented "
        "frp_neutral_insertions_equal_neutral_routed"
    )
)

_EXPECTED_EVENT_FIELDS = dict(zip(_COST_CLASSES, _EVENT_FIELDS, strict=True))
_EXPECTED_BOUNDS = {
    "encoded_bit_toggle": (0.0078125, 0.03125, 0.125),
    "clocked_state_bit": (0.015625, 0.0625, 0.25),
    "register_write_bit": (0.03125, 0.125, 0.5),
    "comparison_event": (0.125, 0.5, 2.0),
    "control_event": (0.25, 1.0, 8.0),
    "queue_read": (1.0, 5.0, 30.0),
    "queue_write": (1.5, 7.5, 40.0),
    "lut_read_32": (20.0, 50.0, 100.0),
    "fixed_point_multiply_32x32": (20.0, 30.0, 40.0),
    "fixed_point_accumulate_64": (1.5, 2.0, 4.0),
    "fixed_point_add_32": (0.5, 1.0, 2.0),
    "fixed_point_compare_32": (0.5, 1.0, 2.0),
}
_EXPECTED_BASIS_TYPES = {
    cost_class: "implementation_assumption" for cost_class in _COST_CLASSES
}
_EXPECTED_BASIS_TYPES.update(
    {
        "lut_read_32": "derived_from_literature_anchor",
        "fixed_point_multiply_32x32": "literature_anchor",
        "fixed_point_accumulate_64": "derived_from_literature_anchor",
        "fixed_point_add_32": "literature_anchor",
    }
)
_EXPECTED_UNCERTAINTY = {cost_class: "high" for cost_class in _COST_CLASSES}
_EXPECTED_UNCERTAINTY.update(
    {
        "fixed_point_multiply_32x32": "medium",
        "fixed_point_accumulate_64": "medium",
        "fixed_point_add_32": "low",
    }
)
_EXPECTED_REFERENCE_KEYS = {
    cost_class: _REFERENCE_ORDER[0] for cost_class in _COST_CLASSES
}
_EXPECTED_REFERENCE_KEYS.update(
    {
        "queue_read": _REFERENCE_ORDER[3],
        "queue_write": _REFERENCE_ORDER[3],
        "lut_read_32": _REFERENCE_ORDER[2],
        "fixed_point_multiply_32x32": _REFERENCE_ORDER[1],
    }
)
_REFERENCE_VALUES = {
    _REFERENCE_ORDER[0]: (
        "32-bit integer addition",
        0.1,
        "pJ",
        "normalization_anchor",
    ),
    _REFERENCE_ORDER[1]: (
        "32-bit integer multiplication",
        3.0,
        "pJ",
        "direct_arithmetic_anchor",
    ),
    _REFERENCE_ORDER[2]: (
        "64-bit access to 8 KB local cache",
        10.0,
        "pJ",
        "local_memory_hierarchy_anchor",
    ),
    _REFERENCE_ORDER[3]: (
        "local memory hierarchy energy context",
        None,
        None,
        "qualitative_local_storage_cost_hierarchy_reference",
    ),
}


class HardwareSensitivityValidationError(ValueError):
    """Raised when a validator input violates routing invariants."""


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _number(value: object) -> bool:
    if not (_integer(value) or isinstance(value, (Decimal, float))):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _nonnegative(value: object) -> bool:
    return _number(value) and value >= 0


def _text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and "\x00" not in value
    )


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _object(value: object) -> Mapping[str, JsonValue] | None:
    return value if isinstance(value, Mapping) else None


def _rows(
    value: object,
) -> tuple[Mapping[str, JsonValue], ...] | None:
    if isinstance(value, tuple) and all(
        isinstance(row, Mapping) for row in value
    ):
        return value
    return None


def _field_set(value: object, fields: frozenset[str]) -> bool:
    return isinstance(value, Mapping) and frozenset(value) == fields


def _true_map(value: object, fields: frozenset[str]) -> bool:
    return _field_set(value, fields) and all(
        value[field] is True for field in fields
    )


def _json_value(value: JsonValue) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def _canonical_digest(value: JsonValue) -> str | None:
    try:
        encoded = json.dumps(
            _json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _without(
    root: Mapping[str, JsonValue],
    field: str,
) -> Mapping[str, JsonValue]:
    return {key: value for key, value in root.items() if key != field}


def _close(left: object, right: object) -> bool:
    if not _number(left) or not _number(right):
        return False
    return math.isclose(
        float(left),
        float(right),
        rel_tol=0.0,
        abs_tol=_FLOAT_TOLERANCE,
    )


def _all_finite(value: object) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, Mapping):
        return all(_all_finite(item) for item in value.values())
    if isinstance(value, tuple):
        return all(_all_finite(item) for item in value)
    return _number(value)


def _spec(
    code: str,
    category: ValidationCategory,
    valid: bool,
    path: str,
    rule: str,
) -> ValidationCheckSpec:
    label = code.replace("_", " ")
    result = "matches" if valid else "does not match"
    return ValidationCheckSpec(
        check_code=code,
        category=category,
        outcome=CheckOutcome.PASS if valid else CheckOutcome.FAIL,
        message=f"The {label} {result} the published upstream contract.",
        source_locations=(SourceLocation(json_path=path),),
        upstream_rule_reference=rule,
    )


def _normalization_valid(value: object) -> bool:
    return (
        _field_set(value, _NORMALIZATION_FIELDS)
        and value.get("primitive") == "32-bit integer addition"
        and _close(value.get("normalized_weight"), 1.0)
        and _close(value.get("reference_energy_value"), 0.1)
        and value.get("reference_energy_unit") == "pJ"
        and value.get("reference_technology_node_nm") == 45
        and value.get("reference_voltage_v") is None
        and value.get("reference_key") == _REFERENCE_ORDER[0]
    )


def _reference_basis_valid(value: object) -> bool:
    rows = _rows(value)
    if rows is None or len(rows) != len(_REFERENCE_ORDER):
        return False
    for row, reference_key in zip(rows, _REFERENCE_ORDER, strict=True):
        expected = _REFERENCE_VALUES[reference_key]
        if not (
            frozenset(row) == _REFERENCE_FIELDS
            and row.get("reference_key") == reference_key
            and row.get("author") == "Mark Horowitz"
            and _text(row.get("title"))
            and _text(row.get("venue"))
            and row.get("year") == 2014
            and row.get("pages") == "10-14"
            and row.get("doi") == "10.1109/ISSCC.2014.6757323"
            and row.get("primitive") == expected[0]
            and (
                row.get("reference_energy_value") is None
                if expected[1] is None
                else _close(row.get("reference_energy_value"), expected[1])
            )
            and row.get("reference_energy_unit") == expected[2]
            and row.get("technology_node_nm") == 45
            and row.get("approximate") is True
            and row.get("role") == expected[3]
        ):
            return False
    return True


def _coefficients_valid(value: object) -> bool:
    if not isinstance(value, Mapping) or tuple(value) != _COST_CLASSES:
        return False
    allowed_basis = frozenset(
        {
            "literature_anchor",
            "derived_from_literature_anchor",
            "implementation_assumption",
            "eda_measurement",
            "silicon_measurement",
        }
    )
    for cost_class in _COST_CLASSES:
        row = _object(value.get(cost_class))
        if row is None or frozenset(row) != _COEFFICIENT_FIELDS:
            return False
        bounds = _EXPECTED_BOUNDS[cost_class]
        source_value = row.get("source_value")
        voltage = row.get("voltage_v")
        if not (
            row.get("event_field") == _EXPECTED_EVENT_FIELDS[cost_class]
            and row.get("cost_class") == cost_class
            and _close(row.get("lower_bound"), bounds[0])
            and _close(row.get("nominal_weight"), bounds[1])
            and _close(row.get("upper_bound"), bounds[2])
            and row.get("basis_type") in allowed_basis
            and row.get("basis_type") == _EXPECTED_BASIS_TYPES[cost_class]
            and row.get("reference_key") == _EXPECTED_REFERENCE_KEYS[cost_class]
            and _text(row.get("reference"))
            and (source_value is None or _number(source_value))
            and _text(row.get("source_unit"))
            and row.get("technology_node_nm") == 45
            and (voltage is None or (_number(voltage) and voltage > 0))
            and _text(row.get("implementation_assumption"))
            and _text(row.get("derivation_rule"))
            and row.get("uncertainty_class")
            == _EXPECTED_UNCERTAINTY[cost_class]
        ):
            return False
    return True


def _expected_scenario_vector(scenario_id: str) -> dict[str, float]:
    index = _SCENARIO_ORDER.index(scenario_id)
    return {
        cost_class: _EXPECTED_BOUNDS[cost_class][index]
        for cost_class in _COST_CLASSES
    }


def _vector_valid(
    value: object,
    scenario_id: str,
    *,
    ordered: bool = False,
) -> bool:
    if not isinstance(value, Mapping) or frozenset(value) != frozenset(
        _COST_CLASSES
    ):
        return False
    if ordered and tuple(value) != _COST_CLASSES:
        return False
    expected = _expected_scenario_vector(scenario_id)
    return all(
        _close(value.get(cost_class), expected[cost_class])
        for cost_class in _COST_CLASSES
    )


def _scenario_vectors_valid(value: object) -> bool:
    if not isinstance(value, Mapping) or tuple(value) != _SCENARIO_ORDER:
        return False
    return all(
        _vector_valid(value.get(scenario_id), scenario_id, ordered=True)
        for scenario_id in _SCENARIO_ORDER
    )


def _evaluation_contract_valid(value: object) -> bool:
    return (
        _field_set(value, _EVALUATION_FIELDS)
        and value.get("execute_architectures_once") is True
        and value.get("preserve_raw_event_traces") is True
        and value.get("apply_same_scenario_vector_to_all_architectures") is True
        and value.get("scenario_result_order") == _SCENARIO_ORDER
        and value.get("thermal_profile") == "common_rc_thermal_proxy_v1"
        and value.get("winner_assertions") == ()
    )


def _validation_contract_valid(value: object) -> bool:
    if not _field_set(value, _VALIDATION_FIELDS):
        return False
    required_true = _VALIDATION_FIELDS - frozenset(
        {
            "required_cost_class_count",
            "require_semantic_completion_ratio",
            "require_semantic_output_match",
            "require_frp_actual_direct_events",
            "require_frp_reserved_state_events",
            "require_frp_queue_overflow_events",
            "require_frp_pending_route_count_final",
            "winner_assertions",
        }
    )
    return (
        value.get("required_cost_class_count") == len(_COST_CLASSES)
        and all(value.get(field) is True for field in required_true)
        and _close(value.get("require_semantic_completion_ratio"), 1.0)
        and _close(value.get("require_semantic_output_match"), 1.0)
        and value.get("require_frp_actual_direct_events") == 0
        and value.get("require_frp_reserved_state_events") == 0
        and value.get("require_frp_queue_overflow_events") == 0
        and value.get("require_frp_pending_route_count_final") == 0
        and value.get("winner_assertions") == ()
    )


def _digest_contract_valid(value: object) -> bool:
    return (
        _field_set(value, _DIGEST_CONTRACT_FIELDS)
        and value.get("algorithm") == "sha256"
        and value.get("canonicalization")
        == "json.dumps(sort_keys=True,separators=(',',':'),"
        "ensure_ascii=False,allow_nan=False)"
        and value.get("excluded_field") == "cost_profile_sha256"
    )


def _profile_specs(
    root: Mapping[str, JsonValue],
) -> tuple[ValidationCheckSpec, ...]:
    rule = "validate_hardware_sensitivity_profile.py"
    results = (
        (
            "hardware_sensitivity_profile_identity",
            ValidationCategory.IDENTITY,
            root.get("schema") == _PROFILE_SCHEMA
            and root.get("suite_name") == _SUITE
            and root.get("profile_name") == _PROFILE_NAME
            and root.get("profile_role") == _PROFILE_ROLE
            and root.get("profile_status") == _PROFILE_STATUS
            and root.get("baseline_profile") == _BASELINE_PROFILE
            and root.get("baseline_result") == _BASELINE_RESULT
            and root.get("provenance_map") == _PROVENANCE_MAP,
            "$",
        ),
        (
            "hardware_sensitivity_profile_fields",
            ValidationCategory.STRUCTURE,
            frozenset(root) == _PROFILE_ROOT_FIELDS,
            "$",
        ),
        (
            "hardware_sensitivity_normalization_reference",
            ValidationCategory.ALLOWED_VALUE,
            _normalization_valid(root.get("normalization_reference")),
            "$.normalization_reference",
        ),
        (
            "hardware_sensitivity_reference_basis",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _reference_basis_valid(root.get("reference_basis")),
            "$.reference_basis",
        ),
        (
            "hardware_sensitivity_profile_orders",
            ValidationCategory.ORDERING,
            root.get("scenario_order") == _SCENARIO_ORDER
            and root.get("coefficient_order") == _COST_CLASSES,
            "$.scenario_order",
        ),
        (
            "hardware_sensitivity_coefficients",
            ValidationCategory.ALLOWED_VALUE,
            _coefficients_valid(root.get("coefficients")),
            "$.coefficients",
        ),
        (
            "hardware_sensitivity_scenario_vectors",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _scenario_vectors_valid(root.get("scenario_vectors")),
            "$.scenario_vectors",
        ),
        (
            "hardware_sensitivity_evaluation_contract",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _evaluation_contract_valid(root.get("evaluation_contract")),
            "$.evaluation_contract",
        ),
        (
            "hardware_sensitivity_validation_contract",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _validation_contract_valid(root.get("validation_contract")),
            "$.validation_contract",
        ),
        (
            "hardware_sensitivity_digest_contract",
            ValidationCategory.DIGEST,
            _digest_contract_valid(root.get("digest_contract")),
            "$.digest_contract",
        ),
        (
            "hardware_sensitivity_profile_digest",
            ValidationCategory.DIGEST,
            _digest(root.get("cost_profile_sha256"))
            and _canonical_digest(_without(root, "cost_profile_sha256"))
            == root.get("cost_profile_sha256"),
            "$.cost_profile_sha256",
        ),
    )
    return tuple(
        _spec(code, category, valid, path, rule)
        for code, category, valid, path in results
    )


def _workload_valid(value: object) -> bool:
    if not _field_set(value, _WORKLOAD_FIELDS):
        return False
    return (
        _integer(value["num_cells"])
        and value["num_cells"] > 0
        and _integer(value["command_count"])
        and value["command_count"] > 0
        and _integer(value["seed"])
        and 0 <= value["seed"] <= 0xFFFFFFFFFFFFFFFF
        and value["issue_policy"] == "transaction_serial"
        and _integer(value["max_completion_cycles_per_command"])
        and value["max_completion_cycles_per_command"] > 0
        and _integer(value["final_cooldown_cycles"])
        and value["final_cooldown_cycles"] >= 0
    )


def _embedded_profile_valid(root: Mapping[str, JsonValue]) -> bool:
    profile = _object(root.get("hardware_sensitivity_profile"))
    if profile is None or frozenset(profile) != _EMBEDDED_PROFILE_FIELDS:
        return False
    return (
        profile.get("schema") == _PROFILE_SCHEMA
        and profile.get("profile_name") == _PROFILE_NAME
        and profile.get("profile_role") == _PROFILE_ROLE
        and profile.get("profile_status") == _PROFILE_STATUS
        and profile.get("cost_profile_sha256")
        == root.get("hardware_sensitivity_profile_sha256")
        and _digest(profile.get("cost_profile_sha256"))
        and profile.get("baseline_profile") == _BASELINE_PROFILE
        and profile.get("baseline_result") == _BASELINE_RESULT
        and profile.get("provenance_map") == _PROVENANCE_MAP
        and _normalization_valid(profile.get("normalization_reference"))
        and profile.get("scenario_order") == _SCENARIO_ORDER
        and profile.get("coefficient_order") == _COST_CLASSES
    )


def _profile_validation_valid(root: Mapping[str, JsonValue]) -> bool:
    validation = _object(root.get("profile_validation"))
    if validation is None or frozenset(validation) != _PROFILE_VALIDATION_FIELDS:
        return False
    return (
        validation.get("status") == "PASS"
        and validation.get("schema") == _PROFILE_SCHEMA
        and validation.get("profile_name") == _PROFILE_NAME
        and validation.get("coefficient_count") == len(_COST_CLASSES)
        and validation.get("scenario_order") == _SCENARIO_ORDER
        and validation.get("reference_count") == len(_REFERENCE_ORDER)
        and validation.get("baseline_result") == _BASELINE_RESULT
        and validation.get("provenance_map") == _PROVENANCE_MAP
        and validation.get("cost_profile_sha256")
        == root.get("hardware_sensitivity_profile_sha256")
    )


def _baseline_binding_valid(root: Mapping[str, JsonValue]) -> bool:
    binding = _object(root.get("baseline_binding"))
    if binding is None or frozenset(binding) != _BASELINE_BINDING_FIELDS:
        return False
    digests = _object(binding.get("architecture_result_sha256"))
    current = _object(binding.get("current_execution"))
    current_checks = (
        _object(current.get("checks")) if current is not None else None
    )
    return (
        binding.get("status") == "PASS"
        and binding.get("baseline_result") == _BASELINE_RESULT
        and binding.get("baseline_schema")
        == "frp.benchmark.architecture_comparison.v1"
        and binding.get("baseline_workload_sha256") == root.get("workload_sha256")
        and binding.get("baseline_cost_profile") == _BASELINE_PROFILE
        and _digest(binding.get("baseline_comparison_package_sha256"))
        and digests is not None
        and frozenset(digests) == frozenset(_ARCHITECTURE_ORDER)
        and all(_digest(digests.get(key)) for key in _ARCHITECTURE_ORDER)
        and _true_map(binding.get("checks"), _BASELINE_CHECK_FIELDS)
        and current is not None
        and frozenset(current) == frozenset({"status", "checks"})
        and current.get("status") == "PASS"
        and current_checks is not None
        and _true_map(current_checks, _CURRENT_EXECUTION_CHECK_FIELDS)
    )


def _thermal_payload(value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
    return {
        "schema": "frp.benchmark.thermal_proxy_profile.v1",
        "suite_name": _SUITE,
        "profile_name": value.get("profile_name"),
        "temperature_unit": value.get("temperature_unit"),
        "ambient_temperature_proxy": value.get("ambient_temperature_proxy"),
        "thermal_decay": value.get("thermal_decay"),
        "thermal_gain": value.get("thermal_gain"),
        "update_equation": _THERMAL_EQUATION,
    }


def _thermal_profile_valid(root: Mapping[str, JsonValue]) -> bool:
    thermal = _object(root.get("thermal_profile"))
    if thermal is None or frozenset(thermal) != _EMBEDDED_THERMAL_FIELDS:
        return False
    return (
        thermal.get("profile_name") == "common_rc_thermal_proxy_v1"
        and thermal.get("temperature_unit") == "normalized_temperature_proxy"
        and _nonnegative(thermal.get("ambient_temperature_proxy"))
        and _number(thermal.get("thermal_decay"))
        and 0 <= thermal.get("thermal_decay") < 1
        and _nonnegative(thermal.get("thermal_gain"))
        and _digest(root.get("thermal_profile_sha256"))
        and _canonical_digest(_thermal_payload(thermal))
        == root.get("thermal_profile_sha256")
    )


def _specific_valid(architecture_id: str, value: object) -> bool:
    expected = _SPECIFIC_FIELDS.get(architecture_id)
    if expected is None or not _field_set(value, expected):
        return False
    if architecture_id == "binary_synchronous_reference":
        return _integer(value["direct_binary_switches"]) and (
            value["direct_binary_switches"] >= 0
        )
    if architecture_id == "binary_clock_gated_reference":
        return (
            _number(value["clock_gate_active_fraction"])
            and 0 <= value["clock_gate_active_fraction"] <= 1
            and _integer(value["direct_binary_switches"])
            and value["direct_binary_switches"] >= 0
            and _integer(value["gated_cycles"])
            and value["gated_cycles"] >= 0
        )
    if architecture_id == "direct_ternary_reference":
        return all(
            _integer(value[field]) and value[field] >= 0 for field in expected
        )
    return (
        all(_integer(value[field]) for field in _FRP_INTEGER_SPECIFIC)
        and all(
            value[field] >= 0
            for field in _FRP_INTEGER_SPECIFIC
            if field not in {"C_minus_P_final_q16", "C_minus_P_min_q16"}
        )
        and all(_number(value[field]) for field in _FRP_NUMBER_SPECIFIC)
        and all(isinstance(value[field], bool) for field in _FRP_BOOLEAN_SPECIFIC)
    )


def _metrics_valid(value: object) -> bool:
    if not _field_set(value, _METRIC_FIELDS):
        return False
    return (
        all(_nonnegative(value[field]) for field in _METRIC_FIELDS)
        and 0 <= value["semantic_completion_ratio"] <= 1
        and 0 <= value["semantic_output_match"] <= 1
        and 0 <= value["active_clock_fraction"] <= 1
    )


def _raw_valid(value: object) -> bool:
    return _field_set(value, _RAW_FIELDS) and all(
        _integer(value[field]) and value[field] >= 0 for field in _RAW_FIELDS
    )


def _metrics_relations_valid(raw: object, metrics: object) -> bool:
    if not isinstance(raw, Mapping) or not isinstance(metrics, Mapping):
        return False
    issued = raw.get("semantic_commands_issued")
    completed = raw.get("semantic_commands_completed")
    cycles = raw.get("processor_cycles")
    active = raw.get("active_clocked_cycles")
    completion_ticks = metrics.get("completion_ticks")
    if not all(_integer(value) for value in (issued, completed, cycles, active)):
        return False
    if not _nonnegative(completion_ticks):
        return False
    completion = completed / issued if issued else 0
    active_fraction = active / cycles if cycles else 0
    throughput = completed / float(completion_ticks) if completion_ticks else 0
    return (
        metrics.get("logical_state_changes") == raw.get("logical_state_changes")
        and metrics.get("encoded_bit_toggles") == raw.get("encoded_bit_toggles")
        and metrics.get("processor_cycles") == cycles
        and metrics.get("active_clocked_cycles") == active
        and _close(metrics.get("semantic_completion_ratio"), completion)
        and _close(metrics.get("active_clock_fraction"), active_fraction)
        and _close(metrics.get("throughput_commands_per_tick"), throughput)
    )


def _raw_ledger_valid(
    root: Mapping[str, JsonValue],
) -> tuple[bool, bool, bool]:
    rows = _rows(root.get("raw_trace_ledger"))
    binding = _object(root.get("baseline_binding"))
    binding_digests = (
        _object(binding.get("architecture_result_sha256"))
        if binding is not None
        else None
    )
    if rows is None or len(rows) != len(_ARCHITECTURE_ORDER):
        return False, False, False
    shapes = True
    values = True
    relations = binding_digests is not None
    for row, architecture_id in zip(rows, _ARCHITECTURE_ORDER, strict=True):
        raw = _object(row.get("raw_event_totals"))
        metrics = _object(row.get("comparison_metrics"))
        shapes = shapes and (
            frozenset(row) == _RAW_LEDGER_FIELDS
            and row.get("architecture_id") == architecture_id
            and _text(row.get("architecture_name"))
            and _digest(row.get("architecture_result_sha256"))
            and _digest(row.get("workload_sha256"))
            and _digest(row.get("raw_event_totals_sha256"))
            and _digest(row.get("raw_event_trace_sha256"))
        )
        values = values and (
            _integer(row.get("processor_cycles"))
            and row.get("processor_cycles", -1) >= 0
            and _raw_valid(raw)
            and _metrics_valid(metrics)
            and _specific_valid(
                architecture_id,
                row.get("architecture_specific_metrics"),
            )
        )
        relations = relations and (
            raw is not None
            and metrics is not None
            and row.get("processor_cycles") == raw.get("processor_cycles")
            and row.get("workload_sha256") == root.get("workload_sha256")
            and row.get("architecture_result_sha256")
            == binding_digests.get(architecture_id)
            and _canonical_digest(raw) == row.get("raw_event_totals_sha256")
            and _metrics_relations_valid(raw, metrics)
        )
    return shapes, values, relations


def _raw_trace_set_valid(root: Mapping[str, JsonValue]) -> bool:
    rows = _rows(root.get("raw_trace_ledger"))
    if rows is None:
        return False
    payload = tuple(
        {
            "architecture_id": row.get("architecture_id"),
            "architecture_result_sha256": row.get("architecture_result_sha256"),
            "raw_event_totals_sha256": row.get("raw_event_totals_sha256"),
            "raw_event_trace_sha256": row.get("raw_event_trace_sha256"),
        }
        for row in rows
    )
    return (
        _digest(root.get("raw_trace_set_sha256"))
        and _canonical_digest(payload) == root.get("raw_trace_set_sha256")
    )


def _cost_profile_payload(
    profile_name: JsonValue,
    costs: JsonValue,
) -> Mapping[str, JsonValue]:
    return {
        "schema": "frp.benchmark.normalized_cost_profile.v1",
        "suite_name": _SUITE,
        "profile_name": profile_name,
        "cost_unit": _SCENARIO_COST_UNIT,
        "costs": costs,
    }


def _normalized_cost_valid(
    value: object,
    raw: object,
    scenario_id: str,
    scenario_digest: object,
) -> bool:
    if not _field_set(value, _NORMALIZED_COST_FIELDS) or not isinstance(
        raw, Mapping
    ):
        return False
    events = _object(value.get("event_totals"))
    contributions = _object(value.get("cost_contribution_totals"))
    vector = _expected_scenario_vector(scenario_id)
    if events is None or contributions is None:
        return False
    if not (
        value.get("profile_name") == f"{_PROFILE_NAME}::{scenario_id}"
        and value.get("cost_unit") == _SCENARIO_COST_UNIT
        and value.get("cost_profile_sha256") == scenario_digest
        and _digest(value.get("cycle_normalized_energy_sha256"))
        and frozenset(events) == frozenset(_EVENT_FIELDS)
        and frozenset(contributions) == frozenset(_COST_CLASSES)
    ):
        return False
    if not all(
        _integer(events.get(field))
        and events.get(field) >= 0
        and events.get(field) == raw.get(field)
        for field in _EVENT_FIELDS
    ):
        return False
    if not all(
        _nonnegative(contributions.get(cost_class))
        and _close(
            contributions.get(cost_class),
            events[event_field] * Decimal(str(vector[cost_class])),
        )
        for event_field, cost_class in _EVENT_TO_COST.items()
    ):
        return False
    total = sum(
        (contributions[cost_class] for cost_class in _COST_CLASSES),
        Decimal(0),
    )
    completed = raw.get("semantic_commands_completed")
    expected_per_command = total / completed if completed else Decimal(0)
    return (
        _nonnegative(value.get("peak_cycle_normalized_energy"))
        and _nonnegative(value.get("total_normalized_energy"))
        and _nonnegative(value.get("normalized_energy_per_completed_command"))
        and _close(value.get("total_normalized_energy"), total)
        and _close(
            value.get("normalized_energy_per_completed_command"),
            expected_per_command,
        )
    )


def _thermal_result_valid(
    value: object,
    root: Mapping[str, JsonValue],
) -> bool:
    thermal = _object(root.get("thermal_profile"))
    return (
        _field_set(value, _THERMAL_RESULT_FIELDS)
        and thermal is not None
        and value.get("profile_name") == thermal.get("profile_name")
        and value.get("temperature_unit") == thermal.get("temperature_unit")
        and value.get("thermal_profile_sha256")
        == root.get("thermal_profile_sha256")
        and _nonnegative(value.get("peak_temperature_proxy"))
        and _nonnegative(value.get("final_temperature_proxy"))
        and value.get("final_temperature_proxy")
        <= value.get("peak_temperature_proxy")
        and _digest(value.get("temperature_proxy_trace_sha256"))
    )


def _matrix_projection(
    architecture: Mapping[str, JsonValue],
    raw: Mapping[str, JsonValue],
) -> dict[str, JsonValue] | None:
    metrics = _object(architecture.get("comparison_metrics"))
    cost = _object(architecture.get("normalized_cost"))
    thermal = _object(architecture.get("thermal_proxy"))
    if metrics is None or cost is None or thermal is None:
        return None
    try:
        return {
            "architecture_id": architecture["architecture_id"],
            "semantic_commands_issued": raw["semantic_commands_issued"],
            "semantic_commands_completed": raw["semantic_commands_completed"],
            "semantic_completion_ratio": metrics["semantic_completion_ratio"],
            "semantic_output_match": metrics["semantic_output_match"],
            "completion_ticks": metrics["completion_ticks"],
            "mean_latency_ticks": metrics["mean_latency_ticks"],
            "p95_latency_ticks": metrics["p95_latency_ticks"],
            "maximum_latency_ticks": metrics["maximum_latency_ticks"],
            "throughput_commands_per_tick": metrics[
                "throughput_commands_per_tick"
            ],
            "logical_state_changes": metrics["logical_state_changes"],
            "encoded_bit_toggles": metrics["encoded_bit_toggles"],
            "processor_cycles": metrics["processor_cycles"],
            "active_clocked_cycles": metrics["active_clocked_cycles"],
            "active_clock_fraction": metrics["active_clock_fraction"],
            "peak_cycle_normalized_energy": cost[
                "peak_cycle_normalized_energy"
            ],
            "total_normalized_energy": cost["total_normalized_energy"],
            "normalized_energy_per_completed_command": cost[
                "normalized_energy_per_completed_command"
            ],
            "peak_temperature_proxy": thermal["peak_temperature_proxy"],
            "final_temperature_proxy": thermal["final_temperature_proxy"],
        }
    except KeyError:
        return None


def _ranking_expected(
    matrix: tuple[Mapping[str, JsonValue], ...],
) -> dict[str, object] | None:
    if len(matrix) != len(_ARCHITECTURE_ORDER):
        return None
    by_id = {str(row.get("architecture_id")): row for row in matrix}
    ranking_values = (
        "total_normalized_energy",
        "normalized_energy_per_completed_command",
        "peak_temperature_proxy",
        "final_temperature_proxy",
    )
    if tuple(by_id) != _ARCHITECTURE_ORDER or not all(
        all(_number(row.get(field)) for field in ranking_values)
        for row in matrix
    ):
        return None
    ordered = tuple(
        sorted(
            _ARCHITECTURE_ORDER,
            key=lambda architecture_id: (
                float(by_id[architecture_id]["total_normalized_energy"]),
                _ARCHITECTURE_ORDER.index(architecture_id),
            ),
        )
    )
    energies = tuple(
        float(by_id[architecture_id]["total_normalized_energy"])
        for architecture_id in ordered
    )
    ties = any(
        math.isclose(
            energies[index],
            energies[index + 1],
            rel_tol=0.0,
            abs_tol=_FLOAT_TOLERANCE,
        )
        for index in range(len(energies) - 1)
    )
    rows = tuple(
        {
            "rank": index + 1,
            "architecture_id": architecture_id,
            "total_normalized_energy": by_id[architecture_id][
                "total_normalized_energy"
            ],
            "normalized_energy_per_completed_command": by_id[architecture_id][
                "normalized_energy_per_completed_command"
            ],
            "peak_temperature_proxy": by_id[architecture_id][
                "peak_temperature_proxy"
            ],
            "final_temperature_proxy": by_id[architecture_id][
                "final_temperature_proxy"
            ],
        }
        for index, architecture_id in enumerate(ordered)
    )
    return {
        "basis": "ascending_total_normalized_energy",
        "architecture_order": ordered,
        "ties_present": ties,
        "rows": rows,
    }


def _scenario_valid(
    root: Mapping[str, JsonValue],
    scenario: Mapping[str, JsonValue],
    scenario_id: str,
    ledger_by_id: Mapping[str, Mapping[str, JsonValue]],
) -> tuple[bool, bool, bool]:
    if frozenset(scenario) != _SCENARIO_FIELDS:
        return False, False, False
    vector = _object(scenario.get("scenario_vector"))
    cost_profile = _object(scenario.get("cost_profile"))
    architectures = _rows(scenario.get("architectures"))
    matrix = _rows(scenario.get("comparison_matrix"))
    ranking = _object(scenario.get("ranking"))
    integrity = _object(scenario.get("integrity"))
    if (
        vector is None
        or cost_profile is None
        or architectures is None
        or matrix is None
        or ranking is None
        or integrity is None
    ):
        return False, False, False
    scenario_digest = scenario.get("scenario_cost_profile_sha256")
    vector_valid = _vector_valid(vector, scenario_id)
    profile_valid = (
        frozenset(cost_profile) == _SCENARIO_COST_FIELDS
        and cost_profile.get("profile_name") == f"{_PROFILE_NAME}::{scenario_id}"
        and cost_profile.get("cost_unit") == _SCENARIO_COST_UNIT
        and cost_profile.get("costs") == vector
        and _digest(scenario_digest)
        and _canonical_digest(
            _cost_profile_payload(cost_profile.get("profile_name"), vector)
        )
        == scenario_digest
    )
    shapes = (
        scenario.get("scenario_id") == scenario_id
        and vector_valid
        and _digest(scenario.get("scenario_vector_sha256"))
        and _canonical_digest(vector) == scenario.get("scenario_vector_sha256")
        and profile_valid
        and len(architectures) == len(_ARCHITECTURE_ORDER)
        and len(matrix) == len(_ARCHITECTURE_ORDER)
        and all(frozenset(row) == _MATRIX_FIELDS for row in matrix)
        and frozenset(ranking) == _RANKING_FIELDS
        and frozenset(integrity) == frozenset({"status", "checks"})
    )
    values = True
    relations = True
    projections: list[dict[str, JsonValue] | None] = []
    for architecture, architecture_id in zip(
        architectures, _ARCHITECTURE_ORDER, strict=True
    ):
        ledger = ledger_by_id.get(architecture_id)
        raw = _object(ledger.get("raw_event_totals")) if ledger is not None else None
        metrics = _object(architecture.get("comparison_metrics"))
        architecture_integrity = _object(architecture.get("integrity"))
        shapes = shapes and (
            frozenset(architecture) == _SCENARIO_ARCHITECTURE_FIELDS
            and architecture.get("architecture_id") == architecture_id
            and _text(architecture.get("architecture_name"))
            and _digest(architecture.get("architecture_result_sha256"))
            and _digest(architecture.get("workload_sha256"))
            and _digest(architecture.get("raw_event_trace_sha256"))
            and _field_set(
                architecture_integrity, _ARCHITECTURE_INTEGRITY_FIELDS
            )
        )
        values = values and (
            _metrics_valid(metrics)
            and architecture_integrity is not None
            and all(isinstance(item, bool) for item in architecture_integrity.values())
            and _normalized_cost_valid(
                architecture.get("normalized_cost"),
                raw,
                scenario_id,
                scenario_digest,
            )
            and _thermal_result_valid(architecture.get("thermal_proxy"), root)
        )
        relations = relations and (
            ledger is not None
            and raw is not None
            and metrics is not None
            and architecture.get("architecture_name")
            == ledger.get("architecture_name")
            and architecture.get("architecture_result_sha256")
            == ledger.get("architecture_result_sha256")
            and architecture.get("workload_sha256") == root.get("workload_sha256")
            and architecture.get("raw_event_trace_sha256")
            == ledger.get("raw_event_trace_sha256")
            and dict(metrics) == dict(ledger.get("comparison_metrics", {}))
        )
        projections.append(
            _matrix_projection(architecture, raw) if raw is not None else None
        )
    relations = relations and all(
        projection is not None and dict(row) == projection
        for row, projection in zip(matrix, projections, strict=True)
    )
    expected_ranking = _ranking_expected(matrix)
    ranking_rows = _rows(ranking.get("rows"))
    relations = relations and (
        expected_ranking is not None
        and ranking_rows is not None
        and all(frozenset(row) == _RANKING_ROW_FIELDS for row in ranking_rows)
        and dict(ranking) == expected_ranking
    )
    expected_checks = {
        "architecture_order_match": (
            tuple(row.get("architecture_id") for row in architectures)
            == _ARCHITECTURE_ORDER
            and tuple(row.get("architecture_id") for row in matrix)
            == _ARCHITECTURE_ORDER
        ),
        "same_architecture_result_digests": all(
            row.get("architecture_result_sha256")
            == ledger_by_id.get(str(row.get("architecture_id")), {}).get(
                "architecture_result_sha256"
            )
            for row in architectures
        ),
        "same_raw_event_trace_digests": all(
            row.get("raw_event_trace_sha256")
            == ledger_by_id.get(str(row.get("architecture_id")), {}).get(
                "raw_event_trace_sha256"
            )
            for row in architectures
        ),
        "same_workload_digest": all(
            row.get("workload_sha256") == root.get("workload_sha256")
            for row in architectures
        ),
        "same_cost_profile_digest": all(
            isinstance(row.get("normalized_cost"), Mapping)
            and row["normalized_cost"].get("cost_profile_sha256")
            == scenario_digest
            for row in architectures
        ),
        "same_thermal_profile_digest": all(
            isinstance(row.get("thermal_proxy"), Mapping)
            and row["thermal_proxy"].get("thermal_profile_sha256")
            == root.get("thermal_profile_sha256")
            for row in architectures
        ),
        "event_trace_closure": all(
            isinstance(row.get("integrity"), Mapping)
            and row["integrity"].get("event_trace_closure") is True
            for row in architectures
        ),
        "cost_cycle_count_closure": all(
            isinstance(row.get("integrity"), Mapping)
            and row["integrity"].get("cost_cycle_count_closure") is True
            for row in architectures
        ),
        "thermal_cycle_count_closure": all(
            isinstance(row.get("integrity"), Mapping)
            and row["integrity"].get("thermal_cycle_count_closure") is True
            for row in architectures
        ),
        "finite_numeric_values": _all_finite(
            {"architectures": architectures, "comparison_matrix": matrix}
        ),
        "semantic_completion_ratio_one": all(
            row.get("semantic_completion_ratio") == 1 for row in matrix
        ),
        "semantic_output_match_one": all(
            row.get("semantic_output_match") == 1 for row in matrix
        ),
    }
    checks = _object(integrity.get("checks"))
    relations = relations and (
        checks is not None
        and frozenset(checks) == _SCENARIO_INTEGRITY_FIELDS
        and dict(checks) == expected_checks
        and integrity.get("status")
        == ("PASS" if all(expected_checks.values()) else "FAIL")
    )
    return shapes, values, relations


def _scenarios_valid(
    root: Mapping[str, JsonValue],
) -> tuple[bool, bool, bool]:
    scenarios = _rows(root.get("scenarios"))
    ledger = _rows(root.get("raw_trace_ledger"))
    if scenarios is None or ledger is None or len(scenarios) != len(_SCENARIO_ORDER):
        return False, False, False
    ledger_by_id = {
        str(row.get("architecture_id")): row for row in ledger
    }
    shapes = True
    values = True
    relations = True
    for scenario, scenario_id in zip(scenarios, _SCENARIO_ORDER, strict=True):
        result = _scenario_valid(root, scenario, scenario_id, ledger_by_id)
        shapes = shapes and result[0]
        values = values and result[1]
        relations = relations and result[2]
    return shapes, values, relations


def _energy_relation(left: object, right: object) -> str | None:
    if not _number(left) or not _number(right):
        return None
    if _close(left, right):
        return "equal_cost"
    return "lower_cost" if left < right else "higher_cost"


def _expected_ranking_stability(
    root: Mapping[str, JsonValue],
) -> dict[str, object] | None:
    scenarios = _rows(root.get("scenarios"))
    if scenarios is None or len(scenarios) != len(_SCENARIO_ORDER):
        return None
    scenario_by_id = {str(row.get("scenario_id")): row for row in scenarios}
    if tuple(scenario_by_id) != _SCENARIO_ORDER:
        return None
    scenario_rankings: dict[str, tuple[JsonValue, ...]] = {}
    energies: dict[str, dict[str, JsonValue]] = {}
    for scenario_id in _SCENARIO_ORDER:
        scenario = scenario_by_id[scenario_id]
        ranking = _object(scenario.get("ranking"))
        matrix = _rows(scenario.get("comparison_matrix"))
        if ranking is None or matrix is None:
            return None
        order = ranking.get("architecture_order")
        if not isinstance(order, tuple):
            return None
        scenario_rankings[scenario_id] = order
        energies[scenario_id] = {
            str(row.get("architecture_id")): row.get("total_normalized_energy")
            for row in matrix
        }
    ranking_sequences = tuple(
        scenario_rankings[scenario_id] for scenario_id in _SCENARIO_ORDER
    )
    ranking_stable = len(set(ranking_sequences)) == 1
    pairwise: list[dict[str, object]] = []
    for left_id, right_id in combinations(_ARCHITECTURE_ORDER, 2):
        relations = {
            scenario_id: _energy_relation(
                energies[scenario_id].get(left_id),
                energies[scenario_id].get(right_id),
            )
            for scenario_id in _SCENARIO_ORDER
        }
        if any(value is None for value in relations.values()):
            return None
        values = tuple(relations.values())
        if all(value == "lower_cost" for value in values):
            classification = "stable_lower_cost"
        elif all(value == "higher_cost" for value in values):
            classification = "stable_higher_cost"
        else:
            classification = "crosses_within_sensitivity_range"
        pairwise.append(
            {
                "left_architecture_id": left_id,
                "right_architecture_id": right_id,
                "interpretation_basis": (
                    "left_architecture_total_normalized_energy_relative_to_right"
                ),
                "scenario_relations": relations,
                "classification": classification,
            }
        )
    return {
        "ranking_basis": "ascending_total_normalized_energy",
        "scenario_rankings": scenario_rankings,
        "ranking_stable": ranking_stable,
        "ranking_sensitive": not ranking_stable,
        "pairwise_stability": tuple(pairwise),
    }


def _ranking_stability_valid(root: Mapping[str, JsonValue]) -> bool:
    value = _object(root.get("ranking_stability"))
    expected = _expected_ranking_stability(root)
    if value is None or expected is None:
        return False
    pairwise = _rows(value.get("pairwise_stability"))
    if pairwise is None or len(pairwise) != 6:
        return False
    return (
        frozenset(value) == _RANKING_STABILITY_FIELDS
        and all(
            frozenset(row) == _PAIRWISE_FIELDS
            and row.get("classification") in _PAIRWISE_CLASSIFICATIONS
            and _field_set(
                row.get("scenario_relations"), frozenset(_SCENARIO_ORDER)
            )
            for row in pairwise
        )
        and dict(value) == expected
    )


def _expected_top_integrity(
    root: Mapping[str, JsonValue],
) -> dict[str, bool] | None:
    ledger = _rows(root.get("raw_trace_ledger"))
    scenarios = _rows(root.get("scenarios"))
    ranking = _object(root.get("ranking_stability"))
    binding = _object(root.get("baseline_binding"))
    qualification = _object(root.get("qualification"))
    if any(value is None for value in (ledger, scenarios, ranking, binding)):
        return None
    binding_digests = _object(binding.get("architecture_result_sha256"))
    current = _object(binding.get("current_execution"))
    if binding_digests is None or current is None:
        return None
    ledger_result_digests = {
        str(row.get("architecture_id")): row.get("architecture_result_sha256")
        for row in ledger
    }
    ledger_trace_digests = {
        str(row.get("architecture_id")): row.get("raw_event_trace_sha256")
        for row in ledger
    }
    scenario_result_maps = tuple(
        {
            str(row.get("architecture_id")): row.get("architecture_result_sha256")
            for row in (_rows(scenario.get("architectures")) or ())
        }
        for scenario in scenarios
    )
    scenario_trace_maps = tuple(
        {
            str(row.get("architecture_id")): row.get("raw_event_trace_sha256")
            for row in (_rows(scenario.get("architectures")) or ())
        }
        for scenario in scenarios
    )
    scenario_ids = tuple(row.get("scenario_id") for row in scenarios)
    scenario_digests = tuple(
        row.get("scenario_cost_profile_sha256") for row in scenarios
    )
    return {
        "profile_validation_pass": _profile_validation_valid(root),
        "baseline_package_contract_pass": (
            binding.get("status") == "PASS"
            and _true_map(binding.get("checks"), _BASELINE_CHECK_FIELDS)
        ),
        "current_execution_baseline_binding_pass": (
            current.get("status") == "PASS"
            and _true_map(
                current.get("checks"), _CURRENT_EXECUTION_CHECK_FIELDS
            )
        ),
        "architecture_order_match": (
            tuple(row.get("architecture_id") for row in ledger)
            == _ARCHITECTURE_ORDER
        ),
        "same_workload_digest": (
            all(
                row.get("workload_sha256") == root.get("workload_sha256")
                for row in ledger
            )
            and binding.get("baseline_workload_sha256")
            == root.get("workload_sha256")
        ),
        "architecture_result_digests_match_baseline": (
            ledger_result_digests == dict(binding_digests)
        ),
        "scenario_order_match": scenario_ids == _SCENARIO_ORDER,
        "scenario_count_three": len(scenarios) == 3,
        "all_scenario_integrity_pass": all(
            isinstance(row.get("integrity"), Mapping)
            and row["integrity"].get("status") == "PASS"
            and isinstance(row["integrity"].get("checks"), Mapping)
            and all(row["integrity"]["checks"].values())
            for row in scenarios
        ),
        "same_architecture_result_digests_all_scenarios": all(
            value == ledger_result_digests for value in scenario_result_maps
        ),
        "same_raw_event_trace_digests_all_scenarios": all(
            value == ledger_trace_digests for value in scenario_trace_maps
        ),
        "same_thermal_profile_digest_all_scenarios": all(
            all(
                isinstance(row.get("thermal_proxy"), Mapping)
                and row["thermal_proxy"].get("thermal_profile_sha256")
                == root.get("thermal_profile_sha256")
                for row in (_rows(scenario.get("architectures")) or ())
            )
            for scenario in scenarios
        ),
        "scenario_vectors_exact": all(
            _vector_valid(row.get("scenario_vector"), scenario_id)
            for row, scenario_id in zip(scenarios, _SCENARIO_ORDER, strict=True)
        ),
        "scenario_cost_profiles_unique": (
            len(scenario_digests) == 3 and len(set(scenario_digests)) == 3
        ),
        "ranking_analysis_complete": (
            isinstance(ranking.get("scenario_rankings"), Mapping)
            and frozenset(ranking["scenario_rankings"])
            == frozenset(_SCENARIO_ORDER)
        ),
        "pairwise_analysis_complete": (
            len(_rows(ranking.get("pairwise_stability")) or ()) == 6
            and all(
                row.get("classification") in _PAIRWISE_CLASSIFICATIONS
                for row in (_rows(ranking.get("pairwise_stability")) or ())
            )
        ),
        "finite_numeric_values": _all_finite(
            {
                "raw_trace_ledger": ledger,
                "scenarios": scenarios,
                "ranking_stability": ranking,
            }
        ),
        "winner_assertions_absent": (
            qualification is not None
            and qualification.get("winner_assertions") == ()
        ),
    }


def _integrity_valid(root: Mapping[str, JsonValue]) -> bool:
    integrity = _object(root.get("integrity"))
    expected = _expected_top_integrity(root)
    if integrity is None or expected is None:
        return False
    checks = _object(integrity.get("checks"))
    return (
        frozenset(integrity) == frozenset({"status", "checks"})
        and checks is not None
        and frozenset(checks) == _TOP_INTEGRITY_FIELDS
        and dict(checks) == expected
        and integrity.get("status")
        == ("PASS" if all(expected.values()) else "FAIL")
    )


def _expected_qualification(
    root: Mapping[str, JsonValue],
) -> dict[str, bool] | None:
    ledger = _rows(root.get("raw_trace_ledger"))
    scenarios = _rows(root.get("scenarios"))
    workload = _object(root.get("workload_profile"))
    integrity = _expected_top_integrity(root)
    qualification = _object(root.get("qualification"))
    if any(value is None for value in (ledger, scenarios, workload, integrity)):
        return None
    ledger_by_id = {str(row.get("architecture_id")): row for row in ledger}
    frp = ledger_by_id.get("frp_v1_7_0_quantized_shadow")
    specific = _object(frp.get("architecture_specific_metrics")) if frp else None
    if specific is None:
        return None
    return {
        "integrity_status_pass": all(integrity.values()),
        "all_architectures_completed_workload": all(
            isinstance(row.get("raw_event_totals"), Mapping)
            and row["raw_event_totals"].get("semantic_commands_issued")
            == workload.get("command_count")
            and row["raw_event_totals"].get("semantic_commands_completed")
            == workload.get("command_count")
            for row in ledger
        ),
        "semantic_completion_ratio_one_all": all(
            isinstance(row.get("comparison_metrics"), Mapping)
            and row["comparison_metrics"].get("semantic_completion_ratio") == 1
            for row in ledger
        ),
        "semantic_output_match_one_all": all(
            isinstance(row.get("comparison_metrics"), Mapping)
            and row["comparison_metrics"].get("semantic_output_match") == 1
            for row in ledger
        ),
        "same_raw_traces_used_for_all_scenarios": integrity[
            "same_raw_event_trace_digests_all_scenarios"
        ],
        "same_architecture_results_used_for_all_scenarios": integrity[
            "same_architecture_result_digests_all_scenarios"
        ],
        "scenario_vectors_global_and_exact": integrity["scenario_vectors_exact"],
        "no_winner_assertions": (
            qualification is not None
            and qualification.get("winner_assertions") == ()
        ),
        "frp_actual_direct_events_zero": specific.get("actual_direct_events") == 0,
        "frp_reserved_state_events_zero": (
            specific.get("reserved_state_events") == 0
        ),
        "frp_queue_overflow_events_zero": (
            specific.get("queue_overflow_events") == 0
        ),
        "frp_pending_route_count_final_zero": (
            specific.get("pending_route_count_final") == 0
        ),
        "frp_requested_direct_events_equal_prevented": (
            specific.get("requested_direct_events")
            == specific.get("prevented_direct_events")
        ),
        "frp_neutral_insertions_equal_neutral_routed": (
            specific.get("neutral_insertions")
            == specific.get("neutral_routed_events")
        ),
    }


def _qualification_valid(root: Mapping[str, JsonValue]) -> bool:
    qualification = _object(root.get("qualification"))
    expected = _expected_qualification(root)
    if qualification is None or expected is None:
        return False
    checks = _object(qualification.get("checks"))
    return (
        frozenset(qualification)
        == frozenset({"policy", "status", "checks", "winner_assertions"})
        and qualification.get("policy") == _QUALIFICATION_POLICY
        and qualification.get("winner_assertions") == ()
        and checks is not None
        and frozenset(checks) == _QUALIFICATION_FIELDS
        and dict(checks) == expected
        and qualification.get("status")
        == ("PASS" if all(expected.values()) else "FAIL")
    )


def _comparison_specs(
    root: Mapping[str, JsonValue],
) -> tuple[ValidationCheckSpec, ...]:
    ledger_shapes, ledger_values, ledger_relations = _raw_ledger_valid(root)
    scenario_shapes, scenario_values, scenario_relations = _scenarios_valid(root)
    top_types = (
        all(
            _text(root.get(field))
            for field in (
                "schema",
                "suite_name",
                "benchmark_kind",
                "frp_reference_version",
                "frp_scheduler",
                "workload_sha256",
                "hardware_sensitivity_profile_sha256",
                "thermal_profile_sha256",
                "raw_trace_set_sha256",
                "hardware_sensitivity_package_sha256",
            )
        )
        and isinstance(root.get("architecture_order"), tuple)
        and isinstance(root.get("raw_trace_ledger"), tuple)
        and isinstance(root.get("scenarios"), tuple)
        and all(
            isinstance(root.get(field), Mapping)
            for field in (
                "workload_profile",
                "hardware_sensitivity_profile",
                "profile_validation",
                "baseline_binding",
                "thermal_profile",
                "ranking_stability",
                "integrity",
                "qualification",
            )
        )
    )
    package_digest = _canonical_digest(
        _without(root, "hardware_sensitivity_package_sha256")
    )
    results = (
        (
            "hardware_sensitivity_comparison_identity",
            ValidationCategory.IDENTITY,
            root.get("schema") == _COMPARISON_SCHEMA
            and root.get("suite_name") == _SUITE
            and root.get("benchmark_kind") == _BENCHMARK_KIND
            and root.get("frp_reference_version") == _FRP_VERSION,
            "$",
        ),
        (
            "hardware_sensitivity_comparison_fields",
            ValidationCategory.STRUCTURE,
            frozenset(root) == _COMPARISON_ROOT_FIELDS,
            "$",
        ),
        (
            "hardware_sensitivity_comparison_types",
            ValidationCategory.TYPE,
            top_types,
            "$",
        ),
        (
            "hardware_sensitivity_comparison_scheduler",
            ValidationCategory.ALLOWED_VALUE,
            root.get("frp_scheduler") in _SCHEDULERS,
            "$.frp_scheduler",
        ),
        (
            "hardware_sensitivity_comparison_order",
            ValidationCategory.ORDERING,
            root.get("architecture_order") == _ARCHITECTURE_ORDER,
            "$.architecture_order",
        ),
        (
            "hardware_sensitivity_comparison_workload",
            ValidationCategory.STRUCTURE,
            _workload_valid(root.get("workload_profile"))
            and _digest(root.get("workload_sha256")),
            "$.workload_profile",
        ),
        (
            "hardware_sensitivity_embedded_profile",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _embedded_profile_valid(root),
            "$.hardware_sensitivity_profile",
        ),
        (
            "hardware_sensitivity_profile_validation",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _profile_validation_valid(root),
            "$.profile_validation",
        ),
        (
            "hardware_sensitivity_baseline_binding",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _baseline_binding_valid(root),
            "$.baseline_binding",
        ),
        (
            "hardware_sensitivity_thermal_profile",
            ValidationCategory.DIGEST,
            _thermal_profile_valid(root),
            "$.thermal_profile",
        ),
        (
            "hardware_sensitivity_raw_ledger_shapes",
            ValidationCategory.STRUCTURE,
            ledger_shapes,
            "$.raw_trace_ledger",
        ),
        (
            "hardware_sensitivity_raw_ledger_values",
            ValidationCategory.TYPE,
            ledger_values,
            "$.raw_trace_ledger",
        ),
        (
            "hardware_sensitivity_raw_ledger_relations",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            ledger_relations,
            "$.raw_trace_ledger",
        ),
        (
            "hardware_sensitivity_raw_trace_set_digest",
            ValidationCategory.DIGEST,
            _raw_trace_set_valid(root),
            "$.raw_trace_set_sha256",
        ),
        (
            "hardware_sensitivity_scenario_shapes",
            ValidationCategory.STRUCTURE,
            scenario_shapes,
            "$.scenarios",
        ),
        (
            "hardware_sensitivity_scenario_values",
            ValidationCategory.ALLOWED_VALUE,
            scenario_values,
            "$.scenarios",
        ),
        (
            "hardware_sensitivity_scenario_relations",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            scenario_relations,
            "$.scenarios",
        ),
        (
            "hardware_sensitivity_ranking_stability",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _ranking_stability_valid(root),
            "$.ranking_stability",
        ),
        (
            "hardware_sensitivity_integrity_vector",
            ValidationCategory.INVARIANT_VECTOR,
            _integrity_valid(root),
            "$.integrity",
        ),
        (
            "hardware_sensitivity_qualification",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _qualification_valid(root),
            "$.qualification",
        ),
        (
            "hardware_sensitivity_package_digest",
            ValidationCategory.DIGEST,
            _digest(root.get("hardware_sensitivity_package_sha256"))
            and package_digest == root.get("hardware_sensitivity_package_sha256"),
            "$.hardware_sensitivity_package_sha256",
        ),
    )
    return tuple(
        _spec(
            code,
            category,
            valid,
            path,
            "run_hardware_sensitivity_comparison.py",
        )
        for code, category, valid, path in results
    )


def _parsed(dispatched: DispatchedArtifact) -> ParsedJsonArtifact:
    if not isinstance(dispatched, DispatchedArtifact):
        raise HardwareSensitivityValidationError(
            "dispatched must be a DispatchedArtifact"
        )
    record = dispatched.compatibility_record
    if (
        dispatched.classification is not ArtifactClassification.JSON
        or dispatched.registration.status is not RegistrationStatus.REGISTERED
        or record is None
        or record.identifier not in _SCHEMAS
        or record.artifact_kind is not None
        or record.measurement_contour is not MeasurementContour.HARDWARE_SENSITIVITY
        or not isinstance(dispatched.parsed_artifact, ParsedJsonArtifact)
    ):
        raise HardwareSensitivityValidationError(
            "artifact is not a registered Hardware-Informed Sensitivity artifact"
        )
    return dispatched.parsed_artifact


@dataclass(frozen=True, slots=True)
class HardwareSensitivityValidation:
    """Immutable result for one Hardware-Informed Sensitivity artifact."""

    dispatched_artifact: DispatchedArtifact
    schema_identifier: str
    check_specs: tuple[ValidationCheckSpec, ...]

    def __post_init__(self) -> None:
        parsed = _parsed(self.dispatched_artifact)
        if (
            self.schema_identifier not in _SCHEMAS
            or parsed.declared_schema_identifier != self.schema_identifier
        ):
            raise HardwareSensitivityValidationError(
                "schema_identifier must match the registered artifact"
            )
        if not self.check_specs or any(
            not isinstance(spec, ValidationCheckSpec) for spec in self.check_specs
        ):
            raise HardwareSensitivityValidationError(
                "check_specs must contain validation specifications"
            )

    @property
    def valid(self) -> bool:
        """Return whether every mandatory check passed."""

        return all(
            not spec.mandatory or spec.outcome is CheckOutcome.PASS
            for spec in self.check_specs
        )


def validate_hardware_sensitivity(
    dispatched: DispatchedArtifact,
) -> HardwareSensitivityValidation:
    """Validate one registered Hardware-Informed Sensitivity artifact."""

    parsed = _parsed(dispatched)
    schema = parsed.declared_schema_identifier
    if schema == _PROFILE_SCHEMA:
        specs = _profile_specs(parsed.root)
    elif schema == _COMPARISON_SCHEMA:
        specs = _comparison_specs(parsed.root)
    else:
        raise HardwareSensitivityValidationError(
            "unsupported Hardware-Informed Sensitivity schema identifier"
        )
    return HardwareSensitivityValidation(
        dispatched_artifact=dispatched,
        schema_identifier=schema,
        check_specs=specs,
    )
