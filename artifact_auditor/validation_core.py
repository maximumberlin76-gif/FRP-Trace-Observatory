"""Shared read-only execution core for Artifact Auditor validation.

This module turns immutable validation specifications into ordered checks and
an Observatory-derived audit report. It does not implement FRP field rules,
execute artifact content, modify source bytes, or infer missing provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4, uuid5

from parsers.artifact_dispatch import (
    DispatchedArtifact,
    RegistrationStatus,
)
from schemas.registry import CompatibilityRecord, IdentifierField

from .audit_report import (
    AuditReport,
    AuditReportError,
    AuditValueSnapshot,
    CheckOutcome,
    MessageSeverity,
    SourceLocation,
    ValidationCategory,
    ValidationCheck,
    ValidationStatus,
)


__all__ = [
    "ValidationCheckSpec",
    "ValidationCoreError",
    "base_check_specs",
    "build_audit_report",
    "derive_validation_status",
    "materialize_validation_checks",
]


_SPEC_VALIDATION_ID = "00000000-0000-4000-8000-000000000000"


class ValidationCoreError(ValueError):
    """Raised when a validation run violates core invariants."""


def _severity_for_outcome(
    outcome: CheckOutcome,
) -> MessageSeverity | None:
    if not isinstance(outcome, CheckOutcome):
        raise ValidationCoreError("outcome must be a CheckOutcome")
    if outcome is CheckOutcome.FAIL:
        return MessageSeverity.ERROR
    if outcome is CheckOutcome.WARNING:
        return MessageSeverity.WARNING
    return None


@dataclass(frozen=True, slots=True)
class ValidationCheckSpec:
    """One ordered validation result before report-local ID assignment."""

    check_code: str
    category: ValidationCategory
    outcome: CheckOutcome
    message: str
    source_locations: tuple[SourceLocation, ...] = ()
    expected: AuditValueSnapshot | None = None
    observed: AuditValueSnapshot | None = None
    upstream_rule_reference: str | None = None
    mandatory: bool = True

    def __post_init__(self) -> None:
        try:
            ValidationCheck(
                check_id=_SPEC_VALIDATION_ID,
                check_code=self.check_code,
                category=self.category,
                outcome=self.outcome,
                severity=_severity_for_outcome(self.outcome),
                source_locations=self.source_locations,
                expected=self.expected,
                observed=self.observed,
                message=self.message,
                upstream_rule_reference=self.upstream_rule_reference,
                mandatory=self.mandatory,
            )
        except (AuditReportError, ValidationCoreError) as exc:
            raise ValidationCoreError(
                f"invalid validation check specification: {exc}"
            ) from exc


def _validate_dispatched_artifact(
    dispatched_artifact: DispatchedArtifact,
) -> None:
    if not isinstance(dispatched_artifact, DispatchedArtifact):
        raise ValidationCoreError(
            "dispatched_artifact must be a DispatchedArtifact"
        )
    if not dispatched_artifact.source_artifact.verify_integrity():
        raise ValidationCoreError(
            "source artifact integrity verification failed"
        )


def _validate_check_specs(
    check_specs: tuple[ValidationCheckSpec, ...],
    *,
    allow_empty: bool,
) -> None:
    if not isinstance(check_specs, tuple):
        raise ValidationCoreError("check_specs must be a tuple")
    if not allow_empty and not check_specs:
        raise ValidationCoreError("check_specs must not be empty")
    if any(
        not isinstance(spec, ValidationCheckSpec)
        for spec in check_specs
    ):
        raise ValidationCoreError(
            "check_specs must contain ValidationCheckSpec values"
        )


def _validate_uuid(value: str, field_name: str) -> UUID:
    if not isinstance(value, str):
        raise ValidationCoreError(f"{field_name} must be a string")
    try:
        return UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValidationCoreError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_utc_timestamp(
    value: datetime,
    field_name: str,
) -> None:
    if not isinstance(value, datetime):
        raise ValidationCoreError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationCoreError(
            f"{field_name} must include a timezone"
        )
    if value.utcoffset() != timedelta(0):
        raise ValidationCoreError(
            f"{field_name} must be normalized to UTC"
        )


def _validate_registry_revision(value: str) -> None:
    if not isinstance(value, str):
        raise ValidationCoreError("registry_revision must be a string")
    if not value or value != value.strip():
        raise ValidationCoreError(
            "registry_revision must be nonempty without outer whitespace"
        )
    if any(character.isspace() for character in value):
        raise ValidationCoreError(
            "registry_revision must not contain whitespace"
        )
    if "\x00" in value:
        raise ValidationCoreError(
            "registry_revision must not contain NUL"
        )


def _validate_missing_package_members(
    missing_package_members: tuple[str, ...],
) -> None:
    if not isinstance(missing_package_members, tuple):
        raise ValidationCoreError(
            "missing_package_members must be a tuple"
        )
    for member in missing_package_members:
        if not isinstance(member, str):
            raise ValidationCoreError(
                "missing_package_members must contain strings"
            )
        if not member or member != member.strip():
            raise ValidationCoreError(
                "missing package members must be nonempty without "
                "outer whitespace"
            )
        if "\x00" in member:
            raise ValidationCoreError(
                "missing package members must not contain NUL"
            )
    if len(set(missing_package_members)) != len(
        missing_package_members
    ):
        raise ValidationCoreError(
            "missing_package_members must be unique"
        )


def _registration_check_spec(
    dispatched_artifact: DispatchedArtifact,
) -> ValidationCheckSpec:
    registration = dispatched_artifact.registration
    status = registration.status

    if status is RegistrationStatus.REGISTERED:
        record = registration.compatibility_record
        if record is None:
            raise ValidationCoreError(
                "registered dispatch is missing its compatibility record"
            )
        return ValidationCheckSpec(
            check_code="registry_resolution",
            category=ValidationCategory.IDENTITY,
            outcome=CheckOutcome.PASS,
            message=(
                "The declared artifact identity matched one exact "
                "compatibility record."
            ),
            expected=AuditValueSnapshot(record.identifier),
            observed=AuditValueSnapshot(
                registration.declared_identifier
            ),
        )

    if status is RegistrationStatus.MISSING_IDENTIFIER:
        return ValidationCheckSpec(
            check_code="registry_resolution",
            category=ValidationCategory.IDENTITY,
            outcome=CheckOutcome.WARNING,
            message=(
                "The parsed artifact does not declare the required "
                "identity field."
            ),
            expected=AuditValueSnapshot("registered identifier string"),
        )

    if status is RegistrationStatus.INVALID_IDENTIFIER:
        return ValidationCheckSpec(
            check_code="registry_resolution",
            category=ValidationCategory.IDENTITY,
            outcome=CheckOutcome.WARNING,
            message=(
                "The declared artifact identity is not a string and "
                "cannot be resolved."
            ),
            expected=AuditValueSnapshot("registered identifier string"),
        )

    if status is RegistrationStatus.UNKNOWN_IDENTIFIER:
        return ValidationCheckSpec(
            check_code="registry_resolution",
            category=ValidationCategory.IDENTITY,
            outcome=CheckOutcome.WARNING,
            message=(
                "No exact compatibility record matches the declared "
                "artifact identity."
            ),
            observed=AuditValueSnapshot(
                registration.declared_identifier
            ),
        )

    if status is RegistrationStatus.UNSUPPORTED_KIND:
        return ValidationCheckSpec(
            check_code="registry_resolution",
            category=ValidationCategory.IDENTITY,
            outcome=CheckOutcome.WARNING,
            message=(
                "The declared artifact kind is not supported for the "
                "resolved identity."
            ),
            expected=AuditValueSnapshot(registration.expected_kinds),
            observed=AuditValueSnapshot(registration.declared_kind),
        )

    if status is RegistrationStatus.NOT_APPLICABLE:
        return ValidationCheckSpec(
            check_code="registry_resolution",
            category=ValidationCategory.IDENTITY,
            outcome=CheckOutcome.NOT_APPLICABLE,
            message=(
                "Registry resolution is not applicable to this "
                "unparsed container classification."
            ),
            observed=AuditValueSnapshot(
                dispatched_artifact.classification.value
            ),
            mandatory=False,
        )

    raise ValidationCoreError("unsupported registration status")


def base_check_specs(
    dispatched_artifact: DispatchedArtifact,
) -> tuple[ValidationCheckSpec, ...]:
    """Return container, classification, and registry checks in order."""

    _validate_dispatched_artifact(dispatched_artifact)
    source = dispatched_artifact.source_artifact
    return (
        ValidationCheckSpec(
            check_code="source_integrity",
            category=ValidationCategory.CONTAINER,
            outcome=CheckOutcome.PASS,
            message=(
                "Captured source bytes match their calculated SHA-256 "
                "digest."
            ),
            expected=AuditValueSnapshot(True),
            observed=AuditValueSnapshot(source.verify_integrity()),
        ),
        ValidationCheckSpec(
            check_code="artifact_classification",
            category=ValidationCategory.CONTAINER,
            outcome=CheckOutcome.PASS,
            message=(
                "The artifact container was classified without executing "
                "its content."
            ),
            observed=AuditValueSnapshot(
                dispatched_artifact.classification.value
            ),
        ),
        _registration_check_spec(dispatched_artifact),
    )


def materialize_validation_checks(
    check_specs: tuple[ValidationCheckSpec, ...],
    *,
    audit_report_id: str,
) -> tuple[ValidationCheck, ...]:
    """Assign stable report-local IDs without changing check order."""

    _validate_check_specs(check_specs, allow_empty=False)
    report_namespace = _validate_uuid(
        audit_report_id,
        "audit_report_id",
    )
    checks: list[ValidationCheck] = []
    for ordinal, spec in enumerate(check_specs, start=1):
        check_id = str(
            uuid5(
                report_namespace,
                f"validation-check:{ordinal}:{spec.check_code}",
            )
        )
        checks.append(
            ValidationCheck(
                check_id=check_id,
                check_code=spec.check_code,
                category=spec.category,
                outcome=spec.outcome,
                severity=_severity_for_outcome(spec.outcome),
                source_locations=spec.source_locations,
                expected=spec.expected,
                observed=spec.observed,
                message=spec.message,
                upstream_rule_reference=(
                    spec.upstream_rule_reference
                ),
                mandatory=spec.mandatory,
            )
        )
    return tuple(checks)


def derive_validation_status(
    dispatched_artifact: DispatchedArtifact,
    checks: tuple[ValidationCheck, ...],
    *,
    validation_complete: bool,
    missing_package_members: tuple[str, ...] = (),
) -> ValidationStatus:
    """Derive one conservative status from registration and checks."""

    _validate_dispatched_artifact(dispatched_artifact)
    if not isinstance(checks, tuple) or not checks:
        raise ValidationCoreError("checks must be a nonempty tuple")
    if any(not isinstance(check, ValidationCheck) for check in checks):
        raise ValidationCoreError(
            "checks must contain ValidationCheck values"
        )
    if not isinstance(validation_complete, bool):
        raise ValidationCoreError(
            "validation_complete must be a boolean"
        )
    _validate_missing_package_members(missing_package_members)

    registration_status = dispatched_artifact.registration.status
    registered = registration_status is RegistrationStatus.REGISTERED
    if validation_complete and not registered:
        raise ValidationCoreError(
            "complete validation requires a registered artifact"
        )
    if missing_package_members and not registered:
        raise ValidationCoreError(
            "missing package members require a registered artifact"
        )

    if not registered:
        if registration_status is RegistrationStatus.UNSUPPORTED_KIND:
            return ValidationStatus.KNOWN_UNSUPPORTED
        return ValidationStatus.UNRECOGNIZED

    if missing_package_members:
        return ValidationStatus.INCOMPLETE_PACKAGE
    if not validation_complete:
        return ValidationStatus.KNOWN_UNSUPPORTED

    outcomes = tuple(check.outcome for check in checks)
    if CheckOutcome.FAIL in outcomes:
        return ValidationStatus.RECOGNIZED_INVALID
    if CheckOutcome.NOT_EVALUATED in outcomes:
        return ValidationStatus.KNOWN_UNSUPPORTED
    if CheckOutcome.WARNING in outcomes:
        return ValidationStatus.RECOGNIZED_VALID_WITH_WARNINGS
    return ValidationStatus.RECOGNIZED_VALID


def _registry_binding_id(
    source_artifact_id: str,
    record: CompatibilityRecord,
    registry_revision: str,
) -> str:
    source_namespace = _validate_uuid(
        source_artifact_id,
        "source_artifact_id",
    )
    kind = record.artifact_kind if record.artifact_kind is not None else ""
    binding_name = (
        f"registry-binding:{registry_revision}:"
        f"{record.identifier_field.value}:{record.identifier}:{kind}"
    )
    return str(uuid5(source_namespace, binding_name))


def _declared_schema_identifier(
    dispatched_artifact: DispatchedArtifact,
) -> str | None:
    registration = dispatched_artifact.registration
    if registration.identifier_field is IdentifierField.SCHEMA:
        return registration.declared_identifier
    return None


def build_audit_report(
    dispatched_artifact: DispatchedArtifact,
    validation_check_specs: tuple[ValidationCheckSpec, ...] = (),
    *,
    validation_complete: bool,
    started_at: datetime,
    completed_at: datetime,
    registry_revision: str,
    observatory_version: str | None = None,
    missing_package_members: tuple[str, ...] = (),
    audit_report_id: str | None = None,
) -> AuditReport:
    """Build one immutable report from a dispatched source and checks."""

    _validate_dispatched_artifact(dispatched_artifact)
    _validate_check_specs(validation_check_specs, allow_empty=True)
    if not isinstance(validation_complete, bool):
        raise ValidationCoreError(
            "validation_complete must be a boolean"
        )
    if validation_complete and not validation_check_specs:
        raise ValidationCoreError(
            "complete validation requires artifact-specific checks"
        )
    _validate_utc_timestamp(started_at, "started_at")
    _validate_utc_timestamp(completed_at, "completed_at")
    _validate_registry_revision(registry_revision)
    _validate_missing_package_members(missing_package_members)

    source = dispatched_artifact.source_artifact
    if started_at < source.loaded_at:
        raise ValidationCoreError(
            "started_at must not precede the source load timestamp"
        )
    if completed_at < started_at:
        raise ValidationCoreError(
            "completed_at must not precede started_at"
        )

    report_id = audit_report_id if audit_report_id is not None else str(
        uuid4()
    )
    _validate_uuid(report_id, "audit_report_id")
    all_specs = base_check_specs(
        dispatched_artifact
    ) + validation_check_specs
    checks = materialize_validation_checks(
        all_specs,
        audit_report_id=report_id,
    )
    overall_status = derive_validation_status(
        dispatched_artifact,
        checks,
        validation_complete=validation_complete,
        missing_package_members=missing_package_members,
    )

    record = dispatched_artifact.compatibility_record
    if record is None:
        registry_binding_id = None
        matched_registry_identifier = None
        matched_registry_kind = None
        producer_path = None
        producer_version = None
        measurement_contour = None
    else:
        registry_binding_id = _registry_binding_id(
            source.source_artifact_id,
            record,
            registry_revision,
        )
        matched_registry_identifier = record.identifier
        matched_registry_kind = record.artifact_kind
        producer_path = record.producer_path
        producer_version = record.producer_version
        measurement_contour = record.measurement_contour

    try:
        return AuditReport(
            audit_report_id=report_id,
            source_artifact_id=source.source_artifact_id,
            source_filename=source.source_filename,
            source_path=source.source_path,
            source_sha256=source.content_sha256,
            source_byte_length=source.byte_length,
            loaded_at=source.loaded_at,
            detected_format=dispatched_artifact.classification,
            declared_schema_identifier=(
                _declared_schema_identifier(dispatched_artifact)
            ),
            declared_kind=(
                dispatched_artifact.registration.declared_kind
            ),
            registry_binding_id=registry_binding_id,
            matched_registry_identifier=matched_registry_identifier,
            matched_registry_kind=matched_registry_kind,
            producer_path=producer_path,
            producer_version=producer_version,
            measurement_contour=measurement_contour,
            started_at=started_at,
            completed_at=completed_at,
            observatory_version=observatory_version,
            registry_revision=registry_revision,
            checks=checks,
            missing_package_members=missing_package_members,
            overall_status=overall_status,
        )
    except AuditReportError as exc:
        raise ValidationCoreError(
            f"audit report construction failed: {exc}"
        ) from exc
