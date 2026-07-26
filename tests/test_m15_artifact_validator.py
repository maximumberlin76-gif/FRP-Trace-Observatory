"""Tests for read-only registered M15 JSON artifact validation."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError, replace

from artifact_auditor.audit_report import CheckOutcome
from artifact_auditor.m15_artifact_validator import (
    M15ArtifactValidation,
    M15ArtifactValidationError,
    validate_m15_artifact,
)
from parsers.artifact_dispatch import (
    DispatchedArtifact,
    dispatch_artifact,
)
from parsers.source_artifact import capture_source_bytes


_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_KINDS = tuple(
    """
    fixed_point_interface_profile
    balanced_ternary_hardware_encoding_map
    quantized_reference_shadow_model
    cycle_exact_reference_trace
    rtl_comparison_vector_package
    systemverilog_testbench_interface_map
    synthesizable_rtl_reference_core
    rtl_assertion_correlation_harness
    reference_rtl_equivalence_report
    qualification_closure_manifest
    """.split()
)
_FIXED, _ENCODING, _SHADOW, _TRACE, _VECTORS = _KINDS[:5]
_SV_MAP, _RTL_CORE, _HARNESS, _EQUIVALENCE, _CLOSURE = _KINDS[5:]
_DIGEST = "0" * 64
_MODES = ("free", "7/1", "1/7")
_STATES = ("free", "balance", "commit", "excite", "neutralize")
_COMMON_CODES = (
    "m15_artifact_envelope",
    "m15_artifact_top_level_fields",
    "m15_artifact_envelope_types",
)
_SEMANTIC_FIELDS = tuple(
    """
    state_sequence_match scheduler_sequence_match
    neutral_route_sequence_match C_minus_P_sign_match
    boundary_order_match
    """.split()
)
_REPLAY_FIELDS = tuple(
    """
    shadow_replay_state_match shadow_replay_scheduler_match
    shadow_replay_pending_route_match shadow_replay_counter_match
    shadow_replay_trace_match shadow_replay_cell_trace_match
    """.split()
)
_VECTOR_NAMES = tuple(
    sorted(
        """
        frp_m15_kernel_vectors.vec
        frp_m15_pending_routes.trace
        frp_m15_scheduler_free_vectors.vec
        frp_m15_scheduler_7_1_vectors.vec
        frp_m15_scheduler_1_7_vectors.vec
        frp_m15_full_correlation_vectors.vec
        frp_m15_cell_trace.vec
        frp_m15_reference_preload.json
        frp_m15_trig_lut_q30.vec
        frp_m15_sha256_manifest.json
        """.split()
    )
)
_RTL_FILES = tuple(
    """
    rtl/m15/frp_m15_types_pkg.sv rtl/m15/frp_m15_fixed_point_pkg.sv
    rtl/m15/frp_m15_trig_lut_pkg.sv rtl/m15/frp_m15_scheduler.sv
    rtl/m15/frp_m15_transition_core.sv
    rtl/m15/frp_m15_neutral_route_queue.sv
    rtl/m15/frp_m15_delay_dynamics.sv rtl/m15/frp_m15_thermal_field.sv
    rtl/m15/frp_m15_gamma_drift.sv
    rtl/m15/frp_m15_hierarchical_coupling.sv
    rtl/m15/frp_m15_multiscale_coherence.sv
    rtl/m15/frp_m15_stability_telemetry.sv rtl/m15/frp_m15_top.sv
    """.split()
)
_ASSERTIONS = tuple(
    (
        "valid balanced ternary encoding|reserved-state exclusion|"
        "direct polarity transition exclusion|active neutral route insertion|"
        "target application after ready tick|actual_direct_events = 0|"
        "transition-limit enforcement|scheduler sequence|"
        "scheduler count consistency|"
        "phase topology fixed-point normalization|"
        "thermal topology fixed-point normalization|"
        "deterministic trace tick count|exact cycle-output match"
    ).split("|")
)
_TRACE_FIELDS = tuple(
    """
    tick reset_n scheduler_mode scheduler_state scheduler_state_name
    auto_targets_enable request_valid_mask request_cell_ids
    request_target_states gamma_noise_update_valid gamma_noise_target_q16
    states_packed states_packed_hex states_human pending_route_count
    switch_load_q16 heat_global_q16 global_phase_coherence_q30 C_q16 P_q16
    C_minus_P_q16 requested_direct_events prevented_direct_events
    neutral_routed_events neutralized_conflicts actual_direct_events
    reserved_state_events queue_overflow_events changes
    """.split()
)


def _boundary() -> dict[str, object]:
    return {
        "release": "FRP v1.6.0",
        "release_status": "PUBLISHED",
        "preserved_kernel": {
            "balanced_ternary_states": [-1, 0, 1],
            "active_neutral_state": 0,
            "tick_separated_neutral_routing": True,
            "scheduler_modes": list(_MODES),
        },
    }


def _configuration() -> dict[str, object]:
    return {
        "cells": 2,
        "hierarchy_depth": 1,
        "request_lanes": 1,
        "seed": 76,
        "steps": 1,
        "scheduler": "free",
    }


def _preload() -> dict[str, object]:
    result: dict[str, object] = {
        "cells": 2,
        "scheduler": "free",
        "states_packed_hex": "0x0",
    }
    for field in (
        "states phase_words frequency_target_q16 frequency_current_q16 "
        "heat_q16 gamma_noise_state_q16 gamma_noise_target_q16"
    ).split():
        result[field] = [0, 0]
    return result


def _summary() -> dict[str, object]:
    return {
        "cells": 2,
        "steps": 1,
        "ticks_recorded": 1,
        "scheduler": "free",
        "scheduler_counts": {"free": 1},
        "scheduler_counts_valid": True,
        "balanced_ternary_state_domain": True,
        "reserved_state_events": 0,
        "actual_direct_events": 0,
        "queue_overflow_events": 0,
        "fixed_point_topology_sum_exact": True,
        "fixed_point_thermal_sum_exact": True,
    }


def _manifest() -> dict[str, object]:
    return {
        "file_count": 10,
        "files": [
            {"name": name, "size_bytes": 1, "sha256": _DIGEST}
            for name in _VECTOR_NAMES
        ],
    }


def _matches(fields: tuple[str, ...]) -> dict[str, float]:
    return dict.fromkeys(fields, 1.0)


def _labels(prefix: str, count: int) -> list[str]:
    return [f"{prefix}_{index}" for index in range(count)]


def _replay() -> dict[str, object]:
    result: dict[str, object] = _matches(_REPLAY_FIELDS)
    result.update(trace_digest=_DIGEST, cell_trace_digest=_DIGEST)
    return result


def _trace_row() -> dict[str, object]:
    row: dict[str, object] = dict.fromkeys(_TRACE_FIELDS, 0)
    row.update(
        scheduler_state_name="free",
        request_cell_ids=[0],
        request_target_states=[0],
        gamma_noise_target_q16=[0],
        states_packed_hex="0x0",
        states_human="NN",
    )
    return row


def _base(kind: str) -> dict[str, object]:
    return {
        "schema": f"frp.m15.{kind}.v{_VERSION}",
        "kind": kind,
        "version": _VERSION,
        "milestone": _MILESTONE,
    }


def _artifact(kind: str) -> dict[str, object]:
    root = _base(kind)
    if kind == _FIXED:
        root.update(
            inherited_boundary=_boundary(),
            profile={
                "general_scalar": {
                    "name": "S32Q16",
                    "width": 32,
                    "fraction_bits": 16,
                    "scale": 1 << 16,
                },
                "normalized_coefficient": {
                    "name": "S32Q30",
                    "fraction_bits": 30,
                    "scale": 1 << 30,
                },
                "phase": {
                    "name": "PHASE_U32",
                    "modulus": 1 << 32,
                },
                "trigonometric_profile": {
                    "table_entries": 4096,
                    "address_bits": 12,
                    "output_type": "S32Q30",
                    "sin_lut_sha256": (
                        "acb0dfe2c00998840f9ca00f9ef9e3b46011db6c745faa"
                        "59a9db13c4121cc57b"
                    ),
                },
                "exponential_profile": {
                    "table_entries": 4096,
                    "input_domain_q16": [0, 524288],
                    "output_type": "S32Q30",
                    "exp_lut_sha256": (
                        "350499727643d6eb7e123a0c2256ed05a7d76f316e4181"
                        "acce170101ae78bf0a"
                    ),
                },
            },
            topology_fixed_point_profile=[{"aggregate_weight_q30": 1 << 30}],
            thermal_fixed_point_profile=[{"aggregate_weight_q30": 1 << 30}],
            fixed_point_topology_sum_exact=True,
            fixed_point_thermal_sum_exact=True,
        )
    elif kind == _ENCODING:
        root.update(
            inherited_boundary=_boundary(),
            state_encoding=[
                {"state": -1, "code": "11", "integer_code": 3},
                {"state": 0, "code": "00", "integer_code": 0},
                {"state": 1, "code": "01", "integer_code": 1},
            ],
            reserved_state_code={"code": "10", "integer_code": 2},
            packed_state_vector={
                "configured_cells": 2,
                "bits_per_cell": 2,
                "configured_width_bits": 4,
            },
            request_interface={"cell_id_width": 1, "request_lanes": 1},
            scheduler_mode_encoding=[
                {"name": name, "code": code}
                for code, name in enumerate(_MODES)
            ],
            scheduler_state_encoding=[
                {"name": name, "code": code}
                for code, name in enumerate(_STATES)
            ],
        )
    elif kind == _SHADOW:
        root.update(
            inherited_boundary=_boundary(),
            execution_model="stateful fixed-point feedback",
            configuration=_configuration(),
            numeric_profile={
                "scalar": "S32Q16",
                "unit": "S32Q30",
                "phase": "PHASE_U32",
                "gamma": "GAMMA_S32",
            },
            preload=_preload(),
            summary=_summary(),
            trace_digest=_DIGEST,
            cell_trace_digest=_DIGEST,
        )
    elif kind == _TRACE:
        root.update(
            configuration=_configuration(),
            preload=_preload(),
            summary=_summary(),
            trace=[_trace_row()],
            route_events=[],
        )
    elif kind == _VECTORS:
        root.update(
            vector_classes=[
                "kernel_transition_vectors",
                "scheduler_vectors",
                "full_correlation_vectors",
            ],
            manifest=_manifest(),
            deterministic_package_digest=_DIGEST,
        )
    elif kind == _SV_MAP:
        root.update(
            parameters={
                "NUM_CELLS": 16,
                "HIERARCHY_DEPTH": 4,
                "REQUEST_LANES": 4,
                "CELL_ID_WIDTH": 4,
                "STATE_VECTOR_WIDTH": 32,
                "SCALAR_WIDTH": 32,
                "PHASE_WIDTH": 32,
            },
            execution_inputs=_labels("execution", 7),
            verification_stimulus_inputs=_labels("stimulus", 3),
            comparison_outputs=_labels("comparison", 14),
            vector_replay_order=_labels("vector", 9),
        )
    elif kind == _RTL_CORE:
        root.update(
            kernel_requirements={
                "balanced_ternary_states": [-1, 0, 1],
                "reserved_state_code": "2'b10",
                "actual_direct_events": 0,
                "tick_separated_neutral_routing": True,
                "scheduler_modes": list(_MODES),
            },
            planned_rtl_files=list(_RTL_FILES),
            exact_tick_execution_order=(
                ["resolve scheduler state"]
                + [f"stage {index}" for index in range(24)]
                + ["capture post-tick outputs"]
            ),
        )
    elif kind == _HARNESS:
        root.update(
            assertion_count=13,
            assertions=list(_ASSERTIONS),
            direct_transition_rules=["rule 0", "rule 1", "rule 2"],
            scheduler_modes=list(_MODES),
            exact_comparison_rule=(
                "actual integer field == expected integer field"
            ),
        )
    elif kind == _EQUIVALENCE:
        root.update(
            floating_reference_to_quantized_shadow=_matches(_SEMANTIC_FIELDS),
            quantized_shadow_deterministic_replay=_replay(),
            rtl_exact_integer_comparison_contract={
                "comparison_rule": "actual == expected",
                "required_domains": _labels("domain", 9),
            },
        )
    elif kind == _CLOSURE:
        root.update(
            artifact_layers=list(_KINDS),
            checks=dict.fromkeys(_labels("artifact", 10), True),
            semantic_correlation=_matches(_SEMANTIC_FIELDS),
            exact_shadow_replay=_replay(),
            vector_manifest=_manifest(),
            status="PASS",
        )
    else:
        raise AssertionError("unsupported test artifact kind")
    return root


def _dispatch(root: dict[str, object]) -> DispatchedArtifact:
    text = json.dumps(root, ensure_ascii=False, separators=(",", ":"))
    source = capture_source_bytes(
        (text + "\n").encode(),
        source_filename="m15_artifact.json",
        source_path="published/m15_artifact.json",
    )
    return dispatch_artifact(source)


def _failed(result: M15ArtifactValidation) -> tuple[str, ...]:
    return tuple(
        spec.check_code for spec in result.check_specs
        if spec.outcome is CheckOutcome.FAIL
    )


def _break_specialized_check(root: dict[str, object], kind: str) -> str:
    if kind == _FIXED:
        root["profile"]["general_scalar"]["name"] = "S31Q16"
        return "m15_fixed_point_domains"
    if kind == _ENCODING:
        root["state_encoding"][2]["state"] = 2
        return "m15_ternary_encoding"
    if kind == _SHADOW:
        root["trace_digest"] = "invalid"
        return "m15_shadow_digest_syntax"
    if kind == _TRACE:
        root["trace"][0]["changes"] = 2
        return "m15_trace_transition_capacity"
    if kind == _VECTORS:
        root["deterministic_package_digest"] = "invalid"
        return "m15_package_digest_syntax"
    if kind == _SV_MAP:
        root["parameters"]["NUM_CELLS"] = 8
        return "m15_systemverilog_parameters"
    if kind == _RTL_CORE:
        root["planned_rtl_files"].pop()
        return "m15_rtl_file_set"
    if kind == _HARNESS:
        root["assertion_count"] = 12
        return "m15_assertion_registry"
    if kind == _EQUIVALENCE:
        record = root["floating_reference_to_quantized_shadow"]
        record["state_sequence_match"] = 0.0
        return "m15_semantic_correlation"
    root["status"] = "REVIEW"
    return "m15_closure_result"


class M15ArtifactValidatorTests(unittest.TestCase):
    def test_all_registered_kinds_pass_without_source_mutation(self) -> None:
        counts = dict(zip(_KINDS, (7, 7, 8, 9, 7, 5, 6, 5, 6, 7)))
        for kind in _KINDS:
            with self.subTest(kind=kind):
                dispatched = _dispatch(_artifact(kind))
                raw = dispatched.source_artifact.raw_bytes
                result = validate_m15_artifact(dispatched)
                self.assertEqual(result.kind, kind)
                self.assertEqual(len(result.check_specs), counts[kind])
                self.assertEqual(_failed(result), ())
                self.assertTrue(result.valid)
                self.assertEqual(
                    tuple(s.check_code for s in result.check_specs[:3]),
                    _COMMON_CODES,
                )
                self.assertEqual(dispatched.source_artifact.raw_bytes, raw)

    def test_each_kind_exposes_a_specialized_failure(self) -> None:
        for kind in _KINDS:
            with self.subTest(kind=kind):
                root = _artifact(kind)
                expected = _break_specialized_check(root, kind)
                result = validate_m15_artifact(_dispatch(root))
                self.assertEqual(_failed(result), (expected,))

    def test_common_contract_failures_remain_distinct(self) -> None:
        cases = (
            ("version", "1.7.1", ("m15_artifact_envelope",)),
            ("extra", True, ("m15_artifact_top_level_fields",)),
            ("milestone", 15, (
                "m15_artifact_envelope",
                "m15_artifact_envelope_types",
            )),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                root = _artifact(_VECTORS)
                root[field] = value
                result = validate_m15_artifact(_dispatch(root))
                self.assertEqual(_failed(result), expected)

    def test_routing_and_result_invariants_are_enforced(self) -> None:
        wrong = _artifact(_FIXED)
        wrong["kind"] = "demo"
        text = capture_source_bytes(
            b"not json\n", source_filename="artifact.txt"
        )
        for value in ("invalid", _dispatch(wrong), dispatch_artifact(text)):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(M15ArtifactValidationError):
                    validate_m15_artifact(value)

        result = validate_m15_artifact(_dispatch(_artifact(_FIXED)))
        with self.assertRaises(M15ArtifactValidationError):
            replace(result, kind=_ENCODING)
        with self.assertRaises(M15ArtifactValidationError):
            replace(result, check_specs=())
        with self.assertRaises(FrozenInstanceError):
            setattr(result, "kind", _ENCODING)
