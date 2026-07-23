"""Immutable source-linked scheduler records for visualization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from artifact_auditor.audit_report import SourceLocation
from transition_visualizer.transition_model import (
    RecordOrigin,
    SourceRecordReference,
)


__all__ = [
    "SchedulerField",
    "SchedulerFieldValue",
    "SchedulerMode",
    "SchedulerModelError",
    "SchedulerNormalizedValue",
    "SchedulerSnapshot",
    "SchedulerSourceValue",
    "SchedulerState",
]


type SchedulerSourceValue = int | str
type SchedulerNormalizedValue = SchedulerMode | SchedulerState


class SchedulerModelError(ValueError):
    """Raised when scheduler data violates its source contract."""


class SchedulerField(StrEnum):
    """Scheduler fields kept distinct in normalized records."""

    MODE = "scheduler_mode"
    STATE = "scheduler_state"


class SchedulerMode(StrEnum):
    """Registered FRP scheduler-mode names."""

    FREE = "free"
    BALANCE_COMMIT = "7/1"
    EXCITE_NEUTRALIZE = "1/7"


class SchedulerState(StrEnum):
    """Registered FRP scheduler-state names."""

    FREE = "free"
    BALANCE = "balance"
    COMMIT = "commit"
    EXCITE = "excite"
    NEUTRALIZE = "neutralize"


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise SchedulerModelError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise SchedulerModelError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise SchedulerModelError(
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
        raise SchedulerModelError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_source_value(
    value: SchedulerSourceValue,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise SchedulerModelError(
            f"{field_name} must be an integer or string"
        )
    if isinstance(value, str):
        _validate_text(value, field_name)


def _validate_origin(value: RecordOrigin) -> None:
    if not isinstance(value, RecordOrigin):
        raise SchedulerModelError("origin must be a RecordOrigin")
    if value is RecordOrigin.OBSERVATORY_DERIVED:
        raise SchedulerModelError(
            "scheduler source records cannot have derived origin"
        )


def _validate_unique_uuids(
    values: tuple[str, ...],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise SchedulerModelError(f"{field_name} must be a tuple")
    for value in values:
        _validate_uuid(value, field_name)
    if len(set(values)) != len(values):
        raise SchedulerModelError(f"{field_name} must be unique")


def _validate_field_binding(
    field: SchedulerField,
    normalized_value: SchedulerNormalizedValue,
) -> None:
    if field is SchedulerField.MODE:
        if not isinstance(normalized_value, SchedulerMode):
            raise SchedulerModelError(
                "scheduler mode requires a SchedulerMode value"
            )
        return
    if not isinstance(normalized_value, SchedulerState):
        raise SchedulerModelError(
            "scheduler state requires a SchedulerState value"
        )


@dataclass(frozen=True, slots=True)
class SchedulerFieldValue:
    """One scheduler mode or state with its source representation."""

    scheduler_field_value_id: str
    source_reference: SourceRecordReference
    field: SchedulerField
    source_value: SchedulerSourceValue
    normalized_value: SchedulerNormalizedValue
    source_location: SourceLocation
    origin: RecordOrigin
    encoding_map_identifier: str | None = None
    published_name: str | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.scheduler_field_value_id,
            "scheduler_field_value_id",
        )
        if not isinstance(self.source_reference, SourceRecordReference):
            raise SchedulerModelError(
                "source_reference must be a SourceRecordReference"
            )
        if not isinstance(self.field, SchedulerField):
            raise SchedulerModelError(
                "field must be a SchedulerField"
            )
        _validate_source_value(self.source_value, "source_value")
        _validate_field_binding(self.field, self.normalized_value)
        if not isinstance(self.source_location, SourceLocation):
            raise SchedulerModelError(
                "source_location must be a SourceLocation"
            )
        _validate_origin(self.origin)
        _validate_optional_text(
            self.encoding_map_identifier,
            "encoding_map_identifier",
        )
        _validate_optional_text(
            self.published_name,
            "published_name",
        )

        if self.origin is RecordOrigin.OBSERVATORY_NORMALIZED:
            if self.encoding_map_identifier is None:
                raise SchedulerModelError(
                    "normalized scheduler values require an encoding map"
                )
        elif (
            not isinstance(self.source_value, str)
            or self.source_value != self.normalized_value.value
        ):
            raise SchedulerModelError(
                "source-origin scheduler values must use registered names"
            )

        if (
            self.published_name is not None
            and self.field is not SchedulerField.STATE
        ):
            raise SchedulerModelError(
                "published_name is available only for scheduler state"
            )

        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )


@dataclass(frozen=True, slots=True)
class SchedulerSnapshot:
    """Scheduler state for one tick with optional published mode."""

    scheduler_snapshot_id: str
    source_reference: SourceRecordReference
    state: SchedulerFieldValue
    mode: SchedulerFieldValue | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.scheduler_snapshot_id,
            "scheduler_snapshot_id",
        )
        if not isinstance(self.source_reference, SourceRecordReference):
            raise SchedulerModelError(
                "source_reference must be a SourceRecordReference"
            )
        if not isinstance(self.state, SchedulerFieldValue):
            raise SchedulerModelError(
                "state must be a SchedulerFieldValue"
            )
        if self.state.field is not SchedulerField.STATE:
            raise SchedulerModelError(
                "state must contain the scheduler-state field"
            )
        if (
            self.state.source_reference.normalized_record_id
            != self.source_reference.normalized_record_id
        ):
            raise SchedulerModelError(
                "state must reference the snapshot source record"
            )

        if self.mode is not None:
            if not isinstance(self.mode, SchedulerFieldValue):
                raise SchedulerModelError(
                    "mode must be a SchedulerFieldValue or None"
                )
            if self.mode.field is not SchedulerField.MODE:
                raise SchedulerModelError(
                    "mode must contain the scheduler-mode field"
                )
            if (
                self.mode.source_reference.source_artifact_id
                != self.source_reference.source_artifact_id
                or self.mode.source_reference.trace_dataset_id
                != self.source_reference.trace_dataset_id
            ):
                raise SchedulerModelError(
                    "mode must belong to the snapshot trace dataset"
                )

        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )

    @property
    def scheduler_state(self) -> SchedulerState:
        """Return the registered scheduler state."""

        value = self.state.normalized_value
        if not isinstance(value, SchedulerState):
            raise SchedulerModelError(
                "state normalization is not a SchedulerState"
            )
        return value

    @property
    def scheduler_mode(self) -> SchedulerMode | None:
        """Return the registered mode only when it was published."""

        if self.mode is None:
            return None
        value = self.mode.normalized_value
        if not isinstance(value, SchedulerMode):
            raise SchedulerModelError(
                "mode normalization is not a SchedulerMode"
            )
        return value
