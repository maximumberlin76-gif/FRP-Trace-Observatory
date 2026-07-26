"""Tests for read-only validation of registered FRP M15 vectors."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError, replace

from artifact_auditor.audit_report import CheckOutcome
from artifact_auditor.m15_vector_validator import (
    M15VectorValidation,
    M15VectorValidationError,
    validate_m15_vector,
)
from parsers.artifact_dispatch import (
    DispatchedArtifact,
    dispatch_artifact,
)
from parsers.m15_vector import (
    CELL_TRACE_COLUMNS,
    M15_VECTOR_FORMAT_VERSION,
    M15_VECTOR_PRODUCER_METADATA_ORDER,
    PRIMARY_VECTOR_COLUMNS,
    ROUTE_TRACE_COLUMNS,
    M15VectorTraceKind,
    expected_columns_for_trace_kind,
)
from parsers.source_artifact import capture_source_bytes


_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_PRIMARY_KINDS = (
    M15VectorTraceKind.KERNEL_TRANSITION_VECTORS,
    M15VectorTraceKind.SCHEDULER_FREE_VECTORS,
    M15VectorTraceKind.SCHEDULER_7_1_VECTORS,
    M15VectorTraceKind.SCHEDULER_1_7_VECTORS,
    M15VectorTraceKind.FULL_CORRELATION_VECTORS,
)
_ALL_KINDS = (
    M15VectorTraceKind.KERNEL_TRANSITION_VECTORS,
    M15VectorTraceKind.PENDING_ROUTES,
    M15VectorTraceKind.SCHEDULER_FREE_VECTORS,
    M15VectorTraceKind.SCHEDULER_7_1_VECTORS,
    M15VectorTraceKind.SCHEDULER_1_7_VECTORS,
    M15VectorTraceKind.FULL_CORRELATION_VECTORS,
    M15VectorTraceKind.CELL_TRACE,
)
_SCHEDULERS = {
    M15VectorTraceKind.KERNEL_TRANSITION_VECTORS: "free",
    M15VectorTraceKind.PENDING_ROUTES: "free",
    M15VectorTraceKind.SCHEDULER_FREE_VECTORS: "free",
    M15VectorTraceKind.SCHEDULER_7_1_VECTORS: "7/1",
    M15VectorTraceKind.SCHEDULER_1_7_VECTORS: "1/7",
    M15VectorTraceKind.FULL_CORRELATION_VECTORS: "free",
    M15VectorTraceKind.CELL_TRACE: "free",
}
_SCHEDULER_CODES = {"free": 0, "7/1": 1, "1/7": 2}
_COMMON_CODES = (
    "m15_vector_metadata_order",
    "m15_vector_metadata_identity",
    "m15_vector_trace_kind",
    "m15_vector_topology_metadata",
    "m15_vector_scheduler_metadata",
    "m15_vector_column_contract",
    "m15_vector_row_count",
)


def _scheduler_state(mode: str, tick: int) -> int:
    if mode == "7/1":
        return 2 if (tick + 1) % 8 == 0 else 1
    if mode == "1/7":
        return 3 if tick % 8 == 0 else 4
    return 0


def _default_steps(trace_kind: M15VectorTraceKind) -> int:
    if trace_kind in {
        M15VectorTraceKind.KERNEL_TRANSITION_VECTORS,
        M15VectorTraceKind.PENDING_ROUTES,
        M15VectorTraceKind.SCHEDULER_FREE_VECTORS,
        M15VectorTraceKind.SCHEDULER_7_1_VECTORS,
        M15VectorTraceKind.SCHEDULER_1_7_VECTORS,
    }:
        return 16
    return 1


def _primary_rows(
    trace_kind: M15VectorTraceKind,
    scheduler: str,
    steps: int,
) -> tuple[tuple[str, ...], ...]:
    rows = []
    for tick in range(steps):
        values = dict.fromkeys(PRIMARY_VECTOR_COLUMNS, "0")
        values.update(
            TICK=f"{tick:08d}",
            RESET_N="1",
            SCHED_MODE=str(_SCHEDULER_CODES[scheduler]),
            SCHED_STATE=str(_scheduler_state(scheduler, tick)),
            AUTO_TARGETS_ENABLE=(
                "1"
                if trace_kind
                is M15VectorTraceKind.FULL_CORRELATION_VECTORS
                else "0"
            ),
            REQ_CELL_IDS="0",
            REQ_TARGET_STATES="0",
            GAMMA_NOISE_TARGETS_Q="0,0",
        )
        rows.append(tuple(values[column] for column in PRIMARY_VECTOR_COLUMNS))
    return tuple(rows)


def _cell_rows() -> tuple[tuple[str, ...], ...]:
    rows = []
    for cell in range(2):
        values = dict.fromkeys(CELL_TRACE_COLUMNS, "0")
        values.update(
            TICK="00000000",
            CELL_ID=str(cell),
            STATE_CODE=str(cell),
            PHASE_WORD="00000000",
        )
        rows.append(tuple(values[column] for column in CELL_TRACE_COLUMNS))
    return tuple(rows)


def _route_rows() -> tuple[tuple[str, ...], ...]:
    return (
        ("00000000", "0", "0", "1", "1", "pending"),
        ("00000001", "1", "0", "1", "1", "applied"),
    )


def _rows(
    trace_kind: M15VectorTraceKind,
    scheduler: str,
    steps: int,
) -> tuple[tuple[str, ...], ...]:
    if trace_kind in _PRIMARY_KINDS:
        return _primary_rows(trace_kind, scheduler, steps)
    if trace_kind is M15VectorTraceKind.CELL_TRACE:
        return _cell_rows()
    return _route_rows()


def _metadata(
    trace_kind: str,
    scheduler: str,
    steps: int,
    columns: tuple[str, ...],
) -> dict[str, object]:
    return {
        "format_version": M15_VECTOR_FORMAT_VERSION,
        "frp_version": "1.7.0",
        "milestone": _MILESTONE,
        "trace_kind": trace_kind,
        "cells": 2,
        "hierarchy_depth": 1,
        "request_lanes": 1,
        "transition_fraction": 0.5,
        "scheduler_mode": scheduler,
        "fractal_alpha": 0.125,
        "thermal_beta": 0.25,
        "scalar_format": "S32Q16",
        "unit_format": "S32Q30",
        "phase_format": "PHASE_U32",
        "seed": 76,
        "trace_steps": steps,
        "column_definition": columns,
    }


def _dispatch(
    trace_kind: M15VectorTraceKind,
    *,
    scheduler: str | None = None,
    steps: int | None = None,
    rows: tuple[tuple[str, ...], ...] | None = None,
    metadata_updates: dict[str, object] | None = None,
    metadata_order: tuple[str, ...] = M15_VECTOR_PRODUCER_METADATA_ORDER,
) -> DispatchedArtifact:
    selected_scheduler = scheduler or _SCHEDULERS[trace_kind]
    selected_steps = steps if steps is not None else _default_steps(trace_kind)
    columns = expected_columns_for_trace_kind(trace_kind)
    assert columns is not None
    metadata = _metadata(
        trace_kind.value,
        selected_scheduler,
        selected_steps,
        columns,
    )
    if metadata_updates:
        metadata.update(metadata_updates)
    selected_rows = (
        rows
        if rows is not None
        else _rows(trace_kind, selected_scheduler, selected_steps)
    )
    lines = [
        f"# {key}="
        + json.dumps(
            metadata[key],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for key in metadata_order
    ]
    lines.append("# " + " | ".join(columns))
    lines.extend(" | ".join(row) for row in selected_rows)
    source = capture_source_bytes(
        ("\n".join(lines) + "\n").encode(),
        source_filename=f"{trace_kind.value}.vec",
        source_path=f"published/m15/{trace_kind.value}.vec",
    )
    return dispatch_artifact(source)


def _changed(
    rows: tuple[tuple[str, ...], ...],
    columns: tuple[str, ...],
    row_index: int,
    column: str,
    value: str,
) -> tuple[tuple[str, ...], ...]:
    mutable_rows = [list(row) for row in rows]
    mutable_rows[row_index][columns.index(column)] = value
    return tuple(tuple(row) for row in mutable_rows)


def _failed(result: M15VectorValidation) -> tuple[str, ...]:
    return tuple(
        spec.check_code
        for spec in result.check_specs
        if spec.outcome is CheckOutcome.FAIL
    )


class M15VectorValidatorTests(unittest.TestCase):
    """Exercise every registered vector family and its exact checks."""

    def test_all_registered_trace_kinds_pass_without_mutation(self) -> None:
        expected_counts = {
            **dict.fromkeys(_PRIMARY_KINDS, 13),
            M15VectorTraceKind.CELL_TRACE: 10,
            M15VectorTraceKind.PENDING_ROUTES: 11,
        }
        for trace_kind in _ALL_KINDS:
            with self.subTest(trace_kind=trace_kind.value):
                dispatched = _dispatch(trace_kind)
                raw_bytes = dispatched.source_artifact.raw_bytes

                result = validate_m15_vector(dispatched)

                self.assertIs(result.trace_kind, trace_kind)
                self.assertEqual(
                    len(result.check_specs),
                    expected_counts[trace_kind],
                )
                self.assertEqual(
                    tuple(spec.check_code for spec in result.check_specs[:7]),
                    _COMMON_CODES,
                )
                self.assertEqual(_failed(result), ())
                self.assertTrue(result.valid)
                self.assertEqual(
                    dispatched.source_artifact.raw_bytes,
                    raw_bytes,
                )

    def test_common_contract_failures_remain_distinct(self) -> None:
        swapped_order = list(M15_VECTOR_PRODUCER_METADATA_ORDER)
        swapped_order[1], swapped_order[2] = (
            swapped_order[2],
            swapped_order[1],
        )
        cases = (
            (
                {"metadata_order": tuple(swapped_order)},
                ("m15_vector_metadata_order",),
            ),
            (
                {"metadata_updates": {"frp_version": "1.7.1"}},
                ("m15_vector_metadata_identity",),
            ),
            (
                {"metadata_updates": {"transition_fraction": 1}},
                ("m15_vector_topology_metadata",),
            ),
        )
        for arguments, expected in cases:
            with self.subTest(expected=expected):
                result = validate_m15_vector(
                    _dispatch(
                        M15VectorTraceKind.FULL_CORRELATION_VECTORS,
                        **arguments,
                    )
                )
                self.assertEqual(_failed(result), expected)

        scheduler_result = validate_m15_vector(
            _dispatch(
                M15VectorTraceKind.SCHEDULER_FREE_VECTORS,
                scheduler="7/1",
            )
        )
        self.assertEqual(
            _failed(scheduler_result),
            ("m15_vector_scheduler_metadata",),
        )

    def test_primary_checks_report_independent_failures(self) -> None:
        trace_kind = M15VectorTraceKind.FULL_CORRELATION_VECTORS
        base_rows = _primary_rows(trace_kind, "free", 2)
        cases = (
            (
                0,
                "HEAT_GLOBAL_Q",
                str(1 << 31),
                "m15_vector_primary_field_encoding",
            ),
            (1, "TICK", "00000000", "m15_vector_tick_order"),
            (
                0,
                "SCHED_STATE",
                "1",
                "m15_vector_scheduler_relation",
            ),
            (0, "STATES_PACKED", "2", "m15_vector_ternary_domain"),
            (
                0,
                "SWITCH_LOAD_Q",
                "1",
                "m15_vector_transition_capacity",
            ),
            (
                0,
                "ACTUAL_DIRECT_EVENTS",
                "1",
                "m15_vector_direct_transition_invariants",
            ),
        )
        for row_index, column, value, expected in cases:
            with self.subTest(check=expected):
                changed = _changed(
                    base_rows,
                    PRIMARY_VECTOR_COLUMNS,
                    row_index,
                    column,
                    value,
                )
                result = validate_m15_vector(
                    _dispatch(trace_kind, steps=2, rows=changed)
                )
                self.assertEqual(_failed(result), (expected,))
                self.assertFalse(result.valid)

    def test_cell_checks_report_independent_failures(self) -> None:
        base_rows = _cell_rows()
        reordered = _changed(
            _changed(
                base_rows,
                CELL_TRACE_COLUMNS,
                0,
                "CELL_ID",
                "1",
            ),
            CELL_TRACE_COLUMNS,
            1,
            "CELL_ID",
            "0",
        )
        cases = (
            (
                _changed(
                    base_rows,
                    CELL_TRACE_COLUMNS,
                    0,
                    "HEAT_Q",
                    str(1 << 31),
                ),
                "m15_vector_cell_field_encoding",
            ),
            (reordered, "m15_vector_cell_tick_order"),
            (
                _changed(
                    base_rows,
                    CELL_TRACE_COLUMNS,
                    0,
                    "STATE_CODE",
                    "2",
                ),
                "m15_vector_cell_ternary_domain",
            ),
        )
        for rows, expected in cases:
            with self.subTest(check=expected):
                result = validate_m15_vector(
                    _dispatch(M15VectorTraceKind.CELL_TRACE, rows=rows)
                )
                self.assertEqual(_failed(result), (expected,))

    def test_route_checks_preserve_order_domain_and_pending_relation(
        self,
    ) -> None:
        base_rows = _route_rows()
        wrong_domain = _changed(
            _changed(
                base_rows,
                ROUTE_TRACE_COLUMNS,
                0,
                "TARGET_STATE_CODE",
                "0",
            ),
            ROUTE_TRACE_COLUMNS,
            1,
            "TARGET_STATE_CODE",
            "0",
        )
        wrong_ready = _changed(
            _changed(
                base_rows,
                ROUTE_TRACE_COLUMNS,
                0,
                "READY_TICK",
                "2",
            ),
            ROUTE_TRACE_COLUMNS,
            1,
            "READY_TICK",
            "2",
        )
        cases = (
            (
                _changed(
                    base_rows,
                    ROUTE_TRACE_COLUMNS,
                    1,
                    "ROUTE_INDEX",
                    "2",
                ),
                ("m15_vector_route_order",),
            ),
            (wrong_domain, ("m15_vector_route_ternary_domain",)),
            (wrong_ready, ("m15_vector_pending_route_relation",)),
            (
                _changed(
                    base_rows,
                    ROUTE_TRACE_COLUMNS,
                    0,
                    "ROUTE_STATUS",
                    "queued",
                ),
                (
                    "m15_vector_route_field_encoding",
                    "m15_vector_route_order",
                    "m15_vector_route_ternary_domain",
                    "m15_vector_pending_route_relation",
                ),
            ),
        )
        for rows, expected in cases:
            with self.subTest(expected=expected):
                result = validate_m15_vector(
                    _dispatch(M15VectorTraceKind.PENDING_ROUTES, rows=rows)
                )
                self.assertEqual(_failed(result), expected)

    def test_routing_and_result_invariants_are_enforced(self) -> None:
        plain_source = capture_source_bytes(
            b"plain text\n",
            source_filename="plain.txt",
        )
        for value in ("invalid", dispatch_artifact(plain_source)):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(M15VectorValidationError):
                    validate_m15_vector(value)

        result = validate_m15_vector(
            _dispatch(M15VectorTraceKind.FULL_CORRELATION_VECTORS)
        )
        with self.assertRaises(M15VectorValidationError):
            replace(
                result,
                trace_kind=M15VectorTraceKind.CELL_TRACE,
            )
        with self.assertRaises(M15VectorValidationError):
            replace(result, check_specs=())
        with self.assertRaises(FrozenInstanceError):
            setattr(
                result,
                "trace_kind",
                M15VectorTraceKind.CELL_TRACE,
            )
