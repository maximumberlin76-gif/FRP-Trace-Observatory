"""Immutable transition telemetry and event-counter records."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from artifact_auditor.audit_report import SourceLocation
from transition_visualizer.transition_model import (
    RecordOrigin,
    SourceRecordReference,
)


__all__ = [
    "EventCounterName",
    "EventCounterSnapshot",
    "EventCounterValue",
    "TelemetryModelError",
    "TelemetryScalar",
    "TransitionTelemetryField",
    "TransitionTelemetryRecord",
    "TransitionTelemetryValue",
]


type TelemetryScalar = bool | int | Decimal


class TelemetryModelError(ValueError):
    """Raised when telemetry data violates its read-only contract."""


class TransitionTelemetryField(StrEnum):
    """Distinct transition-capacity and deferral telemetry fields."""

    TRANSITION_FRACTION = "transition_fraction"
    REQUEST_LANE_COUNT = "request_lane_count"
    CURRENT_TICK_CHANGES = "current_tick_changes"
    SWITCH_LOAD = "switch_load"
    TRANSITION_CAPACITY = "transition_capacity"
    REMAINING_CAPACITY = "remaining_capacity"
    CAPACITY_EXHAUSTED = "capacity_exhausted"
    SCHEDULER_DEFERRAL = "scheduler_deferral"
    CAPACITY_DEFERRAL = "capacity_deferral"


class EventCounterName(StrEnum):
    """Published processor-event counters kept as separate fields."""

    REQUESTED_DIRECT_EVENTS = "requested_direct_events"
    PREVENTED_DIRECT_EVENTS = "prevented_direct_events"
    NEUTRAL_ROUTED_EVENTS = "neutral_routed_events"
    NEUTRALIZED_CONFLICTS = "neutralized_conflicts"
    ACTUAL_DIRECT_EVENTS = "actual_direct_events"
    RESERVED_STATE_EVENTS = "reserved_state_events"
    QUEUE_OVERFLOW_EVENTS = "queue_overflow_events"


_INTEGER_TELEMETRY_FIELDS = frozenset(
    {
        TransitionTelemetryField.REQUEST_LANE_COUNT,
        TransitionTelemetryField.CURRENT_TICK_CHANGES,
        TransitionTelemetryField.TRANSITION_CAPACITY,
        TransitionTelemetryField.REMAINING_CAPACITY,
    }
)
_BOOLEAN_TELEMETRY_FIELDS = frozenset(
    {
        TransitionTelemetryField.CAPACITY_EXHAUSTED,
        TransitionTelemetryField.SCHEDULER_DEFERRAL,
        TransitionTelemetryField.CAPACITY_DEFERRAL,
    }
)


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TelemetryModelError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise TelemetryModelError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise TelemetryModelError(f"{field_name} must not contain NUL")


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
        raise TelemetryModelError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_nonnegative_integer(
    value: int,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TelemetryModelError(f"{field_name} must be an integer")
    if value < 0:
        raise TelemetryModelError(f"{field_name} must be nonnegative")


def _validate_number(
    value: TelemetryScalar,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise TelemetryModelError(
            f"{field_name} must be an integer or Decimal"
        )
    if isinstance(value, Decimal) and not value.is_finite():
        raise TelemetryModelError(f"{field_name} must be finite")


def _validate_locations(
    value: tuple[SourceLocation, ...],
) -> None:
    if not isinstance(value, tuple):
        raise TelemetryModelError("source_locations must be a tuple")
    if not value:
        raise TelemetryModelError("source_locations must not be empty")
    if any(not isinstance(item, SourceLocation) for item in value):
        raise TelemetryModelError(
            "source_locations must contain SourceLocation values"
        )


def _validate_references(
    value: tuple[SourceRecordReference, ...],
) -> None:
    if not isinstance(value, tuple):
        raise TelemetryModelError("source_references must be a tuple")
    if not value:
        raise TelemetryModelError("source_references must not be empty")
    if any(not isinstance(item, SourceRecordReference) for item in value):
        raise TelemetryModelError(
            "source_references must contain SourceRecordReference values"
        )
    record_ids = tuple(item.normalized_record_id for item in value)
    if len(set(record_ids)) != len(record_ids):
        raise TelemetryModelError(
            "source_references must identify unique normalized records"
        )


def _validate_unique_uuids(
    values: tuple[str, ...],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise TelemetryModelError(f"{field_name} must be a tuple")
    for value in values:
        _validate_uuid(value, field_name)
    if len(set(values)) != len(values):
        raise TelemetryModelError(f"{field_name} must be unique")


def _validate_origin(
    origin: RecordOrigin,
    source_field_name: str | None,
    derivation_record_id: str | None,
    derivation_operation: str | None,
) -> None:
    if not isinstance(origin, RecordOrigin):
        raise TelemetryModelError("origin must be a RecordOrigin")
    _validate_optional_text(source_field_name, "source_field_name")

    if origin is RecordOrigin.OBSERVATORY_DERIVED:
        if source_field_name is not None:
            raise TelemetryModelError(
                "derived telemetry cannot claim an upstream field name"
            )
        if derivation_record_id is None:
            raise TelemetryModelError(
                "derived telemetry requires a derivation record"
            )
        _validate_uuid(
            derivation_record_id,
            "derivation_record_id",
        )
        _validate_text(
            derivation_operation,
            "derivation_operation",
        )
    else:
        if source_field_name is None:
            raise TelemetryModelError(
                "source telemetry requires its exact source field name"
            )
        if (
            derivation_record_id is not None
            or derivation_operation is not None
        ):
            raise TelemetryModelError(
                "source telemetry cannot claim derivation"
            )


def _validate_telemetry_value(
    field: TransitionTelemetryField,
    value: TelemetryScalar,
) -> None:
    if field in _INTEGER_TELEMETRY_FIELDS:
        _validate_nonnegative_integer(value, field.value)
        return
    if field in _BOOLEAN_TELEMETRY_FIELDS:
        if not isinstance(value, bool):
            raise TelemetryModelError(
                f"{field.value} must be a bool"
            )
        return

    _validate_number(value, field.value)
    if value < 0:
        raise TelemetryModelError(
            f"{field.value} must be nonnegative"
        )
    if (
        field is TransitionTelemetryField.TRANSITION_FRACTION
        and value > 1
    ):
        raise TelemetryModelError(
            "transition_fraction must not exceed one"
        )


@dataclass(frozen=True, slots=True)
class TransitionTelemetryValue:
    """One source or derived telemetry field with explicit provenance."""

    telemetry_value_id: str
    field: TransitionTelemetryField
    value: TelemetryScalar
    origin: RecordOrigin
    source_references: tuple[SourceRecordReference, ...]
    source_locations: tuple[SourceLocation, ...]
    source_field_name: str | None = None
    derivation_record_id: str | None = None
    derivation_operation: str | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.telemetry_value_id,
            "telemetry_value_id",
        )
        if not isinstance(self.field, TransitionTelemetryField):
            raise TelemetryModelError(
                "field must be a TransitionTelemetryField"
            )
        _validate_telemetry_value(self.field, self.value)
        _validate_references(self.source_references)
        _validate_locations(self.source_locations)
        _validate_origin(
            self.origin,
            self.source_field_name,
            self.derivation_record_id,
            self.derivation_operation,
        )
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )


@dataclass(frozen=True, slots=True)
class TransitionTelemetryRecord:
    """Transition telemetry for one tick without absent-field defaults."""

    telemetry_record_id: str
    tick_reference: SourceRecordReference
    values: tuple[TransitionTelemetryValue, ...]
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.telemetry_record_id,
            "telemetry_record_id",
        )
        if not isinstance(self.tick_reference, SourceRecordReference):
            raise TelemetryModelError(
                "tick_reference must be a SourceRecordReference"
            )
        if not isinstance(self.values, tuple):
            raise TelemetryModelError("values must be a tuple")
        if not self.values:
            raise TelemetryModelError("values must not be empty")
        if any(
            not isinstance(value, TransitionTelemetryValue)
            for value in self.values
        ):
            raise TelemetryModelError(
                "values must contain TransitionTelemetryValue records"
            )

        fields = tuple(value.field for value in self.values)
        if len(set(fields)) != len(fields):
            raise TelemetryModelError(
                "telemetry fields must be unique within one record"
            )
        for value in self.values:
            if not any(
                reference.source_artifact_id
                == self.tick_reference.source_artifact_id
                for reference in value.source_references
            ):
                raise TelemetryModelError(
                    "each telemetry field must reference the tick artifact"
                )

        self._validate_capacity_relations()
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )

    def value_for(
        self,
        field: TransitionTelemetryField,
    ) -> TransitionTelemetryValue | None:
        """Return one present field without synthesizing a default."""

        if not isinstance(field, TransitionTelemetryField):
            raise TelemetryModelError(
                "field must be a TransitionTelemetryField"
            )
        return next(
            (value for value in self.values if value.field is field),
            None,
        )

    def _validate_capacity_relations(self) -> None:
        changes = self.value_for(
            TransitionTelemetryField.CURRENT_TICK_CHANGES
        )
        capacity = self.value_for(
            TransitionTelemetryField.TRANSITION_CAPACITY
        )
        remaining = self.value_for(
            TransitionTelemetryField.REMAINING_CAPACITY
        )
        exhausted = self.value_for(
            TransitionTelemetryField.CAPACITY_EXHAUSTED
        )

        if changes is not None and capacity is not None:
            if changes.value > capacity.value:
                raise TelemetryModelError(
                    "current_tick_changes must not exceed capacity"
                )
        if remaining is not None and capacity is not None:
            if remaining.value > capacity.value:
                raise TelemetryModelError(
                    "remaining_capacity must not exceed capacity"
                )
        if (
            changes is not None
            and capacity is not None
            and remaining is not None
            and remaining.value != capacity.value - changes.value
        ):
            raise TelemetryModelError(
                "remaining_capacity must equal capacity minus changes"
            )
        if remaining is not None and exhausted is not None:
            if exhausted.value != (remaining.value == 0):
                raise TelemetryModelError(
                    "capacity_exhausted must match remaining capacity"
                )


@dataclass(frozen=True, slots=True)
class EventCounterValue:
    """One published counter; zero remains distinct from absence."""

    counter_value_id: str
    counter: EventCounterName
    value: int
    source_reference: SourceRecordReference
    source_location: SourceLocation
    origin: RecordOrigin
    accumulation_classification: str | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(self.counter_value_id, "counter_value_id")
        if not isinstance(self.counter, EventCounterName):
            raise TelemetryModelError(
                "counter must be an EventCounterName"
            )
        _validate_nonnegative_integer(self.value, "value")
        if not isinstance(self.source_reference, SourceRecordReference):
            raise TelemetryModelError(
                "source_reference must be a SourceRecordReference"
            )
        if not isinstance(self.source_location, SourceLocation):
            raise TelemetryModelError(
                "source_location must be a SourceLocation"
            )
        if not isinstance(self.origin, RecordOrigin):
            raise TelemetryModelError("origin must be a RecordOrigin")
        if self.origin is RecordOrigin.OBSERVATORY_DERIVED:
            raise TelemetryModelError(
                "published counters cannot have derived origin"
            )
        _validate_optional_text(
            self.accumulation_classification,
            "accumulation_classification",
        )
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )


@dataclass(frozen=True, slots=True)
class EventCounterSnapshot:
    """Present event counters for one source record."""

    counter_snapshot_id: str
    source_reference: SourceRecordReference
    counters: tuple[EventCounterValue, ...]
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.counter_snapshot_id,
            "counter_snapshot_id",
        )
        if not isinstance(self.source_reference, SourceRecordReference):
            raise TelemetryModelError(
                "source_reference must be a SourceRecordReference"
            )
        if not isinstance(self.counters, tuple):
            raise TelemetryModelError("counters must be a tuple")
        if not self.counters:
            raise TelemetryModelError("counters must not be empty")
        if any(
            not isinstance(counter, EventCounterValue)
            for counter in self.counters
        ):
            raise TelemetryModelError(
                "counters must contain EventCounterValue records"
            )

        counter_names = tuple(
            counter.counter for counter in self.counters
        )
        if len(set(counter_names)) != len(counter_names):
            raise TelemetryModelError(
                "counter names must be unique within one snapshot"
            )
        if any(
            counter.source_reference.normalized_record_id
            != self.source_reference.normalized_record_id
            for counter in self.counters
        ):
            raise TelemetryModelError(
                "counter values must reference the snapshot source record"
            )

        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )

    def value_for(
        self,
        counter: EventCounterName,
    ) -> EventCounterValue | None:
        """Return one present counter without replacing absence with zero."""

        if not isinstance(counter, EventCounterName):
            raise TelemetryModelError(
                "counter must be an EventCounterName"
            )
        return next(
            (
                value
                for value in self.counters
                if value.counter is counter
            ),
            None,
        )
