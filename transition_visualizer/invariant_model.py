"""Immutable source-linked invariant-vector records for visualization."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from artifact_auditor.audit_report import SourceLocation
from schemas.registry import MeasurementContour
from transition_visualizer.transition_model import (
    RecordOrigin,
    SourceRecordReference,
)


__all__ = [
    "InvariantBitRecord",
    "InvariantBitValue",
    "InvariantModelError",
    "InvariantVectorRecord",
]


type InvariantBitValue = bool | int | str


class InvariantModelError(ValueError):
    """Raised when invariant data violates its read-only contract."""


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise InvariantModelError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise InvariantModelError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise InvariantModelError(
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
        raise InvariantModelError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_nonnegative_integer(
    value: int,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvariantModelError(
            f"{field_name} must be an integer"
        )
    if value < 0:
        raise InvariantModelError(
            f"{field_name} must be nonnegative"
        )


def _validate_positive_integer(
    value: int,
    field_name: str,
) -> None:
    _validate_nonnegative_integer(value, field_name)
    if value == 0:
        raise InvariantModelError(
            f"{field_name} must be positive"
        )


def _validate_source_bit_value(value: InvariantBitValue) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if value not in (0, 1):
            raise InvariantModelError(
                "integer source_bit_value must be 0 or 1"
            )
        return
    if isinstance(value, str):
        if value not in {"0", "1"}:
            raise InvariantModelError(
                "string source_bit_value must be '0' or '1'"
            )
        return
    raise InvariantModelError(
        "source_bit_value must be a bool, integer, or string bit"
    )


def _validate_origin(value: RecordOrigin) -> None:
    if not isinstance(value, RecordOrigin):
        raise InvariantModelError("origin must be a RecordOrigin")
    if value is RecordOrigin.OBSERVATORY_DERIVED:
        raise InvariantModelError(
            "invariant source records cannot have derived origin"
        )


def _validate_unique_uuids(
    values: tuple[str, ...],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise InvariantModelError(f"{field_name} must be a tuple")
    for value in values:
        _validate_uuid(value, field_name)
    if len(set(values)) != len(values):
        raise InvariantModelError(f"{field_name} must be unique")


def _source_bit_text(value: InvariantBitValue) -> str:
    if isinstance(value, str):
        return value
    return "1" if value else "0"


@dataclass(frozen=True, slots=True)
class InvariantBitRecord:
    """One source-ordered invariant bit without invented meaning."""

    invariant_bit_record_id: str
    source_reference: SourceRecordReference
    source_bit_position: int
    source_bit_value: InvariantBitValue
    source_location: SourceLocation
    origin: RecordOrigin
    registered_invariant_name: str | None = None
    published_status: str | None = None
    published_status_location: SourceLocation | None = None
    upstream_rule_reference: str | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.invariant_bit_record_id,
            "invariant_bit_record_id",
        )
        if not isinstance(self.source_reference, SourceRecordReference):
            raise InvariantModelError(
                "source_reference must be a SourceRecordReference"
            )
        _validate_nonnegative_integer(
            self.source_bit_position,
            "source_bit_position",
        )
        _validate_source_bit_value(self.source_bit_value)
        if not isinstance(self.source_location, SourceLocation):
            raise InvariantModelError(
                "source_location must be a SourceLocation"
            )
        _validate_origin(self.origin)

        optional_text = (
            (
                "registered_invariant_name",
                self.registered_invariant_name,
            ),
            ("published_status", self.published_status),
            (
                "upstream_rule_reference",
                self.upstream_rule_reference,
            ),
        )
        for field_name, value in optional_text:
            _validate_optional_text(value, field_name)

        if self.published_status is None:
            if self.published_status_location is not None:
                raise InvariantModelError(
                    "status location requires a published status"
                )
        elif not isinstance(
            self.published_status_location,
            SourceLocation,
        ):
            raise InvariantModelError(
                "published status requires a source location"
            )

        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )

    @property
    def display_value(self) -> str:
        """Return the source bit in canonical unsigned display form."""

        return _source_bit_text(self.source_bit_value)


@dataclass(frozen=True, slots=True)
class InvariantVectorRecord:
    """One invariant vector preserving source order and availability."""

    invariant_vector_record_id: str
    source_reference: SourceRecordReference
    original_vector_representation: str
    bit_count: int
    source_location: SourceLocation
    bits: tuple[InvariantBitRecord, ...]
    qualification_contour: MeasurementContour
    origin: RecordOrigin
    bit_order_contract_identifier: str | None = None
    published_aggregate_status: str | None = None
    aggregate_status_location: SourceLocation | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.invariant_vector_record_id,
            "invariant_vector_record_id",
        )
        if not isinstance(self.source_reference, SourceRecordReference):
            raise InvariantModelError(
                "source_reference must be a SourceRecordReference"
            )
        _validate_text(
            self.original_vector_representation,
            "original_vector_representation",
        )
        _validate_positive_integer(self.bit_count, "bit_count")
        if not isinstance(self.source_location, SourceLocation):
            raise InvariantModelError(
                "source_location must be a SourceLocation"
            )
        if not isinstance(self.bits, tuple):
            raise InvariantModelError("bits must be a tuple")
        if not self.bits:
            raise InvariantModelError("bits must not be empty")
        if any(
            not isinstance(bit, InvariantBitRecord)
            for bit in self.bits
        ):
            raise InvariantModelError(
                "bits must contain InvariantBitRecord values"
            )
        if len(self.bits) != self.bit_count:
            raise InvariantModelError(
                "bit_count must equal the number of bit records"
            )

        positions = tuple(
            bit.source_bit_position for bit in self.bits
        )
        if len(set(positions)) != len(positions):
            raise InvariantModelError(
                "source bit positions must be unique"
            )
        if any(
            bit.source_reference.normalized_record_id
            != self.source_reference.normalized_record_id
            for bit in self.bits
        ):
            raise InvariantModelError(
                "bits must reference the vector source record"
            )

        if not isinstance(
            self.qualification_contour,
            MeasurementContour,
        ):
            raise InvariantModelError(
                "qualification_contour must be a MeasurementContour"
            )
        _validate_origin(self.origin)
        _validate_optional_text(
            self.bit_order_contract_identifier,
            "bit_order_contract_identifier",
        )

        registered_names = tuple(
            bit.registered_invariant_name
            for bit in self.bits
            if bit.registered_invariant_name is not None
        )
        if (
            registered_names
            and self.bit_order_contract_identifier is None
        ):
            raise InvariantModelError(
                "registered bit names require a bit-order contract"
            )
        if len(set(registered_names)) != len(registered_names):
            raise InvariantModelError(
                "registered invariant names must be unique"
            )

        _validate_optional_text(
            self.published_aggregate_status,
            "published_aggregate_status",
        )
        if self.published_aggregate_status is None:
            if self.aggregate_status_location is not None:
                raise InvariantModelError(
                    "aggregate location requires a published status"
                )
        elif not isinstance(
            self.aggregate_status_location,
            SourceLocation,
        ):
            raise InvariantModelError(
                "published aggregate status requires a source location"
            )

        self._validate_simple_binary_representation()
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )

    def _validate_simple_binary_representation(self) -> None:
        representation = self.original_vector_representation
        if any(character not in {"0", "1"} for character in representation):
            return
        source_sequence = "".join(
            bit.display_value for bit in self.bits
        )
        if source_sequence != representation:
            raise InvariantModelError(
                "bit records must preserve simple binary source order"
            )

    def bit_for_position(
        self,
        source_bit_position: int,
    ) -> InvariantBitRecord | None:
        """Return one recorded source bit without changing vector order."""

        _validate_nonnegative_integer(
            source_bit_position,
            "source_bit_position",
        )
        return next(
            (
                bit
                for bit in self.bits
                if bit.source_bit_position == source_bit_position
            ),
            None,
        )

    def bit_for_name(
        self,
        registered_invariant_name: str,
    ) -> InvariantBitRecord | None:
        """Return one registered bit without assigning unknown meanings."""

        _validate_text(
            registered_invariant_name,
            "registered_invariant_name",
        )
        return next(
            (
                bit
                for bit in self.bits
                if bit.registered_invariant_name
                == registered_invariant_name
            ),
            None,
        )
