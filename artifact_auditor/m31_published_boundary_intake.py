"""Read-only intake for the exact FRP M31 published evidence boundary.

The module captures four digest-bound M31 JSON documents directly from an
upstream FRP checkout.  It verifies their fixed identities, cross-document
relations, current source provenance, and the ten provenance members retained
inside the immutable M30 archive.  It never executes upstream content,
extracts archive members, normalizes published metrics, or writes upstream.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final

from parsers.json_artifact import (
    JsonArtifactError,
    ParsedJsonArtifact,
    parse_json_artifact,
)
from parsers.source_artifact import (
    SourceArtifact,
    SourceArtifactError,
    SourceContainerFormat,
    capture_source_bytes,
)


__all__ = [
    "FRP_M30_ARCHIVE_BYTES",
    "FRP_M30_ARCHIVE_PATH",
    "FRP_M30_ARCHIVE_SHA256",
    "M31_PUBLISHED_DOCUMENT_IDENTITIES",
    "M31_PUBLISHED_REGISTRY_REVISION",
    "M31PublishedBoundaryError",
    "M31PublishedBoundaryValidation",
    "M31PublishedDocument",
    "M31PublishedDocumentIdentity",
    "M31PublishedDocumentRole",
    "M31PublishedProvenanceSource",
    "validate_m31_published_boundary",
]


M31_PUBLISHED_REGISTRY_REVISION: Final = "m31-published-boundary-v1"
FRP_M30_ARCHIVE_PATH: Final = (
    "artifacts/m30/packages/frp-v3.2.0-m30-archival-release.tar.gz"
)
FRP_M30_ARCHIVE_BYTES: Final = 10_189_989
FRP_M30_ARCHIVE_SHA256: Final = (
    "05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa"
)
_FRP_M30_ARCHIVE_PREFIX: Final = (
    "Fractal-Resonance-Processor-FRP-v3.2.0"
)
_HEX_DIGITS: Final = frozenset("0123456789abcdef")


class M31PublishedBoundaryError(ValueError):
    """Raised when the exact M31 publication boundary is not preserved."""


class M31PublishedDocumentRole(StrEnum):
    """Fixed roles of the four upstream M31 publication documents."""

    FORMAL_SCHEMA = "formal_schema"
    EVIDENCE = "evidence"
    MANIFEST = "manifest"
    QUALIFICATION = "qualification"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise M31PublishedBoundaryError(message)


def _validate_token(value: object, field: str) -> str:
    _require(
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and not any(character.isspace() for character in value),
        f"{field} must be a nonempty machine token",
    )
    return value


def _validate_relative_path(value: object, field: str) -> str:
    text = _validate_token(value, field)
    _require(
        "\\" not in text and "\x00" not in text,
        f"{field} must be a relative POSIX path",
    )
    path = PurePosixPath(text)
    _require(
        not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in text.split("/")),
        f"{field} must be a safe relative POSIX path",
    )
    return text


def _validate_sha256(value: object, field: str) -> str:
    _require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX_DIGITS for character in value),
        f"{field} must be lowercase hexadecimal SHA-256",
    )
    return value


def _validate_positive_integer(value: object, field: str) -> int:
    _require(
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0,
        f"{field} must be a positive integer",
    )
    return value


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class M31PublishedDocumentIdentity:
    """One exact upstream path, byte identity, and JSON identity."""

    role: M31PublishedDocumentRole
    source_path: str
    identifier_field: str
    identifier_value: str
    kind: str | None
    byte_length: int
    raw_sha256: str

    def __post_init__(self) -> None:
        _require(
            isinstance(self.role, M31PublishedDocumentRole),
            "role must be M31PublishedDocumentRole",
        )
        _validate_relative_path(self.source_path, "source_path")
        _validate_token(self.identifier_field, "identifier_field")
        _require(
            self.identifier_field in {"$id", "schema"},
            "identifier_field must be $id or schema",
        )
        _require(
            isinstance(self.identifier_value, str)
            and bool(self.identifier_value)
            and self.identifier_value == self.identifier_value.strip(),
            "identifier_value must be a nonempty string",
        )
        if self.kind is not None:
            _validate_token(self.kind, "kind")
        _validate_positive_integer(self.byte_length, "byte_length")
        _validate_sha256(self.raw_sha256, "raw_sha256")
        if self.role is M31PublishedDocumentRole.FORMAL_SCHEMA:
            _require(
                self.identifier_field == "$id" and self.kind is None,
                "formal schema identity must use only $id",
            )
        else:
            _require(
                self.identifier_field == "schema" and self.kind is not None,
                "published instance identity must use schema and kind",
            )


M31_PUBLISHED_DOCUMENT_IDENTITIES: Final = (
    M31PublishedDocumentIdentity(
        role=M31PublishedDocumentRole.FORMAL_SCHEMA,
        source_path=(
            "schemas/m31/"
            "frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json"
        ),
        identifier_field="$id",
        identifier_value=(
            "https://frp.example/schemas/m31/"
            "frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json"
        ),
        kind=None,
        byte_length=1468,
        raw_sha256=(
            "53d79d45d70753ccd24c3dc4c97af6fee481f86a9d7cdca7ef78b486c76479f7"
        ),
    ),
    M31PublishedDocumentIdentity(
        role=M31PublishedDocumentRole.EVIDENCE,
        source_path=(
            "artifacts/m31/evidence/"
            "m31-phase-interference-active-zero-thermal-evidence.json"
        ),
        identifier_field="schema",
        identifier_value=(
            "frp.m31.phase_interference_active_zero_thermal_evidence.v1"
        ),
        kind="phase_interference_active_zero_thermal_evidence",
        byte_length=39993,
        raw_sha256=(
            "bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42"
        ),
    ),
    M31PublishedDocumentIdentity(
        role=M31PublishedDocumentRole.MANIFEST,
        source_path=(
            "artifacts/m31/manifests/"
            "m31-phase-interference-active-zero-thermal-evidence-manifest.json"
        ),
        identifier_field="schema",
        identifier_value=(
            "frp.m31.phase_interference_active_zero_thermal_evidence_manifest.v1"
        ),
        kind="phase_interference_active_zero_thermal_evidence_manifest",
        byte_length=828,
        raw_sha256=(
            "80f0841d0041cd22c2f76175b6139e601aede7b69823356ae1fefbce5f793e7c"
        ),
    ),
    M31PublishedDocumentIdentity(
        role=M31PublishedDocumentRole.QUALIFICATION,
        source_path=(
            "artifacts/m31/qualification/"
            "m31-phase-interference-active-zero-thermal-evidence-qualification.json"
        ),
        identifier_field="schema",
        identifier_value=(
            "frp.m31.phase_interference_active_zero_thermal_evidence_qualification.v1"
        ),
        kind="phase_interference_active_zero_thermal_evidence_qualification",
        byte_length=1512,
        raw_sha256=(
            "4c2446f954e01ec0aa37cc6c0fc70cf4a87ec565c450628e31b0efcac9160224"
        ),
    ),
)


_IDENTITY_BY_ROLE: Final = {
    identity.role: identity
    for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
}


@dataclass(frozen=True, slots=True)
class M31PublishedDocument:
    """One immutable captured and strictly parsed M31 document."""

    identity: M31PublishedDocumentIdentity
    source_artifact: SourceArtifact
    parsed_artifact: ParsedJsonArtifact

    def __post_init__(self) -> None:
        _require(
            isinstance(self.identity, M31PublishedDocumentIdentity),
            "identity must be M31PublishedDocumentIdentity",
        )
        _require(
            _IDENTITY_BY_ROLE.get(self.identity.role) is self.identity,
            "identity must be the canonical role identity",
        )
        _require(
            isinstance(self.source_artifact, SourceArtifact)
            and self.source_artifact.verify_integrity(),
            "source_artifact must preserve captured integrity",
        )
        _require(
            self.source_artifact.source_path == self.identity.source_path,
            "captured source path differs from the identity",
        )
        _require(
            self.source_artifact.source_filename
            == PurePosixPath(self.identity.source_path).name,
            "captured source filename differs from the identity",
        )
        _require(
            self.source_artifact.byte_length == self.identity.byte_length
            and self.source_artifact.content_sha256 == self.identity.raw_sha256,
            "captured raw-byte identity differs from the registration",
        )
        _require(
            self.source_artifact.detected_container_format
            is SourceContainerFormat.JSON_CANDIDATE,
            "M31 document must be a strict JSON candidate",
        )
        _require(
            isinstance(self.parsed_artifact, ParsedJsonArtifact)
            and self.parsed_artifact.source_artifact is self.source_artifact,
            "parsed artifact must reference the captured source",
        )
        observed_identifier = self.parsed_artifact.root.get(
            self.identity.identifier_field
        )
        _require(
            observed_identifier == self.identity.identifier_value,
            "published JSON identifier differs from the registration",
        )
        if self.identity.kind is not None:
            _require(
                self.parsed_artifact.declared_kind == self.identity.kind,
                "published kind differs from the registration",
            )

    @property
    def root(self) -> Mapping[str, object]:
        """Return the immutable strict JSON root."""

        return self.parsed_artifact.root

    @property
    def raw_bytes(self) -> bytes:
        """Return unchanged upstream bytes."""

        return self.source_artifact.raw_bytes


@dataclass(frozen=True, slots=True)
class M31PublishedProvenanceSource:
    """One current upstream source bound by the M31 evidence."""

    source_artifact: SourceArtifact
    m30_archive_member_verified: bool
    role: str | None

    def __post_init__(self) -> None:
        _require(
            isinstance(self.source_artifact, SourceArtifact)
            and self.source_artifact.verify_integrity(),
            "provenance source must preserve captured integrity",
        )
        _require(
            isinstance(self.source_artifact.source_path, str),
            "provenance source path must be recorded",
        )
        _require(
            isinstance(self.m30_archive_member_verified, bool),
            "m30_archive_member_verified must be boolean",
        )
        if self.role is not None:
            _validate_token(self.role, "role")

    @property
    def source_path(self) -> str:
        """Return the exact recorded upstream path."""

        value = self.source_artifact.source_path
        _require(isinstance(value, str), "provenance path is absent")
        return value


@dataclass(frozen=True, slots=True)
class M31PublishedBoundaryValidation:
    """Complete read-only validation of the four-document M31 boundary."""

    registry_revision: str
    loaded_at: datetime
    documents: tuple[M31PublishedDocument, ...]
    provenance_sources: tuple[M31PublishedProvenanceSource, ...]
    m30_archive_sha256: str
    m30_archive_member_count: int

    def __post_init__(self) -> None:
        _require(
            self.registry_revision == M31_PUBLISHED_REGISTRY_REVISION,
            "registry revision mismatch",
        )
        _require(
            isinstance(self.loaded_at, datetime)
            and self.loaded_at.tzinfo is not None
            and self.loaded_at.utcoffset() == timedelta(0),
            "loaded_at must be timezone-aware UTC",
        )
        _require(
            isinstance(self.documents, tuple)
            and tuple(document.identity for document in self.documents)
            == M31_PUBLISHED_DOCUMENT_IDENTITIES,
            "published document order or inventory mismatch",
        )
        _require(
            isinstance(self.provenance_sources, tuple)
            and len(self.provenance_sources) == 12
            and all(
                isinstance(source, M31PublishedProvenanceSource)
                for source in self.provenance_sources
            ),
            "provenance source inventory mismatch",
        )
        _require(
            all(
                document.source_artifact.loaded_at == self.loaded_at
                for document in self.documents
            )
            and all(
                source.source_artifact.loaded_at == self.loaded_at
                for source in self.provenance_sources
            ),
            "published source timestamps must share loaded_at",
        )
        paths = tuple(source.source_path for source in self.provenance_sources)
        _require(
            len(set(paths)) == len(paths),
            "provenance source paths must be unique",
        )
        _require(
            self.m30_archive_sha256 == FRP_M30_ARCHIVE_SHA256,
            "M30 archive digest mismatch",
        )
        _require(
            self.m30_archive_member_count == 10,
            "M30 archive member count mismatch",
        )
        _require(
            sum(
                source.m30_archive_member_verified
                for source in self.provenance_sources
            )
            == self.m30_archive_member_count,
            "verified archive-member relation mismatch",
        )

    def document(
        self,
        role: M31PublishedDocumentRole,
    ) -> M31PublishedDocument:
        """Return one exact document by canonical role."""

        _require(
            isinstance(role, M31PublishedDocumentRole),
            "role must be M31PublishedDocumentRole",
        )
        for document in self.documents:
            if document.identity.role is role:
                return document
        raise M31PublishedBoundaryError(
            f"canonical M31 document is absent: {role.value}"
        )

    @property
    def total_document_bytes(self) -> int:
        """Return the total raw bytes of the four publication documents."""

        return sum(
            document.source_artifact.byte_length
            for document in self.documents
        )


def _root_path(value: str | Path) -> Path:
    _require(
        isinstance(value, (str, Path)),
        "upstream_root must be a string or Path",
    )
    try:
        path = Path(value)
        _require(
            not path.is_symlink() and path.is_dir(),
            "upstream_root must be a regular directory",
        )
        return path.resolve(strict=True)
    except OSError as exc:
        raise M31PublishedBoundaryError(
            "unable to resolve upstream_root"
        ) from exc


def _read_regular(root: Path, relative: str) -> bytes:
    _validate_relative_path(relative, "source path")
    target = root.joinpath(*PurePosixPath(relative).parts)
    try:
        _require(
            not target.is_symlink() and target.is_file(),
            f"required regular upstream file is missing: {relative}",
        )
        resolved = target.resolve(strict=True)
        _require(
            resolved.is_relative_to(root),
            f"upstream source escapes repository root: {relative}",
        )
        return target.read_bytes()
    except OSError as exc:
        raise M31PublishedBoundaryError(
            f"unable to read upstream source: {relative}"
        ) from exc


def _capture_document(
    root: Path,
    identity: M31PublishedDocumentIdentity,
    timestamp: datetime,
) -> M31PublishedDocument:
    raw = _read_regular(root, identity.source_path)
    _require(
        len(raw) == identity.byte_length
        and hashlib.sha256(raw).hexdigest() == identity.raw_sha256,
        f"raw identity mismatch: {identity.source_path}",
    )
    _require(
        raw.endswith(b"\n") and not raw.endswith(b"\n\n"),
        f"terminal newline mismatch: {identity.source_path}",
    )
    source = capture_source_bytes(
        raw,
        source_filename=PurePosixPath(identity.source_path).name,
        source_path=identity.source_path,
        loaded_at=timestamp,
    )
    parsed = parse_json_artifact(source)
    return M31PublishedDocument(
        identity=identity,
        source_artifact=source,
        parsed_artifact=parsed,
    )


def _identity_entry(
    role: M31PublishedDocumentRole,
) -> dict[str, object]:
    identity = _IDENTITY_BY_ROLE[role]
    return {
        "byte_count": identity.byte_length,
        "path": identity.source_path,
        "raw_sha256": identity.raw_sha256,
    }


def _validate_documents(
    documents: tuple[M31PublishedDocument, ...],
) -> list[dict[str, object]]:
    by_role = {
        document.identity.role: _plain(document.root)
        for document in documents
    }
    schema = by_role[M31PublishedDocumentRole.FORMAL_SCHEMA]
    evidence = by_role[M31PublishedDocumentRole.EVIDENCE]
    manifest = by_role[M31PublishedDocumentRole.MANIFEST]
    qualification = by_role[M31PublishedDocumentRole.QUALIFICATION]
    _require(
        all(isinstance(value, dict) for value in by_role.values()),
        "published document root type mismatch",
    )

    evidence_schema = (
        "frp.m31.phase_interference_active_zero_thermal_evidence.v1"
    )
    _require(
        schema.get("$schema")
        == "https://json-schema.org/draft/2020-12/schema"
        and schema.get("type") == "object"
        and schema.get("additionalProperties") is False
        and schema.get("properties", {})
        .get("schema", {})
        .get("const")
        == evidence_schema,
        "formal schema boundary mismatch",
    )
    required = {
        "schema",
        "version",
        "milestone",
        "kind",
        "status",
        "core",
        "active_zero_execution_evidence",
        "historical_thermal_experiment",
        "current_comparative_thermal_contours",
        "evidence_boundaries",
        "observatory_publication_contract",
        "provenance",
    }
    _require(
        set(evidence) == required
        and set(schema.get("required", [])) == required,
        "evidence field inventory mismatch",
    )
    _require(
        evidence.get("schema") == evidence_schema
        and evidence.get("version") == "1.0.0"
        and evidence.get("milestone") == "M31"
        and evidence.get("status") == "PASS",
        "evidence identity mismatch",
    )

    core = evidence.get("core", {})
    _require(
        core.get("balanced_ternary_notation") == "-1/0/1"
        and core.get("semantic_values") == [-1, 0, 1]
        and core.get("active_neutral_state") == 0
        and core.get("zero_role") == "active_computational_state"
        and core.get("opposite_transition_routes")
        == [[-1, 0, 1], [1, 0, -1]]
        and core.get("temporal_scheduler_modes") == ["1/7", "7/1"]
        and core.get("service_scheduler_mode") == "free"
        and core.get("classical_bit_addition_primary_mechanism") is False
        and core.get("primary_computational_organization")
        == "retained_relative_phase_interference_and_resonant_selection",
        "processor core boundary mismatch",
    )

    active = evidence.get("active_zero_execution_evidence", {})
    _require(
        active.get("record_count") == 100
        and active.get("cell_observation_count") == 800
        and active.get("active_zero_after_observation_count") == 702
        and active.get("invariant_pass_records") == 100
        and active.get("observed_ternary_domain") == [-1, 0, 1]
        and active.get("retained_transition_counts", {}).get(
            "direct_opposite"
        )
        == 0
        and active.get("event_totals", {}).get("actual_direct_events") == 0
        and active.get("event_totals", {}).get("reserved_state_events") == 0
        and active.get("event_totals", {}).get("queue_overflow_events") == 0,
        "active-zero execution boundary mismatch",
    )
    _require(
        sum(active["scheduler_mode_counts"].values()) == 100
        and sum(active["scheduler_state_counts"].values()) == 100
        and sum(active["retained_transition_counts"].values()) == 800,
        "active-zero aggregate relation mismatch",
    )

    historical = evidence.get("historical_thermal_experiment", {})
    current = evidence.get("current_comparative_thermal_contours", {})
    boundaries = evidence.get("evidence_boundaries", {})
    contract = evidence.get("observatory_publication_contract", {})
    _require(
        historical.get("measurement_class")
        == "release_specific_model_thermal_load"
        and historical.get("physical_temperature_measurement") is False
        and historical.get("winner_assertions") == []
        and len(historical.get("rows", [])) == 4,
        "historical thermal contour mismatch",
    )
    focused = historical.get("focused_binary_ternary_comparison", {})
    _require(
        focused.get(
            "heat_peak_ratio_binary_over_active_neutral_ternary"
        )
        == "15.6923076923"
        and focused.get("heat_peak_relative_reduction_percent_exact")
        == "93.6274509804"
        and focused.get(
            "switch_load_ratio_binary_over_active_neutral_ternary"
        )
        == "4.0",
        "historical focused-comparison mismatch",
    )
    _require(
        current.get("measurement_class")
        == "shared_model_comparative_benchmark"
        and current.get("physical_temperature_measurement") is False
        and current.get("historical_heat_peak_interchangeable") is False
        and current.get("baseline", {}).get("winner_assertions") == []
        and current.get("hardware_sensitivity", {}).get(
            "winner_assertions"
        )
        == [],
        "current comparative contour mismatch",
    )
    _require(
        len(boundaries) == 7
        and all(value is True for value in boundaries.values()),
        "evidence boundary flags mismatch",
    )
    _require(
        contract
        == {
            "direction": "upstream_published_bytes_to_downstream",
            "downstream_metric_normalization": "forbidden",
            "downstream_repository": "FRP-Trace-Observatory",
            "downstream_role": "read_only_validation_and_visualization",
            "downstream_semantic_reimplementation": "forbidden",
            "downstream_source_mutation": "forbidden",
            "downstream_writeback": "forbidden",
            "m29_boundary_confirmed": True,
            "published_contours_must_remain_separate": True,
            "upstream_repository": "FRP",
        },
        "Observatory publication contract mismatch",
    )

    stdout_sha256 = (
        "b18e1affec6dec8029086e923b907c9ae3cb0c50131e4291b31fbd2a4d97cbb6"
    )
    _require(
        manifest.get("version") == "1.0.0"
        and manifest.get("milestone") == "M31"
        and manifest.get("status") == "PASS"
        and manifest.get("source_count") == 12
        and manifest.get("historical_experiment_stdout_sha256")
        == stdout_sha256
        and manifest.get("generated_files")
        == [
            _identity_entry(M31PublishedDocumentRole.FORMAL_SCHEMA),
            _identity_entry(M31PublishedDocumentRole.EVIDENCE),
        ],
        "manifest boundary mismatch",
    )
    checks = qualification.get("checks")
    _require(
        qualification.get("version") == "1.0.0"
        and qualification.get("milestone") == "M31"
        and qualification.get("status") == "PASS"
        and isinstance(checks, dict)
        and len(checks) == 13
        and all(value is True for value in checks.values())
        and qualification.get("outputs")
        == [
            _identity_entry(M31PublishedDocumentRole.FORMAL_SCHEMA),
            _identity_entry(M31PublishedDocumentRole.EVIDENCE),
            _identity_entry(M31PublishedDocumentRole.MANIFEST),
        ],
        "qualification boundary mismatch",
    )

    provenance = evidence.get("provenance")
    _require(
        isinstance(provenance, list)
        and len(provenance) == 12
        and manifest.get("source_count") == len(provenance),
        "provenance inventory mismatch",
    )
    paths = [record.get("path") for record in provenance]
    _require(
        all(isinstance(path, str) for path in paths)
        and len(set(paths)) == len(paths),
        "provenance paths must be unique strings",
    )
    return provenance


def _capture_provenance(
    root: Path,
    provenance: Sequence[dict[str, object]],
    timestamp: datetime,
) -> tuple[
    tuple[M31PublishedProvenanceSource, ...],
    bytes,
    tuple[dict[str, object], ...],
]:
    sources: list[M31PublishedProvenanceSource] = []
    archive_records: list[dict[str, object]] = []
    archive_raw: bytes | None = None
    for record in provenance:
        path = _validate_relative_path(record.get("path"), "provenance path")
        byte_count = _validate_positive_integer(
            record.get("byte_count"),
            "provenance byte_count",
        )
        raw_sha256 = _validate_sha256(
            record.get("raw_sha256"),
            "provenance raw_sha256",
        )
        verified = record.get("m30_archive_member_verified")
        _require(
            isinstance(verified, bool),
            "provenance archive flag must be boolean",
        )
        role = record.get("role")
        _require(
            role is None or isinstance(role, str),
            "provenance role must be a string or absent",
        )
        raw = _read_regular(root, path)
        _require(
            len(raw) == byte_count
            and hashlib.sha256(raw).hexdigest() == raw_sha256,
            f"provenance source identity mismatch: {path}",
        )
        source = capture_source_bytes(
            raw,
            source_filename=PurePosixPath(path).name,
            source_path=path,
            loaded_at=timestamp,
        )
        sources.append(
            M31PublishedProvenanceSource(
                source_artifact=source,
                m30_archive_member_verified=verified,
                role=role,
            )
        )
        if verified:
            archive_records.append(record)
        if path == FRP_M30_ARCHIVE_PATH:
            archive_raw = raw

    _require(
        archive_raw is not None
        and len(archive_raw) == FRP_M30_ARCHIVE_BYTES
        and hashlib.sha256(archive_raw).hexdigest()
        == FRP_M30_ARCHIVE_SHA256,
        "exact M30 archive identity mismatch",
    )
    _require(
        len(archive_records) == 10,
        "verified M30 archive-member inventory mismatch",
    )
    return tuple(sources), archive_raw, tuple(archive_records)


def _verify_archive_members(
    archive_raw: bytes,
    archive_records: Sequence[dict[str, object]],
) -> None:
    try:
        with tarfile.open(
            fileobj=io.BytesIO(archive_raw),
            mode="r:gz",
        ) as archive:
            for record in archive_records:
                path = str(record["path"])
                member_name = f"{_FRP_M30_ARCHIVE_PREFIX}/{path}"
                try:
                    member = archive.getmember(member_name)
                except KeyError as exc:
                    raise M31PublishedBoundaryError(
                        f"provenance member is absent from M30: {path}"
                    ) from exc
                _require(
                    member.isfile()
                    and not member.issym()
                    and not member.islnk(),
                    f"provenance archive member is not regular: {path}",
                )
                handle = archive.extractfile(member)
                _require(
                    handle is not None,
                    f"provenance archive member is unreadable: {path}",
                )
                raw = handle.read()
                _require(
                    len(raw) == record["byte_count"]
                    and hashlib.sha256(raw).hexdigest()
                    == record["raw_sha256"],
                    f"provenance archive bytes mismatch: {path}",
                )
    except (tarfile.TarError, OSError) as exc:
        raise M31PublishedBoundaryError(
            "unable to inspect the exact M30 archive"
        ) from exc


def validate_m31_published_boundary(
    upstream_root: str | Path,
    *,
    loaded_at: datetime | None = None,
) -> M31PublishedBoundaryValidation:
    """Validate and capture the exact read-only FRP M31 publication."""

    root = _root_path(upstream_root)
    timestamp = (
        datetime.now(timezone.utc)
        if loaded_at is None
        else loaded_at
    )
    _require(
        isinstance(timestamp, datetime)
        and timestamp.tzinfo is not None
        and timestamp.utcoffset() is not None,
        "loaded_at must be timezone-aware",
    )
    timestamp = timestamp.astimezone(timezone.utc)
    try:
        documents = tuple(
            _capture_document(root, identity, timestamp)
            for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
        )
        provenance = _validate_documents(documents)
        sources, archive_raw, archive_records = _capture_provenance(
            root,
            provenance,
            timestamp,
        )
        _verify_archive_members(archive_raw, archive_records)
        return M31PublishedBoundaryValidation(
            registry_revision=M31_PUBLISHED_REGISTRY_REVISION,
            loaded_at=timestamp,
            documents=documents,
            provenance_sources=sources,
            m30_archive_sha256=FRP_M30_ARCHIVE_SHA256,
            m30_archive_member_count=len(archive_records),
        )
    except M31PublishedBoundaryError:
        raise
    except (JsonArtifactError, SourceArtifactError) as exc:
        raise M31PublishedBoundaryError(
            f"strict M31 source intake failed: {exc}"
        ) from exc


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the exact FRP M31 published evidence as a strictly "
            "read-only Observatory boundary."
        )
    )
    parser.add_argument("--upstream-root", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate_m31_published_boundary(arguments.upstream_root)
    evidence = result.document(M31PublishedDocumentRole.EVIDENCE)
    evidence_root = _plain(evidence.root)
    print("FRP Observatory M31 published boundary intake: PASS")
    print(f"registry_revision={result.registry_revision}")
    print(f"published_documents={len(result.documents)}")
    print(f"published_document_bytes={result.total_document_bytes}")
    print(f"provenance_sources={len(result.provenance_sources)}")
    print(f"m30_archive_sha256={result.m30_archive_sha256}")
    print(f"m30_archive_members={result.m30_archive_member_count}")
    print(
        "balanced_ternary_notation="
        f"{evidence_root['core']['balanced_ternary_notation']}"
    )
    print(
        "active_zero_observations="
        f"{evidence_root['active_zero_execution_evidence']['active_zero_after_observation_count']}"
    )
    print("metric_normalization=forbidden")
    print("semantic_reimplementation=forbidden")
    print("source_mutation=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
