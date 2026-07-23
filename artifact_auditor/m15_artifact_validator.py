"""Read-only validation for registered FRP M15 JSON artifacts.

Each artifact kind keeps its own checks inside the M15 implementation-mapping
contour. The validator does not execute artifact content, regenerate producer
outputs, inspect SystemVerilog, or replace published FRP values.
"""

from __future__ import annotations

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
    "M15ArtifactValidation",
    "M15ArtifactValidationError",
    "validate_m15_artifact",
]


_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_KINDS = (
    "fixed_point_interface_profile",
    "balanced_ternary_hardware_encoding_map",
    "quantized_reference_shadow_model",
    "cycle_exact_reference_trace",
    "rtl_comparison_vector_package",
    "systemverilog_testbench_interface_map",
    "synthesizable_rtl_reference_core",
    "rtl_assertion_correlation_harness",
    "reference_rtl_equivalence_report",
    "qualification_closure_manifest",
)
_COMMON = frozenset({"schema", "kind", "version", "milestone"})


def _fields(text: str) -> frozenset[str]:
    return frozenset(text.split())


_REQUIRED = {
    _KINDS[0]: _COMMON | _fields(
        "inherited_boundary profile topology_fixed_point_profile "
        "thermal_fixed_point_profile fixed_point_topology_sum_exact "
        "fixed_point_thermal_sum_exact"
    ),
    _KINDS[1]: _COMMON | _fields(
        "inherited_boundary state_encoding reserved_state_code "
        "packed_state_vector request_interface scheduler_mode_encoding "
        "scheduler_state_encoding"
    ),
    _KINDS[2]: _COMMON | _fields(
        "inherited_boundary execution_model configuration numeric_profile "
        "preload summary trace_digest cell_trace_digest"
    ),
    _KINDS[3]: _COMMON | _fields(
        "configuration preload summary trace route_events"
    ),
    _KINDS[4]: _COMMON | _fields(
        "vector_classes manifest deterministic_package_digest"
    ),
    _KINDS[5]: _COMMON | _fields(
        "parameters execution_inputs verification_stimulus_inputs "
        "comparison_outputs vector_replay_order"
    ),
    _KINDS[6]: _COMMON | _fields(
        "kernel_requirements planned_rtl_files exact_tick_execution_order"
    ),
    _KINDS[7]: _COMMON | _fields(
        "assertion_count assertions direct_transition_rules scheduler_modes "
        "exact_comparison_rule"
    ),
    _KINDS[8]: _COMMON | _fields(
        "floating_reference_to_quantized_shadow "
        "quantized_shadow_deterministic_replay "
        "rtl_exact_integer_comparison_contract"
    ),
    _KINDS[9]: _COMMON | _fields(
        "artifact_layers checks semantic_correlation exact_shadow_replay "
        "vector_manifest status"
    ),
}
_OPTIONAL = {_KINDS[4]: frozenset({"written_files"})}
_HEX = frozenset("0123456789abcdef")
_SCHEDULER_MODES = ("free", "7/1", "1/7")
_VECTOR_NAMES = tuple(
    sorted(
        (
            "frp_m15_kernel_vectors.vec",
            "frp_m15_pending_routes.trace",
            "frp_m15_scheduler_free_vectors.vec",
            "frp_m15_scheduler_7_1_vectors.vec",
            "frp_m15_scheduler_1_7_vectors.vec",
            "frp_m15_full_correlation_vectors.vec",
            "frp_m15_cell_trace.vec",
            "frp_m15_reference_preload.json",
            "frp_m15_trig_lut_q30.vec",
            "frp_m15_sha256_manifest.json",
        )
    )
)
_TRACE_FIELDS = _fields(
    "tick reset_n scheduler_mode scheduler_state scheduler_state_name "
    "auto_targets_enable request_valid_mask request_cell_ids "
    "request_target_states gamma_noise_update_valid gamma_noise_target_q16 "
    "states_packed states_packed_hex states_human pending_route_count "
    "switch_load_q16 heat_global_q16 global_phase_coherence_q30 C_q16 P_q16 "
    "C_minus_P_q16 requested_direct_events prevented_direct_events "
    "neutral_routed_events neutralized_conflicts actual_direct_events "
    "reserved_state_events queue_overflow_events changes"
)
_RTL_FILES = (
    "rtl/m15/frp_m15_types_pkg.sv",
    "rtl/m15/frp_m15_fixed_point_pkg.sv",
    "rtl/m15/frp_m15_trig_lut_pkg.sv",
    "rtl/m15/frp_m15_scheduler.sv",
    "rtl/m15/frp_m15_transition_core.sv",
    "rtl/m15/frp_m15_neutral_route_queue.sv",
    "rtl/m15/frp_m15_delay_dynamics.sv",
    "rtl/m15/frp_m15_thermal_field.sv",
    "rtl/m15/frp_m15_gamma_drift.sv",
    "rtl/m15/frp_m15_hierarchical_coupling.sv",
    "rtl/m15/frp_m15_multiscale_coherence.sv",
    "rtl/m15/frp_m15_stability_telemetry.sv",
    "rtl/m15/frp_m15_top.sv",
)
_ASSERTIONS = (
    "valid balanced ternary encoding",
    "reserved-state exclusion",
    "direct polarity transition exclusion",
    "active neutral route insertion",
    "target application after ready tick",
    "actual_direct_events = 0",
    "transition-limit enforcement",
    "scheduler sequence",
    "scheduler count consistency",
    "phase topology fixed-point normalization",
    "thermal topology fixed-point normalization",
    "deterministic trace tick count",
    "exact cycle-output match",
)
_SEMANTIC_MATCHES = _fields(
    "state_sequence_match scheduler_sequence_match neutral_route_sequence_match "
    "C_minus_P_sign_match boundary_order_match"
)
_REPLAY_MATCHES = _fields(
    "shadow_replay_state_match shadow_replay_scheduler_match "
    "shadow_replay_pending_route_match shadow_replay_counter_match "
    "shadow_replay_trace_match shadow_replay_cell_trace_match"
)


