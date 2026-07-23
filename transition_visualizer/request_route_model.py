"""Immutable request-lane and route-event records for visualization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from artifact_auditor.audit_report import SourceLocation
from transition_visualizer.transition_model import (
    CanonicalTernaryState,
    RecordOrigin,
    SourceRecordReference,
    SourceStateValue,
)


__all__ = [
    "RequestAcceptanceStatus",
    "RequestLaneRecord",
    "RequestRouteModelError",
    "RouteEventRecord",
    "RouteStatus",
]


class RequestRouteModelError(ValueError):
    """Raised when request or route data violates its source contract."""


class RequestAcceptanceStatus(StrEnum):
    """Published request decision or explicit decision availability."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NOT_RECORDED = "not_recorded"
    NOT_APPLICABLE = "not_applicable"


class RouteStatus(StrEnum):
    """Route statuses published by supported FRP trace contracts."""

    PENDING = "pending"
    APPLIED = "applied"


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise RequestRouteModelError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise RequestRouteModelError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise RequestRouteModelError(
            f"{field_name} must not contain NUL"
        )


def _validate_optional_text(
    value: str | None,
    field_name: str,
) -> None:
    if value is not None:
        _validate_text(value, field_name)


def _validate_uuid(value: str, field_name: str) -> None:
    _validate_text(value, field_name)
    try:
        UUID(value)
    except (ValueError, AttributeError) as exc:
        raise RequestRouteModelError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_nonnegative_integer(
    value: int,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RequestRouteModelError(
            f"{field_name} must be an integer"
        )
    if value < 0:
        raise RequestRouteModelError(
            f"{field_name} must be nonnegative"
        )


def _validate_source_state(
    value: SourceStateValue,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RequestRouteModelError(
            f"{field_name} must be an integer or string"
        )
    if isinstance(value, str):
        _validate_text(value, field_name)


def _validate_unique_uuids(
    values: tuple[str, ...],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise RequestRouteModelError(f"{field_name} must be a tuple")
    for value in values:
        _validate_uuid(value, field_name)
    if len(set(values)) != len(values):
        raise RequestRouteModelError(f"{field_name} must be unique")


def _validate_origin(value: RecordOrigin) -> None:
    if not isinstance(value, RecordOrigin):
        raise RequestRouteModelError("origin must be a RecordOrigin")
    if value is RecordOrigin.OBSERVATORY_DERIVED:
        raise RequestRouteModelError(
            "request and route records cannot have derived origin"
        )


def _validate_target_binding(
    source_value: SourceStateValue | None,
    canonical_value: CanonicalTernaryState | None,
    origin: RecordOrigin,
    encoding_map_identifier: str | None,
) -> None:
    _validate_optional_text(
        encoding_map_identifier,
        "encoding_map_identifier",
    )
    if canonical_value is None:
        return
    if not isinstance(canonical_value, CanonicalTernaryState):
        raise RequestRouteModelError(
            "canonical target must be a CanonicalTernaryState or None"
        )
    if source_value is None:
        raise RequestRouteModelError(
            "canonical targets require a source target"
        )
    if origin is RecordOrigin.OBSERVATORY_NORMALIZED:
        if encoding_map_identifier is None:
            raise RequestRouteModelError(
                "normalized targets require an encoding-map identifier"
            )
    elif (
        not isinstance(source_value, int)
        or source_value != int(canonical_value)
    ):
        raise RequestRouteModelError(
            "source-origin targets must already use canonical values"
        )


@dataclass(frozen=True, slots=True)
class RequestLaneRecord:
    """One ordered request lane without inferred acceptance decisions."""

    request_lane_record_id: str
    source_reference: SourceRecordReference
    lane_index: int
    valid: bool
    acceptance_status: RequestAcceptanceStatus
    origin: RecordOrigin
    cell_id: int | None = None
    source_target_state: SourceStateValue | None = None
    canonical_target_state: CanonicalTernaryState | None = None
    encoding_map_identifier: str | None = None
    rejection_reason: str | None = None
    scheduler_decision: str | None = None
    capacity_decision: str | None = None
    decision_location: SourceLocation | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.request_lane_record_id,
            "request_lane_record_id",
        )
        if not isinstance(self.source_reference, SourceRecordReference):
            raise RequestRouteModelError(
                "source_reference must be a SourceRecordReference"
            )
        _validate_nonnegative_integer(self.lane_index, "lane_index")
        if not isinstance(self.valid, bool):
            raise RequestRouteModelError("valid must be a bool")
        if not isinstance(
            self.acceptance_status,
            RequestAcceptanceStatus,
        ):
            raise RequestRouteModelError(
                "acceptance_status must be a RequestAcceptanceStatus"
            )
        _validate_origin(self.origin)

        if self.cell_id is not None:
            _validate_nonnegative_integer(self.cell_id, "cell_id")
        if self.source_target_state is not None:
            _validate_source_state(
                self.source_target_state,
                "source_target_state",
            )
        if self.valid and (
            self.cell_id is None
            or self.source_target_state is None
            or self.canonical_target_state is None
        ):
            raise RequestRouteModelError(
                "valid lanes require cell, source target, and canonical target"
            )

        _validate_target_binding(
            self.source_target_state,
            self.canonical_target_state,
            self.origin,
            self.encoding_map_identifier,
        )

        optional_text = (
            ("rejection_reason", self.rejection_reason),
            ("scheduler_decision", self.scheduler_decision),
            ("capacity_decision", self.capacity_decision),
        )
        for field_name, value in optional_text:
            _validate_optional_text(value, field_name)

        published_statuses = {
            RequestAcceptanceStatus.ACCEPTED,
            RequestAcceptanceStatus.REJECTED,
        }
        if self.acceptance_status in published_statuses:
            if not isinstance(self.decision_location, SourceLocation):
                raise RequestRouteModelError(
                    "published decisions require a source location"
                )
        elif any(
            value is not None
            for value in (
                self.rejection_reason,
                self.scheduler_decision,
                self.capacity_decision,
                self.decision_location,
            )
        ):
            raise RequestRouteModelError(
                "unavailable decisions must not contain decision data"
            )

        if (
            self.rejection_reason is not None
            and self.acceptance_status
            is not RequestAcceptanceStatus.REJECTED
        ):
            raise RequestRouteModelError(
                "rejection_reason requires rejected status"
            )
        if (
            not self.valid
            and self.acceptance_status in published_statuses
        ):
            raise RequestRouteModelError(
                "invalid lanes cannot carry accepted or rejected status"
            )

        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )


@dataclass(frozen=True, slots=True)
class RouteEventRecord:
    """One published pending or applied route event."""

    route_event_record_id: str
    source_reference: SourceRecordReference
    cell_id: int
    source_target_state: SourceStateValue
    canonical_target_state: CanonicalTernaryState
    ready_tick: int
    route_status: RouteStatus
    origin: RecordOrigin
    route_index: int | None = None
    encoding_map_identifier: str | None = None
    related_transition_ids: tuple[str, ...] = ()
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.route_event_record_id,
            "route_event_record_id",
        )
        if not isinstance(self.source_reference, SourceRecordReference):
            raise RequestRouteModelError(
                "source_reference must be a SourceRecordReference"
            )
        _validate_nonnegative_integer(self.cell_id, "cell_id")
        _validate_source_state(
            self.source_target_state,
            "source_target_state",
        )
        _validate_origin(self.origin)
        _validate_target_binding(
            self.source_target_state,
            self.canonical_target_state,
            self.origin,
            self.encoding_map_identifier,
        )

        _validate_nonnegative_integer(self.ready_tick, "ready_tick")
        if not isinstance(self.route_status, RouteStatus):
            raise RequestRouteModelError(
                "route_status must be a RouteStatus"
            )
        if (
            self.route_status is RouteStatus.PENDING
            and self.ready_tick <= self.source_reference.tick
        ):
            raise RequestRouteModelError(
                "pending routes require a future ready_tick"
            )
        if (
            self.route_status is RouteStatus.APPLIED
            and self.ready_tick > self.source_reference.tick
        ):
            raise RequestRouteModelError(
                "applied routes cannot precede ready_tick"
            )

        if self.route_index is not None:
            _validate_nonnegative_integer(
                self.route_index,
                "route_index",
            )
        _validate_unique_uuids(
            self.related_transition_ids,
            "related_transition_ids",
        )
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )
