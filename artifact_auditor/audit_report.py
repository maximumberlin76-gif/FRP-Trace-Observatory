"""Immutable validation results for Artifact Auditor reports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID

from parsers.artifact_dispatch import ArtifactClassification
from schemas.registry import MeasurementContour


__all__ = [
    "AuditReport",
    "AuditReportError",
    "AuditScalar",
    "AuditValue",
    "AuditValueSnapshot",
    "CheckOutcome",
    "MessageSeverity",
    "SourceLocation",
    "ValidationCategory",
    "ValidationCheck",
    "ValidationStatus",
]


type AuditScalar = None | bool | int | Decimal | str
type AuditValue = (
    AuditScalar
    | tuple[AuditValue, ...]
    | Mapping[str, AuditValue]
)


_SHA256_HEX_LENGTH: Final = 64
_LOWERCASE_HEX: Final = frozenset("0123456789abcdef")


class ValidationStatus(StrEnum):
    """Aggregate outcomes defined by the normalized data model."""

    RECOGNIZED_VALID = "recognized_valid"
    RECOGNIZED_VALID_WITH_WARNINGS = "recognized_valid_with_warnings"
    RECOGNIZED_INVALID = "recognized_invalid"
    KNOWN_UNSUPPORTED = "known_unsupported"
    UNRECOGNIZED = "unrecognized"
    INCOMPLETE_PACKAGE = "incomplete_package"


class ValidationCategory(StrEnum):
    """Non-interchangeable validation categories."""

    CONTAINER = "container"
    IDENTITY = "identity"
    STRUCTURE = "structure"
    TYPE = "type"
    ALLOWED_VALUE = "allowed_value"
    TERNARY_DOMAIN = "ternary_domain"
    ORDERING = "ordering"
    SCHEDULER_RELATION = "scheduler_relation"
    TRANSITION_CAPACITY = "transition_capacity"
    PENDING_ROUTE = "pending_route"
    INVARIANT_VECTOR = "invariant_vector"
    DIGEST = "digest"
    DETERMINISTIC_PACKAGE = "deterministic_package"
    QUALIFICATION_EVIDENCE = "qualification_evidence"


class CheckOutcome(StrEnum):
    """Outcome of one validation operation."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"
    NOT_EVALUATED = "not_evaluated"


