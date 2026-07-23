"""Read-only checks for ``frp.structured_output.v1.7.0`` artifacts.

The registered ``demo`` and ``self_test`` variants are validated as data.
Nothing in an artifact is executed, rewritten, or treated as another FRP
measurement contour.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from parsers.artifact_dispatch import (
    ArtifactClassification,
    DispatchedArtifact,
    RegistrationStatus,
)
from parsers.json_artifact import JsonValue, ParsedJsonArtifact

from .audit_report import CheckOutcome, SourceLocation, ValidationCategory
from .validation_core import ValidationCheckSpec


__all__ = [
    "StructuredOutputValidation",
    "StructuredOutputValidationError",
    "validate_structured_output",
]


_SCHEMA = "frp.structured_output.v1.7.0"
_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_KINDS = ("demo", "self_test")
_HEX = frozenset("0123456789abcdef")


def _names(text: str) -> tuple[str, ...]:
    return tuple(text.split())


_DEMO = _names(
    "schema kind version milestone configuration kernel hardware_profile "
    "summary preload_digest trace_digest cell_trace_digest"
)
_CONFIG = _names(
    "cells steps seed scheduler transition_fraction request_lanes "
    "gamma_nominal fractal_alpha thermal_beta ambient_heat "
    "thermal_time_constant thermal_soft_limit thermal_hard_limit "
    "coupling_nominal delay_alpha thermal_diffusion_gain"
)
_KERNEL = _names(
    "balanced_ternary_states active_neutral_state neutral_routes "
    "scheduler_modes actual_direct_events_target"
)
_HARDWARE = _names("scalar unit phase gamma state_encoding")
_SUMMARY = _names(
    "version milestone cells hierarchy_depth request_lanes steps "
    "ticks_recorded scheduler scheduler_counts scheduler_counts_valid "
    "transition_fraction balanced_ternary_state_domain "
    "reserved_state_events actual_direct_events requested_direct_events "
    "prevented_direct_events neutral_routed_events neutralized_conflicts "
    "pending_route_count_final neutral_route_queue_capacity "
    "queue_overflow_events switch_load_peak_q16 switch_load_peak "
    "C_minus_P_final_q16 C_minus_P_final C_minus_P_min_q16 C_minus_P_min "
    "boundary_detected fixed_point_topology_sum_exact "
    "fixed_point_thermal_sum_exact"
)
_TRACE = _names(
    "tick reset_n scheduler_mode scheduler_state scheduler_state_name "
    "auto_targets_enable request_valid_mask request_cell_ids "
    "request_target_states gamma_noise_update_valid gamma_noise_target_q16 "
    "states_packed states_packed_hex states_human pending_route_count "
    "switch_load_q16 heat_global_q16 global_phase_coherence_q30 C_q16 "
    "P_q16 C_minus_P_q16 requested_direct_events prevented_direct_events "
    "neutral_routed_events neutralized_conflicts actual_direct_events "
    "reserved_state_events queue_overflow_events changes"
)
_CELL = _names(
    "tick cell_id state_code phase_word frequency_target_q16 "
    "frequency_current_q16 frequency_lag_q16 generated_power_q16 heat_q16 "
    "thermal_overload_q16 gamma_noise_state_q16 gamma_effective_word "
    "thermal_node_factor_q30 coupling_field_q16"
)
_ROUTE = _names("tick cell_id target_state ready_tick route_status")
_SELF_TEST = _names(
    "schema kind version milestone status check_count checks "
    "neutral_route_validation scheduler_validation "
    "request_lane_order_validation queue_exhaustion_validation "
    "fixed_point_validation encoding_validation topology_validation "
    "trigonometric_lut_validation semantic_correlation "
    "exact_shadow_replay vector_determinism scaling_validation"
)


class StructuredOutputValidationError(ValueError):
    """Raised when a validator input violates routing invariants."""


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _number(value: object) -> bool:
    return _integer(value) or isinstance(value, Decimal)


def _object(value: object) -> bool:
    return isinstance(value, Mapping)


def _rows(value: object) -> tuple[Mapping[str, JsonValue], ...] | None:
    if isinstance(value, tuple) and all(isinstance(row, Mapping) for row in value):
        return value
    return None


def _spec(
    code: str,
    category: ValidationCategory,
    valid: bool,
    path: str,
) -> ValidationCheckSpec:
    label = code.replace("_", " ")
    result = "matches" if valid else "does not match"
    return ValidationCheckSpec(
        check_code=code,
        category=category,
        outcome=CheckOutcome.PASS if valid else CheckOutcome.FAIL,
        message=f"The {label} {result} the registered upstream contract.",
        source_locations=(SourceLocation(json_path=path),),
        upstream_rule_reference="docs/output_schema.md",
    )


def _not_applicable(code: str, collection: str) -> ValidationCheckSpec:
    return ValidationCheckSpec(
        check_code=code,
        category=ValidationCategory.DIGEST,
        outcome=CheckOutcome.NOT_APPLICABLE,
        message=(
            f"Digest recalculation requires the optional {collection} "
            "collection."
        ),
        upstream_rule_reference="docs/output_schema.md",
        mandatory=False,
    )


def _has_fields(value: object, fields: tuple[str, ...]) -> bool:
    return isinstance(value, Mapping) and all(field in value for field in fields)


def _types(
    value: object,
    *,
    integers: tuple[str, ...] = (),
    numbers: tuple[str, ...] = (),
    strings: tuple[str, ...] = (),
    booleans: tuple[str, ...] = (),
    objects: tuple[str, ...] = (),
    arrays: tuple[str, ...] = (),
) -> bool:
    if not isinstance(value, Mapping):
        return False
    groups = (
        (integers, _integer),
        (numbers, _number),
        (strings, lambda item: isinstance(item, str)),
        (booleans, lambda item: isinstance(item, bool)),
        (objects, _object),
        (arrays, lambda item: isinstance(item, tuple)),
    )
    return all(
        field not in value or predicate(value[field])
        for fields, predicate in groups
        for field in fields
    )


def _row_shape(
    value: object,
    fields: tuple[str, ...],
    *,
    strings: tuple[str, ...] = (),
    arrays: tuple[str, ...] = (),
) -> bool:
    rows = _rows(value)
    if rows is None or not all(_has_fields(row, fields) for row in rows):
        return False
    string_set = frozenset(strings)
    array_set = frozenset(arrays)
    for row in rows:
        for field in fields:
            item = row[field]
            if field in string_set:
                valid = isinstance(item, str)
            elif field in array_set:
                valid = isinstance(item, tuple) and all(_integer(v) for v in item)
            else:
                valid = _integer(item)
            if not valid:
                return False
    return True


def _digest_syntax(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _canonical_digest(value: JsonValue) -> str | None:
    def thaw(item: JsonValue) -> object:
        if isinstance(item, Decimal):
            raise TypeError
        if isinstance(item, Mapping):
            return {key: thaw(member) for key, member in item.items()}
        if isinstance(item, tuple):
            return [thaw(member) for member in item]
        return item

    try:
        text = json.dumps(
            thaw(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ) + "\n"
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _envelope(root: Mapping[str, JsonValue], kind: str) -> bool:
    return (
        root.get("schema") == _SCHEMA
        and root.get("kind") == kind
        and root.get("version") == _VERSION
        and root.get("milestone") == _MILESTONE
    )


def _demo_specs(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    configuration = root.get("configuration")
    kernel = root.get("kernel")
    hardware = root.get("hardware_profile")
    summary = root.get("summary")
    specs = [
        _spec("structured_output_envelope", ValidationCategory.IDENTITY,
              _envelope(root, "demo"), "$"),
        _spec("structured_demo_required_fields", ValidationCategory.STRUCTURE,
              _has_fields(root, _DEMO), "$"),
        _spec("structured_demo_configuration_fields", ValidationCategory.STRUCTURE,
              _has_fields(configuration, _CONFIG), "$.configuration"),
        _spec("structured_demo_kernel_fields", ValidationCategory.STRUCTURE,
              _has_fields(kernel, _KERNEL), "$.kernel"),
        _spec("structured_demo_hardware_fields", ValidationCategory.STRUCTURE,
              _has_fields(hardware, _HARDWARE), "$.hardware_profile"),
        _spec("structured_demo_summary_fields", ValidationCategory.STRUCTURE,
              _has_fields(summary, _SUMMARY), "$.summary"),
    ]

    config_numbers = tuple(
        field
        for field in _CONFIG
        if field not in {"cells", "steps", "seed", "scheduler", "request_lanes"}
    )
    config_types = _types(
        configuration,
        integers=("cells", "steps", "seed", "request_lanes"),
        numbers=config_numbers,
        strings=("scheduler",),
    )
    summary_numbers = (
        "transition_fraction", "switch_load_peak", "C_minus_P_final",
        "C_minus_P_min",
    )
    summary_strings = ("version", "milestone", "scheduler")
    summary_booleans = (
        "scheduler_counts_valid", "balanced_ternary_state_domain",
        "boundary_detected", "fixed_point_topology_sum_exact",
        "fixed_point_thermal_sum_exact",
    )
    summary_integers = tuple(
        field
        for field in _SUMMARY
        if field not in set(summary_numbers + summary_strings + summary_booleans)
        and field != "scheduler_counts"
    )
    summary_types = _types(
        summary,
        integers=summary_integers,
        numbers=summary_numbers,
        strings=summary_strings,
        booleans=summary_booleans,
        objects=("scheduler_counts",),
    )
    specs.extend(
        (
            _spec("structured_demo_configuration_types", ValidationCategory.TYPE,
                  config_types, "$.configuration"),
            _spec("structured_demo_summary_types", ValidationCategory.TYPE,
                  summary_types, "$.summary"),
        )
    )

    expected_kernel = {
        "balanced_ternary_states": (-1, 0, 1),
        "active_neutral_state": 0,
        "neutral_routes": ("-1 -> 0 -> 1", "1 -> 0 -> -1"),
        "scheduler_modes": ("free", "7/1", "1/7"),
        "actual_direct_events_target": 0,
    }
    expected_hardware = {
        "scalar": "S32Q16",
        "unit": "S32Q30",
        "phase": "PHASE_U32",
        "gamma": "GAMMA_S32",
        "state_encoding": {"-1": "11", "0": "00", "1": "01",
                           "reserved": "10"},
    }
    kernel_valid = isinstance(kernel, Mapping) and all(
        kernel.get(field) == value for field, value in expected_kernel.items()
    )
    hardware_valid = isinstance(hardware, Mapping) and all(
        hardware.get(field) == value for field, value in expected_hardware.items()
    )
    config_valid = False
    if isinstance(configuration, Mapping):
        cells = configuration.get("cells")
        config_valid = (
            _integer(cells) and cells >= 2 and cells & (cells - 1) == 0
            and configuration.get("scheduler") in ("free", "7/1", "1/7")
        )
    invariants_valid = isinstance(summary, Mapping) and all(
        (
            summary.get("version") == _VERSION,
            summary.get("milestone") == _MILESTONE,
            summary.get("scheduler_counts_valid") is True,
            summary.get("balanced_ternary_state_domain") is True,
            summary.get("fixed_point_topology_sum_exact") is True,
            summary.get("fixed_point_thermal_sum_exact") is True,
            summary.get("actual_direct_events") == 0,
            summary.get("reserved_state_events") == 0,
        )
    )
    specs.extend(
        (
            _spec("structured_demo_kernel_values",
                  ValidationCategory.TERNARY_DOMAIN, kernel_valid, "$.kernel"),
            _spec("structured_demo_hardware_values",
                  ValidationCategory.ALLOWED_VALUE, hardware_valid,
                  "$.hardware_profile"),
            _spec("structured_demo_configuration_values",
                  ValidationCategory.ALLOWED_VALUE, config_valid,
                  "$.configuration"),
            _spec("structured_demo_summary_invariants",
                  ValidationCategory.INVARIANT_VECTOR, invariants_valid,
                  "$.summary"),
        )
    )

    digests_valid = all(
        _digest_syntax(root.get(field))
        for field in ("preload_digest", "trace_digest", "cell_trace_digest")
    )
    presence = tuple(
        field in root for field in ("trace", "cell_trace", "route_events")
    )
    collections_valid = presence in ((False, False, False), (True, True, True))
    specs.extend(
        (
            _spec("structured_demo_digest_syntax", ValidationCategory.DIGEST,
                  digests_valid, "$"),
            _spec("structured_demo_full_trace_collection",
                  ValidationCategory.STRUCTURE, collections_valid, "$"),
        )
    )
    if presence == (True, True, True):
        specs.extend(_full_trace_specs(root, configuration, summary))
    else:
        specs.extend(
            (
                _not_applicable("structured_demo_trace_digest", "trace"),
                _not_applicable("structured_demo_cell_trace_digest", "cell_trace"),
            )
        )
    return tuple(specs)


def _full_trace_specs(
    root: Mapping[str, JsonValue],
    configuration: object,
    summary: object,
) -> tuple[ValidationCheckSpec, ...]:
    trace_value = root.get("trace")
    cell_value = root.get("cell_trace")
    route_value = root.get("route_events")
    trace = _rows(trace_value)
    cells = _rows(cell_value)
    routes = _rows(route_value)
    trace_shape = _row_shape(
        trace_value,
        _TRACE,
        strings=("scheduler_state_name", "states_packed_hex", "states_human"),
        arrays=("request_cell_ids", "request_target_states",
                "gamma_noise_target_q16"),
    )
    cell_shape = _row_shape(cell_value, _CELL)
    route_shape = _row_shape(route_value, _ROUTE, strings=("route_status",))

    steps = (
        configuration.get("steps")
        if isinstance(configuration, Mapping)
        else None
    )
    cell_count = (
        configuration.get("cells")
        if isinstance(configuration, Mapping)
        else None
    )
    tick_order = (
        trace is not None and _integer(steps)
        and tuple(row.get("tick") for row in trace) == tuple(range(steps))
    )
    cell_order = cells is not None and _integer(steps) and _integer(cell_count)
    if cell_order:
        expected = tuple((tick, cell) for tick in range(steps)
                         for cell in range(cell_count))
        observed = tuple((row.get("tick"), row.get("cell_id")) for row in cells)
        cell_order = observed == expected

    modes = {"free": 0, "7/1": 1, "1/7": 2}
    states = {"free": 0, "balance": 1, "commit": 2,
              "excite": 3, "neutralize": 4}
    scheduler_valid = trace is not None and isinstance(configuration, Mapping)
    if scheduler_valid:
        mode = modes.get(configuration.get("scheduler"))
        scheduler_valid = mode is not None and all(
            row.get("scheduler_mode") == mode
            and states.get(row.get("scheduler_state_name"))
            == row.get("scheduler_state")
            for row in trace
        )

    domain_valid = trace is not None and cells is not None
    if domain_valid:
        domain_valid = all(
            set(row.get("states_human", "")) <= {"M", "N", "P"}
            and all(code in {0, 1, 3}
                    for code in row.get("request_target_states", ()))
            and row.get("actual_direct_events") == 0
            and row.get("reserved_state_events") == 0
            for row in trace
        ) and all(row.get("state_code") in {0, 1, 3} for row in cells)

    capacity_valid = trace is not None and isinstance(summary, Mapping)
    if capacity_valid:
        lanes = summary.get("request_lanes")
        capacity_valid = _integer(lanes) and lanes > 0 and all(
            _integer(row.get("changes")) and 0 <= row["changes"] <= lanes
            for row in trace
        )

    route_valid = routes is not None
    if route_valid:
        ticks = tuple(row.get("tick") for row in routes)
        route_valid = all(_integer(tick) for tick in ticks)
        route_valid = route_valid and ticks == tuple(sorted(ticks))
        route_valid = route_valid and all(
            row.get("route_status") in {"pending", "applied"}
            and row.get("target_state") in {-1, 1}
            and (row.get("route_status") != "applied"
                 or row.get("tick") >= row.get("ready_tick"))
            for row in routes
        )

    relations_valid = trace is not None and isinstance(summary, Mapping)
    if relations_valid:
        declared = summary.get("scheduler_counts")
        counters = _names(
            "requested_direct_events prevented_direct_events "
            "neutral_routed_events neutralized_conflicts actual_direct_events "
            "reserved_state_events queue_overflow_events"
        )
        relations_valid = (
            isinstance(declared, Mapping)
            and dict(declared)
            == dict(Counter(row.get("scheduler_state_name") for row in trace))
            and summary.get("ticks_recorded") == len(trace)
            and (not trace or all(summary.get(field) == trace[-1].get(field)
                                  for field in counters))
        )

    results = (
        ("structured_demo_trace_rows", ValidationCategory.STRUCTURE,
         trace_shape, "$.trace"),
        ("structured_demo_cell_trace_rows", ValidationCategory.STRUCTURE,
         cell_shape, "$.cell_trace"),
        ("structured_demo_route_rows", ValidationCategory.STRUCTURE,
         route_shape, "$.route_events"),
        ("structured_demo_trace_tick_order", ValidationCategory.ORDERING,
         tick_order, "$.trace"),
        ("structured_demo_cell_trace_order", ValidationCategory.ORDERING,
         cell_order, "$.cell_trace"),
        ("structured_demo_scheduler_encoding",
         ValidationCategory.SCHEDULER_RELATION, scheduler_valid, "$.trace"),
        ("structured_demo_trace_ternary_domain",
         ValidationCategory.TERNARY_DOMAIN, domain_valid, "$"),
        ("structured_demo_transition_capacity",
         ValidationCategory.TRANSITION_CAPACITY, capacity_valid, "$.trace"),
        ("structured_demo_pending_route_relations",
         ValidationCategory.PENDING_ROUTE, route_valid, "$.route_events"),
        ("structured_demo_summary_trace_relations",
         ValidationCategory.SCHEDULER_RELATION, relations_valid, "$.summary"),
    )
    specs = [_spec(code, category, valid, path)
             for code, category, valid, path in results]
    for field, collection in (
        ("trace_digest", trace_value),
        ("cell_trace_digest", cell_value),
    ):
        calculated = _canonical_digest(collection)
        specs.append(
            _spec(
                f"structured_demo_{field}",
                ValidationCategory.DIGEST,
                calculated is not None and calculated == root.get(field),
                f"$.{field}",
            )
        )
    return tuple(specs)


def _self_test_specs(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    object_fields = _SELF_TEST[7:]
    field_types = _types(
        root,
        integers=("check_count",),
        strings=("schema", "kind", "version", "milestone", "status"),
        objects=("checks",) + object_fields,
    )
    checks = root.get("checks")
    checks_valid = isinstance(checks, Mapping) and all(
        isinstance(key, str) and isinstance(value, bool)
        for key, value in checks.items()
    )
    count_valid = (
        checks_valid and root.get("check_count") == len(checks) == 41
    )
    all_passed = checks_valid and len(checks) == 41 and all(checks.values())
    qualification_valid = all_passed and root.get("status") == "PASS"
    return (
        _spec("structured_output_envelope", ValidationCategory.IDENTITY,
              _envelope(root, "self_test"), "$"),
        _spec("structured_self_test_required_fields",
              ValidationCategory.STRUCTURE, _has_fields(root, _SELF_TEST), "$"),
        _spec("structured_self_test_field_types", ValidationCategory.TYPE,
              field_types, "$"),
        _spec("structured_self_test_check_registry",
              ValidationCategory.QUALIFICATION_EVIDENCE, count_valid,
              "$.checks"),
        _spec("structured_self_test_qualification_result",
              ValidationCategory.QUALIFICATION_EVIDENCE,
              qualification_valid, "$.status"),
    )


def _parsed(dispatched: DispatchedArtifact) -> ParsedJsonArtifact:
    if not isinstance(dispatched, DispatchedArtifact):
        raise StructuredOutputValidationError(
            "dispatched must be a DispatchedArtifact"
        )
    record = dispatched.compatibility_record
    if (
        dispatched.classification is not ArtifactClassification.JSON
        or dispatched.registration.status is not RegistrationStatus.REGISTERED
        or record is None
        or record.identifier != _SCHEMA
        or record.artifact_kind not in _KINDS
        or not isinstance(dispatched.parsed_artifact, ParsedJsonArtifact)
    ):
        raise StructuredOutputValidationError(
            "artifact is not registered structured output v1.7.0"
        )
    return dispatched.parsed_artifact


@dataclass(frozen=True, slots=True)
class StructuredOutputValidation:
    """Immutable result for one structured-output artifact."""

    dispatched_artifact: DispatchedArtifact
    kind: str
    check_specs: tuple[ValidationCheckSpec, ...]
    full_trace_present: bool

    def __post_init__(self) -> None:
        parsed = _parsed(self.dispatched_artifact)
        if self.kind not in _KINDS or parsed.declared_kind != self.kind:
            raise StructuredOutputValidationError(
                "kind must match the registered artifact"
            )
        if not self.check_specs or any(
            not isinstance(spec, ValidationCheckSpec) for spec in self.check_specs
        ):
            raise StructuredOutputValidationError(
                "check_specs must contain validation specifications"
            )
        if not isinstance(self.full_trace_present, bool):
            raise StructuredOutputValidationError(
                "full_trace_present must be a boolean"
            )

    @property
    def valid(self) -> bool:
        """Return whether every mandatory check passed."""

        return all(
            not spec.mandatory or spec.outcome is CheckOutcome.PASS
            for spec in self.check_specs
        )


def validate_structured_output(
    dispatched: DispatchedArtifact,
) -> StructuredOutputValidation:
    """Validate one registered structured-output artifact read-only."""

    parsed = _parsed(dispatched)
    kind = parsed.declared_kind
    if kind == "demo":
        specs = _demo_specs(parsed.root)
        full_trace = all(
            field in parsed.root for field in ("trace", "cell_trace", "route_events")
        )
    elif kind == "self_test":
        specs = _self_test_specs(parsed.root)
        full_trace = False
    else:
        raise StructuredOutputValidationError("unsupported structured-output kind")
    return StructuredOutputValidation(dispatched, kind, specs, full_trace)
