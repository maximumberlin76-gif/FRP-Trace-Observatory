"""Tests for deterministic audited Trace Explorer dataset construction."""

from __future__ import annotations

import hashlib
import json
import unittest
from collections.abc import Mapping

from artifact_auditor.audit_report import AuditReport, ValidationStatus
from artifact_auditor.auditor import audit_dispatched_artifact
from parsers.artifact_dispatch import DispatchedArtifact, dispatch_artifact
from parsers.source_artifact import SourceArtifact, capture_source_bytes
from schemas.registry import ObservatoryMode
from trace_explorer import (
    OrderingValidationStatus,
    TraceBuilderError,
    TraceCompletenessStatus,
    TraceDataset,
    TraceFamily,
    build_trace_dataset,
)
from transition_visualizer.transition_model import (
    CanonicalTernaryState,
)


_SCHEMA = "frp.structured_output.v1.7.0"
_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_ZERO_DIGEST = "0" * 64


def _canonical_digest(value: object) -> str:
    text = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _configuration() -> dict[str, object]:
    return {
        "ambient_heat": 0.05,
        "cells": 2,
        "coupling_nominal": 0.28,
        "delay_alpha": 0.3,
        "fractal_alpha": 0.7,
        "gamma_nominal": 0.9424777960769379,
        "request_lanes": 1,
        "scheduler": "free",
        "seed": 76,
        "steps": 2,
        "thermal_beta": 1.2,
        "thermal_diffusion_gain": 0.035,
        "thermal_hard_limit": 0.9,
        "thermal_soft_limit": 0.22,
        "thermal_time_constant": 14.0,
        "transition_fraction": 0.25,
    }


def _kernel() -> dict[str, object]:
    return {
        "active_neutral_state": 0,
        "actual_direct_events_target": 0,
        "balanced_ternary_states": [-1, 0, 1],
        "neutral_routes": [
            "-1 -> 0 -> 1",
            "1 -> 0 -> -1",
        ],
        "scheduler_modes": ["free", "7/1", "1/7"],
    }


def _hardware_profile() -> dict[str, object]:
    return {
        "gamma": "GAMMA_S32",
        "phase": "PHASE_U32",
        "scalar": "S32Q16",
        "state_encoding": {
            "-1": "11",
            "0": "00",
            "1": "01",
            "reserved": "10",
        },
        "unit": "S32Q30",
    }


def _trace_row(
    tick: int,
    *,
    packed: int,
    packed_hex: str,
    human: str,
) -> dict[str, object]:
    return {
        "C_minus_P_q16": 65536,
        "C_q16": 131072,
        "P_q16": 65536,
        "actual_direct_events": 0,
        "auto_targets_enable": 0,
        "changes": 0,
        "gamma_noise_target_q16": [0, 0],
        "gamma_noise_update_valid": 0,
        "global_phase_coherence_q30": 1073741824,
        "heat_global_q16": 0,
        "neutral_routed_events": 0,
        "neutralized_conflicts": 0,
        "pending_route_count": 0,
        "prevented_direct_events": 0,
        "queue_overflow_events": 0,
        "request_cell_ids": [0],
        "request_target_states": [0],
        "request_valid_mask": 0,
        "requested_direct_events": 0,
        "reserved_state_events": 0,
        "reset_n": 1,
        "scheduler_mode": 0,
        "scheduler_state": 0,
        "scheduler_state_name": "free",
        "states_human": human,
        "states_packed": packed,
        "states_packed_hex": packed_hex,
        "switch_load_q16": 0,
        "tick": tick,
    }


def _cell_row(
    tick: int,
    cell_id: int,
    state_code: int,
) -> dict[str, int]:
    return {
        "cell_id": cell_id,
        "coupling_field_q16": 0,
        "frequency_current_q16": 65536,
        "frequency_lag_q16": 0,
        "frequency_target_q16": 65536,
        "gamma_effective_word": 644245094,
        "gamma_noise_state_q16": 0,
        "generated_power_q16": 0,
        "heat_q16": 0,
        "phase_word": 0,
        "state_code": state_code,
        "thermal_node_factor_q30": 1073741824,
        "thermal_overload_q16": 0,
        "tick": tick,
    }


def _summary() -> dict[str, object]:
    return {
        "C_minus_P_final": 1,
        "C_minus_P_final_q16": 65536,
        "C_minus_P_min": 1,
        "C_minus_P_min_q16": 65536,
        "actual_direct_events": 0,
        "balanced_ternary_state_domain": True,
        "boundary_detected": False,
        "cells": 2,
        "fixed_point_thermal_sum_exact": True,
        "fixed_point_topology_sum_exact": True,
        "hierarchy_depth": 1,
        "milestone": _MILESTONE,
        "neutral_route_queue_capacity": 2,
        "neutral_routed_events": 0,
        "neutralized_conflicts": 0,
        "pending_route_count_final": 0,
        "prevented_direct_events": 0,
        "queue_overflow_events": 0,
        "request_lanes": 1,
        "requested_direct_events": 0,
        "reserved_state_events": 0,
        "scheduler": "free",
        "scheduler_counts": {"free": 2},
        "scheduler_counts_valid": True,
        "steps": 2,
        "switch_load_peak": 0,
        "switch_load_peak_q16": 0,
        "ticks_recorded": 2,
        "transition_fraction": 0.25,
        "version": _VERSION,
    }


