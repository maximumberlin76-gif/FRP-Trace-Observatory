"""Read-only Trace Explorer projection for the exact FRP M16 publication.

This module is the second M30 mode consumer.  It begins only after the complete
M6 published Artifact Auditor batch has passed, resolves the sole M5
``trace_explorer`` route, and projects the four retained M16 execution records
without executing source content or assigning a legacy measurement contour.

The projection keeps source order, exact ``-1/0/1`` values, active-neutral
routing, scheduler text, request-lane order, transition-capacity relations,
event counters, invariant names, and source coordinates.  M27 and both M28
members remain outside this consumer because the M3 registry does not route
them to Trace Explorer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid5

from artifact_auditor.audit_report import SourceLocation, ValidationStatus
from artifact_auditor.m30_published_auditor import (
    PublishedAuditBatch,
    PublishedAuditReport,
    audit_m30_published_archive,
)
from parsers.m30_published_dispatch import PublishedModeDispatch
from schemas.m30_published_registry import PublishedMeasurementContour
from schemas.registry import ObservatoryMode


__all__ = [
    "M30PublishedTraceDataset",
    "M30PublishedTraceError",
    "PublishedExecutionEpoch",
    "PublishedSchedulerTrace",
    "PublishedTraceCell",
    "PublishedTraceRecord",
    "PublishedTraceRequest",
    "build_m30_published_trace_dataset",
    "explore_m30_published_archive",
]


_MEMBER_ID: Final = "m16-fpga-preparation-execution-trace"
_SCHEMA_IDENTIFIER: Final = (
    "frp.m16.fpga_preparation_execution_trace.v2.1.0"
)
_TRACE_KIND: Final = "m16_fpga_preparation_execution_trace"
_SOURCE_RELEASE: Final = "FRP v1.8.0 / M16"
_SOURCE_PATH: Final = (
    "artifacts/m19/execution/m16-fpga-preparation-execution-trace.json"
)
_TERNARY_DOMAIN: Final = frozenset({-1, 0, 1})
_HEX64: Final = re.compile(r"^[0-9a-f]{64}$")
_DATASET_NAMESPACE: Final = UUID("c85ec707-2815-55ad-a0a8-65be12f46ddd")
_RECORD_NAMESPACE: Final = UUID("57984164-2501-53a2-8819-0d7c44532341")
_EVENT_NAMES: Final = (
    "actual_direct_events",
    "neutral_routed_events",
    "prevented_direct_events",
    "queue_overflow_events",
    "requested_direct_events",
    "reserved_state_events",
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
_VALID_SCHEDULER_MODES: Final = frozenset({"free", "1/7", "7/1"})
_VALID_SCHEDULER_STATES: Final = frozenset(
    {"free", "balance", "commit", "excite", "neutralize"}
)


class M30PublishedTraceError(ValueError):
    """Raised when the published Trace Explorer boundary is violated."""


def _validate_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise M30PublishedTraceError(f"{field} must be a string")
    if not value or value != value.strip() or "\x00" in value:
        raise M30PublishedTraceError(
            f"{field} must be nonempty without outer whitespace or NUL"
        )
    return value


def _validate_nonnegative_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise M30PublishedTraceError(
            f"{field} must be a nonnegative integer"
        )
    return value


def _validate_positive_integer(value: object, field: str) -> int:
    result = _validate_nonnegative_integer(value, field)
    if result == 0:
        raise M30PublishedTraceError(f"{field} must be positive")
    return result


def _validate_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise M30PublishedTraceError(
            f"{field} must be lowercase hexadecimal SHA-256"
        )
    return value


def _validate_uuid(value: object, field: str) -> str:
    text = _validate_text(value, field)
    try:
        UUID(text)
    except ValueError as exc:
        raise M30PublishedTraceError(f"{field} must be a UUID") from exc
    return text


def _validate_ternary(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise M30PublishedTraceError(f"{field} must be an integer")
    if value not in _TERNARY_DOMAIN:
        raise M30PublishedTraceError(f"{field} must remain in -1/0/1")
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
        raise M30PublishedTraceError(f"{field} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise M30PublishedTraceError(f"{field} keys must be strings")
    return value


def _require_sequence(value: object, field: str) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise M30PublishedTraceError(f"{field} must be an array")
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
        raise M30PublishedTraceError(
            f"{field} must contain exactly {length} values"
        )
    validator = _validate_ternary if ternary else _validate_nonnegative_integer
    return tuple(
        validator(item, f"{field}[{index}]")
        for index, item in enumerate(sequence)
    )


def _validate_sorted_cell_ids(value: tuple[int, ...], field: str) -> None:
    if tuple(sorted(set(value))) != value:
        raise M30PublishedTraceError(
            f"{field} must contain unique source-ordered cell identifiers"
        )
    if any(cell_id >= 8 for cell_id in value):
        raise M30PublishedTraceError(f"{field} cell identifier is out of range")


@dataclass(frozen=True, slots=True)
class PublishedTraceRequest:
    """One exact M16 request-lane record in source lane order."""

    lane: int
    valid: bool
    cell_index: int
    target_state: int
    accepted: bool
    rejected: bool

    def __post_init__(self) -> None:
        if self.lane not in (0, 1):
            raise M30PublishedTraceError("request lane must be 0 or 1")
        if not isinstance(self.valid, bool):
            raise M30PublishedTraceError("request valid must be boolean")
        _validate_nonnegative_integer(self.cell_index, "request cell_index")
        if self.cell_index >= 8:
            raise M30PublishedTraceError("request cell_index is out of range")
        _validate_ternary(self.target_state, "request target_state")
        if not isinstance(self.accepted, bool) or not isinstance(
            self.rejected, bool
        ):
            raise M30PublishedTraceError(
                "request accepted and rejected must be boolean"
            )
        if self.accepted and self.rejected:
            raise M30PublishedTraceError(
                "one request cannot be accepted and rejected"
            )
        if not self.valid and (self.accepted or self.rejected):
            raise M30PublishedTraceError(
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
class PublishedSchedulerTrace:
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
            raise M30PublishedTraceError("unknown scheduler mode")
        if self.state not in _VALID_SCHEDULER_STATES:
            raise M30PublishedTraceError("unknown scheduler state")
        _validate_nonnegative_integer(self.ticks_before, "ticks_before")
        _validate_positive_integer(self.ticks_after, "ticks_after")
        if self.ticks_after != self.ticks_before + 1:
            raise M30PublishedTraceError(
                "scheduler ticks_after must equal ticks_before plus one"
            )
        if not isinstance(self.counters_after, tuple):
            raise M30PublishedTraceError("counters_after must be a tuple")
        names = tuple(name for name, _ in self.counters_after)
        if names != _SCHEDULER_COUNTER_NAMES:
            raise M30PublishedTraceError(
                "scheduler counters must retain the exact source key order"
            )
        for name, value in self.counters_after:
            _validate_text(name, "scheduler counter name")
            _validate_nonnegative_integer(value, f"scheduler counter {name}")
        if sum(value for _, value in self.counters_after) != self.ticks_after:
            raise M30PublishedTraceError(
                "scheduler counter sum must equal ticks_after"
            )
        permitted_states = {
            "free": frozenset({"free"}),
            "1/7": frozenset({"excite", "neutralize"}),
            "7/1": frozenset({"balance", "commit"}),
        }
        if self.state not in permitted_states[self.mode]:
            raise M30PublishedTraceError(
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
class PublishedTraceCell:
    """One source-linked cell projection for one M16 execution record."""

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
            raise M30PublishedTraceError("cell_id is out of range")
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
                raise M30PublishedTraceError(f"{field} must be boolean")
        if (
            self.retained_state_before,
            self.retained_state_after,
        ) in ((-1, 1), (1, -1)):
            raise M30PublishedTraceError(
                "direct opposite retained-state transitions are forbidden"
            )
        if self.neutral_routed:
            if self.retained_state_after != 0:
                raise M30PublishedTraceError(
                    "a neutral-routed first leg must retain active neutral 0"
                )
            if self.pending_route_after not in (-1, 1):
                raise M30PublishedTraceError(
                    "a neutral-routed first leg must retain pending polarity"
                )


@dataclass(frozen=True, slots=True)
class PublishedTraceRecord:
    """One immutable M16 execution record and its complete projection."""

    trace_record_id: str
    sequence: int
    execution_epoch: int
    core_ready: bool
    scheduler: PublishedSchedulerTrace
    requests: tuple[PublishedTraceRequest, ...]
    cells: tuple[PublishedTraceCell, ...]
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
        _validate_nonnegative_integer(self.sequence, "sequence")
        _validate_nonnegative_integer(self.execution_epoch, "execution_epoch")
        if not isinstance(self.core_ready, bool) or not self.core_ready:
            raise M30PublishedTraceError("core_ready must remain true")
        if not isinstance(self.scheduler, PublishedSchedulerTrace):
            raise M30PublishedTraceError(
                "scheduler must be PublishedSchedulerTrace"
            )
        if (
            not isinstance(self.requests, tuple)
            or tuple(request.lane for request in self.requests) != (0, 1)
        ):
            raise M30PublishedTraceError(
                "requests must retain exact lane order 0, 1"
            )
        if any(
            not isinstance(request, PublishedTraceRequest)
            for request in self.requests
        ):
            raise M30PublishedTraceError(
                "requests must contain PublishedTraceRequest values"
            )
        if (
            not isinstance(self.cells, tuple)
            or tuple(cell.cell_id for cell in self.cells) != tuple(range(8))
        ):
            raise M30PublishedTraceError(
                "cells must retain exact source order 0 through 7"
            )
        if any(not isinstance(cell, PublishedTraceCell) for cell in self.cells):
            raise M30PublishedTraceError(
                "cells must contain PublishedTraceCell values"
            )
        for field, value in (
            ("accepted_cell_ids", self.accepted_cell_ids),
            ("accepted_change_cell_ids", self.accepted_change_cell_ids),
            ("neutral_routed_cell_ids", self.neutral_routed_cell_ids),
        ):
            if not isinstance(value, tuple):
                raise M30PublishedTraceError(f"{field} must be a tuple")
            _validate_sorted_cell_ids(value, field)
        if self.accepted_cell_ids != tuple(
            cell.cell_id for cell in self.cells if cell.accepted
        ):
            raise M30PublishedTraceError(
                "accepted_cell_ids differ from cell projection"
            )
        if self.accepted_change_cell_ids != tuple(
            cell.cell_id for cell in self.cells if cell.accepted_change
        ):
            raise M30PublishedTraceError(
                "accepted_change_cell_ids differ from cell projection"
            )
        if self.neutral_routed_cell_ids != tuple(
            cell.cell_id for cell in self.cells if cell.neutral_routed
        ):
            raise M30PublishedTraceError(
                "neutral_routed_cell_ids differ from cell projection"
            )
        _validate_positive_integer(self.capacity_limit, "capacity_limit")
        _validate_nonnegative_integer(self.accepted_changes, "accepted_changes")
        _validate_nonnegative_integer(
            self.capacity_remaining, "capacity_remaining"
        )
        if self.accepted_changes > self.capacity_limit:
            raise M30PublishedTraceError(
                "accepted_changes exceeds capacity_limit"
            )
        if self.capacity_remaining != self.capacity_limit - self.accepted_changes:
            raise M30PublishedTraceError(
                "capacity_remaining relation is invalid"
            )
        if not isinstance(self.capacity_exhausted, bool):
            raise M30PublishedTraceError("capacity_exhausted must be boolean")
        if self.capacity_exhausted is not (self.capacity_remaining == 0):
            raise M30PublishedTraceError(
                "capacity_exhausted differs from capacity_remaining"
            )
        if len(self.accepted_change_cell_ids) != self.accepted_changes:
            raise M30PublishedTraceError(
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
            raise M30PublishedTraceError(
                "switch_load_numerator differs from accepted_changes"
            )
        if self.switch_load_q16 != (
            self.switch_load_numerator * 65536 // self.switch_load_denominator
        ):
            raise M30PublishedTraceError("switch_load_q16 relation is invalid")
        if not isinstance(self.event_counts, tuple):
            raise M30PublishedTraceError("event_counts must be a tuple")
        if tuple(name for name, _ in self.event_counts) != _EVENT_NAMES:
            raise M30PublishedTraceError(
                "event counters must retain the exact source key order"
            )
        for name, value in self.event_counts:
            _validate_nonnegative_integer(value, f"event {name}")
        for invariant in (
            "actual_direct_events",
            "reserved_state_events",
            "queue_overflow_events",
        ):
            if self.event_count(invariant) != 0:
                raise M30PublishedTraceError(
                    f"{invariant} must remain zero"
                )
        if self.invariant_names != _INVARIANT_NAMES:
            raise M30PublishedTraceError(
                "invariant names must retain exact source order"
            )
        if not isinstance(self.invariant_all_pass, bool) or not (
            self.invariant_all_pass
        ):
            raise M30PublishedTraceError("all invariant flags must pass")
        if not isinstance(self.source_location, SourceLocation):
            raise M30PublishedTraceError(
                "source_location must be SourceLocation"
            )
        _validate_sha256(self.source_record_sha256, "source_record_sha256")

    def event_count(self, name: str) -> int:
        """Return one exact named source event counter."""

        _validate_text(name, "event name")
        for current, value in self.event_counts:
            if current == name:
                return value
        raise M30PublishedTraceError(f"unknown event counter: {name!r}")

    @property
    def retained_state_before(self) -> tuple[int, ...]:
        """Return the exact source-order retained state before execution."""

        return tuple(cell.retained_state_before for cell in self.cells)

    @property
    def retained_state_after(self) -> tuple[int, ...]:
        """Return the exact source-order retained state after execution."""

        return tuple(cell.retained_state_after for cell in self.cells)

    @property
    def pending_route_before(self) -> tuple[int, ...]:
        """Return exact source-order pending routes before execution."""

        return tuple(cell.pending_route_before for cell in self.cells)

    @property
    def pending_route_after(self) -> tuple[int, ...]:
        """Return exact source-order pending routes after execution."""

        return tuple(cell.pending_route_after for cell in self.cells)

    @property
    def phase_derived_targets(self) -> tuple[int, ...]:
        """Return exact source-order phase-derived targets."""

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
class PublishedExecutionEpoch:
    """One exact source execution-epoch declaration."""

    epoch: int
    mode: str
    record_count: int
    source_location: SourceLocation

    def __post_init__(self) -> None:
        _validate_nonnegative_integer(self.epoch, "epoch")
        _validate_text(self.mode, "epoch mode")
        if self.mode not in _VALID_SCHEDULER_MODES:
            raise M30PublishedTraceError("unknown execution epoch mode")
        _validate_positive_integer(self.record_count, "record_count")
        if not isinstance(self.source_location, SourceLocation):
            raise M30PublishedTraceError(
                "epoch source_location must be SourceLocation"
            )

    def source_payload(self) -> dict[str, object]:
        """Reconstruct the exact upstream epoch declaration."""

        return {
            "epoch": self.epoch,
            "mode": self.mode,
            "record_count": self.record_count,
        }


def _record_payload(record: PublishedTraceRecord) -> dict[str, object]:
    return {
        "execution_epoch": record.execution_epoch,
        "sequence": record.sequence,
        "source_record_sha256": record.source_record_sha256,
        "trace_record_id": record.trace_record_id,
    }


def _dataset_sha256(
    audit_batch: PublishedAuditBatch,
    audit_report: PublishedAuditReport,
    dispatch: PublishedModeDispatch,
    contour: PublishedMeasurementContour,
    epochs: tuple[PublishedExecutionEpoch, ...],
    records: tuple[PublishedTraceRecord, ...],
    source_record_digest: str,
    m15_correlation_status: str,
    physical_measurement_availability: str,
    physical_measurement_correlation_status: str,
) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "archive_sha256": dispatch.member.archive_sha256,
                "audit_batch_sha256": audit_batch.batch_sha256,
                "audit_report_sha256": audit_report.report_sha256,
                "dispatch_sha256": dispatch.dispatch_sha256,
                "epochs": [epoch.source_payload() for epoch in epochs],
                "m15_correlation_status": m15_correlation_status,
                "measurement_contour": contour.value,
                "member_id": dispatch.member_id,
                "physical_measurement_availability": (
                    physical_measurement_availability
                ),
                "physical_measurement_correlation_status": (
                    physical_measurement_correlation_status
                ),
                "raw_sha256": dispatch.member.registration.raw_sha256,
                "records": [_record_payload(record) for record in records],
                "registry_revision": dispatch.member.registry_revision,
                "schema_identifier": (
                    dispatch.member.registration.schema_identifier
                ),
                "source_record_digest": source_record_digest,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class M30PublishedTraceDataset:
    """Complete deterministic Trace Explorer view for one M16 publication."""

    trace_dataset_id: str
    audit_batch: PublishedAuditBatch
    audit_report: PublishedAuditReport
    dispatch: PublishedModeDispatch
    measurement_contour: PublishedMeasurementContour
    epochs: tuple[PublishedExecutionEpoch, ...]
    records: tuple[PublishedTraceRecord, ...]
    source_record_digest: str
    m15_correlation_status: str
    physical_measurement_availability: str
    physical_measurement_correlation_status: str
    dataset_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.trace_dataset_id, "trace_dataset_id")
        if not isinstance(self.audit_batch, PublishedAuditBatch):
            raise M30PublishedTraceError(
                "audit_batch must be PublishedAuditBatch"
            )
        if self.audit_batch.overall_status is not (
            ValidationStatus.RECOGNIZED_VALID
        ):
            raise M30PublishedTraceError("M6 audit batch must be valid")
        if not isinstance(self.audit_report, PublishedAuditReport):
            raise M30PublishedTraceError(
                "audit_report must be PublishedAuditReport"
            )
        expected_report = self.audit_batch.report_for_member(_MEMBER_ID)
        if self.audit_report is not expected_report:
            raise M30PublishedTraceError(
                "audit_report is not exact M6 M16 report evidence"
            )
        if self.audit_report.overall_status is not (
            ValidationStatus.RECOGNIZED_VALID
        ) or self.audit_report.failed_count != 0:
            raise M30PublishedTraceError("M16 M6 report must have no failures")
        if not isinstance(self.dispatch, PublishedModeDispatch):
            raise M30PublishedTraceError(
                "dispatch must be PublishedModeDispatch"
            )
        expected_dispatch = self.audit_batch.dispatch_batch.dispatch_for(
            _MEMBER_ID,
            ObservatoryMode.TRACE_EXPLORER,
        )
        if self.dispatch is not expected_dispatch:
            raise M30PublishedTraceError(
                "dispatch is not the exact M5 Trace Explorer route"
            )
        if self.dispatch.mode is not ObservatoryMode.TRACE_EXPLORER:
            raise M30PublishedTraceError(
                "published trace dataset requires trace_explorer route"
            )
        if self.dispatch.member is not self.audit_report.dispatch.member:
            raise M30PublishedTraceError(
                "Trace Explorer and Artifact Auditor sources differ"
            )
        expected_contour = self.dispatch.member.registration.measurement_contour
        if self.measurement_contour is not expected_contour or (
            self.measurement_contour
            is not PublishedMeasurementContour.M16_FPGA_PREPARATION_EXECUTION
        ):
            raise M30PublishedTraceError(
                "M16 published measurement contour was replaced or aliased"
            )
        if not isinstance(self.epochs, tuple) or not self.epochs:
            raise M30PublishedTraceError("epochs must be a nonempty tuple")
        if any(
            not isinstance(epoch, PublishedExecutionEpoch)
            for epoch in self.epochs
        ):
            raise M30PublishedTraceError(
                "epochs must contain PublishedExecutionEpoch values"
            )
        if tuple(epoch.epoch for epoch in self.epochs) != tuple(
            range(len(self.epochs))
        ):
            raise M30PublishedTraceError(
                "execution epochs must retain contiguous source order"
            )
        if not isinstance(self.records, tuple) or not self.records:
            raise M30PublishedTraceError("records must be a nonempty tuple")
        if any(
            not isinstance(record, PublishedTraceRecord)
            for record in self.records
        ):
            raise M30PublishedTraceError(
                "records must contain PublishedTraceRecord values"
            )
        if tuple(record.sequence for record in self.records) != tuple(
            range(len(self.records))
        ):
            raise M30PublishedTraceError(
                "records must retain contiguous source sequence order"
            )
        counts = Counter(record.execution_epoch for record in self.records)
        if tuple(counts.get(epoch.epoch, 0) for epoch in self.epochs) != tuple(
            epoch.record_count for epoch in self.epochs
        ):
            raise M30PublishedTraceError(
                "record inventory differs from execution epoch declarations"
            )
        mode_by_epoch = {epoch.epoch: epoch.mode for epoch in self.epochs}
        if any(
            record.scheduler.mode != mode_by_epoch[record.execution_epoch]
            for record in self.records
        ):
            raise M30PublishedTraceError(
                "record scheduler mode differs from its source epoch"
            )
        root = _require_mapping(
            self.dispatch.parsed_artifact.root,
            "M16 parsed root",
        )
        if (
            root.get("schema") != _SCHEMA_IDENTIFIER
            or root.get("kind") != _TRACE_KIND
            or root.get("source_release") != _SOURCE_RELEASE
        ):
            raise M30PublishedTraceError(
                "M16 Trace Explorer source identity changed"
            )
        source_records = _require_sequence(root.get("records"), "records")
        if len(source_records) != len(self.records):
            raise M30PublishedTraceError(
                "source and projected record inventories differ"
            )
        for record, source in zip(self.records, source_records, strict=True):
            if record.source_payload() != _plain(source):
                raise M30PublishedTraceError(
                    "projected record differs from exact retained source"
                )
            expected_source_sha = _record_source_sha256(source)
            if record.source_record_sha256 != expected_source_sha:
                raise M30PublishedTraceError(
                    "projected record source digest mismatch"
                )
            expected_record_id = str(
                uuid5(
                    _RECORD_NAMESPACE,
                    (
                        f"{self.dispatch.dispatch_sha256}:"
                        f"{record.sequence}:{expected_source_sha}"
                    ),
                )
            )
            if record.trace_record_id != expected_record_id:
                raise M30PublishedTraceError(
                    "trace_record_id does not bind exact source and order"
                )
            expected_location = SourceLocation(
                json_path=f"$.records[{record.sequence}]",
                array_index=record.sequence,
                package_member=_SOURCE_PATH,
                source_record_ordinal=record.sequence + 1,
            )
            if record.source_location != expected_location:
                raise M30PublishedTraceError(
                    "record source coordinate changed"
                )
        source_epochs = _require_sequence(
            root.get("execution_epochs"),
            "execution_epochs",
        )
        if [epoch.source_payload() for epoch in self.epochs] != _plain(
            source_epochs
        ):
            raise M30PublishedTraceError(
                "projected epochs differ from exact retained source"
            )
        for epoch in self.epochs:
            expected_location = SourceLocation(
                json_path=f"$.execution_epochs[{epoch.epoch}]",
                array_index=epoch.epoch,
                package_member=_SOURCE_PATH,
                source_record_ordinal=epoch.epoch + 1,
            )
            if epoch.source_location != expected_location:
                raise M30PublishedTraceError("epoch source coordinate changed")
        _validate_sha256(self.source_record_digest, "source_record_digest")
        expected_record_digest = _records_document_sha256(source_records)
        if self.source_record_digest != expected_record_digest:
            raise M30PublishedTraceError(
                "source record digest differs from retained record sequence"
            )
        summary = _require_mapping(root.get("summary"), "summary")
        if summary.get("record_digest") != self.source_record_digest:
            raise M30PublishedTraceError(
                "source summary record digest differs from projection"
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
        for value, expected, field in (
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
            if value != expected:
                raise M30PublishedTraceError(
                    f"{field} differs from exact source boundary"
                )
        if (
            self.m15_correlation_status != "not_evaluated_in_m19"
            or self.physical_measurement_availability != "not_in_scope"
            or self.physical_measurement_correlation_status != "not_evaluated"
        ):
            raise M30PublishedTraceError(
                "Trace Explorer conflated execution, semantic, or physical contours"
            )
        _validate_sha256(self.dataset_sha256, "dataset_sha256")
        expected_dataset_digest = _dataset_sha256(
            self.audit_batch,
            self.audit_report,
            self.dispatch,
            self.measurement_contour,
            self.epochs,
            self.records,
            self.source_record_digest,
            self.m15_correlation_status,
            self.physical_measurement_availability,
            self.physical_measurement_correlation_status,
        )
        if self.dataset_sha256 != expected_dataset_digest:
            raise M30PublishedTraceError(
                "dataset_sha256 does not bind exact M6 evidence and projection"
            )
        expected_dataset_id = str(
            uuid5(_DATASET_NAMESPACE, self.dataset_sha256)
        )
        if self.trace_dataset_id != expected_dataset_id:
            raise M30PublishedTraceError(
                "trace_dataset_id does not bind deterministic dataset digest"
            )

    @property
    def member_id(self) -> str:
        """Return the exact M3 published member identifier."""

        return self.dispatch.member_id

    @property
    def record_count(self) -> int:
        """Return the exact count of retained execution records."""

        return len(self.records)

    @property
    def cell_snapshot_count(self) -> int:
        """Return the exact number of projected cell snapshots."""

        return sum(len(record.cells) for record in self.records)

    @property
    def request_count(self) -> int:
        """Return the exact number of projected request-lane records."""

        return sum(len(record.requests) for record in self.records)

    @property
    def observed_scheduler_modes(self) -> tuple[str, ...]:
        """Return source-observed modes only, without synthesizing 7/1."""

        return tuple(dict.fromkeys(epoch.mode for epoch in self.epochs))

    @property
    def observed_ternary_domain(self) -> tuple[int, ...]:
        """Return exact values observed across states, routes, and targets."""

        values: set[int] = set()
        for record in self.records:
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

    @property
    def event_totals(self) -> tuple[tuple[str, int], ...]:
        """Return deterministic source totals for all six event counters."""

        return tuple(
            (
                name,
                sum(record.event_count(name) for record in self.records),
            )
            for name in _EVENT_NAMES
        )


def _build_request(value: object, expected_lane: int) -> PublishedTraceRequest:
    source = _require_mapping(value, f"request[{expected_lane}]")
    lane = _validate_nonnegative_integer(source.get("lane"), "request lane")
    if lane != expected_lane:
        raise M30PublishedTraceError("request lane order changed")
    return PublishedTraceRequest(
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


def _build_scheduler(value: object) -> PublishedSchedulerTrace:
    source = _require_mapping(value, "scheduler")
    counters = _require_mapping(source.get("counters_after"), "counters_after")
    return PublishedSchedulerTrace(
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
    dispatch: PublishedModeDispatch,
    value: object,
    expected_sequence: int,
) -> PublishedTraceRecord:
    source = _require_mapping(value, f"records[{expected_sequence}]")
    sequence = _validate_nonnegative_integer(source.get("sequence"), "sequence")
    if sequence != expected_sequence:
        raise M30PublishedTraceError("record sequence order changed")
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
        PublishedTraceCell(
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
    requests = tuple(
        _build_request(request, lane)
        for lane, request in enumerate(
            _require_sequence(source.get("requests"), "requests")
        )
    )
    if len(requests) != 2:
        raise M30PublishedTraceError("M16 record must contain two request lanes")
    capacity = _require_mapping(
        source.get("transition_capacity"),
        "transition_capacity",
    )
    telemetry = _require_mapping(source.get("telemetry"), "telemetry")
    events = _require_mapping(source.get("events"), "events")
    invariants = _require_mapping(source.get("invariants"), "invariants")
    flags = _require_sequence(invariants.get("flags"), "invariant flags")
    invariant_names: list[str] = []
    for index, flag_value in enumerate(flags):
        flag = _require_mapping(flag_value, f"invariant flags[{index}]")
        invariant_names.append(
            _validate_text(flag.get("name"), f"invariant flags[{index}].name")
        )
        if flag.get("pass") is not True:
            raise M30PublishedTraceError("M16 invariant flag did not pass")
    source_sha = _record_source_sha256(source)
    record_id = str(
        uuid5(
            _RECORD_NAMESPACE,
            f"{dispatch.dispatch_sha256}:{sequence}:{source_sha}",
        )
    )
    return PublishedTraceRecord(
        trace_record_id=record_id,
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
            package_member=_SOURCE_PATH,
            source_record_ordinal=sequence + 1,
        ),
        source_record_sha256=source_sha,
    )


def _build_epoch(value: object, expected_epoch: int) -> PublishedExecutionEpoch:
    source = _require_mapping(value, f"execution_epochs[{expected_epoch}]")
    epoch = _validate_nonnegative_integer(source.get("epoch"), "epoch")
    if epoch != expected_epoch:
        raise M30PublishedTraceError("execution epoch order changed")
    return PublishedExecutionEpoch(
        epoch=epoch,
        mode=_validate_text(source.get("mode"), "epoch mode"),
        record_count=_validate_positive_integer(
            source.get("record_count"),
            "record_count",
        ),
        source_location=SourceLocation(
            json_path=f"$.execution_epochs[{epoch}]",
            array_index=epoch,
            package_member=_SOURCE_PATH,
            source_record_ordinal=epoch + 1,
        ),
    )


def build_m30_published_trace_dataset(
    audit_batch: PublishedAuditBatch,
) -> M30PublishedTraceDataset:
    """Build the sole M30 Trace Explorer dataset from exact M6 evidence."""

    if not isinstance(audit_batch, PublishedAuditBatch):
        raise M30PublishedTraceError(
            "audit_batch must be PublishedAuditBatch"
        )
    if audit_batch.overall_status is not ValidationStatus.RECOGNIZED_VALID:
        raise M30PublishedTraceError("M6 audit batch must pass before M7")
    audit_report = audit_batch.report_for_member(_MEMBER_ID)
    dispatch = audit_batch.dispatch_batch.dispatch_for(
        _MEMBER_ID,
        ObservatoryMode.TRACE_EXPLORER,
    )
    if dispatch.member is not audit_report.dispatch.member:
        raise M30PublishedTraceError(
            "M6 report and M5 Trace Explorer route do not share exact source"
        )
    root = _require_mapping(dispatch.parsed_artifact.root, "M16 parsed root")
    if (
        root.get("schema") != _SCHEMA_IDENTIFIER
        or root.get("kind") != _TRACE_KIND
        or root.get("source_release") != _SOURCE_RELEASE
    ):
        raise M30PublishedTraceError("unsupported M16 published trace identity")
    source_epochs = _require_sequence(
        root.get("execution_epochs"),
        "execution_epochs",
    )
    epochs = tuple(
        _build_epoch(epoch, index)
        for index, epoch in enumerate(source_epochs)
    )
    source_records = _require_sequence(root.get("records"), "records")
    records = tuple(
        _build_record(dispatch, record, index)
        for index, record in enumerate(source_records)
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
    contour = dispatch.member.registration.measurement_contour
    digest = _dataset_sha256(
        audit_batch,
        audit_report,
        dispatch,
        contour,
        epochs,
        records,
        source_record_digest,
        m15_status,
        physical_availability,
        physical_status,
    )
    return M30PublishedTraceDataset(
        trace_dataset_id=str(uuid5(_DATASET_NAMESPACE, digest)),
        audit_batch=audit_batch,
        audit_report=audit_report,
        dispatch=dispatch,
        measurement_contour=contour,
        epochs=epochs,
        records=records,
        source_record_digest=source_record_digest,
        m15_correlation_status=m15_status,
        physical_measurement_availability=physical_availability,
        physical_measurement_correlation_status=physical_status,
        dataset_sha256=digest,
    )


def explore_m30_published_archive(
    archive_path: str | Path,
) -> M30PublishedTraceDataset:
    """Validate M1 through M6 and build the exact M16 trace dataset."""

    return build_m30_published_trace_dataset(
        audit_m30_published_archive(archive_path)
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one deterministic read-only Trace Explorer dataset from "
            "the exact audited FRP M16 publication."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    arguments = parser.parse_args()
    result = explore_m30_published_archive(arguments.archive)
    print("FRP Observatory M30 published Trace Explorer: PASS")
    print(f"member_id={result.member_id}")
    print(f"measurement_contour={result.measurement_contour.value}")
    print(f"records={result.record_count}")
    print(f"cell_snapshots={result.cell_snapshot_count}")
    print(f"requests={result.request_count}")
    print(
        "observed_scheduler_modes="
        + ",".join(result.observed_scheduler_modes)
    )
    print(
        "observed_ternary_domain="
        + "/".join(str(value) for value in result.observed_ternary_domain)
    )
    print(f"source_record_digest={result.source_record_digest}")
    print(f"dataset_sha256={result.dataset_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
