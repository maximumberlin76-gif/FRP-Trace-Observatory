"""Immutable source-linked records for ternary transition visualization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Final
from uuid import UUID

from artifact_auditor.audit_report import (
    SourceLocation,
    ValidationStatus,
)


__all__ = [
    "CANONICAL_TERNARY_DOMAIN",
    "CanonicalTernaryState",
    "RecordOrigin",
    "RouteLegClassification",
    "SourceRecordReference",
    "SourceStateValue",
    "TernaryStateValue",
    "TransitionClassification",
    "TransitionModelError",
    "TransitionRecord",
    "classify_transition",
]


type SourceStateValue = int | str


CANONICAL_TERNARY_DOMAIN: Final = (-1, 0, 1)
_SHA256_HEX_LENGTH: Final = 64
_LOWERCASE_HEX: Final = frozenset("0123456789abcdef")
_VISUALIZER_VALID_STATUSES: Final = frozenset(
    {
        ValidationStatus.RECOGNIZED_VALID,
        ValidationStatus.RECOGNIZED_VALID_WITH_WARNINGS,
    }
)


class TransitionModelError(ValueError):
    """Raised when a transition-view record violates its contract."""


class CanonicalTernaryState(IntEnum):
    """Canonical FRP processor states."""

    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1

    @property
    def display_value(self) -> str:
        """Return the canonical display form without a positive sign."""

        return str(int(self))


class RecordOrigin(StrEnum):
    """Origin labels defined by the normalized read-only data model."""

    UPSTREAM_SOURCE = "upstream_source"
    OBSERVATORY_NORMALIZED = "observatory_normalized"
    OBSERVATORY_DERIVED = "observatory_derived"


class TransitionClassification(StrEnum):
    """State-pair classifications without direct-event attribution."""

    SAME_STATE_RETENTION = "same_state_retention"
    POLARITY_TO_NEUTRAL = "polarity_to_neutral_transition"
    NEUTRAL_TO_POLARITY = "neutral_to_polarity_transition"
    OBSERVED_OPPOSITE_POLARITY = "observed_opposite_polarity_transition"
    UNKNOWN = "unknown_transition"


class RouteLegClassification(StrEnum):
    """Route-leg labels that require validated route relations."""

    FIRST_LEG_NEUTRALIZATION = "first_leg_neutralization"
    PENDING_ROUTE_COMPLETION = "pending_route_completion"
    NON_ROUTE = "non_route_transition"
    NOT_DETERMINED = "not_determined"


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TransitionModelError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise TransitionModelError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise TransitionModelError(f"{field_name} must not contain NUL")


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
        raise TransitionModelError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TransitionModelError(f"{field_name} must be a string")
    if (
        len(value) != _SHA256_HEX_LENGTH
        or any(character not in _LOWERCASE_HEX for character in value)
    ):
        raise TransitionModelError(
            f"{field_name} must be 64 lowercase hexadecimal characters"
        )


def _validate_nonnegative_integer(
    value: int,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TransitionModelError(f"{field_name} must be an integer")
    if value < 0:
        raise TransitionModelError(f"{field_name} must be nonnegative")


def _validate_source_state(
    value: SourceStateValue,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TransitionModelError(
            f"{field_name} must be an integer or string"
        )
    if isinstance(value, str):
        _validate_text(value, field_name)


def _validate_locations(
    value: tuple[SourceLocation, ...],
    field_name: str,
) -> None:
    if not isinstance(value, tuple):
        raise TransitionModelError(f"{field_name} must be a tuple")
    if not value:
        raise TransitionModelError(f"{field_name} must not be empty")
    if any(not isinstance(item, SourceLocation) for item in value):
        raise TransitionModelError(
            f"{field_name} must contain SourceLocation values"
        )


def _validate_unique_uuids(
    values: tuple[str, ...],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise TransitionModelError(f"{field_name} must be a tuple")
    for value in values:
        _validate_uuid(value, field_name)
    if len(set(values)) != len(values):
        raise TransitionModelError(f"{field_name} must be unique")


def _validate_reference_tuple(
    value: tuple[SourceRecordReference, ...],
) -> None:
    if not isinstance(value, tuple):
        raise TransitionModelError("source_references must be a tuple")
    if not value:
        raise TransitionModelError("source_references must not be empty")
    if any(not isinstance(item, SourceRecordReference) for item in value):
        raise TransitionModelError(
            "source_references must contain SourceRecordReference values"
        )
    record_ids = tuple(item.normalized_record_id for item in value)
    if len(set(record_ids)) != len(record_ids):
        raise TransitionModelError(
            "source_references must identify unique normalized records"
        )


def classify_transition(
    source_state: CanonicalTernaryState,
    target_state: CanonicalTernaryState,
) -> TransitionClassification:
    """Classify a canonical state pair without asserting a direct event."""

    if not isinstance(source_state, CanonicalTernaryState):
        raise TransitionModelError(
            "source_state must be a CanonicalTernaryState"
        )
    if not isinstance(target_state, CanonicalTernaryState):
        raise TransitionModelError(
            "target_state must be a CanonicalTernaryState"
        )
    if source_state is target_state:
        return TransitionClassification.SAME_STATE_RETENTION
    if target_state is CanonicalTernaryState.NEUTRAL:
        return TransitionClassification.POLARITY_TO_NEUTRAL
    if source_state is CanonicalTernaryState.NEUTRAL:
        return TransitionClassification.NEUTRAL_TO_POLARITY
    return TransitionClassification.OBSERVED_OPPOSITE_POLARITY


@dataclass(frozen=True, slots=True)
class SourceRecordReference:
    """Validated provenance for one normalized source record."""

    normalized_record_id: str
    source_artifact_id: str
    trace_dataset_id: str
    registry_binding_id: str
    validation_report_id: str
    source_sha256: str
    source_ordinal: int
    tick: int
    validation_status: ValidationStatus
    source_locations: tuple[SourceLocation, ...]
    schema_identifier: str | None = None
    format_identifier: str | None = None

    def __post_init__(self) -> None:
        identifiers = (
            ("normalized_record_id", self.normalized_record_id),
            ("source_artifact_id", self.source_artifact_id),
            ("trace_dataset_id", self.trace_dataset_id),
            ("registry_binding_id", self.registry_binding_id),
            ("validation_report_id", self.validation_report_id),
        )
        for field_name, value in identifiers:
            _validate_uuid(value, field_name)

        _validate_sha256(self.source_sha256, "source_sha256")
        _validate_nonnegative_integer(
            self.source_ordinal,
            "source_ordinal",
        )
        _validate_nonnegative_integer(self.tick, "tick")

        if not isinstance(self.validation_status, ValidationStatus):
            raise TransitionModelError(
                "validation_status must be a ValidationStatus"
            )
        if self.validation_status not in _VISUALIZER_VALID_STATUSES:
            raise TransitionModelError(
                "source records must be valid before visualization"
            )

        _validate_locations(self.source_locations, "source_locations")
        _validate_optional_text(
            self.schema_identifier,
            "schema_identifier",
        )
        _validate_optional_text(
            self.format_identifier,
            "format_identifier",
        )
        if (self.schema_identifier is None) == (
            self.format_identifier is None
        ):
            raise TransitionModelError(
                "exactly one source contract identifier is required"
            )


@dataclass(frozen=True, slots=True)
class TernaryStateValue:
    """One canonical state linked to its unchanged source representation."""

    state_value_id: str
    source_reference: SourceRecordReference
    cell_id: int
    source_value: SourceStateValue
    source_encoding: str
    canonical_state: CanonicalTernaryState
    origin: RecordOrigin
    encoding_map_identifier: str | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(self.state_value_id, "state_value_id")
        if not isinstance(self.source_reference, SourceRecordReference):
            raise TransitionModelError(
                "source_reference must be a SourceRecordReference"
            )
        _validate_nonnegative_integer(self.cell_id, "cell_id")
        _validate_source_state(self.source_value, "source_value")
        _validate_text(self.source_encoding, "source_encoding")

        if not isinstance(self.canonical_state, CanonicalTernaryState):
            raise TransitionModelError(
                "canonical_state must be a CanonicalTernaryState"
            )
        if not isinstance(self.origin, RecordOrigin):
            raise TransitionModelError("origin must be a RecordOrigin")
        if self.origin is RecordOrigin.OBSERVATORY_DERIVED:
            raise TransitionModelError(
                "canonical state decoding is normalization, not derivation"
            )

        _validate_optional_text(
            self.encoding_map_identifier,
            "encoding_map_identifier",
        )
        if self.origin is RecordOrigin.OBSERVATORY_NORMALIZED:
            if self.encoding_map_identifier is None:
                raise TransitionModelError(
                    "normalized states require an encoding-map identifier"
                )
        elif (
            not isinstance(self.source_value, int)
            or self.source_value != int(self.canonical_state)
        ):
            raise TransitionModelError(
                "source-origin states must already use canonical values"
            )

        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    """One source-backed or explicitly derived canonical transition."""

    transition_record_id: str
    source_references: tuple[SourceRecordReference, ...]
    cell_id: int
    source_tick: int
    target_tick: int
    source_state: CanonicalTernaryState
    target_state: CanonicalTernaryState
    classification: TransitionClassification
    route_leg: RouteLegClassification
    origin: RecordOrigin
    related_request_lane_ids: tuple[str, ...] = ()
    related_route_event_ids: tuple[str, ...] = ()
    scheduler_decision: str | None = None
    capacity_decision: str | None = None
    derivation_record_id: str | None = None
    derivation_operation: str | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.transition_record_id,
            "transition_record_id",
        )
        _validate_reference_tuple(self.source_references)
        _validate_nonnegative_integer(self.cell_id, "cell_id")
        _validate_nonnegative_integer(self.source_tick, "source_tick")
        _validate_nonnegative_integer(self.target_tick, "target_tick")
        if self.target_tick < self.source_tick:
            raise TransitionModelError(
                "target_tick must not precede source_tick"
            )

        if not isinstance(self.source_state, CanonicalTernaryState):
            raise TransitionModelError(
                "source_state must be a CanonicalTernaryState"
            )
        if not isinstance(self.target_state, CanonicalTernaryState):
            raise TransitionModelError(
                "target_state must be a CanonicalTernaryState"
            )
        if not isinstance(
            self.classification,
            TransitionClassification,
        ):
            raise TransitionModelError(
                "classification must be a TransitionClassification"
            )
        if not isinstance(self.route_leg, RouteLegClassification):
            raise TransitionModelError(
                "route_leg must be a RouteLegClassification"
            )
        if not isinstance(self.origin, RecordOrigin):
            raise TransitionModelError("origin must be a RecordOrigin")

        expected = classify_transition(
            self.source_state,
            self.target_state,
        )
        if (
            self.classification is not TransitionClassification.UNKNOWN
            and self.classification is not expected
        ):
            raise TransitionModelError(
                "classification does not match the canonical state pair"
            )
        if (
            self.classification is TransitionClassification.UNKNOWN
            and self.route_leg is not RouteLegClassification.NOT_DETERMINED
        ):
            raise TransitionModelError(
                "unknown transitions require an undetermined route leg"
            )

        _validate_unique_uuids(
            self.related_request_lane_ids,
            "related_request_lane_ids",
        )
        _validate_unique_uuids(
            self.related_route_event_ids,
            "related_route_event_ids",
        )

        route_legs = {
            RouteLegClassification.FIRST_LEG_NEUTRALIZATION,
            RouteLegClassification.PENDING_ROUTE_COMPLETION,
        }
        if (
            self.route_leg in route_legs
            and not self.related_route_event_ids
        ):
            raise TransitionModelError(
                "route-leg classifications require route-event evidence"
            )
        if (
            self.route_leg is RouteLegClassification.NON_ROUTE
            and self.related_route_event_ids
        ):
            raise TransitionModelError(
                "non-route transitions cannot reference route events"
            )

        _validate_optional_text(
            self.scheduler_decision,
            "scheduler_decision",
        )
        _validate_optional_text(
            self.capacity_decision,
            "capacity_decision",
        )

        if self.origin is RecordOrigin.OBSERVATORY_DERIVED:
            if self.derivation_record_id is None:
                raise TransitionModelError(
                    "derived transitions require a derivation record"
                )
            _validate_uuid(
                self.derivation_record_id,
                "derivation_record_id",
            )
            _validate_text(
                self.derivation_operation,
                "derivation_operation",
            )
        elif (
            self.derivation_record_id is not None
            or self.derivation_operation is not None
        ):
            raise TransitionModelError(
                "source and normalized transitions cannot claim derivation"
            )

        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )
