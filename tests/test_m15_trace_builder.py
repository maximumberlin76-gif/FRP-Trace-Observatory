"""Tests for audited M15 vector Trace Explorer dataset construction."""

from __future__ import annotations

import json
import unittest
from collections.abc import Sequence

from artifact_auditor.audit_report import AuditReport, ValidationStatus
from artifact_auditor.auditor import audit_dispatched_artifact
from parsers.artifact_dispatch import DispatchedArtifact, dispatch_artifact
from parsers.m15_vector import (
    CELL_TRACE_COLUMNS,
    M15_VECTOR_FORMAT_VERSION,
    PRIMARY_VECTOR_COLUMNS,
    ROUTE_TRACE_COLUMNS,
    M15VectorTraceKind,
)
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
    RouteStatus,
)


_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_STATE_ENCODING = "frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0"
_PRIMARY_CASES = (
    (M15VectorTraceKind.KERNEL_TRANSITION_VECTORS, "free"),
    (M15VectorTraceKind.SCHEDULER_FREE_VECTORS, "free"),
    (M15VectorTraceKind.SCHEDULER_7_1_VECTORS, "7/1"),
    (M15VectorTraceKind.SCHEDULER_1_7_VECTORS, "1/7"),
    (M15VectorTraceKind.FULL_CORRELATION_VECTORS, "free"),
)
_ALL_MODES = (
    ObservatoryMode.ARTIFACT_AUDITOR,
    ObservatoryMode.TRACE_EXPLORER,
    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
)


def _vector_bytes(
    trace_kind: M15VectorTraceKind,
    columns: tuple[str, ...],
    rows: Sequence[Sequence[str]],
    *,
    scheduler_mode: str,
    trace_steps: int,
) -> bytes:
    metadata: dict[str, object] = {
        "format_version": M15_VECTOR_FORMAT_VERSION,
        "frp_version": _VERSION,
        "milestone": _MILESTONE,
        "trace_kind": trace_kind.value,
        "cells": 2,
        "hierarchy_depth": 1,
        "request_lanes": 1,
        "transition_fraction": 0.25,
        "scheduler_mode": scheduler_mode,
        "fractal_alpha": 0.7,
        "thermal_beta": 1.2,
        "scalar_format": "S32Q16",
        "unit_format": "S32Q30",
        "phase_format": "PHASE_U32",
        "seed": 76,
        "trace_steps": trace_steps,
        "column_definition": list(columns),
    }
    lines = [
        (
            f"# {key}="
            + json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        for key, value in metadata.items()
    ]
    lines.append("# " + " | ".join(columns))
    lines.extend(" | ".join(row) for row in rows)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _scheduler_state(scheduler_mode: str, tick: int) -> int:
    if scheduler_mode == "7/1":
        return 2 if (tick + 1) % 8 == 0 else 1
    if scheduler_mode == "1/7":
        return 3 if tick % 8 == 0 else 4
    return 0


def _primary_rows(
    trace_kind: M15VectorTraceKind,
    scheduler_mode: str,
    trace_steps: int,
) -> tuple[tuple[str, ...], ...]:
    scheduler_code = {
        "free": 0,
        "7/1": 1,
        "1/7": 2,
    }[scheduler_mode]
    auto_targets = int(
        trace_kind
        is M15VectorTraceKind.FULL_CORRELATION_VECTORS
    )
    return tuple(
        (
            f"{tick:08d}",
            "1",
            f"{scheduler_code:X}",
            f"{_scheduler_state(scheduler_mode, tick):X}",
            str(auto_targets),
            "1" if tick % 2 else "0",
            f"{tick % 2:X}",
            "1" if tick % 2 == 0 else "3",
            "0",
            "0,0",
            "1" if tick % 2 == 0 else "C",
            "0",
            "0",
            "0",
            "1073741824",
            "65536",
            "0",
            "65536",
            "0",
            "0",
            "0",
            "0",
            "0",
        )
        for tick in range(trace_steps)
    )


def _primary_vector_bytes(
    trace_kind: M15VectorTraceKind,
    scheduler_mode: str,
) -> bytes:
    trace_steps = (
        2
        if trace_kind
        is M15VectorTraceKind.FULL_CORRELATION_VECTORS
        else 16
    )
    return _vector_bytes(
        trace_kind,
        PRIMARY_VECTOR_COLUMNS,
        _primary_rows(
            trace_kind,
            scheduler_mode,
            trace_steps,
        ),
        scheduler_mode=scheduler_mode,
        trace_steps=trace_steps,
    )


def _cell_rows() -> tuple[tuple[str, ...], ...]:
    state_codes = (
        (0, 0, "0"),
        (0, 1, "1"),
        (1, 0, "3"),
        (1, 1, "0"),
    )
    return tuple(
        (
            f"{tick:08d}",
            str(cell_id),
            state_code,
            f"{tick * 2 + cell_id:08X}",
            "65536",
            "65536",
            "0",
            "0",
            "0",
            "0",
            "0",
            "644245094",
            "1073741824",
            "0",
        )
        for tick, cell_id, state_code in state_codes
    )


def _cell_vector_bytes() -> bytes:
    return _vector_bytes(
        M15VectorTraceKind.CELL_TRACE,
        CELL_TRACE_COLUMNS,
        _cell_rows(),
        scheduler_mode="free",
        trace_steps=2,
    )


def _route_rows() -> tuple[tuple[str, ...], ...]:
    return (
        ("00000000", "0", "0", "1", "1", "pending"),
        ("00000001", "1", "0", "1", "1", "applied"),
        ("00000002", "2", "1", "3", "3", "pending"),
        ("00000003", "3", "1", "3", "3", "applied"),
    )


def _route_vector_bytes() -> bytes:
    return _vector_bytes(
        M15VectorTraceKind.PENDING_ROUTES,
        ROUTE_TRACE_COLUMNS,
        _route_rows(),
        scheduler_mode="free",
        trace_steps=16,
    )


def _audit(
    raw_bytes: bytes,
    filename: str,
) -> tuple[SourceArtifact, DispatchedArtifact, AuditReport]:
    source = capture_source_bytes(
        raw_bytes,
        source_filename=filename,
        source_path=f"tests/generated/{filename}",
    )
    dispatched = dispatch_artifact(source)
    report = audit_dispatched_artifact(
        dispatched,
        registry_revision="test-registry",
    )
    return source, dispatched, report


class M15TraceBuilderTests(unittest.TestCase):
    def test_builds_all_primary_vector_kinds(self) -> None:
        for trace_kind, scheduler_mode in _PRIMARY_CASES:
            with self.subTest(trace_kind=trace_kind.value):
                source, dispatched, report = _audit(
                    _primary_vector_bytes(
                        trace_kind,
                        scheduler_mode,
                    ),
                    f"{trace_kind.value}.vec",
                )

                dataset = build_trace_dataset(dispatched, report)
                expected_steps = (
                    2
                    if trace_kind
                    is M15VectorTraceKind.FULL_CORRELATION_VECTORS
                    else 16
                )

                self.assertIsInstance(dataset, TraceDataset)
                self.assertIs(
                    report.overall_status,
                    ValidationStatus.RECOGNIZED_VALID,
                )
                self.assertIs(
                    dataset.trace_family,
                    TraceFamily.M15_PRIMARY_VECTOR,
                )
                self.assertEqual(dataset.kind, trace_kind.value)
                self.assertEqual(
                    dataset.format_identifier,
                    M15_VECTOR_FORMAT_VERSION,
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
                self.assertEqual(
                    dataset.state_encoding_binding,
                    _STATE_ENCODING,
                )
                self.assertEqual(
                    len(dataset.tick_records or ()),
                    expected_steps,
                )
                self.assertEqual(
                    len(dataset.state_snapshots or ()),
                    expected_steps,
                )
                self.assertEqual(
                    len(dataset.request_bundles or ()),
                    expected_steps,
                )
                self.assertEqual(
                    len(dataset.scheduler_snapshots or ()),
                    expected_steps,
                )
                self.assertEqual(
                    len(dataset.source_references),
                    expected_steps + 1,
                )

                first_snapshot = (dataset.state_snapshots or ())[0]
                self.assertEqual(
                    tuple(
                        state.canonical_state
                        for state in first_snapshot.cell_states or ()
                    ),
                    (
                        CanonicalTernaryState.POSITIVE,
                        CanonicalTernaryState.NEUTRAL,
                    ),
                )
                self.assertTrue(
                    all(
                        reference.source_sha256
                        == source.content_sha256
                        for reference in dataset.source_references
                    )
                )
                self.assertTrue(source.verify_integrity())

    def test_builds_per_cell_vector_dataset(self) -> None:
        source, dispatched, report = _audit(
            _cell_vector_bytes(),
            "frp_m15_cell_trace.vec",
        )

        dataset = build_trace_dataset(dispatched, report)
        cell_records = dataset.cell_records or ()

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertIs(
            dataset.trace_family,
            TraceFamily.M15_PER_CELL_VECTOR,
        )
        self.assertIs(
            dataset.ordering_validation,
            OrderingValidationStatus.VALIDATED_SOURCE_ORDER,
        )
        self.assertEqual(
            dataset.eligible_modes,
            (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TRACE_EXPLORER,
            ),
        )
        self.assertEqual(len(cell_records), 4)
        self.assertEqual(len(dataset.source_references), 5)
        self.assertIsNone(dataset.tick_records)
        self.assertEqual(
            tuple(
                record.canonical_state.canonical_state
                for record in cell_records
                if record.canonical_state is not None
            ),
            (
                CanonicalTernaryState.NEUTRAL,
                CanonicalTernaryState.POSITIVE,
                CanonicalTernaryState.NEGATIVE,
                CanonicalTernaryState.NEUTRAL,
            ),
        )
        self.assertTrue(
            all(
                reference.source_sha256 == source.content_sha256
                for reference in dataset.source_references
            )
        )

    def test_builds_pending_route_dataset(self) -> None:
        source, dispatched, report = _audit(
            _route_vector_bytes(),
            "frp_m15_pending_routes.trace",
        )

        dataset = build_trace_dataset(dispatched, report)
        route_events = dataset.route_events or ()

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertIs(
            dataset.trace_family,
            TraceFamily.M15_PENDING_ROUTE,
        )
        self.assertIs(
            dataset.ordering_validation,
            OrderingValidationStatus.VALIDATED_SOURCE_ORDER,
        )
        self.assertEqual(
            dataset.eligible_modes,
            (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            ),
        )
        self.assertEqual(len(route_events), 4)
        self.assertEqual(len(dataset.source_references), 5)
        self.assertIsNone(dataset.tick_records)
        self.assertEqual(
            tuple(event.route_status for event in route_events),
            (
                RouteStatus.PENDING,
                RouteStatus.APPLIED,
                RouteStatus.PENDING,
                RouteStatus.APPLIED,
            ),
        )
        self.assertEqual(
            tuple(
                event.canonical_target_state
                for event in route_events
            ),
            (
                CanonicalTernaryState.POSITIVE,
                CanonicalTernaryState.POSITIVE,
                CanonicalTernaryState.NEGATIVE,
                CanonicalTernaryState.NEGATIVE,
            ),
        )
        self.assertTrue(source.verify_integrity())

    def test_primary_vector_build_is_deterministic(self) -> None:
        raw_bytes = _primary_vector_bytes(
            M15VectorTraceKind.FULL_CORRELATION_VECTORS,
            "free",
        )
        _, dispatched, report = _audit(
            raw_bytes,
            "deterministic-full-correlation.vec",
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

    def test_rejects_reserved_request_state(self) -> None:
        trace_kind = M15VectorTraceKind.FULL_CORRELATION_VECTORS
        rows = list(_primary_rows(trace_kind, "free", 2))
        invalid_row = list(rows[0])
        invalid_row[7] = "2"
        rows[0] = tuple(invalid_row)
        raw_bytes = _vector_bytes(
            trace_kind,
            PRIMARY_VECTOR_COLUMNS,
            rows,
            scheduler_mode="free",
            trace_steps=2,
        )
        _, dispatched, report = _audit(
            raw_bytes,
            "reserved-request-state.vec",
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


if __name__ == "__main__":
    unittest.main()