def _demo_root(
    *,
    include_trace: bool,
) -> dict[str, object]:
    root: dict[str, object] = {
        "configuration": _configuration(),
        "hardware_profile": _hardware_profile(),
        "kernel": _kernel(),
        "kind": "demo",
        "milestone": _MILESTONE,
        "preload_digest": _ZERO_DIGEST,
        "schema": _SCHEMA,
        "summary": _summary(),
        "trace_digest": _ZERO_DIGEST,
        "cell_trace_digest": _ZERO_DIGEST,
        "version": _VERSION,
    }
    if not include_trace:
        return root

    trace = [
        _trace_row(
            0,
            packed=4,
            packed_hex="4",
            human="NP",
        ),
        _trace_row(
            1,
            packed=1,
            packed_hex="1",
            human="PN",
        ),
    ]
    cell_trace = [
        _cell_row(0, 0, 0),
        _cell_row(0, 1, 1),
        _cell_row(1, 0, 1),
        _cell_row(1, 1, 0),
    ]
    root["trace"] = trace
    root["cell_trace"] = cell_trace
    root["route_events"] = []
    root["trace_digest"] = _canonical_digest(trace)
    root["cell_trace_digest"] = _canonical_digest(cell_trace)
    return root


def _source_bytes(root: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            root,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _audit(
    root: Mapping[str, object],
    filename: str,
) -> tuple[SourceArtifact, DispatchedArtifact, AuditReport]:
    source = capture_source_bytes(
        _source_bytes(root),
        source_filename=filename,
        source_path=f"tests/generated/{filename}",
    )
    dispatched = dispatch_artifact(source)
    report = audit_dispatched_artifact(
        dispatched,
        registry_revision="test-registry",
    )
    return source, dispatched, report


class TraceBuilderTests(unittest.TestCase):
    def test_builds_complete_structured_trace(self) -> None:
        source, dispatched, report = _audit(
            _demo_root(include_trace=True),
            "structured-demo.json",
        )

        dataset = build_trace_dataset(dispatched, report)

        self.assertIsInstance(dataset, TraceDataset)
        self.assertIs(
            dataset.trace_family,
            TraceFamily.STRUCTURED_PROCESSOR_TICK,
        )
        self.assertIs(
            dataset.ordering_validation,
            OrderingValidationStatus.VALIDATED_SOURCE_ORDER,
        )
        self.assertIs(
            dataset.completeness_status,
            TraceCompletenessStatus.REQUIRED_COLLECTIONS_PRESENT,
        )
        self.assertEqual(
            dataset.eligible_modes,
            (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TRACE_EXPLORER,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            ),
        )
        self.assertEqual(len(dataset.tick_records or ()), 2)
        self.assertEqual(len(dataset.cell_records or ()), 4)
        self.assertEqual(len(dataset.state_snapshots or ()), 2)
        self.assertEqual(len(dataset.request_bundles or ()), 2)
        self.assertEqual(len(dataset.scheduler_snapshots or ()), 2)
        self.assertEqual(len(dataset.source_references), 7)
        self.assertTrue(
            all(
                reference.source_sha256 == source.content_sha256
                for reference in dataset.source_references
            )
        )

        states = dataset.state_snapshots or ()
        self.assertEqual(
            tuple(
                value.canonical_state
                for value in states[0].cell_states
            ),
            (
                CanonicalTernaryState.NEUTRAL,
                CanonicalTernaryState.POSITIVE,
            ),
        )
        self.assertTrue(source.verify_integrity())

    def test_build_is_deterministic_for_one_audit(self) -> None:
        _, dispatched, report = _audit(
            _demo_root(include_trace=True),
            "deterministic-demo.json",
        )

        first = build_trace_dataset(dispatched, report)
        second = build_trace_dataset(dispatched, report)

        self.assertEqual(first, second)
        self.assertEqual(
            first.trace_dataset_id,
            second.trace_dataset_id,
        )
        self.assertEqual(
            first.normalized_artifact_id,
            second.normalized_artifact_id,
        )

    def test_minimal_demo_is_auditor_only(self) -> None:
        _, dispatched, report = _audit(
            _demo_root(include_trace=False),
            "minimal-demo.json",
        )

        dataset = build_trace_dataset(dispatched, report)

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertIsNone(dataset.tick_records)
        self.assertIsNone(dataset.cell_records)
        self.assertIs(
            dataset.ordering_validation,
            OrderingValidationStatus.NOT_EVALUATED,
        )
        self.assertIs(
            dataset.completeness_status,
            TraceCompletenessStatus.REQUIRED_COLLECTIONS_MISSING,
        )
        self.assertEqual(
            dataset.eligible_modes,
            (ObservatoryMode.ARTIFACT_AUDITOR,),
        )

    def test_rejects_invalid_audit_result(self) -> None:
        root = _demo_root(include_trace=True)
        root["trace_digest"] = _ZERO_DIGEST
        _, dispatched, report = _audit(
            root,
            "invalid-digest-demo.json",
        )

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )
        with self.assertRaisesRegex(
            TraceBuilderError,
            "requires a valid audit report",
        ):
            build_trace_dataset(dispatched, report)

    def test_rejects_report_from_another_source(self) -> None:
        _, dispatched, _ = _audit(
            _demo_root(include_trace=True),
            "complete-demo.json",
        )
        _, _, other_report = _audit(
            _demo_root(include_trace=False),
            "other-demo.json",
        )

        with self.assertRaisesRegex(
            TraceBuilderError,
            "does not describe the dispatched source",
        ):
            build_trace_dataset(dispatched, other_report)


if __name__ == "__main__":
    unittest.main()
