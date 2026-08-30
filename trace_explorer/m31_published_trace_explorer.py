"""Read-only Trace Explorer projection for the exact FRP M31 publication.

This module begins only after the complete M31 published Artifact Auditor
batch has passed.  It resolves the sole M31 ``trace_explorer`` route and
projects the two execution-trace provenance sources named by the published
evidence document.  The RTL and FPGA-preparation contours remain distinct:
their paths, raw digests, local sequences, execution epochs, record digests,
and measurement boundaries are never merged or re-labelled.

The consumer never executes upstream content, invents missing records,
normalizes published metrics, merges thermal contours, reimplements FRP
semantics, mutates the upstream repository, or writes downstream results back
to FRP.  Aggregate values are calculated only to verify the exact summary
already published by M31.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid5

from artifact_auditor.audit_report import SourceLocation, ValidationStatus
from artifact_auditor.m31_published_auditor import (
    M31PublishedAuditBatch,
    M31PublishedAuditReport,
    audit_m31_published_documents,
)
from artifact_auditor.m31_published_boundary_intake import (
    FRP_M30_ARCHIVE_SHA256,
    M31_PUBLISHED_REGISTRY_REVISION,
    M31PublishedDocumentRole,
    M31PublishedProvenanceSource,
)
from parsers.json_artifact import ParsedJsonArtifact, parse_json_artifact
from parsers.m31_published_dispatch import M31PublishedDocumentDispatch
from schemas.m31_published_registry import M31PublishedMeasurementContour
from schemas.registry import ObservatoryMode


__all__ = [
    "M31PublishedExecutionEpoch",
    "M31PublishedSchedulerTrace",
    "M31PublishedTraceCell",
    "M31PublishedTraceContour",
    "M31PublishedTraceDataset",
    "M31PublishedTraceError",
    "M31PublishedTraceRecord",
    "M31PublishedTraceRequest",
    "build_m31_published_trace_dataset",
    "explore_m31_published_documents",
]


_EVIDENCE_SCHEMA: Final = (
    "frp.m31.phase_interference_active_zero_thermal_evidence.v1"
)
_EVIDENCE_KIND: Final = "phase_interference_active_zero_thermal_evidence"
_EVIDENCE_PATH: Final = (
    "artifacts/m31/evidence/"
    "m31-phase-interference-active-zero-thermal-evidence.json"
)
_EVIDENCE_RAW_SHA256: Final = (
    "bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42"
)
_SOURCE_RELEASE: Final = "FRP v1.8.0 / M16"
_TRACE_SOURCE_IDENTITIES: Final = (
    (
        "artifacts/m19/execution/m16-rtl-execution-trace.json",
        "d7945e0d2b5aaa05c5fff2e4e60d3b984017f7e4ae1984c55920368a110020bd",
        "frp.m16.rtl_execution_trace.v2.1.0",
        "m16_rtl_execution_trace",
        "rtl",
    ),
    (
        "artifacts/m19/execution/"
        "m16-fpga-preparation-execution-trace.json",
        "7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f",
        "frp.m16.fpga_preparation_execution_trace.v2.1.0",
        "m16_fpga_preparation_execution_trace",
        "fpga_preparation",
    ),
)
_TRACE_IDENTITY_BY_PATH: Final = {
    identity[0]: identity for identity in _TRACE_SOURCE_IDENTITIES
}
_TERNARY_DOMAIN: Final = frozenset({-1, 0, 1})
_HEX64: Final = re.compile(r"^[0-9a-f]{64}$")
_DATASET_NAMESPACE: Final = UUID("d4bcf199-4d25-5b29-a3dc-6c0c850b68e5")
_CONTOUR_NAMESPACE: Final = UUID("6a6b72dc-5768-5b1d-b589-5d3212f91107")
_RECORD_NAMESPACE: Final = UUID("7253b230-d069-5a82-81db-d19e34e84589")
_EVENT_NAMES: Final = (
    "actual_direct_events",
    "neutral_routed_events",
    "prevented_direct_events",
    "queue_overflow_events",
    "requested_direct_events",
    "reserved_state_events",
)
_TRANSITION_NAMES: Final = (
    "active_zero_to_polarity",
    "direct_opposite",
    "polarity_to_active_zero",
    "retained_same",
)
_INVARIANT_NAMES: Final = (
    "state_domain_valid",
    "scheduler_counts_valid",
    "request_lane_order_valid",
    "pending_polarity_valid",
    "active_neutral_valid",
    "transition_capacity_valid",
    "state_update_valid",
    "no_actual_direct_events",
    "no_reserved_state",
    "no_queue_overflow",
)
_SCHEDULER_COUNTER_NAMES: Final = (
    "balance",
    "commit",
    "excite",
    "free",
    "neutralize",
)
_SCHEDULER_MODE_ORDER: Final = ("free", "7/1", "1/7")
_SCHEDULER_STATE_ORDER: Final = (
    "balance",
    "commit",
    "excite",
    "free",
    "neutralize",
)
_VALID_SCHEDULER_MODES: Final = frozenset(_SCHEDULER_MODE_ORDER)
_VALID_SCHEDULER_STATES: Final = frozenset(_SCHEDULER_STATE_ORDER)
_ACTIVE_ZERO_ROLES: Final = (
    "conflict_neutralization",
    "temporal_separation",
    "balancing",
    "damping",
    "transition_buffering",
    "switching_load_distribution",
    "retained_transition_continuity",
    "pending_route_completion_preparation",
    "stabilization",
)
_PUBLICATION_CONTRACT: Final = (
    ("direction", "upstream_published_bytes_to_downstream"),
    ("downstream_metric_normalization", "forbidden"),
    ("downstream_repository", "FRP-Trace-Observatory"),
    ("downstream_role", "read_only_validation_and_visualization"),
    ("downstream_semantic_reimplementation", "forbidden"),
    ("downstream_source_mutation", "forbidden"),
    ("downstream_writeback", "forbidden"),
    ("m29_boundary_confirmed", True),
    ("published_contours_must_remain_separate", True),
    ("upstream_repository", "FRP"),
)


class M31PublishedTraceError(ValueError):
    """Raised when the M31 published Trace Explorer boundary is violated."""


def _validate_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise M31PublishedTraceError(f"{field} must be a string")
    if not value or value != value.strip() or "\x00" in value:
        raise M31PublishedTraceError(
            f"{field} must be nonempty without outer whitespace or NUL"
        )
    return value


def _validate_nonnegative_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise M31PublishedTraceError(
            f"{field} must be a nonnegative integer"
        )
    return value


def _validate_positive_integer(value: object, field: str) -> int:
    result = _validate_nonnegative_integer(value, field)
    if result == 0:
        raise M31PublishedTraceError(f"{field} must be positive")
    return result


def _validate_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise M31PublishedTraceError(
            f"{field} must be lowercase hexadecimal SHA-256"
        )
    return value


def _validate_uuid(value: object, field: str) -> str:
    text = _validate_text(value, field)
    try:
        UUID(text)
    except ValueError as exc:
        raise M31PublishedTraceError(f"{field} must be a UUID") from exc
    return text


def _validate_ternary(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise M31PublishedTraceError(f"{field} must be an integer")
    if value not in _TERNARY_DOMAIN:
        raise M31PublishedTraceError(f"{field} must remain in -1/0/1")
    return value


def _plain(value: object) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _canonical_json_bytes(value: object, *, ensure_ascii: bool = True) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=ensure_ascii,
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _record_source_sha256(value: object) -> str:
    return _sha256(_canonical_json_bytes(_plain(value), ensure_ascii=False))


def _records_document_sha256(records: object) -> str:
    return _sha256(
        _canonical_json_bytes(_plain(records), ensure_ascii=False) + b"\n"
    )


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise M31PublishedTraceError(f"{field} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise M31PublishedTraceError(f"{field} keys must be strings")
    return value


def _require_sequence(value: object, field: str) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise M31PublishedTraceError(f"{field} must be an array")
    return tuple(value)


def _integer_tuple(
    value: object,
    field: str,
    *,
    length: int | None = None,
    ternary: bool = False,
) -> tuple[int, ...]:
    sequence = _require_sequence(value, field)
    if length is not None and len(sequence) != length:
        raise M31PublishedTraceError(
            f"{field} must contain exactly {length} values"
        )
    validator = _validate_ternary if ternary else _validate_nonnegative_integer
    return tuple(
        validator(item, f"{field}[{index}]")
        for index, item in enumerate(sequence)
    )


def _validate_sorted_cell_ids(value: tuple[int, ...], field: str) -> None:
    if tuple(sorted(set(value))) != value:
        raise M31PublishedTraceError(
            f"{field} must contain unique source-ordered cell identifiers"
        )
    if any(cell_id >= 8 for cell_id in value):
        raise M31PublishedTraceError(f"{field} cell identifier is out of range")


def _ordered_counts(
    value: object,
    names: tuple[str, ...],
    field: str,
) -> tuple[tuple[str, int], ...]:
    source = _require_mapping(value, field)
    if frozenset(source) != frozenset(names):
        raise M31PublishedTraceError(f"{field} key inventory changed")
    return tuple(
        (
            name,
            _validate_nonnegative_integer(
                source.get(name),
                f"{field}.{name}",
            ),
        )
        for name in names
    )


@dataclass(frozen=True, slots=True)
class M31PublishedTraceRequest:
    """One exact M16 request-lane record in source lane order."""

    lane: int
    valid: bool
    cell_index: int
    target_state: int
    accepted: bool
    rejected: bool

    def __post_init__(self) -> None:
        if self.lane not in (0, 1):
            raise M31PublishedTraceError("request lane must be 0 or 1")
        if not isinstance(self.valid, bool):
            raise M31PublishedTraceError("request valid must be boolean")
        _validate_nonnegative_integer(self.cell_index, "request cell_index")
        if self.cell_index >= 8:
            raise M31PublishedTraceError("request cell_index is out of range")
        _validate_ternary(self.target_state, "request target_state")
        if not isinstance(self.accepted, bool) or not isinstance(
            self.rejected, bool
        ):
            raise M31PublishedTraceError(
                "request accepted and rejected must be boolean"
            )
        if self.accepted and self.rejected:
            raise M31PublishedTraceError(
                "one request cannot be accepted and rejected"
            )
        if not self.valid and (self.accepted or self.rejected):
            raise M31PublishedTraceError(
                "an invalid request cannot be accepted or rejected"
            )

    def source_payload(self) -> dict[str, object]:
        """Reconstruct the exact upstream request mapping."""

        return {
            "accepted": self.accepted,
            "cell_index": self.cell_index,
            "lane": self.lane,
            "rejected": self.rejected,
            "target_state": self.target_state,
            "valid": self.valid,
        }


@dataclass(frozen=True, slots=True)
class M31PublishedSchedulerTrace:
    """One exact scheduler snapshot without mode reinterpretation."""

    mode: str
    state: str
    ticks_before: int
    ticks_after: int
    counters_after: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        _validate_text(self.mode, "scheduler mode")
        _validate_text(self.state, "scheduler state")
        if self.mode not in _VALID_SCHEDULER_MODES:
            raise M31PublishedTraceError("unknown scheduler mode")
        if self.state not in _VALID_SCHEDULER_STATES:
            raise M31PublishedTraceError("unknown scheduler state")
        _validate_nonnegative_integer(self.ticks_before, "ticks_before")
        _validate_positive_integer(self.ticks_after, "ticks_after")
        if self.ticks_after != self.ticks_before + 1:
            raise M31PublishedTraceError(
                "scheduler ticks_after must equal ticks_before plus one"
            )
        if not isinstance(self.counters_after, tuple):
            raise M31PublishedTraceError("counters_after must be a tuple")
        if tuple(name for name, _ in self.counters_after) != (
            _SCHEDULER_COUNTER_NAMES
        ):
            raise M31PublishedTraceError(
                "scheduler counters must retain exact source key order"
            )
        for name, value in self.counters_after:
            _validate_text(name, "scheduler counter name")
            _validate_nonnegative_integer(value, f"scheduler counter {name}")
        if sum(value for _, value in self.counters_after) != self.ticks_after:
            raise M31PublishedTraceError(
                "scheduler counter sum must equal ticks_after"
            )
        permitted_states = {
            "free": frozenset({"free"}),
            "1/7": frozenset({"excite", "neutralize"}),
            "7/1": frozenset({"balance", "commit"}),
        }
        if self.state not in permitted_states[self.mode]:
            raise M31PublishedTraceError(
                "scheduler state is incompatible with its exact mode"
            )

    def source_payload(self) -> dict[str, object]:
        """Reconstruct the exact upstream scheduler mapping."""

        return {
            "counters_after": dict(self.counters_after),
            "mode": self.mode,
            "state": self.state,
            "ticks_after": self.ticks_after,
            "ticks_before": self.ticks_before,
        }


@dataclass(frozen=True, slots=True)
class M31PublishedTraceCell:
    """One source-linked cell projection for one execution record."""

    cell_id: int
    phase_derived_target: int
    retained_state_before: int
    retained_state_after: int
    pending_route_before: int
    pending_route_after: int
    accepted: bool
    accepted_change: bool
    neutral_routed: bool

    def __post_init__(self) -> None:
        _validate_nonnegative_integer(self.cell_id, "cell_id")
        if self.cell_id >= 8:
            raise M31PublishedTraceError("cell_id is out of range")
        for field, value in (
            ("phase_derived_target", self.phase_derived_target),
            ("retained_state_before", self.retained_state_before),
            ("retained_state_after", self.retained_state_after),
            ("pending_route_before", self.pending_route_before),
            ("pending_route_after", self.pending_route_after),
        ):
            _validate_ternary(value, field)
        for field, value in (
            ("accepted", self.accepted),
            ("accepted_change", self.accepted_change),
            ("neutral_routed", self.neutral_routed),
        ):
            if not isinstance(value, bool):
                raise M31PublishedTraceError(f"{field} must be boolean")
        if (
            self.retained_state_before,
            self.retained_state_after,
        ) in ((-1, 1), (1, -1)):
            raise M31PublishedTraceError(
                "direct opposite retained-state transitions are forbidden"
            )
        if self.neutral_routed:
            if self.retained_state_after != 0:
                raise M31PublishedTraceError(
                    "a neutral-routed first leg must retain active neutral 0"
                )
            if self.pending_route_after not in (-1, 1):
                raise M31PublishedTraceError(
                    "a neutral-routed first leg must retain pending polarity"
                )


@dataclass(frozen=True, slots=True)
class M31PublishedTraceRecord:
    """One immutable source record and its complete lossless projection."""

    trace_record_id: str
    contour_index: int
    sequence: int
    execution_epoch: int
    core_ready: bool
    scheduler: M31PublishedSchedulerTrace
    requests: tuple[M31PublishedTraceRequest, ...]
    cells: tuple[M31PublishedTraceCell, ...]
    accepted_cell_ids: tuple[int, ...]
    accepted_change_cell_ids: tuple[int, ...]
    neutral_routed_cell_ids: tuple[int, ...]
    capacity_limit: int
    accepted_changes: int
    capacity_remaining: int
    capacity_exhausted: bool
    switch_load_numerator: int
    switch_load_denominator: int
    switch_load_q16: int
    event_counts: tuple[tuple[str, int], ...]
    invariant_names: tuple[str, ...]
    invariant_all_pass: bool
    source_location: SourceLocation
    source_record_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.trace_record_id, "trace_record_id")
        _validate_nonnegative_integer(self.contour_index, "contour_index")
        _validate_nonnegative_integer(self.sequence, "sequence")
        _validate_nonnegative_integer(self.execution_epoch, "execution_epoch")
        if not isinstance(self.core_ready, bool) or not self.core_ready:
            raise M31PublishedTraceError("core_ready must remain true")
        if not isinstance(self.scheduler, M31PublishedSchedulerTrace):
            raise M31PublishedTraceError(
                "scheduler must be M31PublishedSchedulerTrace"
            )
        if (
            not isinstance(self.requests, tuple)
            or tuple(request.lane for request in self.requests) != (0, 1)
        ):
            raise M31PublishedTraceError(
                "requests must retain exact lane order 0, 1"
            )
        if any(
            not isinstance(request, M31PublishedTraceRequest)
            for request in self.requests
        ):
            raise M31PublishedTraceError(
                "requests must contain M31PublishedTraceRequest values"
            )
        if (
            not isinstance(self.cells, tuple)
            or tuple(cell.cell_id for cell in self.cells) != tuple(range(8))
        ):
            raise M31PublishedTraceError(
                "cells must retain exact source order 0 through 7"
            )
        if any(
            not isinstance(cell, M31PublishedTraceCell)
            for cell in self.cells
        ):
            raise M31PublishedTraceError(
                "cells must contain M31PublishedTraceCell values"
            )
        for field, value in (
            ("accepted_cell_ids", self.accepted_cell_ids),
            ("accepted_change_cell_ids", self.accepted_change_cell_ids),
            ("neutral_routed_cell_ids", self.neutral_routed_cell_ids),
        ):
            if not isinstance(value, tuple):
                raise M31PublishedTraceError(f"{field} must be a tuple")
            _validate_sorted_cell_ids(value, field)
        if self.accepted_cell_ids != tuple(
            cell.cell_id for cell in self.cells if cell.accepted
        ):
            raise M31PublishedTraceError(
                "accepted_cell_ids differ from cell projection"
            )
        if self.accepted_change_cell_ids != tuple(
            cell.cell_id for cell in self.cells if cell.accepted_change
        ):
            raise M31PublishedTraceError(
                "accepted_change_cell_ids differ from cell projection"
            )
        if self.neutral_routed_cell_ids != tuple(
            cell.cell_id for cell in self.cells if cell.neutral_routed
        ):
            raise M31PublishedTraceError(
                "neutral_routed_cell_ids differ from cell projection"
            )
        _validate_positive_integer(self.capacity_limit, "capacity_limit")
        _validate_nonnegative_integer(self.accepted_changes, "accepted_changes")
        _validate_nonnegative_integer(
            self.capacity_remaining, "capacity_remaining"
        )
        if self.accepted_changes > self.capacity_limit:
            raise M31PublishedTraceError(
                "accepted_changes exceeds capacity_limit"
            )
        if self.capacity_remaining != self.capacity_limit - self.accepted_changes:
            raise M31PublishedTraceError(
                "capacity_remaining relation is invalid"
            )
        if not isinstance(self.capacity_exhausted, bool):
            raise M31PublishedTraceError("capacity_exhausted must be boolean")
        if self.capacity_exhausted is not (self.capacity_remaining == 0):
            raise M31PublishedTraceError(
                "capacity_exhausted differs from capacity_remaining"
            )
        if len(self.accepted_change_cell_ids) != self.accepted_changes:
            raise M31PublishedTraceError(
                "accepted change cell count differs from accepted_changes"
            )
        _validate_nonnegative_integer(
            self.switch_load_numerator, "switch_load_numerator"
        )
        _validate_positive_integer(
            self.switch_load_denominator, "switch_load_denominator"
        )
        _validate_nonnegative_integer(self.switch_load_q16, "switch_load_q16")
        if self.switch_load_numerator != self.accepted_changes:
            raise M31PublishedTraceError(
                "switch_load_numerator differs from accepted_changes"
            )
        if self.switch_load_q16 != (
            self.switch_load_numerator * 65536 // self.switch_load_denominator
        ):
            raise M31PublishedTraceError("switch_load_q16 relation is invalid")
        if not isinstance(self.event_counts, tuple):
            raise M31PublishedTraceError("event_counts must be a tuple")
        if tuple(name for name, _ in self.event_counts) != _EVENT_NAMES:
            raise M31PublishedTraceError(
                "event counters must retain exact source key order"
            )
        for name, value in self.event_counts:
            _validate_nonnegative_integer(value, f"event {name}")
        for forbidden in (
            "actual_direct_events",
            "reserved_state_events",
            "queue_overflow_events",
        ):
            if self.event_count(forbidden) != 0:
                raise M31PublishedTraceError(f"{forbidden} must remain zero")
        if self.invariant_names != _INVARIANT_NAMES:
            raise M31PublishedTraceError(
                "invariant names must retain exact source order"
            )
        if not isinstance(self.invariant_all_pass, bool) or not (
            self.invariant_all_pass
        ):
            raise M31PublishedTraceError("all invariant flags must pass")
        if not isinstance(self.source_location, SourceLocation):
            raise M31PublishedTraceError(
                "source_location must be SourceLocation"
            )
        _validate_sha256(self.source_record_sha256, "source_record_sha256")

    def event_count(self, name: str) -> int:
        """Return one exact named source event counter."""

        _validate_text(name, "event name")
        for current, value in self.event_counts:
            if current == name:
                return value
        raise M31PublishedTraceError(f"unknown event counter: {name!r}")

    @property
    def retained_state_before(self) -> tuple[int, ...]:
        return tuple(cell.retained_state_before for cell in self.cells)

    @property
    def retained_state_after(self) -> tuple[int, ...]:
        return tuple(cell.retained_state_after for cell in self.cells)

    @property
    def pending_route_before(self) -> tuple[int, ...]:
        return tuple(cell.pending_route_before for cell in self.cells)

    @property
    def pending_route_after(self) -> tuple[int, ...]:
        return tuple(cell.pending_route_after for cell in self.cells)

    @property
    def phase_derived_targets(self) -> tuple[int, ...]:
        return tuple(cell.phase_derived_target for cell in self.cells)

    def source_payload(self) -> dict[str, object]:
        """Reconstruct the complete upstream record without normalization."""

        return {
            "accepted_cell_ids": list(self.accepted_cell_ids),
            "accepted_change_cell_ids": list(self.accepted_change_cell_ids),
            "core_ready": self.core_ready,
            "events": dict(self.event_counts),
            "execution_epoch": self.execution_epoch,
            "invariants": {
                "all_pass": self.invariant_all_pass,
                "flags": [
                    {"name": name, "pass": True}
                    for name in self.invariant_names
                ],
            },
            "neutral_routed_cell_ids": list(self.neutral_routed_cell_ids),
            "pending_route_after": list(self.pending_route_after),
            "pending_route_before": list(self.pending_route_before),
            "phase_derived_targets": list(self.phase_derived_targets),
            "requests": [request.source_payload() for request in self.requests],
            "retained_state_after": list(self.retained_state_after),
            "retained_state_before": list(self.retained_state_before),
            "scheduler": self.scheduler.source_payload(),
            "sequence": self.sequence,
            "telemetry": {
                "switch_load_denominator": self.switch_load_denominator,
                "switch_load_numerator": self.switch_load_numerator,
                "switch_load_q16": self.switch_load_q16,
            },
            "transition_capacity": {
                "accepted_changes": self.accepted_changes,
                "capacity_exhausted": self.capacity_exhausted,
                "capacity_limit": self.capacity_limit,
                "capacity_remaining": self.capacity_remaining,
            },
        }


@dataclass(frozen=True, slots=True)
class M31PublishedExecutionEpoch:
    """One exact source-local execution-epoch declaration."""

    contour_index: int
    epoch: int
    mode: str
    record_count: int
    source_location: SourceLocation

    def __post_init__(self) -> None:
        _validate_nonnegative_integer(self.contour_index, "contour_index")
        _validate_nonnegative_integer(self.epoch, "epoch")
        _validate_text(self.mode, "epoch mode")
        if self.mode not in _VALID_SCHEDULER_MODES:
            raise M31PublishedTraceError("unknown execution epoch mode")
        _validate_positive_integer(self.record_count, "record_count")
        if not isinstance(self.source_location, SourceLocation):
            raise M31PublishedTraceError(
                "epoch source_location must be SourceLocation"
            )

    def source_payload(self) -> dict[str, object]:
        """Reconstruct the exact upstream epoch declaration."""

        return {
            "epoch": self.epoch,
            "mode": self.mode,
            "record_count": self.record_count,
        }


def _record_ledger(record: M31PublishedTraceRecord) -> dict[str, object]:
    return {
        "contour_index": record.contour_index,
        "execution_epoch": record.execution_epoch,
        "sequence": record.sequence,
        "source_record_sha256": record.source_record_sha256,
        "trace_record_id": record.trace_record_id,
    }


def _contour_sha256(
    trace_dispatch_sha256: str,
    contour_index: int,
    source_path: str,
    raw_sha256: str,
    schema_identifier: str,
    trace_kind: str,
    layer: str,
    epochs: tuple[M31PublishedExecutionEpoch, ...],
    records: tuple[M31PublishedTraceRecord, ...],
    source_record_digest: str,
    m15_correlation_status: str,
    physical_measurement_availability: str,
    physical_measurement_correlation_status: str,
) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "contour_index": contour_index,
                "epochs": [epoch.source_payload() for epoch in epochs],
                "layer": layer,
                "m15_correlation_status": m15_correlation_status,
                "physical_measurement_availability": (
                    physical_measurement_availability
                ),
                "physical_measurement_correlation_status": (
                    physical_measurement_correlation_status
                ),
                "raw_sha256": raw_sha256,
                "records": [_record_ledger(record) for record in records],
                "schema_identifier": schema_identifier,
                "source_path": source_path,
                "source_record_digest": source_record_digest,
                "source_release": _SOURCE_RELEASE,
                "trace_dispatch_sha256": trace_dispatch_sha256,
                "trace_kind": trace_kind,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class M31PublishedTraceContour:
    """One immutable source contour retained separately from its peer."""

    trace_contour_id: str
    trace_dispatch_sha256: str
    contour_index: int
    provenance_source: M31PublishedProvenanceSource
    parsed_artifact: ParsedJsonArtifact
    source_path: str
    raw_sha256: str
    schema_identifier: str
    trace_kind: str
    layer: str
    epochs: tuple[M31PublishedExecutionEpoch, ...]
    records: tuple[M31PublishedTraceRecord, ...]
    source_record_digest: str
    m15_correlation_status: str
    physical_measurement_availability: str
    physical_measurement_correlation_status: str
    contour_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.trace_contour_id, "trace_contour_id")
        _validate_sha256(
            self.trace_dispatch_sha256,
            "trace_dispatch_sha256",
        )
        _validate_nonnegative_integer(self.contour_index, "contour_index")
        if self.contour_index >= len(_TRACE_SOURCE_IDENTITIES):
            raise M31PublishedTraceError("contour_index is out of range")
        if not isinstance(
            self.provenance_source,
            M31PublishedProvenanceSource,
        ):
            raise M31PublishedTraceError(
                "provenance_source must be M31PublishedProvenanceSource"
            )
        if not self.provenance_source.m30_archive_member_verified:
            raise M31PublishedTraceError(
                "trace provenance must remain a verified M30 archive member"
            )
        if not isinstance(self.parsed_artifact, ParsedJsonArtifact):
            raise M31PublishedTraceError(
                "parsed_artifact must be ParsedJsonArtifact"
            )
        if self.parsed_artifact.source_artifact is not (
            self.provenance_source.source_artifact
        ):
            raise M31PublishedTraceError(
                "parsed trace must reference exact captured provenance bytes"
            )
        expected = _TRACE_SOURCE_IDENTITIES[self.contour_index]
        if (
            self.source_path,
            self.raw_sha256,
            self.schema_identifier,
            self.trace_kind,
            self.layer,
        ) != expected:
            raise M31PublishedTraceError(
                "trace contour identity or source order changed"
            )
        source = self.provenance_source.source_artifact
        if (
            self.provenance_source.source_path != self.source_path
            or source.content_sha256 != self.raw_sha256
            or not source.verify_integrity()
        ):
            raise M31PublishedTraceError(
                "trace provenance raw identity changed"
            )
        root = _require_mapping(self.parsed_artifact.root, "trace root")
        if (
            root.get("schema") != self.schema_identifier
            or root.get("kind") != self.trace_kind
            or root.get("layer") != self.layer
            or root.get("source_release") != _SOURCE_RELEASE
        ):
            raise M31PublishedTraceError("unsupported trace source identity")
        if not isinstance(self.epochs, tuple) or not self.epochs:
            raise M31PublishedTraceError("epochs must be a nonempty tuple")
        if any(
            not isinstance(epoch, M31PublishedExecutionEpoch)
            for epoch in self.epochs
        ):
            raise M31PublishedTraceError(
                "epochs must contain M31PublishedExecutionEpoch values"
            )
        if tuple(epoch.epoch for epoch in self.epochs) != tuple(
            range(len(self.epochs))
        ) or any(epoch.contour_index != self.contour_index for epoch in self.epochs):
            raise M31PublishedTraceError(
                "execution epochs must retain source-local order"
            )
        if not isinstance(self.records, tuple) or not self.records:
            raise M31PublishedTraceError("records must be a nonempty tuple")
        if any(
            not isinstance(record, M31PublishedTraceRecord)
            for record in self.records
        ):
            raise M31PublishedTraceError(
                "records must contain M31PublishedTraceRecord values"
            )
        if tuple(record.sequence for record in self.records) != tuple(
            range(len(self.records))
        ) or any(
            record.contour_index != self.contour_index
            for record in self.records
        ):
            raise M31PublishedTraceError(
                "records must retain source-local sequence order"
            )
        counts = Counter(record.execution_epoch for record in self.records)
        if tuple(counts.get(epoch.epoch, 0) for epoch in self.epochs) != tuple(
            epoch.record_count for epoch in self.epochs
        ):
            raise M31PublishedTraceError(
                "record inventory differs from execution epoch declarations"
            )
        mode_by_epoch = {epoch.epoch: epoch.mode for epoch in self.epochs}
        if any(
            record.scheduler.mode != mode_by_epoch.get(record.execution_epoch)
            for record in self.records
        ):
            raise M31PublishedTraceError(
                "record scheduler mode differs from its source epoch"
            )
        source_records = _require_sequence(root.get("records"), "records")
        if len(source_records) != len(self.records):
            raise M31PublishedTraceError(
                "source and projected record inventories differ"
            )
        for record, source_record in zip(
            self.records,
            source_records,
            strict=True,
        ):
            if record.source_payload() != _plain(source_record):
                raise M31PublishedTraceError(
                    "projected record differs from exact retained source"
                )
            expected_source_sha = _record_source_sha256(source_record)
            if record.source_record_sha256 != expected_source_sha:
                raise M31PublishedTraceError(
                    "projected record source digest mismatch"
                )
            expected_record_id = str(
                uuid5(
                    _RECORD_NAMESPACE,
                    (
                        f"{self.trace_dispatch_sha256}:{self.source_path}:"
                        f"{self.raw_sha256}:{record.sequence}:"
                        f"{expected_source_sha}"
                    ),
                )
            )
            if record.trace_record_id != expected_record_id:
                raise M31PublishedTraceError(
                    "trace_record_id does not bind exact source and order"
                )
            expected_location = SourceLocation(
                json_path=f"$.records[{record.sequence}]",
                array_index=record.sequence,
                package_member=self.source_path,
                source_record_ordinal=record.sequence + 1,
            )
            if record.source_location != expected_location:
                raise M31PublishedTraceError(
                    "record source coordinate changed"
                )
        source_epochs = _require_sequence(
            root.get("execution_epochs"),
            "execution_epochs",
        )
        if [epoch.source_payload() for epoch in self.epochs] != _plain(
            source_epochs
        ):
            raise M31PublishedTraceError(
                "projected epochs differ from exact retained source"
            )
        for epoch in self.epochs:
            expected_location = SourceLocation(
                json_path=f"$.execution_epochs[{epoch.epoch}]",
                array_index=epoch.epoch,
                package_member=self.source_path,
                source_record_ordinal=epoch.epoch + 1,
            )
            if epoch.source_location != expected_location:
                raise M31PublishedTraceError("epoch source coordinate changed")
        _validate_sha256(self.source_record_digest, "source_record_digest")
        if self.source_record_digest != _records_document_sha256(source_records):
            raise M31PublishedTraceError(
                "source record digest differs from retained record sequence"
            )
        summary = _require_mapping(root.get("summary"), "summary")
        if (
            summary.get("record_digest") != self.source_record_digest
            or summary.get("record_count") != len(self.records)
            or summary.get("invariant_pass_records") != len(self.records)
        ):
            raise M31PublishedTraceError(
                "source summary differs from projected record inventory"
            )
        contours = _require_mapping(
            root.get("measurement_contours"),
            "measurement_contours",
        )
        m15 = _require_mapping(
            contours.get("m15_semantic_reference"),
            "m15_semantic_reference",
        )
        physical = _require_mapping(
            contours.get("physical_measurement"),
            "physical_measurement",
        )
        for value, expected_value, field in (
            (
                self.m15_correlation_status,
                m15.get("correlation_status"),
                "m15_correlation_status",
            ),
            (
                self.physical_measurement_availability,
                physical.get("availability"),
                "physical_measurement_availability",
            ),
            (
                self.physical_measurement_correlation_status,
                physical.get("correlation_status"),
                "physical_measurement_correlation_status",
            ),
        ):
            _validate_text(value, field)
            if value != expected_value:
                raise M31PublishedTraceError(
                    f"{field} differs from exact source boundary"
                )
        if (
            self.m15_correlation_status != "not_evaluated_in_m19"
            or self.physical_measurement_availability != "not_in_scope"
            or self.physical_measurement_correlation_status != "not_evaluated"
        ):
            raise M31PublishedTraceError(
                "execution, semantic, or physical contours were conflated"
            )
        _validate_sha256(self.contour_sha256, "contour_sha256")
        expected_digest = _contour_sha256(
            self.trace_dispatch_sha256,
            self.contour_index,
            self.source_path,
            self.raw_sha256,
            self.schema_identifier,
            self.trace_kind,
            self.layer,
            self.epochs,
            self.records,
            self.source_record_digest,
            self.m15_correlation_status,
            self.physical_measurement_availability,
            self.physical_measurement_correlation_status,
        )
        if self.contour_sha256 != expected_digest:
            raise M31PublishedTraceError(
                "contour_sha256 does not bind the exact source contour"
            )
        if self.trace_contour_id != str(
            uuid5(_CONTOUR_NAMESPACE, self.contour_sha256)
        ):
            raise M31PublishedTraceError(
                "trace_contour_id does not bind deterministic contour digest"
            )

    @property
    def record_count(self) -> int:
        return len(self.records)

    @property
    def cell_snapshot_count(self) -> int:
        return sum(len(record.cells) for record in self.records)

    @property
    def request_count(self) -> int:
        return sum(len(record.requests) for record in self.records)


def _flatten_records(
    contours: tuple[M31PublishedTraceContour, ...],
) -> tuple[M31PublishedTraceRecord, ...]:
    return tuple(record for contour in contours for record in contour.records)


def _observed_scheduler_modes(
    contours: tuple[M31PublishedTraceContour, ...],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            epoch.mode for contour in contours for epoch in contour.epochs
        )
    )


def _observed_ternary_domain(
    records: tuple[M31PublishedTraceRecord, ...],
) -> tuple[int, ...]:
    values: set[int] = set()
    for record in records:
        for cell in record.cells:
            values.update(
                {
                    cell.phase_derived_target,
                    cell.retained_state_before,
                    cell.retained_state_after,
                    cell.pending_route_before,
                    cell.pending_route_after,
                }
            )
        values.update(request.target_state for request in record.requests)
    return tuple(sorted(values))


def _event_totals(
    records: tuple[M31PublishedTraceRecord, ...],
) -> tuple[tuple[str, int], ...]:
    return tuple(
        (name, sum(record.event_count(name) for record in records))
        for name in _EVENT_NAMES
    )


def _transition_totals(
    records: tuple[M31PublishedTraceRecord, ...],
) -> tuple[tuple[str, int], ...]:
    counts = Counter({name: 0 for name in _TRANSITION_NAMES})
    for record in records:
        for cell in record.cells:
            before = cell.retained_state_before
            after = cell.retained_state_after
            if before == after:
                counts["retained_same"] += 1
            elif before == 0 and after in (-1, 1):
                counts["active_zero_to_polarity"] += 1
            elif before in (-1, 1) and after == 0:
                counts["polarity_to_active_zero"] += 1
            elif (before, after) in ((-1, 1), (1, -1)):
                counts["direct_opposite"] += 1
            else:
                raise M31PublishedTraceError(
                    "unknown retained-state transition relation"
                )
    return tuple((name, counts[name]) for name in _TRANSITION_NAMES)


def _scheduler_counts(
    records: tuple[M31PublishedTraceRecord, ...],
    names: tuple[str, ...],
    attribute: str,
) -> tuple[tuple[str, int], ...]:
    counts = Counter(
        getattr(record.scheduler, attribute) for record in records
    )
    if any(name not in names for name in counts):
        raise M31PublishedTraceError("unknown scheduler count category")
    return tuple((name, counts[name]) for name in names if counts[name] > 0)


def _dataset_sha256(
    audit_batch: M31PublishedAuditBatch,
    audit_report: M31PublishedAuditReport,
    dispatch: M31PublishedDocumentDispatch,
    measurement_contour: M31PublishedMeasurementContour,
    contours: tuple[M31PublishedTraceContour, ...],
    active_zero_roles: tuple[str, ...],
    published_event_totals: tuple[tuple[str, int], ...],
    published_transition_totals: tuple[tuple[str, int], ...],
    published_scheduler_mode_counts: tuple[tuple[str, int], ...],
    published_scheduler_state_counts: tuple[tuple[str, int], ...],
) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "active_zero_roles": list(active_zero_roles),
                "audit_batch_sha256": audit_batch.batch_sha256,
                "audit_report_sha256": audit_report.report_sha256,
                "contours": [
                    {
                        "contour_sha256": contour.contour_sha256,
                        "raw_sha256": contour.raw_sha256,
                        "source_path": contour.source_path,
                        "source_record_digest": contour.source_record_digest,
                        "trace_contour_id": contour.trace_contour_id,
                    }
                    for contour in contours
                ],
                "evidence_raw_sha256": _EVIDENCE_RAW_SHA256,
                "m30_archive_sha256": FRP_M30_ARCHIVE_SHA256,
                "measurement_contour": measurement_contour.value,
                "publication_contract": dict(_PUBLICATION_CONTRACT),
                "published_event_totals": dict(published_event_totals),
                "published_scheduler_mode_counts": dict(
                    published_scheduler_mode_counts
                ),
                "published_scheduler_state_counts": dict(
                    published_scheduler_state_counts
                ),
                "published_transition_totals": dict(
                    published_transition_totals
                ),
                "registry_revision": M31_PUBLISHED_REGISTRY_REVISION,
                "trace_dispatch_sha256": dispatch.dispatch_sha256,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class M31PublishedTraceDataset:
    """Complete deterministic Trace Explorer view for M31 evidence."""

    trace_dataset_id: str
    audit_batch: M31PublishedAuditBatch
    audit_report: M31PublishedAuditReport
    dispatch: M31PublishedDocumentDispatch
    measurement_contour: M31PublishedMeasurementContour
    contours: tuple[M31PublishedTraceContour, ...]
    active_zero_roles: tuple[str, ...]
    published_event_totals: tuple[tuple[str, int], ...]
    published_transition_totals: tuple[tuple[str, int], ...]
    published_scheduler_mode_counts: tuple[tuple[str, int], ...]
    published_scheduler_state_counts: tuple[tuple[str, int], ...]
    dataset_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.trace_dataset_id, "trace_dataset_id")
        if not isinstance(self.audit_batch, M31PublishedAuditBatch):
            raise M31PublishedTraceError(
                "audit_batch must be M31PublishedAuditBatch"
            )
        if (
            self.audit_batch.overall_status
            is not ValidationStatus.RECOGNIZED_VALID
            or self.audit_batch.failed_check_count != 0
        ):
            raise M31PublishedTraceError(
                "M31 audit batch must pass before Trace Explorer"
            )
        if not isinstance(self.audit_report, M31PublishedAuditReport):
            raise M31PublishedTraceError(
                "audit_report must be M31PublishedAuditReport"
            )
        expected_report = self.audit_batch.report_for_role(
            M31PublishedDocumentRole.EVIDENCE
        )
        if self.audit_report is not expected_report:
            raise M31PublishedTraceError(
                "audit_report is not exact M31 evidence audit result"
            )
        if (
            self.audit_report.overall_status
            is not ValidationStatus.RECOGNIZED_VALID
            or self.audit_report.failed_count != 0
        ):
            raise M31PublishedTraceError(
                "M31 evidence audit report must have no failures"
            )
        if not isinstance(self.dispatch, M31PublishedDocumentDispatch):
            raise M31PublishedTraceError(
                "dispatch must be M31PublishedDocumentDispatch"
            )
        expected_dispatch = self.audit_batch.dispatch_batch.dispatch_for(
            M31PublishedDocumentRole.EVIDENCE,
            ObservatoryMode.TRACE_EXPLORER,
        )
        if self.dispatch is not expected_dispatch:
            raise M31PublishedTraceError(
                "dispatch is not exact M31 Trace Explorer route"
            )
        if self.dispatch.mode is not ObservatoryMode.TRACE_EXPLORER:
            raise M31PublishedTraceError(
                "M31 trace dataset requires trace_explorer route"
            )
        if (
            self.dispatch.document is not self.audit_report.dispatch.document
            or self.dispatch.source_artifact
            is not self.audit_report.dispatch.source_artifact
        ):
            raise M31PublishedTraceError(
                "Trace Explorer and Artifact Auditor evidence sources differ"
            )
        expected_contour = self.dispatch.route.registration.measurement_contour
        if (
            self.measurement_contour is not expected_contour
            or self.measurement_contour
            is not M31PublishedMeasurementContour.PHASE_INTERFERENCE_ACTIVE_ZERO_THERMAL_EVIDENCE
        ):
            raise M31PublishedTraceError(
                "M31 evidence contour was replaced or aliased"
            )
        if (
            self.dispatch.document.identity.source_path != _EVIDENCE_PATH
            or self.dispatch.source_artifact.content_sha256
            != _EVIDENCE_RAW_SHA256
        ):
            raise M31PublishedTraceError("M31 evidence raw identity changed")
        root = _require_mapping(
            self.dispatch.parsed_artifact.root,
            "M31 evidence root",
        )
        if (
            root.get("schema") != _EVIDENCE_SCHEMA
            or root.get("kind") != _EVIDENCE_KIND
            or root.get("milestone") != "M31"
            or root.get("version") != "1.0.0"
        ):
            raise M31PublishedTraceError("unsupported M31 evidence identity")
        if (
            not isinstance(self.contours, tuple)
            or len(self.contours) != len(_TRACE_SOURCE_IDENTITIES)
            or any(
                not isinstance(contour, M31PublishedTraceContour)
                for contour in self.contours
            )
        ):
            raise M31PublishedTraceError(
                "contours must contain exactly two M31 trace contours"
            )
        if tuple(contour.contour_index for contour in self.contours) != (0, 1):
            raise M31PublishedTraceError("trace contour source order changed")
        if any(
            contour.trace_dispatch_sha256 != self.dispatch.dispatch_sha256
            for contour in self.contours
        ):
            raise M31PublishedTraceError(
                "trace contours do not bind the exact M31 dispatch"
            )
        boundary_sources = (
            self.audit_batch.dispatch_batch.registry_validation
            .boundary.provenance_sources
        )
        if any(
            not any(
                source is contour.provenance_source
                for source in boundary_sources
            )
            for contour in self.contours
        ):
            raise M31PublishedTraceError(
                "trace contour is not exact captured M31 provenance evidence"
            )
        evidence = _require_mapping(
            root.get("active_zero_execution_evidence"),
            "active_zero_execution_evidence",
        )
        declarations = _require_sequence(evidence.get("contours"), "contours")
        if len(declarations) != len(self.contours):
            raise M31PublishedTraceError(
                "published trace contour declaration count changed"
            )
        for contour, declaration_value in zip(
            self.contours,
            declarations,
            strict=True,
        ):
            declaration = _require_mapping(
                declaration_value,
                f"contours[{contour.contour_index}]",
            )
            if (
                declaration.get("path") != contour.source_path
                or declaration.get("raw_sha256") != contour.raw_sha256
                or declaration.get("record_count") != contour.record_count
                or _plain(declaration.get("execution_epochs"))
                != [epoch.source_payload() for epoch in contour.epochs]
            ):
                raise M31PublishedTraceError(
                    "projected contour differs from exact M31 declaration"
                )
        if self.active_zero_roles != _ACTIVE_ZERO_ROLES or _plain(
            evidence.get("active_zero_roles")
        ) != list(self.active_zero_roles):
            raise M31PublishedTraceError(
                "active-zero role declaration changed"
            )
        if self.published_event_totals != _ordered_counts(
            evidence.get("event_totals"),
            _EVENT_NAMES,
            "event_totals",
        ):
            raise M31PublishedTraceError("published event totals changed")
        if self.published_transition_totals != _ordered_counts(
            evidence.get("retained_transition_counts"),
            _TRANSITION_NAMES,
            "retained_transition_counts",
        ):
            raise M31PublishedTraceError(
                "published transition totals changed"
            )
        if self.published_scheduler_mode_counts != _ordered_counts(
            evidence.get("scheduler_mode_counts"),
            _SCHEDULER_MODE_ORDER,
            "scheduler_mode_counts",
        ):
            raise M31PublishedTraceError(
                "published scheduler mode totals changed"
            )
        if self.published_scheduler_state_counts != _ordered_counts(
            evidence.get("scheduler_state_counts"),
            _SCHEDULER_STATE_ORDER,
            "scheduler_state_counts",
        ):
            raise M31PublishedTraceError(
                "published scheduler state totals changed"
            )
        records = self.records
        exact_scalars = (
            ("evidence_class", "published_cycle_exact_execution_trace"),
            ("record_count", self.record_count),
            ("cell_observation_count", self.cell_snapshot_count),
            (
                "active_zero_after_observation_count",
                self.active_zero_after_observation_count,
            ),
            ("invariant_pass_records", self.invariant_pass_record_count),
        )
        if any(evidence.get(name) != expected for name, expected in exact_scalars):
            raise M31PublishedTraceError(
                "published scalar trace summary differs from exact projection"
            )
        if _plain(evidence.get("observed_ternary_domain")) != list(
            self.observed_ternary_domain
        ):
            raise M31PublishedTraceError(
                "published ternary domain differs from exact projection"
            )
        if self.event_totals != self.published_event_totals:
            raise M31PublishedTraceError(
                "published event totals differ from exact projection"
            )
        if self.retained_transition_totals != self.published_transition_totals:
            raise M31PublishedTraceError(
                "published transition totals differ from exact projection"
            )
        if self.scheduler_mode_counts != self.published_scheduler_mode_counts:
            raise M31PublishedTraceError(
                "published scheduler modes differ from exact projection"
            )
        if self.scheduler_state_counts != self.published_scheduler_state_counts:
            raise M31PublishedTraceError(
                "published scheduler states differ from exact projection"
            )
        if self.record_count != 100 or self.cell_snapshot_count != 800:
            raise M31PublishedTraceError("M31 trace inventory changed")
        if self.request_count != 200 or self.invariant_pass_record_count != 100:
            raise M31PublishedTraceError("M31 request or invariant inventory changed")
        if self.active_zero_after_observation_count != 702:
            raise M31PublishedTraceError(
                "M31 active-zero observation inventory changed"
            )
        if self.observed_scheduler_modes != _SCHEDULER_MODE_ORDER:
            raise M31PublishedTraceError(
                "M31 source-observed scheduler mode order changed"
            )
        if self.observed_ternary_domain != (-1, 0, 1):
            raise M31PublishedTraceError("M31 ternary domain changed")
        contract = _require_mapping(
            root.get("observatory_publication_contract"),
            "observatory_publication_contract",
        )
        if tuple(contract.items()) != _PUBLICATION_CONTRACT:
            raise M31PublishedTraceError(
                "M31 Observatory publication contract changed"
            )
        boundaries = _require_mapping(
            root.get("evidence_boundaries"),
            "evidence_boundaries",
        )
        if boundaries.get("historical_and_current_contours_separate") is not True:
            raise M31PublishedTraceError(
                "historical and current thermal contours were conflated"
            )
        _validate_sha256(self.dataset_sha256, "dataset_sha256")
        expected_digest = _dataset_sha256(
            self.audit_batch,
            self.audit_report,
            self.dispatch,
            self.measurement_contour,
            self.contours,
            self.active_zero_roles,
            self.published_event_totals,
            self.published_transition_totals,
            self.published_scheduler_mode_counts,
            self.published_scheduler_state_counts,
        )
        if self.dataset_sha256 != expected_digest:
            raise M31PublishedTraceError(
                "dataset_sha256 does not bind exact M31 evidence and traces"
            )
        if self.trace_dataset_id != str(
            uuid5(_DATASET_NAMESPACE, self.dataset_sha256)
        ):
            raise M31PublishedTraceError(
                "trace_dataset_id does not bind deterministic dataset digest"
            )
        if not records:
            raise M31PublishedTraceError("records must not be empty")

    @property
    def registry_revision(self) -> str:
        return self.audit_batch.dispatch_batch.registry_revision

    @property
    def evidence_raw_sha256(self) -> str:
        return self.dispatch.source_artifact.content_sha256

    @property
    def records(self) -> tuple[M31PublishedTraceRecord, ...]:
        return _flatten_records(self.contours)

    @property
    def trace_contour_count(self) -> int:
        return len(self.contours)

    @property
    def record_count(self) -> int:
        return len(self.records)

    @property
    def cell_snapshot_count(self) -> int:
        return sum(len(record.cells) for record in self.records)

    @property
    def request_count(self) -> int:
        return sum(len(record.requests) for record in self.records)

    @property
    def invariant_pass_record_count(self) -> int:
        return sum(record.invariant_all_pass for record in self.records)

    @property
    def active_zero_after_observation_count(self) -> int:
        return sum(
            cell.retained_state_after == 0
            for record in self.records
            for cell in record.cells
        )

    @property
    def observed_scheduler_modes(self) -> tuple[str, ...]:
        return _observed_scheduler_modes(self.contours)

    @property
    def observed_ternary_domain(self) -> tuple[int, ...]:
        return _observed_ternary_domain(self.records)

    @property
    def event_totals(self) -> tuple[tuple[str, int], ...]:
        return _event_totals(self.records)

    @property
    def retained_transition_totals(self) -> tuple[tuple[str, int], ...]:
        return _transition_totals(self.records)

    @property
    def scheduler_mode_counts(self) -> tuple[tuple[str, int], ...]:
        return _scheduler_counts(
            self.records,
            _SCHEDULER_MODE_ORDER,
            "mode",
        )

    @property
    def scheduler_state_counts(self) -> tuple[tuple[str, int], ...]:
        return _scheduler_counts(
            self.records,
            _SCHEDULER_STATE_ORDER,
            "state",
        )


def _build_request(
    value: object,
    expected_lane: int,
) -> M31PublishedTraceRequest:
    source = _require_mapping(value, f"request[{expected_lane}]")
    lane = _validate_nonnegative_integer(source.get("lane"), "request lane")
    if lane != expected_lane:
        raise M31PublishedTraceError("request lane order changed")
    return M31PublishedTraceRequest(
        lane=lane,
        valid=source.get("valid"),
        cell_index=_validate_nonnegative_integer(
            source.get("cell_index"),
            "request cell_index",
        ),
        target_state=_validate_ternary(
            source.get("target_state"),
            "request target_state",
        ),
        accepted=source.get("accepted"),
        rejected=source.get("rejected"),
    )


def _build_scheduler(value: object) -> M31PublishedSchedulerTrace:
    source = _require_mapping(value, "scheduler")
    counters = _require_mapping(source.get("counters_after"), "counters_after")
    return M31PublishedSchedulerTrace(
        mode=_validate_text(source.get("mode"), "scheduler mode"),
        state=_validate_text(source.get("state"), "scheduler state"),
        ticks_before=_validate_nonnegative_integer(
            source.get("ticks_before"),
            "ticks_before",
        ),
        ticks_after=_validate_positive_integer(
            source.get("ticks_after"),
            "ticks_after",
        ),
        counters_after=tuple(
            (
                name,
                _validate_nonnegative_integer(
                    counters.get(name),
                    f"scheduler counter {name}",
                ),
            )
            for name in _SCHEDULER_COUNTER_NAMES
        ),
    )


def _build_record(
    dispatch: M31PublishedDocumentDispatch,
    contour_index: int,
    source_path: str,
    raw_sha256: str,
    value: object,
    expected_sequence: int,
) -> M31PublishedTraceRecord:
    source = _require_mapping(value, f"records[{expected_sequence}]")
    sequence = _validate_nonnegative_integer(source.get("sequence"), "sequence")
    if sequence != expected_sequence:
        raise M31PublishedTraceError("record sequence order changed")
    retained_before = _integer_tuple(
        source.get("retained_state_before"),
        "retained_state_before",
        length=8,
        ternary=True,
    )
    retained_after = _integer_tuple(
        source.get("retained_state_after"),
        "retained_state_after",
        length=8,
        ternary=True,
    )
    pending_before = _integer_tuple(
        source.get("pending_route_before"),
        "pending_route_before",
        length=8,
        ternary=True,
    )
    pending_after = _integer_tuple(
        source.get("pending_route_after"),
        "pending_route_after",
        length=8,
        ternary=True,
    )
    targets = _integer_tuple(
        source.get("phase_derived_targets"),
        "phase_derived_targets",
        length=8,
        ternary=True,
    )
    accepted_cell_ids = _integer_tuple(
        source.get("accepted_cell_ids"),
        "accepted_cell_ids",
    )
    accepted_change_cell_ids = _integer_tuple(
        source.get("accepted_change_cell_ids"),
        "accepted_change_cell_ids",
    )
    neutral_routed_cell_ids = _integer_tuple(
        source.get("neutral_routed_cell_ids"),
        "neutral_routed_cell_ids",
    )
    accepted_set = frozenset(accepted_cell_ids)
    changed_set = frozenset(accepted_change_cell_ids)
    neutral_set = frozenset(neutral_routed_cell_ids)
    cells = tuple(
        M31PublishedTraceCell(
            cell_id=cell_id,
            phase_derived_target=targets[cell_id],
            retained_state_before=retained_before[cell_id],
            retained_state_after=retained_after[cell_id],
            pending_route_before=pending_before[cell_id],
            pending_route_after=pending_after[cell_id],
            accepted=cell_id in accepted_set,
            accepted_change=cell_id in changed_set,
            neutral_routed=cell_id in neutral_set,
        )
        for cell_id in range(8)
    )
    source_requests = _require_sequence(source.get("requests"), "requests")
    if len(source_requests) != 2:
        raise M31PublishedTraceError("M16 record must contain two request lanes")
    requests = tuple(
        _build_request(request, lane)
        for lane, request in enumerate(source_requests)
    )
    capacity = _require_mapping(
        source.get("transition_capacity"),
        "transition_capacity",
    )
    telemetry = _require_mapping(source.get("telemetry"), "telemetry")
    events = _require_mapping(source.get("events"), "events")
    if frozenset(events) != frozenset(_EVENT_NAMES):
        raise M31PublishedTraceError("event counter inventory changed")
    invariants = _require_mapping(source.get("invariants"), "invariants")
    flags = _require_sequence(invariants.get("flags"), "invariant flags")
    invariant_names: list[str] = []
    for index, flag_value in enumerate(flags):
        flag = _require_mapping(flag_value, f"invariant flags[{index}]")
        invariant_names.append(
            _validate_text(flag.get("name"), f"invariant flags[{index}].name")
        )
        if flag.get("pass") is not True:
            raise M31PublishedTraceError("M16 invariant flag did not pass")
    source_sha = _record_source_sha256(source)
    record_id = str(
        uuid5(
            _RECORD_NAMESPACE,
            (
                f"{dispatch.dispatch_sha256}:{source_path}:{raw_sha256}:"
                f"{sequence}:{source_sha}"
            ),
        )
    )
    return M31PublishedTraceRecord(
        trace_record_id=record_id,
        contour_index=contour_index,
        sequence=sequence,
        execution_epoch=_validate_nonnegative_integer(
            source.get("execution_epoch"),
            "execution_epoch",
        ),
        core_ready=source.get("core_ready"),
        scheduler=_build_scheduler(source.get("scheduler")),
        requests=requests,
        cells=cells,
        accepted_cell_ids=accepted_cell_ids,
        accepted_change_cell_ids=accepted_change_cell_ids,
        neutral_routed_cell_ids=neutral_routed_cell_ids,
        capacity_limit=_validate_positive_integer(
            capacity.get("capacity_limit"),
            "capacity_limit",
        ),
        accepted_changes=_validate_nonnegative_integer(
            capacity.get("accepted_changes"),
            "accepted_changes",
        ),
        capacity_remaining=_validate_nonnegative_integer(
            capacity.get("capacity_remaining"),
            "capacity_remaining",
        ),
        capacity_exhausted=capacity.get("capacity_exhausted"),
        switch_load_numerator=_validate_nonnegative_integer(
            telemetry.get("switch_load_numerator"),
            "switch_load_numerator",
        ),
        switch_load_denominator=_validate_positive_integer(
            telemetry.get("switch_load_denominator"),
            "switch_load_denominator",
        ),
        switch_load_q16=_validate_nonnegative_integer(
            telemetry.get("switch_load_q16"),
            "switch_load_q16",
        ),
        event_counts=tuple(
            (
                name,
                _validate_nonnegative_integer(
                    events.get(name),
                    f"event {name}",
                ),
            )
            for name in _EVENT_NAMES
        ),
        invariant_names=tuple(invariant_names),
        invariant_all_pass=invariants.get("all_pass"),
        source_location=SourceLocation(
            json_path=f"$.records[{sequence}]",
            array_index=sequence,
            package_member=source_path,
            source_record_ordinal=sequence + 1,
        ),
        source_record_sha256=source_sha,
    )


def _build_epoch(
    value: object,
    contour_index: int,
    source_path: str,
    expected_epoch: int,
) -> M31PublishedExecutionEpoch:
    source = _require_mapping(value, f"execution_epochs[{expected_epoch}]")
    epoch = _validate_nonnegative_integer(source.get("epoch"), "epoch")
    if epoch != expected_epoch:
        raise M31PublishedTraceError("execution epoch order changed")
    return M31PublishedExecutionEpoch(
        contour_index=contour_index,
        epoch=epoch,
        mode=_validate_text(source.get("mode"), "epoch mode"),
        record_count=_validate_positive_integer(
            source.get("record_count"),
            "record_count",
        ),
        source_location=SourceLocation(
            json_path=f"$.execution_epochs[{epoch}]",
            array_index=epoch,
            package_member=source_path,
            source_record_ordinal=epoch + 1,
        ),
    )


def _provenance_for_path(
    audit_batch: M31PublishedAuditBatch,
    source_path: str,
) -> M31PublishedProvenanceSource:
    sources = (
        audit_batch.dispatch_batch.registry_validation
        .boundary.provenance_sources
    )
    matches = tuple(source for source in sources if source.source_path == source_path)
    if len(matches) != 1:
        raise M31PublishedTraceError(
            f"exact trace provenance source is absent: {source_path}"
        )
    return matches[0]


def _build_contour(
    audit_batch: M31PublishedAuditBatch,
    dispatch: M31PublishedDocumentDispatch,
    contour_index: int,
    declaration_value: object,
) -> M31PublishedTraceContour:
    declaration = _require_mapping(
        declaration_value,
        f"contours[{contour_index}]",
    )
    expected = _TRACE_SOURCE_IDENTITIES[contour_index]
    source_path, raw_sha256, schema_identifier, trace_kind, layer = expected
    if (
        declaration.get("path") != source_path
        or declaration.get("raw_sha256") != raw_sha256
    ):
        raise M31PublishedTraceError(
            "M31 trace contour path or raw digest changed"
        )
    provenance = _provenance_for_path(audit_batch, source_path)
    if provenance.source_artifact.content_sha256 != raw_sha256:
        raise M31PublishedTraceError(
            "captured trace provenance digest differs from M31 declaration"
        )
    parsed = parse_json_artifact(provenance.source_artifact)
    root = _require_mapping(parsed.root, f"trace[{contour_index}] root")
    if (
        root.get("schema") != schema_identifier
        or root.get("kind") != trace_kind
        or root.get("layer") != layer
        or root.get("source_release") != _SOURCE_RELEASE
    ):
        raise M31PublishedTraceError("unsupported trace provenance identity")
    source_epochs = _require_sequence(
        root.get("execution_epochs"),
        "execution_epochs",
    )
    epochs = tuple(
        _build_epoch(epoch, contour_index, source_path, index)
        for index, epoch in enumerate(source_epochs)
    )
    source_records = _require_sequence(root.get("records"), "records")
    records = tuple(
        _build_record(
            dispatch,
            contour_index,
            source_path,
            raw_sha256,
            record,
            index,
        )
        for index, record in enumerate(source_records)
    )
    if declaration.get("record_count") != len(records) or _plain(
        declaration.get("execution_epochs")
    ) != [epoch.source_payload() for epoch in epochs]:
        raise M31PublishedTraceError(
            "M31 trace declaration differs from captured source inventory"
        )
    source_record_digest = _records_document_sha256(source_records)
    contours = _require_mapping(
        root.get("measurement_contours"),
        "measurement_contours",
    )
    m15 = _require_mapping(
        contours.get("m15_semantic_reference"),
        "m15_semantic_reference",
    )
    physical = _require_mapping(
        contours.get("physical_measurement"),
        "physical_measurement",
    )
    m15_status = _validate_text(
        m15.get("correlation_status"),
        "m15 correlation status",
    )
    physical_availability = _validate_text(
        physical.get("availability"),
        "physical measurement availability",
    )
    physical_status = _validate_text(
        physical.get("correlation_status"),
        "physical measurement correlation status",
    )
    digest = _contour_sha256(
        dispatch.dispatch_sha256,
        contour_index,
        source_path,
        raw_sha256,
        schema_identifier,
        trace_kind,
        layer,
        epochs,
        records,
        source_record_digest,
        m15_status,
        physical_availability,
        physical_status,
    )
    return M31PublishedTraceContour(
        trace_contour_id=str(uuid5(_CONTOUR_NAMESPACE, digest)),
        trace_dispatch_sha256=dispatch.dispatch_sha256,
        contour_index=contour_index,
        provenance_source=provenance,
        parsed_artifact=parsed,
        source_path=source_path,
        raw_sha256=raw_sha256,
        schema_identifier=schema_identifier,
        trace_kind=trace_kind,
        layer=layer,
        epochs=epochs,
        records=records,
        source_record_digest=source_record_digest,
        m15_correlation_status=m15_status,
        physical_measurement_availability=physical_availability,
        physical_measurement_correlation_status=physical_status,
        contour_sha256=digest,
    )


def build_m31_published_trace_dataset(
    audit_batch: M31PublishedAuditBatch,
) -> M31PublishedTraceDataset:
    """Build the sole M31 Trace Explorer dataset from exact audit evidence."""

    if not isinstance(audit_batch, M31PublishedAuditBatch):
        raise M31PublishedTraceError(
            "audit_batch must be M31PublishedAuditBatch"
        )
    if (
        audit_batch.overall_status is not ValidationStatus.RECOGNIZED_VALID
        or audit_batch.failed_check_count != 0
    ):
        raise M31PublishedTraceError(
            "M31 audit batch must pass before Trace Explorer"
        )
    audit_report = audit_batch.report_for_role(
        M31PublishedDocumentRole.EVIDENCE
    )
    dispatch = audit_batch.dispatch_batch.dispatch_for(
        M31PublishedDocumentRole.EVIDENCE,
        ObservatoryMode.TRACE_EXPLORER,
    )
    if (
        dispatch.document is not audit_report.dispatch.document
        or dispatch.source_artifact is not audit_report.dispatch.source_artifact
    ):
        raise M31PublishedTraceError(
            "audit report and Trace Explorer route do not share exact evidence"
        )
    root = _require_mapping(dispatch.parsed_artifact.root, "M31 evidence root")
    if (
        root.get("schema") != _EVIDENCE_SCHEMA
        or root.get("kind") != _EVIDENCE_KIND
    ):
        raise M31PublishedTraceError("unsupported M31 evidence identity")
    evidence = _require_mapping(
        root.get("active_zero_execution_evidence"),
        "active_zero_execution_evidence",
    )
    declarations = _require_sequence(evidence.get("contours"), "contours")
    if len(declarations) != len(_TRACE_SOURCE_IDENTITIES):
        raise M31PublishedTraceError(
            "M31 evidence must declare exactly two trace contours"
        )
    contours = tuple(
        _build_contour(audit_batch, dispatch, index, declaration)
        for index, declaration in enumerate(declarations)
    )
    active_zero_roles = tuple(
        _validate_text(role, f"active_zero_roles[{index}]")
        for index, role in enumerate(
            _require_sequence(
                evidence.get("active_zero_roles"),
                "active_zero_roles",
            )
        )
    )
    event_totals = _ordered_counts(
        evidence.get("event_totals"),
        _EVENT_NAMES,
        "event_totals",
    )
    transition_totals = _ordered_counts(
        evidence.get("retained_transition_counts"),
        _TRANSITION_NAMES,
        "retained_transition_counts",
    )
    scheduler_mode_counts = _ordered_counts(
        evidence.get("scheduler_mode_counts"),
        _SCHEDULER_MODE_ORDER,
        "scheduler_mode_counts",
    )
    scheduler_state_counts = _ordered_counts(
        evidence.get("scheduler_state_counts"),
        _SCHEDULER_STATE_ORDER,
        "scheduler_state_counts",
    )
    contour = dispatch.route.registration.measurement_contour
    digest = _dataset_sha256(
        audit_batch,
        audit_report,
        dispatch,
        contour,
        contours,
        active_zero_roles,
        event_totals,
        transition_totals,
        scheduler_mode_counts,
        scheduler_state_counts,
    )
    return M31PublishedTraceDataset(
        trace_dataset_id=str(uuid5(_DATASET_NAMESPACE, digest)),
        audit_batch=audit_batch,
        audit_report=audit_report,
        dispatch=dispatch,
        measurement_contour=contour,
        contours=contours,
        active_zero_roles=active_zero_roles,
        published_event_totals=event_totals,
        published_transition_totals=transition_totals,
        published_scheduler_mode_counts=scheduler_mode_counts,
        published_scheduler_state_counts=scheduler_state_counts,
        dataset_sha256=digest,
    )


def explore_m31_published_documents(
    upstream_root: str | Path,
    *,
    loaded_at: datetime | None = None,
) -> M31PublishedTraceDataset:
    """Validate M31 intake through audit and build the trace dataset."""

    return build_m31_published_trace_dataset(
        audit_m31_published_documents(
            upstream_root,
            loaded_at=loaded_at,
        )
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one deterministic read-only Trace Explorer dataset from "
            "the exact audited FRP M31 publication."
        )
    )
    parser.add_argument("--upstream-root", required=True, type=Path)
    arguments = parser.parse_args()
    result = explore_m31_published_documents(arguments.upstream_root)
    print("FRP Observatory M31 published Trace Explorer: PASS")
    print(f"registry_revision={result.registry_revision}")
    print(f"evidence_raw_sha256={result.evidence_raw_sha256}")
    print(f"trace_contours={result.trace_contour_count}")
    print(f"records={result.record_count}")
    print(f"cell_snapshots={result.cell_snapshot_count}")
    print(f"requests={result.request_count}")
    print(f"invariant_pass_records={result.invariant_pass_record_count}")
    print(
        "active_zero_after_observations="
        f"{result.active_zero_after_observation_count}"
    )
    print(
        "observed_scheduler_modes="
        + ",".join(result.observed_scheduler_modes)
    )
    print(
        "observed_ternary_domain="
        + "/".join(str(value) for value in result.observed_ternary_domain)
    )
    print("event_totals=" + json.dumps(dict(result.event_totals), sort_keys=True))
    print(
        "retained_transition_totals="
        + json.dumps(dict(result.retained_transition_totals), sort_keys=True)
    )
    for contour in result.contours:
        print(
            f"contour[{contour.contour_index}]="
            f"{contour.source_path}|records={contour.record_count}|"
            f"source_record_digest={contour.source_record_digest}|"
            f"contour_sha256={contour.contour_sha256}"
        )
    print(f"dataset_sha256={result.dataset_sha256}")
    print("source_execution=forbidden")
    print("metric_normalization=forbidden")
    print("thermal_contour_merging=forbidden")
    print("semantic_reimplementation=forbidden")
    print("source_mutation=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