class M15ArtifactValidationError(ValueError):
    """Raised when a validator input violates routing invariants."""


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _number(value: object) -> bool:
    return _integer(value) or isinstance(value, Decimal)


def _object(value: object) -> Mapping[str, JsonValue] | None:
    return value if isinstance(value, Mapping) else None


def _array(value: object) -> tuple[JsonValue, ...] | None:
    return value if isinstance(value, tuple) else None


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _spec(
    code: str,
    category: ValidationCategory,
    valid: bool,
    path: str,
) -> ValidationCheckSpec:
    relation = "matches" if valid else "does not match"
    return ValidationCheckSpec(
        check_code=code,
        category=category,
        outcome=CheckOutcome.PASS if valid else CheckOutcome.FAIL,
        message=(
            f"The {code.replace('_', ' ')} {relation} the registered "
            "upstream contract."
        ),
        source_locations=(SourceLocation(json_path=path),),
        upstream_rule_reference="docs/output_schema.md",
    )


def _parsed(
    dispatched: DispatchedArtifact,
) -> tuple[ParsedJsonArtifact, str]:
    if not isinstance(dispatched, DispatchedArtifact):
        raise M15ArtifactValidationError(
            "dispatched must be a DispatchedArtifact"
        )
    parsed = dispatched.parsed_artifact
    record = dispatched.compatibility_record
    kind = parsed.declared_kind if isinstance(parsed, ParsedJsonArtifact) else None
    expected_schema = f"frp.m15.{kind}.v{_VERSION}"
    if (
        dispatched.classification is not ArtifactClassification.JSON
        or dispatched.registration.status
        is not RegistrationStatus.REGISTERED
        or not isinstance(parsed, ParsedJsonArtifact)
        or record is None
        or kind not in _KINDS
        or record.artifact_kind != kind
        or record.identifier != expected_schema
    ):
        raise M15ArtifactValidationError(
            "artifact is not a registered M15 JSON artifact"
        )
    return parsed, kind


def _boundary(value: object) -> bool:
    boundary = _object(value)
    kernel = _object(boundary.get("preserved_kernel")) if boundary else None
    return bool(
        boundary
        and boundary.get("release") == "FRP v1.6.0"
        and boundary.get("release_status") == "PUBLISHED"
        and kernel
        and kernel.get("balanced_ternary_states") == (-1, 0, 1)
        and kernel.get("active_neutral_state") == 0
        and kernel.get("tick_separated_neutral_routing") is True
        and kernel.get("scheduler_modes") == _SCHEDULER_MODES
    )


