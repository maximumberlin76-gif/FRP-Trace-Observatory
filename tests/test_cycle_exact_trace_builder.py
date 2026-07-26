"""Tests for audited cycle-exact Trace Explorer dataset construction."""

from __future__ import annotations

import json
import unittest

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
from transition_visualizer import (
    CanonicalTernaryState,
    RequestAcceptanceStatus,
    RouteStatus,
    SchedulerMode,
    SchedulerState,
)


_SCHEMA = "frp.m15.cycle_exact_reference_trace.v1.7.0"
_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_STATE_ENCODING = "frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0"
_ALL_MODES = (
    ObservatoryMode.ARTIFACT_AUDITOR,
    ObservatoryMode.TRACE_EXPLORER,
    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
)


def _configuration() -> dict[str, object]:
    return {
        "cells": 2,
        "request_lanes": 1,
        "scheduler": "free",
        "steps": 4,
    }


def _preload() -> dict[str, object]:
    return {
        "cells": 2,
        "frequency_current_q16": [65536, 65536],
        "frequency_target_q16": [65536, 65536],
        "gamma_noise_state_q16": [0, 0],
        "gamma_noise_target_q16": [0, 0],
        "heat_q16": [0, 0],
        "phase_words": [0, 0],
        "scheduler": "free",
        "seed": 1,
        "states": [-1, 1],
        "states_packed_hex": "7",
    }


def _trace_row(
    tick: int,
    *,
    packed: int,
    packed_hex: str,
    human_state: str,
    request_valid: int,
    request_target: int,
    pending_routes: int,
    cumulative_routes: int,
) -> dict[str, object]:
    return {
        "C_minus_P_q16": 65536,
        "C_q16": 65536,
        "P_q16": 0,
        "actual_direct_events": 0,
        "auto_targets_enable": 1,
        "changes": 1,
        "gamma_noise_target_q16": [0, 0],
        "gamma_noise_update_valid": 0,
        "global_phase_coherence_q30": 1073741824,
        "heat_global_q16": 0,
        "neutral_routed_events": cumulative_routes,
        "neutralized_conflicts": cumulative_routes,
        "pending_route_count": pending_routes,
        "prevented_direct_events": cumulative_routes,
        "queue_overflow_events": 0,
        "request_cell_ids": [0],
        "request_target_states": [request_target],
        "request_valid_mask": request_valid,
        "requested_direct_events": cumulative_routes,
        "reserved_state_events": 0,
        "reset_n": 1,
        "scheduler_mode": 0,
        "scheduler_state": 0,
        "scheduler_state_name": "free",
        "states_human": human_state,
        "states_packed": packed,
        "states_packed_hex": packed_hex,
        "switch_load_q16": 32768,
        "tick": tick,
    }


def _trace() -> list[dict[str, object]]:
    return [
        _trace_row(
            0,
            packed=4,
            packed_hex="4",
            human_state="NP",
            request_valid=1,
            request_target=1,
            pending_routes=1,
            cumulative_routes=1,
        ),
        _trace_row(
            1,
            packed=5,
            packed_hex="5",
            human_state="PP",
            request_valid=0,
            request_target=1,
            pending_routes=0,
            cumulative_routes=1,
        ),
        _trace_row(
            2,
            packed=4,
            packed_hex="4",
            human_state="NP",
            request_valid=1,
            request_target=3,
            pending_routes=1,
            cumulative_routes=2,
        ),
        _trace_row(
            3,
            packed=7,
            packed_hex="7",
            human_state="MP",
            request_valid=0,
            request_target=3,
            pending_routes=0,
            cumulative_routes=2,
        ),
    ]


def _route_events() -> list[dict[str, object]]:
    return [
        {
            "cell_id": 0,
            "ready_tick": 1,
            "route_status": "pending",
            "target_state": 1,
            "tick": 0,
        },
        {
            "cell_id": 0,
            "ready_tick": 1,
            "route_status": "applied",
            "target_state": 1,
            "tick": 1,
        },
        {
            "cell_id": 0,
            "ready_tick": 3,
            "route_status": "pending",
            "target_state": -1,
            "tick": 2,
        },
        {
            "cell_id": 0,
            "ready_tick": 3,
            "route_status": "applied",
            "target_state": -1,
            "tick": 3,
        },
    ]


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
        "neutral_routed_events": 2,
        "neutralized_conflicts": 2,
        "pending_route_count_final": 0,
        "prevented_direct_events": 2,
        "queue_overflow_events": 0,
        "request_lanes": 1,
        "requested_direct_events": 2,
        "reserved_state_events": 0,
        "scheduler": "free",
        "scheduler_counts": {"free": 4},
        "scheduler_counts_valid": True,
        "steps": 4,
        "switch_load_peak": 0.5,
        "switch_load_peak_q16": 32768,
        "ticks_recorded": 4,
        "transition_fraction": 0.25,
        "version": _VERSION,
    }


def _cycle_root() -> dict[str, object]:
    return {
        "configuration": _configuration(),
        "kind": "cycle_exact_reference_trace",
        "milestone": _MILESTONE,
        "preload": _preload(),
        "route_events": _route_events(),
        "schema": _SCHEMA,
        "summary": _summary(),
        "trace": _trace(),
        "version": _VERSION,
    }


def _source_bytes(root: dict[str, object]) -> bytes:
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
    root: dict[str, object],
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