class MessageSeverity(StrEnum):
    """Severity assigned to a validation message when applicable."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AuditReportError(ValueError):
    """Raised when an audit-report record violates its invariants."""


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise AuditReportError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise AuditReportError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise AuditReportError(f"{field_name} must not contain NUL")


def _validate_optional_text(
    value: str | None,
    field_name: str,
) -> None:
    if value is not None:
        _validate_text(value, field_name)


def _validate_optional_source_string(
    value: str | None,
    field_name: str,
) -> None:
    if value is not None and not isinstance(value, str):
        raise AuditReportError(
            f"{field_name} must be a string or None"
        )


def _validate_source_filename(value: str) -> None:
    if not isinstance(value, str):
        raise AuditReportError("source_filename must be a string")
    if not value.strip():
        raise AuditReportError("source_filename must not be empty")
    if value in {".", ".."}:
        raise AuditReportError("source_filename must name a file")
    if "\x00" in value:
        raise AuditReportError("source_filename must not contain NUL")
    if "/" in value or "\\" in value:
        raise AuditReportError(
            "source_filename must not contain path separators"
        )


def _validate_optional_source_path(value: str | None) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise AuditReportError("source_path must be a string or None")
    if not value:
        raise AuditReportError("source_path must not be empty")
    if "\x00" in value:
        raise AuditReportError("source_path must not contain NUL")


def _validate_token(value: str, field_name: str) -> None:
    _validate_text(value, field_name)
    if any(character.isspace() for character in value):
        raise AuditReportError(f"{field_name} must not contain whitespace")


def _validate_uuid(value: str, field_name: str) -> None:
    _validate_token(value, field_name)
    try:
        UUID(value)
    except (ValueError, AttributeError) as exc:
        raise AuditReportError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_positive_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuditReportError(f"{field_name} must be an integer")
    if value <= 0:
        raise AuditReportError(f"{field_name} must be positive")


def _validate_nonnegative_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuditReportError(f"{field_name} must be an integer")
    if value < 0:
        raise AuditReportError(f"{field_name} must be nonnegative")


def _validate_utc_timestamp(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise AuditReportError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise AuditReportError(f"{field_name} must include a timezone")
    if value.utcoffset() != timedelta(0):
        raise AuditReportError(f"{field_name} must be normalized to UTC")


def _validate_sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise AuditReportError(f"{field_name} must be a string")
    if (
        len(value) != _SHA256_HEX_LENGTH
        or any(character not in _LOWERCASE_HEX for character in value)
    ):
        raise AuditReportError(
            f"{field_name} must be 64 lowercase hexadecimal characters"
        )


def _freeze_audit_value(value: object) -> AuditValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise AuditReportError(
                "audit values must not contain non-finite decimals"
            )
        return value
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_audit_value(item) for item in value)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise AuditReportError(
                "audit-value mapping keys must be strings"
            )
        return MappingProxyType(
            {
                key: _freeze_audit_value(item)
                for key, item in value.items()
            }
        )
     raise AuditReportError(
        f"unsupported audit value type: {type(value).__name__}"
    )


@dataclass(frozen=True, slots=True)
class AuditValueSnapshot:
    """One immutable expected or observed validation value."""   


    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _freeze_audit_value(self.value),
        )


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Known source coordinates without invented location data."""

    line_number: int | None = None
    column_number: int | None = None
    json_path: str | None = None
    array_index: int | None = None
    vector_column: str | None = None
    package_member: str | None = None
    markdown_heading: str | None = None
    markdown_table_row: int | None = None
    source_record_ordinal: int | None = None

    def __post_init__(self) -> None:
        positive_integers = (
            ("line_number", self.line_number),
            ("column_number", self.column_number),
            ("markdown_table_row", self.markdown_table_row),
            ("source_record_ordinal", self.source_record_ordinal),
        )
        for field_name, value in positive_integers:
            if value is not None:
                _validate_positive_integer(value, field_name)

        if self.array_index is not None:
            _validate_nonnegative_integer(
                self.array_index,
                "array_index",
            )

        optional_text = (
            ("json_path", self.json_path),
            ("vector_column", self.vector_column),
            ("package_member", self.package_member),
            ("markdown_heading", self.markdown_heading),
        )
        for field_name, value in optional_text:
            _validate_optional_text(value, field_name)

        if self.column_number is not None and self.line_number is None:
            raise AuditReportError(
                "column_number requires line_number"
            )

        if all(
            value is None
            for value in (
                self.line_number,
                self.column_number,
                self.json_path,
                self.array_index,
                self.vector_column,
                self.package_member,
                self.markdown_heading,
                self.markdown_table_row,
                self.source_record_ordinal,
            )
        ):
            raise AuditReportError(
                "source location must contain at least one known coordinate"
            )


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    """One immutable validation operation and its result."""

    check_id: str
    check_code: str
    category: ValidationCategory
    outcome: CheckOutcome
    severity: MessageSeverity | None
    source_locations: tuple[SourceLocation, ...]
    expected: AuditValueSnapshot | None
    observed: AuditValueSnapshot | None
    message: str
    upstream_rule_reference: str | None
    mandatory: bool = True

    def __post_init__(self) -> None:
        _validate_uuid(self.check_id, "check_id")
        _validate_token(self.check_code, "check_code")
        if not isinstance(self.category, ValidationCategory):
            raise AuditReportError(
                "category must be a ValidationCategory"
            )
        if not isinstance(self.outcome, CheckOutcome):
            raise AuditReportError("outcome must be a CheckOutcome")
        if self.severity is not None and not isinstance(
            self.severity,
            MessageSeverity,
        ):
            raise AuditReportError(
                "severity must be a MessageSeverity or None"
            )
        if not isinstance(self.source_locations, tuple):
            raise AuditReportError("source_locations must be a tuple")
        if any(
            not isinstance(location, SourceLocation)
            for location in self.source_locations
        ):
            raise AuditReportError(
                "source_locations must contain SourceLocation values"
            )
        if len(set(self.source_locations)) != len(self.source_locations):
            raise AuditReportError("source_locations must be unique")
        if self.expected is not None and not isinstance(
            self.expected,
            AuditValueSnapshot,
        ):
            raise AuditReportError(
                "expected must be an AuditValueSnapshot or None"
            )
        if self.observed is not None and not isinstance(
            self.observed,
            AuditValueSnapshot,
        ):
            raise AuditReportError(
                "observed must be an AuditValueSnapshot or None"
            )
        _validate_text(self.message, "message")
        _validate_optional_text(
            self.upstream_rule_reference,
            "upstream_rule_reference",
        )
        if not isinstance(self.mandatory, bool):
            raise AuditReportError("mandatory must be a boolean")

        if self.outcome in {
            CheckOutcome.PASS,
            CheckOutcome.NOT_APPLICABLE,
        }:
            if self.severity is not None:
                raise AuditReportError(
                    "pass and not-applicable checks must not have severity"
                )
        elif self.outcome is CheckOutcome.FAIL:
            if self.severity is not MessageSeverity.ERROR:
                raise AuditReportError(
                    "failed checks must have error severity"
                )
        elif self.outcome is CheckOutcome.WARNING:
            if self.severity is not MessageSeverity.WARNING:
                raise AuditReportError(
                    "warning checks must have warning severity"
                )
        elif (
            self.outcome is CheckOutcome.NOT_EVALUATED
            and self.severity is MessageSeverity.ERROR
        ):
                        raise AuditReportError(
                "not-evaluated checks must not have error severity"
            )


