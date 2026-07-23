"""Read-only orchestration for one Artifact Auditor validation run.

This module dispatches captured source bytes to an existing contour-specific
validator and builds one Observatory-derived audit report. It does not execute
artifact content, follow producer-declared paths, infer missing package bytes,
modify source artifacts, or combine FRP measurement contours.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from parsers.artifact_dispatch import (
    ArtifactClassification,
    DispatchedArtifact,
    RegistrationStatus,
    dispatch_artifact,
)
from parsers.source_artifact import SourceArtifact
from schemas.registry import MeasurementContour

from .audit_report import AuditReport
from .comparative_architecture_validator import (
    validate_comparative_architecture,
)
from .deterministic_package_validator import (
    validate_deterministic_package,
)
from .hardware_sensitivity_validator import (
    validate_hardware_sensitivity,
)
from .m15_artifact_validator import validate_m15_artifact
from .m15_vector_validator import validate_m15_vector
from .m3_benchmark_validator import validate_m3_benchmark
from .structured_output_validator import validate_structured_output
from .validation_core import (
    ValidationCheckSpec,
    build_audit_report,
)


__all__ = [
    "ArtifactAuditorError",
    "audit_dispatched_artifact",
    "audit_source_artifact",
]


_M15_PACKAGE_KIND = "rtl_comparison_vector_package"


class ArtifactAuditorError(ValueError):
    """Raised when an audit request violates orchestration invariants."""


@dataclass(frozen=True, slots=True)
class _ValidationRoute:
    check_specs: tuple[ValidationCheckSpec, ...]
    validation_complete: bool
    missing_package_members: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.check_specs, tuple):
            raise ArtifactAuditorError("check_specs must be a tuple")
        if any(
            not isinstance(spec, ValidationCheckSpec)
            for spec in self.check_specs
        ):
            raise ArtifactAuditorError(
                "check_specs must contain ValidationCheckSpec values"
            )
        if not isinstance(self.validation_complete, bool):
            raise ArtifactAuditorError(
                "validation_complete must be a boolean"
            )
        if self.validation_complete and not self.check_specs:
            raise ArtifactAuditorError(
                "complete validation requires artifact-specific checks"
            )
        if not isinstance(self.missing_package_members, tuple):
            raise ArtifactAuditorError(
                "missing_package_members must be a tuple"
            )
        if any(
            not isinstance(name, str) or not name
            for name in self.missing_package_members
        ):
            raise ArtifactAuditorError(
                "missing_package_members must contain nonempty strings"
            )
        if (
            self.missing_package_members
            != tuple(sorted(self.missing_package_members))
            or len(set(self.missing_package_members))
            != len(self.missing_package_members)
        ):
            raise ArtifactAuditorError(
                "missing_package_members must be ordered and unique"
            )
        if self.validation_complete and self.missing_package_members:
            raise ArtifactAuditorError(
                "complete validation cannot have missing package members"
            )


def _validate_dispatched(dispatched: DispatchedArtifact) -> None:
    if not isinstance(dispatched, DispatchedArtifact):
        raise ArtifactAuditorError(
            "dispatched_artifact must be a DispatchedArtifact"
        )
    if not dispatched.source_artifact.verify_integrity():
        raise ArtifactAuditorError(
            "source artifact integrity verification failed"
        )


def _validate_package_members(
    package_members: Mapping[str, SourceArtifact] | None,
) -> None:
    if package_members is not None and not isinstance(
        package_members, Mapping
    ):
        raise ArtifactAuditorError(
            "package_members must be a mapping or None"
        )


def _without_package_members(
    package_members: Mapping[str, SourceArtifact] | None,
) -> None:
    if package_members is not None:
        raise ArtifactAuditorError(
            "package_members apply only to the registered M15 "
            "rtl_comparison_vector_package artifact"
        )


def _route_registered(
    dispatched: DispatchedArtifact,
    package_members: Mapping[str, SourceArtifact] | None,
) -> _ValidationRoute:
    record = dispatched.compatibility_record
    if record is None:
        raise ArtifactAuditorError(
            "registered dispatch is missing its compatibility record"
        )

    contour = record.measurement_contour
    if contour is MeasurementContour.STRUCTURED_OUTPUT:
        _without_package_members(package_members)
        result = validate_structured_output(dispatched)
        return _ValidationRoute(result.check_specs, True)

    if contour is MeasurementContour.M3_BENCHMARK_MATRIX:
        _without_package_members(package_members)
        result = validate_m3_benchmark(dispatched)
        return _ValidationRoute(result.check_specs, True)

    if contour is MeasurementContour.M15_IMPLEMENTATION_MAPPING:
        if dispatched.classification is ArtifactClassification.M15_VECTOR:
            _without_package_members(package_members)
            result = validate_m15_vector(dispatched)
            return _ValidationRoute(result.check_specs, True)

        if dispatched.classification is not ArtifactClassification.JSON:
            raise ArtifactAuditorError(
                "registered M15 artifact has an unsupported classification"
            )

        artifact_result = validate_m15_artifact(dispatched)
        if record.artifact_kind != _M15_PACKAGE_KIND:
            _without_package_members(package_members)
            return _ValidationRoute(artifact_result.check_specs, True)

        package_result = validate_deterministic_package(
            dispatched,
            {} if package_members is None else package_members,
        )
        missing = package_result.missing_member_names
        return _ValidationRoute(
            artifact_result.check_specs + package_result.check_specs,
            not missing,
            missing,
        )

    if contour is MeasurementContour.COMPARATIVE_ARCHITECTURE:
        _without_package_members(package_members)
        result = validate_comparative_architecture(dispatched)
        return _ValidationRoute(result.check_specs, True)

    if contour is MeasurementContour.HARDWARE_SENSITIVITY:
        _without_package_members(package_members)
        result = validate_hardware_sensitivity(dispatched)
        return _ValidationRoute(result.check_specs, True)

    raise ArtifactAuditorError(
        "registered artifact has no contour-specific validator route"
    )


def _route_validation(
    dispatched: DispatchedArtifact,
    package_members: Mapping[str, SourceArtifact] | None,
) -> _ValidationRoute:
    _validate_dispatched(dispatched)
    _validate_package_members(package_members)
    if dispatched.registration.status is not RegistrationStatus.REGISTERED:
        _without_package_members(package_members)
        return _ValidationRoute((), False)
    return _route_registered(dispatched, package_members)


def _validate_optional_timestamp(
    value: datetime | None,
    field_name: str,
) -> None:
    if value is None:
        return
    if not isinstance(value, datetime):
        raise ArtifactAuditorError(f"{field_name} must be a datetime or None")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ArtifactAuditorError(
            f"{field_name} must include a timezone"
        )
    if value.utcoffset() != timedelta(0):
        raise ArtifactAuditorError(
            f"{field_name} must be normalized to UTC"
        )


def _started_at(
    source: SourceArtifact,
    requested: datetime | None,
) -> datetime:
    _validate_optional_timestamp(requested, "started_at")
    if requested is not None:
        return requested
    now = datetime.now(timezone.utc)
    return source.loaded_at if source.loaded_at > now else now


def _completed_at(
    started_at: datetime,
    requested: datetime | None,
) -> datetime:
    _validate_optional_timestamp(requested, "completed_at")
    if requested is not None:
        return requested
    now = datetime.now(timezone.utc)
    return started_at if started_at > now else now


def audit_dispatched_artifact(
    dispatched_artifact: DispatchedArtifact,
    *,
    registry_revision: str,
    package_members: Mapping[str, SourceArtifact] | None = None,
    observatory_version: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    audit_report_id: str | None = None,
) -> AuditReport:
    """Validate one dispatched artifact and build an immutable report."""

    _validate_dispatched(dispatched_artifact)
    started = _started_at(
        dispatched_artifact.source_artifact,
        started_at,
    )
    route = _route_validation(dispatched_artifact, package_members)
    completed = _completed_at(started, completed_at)
    return build_audit_report(
        dispatched_artifact,
        route.check_specs,
        validation_complete=route.validation_complete,
        started_at=started,
        completed_at=completed,
        registry_revision=registry_revision,
        observatory_version=observatory_version,
        missing_package_members=route.missing_package_members,
        audit_report_id=audit_report_id,
    )


def audit_source_artifact(
    source_artifact: SourceArtifact,
    *,
    registry_revision: str,
    package_members: Mapping[str, SourceArtifact] | None = None,
    observatory_version: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    audit_report_id: str | None = None,
) -> AuditReport:
    """Dispatch captured source bytes and build one immutable audit report."""

    if not isinstance(source_artifact, SourceArtifact):
        raise ArtifactAuditorError(
            "source_artifact must be a SourceArtifact"
        )
    dispatched = dispatch_artifact(source_artifact)
    return audit_dispatched_artifact(
        dispatched,
        registry_revision=registry_revision,
        package_members=package_members,
        observatory_version=observatory_version,
        started_at=started_at,
        completed_at=completed_at,
        audit_report_id=audit_report_id,
    )
