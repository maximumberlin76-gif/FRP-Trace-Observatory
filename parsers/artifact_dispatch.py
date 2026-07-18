"""Read-only artifact classification and exact compatibility binding."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from schemas.registry import (
    CompatibilityRecord,
    IdentifierField,
    UnsupportedArtifactKindError,
    UnknownArtifactIdentifierError,
    resolve_compatibility_record,
)

from .json_artifact import (
    JsonValue,
    ParsedJsonArtifact,
    parse_json_artifact,
)
from .m15_vector import (
    M15VectorArtifact,
    parse_m15_vector,
)
from .source_artifact import (
    SourceArtifact,
    SourceContainerFormat,
)


__all__ = [
    "ArtifactClassification",
    "ArtifactDispatchError",
    "DispatchedArtifact",
    "ParsedArtifact",
    "RegistrationResult",
    "RegistrationStatus",
    "dispatch_artifact",
]


type ParsedArtifact = ParsedJsonArtifact | M15VectorArtifact


class ArtifactClassification(StrEnum):
    """Safely determined artifact container and parsed envelope type."""

    EMPTY = "empty"
    JSON = "json"
    M15_VECTOR = "m15_vector"
    UTF8_TEXT = "utf8_text"
    ZIP = "zip"
    BINARY = "binary"


class RegistrationStatus(StrEnum):
    """Result of exact compatibility registry resolution."""

    REGISTERED = "registered"
    MISSING_IDENTIFIER = "missing_identifier"
    INVALID_IDENTIFIER = "invalid_identifier"
    UNKNOWN_IDENTIFIER = "unknown_identifier"
    UNSUPPORTED_KIND = "unsupported_kind"
    NOT_APPLICABLE = "not_applicable"


class ArtifactDispatchError(ValueError):
    """Raised when dispatch metadata violates read-only invariants."""

@dataclass(frozen=True, slots=True)
class RegistrationResult:
    """Immutable exact-registry resolution result for one artifact."""

    status: RegistrationStatus
    identifier_field: IdentifierField | None
    declared_identifier: str | None
    declared_kind: str | None
    compatibility_record: CompatibilityRecord | None
    expected_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, RegistrationStatus):
            raise ArtifactDispatchError(
                "status must be a RegistrationStatus"
            )
        if (
            self.identifier_field is not None
            and not isinstance(self.identifier_field, IdentifierField)
        ):
            raise ArtifactDispatchError(
                "identifier_field must be an IdentifierField or None"
            )
        if (
            self.declared_identifier is not None
            and not isinstance(self.declared_identifier, str)
        ):
            raise ArtifactDispatchError(
                "declared_identifier must be a string or None"
            )
        if (
            self.declared_kind is not None
            and not isinstance(self.declared_kind, str)
        ):
            raise ArtifactDispatchError(
                "declared_kind must be a string or None"
            )
        if (
            self.compatibility_record is not None
            and not isinstance(
                self.compatibility_record,
                CompatibilityRecord,
            )
        ):
            raise ArtifactDispatchError(
                "compatibility_record must be a CompatibilityRecord or None"
            )
        if not isinstance(self.expected_kinds, tuple):
            raise ArtifactDispatchError("expected_kinds must be a tuple")
        if any(
            not isinstance(kind, str) or not kind
            for kind in self.expected_kinds
        ):
            raise ArtifactDispatchError(
                "expected_kinds must contain nonempty strings"
            )
        if len(set(self.expected_kinds)) != len(self.expected_kinds):
            raise ArtifactDispatchError("expected_kinds must be unique")

        if self.status is RegistrationStatus.REGISTERED:
            self._validate_registered()
            return

        if self.compatibility_record is not None:
            raise ArtifactDispatchError(
                "only registered results may contain a compatibility record"
            )

        if self.status is RegistrationStatus.NOT_APPLICABLE:
            if any(
                value is not None
                for value in (
                    self.identifier_field,
                    self.declared_identifier,
                    self.declared_kind,
                )
            ) or self.expected_kinds:
                raise ArtifactDispatchError(
                    "not-applicable results must not declare registry data"
                )
            return

        if self.identifier_field is None:
            raise ArtifactDispatchError(
                "registry resolution results require identifier_field"
            )
        if self.status in {
            RegistrationStatus.MISSING_IDENTIFIER,
            RegistrationStatus.INVALID_IDENTIFIER,
        }:
            if self.declared_identifier is not None:
                raise ArtifactDispatchError(
                    "missing or invalid identifiers must not be normalized"
                )
            if self.expected_kinds:
                raise ArtifactDispatchError(
                    "missing or invalid identifiers have no expected kinds"
                )
            return

        if self.declared_identifier is None:
            raise ArtifactDispatchError(
                "unknown identifiers and unsupported kinds require "
                "an identifier"
            )
        if self.status is RegistrationStatus.UNKNOWN_IDENTIFIER:
            if self.expected_kinds:
                raise ArtifactDispatchError(
                    "unknown identifiers have no expected kinds"
                )
            return
        if self.status is RegistrationStatus.UNSUPPORTED_KIND:
            if not self.expected_kinds:
                raise ArtifactDispatchError(
                    "unsupported kinds require expected_kinds"
                )
            return
        raise ArtifactDispatchError("unsupported registration status")

    def _validate_registered(self) -> None:
        record = self.compatibility_record
        if record is None:
            raise ArtifactDispatchError(
                "registered results require a compatibility record"
            )
        if self.identifier_field is not record.identifier_field:
            raise ArtifactDispatchError(
                "identifier_field does not match the compatibility record"
            )
        if self.declared_identifier != record.identifier:
            raise ArtifactDispatchError(
                "declared_identifier does not match the compatibility record"
            )
        if (
            record.artifact_kind is not None
            and self.declared_kind != record.artifact_kind
        ):
            raise ArtifactDispatchError(
                "declared_kind does not match the compatibility record"
            )
        if self.expected_kinds:
            raise ArtifactDispatchError(
                "registered results must not contain expected_kinds"
            )

      @dataclass(frozen=True, slots=True)
class DispatchedArtifact:
    """One immutable classification linked to unchanged source bytes."""

    source_artifact: SourceArtifact
    classification: ArtifactClassification
    parsed_artifact: ParsedArtifact | None
    registration: RegistrationResult

    def __post_init__(self) -> None:
        if not isinstance(self.source_artifact, SourceArtifact):
            raise ArtifactDispatchError(
                "source_artifact must be a SourceArtifact"
            )
        if not self.source_artifact.verify_integrity():
            raise ArtifactDispatchError(
                "source artifact integrity verification failed"
            )
        if not isinstance(self.classification, ArtifactClassification):
            raise ArtifactDispatchError(
                "classification must be an ArtifactClassification"
            )
        if not isinstance(self.registration, RegistrationResult):
            raise ArtifactDispatchError(
                "registration must be a RegistrationResult"
            )

        if self.classification is ArtifactClassification.JSON:
            if not isinstance(self.parsed_artifact, ParsedJsonArtifact):
                raise ArtifactDispatchError(
                    "JSON classifications require ParsedJsonArtifact"
                )
        elif self.classification is ArtifactClassification.M15_VECTOR:
            if not isinstance(self.parsed_artifact, M15VectorArtifact):
                raise ArtifactDispatchError(
                    "M15 vector classifications require M15VectorArtifact"
                )
        elif self.parsed_artifact is not None:
            raise ArtifactDispatchError(
                "unparsed classifications must not contain parsed artifacts"
            )

        if self.parsed_artifact is not None:
            parsed_source = self.parsed_artifact.source_artifact
            if parsed_source is not self.source_artifact:
                raise ArtifactDispatchError(
                    "parsed artifact must reference the same source artifact"
                )
        elif (
            self.registration.status
            is not RegistrationStatus.NOT_APPLICABLE
        ):
            raise ArtifactDispatchError(
                "unparsed classifications must be registry-not-applicable"
            )

        expected_classification = _classification_for_source(
            self.source_artifact,
            parsed_artifact=self.parsed_artifact,
        )
        if self.classification is not expected_classification:
            raise ArtifactDispatchError(
                "classification does not match the source container"
            )

    @property
    def content_sha256(self) -> str:
        """Return the digest of the original, unchanged source bytes."""

        return self.source_artifact.content_sha256

    @property
    def compatibility_record(self) -> CompatibilityRecord | None:
        """Return the exact registry record when registration succeeded."""

        return self.registration.compatibility_record

def _classification_for_source(
    source: SourceArtifact,
    *,
    parsed_artifact: ParsedArtifact | None,
) -> ArtifactClassification:
    if isinstance(parsed_artifact, ParsedJsonArtifact):
        return ArtifactClassification.JSON
    if isinstance(parsed_artifact, M15VectorArtifact):
        return ArtifactClassification.M15_VECTOR

    container = source.detected_container_format
    if container is SourceContainerFormat.EMPTY:
        return ArtifactClassification.EMPTY
    if container is SourceContainerFormat.UTF8_TEXT:
        return ArtifactClassification.UTF8_TEXT
    if container is SourceContainerFormat.ZIP:
        return ArtifactClassification.ZIP
    if container is SourceContainerFormat.BINARY:
        return ArtifactClassification.BINARY
    if container is SourceContainerFormat.JSON_CANDIDATE:
        raise ArtifactDispatchError(
            "JSON candidates must be parsed before classification"
        )
    raise ArtifactDispatchError("unsupported source container format")


def _not_applicable_registration() -> RegistrationResult:
    return RegistrationResult(
        status=RegistrationStatus.NOT_APPLICABLE,
        identifier_field=None,
        declared_identifier=None,
        declared_kind=None,
        compatibility_record=None,
    )


def _registered_result(
    record: CompatibilityRecord,
    *,
    declared_kind: str | None,
) -> RegistrationResult:
    return RegistrationResult(
        status=RegistrationStatus.REGISTERED,
        identifier_field=record.identifier_field,
        declared_identifier=record.identifier,
        declared_kind=declared_kind,
        compatibility_record=record,
    )


def _json_registration(
    parsed: ParsedJsonArtifact,
) -> RegistrationResult:
    missing = object()
    schema_value: JsonValue | object = parsed.root.get(
        "schema",
        missing,
    )
    if schema_value is missing:
        return RegistrationResult(
            status=RegistrationStatus.MISSING_IDENTIFIER,
            identifier_field=IdentifierField.SCHEMA,
            declared_identifier=None,
            declared_kind=parsed.declared_kind,
            compatibility_record=None,
        )
    if not isinstance(schema_value, str):
        return RegistrationResult(
            status=RegistrationStatus.INVALID_IDENTIFIER,
            identifier_field=IdentifierField.SCHEMA,
            declared_identifier=None,
            declared_kind=parsed.declared_kind,
            compatibility_record=None,
        )

    try:
        record = resolve_compatibility_record(
            schema_value,
            declared_kind=parsed.declared_kind,
            identifier_field=IdentifierField.SCHEMA,
        )
    except UnknownArtifactIdentifierError:
        return RegistrationResult(
            status=RegistrationStatus.UNKNOWN_IDENTIFIER,
            identifier_field=IdentifierField.SCHEMA,
            declared_identifier=schema_value,
            declared_kind=parsed.declared_kind,
            compatibility_record=None,
        )
    except UnsupportedArtifactKindError as exc:
        return RegistrationResult(
            status=RegistrationStatus.UNSUPPORTED_KIND,
            identifier_field=IdentifierField.SCHEMA,
            declared_identifier=schema_value,
            declared_kind=parsed.declared_kind,
            compatibility_record=None,
            expected_kinds=exc.expected_kinds,
        )
    return _registered_result(
        record,
        declared_kind=parsed.declared_kind,
    )


def _vector_registration(
    parsed: M15VectorArtifact,
) -> RegistrationResult:
    record = resolve_compatibility_record(
        parsed.format_identifier,
        identifier_field=IdentifierField.FORMAT_VERSION,
    )
    return _registered_result(record, declared_kind=None)


def _declares_vector_format(source: SourceArtifact) -> bool:
    try:
        text = source.raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    lines = text.splitlines()
    if not lines:
        return False
    return lines[0].startswith("# format_version=")

def dispatch_artifact(source: SourceArtifact) -> DispatchedArtifact:
    """Classify and bind one source without executing artifact content."""

    if not isinstance(source, SourceArtifact):
        raise ArtifactDispatchError("source must be a SourceArtifact")
    if not source.verify_integrity():
        raise ArtifactDispatchError(
            "source artifact integrity verification failed"
        )

    if (
        source.detected_container_format
        is SourceContainerFormat.JSON_CANDIDATE
    ):
        parsed_json = parse_json_artifact(source)
        return DispatchedArtifact(
            source_artifact=source,
            classification=ArtifactClassification.JSON,
            parsed_artifact=parsed_json,
            registration=_json_registration(parsed_json),
        )

    if (
        source.detected_container_format
        is SourceContainerFormat.UTF8_TEXT
        and _declares_vector_format(source)
    ):
        parsed_vector = parse_m15_vector(source)
        return DispatchedArtifact(
            source_artifact=source,
            classification=ArtifactClassification.M15_VECTOR,
            parsed_artifact=parsed_vector,
            registration=_vector_registration(parsed_vector),
        )

    return DispatchedArtifact(
        source_artifact=source,
        classification=_classification_for_source(
            source,
            parsed_artifact=None,
        ),
        parsed_artifact=None,
        registration=_not_applicable_registration(),
    )