class CycleExactTraceBuilderTests(unittest.TestCase):
    def test_builds_complete_cycle_exact_dataset(self) -> None:
        source, dispatched, report = _audit(
            _cycle_root(),
            "cycle-exact-reference-trace.json",
        )

        dataset = build_trace_dataset(dispatched, report)
        snapshots = dataset.state_snapshots or ()
        requests = dataset.request_bundles or ()
        schedulers = dataset.scheduler_snapshots or ()
        routes = dataset.route_events or ()

        self.assertIsInstance(dataset, TraceDataset)
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertIs(
            dataset.trace_family,
            TraceFamily.CYCLE_EXACT_REFERENCE,
        )
        self.assertEqual(dataset.schema_identifier, _SCHEMA)
        self.assertEqual(
            dataset.kind,
            "cycle_exact_reference_trace",
        )
        self.assertIsNone(dataset.format_identifier)
        self.assertEqual(
            dataset.state_encoding_binding,
            _STATE_ENCODING,
        )
        self.assertIs(
            dataset.ordering_validation,
            OrderingValidationStatus.VALIDATED_SOURCE_ORDER,
        )
        self.assertIs(
            dataset.completeness_status,
            TraceCompletenessStatus.REQUIRED_COLLECTIONS_PRESENT,
        )
        self.assertEqual(dataset.eligible_modes, _ALL_MODES)
        self.assertEqual(len(dataset.tick_records or ()), 4)
        self.assertEqual(len(snapshots), 4)
        self.assertEqual(len(requests), 4)
        self.assertEqual(len(schedulers), 4)
        self.assertEqual(len(routes), 4)
        self.assertEqual(
            len(dataset.transition_telemetry_records or ()),
            4,
        )
        self.assertEqual(len(dataset.telemetry_snapshots or ()), 4)
        self.assertEqual(
            len(dataset.event_counter_snapshots or ()),
            4,
        )
        self.assertEqual(len(dataset.source_references), 9)
        self.assertIsNone(dataset.cell_records)
        self.assertIsNone(dataset.transitions)

        self.assertEqual(
            tuple(
                state.canonical_state
                for state in snapshots[0].cell_states or ()
            ),
            (
                CanonicalTernaryState.NEUTRAL,
                CanonicalTernaryState.POSITIVE,
            ),
        )
        self.assertEqual(
            tuple(
                state.canonical_state
                for state in snapshots[-1].cell_states or ()
            ),
            (
                CanonicalTernaryState.NEGATIVE,
                CanonicalTernaryState.POSITIVE,
            ),
        )
        self.assertIs(
            requests[0].request_lanes[0].acceptance_status,
            RequestAcceptanceStatus.NOT_RECORDED,
        )
        self.assertIs(
            requests[1].request_lanes[0].acceptance_status,
            RequestAcceptanceStatus.NOT_APPLICABLE,
        )
        self.assertTrue(
            all(
                snapshot.mode is not None
                and snapshot.mode.normalized_value
                is SchedulerMode.FREE
                and snapshot.state.normalized_value
                is SchedulerState.FREE
                for snapshot in schedulers
            )
        )
        self.assertEqual(
            tuple(event.route_status for event in routes),
            (
                RouteStatus.PENDING,
                RouteStatus.APPLIED,
                RouteStatus.PENDING,
                RouteStatus.APPLIED,
            ),
        )
        self.assertEqual(
            tuple(event.canonical_target_state for event in routes),
            (
                CanonicalTernaryState.POSITIVE,
                CanonicalTernaryState.POSITIVE,
                CanonicalTernaryState.NEGATIVE,
                CanonicalTernaryState.NEGATIVE,
            ),
        )
        self.assertTrue(
            all(
                reference.source_sha256 == source.content_sha256
                for reference in dataset.source_references
            )
        )
        self.assertEqual(source.raw_bytes, _source_bytes(_cycle_root()))
        self.assertTrue(source.verify_integrity())

    def test_cycle_exact_build_is_deterministic(self) -> None:
        _, dispatched, report = _audit(
            _cycle_root(),
            "deterministic-cycle-exact.json",
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

    def test_rejects_invalid_trace_order(self) -> None:
        root = _cycle_root()
        trace = _trace()
        root["trace"] = [trace[0], trace[2], trace[1], trace[3]]
        _, dispatched, report = _audit(
            root,
            "invalid-cycle-order.json",
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

    def test_rejects_human_state_contradiction(self) -> None:
        root = _cycle_root()
        trace = _trace()
        trace[0]["states_human"] = "MP"
        root["trace"] = trace
        _, dispatched, report = _audit(
            root,
            "contradictory-human-state.json",
        )

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        with self.assertRaisesRegex(
            TraceBuilderError,
            "states_human contradicts states_packed",
        ):
            build_trace_dataset(dispatched, report)

    def test_rejects_packed_hex_contradiction(self) -> None:
        root = _cycle_root()
        trace = _trace()
        trace[0]["states_packed_hex"] = "5"
        root["trace"] = trace
        _, dispatched, report = _audit(
            root,
            "contradictory-packed-hex.json",
        )

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        with self.assertRaisesRegex(
            TraceBuilderError,
            "states_packed_hex contradicts states_packed",
        ):
            build_trace_dataset(dispatched, report)


if __name__ == "__main__":
    unittest.main()
