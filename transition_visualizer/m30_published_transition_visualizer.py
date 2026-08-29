"""Read-only full-core transition visualization for exact FRP M30 data.

This module consumes the already qualified M1 through M7 Observatory chain,
then retains four additional immutable M30 members required to expose the
complete M16 execution surface:

* the 96-record RTL execution trace;
* the 4-record FPGA-preparation execution trace;
* the M28 canonical Trace Observatory bundle;
* the M28 fixture manifest.

The two M16 measurement contours remain separate.  Their exact source records
are cross-checked against the M28 bundle, the fixture manifest, the M7 FPGA
Trace Explorer projection, and the immutable M28 upstream contract.  The
result contains 800 cell frames and displays the balanced ternary kernel as
-1/0/1 with active neutral 0 and both temporal scheduler modes 1/7 and 7/1.

No upstream source is executed, normalized, rewritten, or written back.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final
from uuid import UUID, uuid5

from artifact_auditor.audit_report import SourceLocation, ValidationStatus
from artifact_auditor.m30_archive_intake import (
    FRP_M30_ARCHIVE_SHA256,
    M30ArchiveValidation,
    RetainedArchiveMember,
    validate_m30_archive,
)
from artifact_auditor.m30_published_auditor import (
    PublishedAuditBatch,
    PublishedAuditReport,
    audit_m30_published_archive,
)
from parsers.json_artifact import ParsedJsonArtifact, parse_json_artifact
from parsers.m30_published_dispatch import PublishedModeDispatch
from parsers.source_artifact import capture_source_bytes
from schemas.registry import ObservatoryMode
from trace_explorer.m30_published_trace_explorer import (
    M30PublishedTraceDataset,
    PublishedExecutionEpoch,
    PublishedSchedulerTrace,
    PublishedTraceCell,
    PublishedTraceRecord,
    PublishedTraceRequest,
    build_m30_published_trace_dataset,
)


__all__ = [
    "M30FullCoreTraceEvidence",
    "M30PublishedTransitionVisualizerDataset",
    "M30PublishedVisualizerError",
    "PublishedCoreTraceSource",
    "PublishedTelemetrySemantic",
    "PublishedTransitionFrame",
    "build_m30_published_transition_visualizer",
    "load_m30_full_core_trace_evidence",
    "visualize_m30_published_archive",
]


@dataclass(frozen=True, slots=True)
class _TraceSourceSpec:
    dataset_id: str
    fixture_id: str
    source_path: str
    schema_identifier: str
    source_kind: str
    layer: str
    measurement_contour: str
    raw_sha256: str
    byte_length: int
    record_count: int
    source_record_digest: str
    bundle_records_digest: str
    execution_epochs: tuple[tuple[int, str, int], ...]


_RTL_SPEC: Final = _TraceSourceSpec(
    dataset_id="m16-rtl-execution",
    fixture_id="m16-rtl-execution-trace",
    source_path="artifacts/m19/execution/m16-rtl-execution-trace.json",
    schema_identifier="frp.m16.rtl_execution_trace.v2.1.0",
    source_kind="m16_rtl_execution_trace",
    layer="rtl",
    measurement_contour="m16_rtl_execution",
    raw_sha256=(
        "d7945e0d2b5aaa05c5fff2e4e60d3b984017f7e4ae1984c55920368a110020bd"
    ),
    byte_length=152_109,
    record_count=96,
    source_record_digest=(
        "3f730a3d088e4d75fdd1631dd234878a6acd3a7561cb463e19c815096c04fe6a"
    ),
    bundle_records_digest=(
        "902d1a3601ba93dc75a0ed03c69a817869890df23ea5b17ccf07d84d115bc174"
    ),
    execution_epochs=(
        (0, "free", 16),
        (1, "7/1", 64),
        (2, "1/7", 16),
    ),
)
_FPGA_SPEC: Final = _TraceSourceSpec(
    dataset_id="m16-fpga-preparation-execution",
    fixture_id="m16-fpga-preparation-execution-trace",
    source_path=(
        "artifacts/m19/execution/"
        "m16-fpga-preparation-execution-trace.json"
    ),
    schema_identifier=(
        "frp.m16.fpga_preparation_execution_trace.v2.1.0"
    ),
    source_kind="m16_fpga_preparation_execution_trace",
    layer="fpga_preparation",
    measurement_contour="m16_fpga_preparation_execution",
    raw_sha256=(
        "7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f"
    ),
    byte_length=9_013,
    record_count=4,
    source_record_digest=(
        "4b2e8aec64a0b3cb76d0819383ed66d306b8e50dc3feb7bb8c6c76486cd83d57"
    ),
    bundle_records_digest=(
        "588cc3cbc2ec7454bd7ac0efa1c22a9fa61752e53eeb74366846989282f50a06"
    ),
    execution_epochs=(
        (0, "free", 3),
        (1, "1/7", 1),
    ),
)
_TRACE_SPECS: Final = (_RTL_SPEC, _FPGA_SPEC)
_TRACE_SPEC_BY_DATASET: Final = {
    spec.dataset_id: spec for spec in _TRACE_SPECS
}

_FPGA_REGISTRY_MEMBER_ID: Final = (
    "m16-fpga-preparation-execution-trace"
)
_M27_MEMBER_ID: Final = "m27-telemetry-semantics"
_M28_UPSTREAM_MEMBER_ID: Final = (
    "m28-trace-observatory-upstream-contract"
)
_M27_SOURCE_PATH: Final = (
    "artifacts/m27/telemetry/m27-telemetry-semantics.json"
)
_M28_BUNDLE_PATH: Final = (
    "artifacts/m28/exports/"
    "m28-observatory-canonical-trace-bundle.json"
)
_M28_FIXTURE_MANIFEST_PATH: Final = (
    "artifacts/m28/fixtures/"
    "m28-observatory-fixture-manifest.json"
)
_FULL_CORE_RETAIN_PATHS: Final = tuple(
    sorted(
        (
            _RTL_SPEC.source_path,
            _FPGA_SPEC.source_path,
            _M28_BUNDLE_PATH,
            _M28_FIXTURE_MANIFEST_PATH,
        )
    )
)

_M28_BUNDLE_RAW_SHA256: Final = (
    "9774e80d00c628193d5656608f2b1f830a05f960abadb83d9c4840f262ca07ed"
)
_M28_BUNDLE_BYTE_LENGTH: Final = 511_783
_M28_BUNDLE_DIGEST: Final = (
    "34d09ed25c5d5f85f26dc5430a12e58c7abccfaa5f9850e15efb84f302d76d51"
)
_M28_FIXTURE_MANIFEST_RAW_SHA256: Final = (
    "5d1be27e20a6a5978cb75e1185b9360621a92eb116b7a712fa5d6b813d0951fe"
)
_M28_FIXTURE_MANIFEST_BYTE_LENGTH: Final = 5_720
_M28_FIXTURE_SET_DIGEST: Final = (
    "c72be639b95b96917341d3800d2ee25a55a03e2156cd1d7f504825025053429a"
)
_M28_FIXTURE_MANIFEST_DIGEST: Final = (
    "42cc4416622c0e4050ac080ab9d11e595a97f00cd553484f3d97b4ae1a0ac591"
)
_M28_SOURCE_COMMIT: Final = (
    "23e464206f85cd9473101d9221027ee33d9dd094"
)

_M16_VISUALIZER_DISPATCH_SHA256: Final = (
    "204c63f20db49a7d946b0963058db148fe43bb715c353c74ac4f6b203e4e792f"
)
_M27_VISUALIZER_DISPATCH_SHA256: Final = (
    "b17c84a8adc66205f75d8ae81053b181ba585647e8a5e29764f0d6ec062d4d21"
)
_M27_SEMANTICS_DIGEST: Final = (
    "4c3cbbf7e23bf9645d84c6affa009dffc339a1277ee6fc482fd43ba946863599"
)

_TERNARY_DOMAIN: Final = frozenset({-1, 0, 1})
_CANONICAL_TEMPORAL_MODES: Final = ("1/7", "7/1")
_VALID_SCHEDULER_MODES: Final = frozenset({"free", "1/7", "7/1"})
_VALID_SCHEDULER_STATES: Final = frozenset(
    {"free", "balance", "commit", "excite", "neutralize"}
)
_HEX64: Final = re.compile(r"^[0-9a-f]{64}$")

_SOURCE_NAMESPACE: Final = UUID("3a635239-bb31-5b10-b527-e7f71eced78e")
_RECORD_NAMESPACE: Final = UUID("4db767cb-603c-5790-a69c-c6a34c602aed")
_EVIDENCE_NAMESPACE: Final = UUID("39a70a09-bdf0-5d08-9c48-4503e9585561")
_FRAME_NAMESPACE: Final = UUID("af566826-8bf1-5cb9-9fd1-3f03a65a7fd4")
_SEMANTIC_NAMESPACE: Final = UUID("53ac4ea3-8297-5b8b-8995-c4a1c9e917a5")
_DATASET_NAMESPACE: Final = UUID("9ec921ce-60db-5c39-a63c-4afe37bc1b0d")

_M16_ROOT_FIELDS: Final = (
    "configuration",
    "execution_epochs",
    "kind",
    "layer",
    "measurement_contours",
    "milestone",
    "monitor",
    "qualified_source",
    "raw_trace",
    "records",
    "schema",
    "source_release",
    "source_testbench",
    "summary",
    "version",
)
_M16_CONFIGURATION: Final = {
    "cells": 8,
    "counter_bits": 32,
    "request_lanes": 2,
    "state_bits": 2,
    "transition_fraction_denominator": 4,
    "transition_fraction_numerator": 1,
}
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
_TRANSITION_CLASSIFICATIONS: Final = (
    "same_state_retention",
    "polarity_to_neutral_transition",
    "neutral_to_polarity_transition",
)
_ROUTE_LEGS: Final = (
    "non_route_transition",
    "first_leg_neutralization",
    "pending_route_completion",
)
_VALIDATED_RELATIONS: Final = (
    "transition_pressure_q16 equals thermal_state_proxy_q16 plus switching_load_q16",
    "stability_margin_q16 equals coherence_capacity_q16 minus transition_pressure_q16",
    "changes never exceeds request_lanes",
    "pending_route_count never exceeds queue_capacity",
)
_INTERPRETATION_BOUNDARY: Final = (
    ("all_values_are_dimensionless", True),
    ("all_values_are_model_derived", True),
    ("physical_measurements_published", False),
    ("physical_units_published", False),
    ("unsupported_physical_interpretation", "prohibited"),
)
_EXPECTED_MODE_COUNTS: Final = (
    ("free", 19),
    ("1/7", 17),
    ("7/1", 64),
)
_EXPECTED_STATE_COUNTS: Final = (
    ("free", 19),
    ("balance", 56),
    ("commit", 8),
    ("excite", 3),
    ("neutralize", 14),
)
_EXPECTED_TRANSITION_COUNTS: Final = (
    ("same_state_retention", 783),
    ("polarity_to_neutral_transition", 5),
    ("neutral_to_polarity_transition", 12),
)
_EXPECTED_ROUTE_COUNTS: Final = (
    ("non_route_transition", 790),
    ("first_leg_neutralization", 5),
    ("pending_route_completion", 5),
)


class M30PublishedVisualizerError(ValueError):
    """Raised when the exact M30 transition-visualizer boundary is violated."""


def _validate_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise M30PublishedVisualizerError(f"{field} must be a string")
    if not value or value != value.strip() or "\x00" in value:
        raise M30PublishedVisualizerError(
            f"{field} must be nonempty without outer whitespace or NUL"
        )
    return value


def _validate_nonnegative_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise M30PublishedVisualizerError(
            f"{field} must be a nonnegative integer"
        )
    return value


def _validate_positive_integer(value: object, field: str) -> int:
    result = _validate_nonnegative_integer(value, field)
    if result == 0:
        raise M30PublishedVisualizerError(f"{field} must be positive")
    return result


def _validate_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise M30PublishedVisualizerError(f"{field} must be an integer")
    return value


def _validate_ternary(value: object, field: str) -> int:
    result = _validate_integer(value, field)
    if result not in _TERNARY_DOMAIN:
        raise M30PublishedVisualizerError(f"{field} must remain in -1/0/1")
    return result


def _validate_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise M30PublishedVisualizerError(
            f"{field} must be lowercase hexadecimal SHA-256"
        )
    return value


def _validate_uuid(value: object, field: str) -> str:
    text = _validate_text(value, field)
    try:
        UUID(text)
    except ValueError as exc:
        raise M30PublishedVisualizerError(f"{field} must be a UUID") from exc
    return text


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


def _source_sha256(value: object) -> str:
    return _sha256(_canonical_json_bytes(_plain(value), ensure_ascii=False))


def _records_document_sha256(records: object) -> str:
    return _sha256(
        _canonical_json_bytes(_plain(records), ensure_ascii=False) + b"\n"
    )


def _object_digest(value: object) -> str:
    return _sha256(_canonical_json_bytes(_plain(value)))


def _verify_embedded_digest(
    value: Mapping[str, Any],
    field: str,
    expected: str,
) -> None:
    plain = _plain(value)
    observed = plain.pop(field, None)
    if observed != expected or observed != _object_digest(plain):
        raise M30PublishedVisualizerError(f"{field} mismatch")


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise M30PublishedVisualizerError(f"{field} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise M30PublishedVisualizerError(f"{field} keys must be strings")
    return value


def _require_sequence(value: object, field: str) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise M30PublishedVisualizerError(f"{field} must be an array")
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
        raise M30PublishedVisualizerError(
            f"{field} must contain exactly {length} values"
        )
    validator = _validate_ternary if ternary else _validate_nonnegative_integer
    return tuple(
        validator(item, f"{field}[{index}]")
        for index, item in enumerate(sequence)
    )


def _validate_sorted_cell_ids(value: tuple[int, ...], field: str) -> None:
    if tuple(sorted(set(value))) != value:
        raise M30PublishedVisualizerError(
            f"{field} must retain unique ascending source order"
        )
    if any(cell_id >= 8 for cell_id in value):
        raise M30PublishedVisualizerError(f"{field} cell id is out of range")


def _transition_classification(before: int, after: int) -> str:
    _validate_ternary(before, "retained_state_before")
    _validate_ternary(after, "retained_state_after")
    if before == after:
        return "same_state_retention"
    if after == 0:
        return "polarity_to_neutral_transition"
    if before == 0:
        return "neutral_to_polarity_transition"
    raise M30PublishedVisualizerError(
        "direct opposite retained-state transition is forbidden"
    )


def _route_leg(cell: PublishedTraceCell) -> str:
    if cell.neutral_routed:
        return "first_leg_neutralization"
    if (
        cell.pending_route_before in (-1, 1)
        and cell.retained_state_before == 0
        and cell.retained_state_after == cell.pending_route_before
        and cell.pending_route_after == 0
    ):
        return "pending_route_completion"
    return "non_route_transition"


def _build_request(value: object, expected_lane: int) -> PublishedTraceRequest:
    source = _require_mapping(value, f"request[{expected_lane}]")
    lane = _validate_nonnegative_integer(source.get("lane"), "request lane")
    if lane != expected_lane:
        raise M30PublishedVisualizerError("request lane order changed")
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
    mode = _validate_text(source.get("mode"), "scheduler mode")
    state = _validate_text(source.get("state"), "scheduler state")
    if mode not in _VALID_SCHEDULER_MODES:
        raise M30PublishedVisualizerError("unknown scheduler mode")
    if state not in _VALID_SCHEDULER_STATES:
        raise M30PublishedVisualizerError("unknown scheduler state")
    return PublishedSchedulerTrace(
        mode=mode,
        state=state,
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


def _build_trace_record(
    spec: _TraceSourceSpec,
    value: object,
    expected_sequence: int,
) -> PublishedTraceRecord:
    source = _require_mapping(value, f"records[{expected_sequence}]")
    sequence = _validate_nonnegative_integer(source.get("sequence"), "sequence")
    if sequence != expected_sequence:
        raise M30PublishedVisualizerError("record sequence order changed")
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
    accepted_ids = _integer_tuple(
        source.get("accepted_cell_ids"),
        "accepted_cell_ids",
    )
    changed_ids = _integer_tuple(
        source.get("accepted_change_cell_ids"),
        "accepted_change_cell_ids",
    )
    neutral_ids = _integer_tuple(
        source.get("neutral_routed_cell_ids"),
        "neutral_routed_cell_ids",
    )
    for field, values in (
        ("accepted_cell_ids", accepted_ids),
        ("accepted_change_cell_ids", changed_ids),
        ("neutral_routed_cell_ids", neutral_ids),
    ):
        _validate_sorted_cell_ids(values, field)
    accepted_set = frozenset(accepted_ids)
    changed_set = frozenset(changed_ids)
    neutral_set = frozenset(neutral_ids)
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
        _build_request(item, lane)
        for lane, item in enumerate(
            _require_sequence(source.get("requests"), "requests")
        )
    )
    if len(requests) != 2:
        raise M30PublishedVisualizerError(
            "M16 record must contain two request lanes"
        )
    capacity = _require_mapping(
        source.get("transition_capacity"),
        "transition_capacity",
    )
    telemetry = _require_mapping(source.get("telemetry"), "telemetry")
    events = _require_mapping(source.get("events"), "events")
    invariants = _require_mapping(source.get("invariants"), "invariants")
    flags = _require_sequence(invariants.get("flags"), "invariant flags")
    invariant_names: list[str] = []
    for index, value in enumerate(flags):
        flag = _require_mapping(value, f"invariant flags[{index}]")
        invariant_names.append(
            _validate_text(flag.get("name"), f"invariant flags[{index}].name")
        )
        if flag.get("pass") is not True:
            raise M30PublishedVisualizerError("M16 invariant flag did not pass")
    source_digest = _source_sha256(source)
    record_id = str(
        uuid5(
            _RECORD_NAMESPACE,
            (
                f"{spec.dataset_id}:{spec.raw_sha256}:"
                f"{sequence}:{source_digest}"
            ),
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
        accepted_cell_ids=accepted_ids,
        accepted_change_cell_ids=changed_ids,
        neutral_routed_cell_ids=neutral_ids,
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
            package_member=spec.source_path,
            source_record_ordinal=sequence + 1,
        ),
        source_record_sha256=source_digest,
    )


def _build_epoch(
    spec: _TraceSourceSpec,
    value: object,
    expected_epoch: int,
) -> PublishedExecutionEpoch:
    source = _require_mapping(value, f"execution_epochs[{expected_epoch}]")
    epoch = _validate_nonnegative_integer(source.get("epoch"), "epoch")
    if epoch != expected_epoch:
        raise M30PublishedVisualizerError("execution epoch order changed")
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
            package_member=spec.source_path,
            source_record_ordinal=epoch + 1,
        ),
    )


@dataclass(frozen=True, slots=True)
class PublishedCoreTraceSource:
    """One exact unchanged M16 trace and its validated record projection."""

    trace_source_id: str
    dataset_id: str
    retained_member: RetainedArchiveMember
    parsed_artifact: ParsedJsonArtifact
    epochs: tuple[PublishedExecutionEpoch, ...]
    records: tuple[PublishedTraceRecord, ...]
    source_record_digest: str

    def __post_init__(self) -> None:
        _validate_uuid(self.trace_source_id, "trace_source_id")
        spec = _TRACE_SPEC_BY_DATASET.get(self.dataset_id)
        if spec is None:
            raise M30PublishedVisualizerError("unknown M16 trace dataset")
        if not isinstance(self.retained_member, RetainedArchiveMember):
            raise M30PublishedVisualizerError(
                "retained_member must be RetainedArchiveMember"
            )
        member = self.retained_member.member
        if (
            member.path != spec.source_path
            or member.byte_length != spec.byte_length
            or member.raw_sha256 != spec.raw_sha256
        ):
            raise M30PublishedVisualizerError(
                "M16 retained member identity changed"
            )
        if not isinstance(self.parsed_artifact, ParsedJsonArtifact):
            raise M30PublishedVisualizerError(
                "parsed_artifact must be ParsedJsonArtifact"
            )
        source = self.parsed_artifact.source_artifact
        if (
            source.source_path != spec.source_path
            or source.source_filename != PurePosixPath(spec.source_path).name
            or source.raw_bytes != self.retained_member.raw_bytes
            or source.byte_length != spec.byte_length
            or source.content_sha256 != spec.raw_sha256
            or not source.verify_integrity()
        ):
            raise M30PublishedVisualizerError(
                "parsed M16 source differs from retained bytes"
            )
        root = _require_mapping(
            self.parsed_artifact.root,
            f"{self.dataset_id} root",
        )
        if tuple(sorted(root)) != _M16_ROOT_FIELDS:
            raise M30PublishedVisualizerError("M16 root field set changed")
        expected_identity = {
            "kind": spec.source_kind,
            "layer": spec.layer,
            "milestone": (
                "M19 — Machine-Readable M16 Execution and "
                "Qualification Evidence"
            ),
            "schema": spec.schema_identifier,
            "source_release": "FRP v1.8.0 / M16",
            "version": "2.1.0",
        }
        if {
            name: root.get(name) for name in expected_identity
        } != expected_identity:
            raise M30PublishedVisualizerError("M16 source identity changed")
        if _plain(root.get("configuration")) != _M16_CONFIGURATION:
            raise M30PublishedVisualizerError("M16 configuration changed")
        if self.parsed_artifact.declared_schema_identifier != (
            spec.schema_identifier
        ) or self.parsed_artifact.declared_kind != spec.source_kind:
            raise M30PublishedVisualizerError(
                "strict parser metadata differs from M16 declaration"
            )
        source_epochs = _require_sequence(
            root.get("execution_epochs"),
            "execution_epochs",
        )
        expected_epochs = [
            {"epoch": epoch, "mode": mode, "record_count": count}
            for epoch, mode, count in spec.execution_epochs
        ]
        if _plain(source_epochs) != expected_epochs:
            raise M30PublishedVisualizerError(
                "M16 execution epoch declaration changed"
            )
        if (
            not isinstance(self.epochs, tuple)
            or [epoch.source_payload() for epoch in self.epochs]
            != expected_epochs
        ):
            raise M30PublishedVisualizerError(
                "projected M16 epochs differ from source"
            )
        for epoch in self.epochs:
            expected_location = SourceLocation(
                json_path=f"$.execution_epochs[{epoch.epoch}]",
                array_index=epoch.epoch,
                package_member=spec.source_path,
                source_record_ordinal=epoch.epoch + 1,
            )
            if epoch.source_location != expected_location:
                raise M30PublishedVisualizerError(
                    "M16 epoch source location changed"
                )
        source_records = _require_sequence(root.get("records"), "records")
        if (
            len(source_records) != spec.record_count
            or not isinstance(self.records, tuple)
            or len(self.records) != spec.record_count
        ):
            raise M30PublishedVisualizerError(
                "M16 record inventory length changed"
            )
        if tuple(record.sequence for record in self.records) != tuple(
            range(spec.record_count)
        ):
            raise M30PublishedVisualizerError(
                "M16 records lost contiguous source order"
            )
        for record, source_record in zip(
            self.records,
            source_records,
            strict=True,
        ):
            if not isinstance(record, PublishedTraceRecord):
                raise M30PublishedVisualizerError(
                    "records must contain PublishedTraceRecord values"
                )
            if record.source_payload() != _plain(source_record):
                raise M30PublishedVisualizerError(
                    "M16 record projection differs from exact source"
                )
            expected_record_sha = _source_sha256(source_record)
            if record.source_record_sha256 != expected_record_sha:
                raise M30PublishedVisualizerError(
                    "M16 source-record digest mismatch"
                )
            expected_record_id = str(
                uuid5(
                    _RECORD_NAMESPACE,
                    (
                        f"{spec.dataset_id}:{spec.raw_sha256}:"
                        f"{record.sequence}:{expected_record_sha}"
                    ),
                )
            )
            if record.trace_record_id != expected_record_id:
                raise M30PublishedVisualizerError(
                    "M16 trace-record identity mismatch"
                )
            expected_location = SourceLocation(
                json_path=f"$.records[{record.sequence}]",
                array_index=record.sequence,
                package_member=spec.source_path,
                source_record_ordinal=record.sequence + 1,
            )
            if record.source_location != expected_location:
                raise M30PublishedVisualizerError(
                    "M16 record source location changed"
                )
            if any(
                (cell.retained_state_before, cell.retained_state_after)
                in ((-1, 1), (1, -1))
                for cell in record.cells
            ):
                raise M30PublishedVisualizerError(
                    "M16 source contains a direct opposite transition"
                )
        epoch_counts = Counter(
            record.execution_epoch for record in self.records
        )
        epoch_modes = {
            epoch.epoch: epoch.mode for epoch in self.epochs
        }
        if tuple(
            epoch_counts.get(epoch.epoch, 0) for epoch in self.epochs
        ) != tuple(epoch.record_count for epoch in self.epochs):
            raise M30PublishedVisualizerError(
                "M16 records differ from epoch counts"
            )
        if any(
            record.scheduler.mode != epoch_modes[record.execution_epoch]
            for record in self.records
        ):
            raise M30PublishedVisualizerError(
                "M16 scheduler mode differs from execution epoch"
            )
        _validate_sha256(
            self.source_record_digest,
            "source_record_digest",
        )
        if (
            self.source_record_digest != spec.source_record_digest
            or self.source_record_digest
            != _records_document_sha256(source_records)
        ):
            raise M30PublishedVisualizerError(
                "M16 source record digest changed"
            )
        summary = _require_mapping(root.get("summary"), "summary")
        scheduler_states = Counter(
            record.scheduler.state for record in self.records
        )
        calculated_summary = {
            "event_totals": {
                name: sum(
                    record.event_count(name) for record in self.records
                )
                for name in _EVENT_NAMES
            },
            "execution_epoch_count": len(self.epochs),
            "invariant_pass_records": sum(
                record.invariant_all_pass for record in self.records
            ),
            "maximum_switch_load_numerator": max(
                record.switch_load_numerator for record in self.records
            ),
            "record_count": len(self.records),
            "record_digest": self.source_record_digest,
            "scheduler_state_counts": dict(
                sorted(scheduler_states.items())
            ),
            "total_accepted_changes": sum(
                record.accepted_changes for record in self.records
            ),
            "zero_event_status": "PASS",
        }
        if _plain(summary) != calculated_summary:
            raise M30PublishedVisualizerError(
                "M16 source summary differs from exact records"
            )
        contours = _require_mapping(
            root.get("measurement_contours"),
            "measurement_contours",
        )
        m15 = _require_mapping(
            contours.get("m15_semantic_reference"),
            "m15_semantic_reference",
        )
        execution = _require_mapping(
            contours.get("m16_execution"),
            "m16_execution",
        )
        physical = _require_mapping(
            contours.get("physical_measurement"),
            "physical_measurement",
        )
        if (
            m15.get("correlation_status") != "not_evaluated_in_m19"
            or execution.get("availability")
            != "emitted_by_m16_execution_boundary"
            or physical.get("availability") != "not_in_scope"
            or physical.get("correlation_status") != "not_evaluated"
        ):
            raise M30PublishedVisualizerError(
                "M16 execution, semantic, and physical contours were conflated"
            )
        expected_id = str(
            uuid5(
                _SOURCE_NAMESPACE,
                f"{spec.dataset_id}:{spec.raw_sha256}",
            )
        )
        if self.trace_source_id != expected_id:
            raise M30PublishedVisualizerError(
                "trace_source_id does not bind exact source identity"
            )

    @property
    def spec(self) -> _TraceSourceSpec:
        """Return the fixed source specification for this dataset."""

        return _TRACE_SPEC_BY_DATASET[self.dataset_id]

    @property
    def source_path(self) -> str:
        return self.spec.source_path

    @property
    def raw_sha256(self) -> str:
        return self.spec.raw_sha256

    @property
    def measurement_contour(self) -> str:
        return self.spec.measurement_contour


def _parse_retained_member(
    validation: M30ArchiveValidation,
    path: str,
) -> ParsedJsonArtifact:
    retained = validation.retained_member(path)
    source = capture_source_bytes(
        retained.raw_bytes,
        source_filename=PurePosixPath(path).name,
        source_path=path,
    )
    return parse_json_artifact(source)


def _build_trace_source(
    validation: M30ArchiveValidation,
    spec: _TraceSourceSpec,
) -> PublishedCoreTraceSource:
    parsed = _parse_retained_member(validation, spec.source_path)
    root = _require_mapping(parsed.root, f"{spec.dataset_id} root")
    source_epochs = _require_sequence(
        root.get("execution_epochs"),
        "execution_epochs",
    )
    epochs = tuple(
        _build_epoch(spec, value, index)
        for index, value in enumerate(source_epochs)
    )
    source_records = _require_sequence(root.get("records"), "records")
    records = tuple(
        _build_trace_record(spec, value, sequence)
        for sequence, value in enumerate(source_records)
    )
    return PublishedCoreTraceSource(
        trace_source_id=str(
            uuid5(
                _SOURCE_NAMESPACE,
                f"{spec.dataset_id}:{spec.raw_sha256}",
            )
        ),
        dataset_id=spec.dataset_id,
        retained_member=validation.retained_member(spec.source_path),
        parsed_artifact=parsed,
        epochs=epochs,
        records=records,
        source_record_digest=_records_document_sha256(source_records),
    )


def _validate_bundle(
    parsed: ParsedJsonArtifact,
    trace_sources: tuple[PublishedCoreTraceSource, ...],
) -> None:
    if (
        parsed.source_artifact.source_path != _M28_BUNDLE_PATH
        or parsed.source_artifact.byte_length != _M28_BUNDLE_BYTE_LENGTH
        or parsed.content_sha256 != _M28_BUNDLE_RAW_SHA256
    ):
        raise M30PublishedVisualizerError(
            "M28 canonical bundle raw identity changed"
        )
    root = _require_mapping(parsed.root, "M28 canonical bundle")
    expected_identity = {
        "schema": "frp.m28.trace_observatory_canonical_trace_bundle.v3.0.0",
        "kind": "trace_observatory_canonical_trace_bundle",
        "milestone": "M28",
        "version": "3.0.0",
        "status": "PASS",
        "source_commit": _M28_SOURCE_COMMIT,
        "dataset_count": 3,
        "record_count": 196,
        "ordering_rule": "source_dataset_order_then_source_record_order",
    }
    if {name: root.get(name) for name in expected_identity} != (
        expected_identity
    ):
        raise M30PublishedVisualizerError(
            "M28 canonical bundle identity changed"
        )
    if _plain(root.get("canonical_ternary_domain")) != [-1, 0, 1]:
        raise M30PublishedVisualizerError(
            "M28 bundle ternary domain changed"
        )
    if _plain(root.get("scheduler_modes")) != ["free", "7/1", "1/7"]:
        raise M30PublishedVisualizerError(
            "M28 bundle scheduler modes changed"
        )
    _verify_embedded_digest(root, "bundle_digest", _M28_BUNDLE_DIGEST)
    datasets = _require_sequence(root.get("datasets"), "M28 datasets")
    if len(datasets) != 3:
        raise M30PublishedVisualizerError(
            "M28 canonical bundle dataset inventory changed"
        )
    expected_ids = (
        "m16-rtl-execution",
        "m16-fpga-preparation-execution",
        "m27-long-run-checkpoints",
    )
    if tuple(
        _require_mapping(item, "M28 dataset").get("dataset_id")
        for item in datasets
    ) != expected_ids:
        raise M30PublishedVisualizerError(
            "M28 canonical dataset order changed"
        )
    total_records = 0
    for index, value in enumerate(datasets):
        dataset = _require_mapping(value, f"M28 datasets[{index}]")
        records = _require_sequence(
            dataset.get("records"),
            f"M28 datasets[{index}].records",
        )
        record_count = _validate_nonnegative_integer(
            dataset.get("record_count"),
            f"M28 datasets[{index}].record_count",
        )
        if record_count != len(records):
            raise M30PublishedVisualizerError(
                "M28 dataset record-count relation changed"
            )
        if dataset.get("records_digest") != _object_digest(records):
            raise M30PublishedVisualizerError(
                "M28 dataset records digest mismatch"
            )
        if _plain(dataset.get("observatory_modes")) != [
            "artifact_auditor",
            "ternary_transition_visualizer",
            "trace_explorer",
        ]:
            raise M30PublishedVisualizerError(
                "M28 dataset Observatory routing changed"
            )
        total_records += record_count
    if total_records != 196:
        raise M30PublishedVisualizerError(
            "M28 total dataset record count changed"
        )
    for source, value in zip(trace_sources, datasets[:2], strict=True):
        spec = source.spec
        dataset = _require_mapping(value, f"M28 {spec.dataset_id}")
        source_artifact = _require_mapping(
            dataset.get("source_artifact"),
            "M28 source_artifact",
        )
        expected = {
            "dataset_id": spec.dataset_id,
            "measurement_contour": spec.measurement_contour,
            "record_count": spec.record_count,
            "record_order": "unchanged_source_order",
            "records_digest": spec.bundle_records_digest,
            "source_identifier": spec.schema_identifier,
            "source_kind": spec.source_kind,
        }
        if {name: dataset.get(name) for name in expected} != expected:
            raise M30PublishedVisualizerError(
                "M28 M16 dataset declaration changed"
            )
        if _plain(source_artifact) != {
            "bytes": spec.byte_length,
            "path": spec.source_path,
            "raw_sha256": spec.raw_sha256,
        }:
            raise M30PublishedVisualizerError(
                "M28 M16 source-artifact identity changed"
            )
        if _plain(dataset.get("records")) != [
            record.source_payload() for record in source.records
        ]:
            raise M30PublishedVisualizerError(
                "M28 M16 records differ from direct unchanged trace"
            )


def _validate_fixture_manifest(
    parsed: ParsedJsonArtifact,
    trace_sources: tuple[PublishedCoreTraceSource, ...],
) -> None:
    if (
        parsed.source_artifact.source_path != _M28_FIXTURE_MANIFEST_PATH
        or parsed.source_artifact.byte_length
        != _M28_FIXTURE_MANIFEST_BYTE_LENGTH
        or parsed.content_sha256 != _M28_FIXTURE_MANIFEST_RAW_SHA256
    ):
        raise M30PublishedVisualizerError(
            "M28 fixture manifest raw identity changed"
        )
    root = _require_mapping(parsed.root, "M28 fixture manifest")
    expected_identity = {
        "schema": "frp.m28.trace_observatory_fixture_manifest.v3.0.0",
        "kind": "trace_observatory_fixture_manifest",
        "milestone": "M28",
        "version": "3.0.0",
        "status": "PASS",
        "source_commit": _M28_SOURCE_COMMIT,
        "copy_requirement": "unchanged_upstream_bytes",
        "fixture_count": 6,
        "fixture_set_digest": _M28_FIXTURE_SET_DIGEST,
    }
    if {name: root.get(name) for name in expected_identity} != (
        expected_identity
    ):
        raise M30PublishedVisualizerError(
            "M28 fixture manifest identity changed"
        )
    if _plain(root.get("digest_contract")) != {
        "algorithm": "sha256",
        "pre_parse": True,
        "scope": "raw_source_bytes",
    }:
        raise M30PublishedVisualizerError(
            "M28 fixture digest contract changed"
        )
    _verify_embedded_digest(
        root,
        "manifest_digest",
        _M28_FIXTURE_MANIFEST_DIGEST,
    )
    fixtures = _require_sequence(root.get("fixtures"), "M28 fixtures")
    if len(fixtures) != 6 or _object_digest(fixtures) != (
        _M28_FIXTURE_SET_DIGEST
    ):
        raise M30PublishedVisualizerError(
            "M28 fixture inventory digest changed"
        )
    for source, value in zip(trace_sources, fixtures[:2], strict=True):
        spec = source.spec
        fixture = _require_mapping(value, f"fixture {spec.fixture_id}")
        expected = {
            "artifact_bytes": spec.byte_length,
            "artifact_path": spec.source_path,
            "artifact_raw_sha256": spec.raw_sha256,
            "copy_requirement": "unchanged_upstream_bytes",
            "fixture_id": spec.fixture_id,
            "measurement_contour": spec.measurement_contour,
            "source_identifier": spec.schema_identifier,
            "source_kind": spec.source_kind,
        }
        if {name: fixture.get(name) for name in expected} != expected:
            raise M30PublishedVisualizerError(
                "M28 M16 fixture declaration changed"
            )
        if _plain(fixture.get("observatory_modes")) != [
            "artifact_auditor",
            "ternary_transition_visualizer",
            "trace_explorer",
        ]:
            raise M30PublishedVisualizerError(
                "M28 M16 fixture routing changed"
            )


def _evidence_sha256(
    archive_validation: M30ArchiveValidation,
    bundle: ParsedJsonArtifact,
    manifest: ParsedJsonArtifact,
    trace_sources: tuple[PublishedCoreTraceSource, ...],
) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "archive_sha256": archive_validation.archive_sha256,
                "canonical_bundle_raw_sha256": bundle.content_sha256,
                "fixture_manifest_raw_sha256": manifest.content_sha256,
                "trace_sources": [
                    {
                        "dataset_id": source.dataset_id,
                        "raw_sha256": source.raw_sha256,
                        "source_record_digest": (
                            source.source_record_digest
                        ),
                        "trace_source_id": source.trace_source_id,
                    }
                    for source in trace_sources
                ],
            }
        )
    )


@dataclass(frozen=True, slots=True)
class M30FullCoreTraceEvidence:
    """Exact archive, M28 routing, and both unchanged M16 trace sources."""

    evidence_id: str
    archive_validation: M30ArchiveValidation
    canonical_bundle: ParsedJsonArtifact
    fixture_manifest: ParsedJsonArtifact
    trace_sources: tuple[PublishedCoreTraceSource, ...]
    evidence_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.evidence_id, "evidence_id")
        if not isinstance(self.archive_validation, M30ArchiveValidation):
            raise M30PublishedVisualizerError(
                "archive_validation must be M30ArchiveValidation"
            )
        if self.archive_validation.archive_sha256 != FRP_M30_ARCHIVE_SHA256:
            raise M30PublishedVisualizerError(
                "full-core evidence is not from the exact M30 archive"
            )
        retained_paths = tuple(
            retained.member.path
            for retained in self.archive_validation.retained_members
        )
        if retained_paths != _FULL_CORE_RETAIN_PATHS:
            raise M30PublishedVisualizerError(
                "full-core retained-member inventory changed"
            )
        if not isinstance(self.canonical_bundle, ParsedJsonArtifact):
            raise M30PublishedVisualizerError(
                "canonical_bundle must be ParsedJsonArtifact"
            )
        if not isinstance(self.fixture_manifest, ParsedJsonArtifact):
            raise M30PublishedVisualizerError(
                "fixture_manifest must be ParsedJsonArtifact"
            )
        if (
            not isinstance(self.trace_sources, tuple)
            or tuple(source.dataset_id for source in self.trace_sources)
            != tuple(spec.dataset_id for spec in _TRACE_SPECS)
        ):
            raise M30PublishedVisualizerError(
                "full-core trace source order changed"
            )
        if any(
            not isinstance(source, PublishedCoreTraceSource)
            for source in self.trace_sources
        ):
            raise M30PublishedVisualizerError(
                "trace_sources must contain PublishedCoreTraceSource values"
            )
        for source in self.trace_sources:
            if source.retained_member is not (
                self.archive_validation.retained_member(source.source_path)
            ):
                raise M30PublishedVisualizerError(
                    "M16 trace source is not retained by this validation"
                )
        if self.canonical_bundle.source_artifact.raw_bytes != (
            self.archive_validation.retained_member(
                _M28_BUNDLE_PATH
            ).raw_bytes
        ):
            raise M30PublishedVisualizerError(
                "canonical bundle differs from retained archive bytes"
            )
        if self.fixture_manifest.source_artifact.raw_bytes != (
            self.archive_validation.retained_member(
                _M28_FIXTURE_MANIFEST_PATH
            ).raw_bytes
        ):
            raise M30PublishedVisualizerError(
                "fixture manifest differs from retained archive bytes"
            )
        _validate_bundle(self.canonical_bundle, self.trace_sources)
        _validate_fixture_manifest(
            self.fixture_manifest,
            self.trace_sources,
        )
        _validate_sha256(self.evidence_sha256, "evidence_sha256")
        expected_digest = _evidence_sha256(
            self.archive_validation,
            self.canonical_bundle,
            self.fixture_manifest,
            self.trace_sources,
        )
        if self.evidence_sha256 != expected_digest:
            raise M30PublishedVisualizerError(
                "evidence_sha256 does not bind complete full-core evidence"
            )
        expected_id = str(uuid5(_EVIDENCE_NAMESPACE, expected_digest))
        if self.evidence_id != expected_id:
            raise M30PublishedVisualizerError(
                "evidence_id does not bind evidence_sha256"
            )

    def source_for_dataset(self, dataset_id: str) -> PublishedCoreTraceSource:
        """Resolve one exact trace dataset without aliases."""

        _validate_text(dataset_id, "dataset_id")
        matches = tuple(
            source
            for source in self.trace_sources
            if source.dataset_id == dataset_id
        )
        if len(matches) != 1:
            raise M30PublishedVisualizerError(
                f"unknown full-core trace dataset: {dataset_id!r}"
            )
        return matches[0]


def load_m30_full_core_trace_evidence(
    archive_path: str | Path,
) -> M30FullCoreTraceEvidence:
    """Validate and retain the exact read-only full-core M30 members."""

    validation = validate_m30_archive(
        archive_path,
        retain_paths=_FULL_CORE_RETAIN_PATHS,
    )
    trace_sources = tuple(
        _build_trace_source(validation, spec) for spec in _TRACE_SPECS
    )
    bundle = _parse_retained_member(validation, _M28_BUNDLE_PATH)
    manifest = _parse_retained_member(
        validation,
        _M28_FIXTURE_MANIFEST_PATH,
    )
    digest = _evidence_sha256(
        validation,
        bundle,
        manifest,
        trace_sources,
    )
    return M30FullCoreTraceEvidence(
        evidence_id=str(uuid5(_EVIDENCE_NAMESPACE, digest)),
        archive_validation=validation,
        canonical_bundle=bundle,
        fixture_manifest=manifest,
        trace_sources=trace_sources,
        evidence_sha256=digest,
    )


def _frame_payload(
    *,
    route_authority_sha256: str,
    trace_source_id: str,
    source_dataset_id: str,
    source_path: str,
    source_trace_sha256: str,
    measurement_contour: str,
    trace_record_id: str,
    source_record_sha256: str,
    sequence: int,
    execution_epoch: int,
    scheduler_mode: str,
    scheduler_state: str,
    cell_id: int,
    phase_derived_target: int,
    retained_state_before: int,
    retained_state_after: int,
    pending_route_before: int,
    pending_route_after: int,
    accepted: bool,
    accepted_change: bool,
    neutral_routed: bool,
    transition_classification: str,
    route_leg: str,
    source_location: SourceLocation,
) -> dict[str, object]:
    return {
        "accepted": accepted,
        "accepted_change": accepted_change,
        "cell_id": cell_id,
        "execution_epoch": execution_epoch,
        "measurement_contour": measurement_contour,
        "neutral_routed": neutral_routed,
        "pending_route_after": pending_route_after,
        "pending_route_before": pending_route_before,
        "phase_derived_target": phase_derived_target,
        "retained_state_after": retained_state_after,
        "retained_state_before": retained_state_before,
        "route_authority_sha256": route_authority_sha256,
        "route_leg": route_leg,
        "scheduler_mode": scheduler_mode,
        "scheduler_state": scheduler_state,
        "sequence": sequence,
        "source_dataset_id": source_dataset_id,
        "source_location": {
            "array_index": source_location.array_index,
            "json_path": source_location.json_path,
            "package_member": source_location.package_member,
            "source_record_ordinal": source_location.source_record_ordinal,
        },
        "source_path": source_path,
        "source_record_sha256": source_record_sha256,
        "source_trace_sha256": source_trace_sha256,
        "trace_record_id": trace_record_id,
        "trace_source_id": trace_source_id,
        "transition_classification": transition_classification,
    }


@dataclass(frozen=True, slots=True)
class PublishedTransitionFrame:
    """One exact source-linked M16 cell transition for presentation."""

    transition_frame_id: str
    route_authority_sha256: str
    trace_source_id: str
    source_dataset_id: str
    source_path: str
    source_trace_sha256: str
    measurement_contour: str
    trace_record_id: str
    source_record_sha256: str
    sequence: int
    execution_epoch: int
    scheduler_mode: str
    scheduler_state: str
    cell_id: int
    phase_derived_target: int
    retained_state_before: int
    retained_state_after: int
    pending_route_before: int
    pending_route_after: int
    accepted: bool
    accepted_change: bool
    neutral_routed: bool
    transition_classification: str
    route_leg: str
    source_location: SourceLocation
    frame_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.transition_frame_id, "transition_frame_id")
        _validate_sha256(
            self.route_authority_sha256,
            "route_authority_sha256",
        )
        if self.route_authority_sha256 != _M28_BUNDLE_RAW_SHA256:
            raise M30PublishedVisualizerError(
                "transition frame lost exact M28 route authority"
            )
        _validate_uuid(self.trace_source_id, "trace_source_id")
        spec = _TRACE_SPEC_BY_DATASET.get(self.source_dataset_id)
        if spec is None:
            raise M30PublishedVisualizerError(
                "transition frame has unknown source dataset"
            )
        if (
            self.source_path != spec.source_path
            or self.source_trace_sha256 != spec.raw_sha256
            or self.measurement_contour != spec.measurement_contour
            or self.trace_source_id
            != str(
                uuid5(
                    _SOURCE_NAMESPACE,
                    f"{spec.dataset_id}:{spec.raw_sha256}",
                )
            )
        ):
            raise M30PublishedVisualizerError(
                "transition frame source identity changed"
            )
        _validate_uuid(self.trace_record_id, "trace_record_id")
        _validate_sha256(self.source_record_sha256, "source_record_sha256")
        _validate_nonnegative_integer(self.sequence, "sequence")
        if self.sequence >= spec.record_count:
            raise M30PublishedVisualizerError(
                "transition frame sequence is out of range"
            )
        _validate_nonnegative_integer(self.execution_epoch, "execution_epoch")
        if self.scheduler_mode not in _VALID_SCHEDULER_MODES:
            raise M30PublishedVisualizerError("unknown scheduler mode")
        if self.scheduler_state not in _VALID_SCHEDULER_STATES:
            raise M30PublishedVisualizerError("unknown scheduler state")
        _validate_nonnegative_integer(self.cell_id, "cell_id")
        if self.cell_id >= 8:
            raise M30PublishedVisualizerError("cell_id is out of range")
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
                raise M30PublishedVisualizerError(f"{field} must be boolean")
        expected_classification = _transition_classification(
            self.retained_state_before,
            self.retained_state_after,
        )
        if self.transition_classification != expected_classification:
            raise M30PublishedVisualizerError(
                "transition classification differs from exact state pair"
            )
        if self.route_leg not in _ROUTE_LEGS:
            raise M30PublishedVisualizerError(
                "unknown route-leg classification"
            )
        if self.route_leg == "first_leg_neutralization" and not (
            self.neutral_routed
            and self.retained_state_after == 0
            and self.pending_route_after in (-1, 1)
        ):
            raise M30PublishedVisualizerError(
                "first route leg must retain active neutral 0"
            )
        if self.route_leg == "pending_route_completion" and not (
            self.pending_route_before in (-1, 1)
            and self.retained_state_before == 0
            and self.retained_state_after == self.pending_route_before
            and self.pending_route_after == 0
        ):
            raise M30PublishedVisualizerError(
                "pending completion does not match exact route relation"
            )
        if not isinstance(self.source_location, SourceLocation):
            raise M30PublishedVisualizerError(
                "source_location must be SourceLocation"
            )
        expected_location = SourceLocation(
            json_path=(
                f"$.records[{self.sequence}]."
                f"retained_state_after[{self.cell_id}]"
            ),
            array_index=self.cell_id,
            package_member=spec.source_path,
            source_record_ordinal=self.sequence + 1,
        )
        if self.source_location != expected_location:
            raise M30PublishedVisualizerError(
                "transition frame source location changed"
            )
        _validate_sha256(self.frame_sha256, "frame_sha256")
        expected_digest = _sha256(
            _canonical_json_bytes(self.deterministic_payload())
        )
        if self.frame_sha256 != expected_digest:
            raise M30PublishedVisualizerError(
                "frame_sha256 does not bind complete projection"
            )
        if self.transition_frame_id != str(
            uuid5(_FRAME_NAMESPACE, self.frame_sha256)
        ):
            raise M30PublishedVisualizerError(
                "transition_frame_id does not bind frame_sha256"
            )

    def deterministic_payload(self) -> dict[str, object]:
        """Return the complete canonical frame payload."""

        return _frame_payload(
            route_authority_sha256=self.route_authority_sha256,
            trace_source_id=self.trace_source_id,
            source_dataset_id=self.source_dataset_id,
            source_path=self.source_path,
            source_trace_sha256=self.source_trace_sha256,
            measurement_contour=self.measurement_contour,
            trace_record_id=self.trace_record_id,
            source_record_sha256=self.source_record_sha256,
            sequence=self.sequence,
            execution_epoch=self.execution_epoch,
            scheduler_mode=self.scheduler_mode,
            scheduler_state=self.scheduler_state,
            cell_id=self.cell_id,
            phase_derived_target=self.phase_derived_target,
            retained_state_before=self.retained_state_before,
            retained_state_after=self.retained_state_after,
            pending_route_before=self.pending_route_before,
            pending_route_after=self.pending_route_after,
            accepted=self.accepted,
            accepted_change=self.accepted_change,
            neutral_routed=self.neutral_routed,
            transition_classification=self.transition_classification,
            route_leg=self.route_leg,
            source_location=self.source_location,
        )


def _build_frame(
    source: PublishedCoreTraceSource,
    record: PublishedTraceRecord,
    cell: PublishedTraceCell,
) -> PublishedTransitionFrame:
    classification = _transition_classification(
        cell.retained_state_before,
        cell.retained_state_after,
    )
    route_leg = _route_leg(cell)
    location = SourceLocation(
        json_path=(
            f"$.records[{record.sequence}]."
            f"retained_state_after[{cell.cell_id}]"
        ),
        array_index=cell.cell_id,
        package_member=source.source_path,
        source_record_ordinal=record.sequence + 1,
    )
    payload = _frame_payload(
        route_authority_sha256=_M28_BUNDLE_RAW_SHA256,
        trace_source_id=source.trace_source_id,
        source_dataset_id=source.dataset_id,
        source_path=source.source_path,
        source_trace_sha256=source.raw_sha256,
        measurement_contour=source.measurement_contour,
        trace_record_id=record.trace_record_id,
        source_record_sha256=record.source_record_sha256,
        sequence=record.sequence,
        execution_epoch=record.execution_epoch,
        scheduler_mode=record.scheduler.mode,
        scheduler_state=record.scheduler.state,
        cell_id=cell.cell_id,
        phase_derived_target=cell.phase_derived_target,
        retained_state_before=cell.retained_state_before,
        retained_state_after=cell.retained_state_after,
        pending_route_before=cell.pending_route_before,
        pending_route_after=cell.pending_route_after,
        accepted=cell.accepted,
        accepted_change=cell.accepted_change,
        neutral_routed=cell.neutral_routed,
        transition_classification=classification,
        route_leg=route_leg,
        source_location=location,
    )
    digest = _sha256(_canonical_json_bytes(payload))
    return PublishedTransitionFrame(
        transition_frame_id=str(uuid5(_FRAME_NAMESPACE, digest)),
        route_authority_sha256=_M28_BUNDLE_RAW_SHA256,
        trace_source_id=source.trace_source_id,
        source_dataset_id=source.dataset_id,
        source_path=source.source_path,
        source_trace_sha256=source.raw_sha256,
        measurement_contour=source.measurement_contour,
        trace_record_id=record.trace_record_id,
        source_record_sha256=record.source_record_sha256,
        sequence=record.sequence,
        execution_epoch=record.execution_epoch,
        scheduler_mode=record.scheduler.mode,
        scheduler_state=record.scheduler.state,
        cell_id=cell.cell_id,
        phase_derived_target=cell.phase_derived_target,
        retained_state_before=cell.retained_state_before,
        retained_state_after=cell.retained_state_after,
        pending_route_before=cell.pending_route_before,
        pending_route_after=cell.pending_route_after,
        accepted=cell.accepted,
        accepted_change=cell.accepted_change,
        neutral_routed=cell.neutral_routed,
        transition_classification=classification,
        route_leg=route_leg,
        source_location=location,
        frame_sha256=digest,
    )


@dataclass(frozen=True, slots=True)
class PublishedTelemetrySemantic:
    """One exact M27 dimensionless model-derived telemetry declaration."""

    semantic_record_id: str
    visualizer_dispatch_sha256: str
    ordinal: int
    telemetry_id: str
    classification: str
    domain_minimum: int
    domain_maximum: int
    relation: str
    storage_type: str
    source_location: SourceLocation
    source_record_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.semantic_record_id, "semantic_record_id")
        _validate_sha256(
            self.visualizer_dispatch_sha256,
            "visualizer_dispatch_sha256",
        )
        if self.visualizer_dispatch_sha256 != (
            _M27_VISUALIZER_DISPATCH_SHA256
        ):
            raise M30PublishedVisualizerError(
                "semantic record lost exact M27 visualizer route"
            )
        _validate_nonnegative_integer(self.ordinal, "ordinal")
        for field, value in (
            ("telemetry_id", self.telemetry_id),
            ("classification", self.classification),
            ("relation", self.relation),
            ("storage_type", self.storage_type),
        ):
            _validate_text(value, field)
        _validate_integer(self.domain_minimum, "domain_minimum")
        _validate_integer(self.domain_maximum, "domain_maximum")
        if self.domain_minimum > self.domain_maximum:
            raise M30PublishedVisualizerError(
                "telemetry domain minimum exceeds maximum"
            )
        if not isinstance(self.source_location, SourceLocation):
            raise M30PublishedVisualizerError(
                "source_location must be SourceLocation"
            )
        expected_location = SourceLocation(
            json_path=f"$.telemetry[{self.ordinal}]",
            array_index=self.ordinal,
            package_member=_M27_SOURCE_PATH,
            source_record_ordinal=self.ordinal + 1,
        )
        if self.source_location != expected_location:
            raise M30PublishedVisualizerError(
                "telemetry source location changed"
            )
        _validate_sha256(self.source_record_sha256, "source_record_sha256")
        if self.source_record_sha256 != _source_sha256(
            self.source_payload()
        ):
            raise M30PublishedVisualizerError(
                "semantic source digest differs from exact declaration"
            )
        expected_id = str(
            uuid5(
                _SEMANTIC_NAMESPACE,
                (
                    f"{self.visualizer_dispatch_sha256}:"
                    f"{self.ordinal}:{self.source_record_sha256}"
                ),
            )
        )
        if self.semantic_record_id != expected_id:
            raise M30PublishedVisualizerError(
                "semantic_record_id does not bind source identity"
            )

    def source_payload(self) -> dict[str, object]:
        """Reconstruct the exact upstream telemetry declaration."""

        return {
            "classification": self.classification,
            "domain": {
                "maximum": self.domain_maximum,
                "minimum": self.domain_minimum,
            },
            "relation": self.relation,
            "storage_type": self.storage_type,
            "telemetry_id": self.telemetry_id,
        }


def _build_semantic(
    dispatch: PublishedModeDispatch,
    value: object,
    ordinal: int,
) -> PublishedTelemetrySemantic:
    source = _require_mapping(value, f"telemetry[{ordinal}]")
    domain = _require_mapping(source.get("domain"), "telemetry domain")
    source_digest = _source_sha256(source)
    semantic_id = str(
        uuid5(
            _SEMANTIC_NAMESPACE,
            f"{dispatch.dispatch_sha256}:{ordinal}:{source_digest}",
        )
    )
    return PublishedTelemetrySemantic(
        semantic_record_id=semantic_id,
        visualizer_dispatch_sha256=dispatch.dispatch_sha256,
        ordinal=ordinal,
        telemetry_id=_validate_text(
            source.get("telemetry_id"),
            "telemetry_id",
        ),
        classification=_validate_text(
            source.get("classification"),
            "classification",
        ),
        domain_minimum=_validate_integer(
            domain.get("minimum"),
            "domain minimum",
        ),
        domain_maximum=_validate_integer(
            domain.get("maximum"),
            "domain maximum",
        ),
        relation=_validate_text(source.get("relation"), "relation"),
        storage_type=_validate_text(
            source.get("storage_type"),
            "storage_type",
        ),
        source_location=SourceLocation(
            json_path=f"$.telemetry[{ordinal}]",
            array_index=ordinal,
            package_member=_M27_SOURCE_PATH,
            source_record_ordinal=ordinal + 1,
        ),
        source_record_sha256=source_digest,
    )


def _dataset_sha256(
    audit_batch: PublishedAuditBatch,
    trace_dataset: M30PublishedTraceDataset,
    full_core_evidence: M30FullCoreTraceEvidence,
    m16_audit_report: PublishedAuditReport,
    m27_audit_report: PublishedAuditReport,
    m16_dispatch: PublishedModeDispatch,
    m27_dispatch: PublishedModeDispatch,
    frames: tuple[PublishedTransitionFrame, ...],
    semantics: tuple[PublishedTelemetrySemantic, ...],
    validated_relations: tuple[str, ...],
    interpretation_boundary: tuple[tuple[str, object], ...],
    semantics_digest: str,
) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "audit_batch_sha256": audit_batch.batch_sha256,
                "full_core_evidence_sha256": (
                    full_core_evidence.evidence_sha256
                ),
                "interpretation_boundary": dict(
                    interpretation_boundary
                ),
                "m16_audit_report_sha256": (
                    m16_audit_report.report_sha256
                ),
                "m16_visualizer_dispatch_sha256": (
                    m16_dispatch.dispatch_sha256
                ),
                "m27_audit_report_sha256": (
                    m27_audit_report.report_sha256
                ),
                "m27_semantics_digest": semantics_digest,
                "m27_visualizer_dispatch_sha256": (
                    m27_dispatch.dispatch_sha256
                ),
                "semantic_records": [
                    {
                        "semantic_record_id": item.semantic_record_id,
                        "source_record_sha256": (
                            item.source_record_sha256
                        ),
                    }
                    for item in semantics
                ],
                "trace_dataset_sha256": trace_dataset.dataset_sha256,
                "transition_frames": [
                    {
                        "frame_sha256": frame.frame_sha256,
                        "transition_frame_id": frame.transition_frame_id,
                    }
                    for frame in frames
                ],
                "validated_relations": list(validated_relations),
            }
        )
    )


@dataclass(frozen=True, slots=True)
class M30PublishedTransitionVisualizerDataset:
    """Deterministic full-core M30 transition-visualizer dataset."""

    visualizer_dataset_id: str
    audit_batch: PublishedAuditBatch
    trace_dataset: M30PublishedTraceDataset
    full_core_evidence: M30FullCoreTraceEvidence
    m16_audit_report: PublishedAuditReport
    m27_audit_report: PublishedAuditReport
    m16_dispatch: PublishedModeDispatch
    m27_dispatch: PublishedModeDispatch
    transition_frames: tuple[PublishedTransitionFrame, ...]
    telemetry_semantics: tuple[PublishedTelemetrySemantic, ...]
    validated_relations: tuple[str, ...]
    interpretation_boundary: tuple[tuple[str, object], ...]
    semantics_digest: str
    dataset_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.visualizer_dataset_id, "visualizer_dataset_id")
        if not isinstance(self.audit_batch, PublishedAuditBatch):
            raise M30PublishedVisualizerError(
                "audit_batch must be PublishedAuditBatch"
            )
        if self.audit_batch.overall_status is not (
            ValidationStatus.RECOGNIZED_VALID
        ):
            raise M30PublishedVisualizerError("M6 audit batch must pass")
        if not isinstance(self.trace_dataset, M30PublishedTraceDataset):
            raise M30PublishedVisualizerError(
                "trace_dataset must be M30PublishedTraceDataset"
            )
        if self.trace_dataset.audit_batch is not self.audit_batch:
            raise M30PublishedVisualizerError(
                "M7 and M8 must share the exact M6 audit batch"
            )
        if not isinstance(
            self.full_core_evidence,
            M30FullCoreTraceEvidence,
        ):
            raise M30PublishedVisualizerError(
                "full_core_evidence must be M30FullCoreTraceEvidence"
            )
        if self.full_core_evidence.archive_validation.archive_sha256 != (
            self.audit_batch.dispatch_batch.archive_sha256
        ):
            raise M30PublishedVisualizerError(
                "M6 and full-core evidence archives differ"
            )
        for report, member_id, field in (
            (
                self.m16_audit_report,
                _FPGA_REGISTRY_MEMBER_ID,
                "m16_audit_report",
            ),
            (
                self.m27_audit_report,
                _M27_MEMBER_ID,
                "m27_audit_report",
            ),
        ):
            if not isinstance(report, PublishedAuditReport):
                raise M30PublishedVisualizerError(
                    f"{field} must be PublishedAuditReport"
                )
            if report is not self.audit_batch.report_for_member(member_id):
                raise M30PublishedVisualizerError(
                    f"{field} is not exact M6 evidence"
                )
            if report.overall_status is not ValidationStatus.RECOGNIZED_VALID:
                raise M30PublishedVisualizerError(f"{field} must pass")
        expected_m16_dispatch = (
            self.audit_batch.dispatch_batch.dispatch_for(
                _FPGA_REGISTRY_MEMBER_ID,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            )
        )
        expected_m27_dispatch = (
            self.audit_batch.dispatch_batch.dispatch_for(
                _M27_MEMBER_ID,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            )
        )
        if self.m16_dispatch is not expected_m16_dispatch:
            raise M30PublishedVisualizerError(
                "m16_dispatch is not exact M5 visualizer route"
            )
        if self.m27_dispatch is not expected_m27_dispatch:
            raise M30PublishedVisualizerError(
                "m27_dispatch is not exact M5 visualizer route"
            )
        if (
            self.m16_dispatch.dispatch_sha256
            != _M16_VISUALIZER_DISPATCH_SHA256
            or self.m27_dispatch.dispatch_sha256
            != _M27_VISUALIZER_DISPATCH_SHA256
        ):
            raise M30PublishedVisualizerError(
                "M5 visualizer dispatch identity changed"
            )
        fpga_source = self.full_core_evidence.source_for_dataset(
            _FPGA_SPEC.dataset_id
        )
        if self.m16_dispatch.raw_bytes != fpga_source.retained_member.raw_bytes:
            raise M30PublishedVisualizerError(
                "M5 FPGA dispatch and direct full-core bytes differ"
            )
        if self.trace_dataset.dispatch.raw_bytes != (
            fpga_source.retained_member.raw_bytes
        ):
            raise M30PublishedVisualizerError(
                "M7 FPGA source and direct full-core bytes differ"
            )
        if len(self.trace_dataset.records) != len(fpga_source.records):
            raise M30PublishedVisualizerError(
                "M7 FPGA record inventory changed"
            )
        for m7_record, source_record in zip(
            self.trace_dataset.records,
            fpga_source.records,
            strict=True,
        ):
            if (
                m7_record.source_payload()
                != source_record.source_payload()
                or m7_record.source_record_sha256
                != source_record.source_record_sha256
            ):
                raise M30PublishedVisualizerError(
                    "M7 FPGA projection differs from full-core source"
                )
        contract = self.audit_batch.report_for_member(
            _M28_UPSTREAM_MEMBER_ID
        ).dispatch.parsed_artifact.root
        core = _require_mapping(
            _require_mapping(contract, "M28 upstream contract").get(
                "immutable_core"
            ),
            "immutable_core",
        )
        if (
            core.get("balanced_ternary_notation") != "-1/0/1"
            or _plain(core.get("semantic_values")) != [-1, 0, 1]
            or core.get("active_neutral_state") != 0
            or _plain(core.get("opposite_transition_routes"))
            != [[-1, 0, 1], [1, 0, -1]]
            or core.get("service_scheduler_mode") != "free"
            or _plain(core.get("temporal_scheduler_modes"))
            != ["1/7", "7/1"]
        ):
            raise M30PublishedVisualizerError("immutable FRP core changed")
        direction = _require_mapping(
            _require_mapping(contract, "M28 upstream contract").get(
                "integration_direction"
            ),
            "integration_direction",
        )
        if (
            direction.get("producer") != "Fractal-Resonance-Processor"
            or direction.get("consumer") != "FRP-Trace-Observatory"
            or direction.get("direction")
            != "upstream_to_downstream_only"
            or direction.get("transport")
            != "published_versioned_artifacts"
            or direction.get("upstream_semantic_authority") is not True
            or direction.get("downstream_source_mutation") != "forbidden"
            or direction.get("downstream_writeback") != "forbidden"
        ):
            raise M30PublishedVisualizerError(
                "Observatory read-only upstream boundary changed"
            )
        if (
            not isinstance(self.transition_frames, tuple)
            or len(self.transition_frames) != 800
            or any(
                not isinstance(frame, PublishedTransitionFrame)
                for frame in self.transition_frames
            )
        ):
            raise M30PublishedVisualizerError(
                "transition_frames must contain exactly 800 frames"
            )
        expected_pairs = tuple(
            (source, record, cell)
            for source in self.full_core_evidence.trace_sources
            for record in source.records
            for cell in record.cells
        )
        for frame, (source, record, cell) in zip(
            self.transition_frames,
            expected_pairs,
            strict=True,
        ):
            observed = (
                frame.trace_source_id,
                frame.source_dataset_id,
                frame.source_path,
                frame.source_trace_sha256,
                frame.measurement_contour,
                frame.trace_record_id,
                frame.source_record_sha256,
                frame.sequence,
                frame.execution_epoch,
                frame.scheduler_mode,
                frame.scheduler_state,
                frame.cell_id,
                frame.phase_derived_target,
                frame.retained_state_before,
                frame.retained_state_after,
                frame.pending_route_before,
                frame.pending_route_after,
                frame.accepted,
                frame.accepted_change,
                frame.neutral_routed,
                frame.transition_classification,
                frame.route_leg,
            )
            expected = (
                source.trace_source_id,
                source.dataset_id,
                source.source_path,
                source.raw_sha256,
                source.measurement_contour,
                record.trace_record_id,
                record.source_record_sha256,
                record.sequence,
                record.execution_epoch,
                record.scheduler.mode,
                record.scheduler.state,
                cell.cell_id,
                cell.phase_derived_target,
                cell.retained_state_before,
                cell.retained_state_after,
                cell.pending_route_before,
                cell.pending_route_after,
                cell.accepted,
                cell.accepted_change,
                cell.neutral_routed,
                _transition_classification(
                    cell.retained_state_before,
                    cell.retained_state_after,
                ),
                _route_leg(cell),
            )
            if observed != expected:
                raise M30PublishedVisualizerError(
                    "transition frame differs from exact M16 source cell"
                )
        if self.observed_ternary_domain != (-1, 0, 1):
            raise M30PublishedVisualizerError(
                "complete observed ternary domain changed"
            )
        if self.scheduler_mode_record_counts != _EXPECTED_MODE_COUNTS:
            raise M30PublishedVisualizerError(
                "complete scheduler mode counts changed"
            )
        if self.scheduler_state_record_counts != _EXPECTED_STATE_COUNTS:
            raise M30PublishedVisualizerError(
                "complete scheduler state counts changed"
            )
        if (
            self.transition_classification_counts
            != _EXPECTED_TRANSITION_COUNTS
        ):
            raise M30PublishedVisualizerError(
                "complete transition classification counts changed"
            )
        if self.route_leg_counts != _EXPECTED_ROUTE_COUNTS:
            raise M30PublishedVisualizerError(
                "complete neutral-route leg counts changed"
            )
        if any(
            (frame.retained_state_before, frame.retained_state_after)
            in ((-1, 1), (1, -1))
            for frame in self.transition_frames
        ):
            raise M30PublishedVisualizerError(
                "visualizer contains a direct opposite transition"
            )
        if (
            not isinstance(self.telemetry_semantics, tuple)
            or len(self.telemetry_semantics) != 6
            or any(
                not isinstance(item, PublishedTelemetrySemantic)
                for item in self.telemetry_semantics
            )
        ):
            raise M30PublishedVisualizerError(
                "telemetry_semantics must contain six declarations"
            )
        if tuple(item.ordinal for item in self.telemetry_semantics) != tuple(
            range(6)
        ):
            raise M30PublishedVisualizerError(
                "telemetry semantics lost exact source order"
            )
        m27_root = _require_mapping(
            self.m27_dispatch.parsed_artifact.root,
            "M27 parsed root",
        )
        source_semantics = _require_sequence(
            m27_root.get("telemetry"),
            "M27 telemetry",
        )
        if [
            item.source_payload() for item in self.telemetry_semantics
        ] != _plain(source_semantics):
            raise M30PublishedVisualizerError(
                "telemetry semantics differ from exact M27 source"
            )
        if self.validated_relations != _VALIDATED_RELATIONS or list(
            self.validated_relations
        ) != _plain(m27_root.get("validated_relations")):
            raise M30PublishedVisualizerError(
                "validated M27 relations changed"
            )
        if self.interpretation_boundary != _INTERPRETATION_BOUNDARY or dict(
            self.interpretation_boundary
        ) != _plain(m27_root.get("interpretation_boundary")):
            raise M30PublishedVisualizerError(
                "M27 interpretation boundary changed"
            )
        _validate_sha256(self.semantics_digest, "semantics_digest")
        if (
            self.semantics_digest != _M27_SEMANTICS_DIGEST
            or self.semantics_digest != m27_root.get("semantics_digest")
        ):
            raise M30PublishedVisualizerError(
                "M27 semantics digest changed"
            )
        _validate_sha256(self.dataset_sha256, "dataset_sha256")
        expected_digest = _dataset_sha256(
            self.audit_batch,
            self.trace_dataset,
            self.full_core_evidence,
            self.m16_audit_report,
            self.m27_audit_report,
            self.m16_dispatch,
            self.m27_dispatch,
            self.transition_frames,
            self.telemetry_semantics,
            self.validated_relations,
            self.interpretation_boundary,
            self.semantics_digest,
        )
        if self.dataset_sha256 != expected_digest:
            raise M30PublishedVisualizerError(
                "dataset_sha256 does not bind complete M8 evidence"
            )
        if self.visualizer_dataset_id != str(
            uuid5(_DATASET_NAMESPACE, self.dataset_sha256)
        ):
            raise M30PublishedVisualizerError(
                "visualizer_dataset_id does not bind dataset_sha256"
            )

    @property
    def canonical_temporal_scheduler_modes(self) -> tuple[str, str]:
        """Return the immutable temporal scheduler modes."""

        return _CANONICAL_TEMPORAL_MODES

    @property
    def observed_scheduler_modes(self) -> tuple[str, ...]:
        """Return actual source-observed modes in first-occurrence order."""

        return tuple(
            dict.fromkeys(
                record.scheduler.mode
                for source in self.full_core_evidence.trace_sources
                for record in source.records
            )
        )

    @property
    def scheduler_mode_record_counts(self) -> tuple[tuple[str, int], ...]:
        """Return exact full-core record counts by scheduler mode."""

        counts = Counter(
            record.scheduler.mode
            for source in self.full_core_evidence.trace_sources
            for record in source.records
        )
        return tuple((mode, counts.get(mode, 0)) for mode, _ in _EXPECTED_MODE_COUNTS)

    @property
    def scheduler_state_record_counts(self) -> tuple[tuple[str, int], ...]:
        """Return exact full-core record counts by scheduler state."""

        counts = Counter(
            record.scheduler.state
            for source in self.full_core_evidence.trace_sources
            for record in source.records
        )
        return tuple(
            (state, counts.get(state, 0))
            for state, _ in _EXPECTED_STATE_COUNTS
        )

    @property
    def transition_classification_counts(self) -> tuple[tuple[str, int], ...]:
        """Return exact frame totals by transition classification."""

        counts = Counter(
            frame.transition_classification for frame in self.transition_frames
        )
        return tuple(
            (name, counts.get(name, 0))
            for name in _TRANSITION_CLASSIFICATIONS
        )

    @property
    def route_leg_counts(self) -> tuple[tuple[str, int], ...]:
        """Return exact frame totals by active-neutral route leg."""

        counts = Counter(frame.route_leg for frame in self.transition_frames)
        return tuple((name, counts.get(name, 0)) for name in _ROUTE_LEGS)

    @property
    def observed_ternary_domain(self) -> tuple[int, ...]:
        """Return the complete source-observed balanced ternary domain."""

        values: set[int] = set()
        for source in self.full_core_evidence.trace_sources:
            for record in source.records:
                for cell in record.cells:
                    values.update(
                        (
                            cell.phase_derived_target,
                            cell.retained_state_before,
                            cell.retained_state_after,
                            cell.pending_route_before,
                            cell.pending_route_after,
                        )
                    )
                values.update(
                    request.target_state for request in record.requests
                )
        return tuple(sorted(values))

    @property
    def trace_record_count(self) -> int:
        """Return the exact combined M16 record count."""

        return sum(
            len(source.records)
            for source in self.full_core_evidence.trace_sources
        )


def build_m30_published_transition_visualizer(
    audit_batch: PublishedAuditBatch,
    full_core_evidence: M30FullCoreTraceEvidence,
) -> M30PublishedTransitionVisualizerDataset:
    """Build the exact full-core M30 transition-visualizer dataset."""

    if not isinstance(audit_batch, PublishedAuditBatch):
        raise M30PublishedVisualizerError(
            "audit_batch must be PublishedAuditBatch"
        )
    if audit_batch.overall_status is not ValidationStatus.RECOGNIZED_VALID:
        raise M30PublishedVisualizerError("M6 audit batch must pass before M8")
    if not isinstance(full_core_evidence, M30FullCoreTraceEvidence):
        raise M30PublishedVisualizerError(
            "full_core_evidence must be M30FullCoreTraceEvidence"
        )
    trace_dataset = build_m30_published_trace_dataset(audit_batch)
    m16_report = audit_batch.report_for_member(_FPGA_REGISTRY_MEMBER_ID)
    m27_report = audit_batch.report_for_member(_M27_MEMBER_ID)
    m16_dispatch = audit_batch.dispatch_batch.dispatch_for(
        _FPGA_REGISTRY_MEMBER_ID,
        ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    )
    m27_dispatch = audit_batch.dispatch_batch.dispatch_for(
        _M27_MEMBER_ID,
        ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    )
    frames = tuple(
        _build_frame(source, record, cell)
        for source in full_core_evidence.trace_sources
        for record in source.records
        for cell in record.cells
    )
    m27_root = _require_mapping(
        m27_dispatch.parsed_artifact.root,
        "M27 parsed root",
    )
    source_semantics = _require_sequence(
        m27_root.get("telemetry"),
        "M27 telemetry",
    )
    semantics = tuple(
        _build_semantic(m27_dispatch, value, ordinal)
        for ordinal, value in enumerate(source_semantics)
    )
    validated_relations = tuple(
        _validate_text(value, f"validated_relations[{index}]")
        for index, value in enumerate(
            _require_sequence(
                m27_root.get("validated_relations"),
                "validated_relations",
            )
        )
    )
    interpretation_source = _require_mapping(
        m27_root.get("interpretation_boundary"),
        "interpretation_boundary",
    )
    interpretation_boundary = tuple(
        (name, interpretation_source.get(name))
        for name, _ in _INTERPRETATION_BOUNDARY
    )
    semantics_digest = _validate_sha256(
        m27_root.get("semantics_digest"),
        "semantics_digest",
    )
    digest = _dataset_sha256(
        audit_batch,
        trace_dataset,
        full_core_evidence,
        m16_report,
        m27_report,
        m16_dispatch,
        m27_dispatch,
        frames,
        semantics,
        validated_relations,
        interpretation_boundary,
        semantics_digest,
    )
    return M30PublishedTransitionVisualizerDataset(
        visualizer_dataset_id=str(uuid5(_DATASET_NAMESPACE, digest)),
        audit_batch=audit_batch,
        trace_dataset=trace_dataset,
        full_core_evidence=full_core_evidence,
        m16_audit_report=m16_report,
        m27_audit_report=m27_report,
        m16_dispatch=m16_dispatch,
        m27_dispatch=m27_dispatch,
        transition_frames=frames,
        telemetry_semantics=semantics,
        validated_relations=validated_relations,
        interpretation_boundary=interpretation_boundary,
        semantics_digest=semantics_digest,
        dataset_sha256=digest,
    )


def visualize_m30_published_archive(
    archive_path: str | Path,
) -> M30PublishedTransitionVisualizerDataset:
    """Validate M1 through M7 and build the exact M8 full-core dataset."""

    path = Path(archive_path)
    audit_batch = audit_m30_published_archive(path)
    evidence = load_m30_full_core_trace_evidence(path)
    return build_m30_published_transition_visualizer(
        audit_batch,
        evidence,
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one deterministic read-only full-core transition "
            "visualizer dataset from exact FRP M30 publications."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    arguments = parser.parse_args()
    result = visualize_m30_published_archive(arguments.archive)
    print("FRP Observatory M8 full-core Transition Visualizer: PASS")
    print(f"trace_sources={len(result.full_core_evidence.trace_sources)}")
    print(f"trace_records={result.trace_record_count}")
    print(f"transition_frames={len(result.transition_frames)}")
    print(f"telemetry_semantics={len(result.telemetry_semantics)}")
    print("balanced_ternary_notation=-1/0/1")
    print("active_neutral_state=0")
    print(
        "temporal_scheduler_modes="
        + ",".join(result.canonical_temporal_scheduler_modes)
    )
    print(
        "observed_scheduler_modes="
        + ",".join(result.observed_scheduler_modes)
    )
    print(
        "scheduler_mode_record_counts="
        f"{result.scheduler_mode_record_counts}"
    )
    print(
        "scheduler_state_record_counts="
        f"{result.scheduler_state_record_counts}"
    )
    print(
        "observed_ternary_domain="
        + "/".join(str(value) for value in result.observed_ternary_domain)
    )
    print(
        "transition_classification_counts="
        f"{result.transition_classification_counts}"
    )
    print(f"route_leg_counts={result.route_leg_counts}")
    print(f"dataset_sha256={result.dataset_sha256}")
    print(f"visualizer_dataset_id={result.visualizer_dataset_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