def _aggregate_exact(value: object) -> bool:
    rows = _array(value)
    weights = (
        tuple(row.get("aggregate_weight_q30") for row in rows)
        if rows and all(isinstance(row, Mapping) for row in rows)
        else ()
    )
    return bool(
        weights
        and all(_integer(weight) for weight in weights)
        and sum(weights) == 1 << 30
    )


def _fixed(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    profile = _object(root.get("profile"))
    scalar = _object(profile.get("general_scalar")) if profile else None
    unit = _object(profile.get("normalized_coefficient")) if profile else None
    phase = _object(profile.get("phase")) if profile else None
    trig = _object(profile.get("trigonometric_profile")) if profile else None
    exp = _object(profile.get("exponential_profile")) if profile else None
    domains = bool(
        scalar
        and unit
        and phase
        and scalar.get("name") == "S32Q16"
        and scalar.get("width") == 32
        and scalar.get("fraction_bits") == 16
        and scalar.get("scale") == 1 << 16
        and unit.get("name") == "S32Q30"
        and unit.get("fraction_bits") == 30
        and unit.get("scale") == 1 << 30
        and phase.get("name") == "PHASE_U32"
        and phase.get("modulus") == 1 << 32
    )
    lookup = bool(
        trig
        and exp
        and trig.get("table_entries") == 4096
        and trig.get("address_bits") == 12
        and trig.get("output_type") == "S32Q30"
        and trig.get("sin_lut_sha256")
        == "acb0dfe2c00998840f9ca00f9ef9e3b46011db6c745faa59a9db13c4121cc57b"
        and exp.get("table_entries") == 4096
        and exp.get("input_domain_q16") == (0, 524288)
        and exp.get("output_type") == "S32Q30"
        and exp.get("exp_lut_sha256")
        == "350499727643d6eb7e123a0c2256ed05a7d76f316e4181acce170101ae78bf0a"
    )
    exact = (
        root.get("fixed_point_topology_sum_exact") is True
        and root.get("fixed_point_thermal_sum_exact") is True
        and _aggregate_exact(root.get("topology_fixed_point_profile"))
        and _aggregate_exact(root.get("thermal_fixed_point_profile"))
    )
    return (
        _spec(
            "m15_inherited_boundary",
            ValidationCategory.IDENTITY,
            _boundary(root.get("inherited_boundary")),
            "$.inherited_boundary",
        ),
        _spec(
            "m15_fixed_point_domains",
            ValidationCategory.ALLOWED_VALUE,
            domains,
            "$.profile",
        ),
        _spec(
            "m15_lookup_profiles",
            ValidationCategory.DIGEST,
            lookup,
            "$.profile",
        ),
        _spec(
            "m15_fixed_point_sum_relations",
            ValidationCategory.INVARIANT_VECTOR,
            exact,
            "$",
        ),
    )


def _encoding(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    packed = _object(root.get("packed_state_vector"))
    request = _object(root.get("request_interface"))
    cells = packed.get("configured_cells") if packed else None
    width = packed.get("configured_width_bits") if packed else None
    ternary = (
        root.get("state_encoding")
        == (
            {"state": -1, "code": "11", "integer_code": 3},
            {"state": 0, "code": "00", "integer_code": 0},
            {"state": 1, "code": "01", "integer_code": 1},
        )
        and root.get("reserved_state_code")
        == {"code": "10", "integer_code": 2}
    )
    dimensions = bool(
        packed
        and request
        and _integer(cells)
        and cells >= 2
        and packed.get("bits_per_cell") == 2
        and width == 2 * cells
        and request.get("cell_id_width") == (cells - 1).bit_length()
        and _integer(request.get("request_lanes"))
        and request.get("request_lanes") > 0
    )
    scheduler = (
        root.get("scheduler_mode_encoding")
        == tuple(
            {"name": name, "code": code}
            for name, code in zip(_SCHEDULER_MODES, range(3), strict=True)
        )
        and root.get("scheduler_state_encoding")
        == tuple(
            {"name": name, "code": code}
            for code, name in enumerate(
                ("free", "balance", "commit", "excite", "neutralize")
            )
        )
    )
    return (
        _spec(
            "m15_inherited_boundary",
            ValidationCategory.IDENTITY,
            _boundary(root.get("inherited_boundary")),
            "$.inherited_boundary",
        ),
        _spec(
            "m15_ternary_encoding",
            ValidationCategory.TERNARY_DOMAIN,
            ternary,
            "$.state_encoding",
        ),
        _spec(
            "m15_encoding_dimensions",
            ValidationCategory.ALLOWED_VALUE,
            dimensions,
            "$.packed_state_vector",
        ),
        _spec(
            "m15_scheduler_encoding",
            ValidationCategory.SCHEDULER_RELATION,
            scheduler,
            "$",
        ),
    )


def _preload(
    value: object,
    config: Mapping[str, JsonValue] | None,
) -> bool:
    preload = _object(value)
    if not preload or not config:
        return False
    cells = config.get("cells")
    arrays = (
        "states",
        "phase_words",
        "frequency_target_q16",
        "frequency_current_q16",
        "heat_q16",
        "gamma_noise_state_q16",
        "gamma_noise_target_q16",
    )
    return bool(
        _integer(cells)
        and cells > 0
        and preload.get("cells") == cells
        and preload.get("scheduler") == config.get("scheduler")
        and all(
            isinstance(preload.get(field), tuple)
            and len(preload[field]) == cells
            for field in arrays
        )
        and all(state in {-1, 0, 1} for state in preload["states"])
        and isinstance(preload.get("states_packed_hex"), str)
    )


def _summary(
    value: object,
    config: Mapping[str, JsonValue] | None,
) -> bool:
    summary = _object(value)
    return bool(
        summary
        and config
        and summary.get("cells") == config.get("cells")
        and summary.get("steps") == config.get("steps")
        and summary.get("ticks_recorded") == config.get("steps")
        and summary.get("scheduler") == config.get("scheduler")
        and summary.get("scheduler_counts_valid") is True
        and summary.get("balanced_ternary_state_domain") is True
        and summary.get("reserved_state_events") == 0
        and summary.get("actual_direct_events") == 0
        and summary.get("queue_overflow_events") == 0
        and summary.get("fixed_point_topology_sum_exact") is True
        and summary.get("fixed_point_thermal_sum_exact") is True
    )


def _shadow(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    config = _object(root.get("configuration"))
    numeric = _object(root.get("numeric_profile"))
    values = bool(
        config
        and numeric
        and root.get("execution_model") == "stateful fixed-point feedback"
        and dict(numeric)
        == {
            "scalar": "S32Q16",
            "unit": "S32Q30",
            "phase": "PHASE_U32",
            "gamma": "GAMMA_S32",
        }
        and config.get("scheduler") in _SCHEDULER_MODES
        and all(
            _integer(config.get(field))
            for field in (
                "cells",
                "hierarchy_depth",
                "request_lanes",
                "seed",
                "steps",
            )
        )
    )
    return (
        _spec(
            "m15_inherited_boundary",
            ValidationCategory.IDENTITY,
            _boundary(root.get("inherited_boundary")),
            "$.inherited_boundary",
        ),
        _spec(
            "m15_shadow_configuration",
            ValidationCategory.ALLOWED_VALUE,
            values,
            "$.configuration",
        ),
        _spec(
            "m15_shadow_preload",
            ValidationCategory.TERNARY_DOMAIN,
            _preload(root.get("preload"), config),
            "$.preload",
        ),
        _spec(
            "m15_shadow_summary",
            ValidationCategory.INVARIANT_VECTOR,
            _summary(root.get("summary"), config),
            "$.summary",
        ),
        _spec(
            "m15_shadow_digest_syntax",
            ValidationCategory.DIGEST,
            _digest(root.get("trace_digest"))
            and _digest(root.get("cell_trace_digest")),
            "$",
        ),
    )


def _trace(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    config = _object(root.get("configuration"))
    rows = _array(root.get("trace"))
    routes = _array(root.get("route_events"))
    steps = config.get("steps") if config else None
    lanes = config.get("request_lanes") if config else None
    shape = bool(
        rows is not None
        and all(
            isinstance(row, Mapping) and _TRACE_FIELDS <= set(row)
            for row in rows
        )
        and _integer(steps)
        and len(rows) == steps
        and tuple(row.get("tick") for row in rows) == tuple(range(steps))
    )
    modes = {"free": 0, "7/1": 1, "1/7": 2}
    states = {
        "free": 0,
        "balance": 1,
        "commit": 2,
        "excite": 3,
        "neutralize": 4,
    }
    scheduler = bool(
        rows is not None
        and config
        and config.get("scheduler") in modes
        and all(isinstance(row, Mapping) for row in rows)
        and all(
            row.get("scheduler_mode") == modes[config["scheduler"]]
            and states.get(row.get("scheduler_state_name"))
            == row.get("scheduler_state")
            for row in rows
            if isinstance(row, Mapping)
        )
    )
    transition = bool(
        rows is not None
        and _integer(lanes)
        and lanes > 0
        and all(
            isinstance(row, Mapping)
            and set(row.get("states_human", "")) <= {"M", "N", "P"}
            and all(
                code in {0, 1, 3}
                for code in row.get("request_target_states", ())
            )
            and _integer(row.get("changes"))
            and 0 <= row["changes"] <= lanes
            and row.get("actual_direct_events") == 0
            and row.get("reserved_state_events") == 0
            for row in rows
        )
    )
    route_valid = bool(
        routes is not None
        and all(isinstance(row, Mapping) for row in routes)
        and all(_integer(row.get("tick")) for row in routes)
        and tuple(row.get("tick") for row in routes)
        == tuple(sorted(row.get("tick") for row in routes))
        and all(
            row.get("target_state") in {-1, 1}
            and row.get("route_status") in {"pending", "applied"}
            and _integer(row.get("ready_tick"))
            and (
                row.get("route_status") != "applied"
                or row.get("tick") >= row.get("ready_tick")
            )
            for row in routes
        )
    )
    summary = _object(root.get("summary"))
    relations = bool(
        rows is not None
        and summary
        and all(isinstance(row, Mapping) for row in rows)
        and _summary(summary, config)
        and dict(summary.get("scheduler_counts", {}))
        == dict(
            Counter(row.get("scheduler_state_name") for row in rows)
        )
    )
    return (
        _spec(
            "m15_trace_preload",
            ValidationCategory.TERNARY_DOMAIN,
            _preload(root.get("preload"), config),
            "$.preload",
        ),
        _spec(
            "m15_trace_shape_and_order",
            ValidationCategory.ORDERING,
            shape,
            "$.trace",
        ),
        _spec(
            "m15_trace_scheduler_relation",
            ValidationCategory.SCHEDULER_RELATION,
            scheduler,
            "$.trace",
        ),
        _spec(
            "m15_trace_transition_capacity",
            ValidationCategory.TRANSITION_CAPACITY,
            transition,
            "$.trace",
        ),
        _spec(
            "m15_trace_pending_routes",
            ValidationCategory.PENDING_ROUTE,
            route_valid,
            "$.route_events",
        ),
        _spec(
            "m15_trace_summary_relations",
            ValidationCategory.INVARIANT_VECTOR,
            relations,
            "$.summary",
        ),
    )


def _manifest(value: object) -> bool:
    manifest = _object(value)
    files = _array(manifest.get("files")) if manifest else None
    return bool(
        manifest
        and manifest.get("file_count") == 10
        and files is not None
        and len(files) == 10
        and tuple(
            row.get("name")
            for row in files
            if isinstance(row, Mapping)
        )
        == _VECTOR_NAMES
        and all(
            isinstance(row, Mapping)
            and set(row) == {"name", "size_bytes", "sha256"}
            and _integer(row.get("size_bytes"))
            and row.get("size_bytes") > 0
            and _digest(row.get("sha256"))
            for row in files
        )
    )


def _vectors(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    optional = root.get("written_files")
    written = optional is None or (
        isinstance(optional, tuple)
        and all(isinstance(path, str) and path for path in optional)
    )
    return (
        _spec(
            "m15_vector_classes",
            ValidationCategory.ALLOWED_VALUE,
            root.get("vector_classes")
            == (
                "kernel_transition_vectors",
                "scheduler_vectors",
                "full_correlation_vectors",
            ),
            "$.vector_classes",
        ),
        _spec(
            "m15_vector_manifest",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _manifest(root.get("manifest")),
            "$.manifest",
        ),
        _spec(
            "m15_package_digest_syntax",
            ValidationCategory.DIGEST,
            _digest(root.get("deterministic_package_digest")),
            "$.deterministic_package_digest",
        ),
        _spec(
            "m15_written_file_paths",
            ValidationCategory.TYPE,
            written,
            "$.written_files",
        ),
    )


def _sv_map(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    parameters = _object(root.get("parameters"))
    expected = {
        "NUM_CELLS": 16,
        "HIERARCHY_DEPTH": 4,
        "REQUEST_LANES": 4,
        "CELL_ID_WIDTH": 4,
        "STATE_VECTOR_WIDTH": 32,
        "SCALAR_WIDTH": 32,
        "PHASE_WIDTH": 32,
    }
    arrays = (
        ("execution_inputs", 7),
        ("verification_stimulus_inputs", 3),
        ("comparison_outputs", 14),
        ("vector_replay_order", 9),
    )
    interface = all(
        isinstance(root.get(field), tuple)
        and len(root[field]) == count
        and all(isinstance(item, str) for item in root[field])
        for field, count in arrays
    )
    return (
        _spec(
            "m15_systemverilog_parameters",
            ValidationCategory.ALLOWED_VALUE,
            parameters is not None and dict(parameters) == expected,
            "$.parameters",
        ),
        _spec(
            "m15_systemverilog_interface_lists",
            ValidationCategory.STRUCTURE,
            interface,
            "$",
        ),
    )


def _rtl_core(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    kernel = _object(root.get("kernel_requirements"))
    order = _array(root.get("exact_tick_execution_order"))
    kernel_valid = bool(
        kernel
        and kernel.get("balanced_ternary_states") == (-1, 0, 1)
        and kernel.get("reserved_state_code") == "2'b10"
        and kernel.get("actual_direct_events") == 0
        and kernel.get("tick_separated_neutral_routing") is True
        and kernel.get("scheduler_modes") == _SCHEDULER_MODES
    )
    order_valid = bool(
        order
        and len(order) == 26
        and all(isinstance(stage, str) for stage in order)
        and len(set(order)) == 26
        and order[0] == "resolve scheduler state"
        and order[-1] == "capture post-tick outputs"
    )
    return (
        _spec(
            "m15_rtl_kernel_requirements",
            ValidationCategory.TERNARY_DOMAIN,
            kernel_valid,
            "$.kernel_requirements",
        ),
        _spec(
            "m15_rtl_file_set",
            ValidationCategory.STRUCTURE,
            root.get("planned_rtl_files") == _RTL_FILES,
            "$.planned_rtl_files",
        ),
        _spec(
            "m15_tick_execution_order",
            ValidationCategory.ORDERING,
            order_valid,
            "$.exact_tick_execution_order",
        ),
    )


def _harness(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    rules = _array(root.get("direct_transition_rules"))
    assertions = (
        root.get("assertion_count") == 13
        and root.get("assertions") == _ASSERTIONS
    )
    contract = (
        rules is not None
        and len(rules) == 3
        and all(isinstance(rule, str) for rule in rules)
        and root.get("scheduler_modes") == _SCHEDULER_MODES
        and root.get("exact_comparison_rule")
        == "actual integer field == expected integer field"
    )
    return (
        _spec(
            "m15_assertion_registry",
            ValidationCategory.INVARIANT_VECTOR,
            assertions,
            "$.assertions",
        ),
        _spec(
            "m15_assertion_contract",
            ValidationCategory.ALLOWED_VALUE,
            contract,
            "$",
        ),
    )


def _matches(value: object, fields: frozenset[str]) -> bool:
    record = _object(value)
    return bool(
        record
        and fields <= set(record)
        and all(
            _number(record[field])
            and record[field] == Decimal("1.0")
            for field in fields
        )
    )


def _replay(value: object) -> bool:
    record = _object(value)
    return bool(
        _matches(value, _REPLAY_MATCHES)
        and record
        and _digest(record.get("trace_digest"))
        and _digest(record.get("cell_trace_digest"))
    )


def _equivalence(
    root: Mapping[str, JsonValue],
) -> tuple[ValidationCheckSpec, ...]:
    contract = _object(root.get("rtl_exact_integer_comparison_contract"))
    contract_valid = bool(
        contract
        and contract.get("comparison_rule") == "actual == expected"
        and isinstance(contract.get("required_domains"), tuple)
        and len(contract["required_domains"]) == 9
        and all(
            isinstance(item, str)
            for item in contract["required_domains"]
        )
    )
    return (
        _spec(
            "m15_semantic_correlation",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _matches(
                root.get("floating_reference_to_quantized_shadow"),
                _SEMANTIC_MATCHES,
            ),
            "$.floating_reference_to_quantized_shadow",
        ),
        _spec(
            "m15_exact_shadow_replay",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _replay(
                root.get("quantized_shadow_deterministic_replay")
            ),
            "$.quantized_shadow_deterministic_replay",
        ),
        _spec(
            "m15_rtl_comparison_contract",
            ValidationCategory.ALLOWED_VALUE,
            contract_valid,
            "$.rtl_exact_integer_comparison_contract",
        ),
    )


def _closure(root: Mapping[str, JsonValue]) -> tuple[ValidationCheckSpec, ...]:
    checks = _object(root.get("checks"))
    closure = bool(
        root.get("status") == "PASS"
        and checks
        and len(checks) == 10
        and all(
            isinstance(value, bool) and value
            for value in checks.values()
        )
        and root.get("artifact_layers") == _KINDS
    )
    return (
        _spec(
            "m15_closure_result",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            closure,
            "$",
        ),
        _spec(
            "m15_closure_vector_manifest",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _manifest(root.get("vector_manifest")),
            "$.vector_manifest",
        ),
        _spec(
            "m15_closure_semantic_correlation",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _matches(
                root.get("semantic_correlation"),
                _SEMANTIC_MATCHES,
            ),
            "$.semantic_correlation",
        ),
        _spec(
            "m15_closure_exact_replay",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _replay(root.get("exact_shadow_replay")),
            "$.exact_shadow_replay",
        ),
    )


_VALIDATORS = {
    _KINDS[0]: _fixed,
    _KINDS[1]: _encoding,
    _KINDS[2]: _shadow,
    _KINDS[3]: _trace,
    _KINDS[4]: _vectors,
    _KINDS[5]: _sv_map,
    _KINDS[6]: _rtl_core,
    _KINDS[7]: _harness,
    _KINDS[8]: _equivalence,
    _KINDS[9]: _closure,
}


def _common_specs(
    root: Mapping[str, JsonValue],
    kind: str,
) -> tuple[ValidationCheckSpec, ...]:
    schema = f"frp.m15.{kind}.v{_VERSION}"
    keys = frozenset(root)
    allowed = _REQUIRED[kind] | _OPTIONAL.get(kind, frozenset())
    return (
        _spec(
            "m15_artifact_envelope",
            ValidationCategory.IDENTITY,
            root.get("schema") == schema
            and root.get("kind") == kind
            and root.get("version") == _VERSION
            and root.get("milestone") == _MILESTONE,
            "$",
        ),
        _spec(
            "m15_artifact_top_level_fields",
            ValidationCategory.STRUCTURE,
            _REQUIRED[kind] <= keys <= allowed,
            "$",
        ),
        _spec(
            "m15_artifact_envelope_types",
            ValidationCategory.TYPE,
            all(
                isinstance(root.get(field), str)
                for field in _COMMON
            ),
            "$",
        ),
    )


@dataclass(frozen=True, slots=True)
class M15ArtifactValidation:
    """Immutable validation result for one registered M15 JSON artifact."""

    dispatched_artifact: DispatchedArtifact
    kind: str
    check_specs: tuple[ValidationCheckSpec, ...]

    def __post_init__(self) -> None:
        parsed, parsed_kind = _parsed(self.dispatched_artifact)
        if self.kind != parsed_kind or parsed.declared_kind != self.kind:
            raise M15ArtifactValidationError(
                "kind must match the registered artifact"
            )
        if not self.check_specs or any(
            not isinstance(spec, ValidationCheckSpec)
            for spec in self.check_specs
        ):
            raise M15ArtifactValidationError(
                "check_specs must contain validation specifications"
            )

    @property
    def valid(self) -> bool:
        """Return whether every mandatory check passed."""

        return all(
            not spec.mandatory or spec.outcome is CheckOutcome.PASS
            for spec in self.check_specs
        )


def validate_m15_artifact(
    dispatched: DispatchedArtifact,
) -> M15ArtifactValidation:
    """Validate one registered M15 JSON artifact without mutation."""

    parsed, kind = _parsed(dispatched)
    specs = _common_specs(parsed.root, kind) + _VALIDATORS[kind](parsed.root)
    return M15ArtifactValidation(dispatched, kind, specs)
