"""Read-only validation for Comparative Architecture Benchmark artifacts.

The validator covers the three exact schema identifiers registered for the
Comparative Architecture Benchmark Suite.  It validates published data and
digest relations without executing producers or reconstructing processor
semantics.  The schema-free workload profile remains an embedded input and is
not assigned an Observatory schema identifier.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

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
    "ComparativeArchitectureValidation",
    "ComparativeArchitectureValidationError",
    "validate_comparative_architecture",
]


_COST_SCHEMA = "frp.benchmark.normalized_cost_profile.v1"
_THERMAL_SCHEMA = "frp.benchmark.thermal_proxy_profile.v1"
_COMPARISON_SCHEMA = "frp.benchmark.architecture_comparison.v1"
_SCHEMAS = (_COST_SCHEMA, _THERMAL_SCHEMA, _COMPARISON_SCHEMA)
_SUITE = "FRP Comparative Architecture Benchmark Suite"
_BENCHMARK_KIND = "comparative_architecture_matrix"
_FRP_VERSION = "1.7.0"
_SCHEDULERS = frozenset({"7/1", "1/7"})
_QUALIFICATION_POLICY = "integrity_only_no_winner_assertions"
_THERMAL_EQUATION = (
    "ambient + (temperature - ambient) * thermal_decay "
    "+ normalized_cycle_cost * thermal_gain"
)
_HEX = frozenset("0123456789abcdef")


def _names(text: str) -> tuple[str, ...]:
    return tuple(text.split())


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
_TOP_FIELDS = frozenset(
    _names(
        "schema suite_name benchmark_kind frp_reference_version "
        "frp_scheduler architecture_order workload_profile workload_sha256 "
        "cost_profile cost_profile_sha256 thermal_profile "
        "thermal_profile_sha256 architectures comparison_matrix integrity "
        "qualification comparison_package_sha256"
    )
)
_COST_FIELDS = frozenset(
    _names(
        "schema suite_name profile_name cost_unit costs "
        "cost_profile_sha256"
    )
)
_THERMAL_FIELDS = frozenset(
    _names(
        "schema suite_name profile_name temperature_unit "
        "ambient_temperature_proxy thermal_decay thermal_gain "
        "update_equation thermal_profile_sha256"
    )
)
_WORKLOAD_FIELDS = frozenset(
    _names(
        "num_cells command_count seed issue_policy "
        "max_completion_cycles_per_command final_cooldown_cycles"
    )
)
_EMBEDDED_COST_FIELDS = frozenset(_names("profile_name cost_unit costs"))
_EMBEDDED_THERMAL_FIELDS = frozenset(
    _names(
        "profile_name temperature_unit ambient_temperature_proxy "
        "thermal_decay thermal_gain"
    )
)
_ARCHITECTURE_FIELDS = frozenset(
    _names(
        "architecture_id architecture_name architecture_result_sha256 "
        "architecture_specific_metrics comparison_metrics integrity "
        "normalized_cost raw_event_totals thermal_proxy workload_sha256"
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
_SPECIFIC_FIELDS = {
    "binary_synchronous_reference": frozenset(
        {"direct_binary_switches"}
    ),
    "binary_clock_gated_reference": frozenset(
        _names("clock_gate_active_fraction direct_binary_switches gated_cycles")
    ),
    "direct_ternary_reference": frozenset(
        _names(
            "direct_opposite_polarity_changes gated_cycles "
            "neutral_state_exits"
        )
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
_TOP_INTEGRITY_FIELDS = frozenset(
    _names(
        "architecture_order_match architecture_ids_unique "
        "same_workload_digest same_cost_profile_digest "
        "same_thermal_profile_digest architecture_result_digests_valid "
        "event_trace_closure cost_cycle_count_closure "
        "thermal_cycle_count_closure finite_numeric_values"
    )
)
_QUALIFICATION_FIELDS = frozenset(
    _names(
        "same_workload_digest same_cost_profile_digest "
        "same_thermal_profile_digest architecture_order_match "
        "all_architectures_completed_workload semantic_output_match_one "
        "finite_metric_values cost_trace_closure "
        "thermal_trace_cycle_closure frp_actual_direct_events_zero "
        "frp_reserved_state_events_zero frp_queue_overflow_events_zero "
        "frp_pending_route_count_final_zero"
    )
)


class ComparativeArchitectureValidationError(ValueError):
    """Raised when a validator input violates routing invariants."""


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _number(value: object) -> bool:
    if not (_integer(value) or isinstance(value, Decimal)):
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
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


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


def _cost_payload(
    profile_name: JsonValue,
    cost_unit: JsonValue,
    costs: JsonValue,
) -> Mapping[str, JsonValue]:
    return {
        "schema": _COST_SCHEMA,
        "suite_name": _SUITE,
        "profile_name": profile_name,
        "cost_unit": cost_unit,
        "costs": costs,
    }


def _thermal_payload(
    profile_name: JsonValue,
    temperature_unit: JsonValue,
    ambient: JsonValue,
    decay: JsonValue,
    gain: JsonValue,
) -> Mapping[str, JsonValue]:
    return {
        "schema": _THERMAL_SCHEMA,
        "suite_name": _SUITE,
        "profile_name": profile_name,
        "temperature_unit": temperature_unit,
        "ambient_temperature_proxy": ambient,
        "thermal_decay": decay,
        "thermal_gain": gain,
        "update_equation": _THERMAL_EQUATION,
    }


def _cost_values_valid(costs: object) -> bool:
    return (
        _field_set(costs, frozenset(_COST_CLASSES))
        and all(_nonnegative(costs[field]) for field in _COST_CLASSES)
        and any(costs[field] > 0 for field in _COST_CLASSES)
    )


def _thermal_values_valid(
    ambient: object,
    decay: object,
    gain: object,
) -> bool:
    return (
        _nonnegative(ambient)
        and _number(decay)
        and 0 <= decay < 1
        and _nonnegative(gain)
    )


def _cost_specs(
    root: Mapping[str, JsonValue],
) -> tuple[ValidationCheckSpec, ...]:
    costs = root.get("costs")
    types_valid = (
        all(
            _text(root.get(field))
            for field in ("schema", "suite_name", "profile_name", "cost_unit")
        )
        and isinstance(costs, Mapping)
        and isinstance(root.get("cost_profile_sha256"), str)
    )
    values_valid = _cost_values_valid(costs)
    expected = _canonical_digest(
        _cost_payload(
            root.get("profile_name"),
            root.get("cost_unit"),
            root.get("costs"),
        )
    )
    results = (
        (
            "comparative_cost_profile_identity",
            ValidationCategory.IDENTITY,
            root.get("schema") == _COST_SCHEMA
            and root.get("suite_name") == _SUITE,
            "$",
        ),
        (
            "comparative_cost_profile_fields",
            ValidationCategory.STRUCTURE,
            frozenset(root) == _COST_FIELDS,
            "$",
        ),
        (
            "comparative_cost_profile_types",
            ValidationCategory.TYPE,
            types_valid,
            "$",
        ),
        (
            "comparative_cost_profile_values",
            ValidationCategory.ALLOWED_VALUE,
            values_valid,
            "$.costs",
        ),
        (
            "comparative_cost_profile_digest",
            ValidationCategory.DIGEST,
            _digest(root.get("cost_profile_sha256"))
            and expected == root.get("cost_profile_sha256"),
            "$.cost_profile_sha256",
        ),
    )
    return tuple(
        _spec(code, category, valid, path, "common_cost_model.py")
        for code, category, valid, path in results
    )


def _thermal_specs(
    root: Mapping[str, JsonValue],
) -> tuple[ValidationCheckSpec, ...]:
    types_valid = (
        all(
            _text(root.get(field))
            for field in (
                "schema",
                "suite_name",
                "profile_name",
                "temperature_unit",
                "update_equation",
            )
        )
        and all(
            _number(root.get(field))
            for field in (
                "ambient_temperature_proxy",
                "thermal_decay",
                "thermal_gain",
            )
        )
        and isinstance(root.get("thermal_profile_sha256"), str)
    )
    values_valid = _thermal_values_valid(
        root.get("ambient_temperature_proxy"),
        root.get("thermal_decay"),
        root.get("thermal_gain"),
    ) and root.get("update_equation") == _THERMAL_EQUATION
    expected = _canonical_digest(
        _thermal_payload(
            root.get("profile_name"),
            root.get("temperature_unit"),
            root.get("ambient_temperature_proxy"),
            root.get("thermal_decay"),
            root.get("thermal_gain"),
        )
    )
    results = (
        (
            "comparative_thermal_profile_identity",
            ValidationCategory.IDENTITY,
            root.get("schema") == _THERMAL_SCHEMA
            and root.get("suite_name") == _SUITE,
            "$",
        ),
        (
            "comparative_thermal_profile_fields",
            ValidationCategory.STRUCTURE,
            frozenset(root) == _THERMAL_FIELDS,
            "$",
        ),
        (
            "comparative_thermal_profile_types",
            ValidationCategory.TYPE,
            types_valid,
            "$",
        ),
        (
            "comparative_thermal_profile_values",
            ValidationCategory.ALLOWED_VALUE,
            values_valid,
            "$",
        ),
        (
            "comparative_thermal_profile_digest",
            ValidationCategory.DIGEST,
            _digest(root.get("thermal_profile_sha256"))
            and expected == root.get("thermal_profile_sha256"),
            "$.thermal_profile_sha256",
        ),
    )
    return tuple(
        _spec(code, category, valid, path, "common_thermal_model.py")
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


def _embedded_profiles_valid(root: Mapping[str, JsonValue]) -> bool:
    cost = _object(root.get("cost_profile"))
    thermal = _object(root.get("thermal_profile"))
    if cost is None or thermal is None:
        return False
    return (
        frozenset(cost) == _EMBEDDED_COST_FIELDS
        and _text(cost.get("profile_name"))
        and _text(cost.get("cost_unit"))
        and _cost_values_valid(cost.get("costs"))
        and frozenset(thermal) == _EMBEDDED_THERMAL_FIELDS
        and _text(thermal.get("profile_name"))
        and _text(thermal.get("temperature_unit"))
        and _thermal_values_valid(
            thermal.get("ambient_temperature_proxy"),
            thermal.get("thermal_decay"),
            thermal.get("thermal_gain"),
        )
    )


def _embedded_profile_digests_valid(
    root: Mapping[str, JsonValue],
) -> bool:
    cost = _object(root.get("cost_profile"))
    thermal = _object(root.get("thermal_profile"))
    if cost is None or thermal is None:
        return False
    cost_digest = _canonical_digest(
        _cost_payload(
            cost.get("profile_name"),
            cost.get("cost_unit"),
            cost.get("costs"),
        )
    )
    thermal_digest = _canonical_digest(
        _thermal_payload(
            thermal.get("profile_name"),
            thermal.get("temperature_unit"),
            thermal.get("ambient_temperature_proxy"),
            thermal.get("thermal_decay"),
            thermal.get("thermal_gain"),
        )
    )
    return (
        _digest(root.get("cost_profile_sha256"))
        and _digest(root.get("thermal_profile_sha256"))
        and cost_digest == root.get("cost_profile_sha256")
        and thermal_digest == root.get("thermal_profile_sha256")
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
        return all(_integer(value[field]) and value[field] >= 0 for field in expected)
    return (
        all(
            _integer(value[field])
            for field in _FRP_INTEGER_SPECIFIC
        )
        and all(
            value[field] >= 0
            for field in _FRP_INTEGER_SPECIFIC
            if field not in {"C_minus_P_final_q16", "C_minus_P_min_q16"}
        )
        and all(_number(value[field]) for field in _FRP_NUMBER_SPECIFIC)
        and all(
            isinstance(value[field], bool)
            for field in _FRP_BOOLEAN_SPECIFIC
        )
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
        _integer(value[field]) and _number(value[field]) and value[field] >= 0
        for field in _RAW_FIELDS
    )


def _cost_result_valid(
    value: object,
    raw: object,
    top_cost: object,
    top_digest: object,
) -> bool:
    if (
        not _field_set(value, _NORMALIZED_COST_FIELDS)
        or not isinstance(raw, Mapping)
        or not isinstance(top_cost, Mapping)
    ):
        return False
    events = _object(value.get("event_totals"))
    contributions = _object(value.get("cost_contribution_totals"))
    costs = _object(top_cost.get("costs"))
    if events is None or contributions is None or costs is None:
        return False
    shape = (
        frozenset(events) == frozenset(_EVENT_FIELDS)
        and frozenset(contributions) == frozenset(_COST_CLASSES)
        and value.get("profile_name") == top_cost.get("profile_name")
        and value.get("cost_unit") == top_cost.get("cost_unit")
        and value.get("cost_profile_sha256") == top_digest
        and _digest(value.get("cycle_normalized_energy_sha256"))
    )
    if not shape:
        return False
    event_closure = all(
        _integer(events[field])
        and _number(events[field])
        and events[field] >= 0
        and events[field] == raw.get(field)
        for field in _EVENT_FIELDS
    )
    if not event_closure or not _cost_values_valid(costs):
        return False
    contribution_closure = all(
        _nonnegative(contributions[cost_class])
        and _close(
            contributions[cost_class],
            events[event_field] * costs[cost_class],
        )
        for event_field, cost_class in _EVENT_TO_COST.items()
    )
    totals = all(
        _nonnegative(value.get(field))
        for field in (
            "peak_cycle_normalized_energy",
            "total_normalized_energy",
            "normalized_energy_per_completed_command",
        )
    )
    if not (contribution_closure and totals):
        return False
    total = sum(contributions.values(), Decimal(0))
    completed = raw.get("semantic_commands_completed")
    if not (
        _integer(completed)
        and _number(completed)
        and completed >= 0
    ):
        return False
    expected_per_command = total / completed if completed else Decimal(0)
    return (
        _close(value.get("total_normalized_energy"), total)
        and _close(
            value.get("normalized_energy_per_completed_command"),
            expected_per_command,
        )
    )


def _thermal_result_valid(
    value: object,
    top_thermal: object,
    top_digest: object,
) -> bool:
    return (
        _field_set(value, _THERMAL_RESULT_FIELDS)
        and isinstance(top_thermal, Mapping)
        and value.get("profile_name") == top_thermal.get("profile_name")
        and value.get("temperature_unit")
        == top_thermal.get("temperature_unit")
        and value.get("thermal_profile_sha256") == top_digest
        and _nonnegative(value.get("peak_temperature_proxy"))
        and _nonnegative(value.get("final_temperature_proxy"))
        and value.get("final_temperature_proxy")
        <= value.get("peak_temperature_proxy")
        and _digest(value.get("temperature_proxy_trace_sha256"))
    )


def _architecture_relations_valid(
    architecture: Mapping[str, JsonValue],
) -> bool:
    raw = _object(architecture.get("raw_event_totals"))
    metrics = _object(architecture.get("comparison_metrics"))
    if raw is None or metrics is None:
        return False
    issued = raw.get("semantic_commands_issued")
    completed = raw.get("semantic_commands_completed")
    cycles = raw.get("processor_cycles")
    active = raw.get("active_clocked_cycles")
    completion_ticks = metrics.get("completion_ticks")
    if not all(
        _integer(value) and _number(value)
        for value in (issued, completed, cycles, active)
    ) or not _nonnegative(completion_ticks):
        return False
    expected_completion = (
        Decimal(completed) / Decimal(issued) if issued else Decimal(0)
    )
    expected_active = (
        Decimal(active) / Decimal(cycles)
        if cycles
        else Decimal(0)
    )
    expected_throughput = (
        Decimal(completed) / Decimal(completion_ticks)
        if completion_ticks
        else Decimal(0)
    )
    return (
        metrics.get("logical_state_changes")
        == raw.get("logical_state_changes")
        and metrics.get("encoded_bit_toggles")
        == raw.get("encoded_bit_toggles")
        and metrics.get("processor_cycles") == cycles
        and metrics.get("active_clocked_cycles")
        == raw.get("active_clocked_cycles")
        and _close(metrics.get("semantic_completion_ratio"), expected_completion)
        and _close(metrics.get("active_clock_fraction"), expected_active)
        and _close(
            metrics.get("throughput_commands_per_tick"),
            expected_throughput,
        )
    )


def _architectures_valid(
    root: Mapping[str, JsonValue],
) -> tuple[bool, bool, bool]:
    architectures = _rows(root.get("architectures"))
    if architectures is None or len(architectures) != len(_ARCHITECTURE_ORDER):
        return False, False, False
    shapes_valid = True
    values_valid = True
    relations_valid = True
    for architecture, architecture_id in zip(
        architectures,
        _ARCHITECTURE_ORDER,
        strict=True,
    ):
        shapes_valid = shapes_valid and (
            frozenset(architecture) == _ARCHITECTURE_FIELDS
            and architecture.get("architecture_id") == architecture_id
            and _text(architecture.get("architecture_name"))
            and _digest(architecture.get("architecture_result_sha256"))
            and _digest(architecture.get("workload_sha256"))
            and _field_set(
                architecture.get("integrity"),
                _ARCHITECTURE_INTEGRITY_FIELDS,
            )
        )
        values_valid = values_valid and (
            _raw_valid(architecture.get("raw_event_totals"))
            and _metrics_valid(architecture.get("comparison_metrics"))
            and _specific_valid(
                architecture_id,
                architecture.get("architecture_specific_metrics"),
            )
            and all(
                isinstance(value, bool)
                for value in (
                    architecture.get("integrity", {}).values()
                    if isinstance(architecture.get("integrity"), Mapping)
                    else ()
                )
            )
        )
        relations_valid = relations_valid and (
            architecture.get("workload_sha256") == root.get("workload_sha256")
            and _cost_result_valid(
                architecture.get("normalized_cost"),
                architecture.get("raw_event_totals"),
                root.get("cost_profile"),
                root.get("cost_profile_sha256"),
            )
            and _thermal_result_valid(
                architecture.get("thermal_proxy"),
                root.get("thermal_profile"),
                root.get("thermal_profile_sha256"),
            )
            and _architecture_relations_valid(architecture)
        )
    return shapes_valid, values_valid, relations_valid


def _matrix_row(architecture: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    raw = architecture["raw_event_totals"]
    metrics = architecture["comparison_metrics"]
    cost = architecture["normalized_cost"]
    thermal = architecture["thermal_proxy"]
    assert isinstance(raw, Mapping)
    assert isinstance(metrics, Mapping)
    assert isinstance(cost, Mapping)
    assert isinstance(thermal, Mapping)
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


def _matrix_valid(root: Mapping[str, JsonValue]) -> bool:
    architectures = _rows(root.get("architectures"))
    matrix = _rows(root.get("comparison_matrix"))
    if (
        architectures is None
        or matrix is None
        or len(architectures) != len(_ARCHITECTURE_ORDER)
        or len(matrix) != len(_ARCHITECTURE_ORDER)
        or not all(frozenset(row) == _MATRIX_FIELDS for row in matrix)
    ):
        return False
    try:
        return all(
            dict(row) == _matrix_row(architecture)
            for row, architecture in zip(matrix, architectures, strict=True)
        )
    except (KeyError, TypeError, AssertionError):
        return False


def _expected_integrity(
    root: Mapping[str, JsonValue],
) -> dict[str, bool] | None:
    architectures = _rows(root.get("architectures"))
    matrix = _rows(root.get("comparison_matrix"))
    if architectures is None or matrix is None:
        return None
    ids = tuple(row.get("architecture_id") for row in architectures)
    matrix_ids = tuple(row.get("architecture_id") for row in matrix)
    integrity_rows = tuple(_object(row.get("integrity")) for row in architectures)
    if any(row is None for row in integrity_rows):
        return None
    ids_unique = all(isinstance(value, str) for value in ids) and (
        len(set(ids)) == len(_ARCHITECTURE_ORDER)
    )
    return {
        "architecture_order_match": (
            ids == _ARCHITECTURE_ORDER and matrix_ids == _ARCHITECTURE_ORDER
        ),
        "architecture_ids_unique": ids_unique,
        "same_workload_digest": all(
            row.get("workload_sha256") == root.get("workload_sha256")
            for row in architectures
        ),
        "same_cost_profile_digest": all(
            isinstance(row.get("normalized_cost"), Mapping)
            and row["normalized_cost"].get("cost_profile_sha256")
            == root.get("cost_profile_sha256")
            for row in architectures
        ),
        "same_thermal_profile_digest": all(
            isinstance(row.get("thermal_proxy"), Mapping)
            and row["thermal_proxy"].get("thermal_profile_sha256")
            == root.get("thermal_profile_sha256")
            for row in architectures
        ),
        "architecture_result_digests_valid": all(
            _digest(row.get("architecture_result_sha256"))
            for row in architectures
        ),
        "event_trace_closure": all(
            row is not None and row.get("event_trace_closure") is True
            for row in integrity_rows
        ),
        "cost_cycle_count_closure": all(
            row is not None and row.get("cost_cycle_count_closure") is True
            for row in integrity_rows
        ),
        "thermal_cycle_count_closure": all(
            row is not None and row.get("thermal_cycle_count_closure") is True
            for row in integrity_rows
        ),
        "finite_numeric_values": all(
            row is not None and row.get("finite_numeric_values") is True
            for row in integrity_rows
        ),
    }


def _integrity_valid(root: Mapping[str, JsonValue]) -> bool:
    integrity = _object(root.get("integrity"))
    expected = _expected_integrity(root)
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
    architectures = _rows(root.get("architectures"))
    integrity = _expected_integrity(root)
    workload = _object(root.get("workload_profile"))
    if architectures is None or integrity is None or workload is None:
        return None
    frp = next(
        (
            row
            for row in architectures
            if row.get("architecture_id") == "frp_v1_7_0_quantized_shadow"
        ),
        None,
    )
    if not isinstance(frp, Mapping):
        return None
    specific = _object(frp.get("architecture_specific_metrics"))
    if specific is None:
        return None
    command_count = workload.get("command_count")
    return {
        "same_workload_digest": integrity["same_workload_digest"],
        "same_cost_profile_digest": integrity["same_cost_profile_digest"],
        "same_thermal_profile_digest": integrity[
            "same_thermal_profile_digest"
        ],
        "architecture_order_match": integrity["architecture_order_match"],
        "all_architectures_completed_workload": all(
            isinstance(row.get("raw_event_totals"), Mapping)
            and row["raw_event_totals"].get("semantic_commands_issued")
            == command_count
            and row["raw_event_totals"].get("semantic_commands_completed")
            == command_count
            for row in architectures
        ),
        "semantic_output_match_one": all(
            isinstance(row.get("comparison_metrics"), Mapping)
            and row["comparison_metrics"].get("semantic_output_match")
            == 1
            for row in architectures
        ),
        "finite_metric_values": integrity["finite_numeric_values"],
        "cost_trace_closure": (
            integrity["event_trace_closure"]
            and integrity["cost_cycle_count_closure"]
        ),
        "thermal_trace_cycle_closure": integrity[
            "thermal_cycle_count_closure"
        ],
        "frp_actual_direct_events_zero": (
            specific.get("actual_direct_events") == 0
        ),
        "frp_reserved_state_events_zero": (
            specific.get("reserved_state_events") == 0
        ),
        "frp_queue_overflow_events_zero": (
            specific.get("queue_overflow_events") == 0
        ),
        "frp_pending_route_count_final_zero": (
            specific.get("pending_route_count_final") == 0
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
    shapes_valid, values_valid, relations_valid = _architectures_valid(root)
    top_types = (
        all(
            isinstance(root.get(field), str)
            for field in (
                "schema",
                "suite_name",
                "benchmark_kind",
                "frp_reference_version",
                "frp_scheduler",
                "workload_sha256",
                "cost_profile_sha256",
                "thermal_profile_sha256",
                "comparison_package_sha256",
            )
        )
        and all(
            isinstance(root.get(field), tuple)
            for field in ("architecture_order", "architectures", "comparison_matrix")
        )
        and all(
            isinstance(root.get(field), Mapping)
            for field in (
                "workload_profile",
                "cost_profile",
                "thermal_profile",
                "integrity",
                "qualification",
            )
        )
    )
    package_digest = _canonical_digest(
        _without(root, "comparison_package_sha256")
    )
    results = (
        (
            "comparative_architecture_identity",
            ValidationCategory.IDENTITY,
            root.get("schema") == _COMPARISON_SCHEMA
            and root.get("suite_name") == _SUITE
            and root.get("benchmark_kind") == _BENCHMARK_KIND
            and root.get("frp_reference_version") == _FRP_VERSION,
            "$",
        ),
        (
            "comparative_architecture_top_level_fields",
            ValidationCategory.STRUCTURE,
            frozenset(root) == _TOP_FIELDS,
            "$",
        ),
        (
            "comparative_architecture_top_level_types",
            ValidationCategory.TYPE,
            top_types,
            "$",
        ),
        (
            "comparative_architecture_scheduler",
            ValidationCategory.ALLOWED_VALUE,
            isinstance(root.get("frp_scheduler"), str)
            and root.get("frp_scheduler") in _SCHEDULERS,
            "$.frp_scheduler",
        ),
        (
            "comparative_architecture_order",
            ValidationCategory.ORDERING,
            root.get("architecture_order") == _ARCHITECTURE_ORDER,
            "$.architecture_order",
        ),
        (
            "comparative_architecture_workload_profile",
            ValidationCategory.STRUCTURE,
            _workload_valid(root.get("workload_profile"))
            and _digest(root.get("workload_sha256")),
            "$.workload_profile",
        ),
        (
            "comparative_architecture_embedded_profiles",
            ValidationCategory.STRUCTURE,
            _embedded_profiles_valid(root),
            "$.cost_profile",
        ),
        (
            "comparative_architecture_profile_digests",
            ValidationCategory.DIGEST,
            _embedded_profile_digests_valid(root),
            "$.cost_profile_sha256",
        ),
        (
            "comparative_architecture_result_shapes",
            ValidationCategory.STRUCTURE,
            shapes_valid,
            "$.architectures",
        ),
        (
            "comparative_architecture_result_values",
            ValidationCategory.TYPE,
            values_valid,
            "$.architectures",
        ),
        (
            "comparative_architecture_result_relations",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            relations_valid,
            "$.architectures",
        ),
        (
            "comparative_architecture_matrix_projection",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _matrix_valid(root),
            "$.comparison_matrix",
        ),
        (
            "comparative_architecture_integrity_vector",
            ValidationCategory.INVARIANT_VECTOR,
            _integrity_valid(root),
            "$.integrity",
        ),
        (
            "comparative_architecture_qualification",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _qualification_valid(root),
            "$.qualification",
        ),
        (
            "comparative_architecture_package_digest",
            ValidationCategory.DIGEST,
            _digest(root.get("comparison_package_sha256"))
            and package_digest == root.get("comparison_package_sha256"),
            "$.comparison_package_sha256",
        ),
    )
    return tuple(
        _spec(
            code,
            category,
            valid,
            path,
            "run_architecture_comparison.py",
        )
        for code, category, valid, path in results
    )


def _parsed(dispatched: DispatchedArtifact) -> ParsedJsonArtifact:
    if not isinstance(dispatched, DispatchedArtifact):
        raise ComparativeArchitectureValidationError(
            "dispatched must be a DispatchedArtifact"
        )
    record = dispatched.compatibility_record
    if (
        dispatched.classification is not ArtifactClassification.JSON
        or dispatched.registration.status
        is not RegistrationStatus.REGISTERED
        or record is None
        or record.identifier not in _SCHEMAS
        or record.artifact_kind is not None
        or record.measurement_contour
        is not MeasurementContour.COMPARATIVE_ARCHITECTURE
        or not isinstance(dispatched.parsed_artifact, ParsedJsonArtifact)
    ):
        raise ComparativeArchitectureValidationError(
            "artifact is not a registered Comparative Architecture artifact"
        )
    return dispatched.parsed_artifact


@dataclass(frozen=True, slots=True)
class ComparativeArchitectureValidation:
    """Immutable result for one Comparative Architecture artifact."""

    dispatched_artifact: DispatchedArtifact
    schema_identifier: str
    check_specs: tuple[ValidationCheckSpec, ...]

    def __post_init__(self) -> None:
        parsed = _parsed(self.dispatched_artifact)
        if (
            self.schema_identifier not in _SCHEMAS
            or parsed.declared_schema_identifier != self.schema_identifier
        ):
            raise ComparativeArchitectureValidationError(
                "schema_identifier must match the registered artifact"
            )
        if not self.check_specs or any(
            not isinstance(spec, ValidationCheckSpec)
            for spec in self.check_specs
        ):
            raise ComparativeArchitectureValidationError(
                "check_specs must contain validation specifications"
            )

    @property
    def valid(self) -> bool:
        """Return whether every mandatory check passed."""

        return all(
            not spec.mandatory or spec.outcome is CheckOutcome.PASS
            for spec in self.check_specs
        )


def validate_comparative_architecture(
    dispatched: DispatchedArtifact,
) -> ComparativeArchitectureValidation:
    """Validate one registered Comparative Architecture artifact."""

    parsed = _parsed(dispatched)
    schema = parsed.declared_schema_identifier
    if schema == _COST_SCHEMA:
        specs = _cost_specs(parsed.root)
    elif schema == _THERMAL_SCHEMA:
        specs = _thermal_specs(parsed.root)
    elif schema == _COMPARISON_SCHEMA:
        specs = _comparison_specs(parsed.root)
    else:
        raise ComparativeArchitectureValidationError(
            "unsupported Comparative Architecture schema identifier"
        )
    return ComparativeArchitectureValidation(
        dispatched_artifact=dispatched,
        schema_identifier=schema,
        check_specs=specs,
    )