@dataclass(frozen=True, slots=True)
class AuditReport:
    """One Observatory-derived report backed by immutable checks."""

    audit_report_id: str
    source_artifact_id: str
    source_filename: str
    source_path: str | None
    source_sha256: str
    source_byte_length: int
    loaded_at: datetime
    detected_format: ArtifactClassification
    declared_schema_identifier: str | None
    declared_kind: str | None
    registry_binding_id: str | None
    matched_registry_identifier: str | None
    matched_registry_kind: str | None
    producer_path: str | None
    producer_version: str | None
    measurement_contour: MeasurementContour | None
    started_at: datetime
    completed_at: datetime
    observatory_version: str | None
    registry_revision: str
    checks: tuple[ValidationCheck, ...]
    missing_package_members: tuple[str, ...]
    overall_status: ValidationStatus

    def __post_init__(self) -> None:
        _validate_uuid(self.audit_report_id, "audit_report_id")
        _validate_uuid(self.source_artifact_id, "source_artifact_id")
        _validate_source_filename(self.source_filename)
        _validate_optional_source_path(self.source_path)
        _validate_sha256(self.source_sha256, "source_sha256")
        _validate_nonnegative_integer(
            self.source_byte_length,
            "source_byte_length",
        )
        _validate_utc_timestamp(self.loaded_at, "loaded_at")
        if not isinstance(self.detected_format, ArtifactClassification):
            raise AuditReportError(
                "detected_format must be an ArtifactClassification"
            )

        optional_source_strings = (
            (
                "declared_schema_identifier",
                self.declared_schema_identifier,
            ),
            ("declared_kind", self.declared_kind),
        )
        for field_name, value in optional_source_strings:
            _validate_optional_source_string(value, field_name)

        optional_text = (
            ("registry_binding_id", self.registry_binding_id),
            (
                "matched_registry_identifier",
                self.matched_registry_identifier,
            ),
            ("matched_registry_kind", self.matched_registry_kind),
            ("producer_path", self.producer_path),
            ("producer_version", self.producer_version),
            ("observatory_version", self.observatory_version),
        )
        for field_name, value in optional_text:
            _validate_optional_text(value, field_name)
        if self.registry_binding_id is not None:
            _validate_token(
                self.registry_binding_id,
                "registry_binding_id",
            )

        if (
            self.measurement_contour is not None
            and not isinstance(
                self.measurement_contour,
                MeasurementContour,
            )
        ):
            raise AuditReportError(
                "measurement_contour must be a MeasurementContour or None"
            )

        _validate_utc_timestamp(self.started_at, "started_at")
        _validate_utc_timestamp(self.completed_at, "completed_at")
        if self.started_at < self.loaded_at:
            raise AuditReportError(
                "started_at must not precede loaded_at"
            )
        if self.completed_at < self.started_at:
            raise AuditReportError(
                "completed_at must not precede started_at"
            )

        _validate_token(self.registry_revision, "registry_revision")
        if not isinstance(self.checks, tuple) or not self.checks:
            raise AuditReportError("checks must be a nonempty tuple")
        if any(
            not isinstance(check, ValidationCheck)
            for check in self.checks
        ):
            raise AuditReportError(
                "checks must contain ValidationCheck values"
            )
        check_ids = tuple(check.check_id for check in self.checks)
        if len(set(check_ids)) != len(check_ids):
            raise AuditReportError("check identifiers must be unique")

        if not isinstance(self.missing_package_members, tuple):
            raise AuditReportError(
                "missing_package_members must be a tuple"
            )
        for member in self.missing_package_members:
            _validate_text(member, "missing package member")
        if len(set(self.missing_package_members)) != len(
            self.missing_package_members
        ):
            raise AuditReportError(
                "missing_package_members must be unique"
            )

        if not isinstance(self.overall_status, ValidationStatus):
            raise AuditReportError(
                "overall_status must be a ValidationStatus"
            )

        self._validate_registry_association()
        self._validate_aggregate_status()

    def _validate_registry_association(self) -> None:
        registered_statuses = {
            ValidationStatus.RECOGNIZED_VALID,
            ValidationStatus.RECOGNIZED_VALID_WITH_WARNINGS,
            ValidationStatus.RECOGNIZED_INVALID,
            ValidationStatus.INCOMPLETE_PACKAGE,
        }
        if (
            self.overall_status in registered_statuses
            and self.registry_binding_id is None
        ):
            raise AuditReportError(
                "recognized reports require registry_binding_id"
            )
        if (
            self.overall_status is ValidationStatus.UNRECOGNIZED
            and self.registry_binding_id is not None
        ):
            raise AuditReportError(
                "unrecognized reports must not have registry_binding_id"
            )
        if self.registry_binding_id is None and any(
            value is not None
            for value in (
                self.matched_registry_identifier,
                self.matched_registry_kind,
                self.producer_path,
                self.producer_version,
                self.measurement_contour,
            )
        ):
            raise AuditReportError(
                "registry-derived fields require registry_binding_id"
            )

    def _validate_aggregate_status(self) -> None:
        outcomes = tuple(check.outcome for check in self.checks)
        has_failure = CheckOutcome.FAIL in outcomes
        has_warning = CheckOutcome.WARNING in outcomes
        has_not_evaluated = CheckOutcome.NOT_EVALUATED in outcomes

        if self.overall_status is ValidationStatus.RECOGNIZED_VALID:
            if has_failure or has_warning or has_not_evaluated:
                raise AuditReportError(
                    "recognized-valid reports require fully evaluated "
                    "checks without failures or warnings"
                )
        elif (
            self.overall_status
            is ValidationStatus.RECOGNIZED_VALID_WITH_WARNINGS
        ):
            if has_failure or not has_warning:
                raise AuditReportError(
                    "warning reports require warnings and no failures"
                )
        elif self.overall_status is ValidationStatus.RECOGNIZED_INVALID:
            if not has_failure:
                raise AuditReportError(
                    "recognized-invalid reports require a failed check"
                )
        elif self.overall_status is ValidationStatus.INCOMPLETE_PACKAGE:
            if not self.missing_package_members:
                raise AuditReportError(
                    "incomplete-package reports require missing members"
                )

        if (
            self.overall_status is not ValidationStatus.INCOMPLETE_PACKAGE
            and self.missing_package_members
        ):
            raise AuditReportError(
                "missing package members require incomplete-package status"
            )

    @property
    def check_ids(self) -> tuple[str, ...]:
        """Return validation-check identities in execution order."""

        return tuple(check.check_id for check in self.checks)

    @property
    def passed_checks(self) -> tuple[ValidationCheck, ...]:
        """Return checks with a pass outcome."""

        return tuple(
            check
            for check in self.checks
            if check.outcome is CheckOutcome.PASS
        )

    @property
    def failed_checks(self) -> tuple[ValidationCheck, ...]:
        """Return checks with a fail outcome."""

        return tuple(
            check
            for check in self.checks
            if check.outcome is CheckOutcome.FAIL
        )

    @property
    def warning_checks(self) -> tuple[ValidationCheck, ...]:
        """Return checks with a warning outcome."""

        return tuple(
            check
            for check in self.checks
            if check.outcome is CheckOutcome.WARNING
        )

    @property
    def not_evaluated_checks(self) -> tuple[ValidationCheck, ...]:
        """Return checks that were not evaluated."""

        return tuple(
            check
            for check in self.checks
            if check.outcome is CheckOutcome.NOT_EVALUATED
        )

    @property
    def digest_checks(self) -> tuple[ValidationCheck, ...]:
        """Return checks that compare or record digest evidence."""

        return tuple(
            check
            for check in self.checks
            if check.category is ValidationCategory.DIGEST
        )

    @property
    def report_origin(self) -> str:
        """Identify the report as an Observatory-derived artifact."""

        return "observatory_derived" 
