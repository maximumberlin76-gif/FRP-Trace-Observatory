"""Read-only intake for the four exact FRP M30 published members.

The intake begins only after the M1 archive, M2 published boundary, and M3
registry validations succeed.  It retains the four registered raw members,
captures their unchanged bytes through the existing source-artifact model,
strictly decodes their JSON objects, and binds each object to its exact
identifier field and existing Observatory mode routes.  It never executes,
normalizes, rewrites, extracts, or writes back upstream content.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final, Mapping

from artifact_auditor.m30_archive_intake import (
    FRP_M30_ARCHIVE_SHA256,
    M30ArchiveValidation,
    RetainedArchiveMember,
    validate_m30_archive,
)
from parsers.json_artifact import ParsedJsonArtifact, parse_json_artifact
from parsers.source_artifact import (
    SourceArtifact,
    SourceContainerFormat,
    capture_source_bytes,
)
from schemas.m30_published_registry import (
    M30_PUBLISHED_REGISTRY_REVISION,
    PublishedMemberRegistration,
    PublishedModeRoute,
    PublishedRegistryValidation,
    registration_for_member_id,
    validate_m30_published_registry,
)
from schemas.registry import ObservatoryMode


__all__ = [
    "M30PublishedMemberIntakeError",
    "PublishedIdentifierBinding",
    "PublishedIdentifierEvidence",
    "PublishedIdentifierMismatchError",
    "PublishedMemberIntake",
    "PublishedMemberIntakeBatch",
    "identifier_binding_for_registration",
    "identifier_evidence_for_registration",
    "intake_m30_published_members",
]


class PublishedIdentifierBinding(StrEnum):
    """Exact published field layout supporting one M3 identifier."""

    SCHEMA_FIELD = "schema_field"
    ARTIFACT_ID_SCHEMA_VERSION_FIELDS = (
        "artifact_id_schema_version_fields"
    )


_IDENTIFIER_BINDINGS_BY_MEMBER_ID: Final[
    Mapping[str, PublishedIdentifierBinding]
]
_IDENTIFIER_BINDINGS_BY_MEMBER_ID = MappingProxyType(
    {
        "m16-fpga-preparation-execution-trace": (
            PublishedIdentifierBinding.SCHEMA_FIELD
        ),
        "m27-telemetry-semantics": (
            PublishedIdentifierBinding.ARTIFACT_ID_SCHEMA_VERSION_FIELDS
        ),
        "m28-trace-observatory-upstream-contract": (
            PublishedIdentifierBinding.SCHEMA_FIELD
        ),
        "m28-hierarchical-scaling-contract": (
            PublishedIdentifierBinding.SCHEMA_FIELD
        ),
    }
)
_IDENTIFIER_EVIDENCE_BY_MEMBER_ID: Final[
    Mapping[str, tuple[tuple[str, str], ...]]
]
_IDENTIFIER_EVIDENCE_BY_MEMBER_ID = MappingProxyType(
    {
        "m16-fpga-preparation-execution-trace": (
            (
                "schema",
                "frp.m16.fpga_preparation_execution_trace.v2.1.0",
            ),
        ),
        "m27-telemetry-semantics": (
            ("artifact_id", "frp-m27-telemetry-semantics"),
            ("schema_version", "2.9.0"),
        ),
        "m28-trace-observatory-upstream-contract": (
            (
                "schema",
                "frp.m28.trace_observatory_upstream_contract.v3.0.0",
            ),
        ),
        "m28-hierarchical-scaling-contract": (
            (
                "schema",
                "frp.m28.hierarchical_scaling_contract.v3.0.0",
            ),
        ),
    }
)


class M30PublishedMemberIntakeError(ValueError):
    """Raised when a published-member intake invariant is violated."""


class PublishedIdentifierMismatchError(M30PublishedMemberIntakeError):
    """Raised when exact parsed identifier evidence differs from M3."""

    def __init__(
        self,
        member_id: str,
        field_name: str,
        observed: object,
        expected: str,
    ) -> None:
        super().__init__(
            f"published member {member_id!r} {field_name} mismatch: "
            f"{observed!r} != {expected!r}"
        )
        self.member_id = member_id
        self.field_name = field_name
        self.observed = observed
        self.expected = expected


@dataclass(frozen=True, slots=True)
class PublishedIdentifierEvidence:
    """One exact unmodified identifier-bearing field and value."""

    field_name: str
    value: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.field_name, str)
            or not self.field_name
            or self.field_name != self.field_name.strip()
            or any(character.isspace() for character in self.field_name)
        ):
            raise M30PublishedMemberIntakeError(
                "identifier evidence field_name must be a machine token"
            )
        if (
            not isinstance(self.value, str)
            or not self.value
            or self.value != self.value.strip()
        ):
            raise M30PublishedMemberIntakeError(
                "identifier evidence value must be a nonempty string"
            )


def _expected_routes(
    registration: PublishedMemberRegistration,
) -> tuple[PublishedModeRoute, ...]:
    return tuple(
        PublishedModeRoute(registration=registration, mode=mode)
        for mode in registration.observatory_modes
    )


def identifier_binding_for_registration(
    registration: PublishedMemberRegistration,
) -> PublishedIdentifierBinding:
    """Return the exact field layout for one canonical M3 registration."""

    if not isinstance(registration, PublishedMemberRegistration):
        raise M30PublishedMemberIntakeError(
            "registration must be PublishedMemberRegistration"
        )
    try:
        canonical = registration_for_member_id(registration.member_id)
    except LookupError as exc:
        raise M30PublishedMemberIntakeError(
            f"registration is not in the canonical M30 inventory: "
            f"{registration.member_id!r}"
        ) from exc
    if registration != canonical:
        raise M30PublishedMemberIntakeError(
            "registration differs from the canonical M30 identity"
        )
    try:
        return _IDENTIFIER_BINDINGS_BY_MEMBER_ID[registration.member_id]
    except KeyError as exc:
        raise M30PublishedMemberIntakeError(
            "canonical M30 registration has no identifier binding"
        ) from exc


def identifier_evidence_for_registration(
    registration: PublishedMemberRegistration,
) -> tuple[PublishedIdentifierEvidence, ...]:
    """Return exact published identifier fields for one M3 registration."""

    identifier_binding_for_registration(registration)
    try:
        values = _IDENTIFIER_EVIDENCE_BY_MEMBER_ID[
            registration.member_id
        ]
    except KeyError as exc:
        raise M30PublishedMemberIntakeError(
            "canonical M30 registration has no identifier evidence"
        ) from exc
    return tuple(
        PublishedIdentifierEvidence(field_name=field_name, value=value)
        for field_name, value in values
    )


@dataclass(frozen=True, slots=True)
class PublishedMemberIntake:
    """One exact raw member, strict JSON view, and eligible mode routes."""

    archive_sha256: str
    registry_revision: str
    registration: PublishedMemberRegistration
    routes: tuple[PublishedModeRoute, ...]
    retained_member: RetainedArchiveMember
    source_artifact: SourceArtifact
    parsed_artifact: ParsedJsonArtifact
    identifier_binding: PublishedIdentifierBinding
    identifier_evidence: tuple[PublishedIdentifierEvidence, ...]

    def __post_init__(self) -> None:
        if self.archive_sha256 != FRP_M30_ARCHIVE_SHA256:
            raise M30PublishedMemberIntakeError(
                "published intake archive digest mismatch"
            )
        if self.registry_revision != M30_PUBLISHED_REGISTRY_REVISION:
            raise M30PublishedMemberIntakeError(
                "published intake registry revision mismatch"
            )
        if not isinstance(
            self.registration,
            PublishedMemberRegistration,
        ):
            raise M30PublishedMemberIntakeError(
                "registration must be PublishedMemberRegistration"
            )
        try:
            canonical_registration = registration_for_member_id(
                self.registration.member_id
            )
        except LookupError as exc:
            raise M30PublishedMemberIntakeError(
                "registration is not in the canonical M30 inventory"
            ) from exc
        if self.registration != canonical_registration:
            raise M30PublishedMemberIntakeError(
                "registration differs from the canonical M30 identity"
            )
        if not isinstance(self.routes, tuple):
            raise M30PublishedMemberIntakeError("routes must be a tuple")
        if self.routes != _expected_routes(self.registration):
            raise M30PublishedMemberIntakeError(
                "published intake route inventory mismatch"
            )
        if not isinstance(self.retained_member, RetainedArchiveMember):
            raise M30PublishedMemberIntakeError(
                "retained_member must be RetainedArchiveMember"
            )
        retained_metadata = self.retained_member.member
        if retained_metadata.path != self.registration.source_path:
            raise M30PublishedMemberIntakeError(
                "retained member path differs from the registration"
            )
        if retained_metadata.byte_length != self.registration.byte_length:
            raise M30PublishedMemberIntakeError(
                "retained member byte length differs from the registration"
            )
        if retained_metadata.raw_sha256 != self.registration.raw_sha256:
            raise M30PublishedMemberIntakeError(
                "retained member digest differs from the registration"
            )
        if not isinstance(self.source_artifact, SourceArtifact):
            raise M30PublishedMemberIntakeError(
                "source_artifact must be SourceArtifact"
            )
        if not self.source_artifact.verify_integrity():
            raise M30PublishedMemberIntakeError(
                "source artifact integrity verification failed"
            )
        expected_filename = PurePosixPath(
            self.registration.source_path
        ).name
        if self.source_artifact.source_filename != expected_filename:
            raise M30PublishedMemberIntakeError(
                "source filename differs from the registered path"
            )
        if self.source_artifact.source_path != self.registration.source_path:
            raise M30PublishedMemberIntakeError(
                "source path differs from the registration"
            )
        if self.source_artifact.byte_length != self.registration.byte_length:
            raise M30PublishedMemberIntakeError(
                "source byte length differs from the registration"
            )
        if self.source_artifact.content_sha256 != self.registration.raw_sha256:
            raise M30PublishedMemberIntakeError(
                "source digest differs from the registration"
            )
        if self.source_artifact.raw_bytes != self.retained_member.raw_bytes:
            raise M30PublishedMemberIntakeError(
                "source bytes differ from the retained archive member"
            )
        if (
            self.source_artifact.detected_container_format
            is not SourceContainerFormat.JSON_CANDIDATE
        ):
            raise M30PublishedMemberIntakeError(
                "published member must be a strict JSON candidate"
            )
        if not isinstance(self.parsed_artifact, ParsedJsonArtifact):
            raise M30PublishedMemberIntakeError(
                "parsed_artifact must be ParsedJsonArtifact"
            )
        if self.parsed_artifact.source_artifact is not self.source_artifact:
            raise M30PublishedMemberIntakeError(
                "parsed artifact must reference the captured source"
            )
        if not isinstance(
            self.identifier_binding,
            PublishedIdentifierBinding,
        ):
            raise M30PublishedMemberIntakeError(
                "identifier_binding must be PublishedIdentifierBinding"
            )
        expected_binding = identifier_binding_for_registration(
            self.registration
        )
        if self.identifier_binding is not expected_binding:
            raise M30PublishedMemberIntakeError(
                "identifier binding differs from the canonical M30 binding"
            )
        if not isinstance(self.identifier_evidence, tuple):
            raise M30PublishedMemberIntakeError(
                "identifier_evidence must be a tuple"
            )
        if (
            not self.identifier_evidence
            or any(
                not isinstance(item, PublishedIdentifierEvidence)
                for item in self.identifier_evidence
            )
        ):
            raise M30PublishedMemberIntakeError(
                "identifier_evidence must contain exact field evidence"
            )
        expected_evidence = identifier_evidence_for_registration(
            self.registration
        )
        if self.identifier_evidence != expected_evidence:
            raise M30PublishedMemberIntakeError(
                "identifier evidence differs from the canonical M30 evidence"
            )
        field_names = tuple(
            item.field_name for item in self.identifier_evidence
        )
        if len(set(field_names)) != len(field_names):
            raise M30PublishedMemberIntakeError(
                "identifier evidence field names must be unique"
            )
        if self.identifier_binding is PublishedIdentifierBinding.SCHEMA_FIELD:
            expected_shape = ("schema",)
            if field_names != expected_shape:
                raise M30PublishedMemberIntakeError(
                    "schema binding requires only the schema field"
                )
            if (
                self.identifier_evidence[0].value
                != self.registration.schema_identifier
            ):
                raise M30PublishedMemberIntakeError(
                    "schema evidence differs from the registration"
                )
        else:
            expected_shape = ("artifact_id", "schema_version")
            if field_names != expected_shape:
                raise M30PublishedMemberIntakeError(
                    "composite binding requires artifact_id then "
                    "schema_version"
                )
        for evidence in self.identifier_evidence:
            observed = self.parsed_artifact.root.get(evidence.field_name)
            if observed != evidence.value:
                raise PublishedIdentifierMismatchError(
                    self.registration.member_id,
                    evidence.field_name,
                    observed,
                    evidence.value,
                )
        if (
            self.identifier_binding
            is PublishedIdentifierBinding.ARTIFACT_ID_SCHEMA_VERSION_FIELDS
            and self.parsed_artifact.declared_schema_identifier is not None
        ):
            raise M30PublishedMemberIntakeError(
                "composite identifier members must not declare a schema alias"
            )

    @property
    def member_id(self) -> str:
        """Return the exact M3 member identity."""

        return self.registration.member_id

    @property
    def eligible_modes(self) -> tuple[ObservatoryMode, ...]:
        """Return only the exact existing modes registered for this member."""

        return tuple(route.mode for route in self.routes)

    @property
    def raw_bytes(self) -> bytes:
        """Return the unchanged retained upstream bytes."""

        return self.source_artifact.raw_bytes


@dataclass(frozen=True, slots=True)
class PublishedMemberIntakeBatch:
    """Complete four-member intake evidence for one exact M30 archive."""

    archive_validation: M30ArchiveValidation
    registry_validation: PublishedRegistryValidation
    members: tuple[PublishedMemberIntake, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.archive_validation, M30ArchiveValidation):
            raise M30PublishedMemberIntakeError(
                "archive_validation must be M30ArchiveValidation"
            )
        if not isinstance(
            self.registry_validation,
            PublishedRegistryValidation,
        ):
            raise M30PublishedMemberIntakeError(
                "registry_validation must be PublishedRegistryValidation"
            )
        if (
            self.archive_validation.archive_sha256
            != self.registry_validation.archive_sha256
        ):
            raise M30PublishedMemberIntakeError(
                "archive and registry validation digests differ"
            )
        if not isinstance(self.members, tuple):
            raise M30PublishedMemberIntakeError(
                "members must be a tuple"
            )
        if any(
            not isinstance(member, PublishedMemberIntake)
            for member in self.members
        ):
            raise M30PublishedMemberIntakeError(
                "members must contain PublishedMemberIntake values"
            )
        expected_registrations = self.registry_validation.registrations
        if tuple(
            member.registration for member in self.members
        ) != expected_registrations:
            raise M30PublishedMemberIntakeError(
                "published intake member order or inventory mismatch"
            )
        expected_paths = tuple(
            registration.source_path
            for registration in expected_registrations
        )
        retained_paths = tuple(
            retained.member.path
            for retained in self.archive_validation.retained_members
        )
        if retained_paths != expected_paths:
            raise M30PublishedMemberIntakeError(
                "retained archive inventory differs from the registry"
            )
        for member in self.members:
            if (
                member.archive_sha256
                != self.archive_validation.archive_sha256
            ):
                raise M30PublishedMemberIntakeError(
                    "member archive digest differs from the batch"
                )
            if (
                member.registry_revision
                != self.registry_validation.registry_revision
            ):
                raise M30PublishedMemberIntakeError(
                    "member registry revision differs from the batch"
                )
            if member.retained_member is not (
                self.archive_validation.retained_member(
                    member.registration.source_path
                )
            ):
                raise M30PublishedMemberIntakeError(
                    "member retained evidence is not from this batch"
                )

    @property
    def total_byte_length(self) -> int:
        """Return the exact total retained raw-byte length."""

        return sum(member.source_artifact.byte_length for member in self.members)

    @property
    def total_route_count(self) -> int:
        """Return the exact count of eligible member-to-mode routes."""

        return sum(len(member.routes) for member in self.members)

    def members_for_mode(
        self,
        mode: ObservatoryMode,
    ) -> tuple[PublishedMemberIntake, ...]:
        """Return source-order members eligible for one existing mode."""

        if not isinstance(mode, ObservatoryMode):
            raise M30PublishedMemberIntakeError(
                "mode must be ObservatoryMode"
            )
        return tuple(
            member for member in self.members if mode in member.eligible_modes
        )


def _capture_member(
    retained: RetainedArchiveMember,
    registration: PublishedMemberRegistration,
    *,
    loaded_at: datetime,
) -> PublishedMemberIntake:
    source = capture_source_bytes(
        retained.raw_bytes,
        source_filename=PurePosixPath(registration.source_path).name,
        source_path=registration.source_path,
        loaded_at=loaded_at,
    )
    parsed = parse_json_artifact(source)
    identifier_binding = identifier_binding_for_registration(registration)
    identifier_evidence = identifier_evidence_for_registration(registration)
    return PublishedMemberIntake(
        archive_sha256=FRP_M30_ARCHIVE_SHA256,
        registry_revision=M30_PUBLISHED_REGISTRY_REVISION,
        registration=registration,
        routes=_expected_routes(registration),
        retained_member=retained,
        source_artifact=source,
        parsed_artifact=parsed,
        identifier_binding=identifier_binding,
        identifier_evidence=identifier_evidence,
    )


def intake_m30_published_members(
    archive_path: str | Path,
    *,
    loaded_at: datetime | None = None,
) -> PublishedMemberIntakeBatch:
    """Capture and strictly decode all four canonical published members."""

    registry_validation = validate_m30_published_registry(archive_path)
    registrations = registry_validation.registrations
    retain_paths = tuple(
        registration.source_path for registration in registrations
    )
    archive_validation = validate_m30_archive(
        archive_path,
        retain_paths=retain_paths,
    )
    timestamp = (
        datetime.now(timezone.utc) if loaded_at is None else loaded_at
    )
    members = tuple(
        _capture_member(
            archive_validation.retained_member(
                registration.source_path
            ),
            registration,
            loaded_at=timestamp,
        )
        for registration in registrations
    )
    return PublishedMemberIntakeBatch(
        archive_validation=archive_validation,
        registry_validation=registry_validation,
        members=members,
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture and strictly decode the four exact FRP M30 published "
            "members without execution, normalization, or writeback."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    arguments = parser.parse_args()
    result = intake_m30_published_members(arguments.archive)
    mode_counts = {
        mode: len(result.members_for_mode(mode))
        for mode in ObservatoryMode
    }
    field_counts = {
        binding: sum(
            member.identifier_binding is binding
            for member in result.members
        )
        for binding in PublishedIdentifierBinding
    }
    print("FRP Observatory M30 published member intake: PASS")
    print(f"archive_sha256={result.archive_validation.archive_sha256}")
    print(
        "registry_revision="
        f"{result.registry_validation.registry_revision}"
    )
    print(f"published_members={len(result.members)}")
    print(f"retained_raw_bytes={result.total_byte_length}")
    print(f"strict_json_objects={len(result.members)}")
    print(f"mode_routes={result.total_route_count}")
    print(
        "artifact_auditor_members="
        f"{mode_counts[ObservatoryMode.ARTIFACT_AUDITOR]}"
    )
    print(
        "ternary_transition_visualizer_members="
        f"{mode_counts[ObservatoryMode.TERNARY_TRANSITION_VISUALIZER]}"
    )
    print(
        "trace_explorer_members="
        f"{mode_counts[ObservatoryMode.TRACE_EXPLORER]}"
    )
    print(
        "schema_field_bindings="
        f"{field_counts[PublishedIdentifierBinding.SCHEMA_FIELD]}"
    )
    print(
        "artifact_id_schema_version_bindings="
        f"{field_counts[PublishedIdentifierBinding.ARTIFACT_ID_SCHEMA_VERSION_FIELDS]}"
    )
    print("raw_byte_preservation=required")
    print("source_execution=forbidden")
    print("semantic_normalization=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
