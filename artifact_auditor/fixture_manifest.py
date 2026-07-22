"""Parser and immutable model for the canonical fixture manifest."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Final

from parsers.json_artifact import (
    JsonObject,
    JsonValue,
    ParsedJsonArtifact,
    parse_json_artifact,
)
from parsers.source_artifact import SourceArtifact
from schemas.registry import MeasurementContour, ObservatoryMode


__all__ = [
    "CANONICAL_FIXTURE_MANIFEST_OWNER",
    "CANONICAL_FIXTURE_MANIFEST_TYPE",
    "CANONICAL_FIXTURE_MANIFEST_VERSION",
    "CanonicalFixtureManifest",
    "CanonicalFixtureRecord",
    "FixtureIdentificationBasis",
    "FixtureManifestError",
    "RawDigestContract",
    "parse_canonical_fixture_manifest",
]


CANONICAL_FIXTURE_MANIFEST_TYPE: Final = "canonical_fixture_manifest"
CANONICAL_FIXTURE_MANIFEST_VERSION: Final = "1"
CANONICAL_FIXTURE_MANIFEST_OWNER: Final = "FRP Trace Observatory"
_FIXTURE_ORDER: Final = "fixture_path_lexicographic"
_COPY_REQUIREMENT: Final = "unchanged_upstream_bytes"
_RAW_DIGEST_ALGORITHM: Final = "sha256"
_RAW_DIGEST_SCOPE: Final = "raw_source_bytes"
_RAW_DIGEST_ORIGIN: Final = "observatory_calculated"
_SHA256_HEX_LENGTH: Final = 64
_LOWERCASE_HEX: Final = frozenset("0123456789abcdef")

_ROOT_FIELDS: Final = frozenset(
    {
        "manifest_type",
        "manifest_version",
        "manifest_owner",
        "upstream_repository",
        "upstream_release",
        "upstream_milestone",
        "fixture_order",
        "fixture_count",
        "raw_digest_contract",
        "copy_requirement",
        "fixtures",
    }
)
_RAW_DIGEST_FIELDS: Final = frozenset(
    {
        "algorithm",
        "scope",
        "origin",
    }
)
_FIXTURE_FIELDS: Final = frozenset(
    {
        "fixture_path",
        "source_filename",
        "upstream_source_path",
        "upstream_schema_identifier",
        "upstream_schema_version",
        "upstream_kind",
        "identification_basis",
        "producer_path",
        "producer_version",
        "validator_path",
        "measurement_contour",
        "observatory_modes",
        "byte_length",
        "raw_source_sha256",
    }
)


class FixtureIdentificationBasis(StrEnum):
    """Identity evidence recorded for one canonical fixture."""

    EMBEDDED_SCHEMA_AND_RAW_DIGEST = (
        "embedded_schema_identifier_and_raw_source_digest"
    )
    EXACT_PATH_AND_RAW_DIGEST = (
        "exact_upstream_path_and_raw_source_digest"
    )


class FixtureManifestError(ValueError):
    """Raised when the canonical fixture manifest is invalid."""

    def __init__(
        self,
        message: str,
        *,
        json_path: str = "$",
    ) -> None:
        super().__init__(f"{json_path}: {message}")
        self.message = message
        self.json_path = json_path


def _validate_text(
    value: str,
    field_name: str,
    *,
    allow_whitespace: bool = True,
) -> None:
    if not isinstance(value, str):
        raise FixtureManifestError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise FixtureManifestError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise FixtureManifestError(f"{field_name} must not contain NUL")
    if not allow_whitespace and any(
        character.isspace() for character in value
    ):
        raise FixtureManifestError(
            f"{field_name} must not contain whitespace"
        )


def _validate_optional_text(
    value: str | None,
    field_name: str,
    *,
    allow_whitespace: bool = True,
) -> None:
    if value is not None:
        _validate_text(
            value,
            field_name,
            allow_whitespace=allow_whitespace,
        )


def _validate_relative_path(
    value: str | None,
    field_name: str,
    *,
    required: bool,
) -> None:
    if value is None:
        if required:
            raise FixtureManifestError(f"{field_name} is required")
        return
    _validate_text(value, field_name)
    if value.startswith("/") or "\\" in value:
        raise FixtureManifestError(
            f"{field_name} must be a relative POSIX path"
        )
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise FixtureManifestError(
            f"{field_name} must not contain empty or traversal segments"
        )


def _validate_source_filename(value: str) -> None:
    _validate_text(value, "source_filename")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise FixtureManifestError(
            "source_filename must contain one filename"
        )


def _validate_positive_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FixtureManifestError(f"{field_name} must be an integer")
    if value <= 0:
        raise FixtureManifestError(f"{field_name} must be positive")


def _validate_sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise FixtureManifestError(f"{field_name} must be a string")
    if (
        len(value) != _SHA256_HEX_LENGTH
        or any(character not in _LOWERCASE_HEX for character in value)
    ):
        raise FixtureManifestError(
            f"{field_name} must be 64 lowercase hexadecimal characters"
        )


def _require_exact_fields(
    value: Mapping[str, JsonValue],
    expected_fields: frozenset[str],
    *,
    json_path: str,
) -> None:
    observed_fields = frozenset(value)
    if observed_fields == expected_fields:
        return
    missing = tuple(sorted(expected_fields - observed_fields))
    unexpected = tuple(sorted(observed_fields - expected_fields))
    details: list[str] = []
    if missing:
        details.append(f"missing fields: {missing!r}")
    if unexpected:
        details.append(f"unexpected fields: {unexpected!r}")
    raise FixtureManifestError(
        "; ".join(details),
        json_path=json_path,
    )


def _require_mapping(
    value: JsonValue,
    *,
    json_path: str,
) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise FixtureManifestError(
            "value must be an object",
            json_path=json_path,
        )
    return value


def _require_array(
    value: JsonValue,
    *,
    json_path: str,
) -> tuple[JsonValue, ...]:
    if not isinstance(value, tuple):
        raise FixtureManifestError(
            "value must be an array",
            json_path=json_path,
        )
    return value


def _require_string(
    value: JsonValue,
    *,
    json_path: str,
) -> str:
    if not isinstance(value, str):
        raise FixtureManifestError(
            "value must be a string",
            json_path=json_path,
        )
    return value


def _optional_string(
    value: JsonValue,
    *,
    json_path: str,
) -> str | None:
    if value is None:
        return None
    return _require_string(value, json_path=json_path)


def _require_integer(
    value: JsonValue,
    *,
    json_path: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FixtureManifestError(
            "value must be an integer",
            json_path=json_path,
        )
    return value


@dataclass(frozen=True, slots=True)
class RawDigestContract:
    """Digest rules for the unchanged canonical fixture bytes."""

    algorithm: str
    scope: str
    origin: str

    def __post_init__(self) -> None:
        if self.algorithm != _RAW_DIGEST_ALGORITHM:
            raise FixtureManifestError(
                f"algorithm must be {_RAW_DIGEST_ALGORITHM!r}"
            )
        if self.scope != _RAW_DIGEST_SCOPE:
            raise FixtureManifestError(
                f"scope must be {_RAW_DIGEST_SCOPE!r}"
            )
        if self.origin != _RAW_DIGEST_ORIGIN:
            raise FixtureManifestError(
                f"origin must be {_RAW_DIGEST_ORIGIN!r}"
            )


@dataclass(frozen=True, slots=True)
class CanonicalFixtureRecord:
    """One immutable upstream-to-Observatory fixture association."""

    fixture_path: str
    source_filename: str
    upstream_source_path: str
    upstream_schema_identifier: str | None
    upstream_schema_version: str | None
    upstream_kind: str | None
    identification_basis: FixtureIdentificationBasis
    producer_path: str | None
    producer_version: str | None
    validator_path: str | None
    measurement_contour: MeasurementContour
    observatory_modes: tuple[ObservatoryMode, ...]
    byte_length: int
    raw_source_sha256: str

    def __post_init__(self) -> None:
        _validate_relative_path(
            self.fixture_path,
            "fixture_path",
            required=True,
        )
        if not self.fixture_path.startswith("fixtures/"):
            raise FixtureManifestError(
                "fixture_path must be below fixtures/"
            )
        _validate_source_filename(self.source_filename)
        _validate_relative_path(
            self.upstream_source_path,
            "upstream_source_path",
            required=True,
        )
        if PurePosixPath(self.fixture_path).name != self.source_filename:
            raise FixtureManifestError(
                "source_filename must match the fixture path basename"
            )
        if (
            PurePosixPath(self.upstream_source_path).name
            != self.source_filename
        ):
            raise FixtureManifestError(
                "source_filename must match the upstream path basename"
            )

        _validate_optional_text(
            self.upstream_schema_identifier,
            "upstream_schema_identifier",
            allow_whitespace=False,
        )
        _validate_optional_text(
            self.upstream_schema_version,
            "upstream_schema_version",
            allow_whitespace=False,
        )
        _validate_optional_text(
            self.upstream_kind,
            "upstream_kind",
            allow_whitespace=False,
        )
        if not isinstance(
            self.identification_basis,
            FixtureIdentificationBasis,
        ):
            raise FixtureManifestError(
                "identification_basis must be a FixtureIdentificationBasis"
            )

        if (
            self.identification_basis
            is FixtureIdentificationBasis.EMBEDDED_SCHEMA_AND_RAW_DIGEST
        ):
            if (
                self.upstream_schema_identifier is None
                or self.upstream_schema_version is None
            ):
                raise FixtureManifestError(
                    "embedded-schema identification requires identifier "
                    "and version"
                )
            if not self.upstream_schema_identifier.startswith("frp."):
                raise FixtureManifestError(
                    "upstream schema identifier must begin with 'frp.'"
                )
            if not self.upstream_schema_identifier.endswith(
                f".v{self.upstream_schema_version}"
            ):
                raise FixtureManifestError(
                    "upstream schema version must match the identifier"
                )
        elif (
            self.identification_basis
            is FixtureIdentificationBasis.EXACT_PATH_AND_RAW_DIGEST
        ):
            if any(
                value is not None
                for value in (
                    self.upstream_schema_identifier,
                    self.upstream_schema_version,
                    self.upstream_kind,
                )
            ):
                raise FixtureManifestError(
                    "schema-free identification must not assign upstream "
                    "schema metadata"
                )

        _validate_relative_path(
            self.producer_path,
            "producer_path",
            required=False,
        )
        _validate_optional_text(
            self.producer_version,
            "producer_version",
            allow_whitespace=False,
        )
        if self.producer_version is not None and self.producer_path is None:
            raise FixtureManifestError(
                "producer_version requires producer_path"
            )
        _validate_relative_path(
            self.validator_path,
            "validator_path",
            required=False,
        )

        if not isinstance(self.measurement_contour, MeasurementContour):
            raise FixtureManifestError(
                "measurement_contour must be a MeasurementContour"
            )
        if not isinstance(self.observatory_modes, tuple):
            raise FixtureManifestError("observatory_modes must be a tuple")
        if not self.observatory_modes:
            raise FixtureManifestError(
                "observatory_modes must not be empty"
            )
        if any(
            not isinstance(mode, ObservatoryMode)
            for mode in self.observatory_modes
        ):
            raise FixtureManifestError(
                "observatory_modes must contain ObservatoryMode values"
            )
        if len(set(self.observatory_modes)) != len(
            self.observatory_modes
        ):
            raise FixtureManifestError(
                "observatory_modes must be unique"
            )

        _validate_positive_integer(self.byte_length, "byte_length")
        _validate_sha256(
            self.raw_source_sha256,
            "raw_source_sha256",
        )

    def matches_source(self, source: SourceArtifact) -> bool:
        """Check filename, length, digest, and captured-byte integrity."""

        if not isinstance(source, SourceArtifact):
            raise FixtureManifestError(
                "source must be a SourceArtifact"
            )
        return (
            source.verify_integrity()
            and source.source_filename == self.source_filename
            and source.byte_length == self.byte_length
            and source.content_sha256 == self.raw_source_sha256
        )


@dataclass(frozen=True, slots=True)
class CanonicalFixtureManifest:
    """Immutable parsed inventory linked to unchanged manifest bytes."""

    source_artifact: SourceArtifact
    parsed_artifact: ParsedJsonArtifact
    manifest_type: str
    manifest_version: str
    manifest_owner: str
    upstream_repository: str
    upstream_release: str
    upstream_milestone: str
    fixture_order: str
    fixture_count: int
    raw_digest_contract: RawDigestContract
    copy_requirement: str
    fixtures: tuple[CanonicalFixtureRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_artifact, SourceArtifact):
            raise FixtureManifestError(
                "source_artifact must be a SourceArtifact"
            )
        if not self.source_artifact.verify_integrity():
            raise FixtureManifestError(
                "source artifact integrity verification failed"
            )
        if not isinstance(self.parsed_artifact, ParsedJsonArtifact):
            raise FixtureManifestError(
                "parsed_artifact must be a ParsedJsonArtifact"
            )
        if self.parsed_artifact.source_artifact is not self.source_artifact:
            raise FixtureManifestError(
                "parsed artifact must reference the manifest source"
            )

        if self.manifest_type != CANONICAL_FIXTURE_MANIFEST_TYPE:
            raise FixtureManifestError(
                "unsupported canonical fixture manifest type"
            )
        if self.manifest_version != CANONICAL_FIXTURE_MANIFEST_VERSION:
            raise FixtureManifestError(
                "unsupported canonical fixture manifest version"
            )
        if self.manifest_owner != CANONICAL_FIXTURE_MANIFEST_OWNER:
            raise FixtureManifestError(
                "unexpected canonical fixture manifest owner"
            )
        _validate_text(
            self.upstream_repository,
            "upstream_repository",
            allow_whitespace=False,
        )
        _validate_text(
            self.upstream_release,
            "upstream_release",
            allow_whitespace=False,
        )
        _validate_text(
            self.upstream_milestone,
            "upstream_milestone",
            allow_whitespace=False,
        )
        if self.fixture_order != _FIXTURE_ORDER:
            raise FixtureManifestError(
                f"fixture_order must be {_FIXTURE_ORDER!r}"
            )
        _validate_positive_integer(self.fixture_count, "fixture_count")
        if not isinstance(self.raw_digest_contract, RawDigestContract):
            raise FixtureManifestError(
                "raw_digest_contract must be a RawDigestContract"
            )
        if self.copy_requirement != _COPY_REQUIREMENT:
            raise FixtureManifestError(
                f"copy_requirement must be {_COPY_REQUIREMENT!r}"
            )

        if not isinstance(self.fixtures, tuple) or not self.fixtures:
            raise FixtureManifestError(
                "fixtures must be a nonempty tuple"
            )
        if any(
            not isinstance(fixture, CanonicalFixtureRecord)
            for fixture in self.fixtures
        ):
            raise FixtureManifestError(
                "fixtures must contain CanonicalFixtureRecord values"
            )
        if self.fixture_count != len(self.fixtures):
            raise FixtureManifestError(
                "fixture_count does not match fixtures"
            )

        fixture_paths = tuple(
            fixture.fixture_path for fixture in self.fixtures
        )
        if fixture_paths != tuple(sorted(fixture_paths)):
            raise FixtureManifestError(
                "fixtures must follow fixture_path lexicographic order"
            )
        if len(set(fixture_paths)) != len(fixture_paths):
            raise FixtureManifestError("fixture paths must be unique")

        upstream_paths = tuple(
            fixture.upstream_source_path for fixture in self.fixtures
        )
        if len(set(upstream_paths)) != len(upstream_paths):
            raise FixtureManifestError(
                "upstream source paths must be unique"
            )

    @property
    def source_artifact_id(self) -> str:
        """Return the manifest source-artifact identity."""

        return self.source_artifact.source_artifact_id

    @property
    def content_sha256(self) -> str:
        """Return the digest of the unchanged manifest source bytes."""

        return self.source_artifact.content_sha256

    @property
    def schema_free_fixtures(self) -> tuple[CanonicalFixtureRecord, ...]:
        """Return fixtures that have no upstream schema identifier."""

        return tuple(
            fixture
            for fixture in self.fixtures
            if fixture.upstream_schema_identifier is None
        )

    def fixture_for_path(self, fixture_path: str) -> CanonicalFixtureRecord:
        """Return one exact downstream fixture-path record."""

        if not isinstance(fixture_path, str):
            raise FixtureManifestError("fixture_path must be a string")
        for fixture in self.fixtures:
            if fixture.fixture_path == fixture_path:
                return fixture
        raise KeyError(fixture_path)

    def fixture_for_upstream_path(
        self,
        upstream_source_path: str,
    ) -> CanonicalFixtureRecord:
        """Return one exact upstream source-path record."""

        if not isinstance(upstream_source_path, str):
            raise FixtureManifestError(
                "upstream_source_path must be a string"
            )
        for fixture in self.fixtures:
            if fixture.upstream_source_path == upstream_source_path:
                return fixture
        raise KeyError(upstream_source_path)


def _parse_raw_digest_contract(
    value: JsonValue,
    *,
    json_path: str,
) -> RawDigestContract:
    contract = _require_mapping(value, json_path=json_path)
    _require_exact_fields(
        contract,
        _RAW_DIGEST_FIELDS,
        json_path=json_path,
    )
    return RawDigestContract(
        algorithm=_require_string(
            contract["algorithm"],
            json_path=f"{json_path}.algorithm",
        ),
        scope=_require_string(
            contract["scope"],
            json_path=f"{json_path}.scope",
        ),
        origin=_require_string(
            contract["origin"],
            json_path=f"{json_path}.origin",
        ),
    )


def _parse_observatory_modes(
    value: JsonValue,
    *,
    json_path: str,
) -> tuple[ObservatoryMode, ...]:
    raw_modes = _require_array(value, json_path=json_path)
    modes: list[ObservatoryMode] = []
    for index, raw_mode in enumerate(raw_modes):
        item_path = f"{json_path}[{index}]"
        mode_text = _require_string(raw_mode, json_path=item_path)
        try:
            modes.append(ObservatoryMode(mode_text))
        except ValueError as exc:
            raise FixtureManifestError(
                f"unknown Observatory mode: {mode_text!r}",
                json_path=item_path,
            ) from exc
    return tuple(modes)


def _parse_fixture_record(
    value: JsonValue,
    *,
    json_path: str,
) -> CanonicalFixtureRecord:
    record = _require_mapping(value, json_path=json_path)
    _require_exact_fields(
        record,
        _FIXTURE_FIELDS,
        json_path=json_path,
    )

    basis_text = _require_string(
        record["identification_basis"],
        json_path=f"{json_path}.identification_basis",
    )
    try:
        identification_basis = FixtureIdentificationBasis(basis_text)
    except ValueError as exc:
        raise FixtureManifestError(
            f"unknown identification basis: {basis_text!r}",
            json_path=f"{json_path}.identification_basis",
        ) from exc

    contour_text = _require_string(
        record["measurement_contour"],
        json_path=f"{json_path}.measurement_contour",
    )
    try:
        measurement_contour = MeasurementContour(contour_text)
    except ValueError as exc:
        raise FixtureManifestError(
            f"unknown measurement contour: {contour_text!r}",
            json_path=f"{json_path}.measurement_contour",
        ) from exc

    try:
        return CanonicalFixtureRecord(
            fixture_path=_require_string(
                record["fixture_path"],
                json_path=f"{json_path}.fixture_path",
            ),
            source_filename=_require_string(
                record["source_filename"],
                json_path=f"{json_path}.source_filename",
            ),
            upstream_source_path=_require_string(
                record["upstream_source_path"],
                json_path=f"{json_path}.upstream_source_path",
            ),
            upstream_schema_identifier=_optional_string(
                record["upstream_schema_identifier"],
                json_path=f"{json_path}.upstream_schema_identifier",
            ),
            upstream_schema_version=_optional_string(
                record["upstream_schema_version"],
                json_path=f"{json_path}.upstream_schema_version",
            ),
            upstream_kind=_optional_string(
                record["upstream_kind"],
                json_path=f"{json_path}.upstream_kind",
            ),
            identification_basis=identification_basis,
            producer_path=_optional_string(
                record["producer_path"],
                json_path=f"{json_path}.producer_path",
            ),
            producer_version=_optional_string(
                record["producer_version"],
                json_path=f"{json_path}.producer_version",
            ),
            validator_path=_optional_string(
                record["validator_path"],
                json_path=f"{json_path}.validator_path",
            ),
            measurement_contour=measurement_contour,
            observatory_modes=_parse_observatory_modes(
                record["observatory_modes"],
                json_path=f"{json_path}.observatory_modes",
            ),
            byte_length=_require_integer(
                record["byte_length"],
                json_path=f"{json_path}.byte_length",
            ),
            raw_source_sha256=_require_string(
                record["raw_source_sha256"],
                json_path=f"{json_path}.raw_source_sha256",
            ),
        )
    except FixtureManifestError as exc:
        if exc.json_path != "$":
            raise
        raise FixtureManifestError(
            exc.message,
            json_path=json_path,
        ) from exc


def parse_canonical_fixture_manifest(
    source: SourceArtifact,
) -> CanonicalFixtureManifest:
    """Parse the internal manifest without assigning upstream semantics."""

    if not isinstance(source, SourceArtifact):
        raise FixtureManifestError("source must be a SourceArtifact")
    if not source.verify_integrity():
        raise FixtureManifestError(
            "source artifact integrity verification failed"
        )

    parsed = parse_json_artifact(source)
    root: JsonObject = parsed.root
    _require_exact_fields(root, _ROOT_FIELDS, json_path="$")

    fixtures_value = _require_array(
        root["fixtures"],
        json_path="$.fixtures",
    )
    fixtures = tuple(
        _parse_fixture_record(
            fixture,
            json_path=f"$.fixtures[{index}]",
        )
        for index, fixture in enumerate(fixtures_value)
    )

    return CanonicalFixtureManifest(
        source_artifact=source,
        parsed_artifact=parsed,
        manifest_type=_require_string(
            root["manifest_type"],
            json_path="$.manifest_type",
        ),
        manifest_version=_require_string(
            root["manifest_version"],
            json_path="$.manifest_version",
        ),
        manifest_owner=_require_string(
            root["manifest_owner"],
            json_path="$.manifest_owner",
        ),
        upstream_repository=_require_string(
            root["upstream_repository"],
            json_path="$.upstream_repository",
        ),
        upstream_release=_require_string(
            root["upstream_release"],
            json_path="$.upstream_release",
        ),
        upstream_milestone=_require_string(
            root["upstream_milestone"],
            json_path="$.upstream_milestone",
        ),
        fixture_order=_require_string(
            root["fixture_order"],
            json_path="$.fixture_order",
        ),
        fixture_count=_require_integer(
            root["fixture_count"],
            json_path="$.fixture_count",
        ),
        raw_digest_contract=_parse_raw_digest_contract(
            root["raw_digest_contract"],
            json_path="$.raw_digest_contract",
        ),
        copy_requirement=_require_string(
            root["copy_requirement"],
            json_path="$.copy_requirement",
        ),
        fixtures=fixtures,
    )
                
        
