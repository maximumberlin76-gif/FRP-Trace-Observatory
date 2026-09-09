"""Read-only intake for the exact FRP M32 published trace boundary.

The module captures four digest-bound M32 JSON documents directly from an
upstream FRP checkout. It verifies their fixed identities, cross-document
relations, 29 current source identities, four transcript identity records,
and the deterministic trace invariants retained by the publication. It never
executes upstream content, reads transient workflow artifacts, normalizes
published records, mutates source files, or writes upstream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
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
    "M32_PUBLISHED_DOCUMENT_IDENTITIES",
    "M32_PUBLISHED_REGISTRY_REVISION",
    "M32_PUBLISHED_TRANSCRIPT_IDENTITIES",
    "M32_SOURCE_COMMIT",
    "M32PublishedBoundaryError",
    "M32PublishedBoundaryValidation",
    "M32PublishedDocument",
    "M32PublishedDocumentIdentity",
    "M32PublishedDocumentRole",
    "M32PublishedSourceIdentity",
    "M32PublishedTranscriptIdentity",
    "validate_m32_published_boundary",
]


M32_PUBLISHED_REGISTRY_REVISION: Final = "m32-published-boundary-v1"
M32_SOURCE_COMMIT: Final = (
    "c0bc0fbc2c1c2e500b19d0ba84b3431a813e3941"
)
_HEX_DIGITS: Final = frozenset("0123456789abcdef")
_BUNDLE_PAYLOAD_SHA256: Final = (
    "63b36c1fb29d28a33bb5387d7658c97fc0a51f6823f79dc71382132236685f9b"
)
_MANIFEST_PAYLOAD_SHA256: Final = (
    "a9dd7d470fd094cb1dbb6fa360f6c28bf50d4aae4bf2f1ba34ad223655968c2e"
)
_QUALIFICATION_PAYLOAD_SHA256: Final = (
    "a695ccb3c7f083e219ff6908dfc38e6f4e7ef37fca6da22f40c6303117027c5d"
)


class M32PublishedBoundaryError(ValueError):
    """Raised when the exact M32 publication boundary is not preserved."""


class M32PublishedDocumentRole(StrEnum):
    """Fixed roles of the four upstream M32 publication documents."""

    FORMAL_SCHEMA = "formal_schema"
    TRACE_BUNDLE = "trace_bundle"
    MANIFEST = "manifest"
    QUALIFICATION = "qualification"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise M32PublishedBoundaryError(message)


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


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_digest(value: dict[str, object], field: str) -> str:
    payload = dict(value)
    payload.pop(field, None)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class M32PublishedDocumentIdentity:
    """One exact upstream path, byte identity, and JSON identity."""

    role: M32PublishedDocumentRole
    source_path: str
    identifier_field: str
    identifier_value: str
    kind: str | None
    byte_length: int
    raw_sha256: str

    def __post_init__(self) -> None:
        _require(
            isinstance(self.role, M32PublishedDocumentRole),
            "role must be M32PublishedDocumentRole",
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
        if self.role is M32PublishedDocumentRole.FORMAL_SCHEMA:
            _require(
                self.identifier_field == "$id" and self.kind is None,
                "formal schema identity must use only $id",
            )
        else:
            _require(
                self.identifier_field == "schema" and self.kind is not None,
                "published instance identity must use schema and kind",
            )


M32_PUBLISHED_DOCUMENT_IDENTITIES: Final = (
    M32PublishedDocumentIdentity(
        role=M32PublishedDocumentRole.FORMAL_SCHEMA,
        source_path=(
            "schemas/m32/"
            "frp.m32.deterministic_rtl_trace_bundle.v1.schema.json"
        ),
        identifier_field="$id",
        identifier_value=(
            "https://frp.example/schemas/m32/"
            "frp.m32.deterministic_rtl_trace_bundle.v1.schema.json"
        ),
        kind=None,
        byte_length=34_066,
        raw_sha256=(
            "534db8227218184cac5d1cabb461dd63b1b61a99e0269c98535539ad3f7d7da2"
        ),
    ),
    M32PublishedDocumentIdentity(
        role=M32PublishedDocumentRole.TRACE_BUNDLE,
        source_path=(
            "artifacts/m32/exports/"
            "m32-deterministic-rtl-trace-bundle.json"
        ),
        identifier_field="schema",
        identifier_value="frp.m32.deterministic_rtl_trace_bundle.v1",
        kind="deterministic_rtl_trace_bundle",
        byte_length=412_195,
        raw_sha256=(
            "62d8c1e6d205b9262a5c950883d3259275d5049f7a896ae12956a210cb75b7e0"
        ),
    ),
    M32PublishedDocumentIdentity(
        role=M32PublishedDocumentRole.MANIFEST,
        source_path=(
            "artifacts/m32/manifests/"
            "m32-deterministic-rtl-trace-manifest.json"
        ),
        identifier_field="schema",
        identifier_value="frp.m32.deterministic_rtl_trace_manifest.v1",
        kind="deterministic_rtl_trace_manifest",
        byte_length=7_211,
        raw_sha256=(
            "da011dbc726d6d1fc0b7dbae12afe1e13d8240df64b9474fd0130c94ba005859"
        ),
    ),
    M32PublishedDocumentIdentity(
        role=M32PublishedDocumentRole.QUALIFICATION,
        source_path=(
            "artifacts/m32/qualification/"
            "m32-deterministic-rtl-trace-qualification.json"
        ),
        identifier_field="schema",
        identifier_value=(
            "frp.m32.deterministic_rtl_trace_qualification.v1"
        ),
        kind="deterministic_rtl_trace_qualification",
        byte_length=4_624,
        raw_sha256=(
            "26ec2d3eadd73b490eb023572101bb78cf5d11561ead91b78b1a30e690458273"
        ),
    ),
)


_IDENTITY_BY_ROLE: Final = {
    identity.role: identity
    for identity in M32_PUBLISHED_DOCUMENT_IDENTITIES
}


@dataclass(frozen=True, slots=True)
class M32PublishedDocument:
    """One immutable captured and strictly parsed M32 document."""

    identity: M32PublishedDocumentIdentity
    source_artifact: SourceArtifact
    parsed_artifact: ParsedJsonArtifact

    def __post_init__(self) -> None:
        _require(
            isinstance(self.identity, M32PublishedDocumentIdentity),
            "identity must be M32PublishedDocumentIdentity",
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
            "M32 document must be a strict JSON candidate",
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
class M32PublishedSourceIdentity:
    """One exact current upstream source identity captured read-only."""

    source_path: str
    byte_length: int
    raw_sha256: str
    source_artifact: SourceArtifact

    def __post_init__(self) -> None:
        _validate_relative_path(self.source_path, "source_path")
        _validate_positive_integer(self.byte_length, "byte_length")
        _validate_sha256(self.raw_sha256, "raw_sha256")
        _require(
            isinstance(self.source_artifact, SourceArtifact)
            and self.source_artifact.verify_integrity(),
            "source identity must preserve captured integrity",
        )
        _require(
            self.source_artifact.source_path == self.source_path,
            "captured source path differs from the published identity",
        )
        _require(
            self.source_artifact.source_filename
            == PurePosixPath(self.source_path).name,
            "captured source filename differs from the published identity",
        )
        _require(
            self.source_artifact.byte_length == self.byte_length
            and self.source_artifact.content_sha256 == self.raw_sha256,
            "captured source bytes differ from the published identity",
        )


@dataclass(frozen=True, slots=True)
class M32PublishedTranscriptIdentity:
    """One immutable identity record for a transient M32 transcript."""

    artifact_member_path: str
    byte_length: int
    raw_sha256: str
    replay: int
    scheduler_mode: str

    def __post_init__(self) -> None:
        _validate_relative_path(
            self.artifact_member_path,
            "artifact_member_path",
        )
        _validate_positive_integer(self.byte_length, "byte_length")
        _validate_sha256(self.raw_sha256, "raw_sha256")
        _validate_positive_integer(self.replay, "replay")
        _require(
            self.scheduler_mode in {"7/1", "1/7"},
            "scheduler_mode must be 7/1 or 1/7",
        )


M32_PUBLISHED_TRANSCRIPT_IDENTITIES: Final = (
    M32PublishedTranscriptIdentity(
        artifact_member_path="m32-mode-7-1-full-trace-run-1.log",
        byte_length=105_702,
        raw_sha256=(
            "9517a02cd1ce2c687365f3712a453a9370e505ee4267e151fd05b266977ce915"
        ),
        replay=1,
        scheduler_mode="7/1",
    ),
    M32PublishedTranscriptIdentity(
        artifact_member_path="m32-mode-7-1-full-trace-run-2.log",
        byte_length=105_702,
        raw_sha256=(
            "9517a02cd1ce2c687365f3712a453a9370e505ee4267e151fd05b266977ce915"
        ),
        replay=2,
        scheduler_mode="7/1",
    ),
    M32PublishedTranscriptIdentity(
        artifact_member_path="m32-mode-1-7-full-trace-run-1.log",
        byte_length=112_364,
        raw_sha256=(
            "41de8e92c28f150f8d163fc1438b4d4381fa42d76a970f9246bbda4679491d89"
        ),
        replay=1,
        scheduler_mode="1/7",
    ),
    M32PublishedTranscriptIdentity(
        artifact_member_path="m32-mode-1-7-full-trace-run-2.log",
        byte_length=112_364,
        raw_sha256=(
            "41de8e92c28f150f8d163fc1438b4d4381fa42d76a970f9246bbda4679491d89"
        ),
        replay=2,
        scheduler_mode="1/7",
    ),
)


@dataclass(frozen=True, slots=True)
class M32PublishedBoundaryValidation:
    """Complete read-only validation of the four-document M32 boundary."""

    registry_revision: str
    loaded_at: datetime
    documents: tuple[M32PublishedDocument, ...]
    source_identities: tuple[M32PublishedSourceIdentity, ...]
    transcript_identities: tuple[M32PublishedTranscriptIdentity, ...]
    source_commit: str
    trace_count: int
    source_tick_count: int
    record_count: int
    active_zero_cell_observation_count: int
    direct_opposite_transition_count: int
    reserved_state_event_count: int
    queue_overflow_event_count: int

    def __post_init__(self) -> None:
        _require(
            self.registry_revision == M32_PUBLISHED_REGISTRY_REVISION,
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
            == M32_PUBLISHED_DOCUMENT_IDENTITIES,
            "published document order or inventory mismatch",
        )
        _require(
            isinstance(self.source_identities, tuple)
            and len(self.source_identities) == 29
            and all(
                isinstance(source, M32PublishedSourceIdentity)
                for source in self.source_identities
            ),
            "source identity inventory mismatch",
        )
        _require(
            isinstance(self.transcript_identities, tuple)
            and self.transcript_identities
            == M32_PUBLISHED_TRANSCRIPT_IDENTITIES,
            "transcript identity inventory mismatch",
        )
        _require(
            all(
                document.source_artifact.loaded_at == self.loaded_at
                for document in self.documents
            )
            and all(
                source.source_artifact.loaded_at == self.loaded_at
                for source in self.source_identities
            ),
            "published source timestamps must share loaded_at",
        )
        source_paths = tuple(
            source.source_path for source in self.source_identities
        )
        _require(
            len(set(source_paths)) == len(source_paths),
            "source identity paths must be unique",
        )
        bundle = next(
            document
            for document in self.documents
            if document.identity.role
            is M32PublishedDocumentRole.TRACE_BUNDLE
        )
        source_boundary = bundle.root.get("source_boundary")
        _require(
            isinstance(source_boundary, Mapping),
            "source boundary is absent from the trace bundle",
        )
        published_source_records = source_boundary.get("source_identities")
        _require(
            isinstance(published_source_records, tuple),
            "published source identity records must be immutable",
        )
        captured_source_records = tuple(
            {
                "path": source.source_path,
                "byte_count": source.byte_length,
                "raw_sha256": source.raw_sha256,
            }
            for source in self.source_identities
        )
        _require(
            tuple(_plain(record) for record in published_source_records)
            == captured_source_records,
            "captured source identities differ from the trace bundle",
        )
        published_transcript_records = source_boundary.get(
            "transcript_identities"
        )
        captured_transcript_records = tuple(
            {
                "artifact_member_path": transcript.artifact_member_path,
                "byte_count": transcript.byte_length,
                "raw_sha256": transcript.raw_sha256,
                "replay": transcript.replay,
                "scheduler_mode": transcript.scheduler_mode,
            }
            for transcript in self.transcript_identities
        )
        _require(
            isinstance(published_transcript_records, tuple)
            and tuple(
                _plain(record) for record in published_transcript_records
            )
            == captured_transcript_records,
            "captured transcript identities differ from the trace bundle",
        )
        _require(
            self.source_commit == M32_SOURCE_COMMIT,
            "source commit mismatch",
        )
        _require(self.trace_count == 2, "trace count mismatch")
        _require(self.source_tick_count == 33, "source tick count mismatch")
        _require(self.record_count == 396, "record count mismatch")
        _require(
            self.active_zero_cell_observation_count == 238,
            "active-zero observation count mismatch",
        )
        _require(
            self.direct_opposite_transition_count == 0,
            "direct opposite transition count mismatch",
        )
        _require(
            self.reserved_state_event_count == 0,
            "reserved-state event count mismatch",
        )
        _require(
            self.queue_overflow_event_count == 0,
            "queue-overflow event count mismatch",
        )
        _require(
            self.total_document_bytes == 458_096,
            "published document byte total mismatch",
        )
        _require(
            self.total_source_bytes == 442_916,
            "source identity byte total mismatch",
        )
        _require(
            self.total_transcript_bytes == 436_132,
            "transcript identity byte total mismatch",
        )

    def document(
        self,
        role: M32PublishedDocumentRole,
    ) -> M32PublishedDocument:
        """Return one exact document by canonical role."""

        _require(
            isinstance(role, M32PublishedDocumentRole),
            "role must be M32PublishedDocumentRole",
        )
        for document in self.documents:
            if document.identity.role is role:
                return document
        raise M32PublishedBoundaryError(
            f"canonical M32 document is absent: {role.value}"
        )

    @property
    def total_document_bytes(self) -> int:
        """Return total raw bytes of the four publication documents."""

        return sum(
            document.source_artifact.byte_length
            for document in self.documents
        )

    @property
    def total_source_bytes(self) -> int:
        """Return total raw bytes of the 29 current source identities."""

        return sum(source.byte_length for source in self.source_identities)

    @property
    def total_transcript_bytes(self) -> int:
        """Return total raw bytes represented by transcript identities."""

        return sum(
            transcript.byte_length
            for transcript in self.transcript_identities
        )


_QUALIFICATION_CHECK_IDS: Final = (
    "source_identities_exact",
    "workflow_identity_exact",
    "mode_7_1_primary_transcript_identity_exact",
    "mode_7_1_replay_transcript_identity_exact",
    "mode_7_1_replays_byte_identical",
    "mode_1_7_primary_transcript_identity_exact",
    "mode_1_7_replay_transcript_identity_exact",
    "mode_1_7_replays_byte_identical",
    "mode_7_1_scheduler_cadence_exact",
    "mode_1_7_scheduler_cadence_exact",
    "source_tick_coordinates_complete",
    "cell_coordinates_complete",
    "request_lane_coordinates_complete",
    "packed_bank_matches_cell_records",
    "packed_masks_match_cell_records",
    "ternary_code_value_pairs_valid",
    "active_zero_markers_exact",
    "pending_route_markers_exact",
    "phase_derived_target_separate_from_execution",
    "registered_target_separate_from_execution",
    "source_boundary_and_execution_fields_separate",
    "first_route_legs_observed",
    "second_route_legs_observed",
    "route_legs_separately_observable",
    "direct_opposite_transitions_absent",
    "reserved_state_events_zero",
    "queue_overflow_events_zero",
    "invariant_flags_all_valid",
    "phase_evolution_records_present",
    "local_effective_gamma_records_present",
    "relative_phase_interference_records_present",
    "retained_frequency_dynamics_observed",
    "phase_order_scales_separate",
    "coherence_capacity_separate_from_phase_order",
    "thermal_telemetry_present",
    "stability_telemetry_present",
    "canonical_bundle_schema_valid",
    "canonical_bundle_digest_reproduced",
)


_TRACE_PROFILES: Final = {
    "7/1": {
        "scheduler_mode_code": 1,
        "source_tick_count": 16,
        "sample_record_count": 16,
        "bank_record_count": 16,
        "cell_record_count": 128,
        "request_record_count": 32,
        "record_count": 192,
        "active_zero_cell_observation_count": 115,
        "scheduler_state_counts": {"balance": 14, "commit": 2},
        "first_route_leg_coordinates": [
            {"source_tick": 9, "source_cell": 0}
        ],
        "second_route_leg_coordinates": [
            {"source_tick": 15, "source_cell": 0}
        ],
        "records_sha256": (
            "bc412e6d548cb1d7f4a2264b526d6d98ac669b75e59c03cd5dbc7cd88756f033"
        ),
    },
    "1/7": {
        "scheduler_mode_code": 2,
        "source_tick_count": 17,
        "sample_record_count": 17,
        "bank_record_count": 17,
        "cell_record_count": 136,
        "request_record_count": 34,
        "record_count": 204,
        "active_zero_cell_observation_count": 123,
        "scheduler_state_counts": {"excite": 3, "neutralize": 14},
        "first_route_leg_coordinates": [
            {"source_tick": 10, "source_cell": 0}
        ],
        "second_route_leg_coordinates": [
            {"source_tick": 16, "source_cell": 0}
        ],
        "records_sha256": (
            "dfb28db5a8bcef2b43c83edd6b420a2286f8f804cfbaead716c2647cffbdf1f5"
        ),
    },
}


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
        raise M32PublishedBoundaryError(
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
        raise M32PublishedBoundaryError(
            f"unable to read upstream source: {relative}"
        ) from exc


def _capture_document(
    root: Path,
    identity: M32PublishedDocumentIdentity,
    timestamp: datetime,
) -> M32PublishedDocument:
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
    return M32PublishedDocument(
        identity=identity,
        source_artifact=source,
        parsed_artifact=parsed,
    )


def _identity_entry(
    role: M32PublishedDocumentRole,
) -> dict[str, object]:
    identity = _IDENTITY_BY_ROLE[role]
    return {
        "byte_count": identity.byte_length,
        "path": identity.source_path,
        "raw_sha256": identity.raw_sha256,
    }


def _validate_trace_bundle(bundle: dict[str, object]) -> None:
    bundle_keys = {
        "schema",
        "version",
        "milestone",
        "kind",
        "status",
        "source_boundary",
        "execution_contract",
        "trace_count",
        "source_tick_count",
        "record_count",
        "traces",
        "bundle_digest_scope",
        "bundle_sha256",
    }
    _require(
        set(bundle) == bundle_keys
        and bundle.get("schema")
        == "frp.m32.deterministic_rtl_trace_bundle.v1"
        and bundle.get("version") == "1.0.0"
        and bundle.get("milestone") == "M32"
        and bundle.get("kind") == "deterministic_rtl_trace_bundle"
        and bundle.get("status") == "PASS"
        and bundle.get("trace_count") == 2
        and bundle.get("source_tick_count") == 33
        and bundle.get("record_count") == 396
        and bundle.get("bundle_digest_scope")
        == "canonical_json_without_bundle_sha256"
        and bundle.get("bundle_sha256") == _BUNDLE_PAYLOAD_SHA256
        and _canonical_digest(bundle, "bundle_sha256")
        == _BUNDLE_PAYLOAD_SHA256,
        "canonical bundle identity mismatch",
    )

    execution = bundle.get("execution_contract")
    _require(
        isinstance(execution, dict)
        and execution.get("canonical_ternary_domain") == [-1, 0, 1]
        and execution.get("canonical_ternary_notation") == "-1/0/1"
        and execution.get("opposite_polarity_routes")
        == [[-1, 0, 1], [1, 0, -1]]
        and execution.get("direct_opposite_transitions_allowed") is False
        and execution.get("route_legs_separately_observable") is True
        and execution.get("scheduler_modes") == ["7/1", "1/7"]
        and execution.get("phase_derived_target_is_executed_state") is False
        and execution.get("registered_target_is_final_executed_state")
        is False
        and execution.get(
            "phase_order_and_coherence_capacity_interchangeable"
        )
        is False
        and execution.get("packed_cell_order")
        == "cell_0_least_significant",
        "execution contract mismatch",
    )
    active_zero_roles = execution.get("active_zero_roles")
    _require(
        isinstance(active_zero_roles, list)
        and len(active_zero_roles) == 8,
        "active-zero role inventory mismatch",
    )

    traces = bundle.get("traces")
    _require(
        isinstance(traces, list)
        and [trace.get("scheduler_mode") for trace in traces]
        == ["7/1", "1/7"],
        "scheduler trace order mismatch",
    )
    code_to_value = {0: 0, 1: 1, 3: -1}
    retained_domain: set[int] = set()
    for trace in traces:
        mode = trace["scheduler_mode"]
        profile = _TRACE_PROFILES[mode]
        records = trace.get("records")
        _require(
            isinstance(records, list),
            f"{mode} record inventory mismatch",
        )
        for field, expected in profile.items():
            _require(
                trace.get(field) == expected,
                f"{mode} trace field mismatch: {field}",
            )
        _require(
            hashlib.sha256(_canonical_json_bytes(records)).hexdigest()
            == profile["records_sha256"],
            f"{mode} record payload digest mismatch",
        )
        _require(
            len(records) == profile["source_tick_count"],
            f"{mode} source tick cardinality mismatch",
        )

        scheduler_states: Counter[str] = Counter()
        first_route_coordinates: list[dict[str, int]] = []
        second_route_coordinates: list[dict[str, int]] = []
        active_zero_count = 0
        previous_retained: dict[int, int] = {}

        for tick, record in enumerate(records):
            _require(
                set(record)
                == {"source_tick", "sample", "bank", "cells", "requests"},
                f"{mode} record field inventory mismatch",
            )
            _require(
                record.get("source_tick") == tick,
                f"{mode} source tick sequence mismatch",
            )
            sample = record.get("sample")
            bank = record.get("bank")
            cells = record.get("cells")
            requests = record.get("requests")
            _require(
                isinstance(sample, dict) and isinstance(bank, dict),
                f"{mode} sample or bank mismatch",
            )
            _require(
                isinstance(cells, list) and len(cells) == 8,
                f"{mode} cell cardinality mismatch",
            )
            _require(
                isinstance(requests, list) and len(requests) == 2,
                f"{mode} request cardinality mismatch",
            )
            _require(
                sample.get("source_tick") == tick
                and bank.get("source_tick") == tick
                and sample.get("scheduler_mode") == mode
                and sample.get("scheduler_mode_code")
                == profile["scheduler_mode_code"]
                and sample.get("actual_direct_events") == 0
                and sample.get("reserved_state_events") == 0
                and sample.get("queue_overflow_events") == 0
                and sample.get("invariant_all_valid") is True
                and sample.get("invariant_flags_hex") == "3ff"
                and sample.get("phase_target_domain_valid") is True
                and sample.get("registered_target_domain_valid") is True,
                f"{mode} sample invariant mismatch",
            )
            scheduler_state = sample.get("scheduler_state")
            _require(
                isinstance(scheduler_state, str),
                f"{mode} scheduler state mismatch",
            )
            scheduler_states[scheduler_state] += 1

            _require(
                [cell.get("source_cell") for cell in cells]
                == list(range(8)),
                f"{mode} cell coordinate mismatch",
            )
            _require(
                [request.get("request_lane") for request in requests]
                == [0, 1],
                f"{mode} request coordinate mismatch",
            )

            for cell in cells:
                _require(
                    cell.get("source_tick") == tick,
                    f"{mode} cell source tick mismatch",
                )
                cell_index = cell["source_cell"]
                for prefix in (
                    "source_target",
                    "registered_target",
                    "execution_target",
                    "retained_state",
                    "pending_target",
                ):
                    code = cell.get(f"{prefix}_code")
                    value = cell.get(f"{prefix}_value")
                    _require(
                        code in code_to_value and code_to_value[code] == value,
                        f"{mode} ternary pair mismatch: {prefix}",
                    )
                retained = cell["retained_state_value"]
                retained_domain.add(retained)
                _require(
                    cell.get("active_zero") is (retained == 0),
                    f"{mode} active-zero marker mismatch",
                )
                active_zero_count += int(cell["active_zero"])
                previous = previous_retained.get(cell_index)
                _require(
                    not (
                        previous in {-1, 1}
                        and retained == -previous
                    ),
                    f"{mode} direct opposite transition",
                )
                previous_retained[cell_index] = retained
                coordinate = {
                    "source_tick": tick,
                    "source_cell": cell_index,
                }
                if cell.get("first_route_leg") is True:
                    first_route_coordinates.append(coordinate)
                if cell.get("second_route_leg") is True:
                    second_route_coordinates.append(coordinate)

            for request in requests:
                _require(
                    request.get("source_tick") == tick,
                    f"{mode} request source tick mismatch",
                )
                for prefix in ("phase_target", "execution_target"):
                    code = request.get(f"{prefix}_code")
                    value = request.get(f"{prefix}_value")
                    _require(
                        code in code_to_value and code_to_value[code] == value,
                        f"{mode} request ternary pair mismatch: {prefix}",
                    )

        _require(
            dict(scheduler_states) == profile["scheduler_state_counts"],
            f"{mode} scheduler cadence mismatch",
        )
        _require(
            active_zero_count
            == profile["active_zero_cell_observation_count"],
            f"{mode} active-zero count mismatch",
        )
        _require(
            first_route_coordinates
            == profile["first_route_leg_coordinates"],
            f"{mode} first route leg mismatch",
        )
        _require(
            second_route_coordinates
            == profile["second_route_leg_coordinates"],
            f"{mode} second route leg mismatch",
        )

    _require(
        retained_domain == {-1, 0, 1},
        "retained ternary domain mismatch",
    )


def _validate_documents(
    documents: tuple[M32PublishedDocument, ...],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by_role = {
        document.identity.role: _plain(document.root)
        for document in documents
    }
    schema = by_role[M32PublishedDocumentRole.FORMAL_SCHEMA]
    bundle = by_role[M32PublishedDocumentRole.TRACE_BUNDLE]
    manifest = by_role[M32PublishedDocumentRole.MANIFEST]
    qualification = by_role[M32PublishedDocumentRole.QUALIFICATION]
    _require(
        all(isinstance(value, dict) for value in by_role.values()),
        "published document root type mismatch",
    )

    bundle_keys = {
        "schema",
        "version",
        "milestone",
        "kind",
        "status",
        "source_boundary",
        "execution_contract",
        "trace_count",
        "source_tick_count",
        "record_count",
        "traces",
        "bundle_digest_scope",
        "bundle_sha256",
    }
    _require(
        schema.get("$schema")
        == "https://json-schema.org/draft/2020-12/schema"
        and schema.get("$id")
        == (
            "https://frp.example/schemas/m32/"
            "frp.m32.deterministic_rtl_trace_bundle.v1.schema.json"
        )
        and schema.get("title") == "FRP M32 Deterministic RTL Trace Bundle"
        and schema.get("type") == "object"
        and schema.get("additionalProperties") is False
        and set(schema.get("required", [])) == bundle_keys
        and schema.get("properties", {}).get("schema", {}).get("const")
        == "frp.m32.deterministic_rtl_trace_bundle.v1",
        "formal schema boundary mismatch",
    )
    _validate_trace_bundle(bundle)

    source_boundary = bundle.get("source_boundary")
    _require(
        isinstance(source_boundary, dict)
        and source_boundary.get("repository")
        == (
            "Fractal-Resonance-Processor-FRP-Ternary-"
            "Resonant-Coherence-Processor"
        )
        and source_boundary.get("provenance_class")
        == "upstream_frp_systemverilog_rtl"
        and source_boundary.get("source_commit") == M32_SOURCE_COMMIT
        and source_boundary.get("source_identity_count") == 29
        and source_boundary.get("transcript_identity_count") == 4
        and source_boundary.get("workflow_name")
        == "FRP M32 Registered Target Core"
        and source_boundary.get("workflow_path")
        == (
            ".github/workflows/"
            "frp-m32-registered-target-boundary-workflow.yml"
        ),
        "source boundary mismatch",
    )

    source_records = source_boundary.get("source_identities")
    _require(
        isinstance(source_records, list)
        and len(source_records) == 29
        and source_records == manifest.get("source_identities"),
        "source identity inventory mismatch",
    )
    source_paths: list[str] = []
    for record in source_records:
        _require(
            isinstance(record, dict)
            and set(record) == {"path", "byte_count", "raw_sha256"},
            "source identity record mismatch",
        )
        source_paths.append(
            _validate_relative_path(record.get("path"), "source path")
        )
        _validate_positive_integer(record.get("byte_count"), "source bytes")
        _validate_sha256(record.get("raw_sha256"), "source digest")
    _require(
        len(set(source_paths)) == 29,
        "source identity paths are not unique",
    )
    source_groups = Counter(
        "m31_rtl"
        if path.startswith("rtl/m31/")
        else "m32_rtl"
        if path.startswith("rtl/m32/")
        else "m32_formal"
        if path.startswith("formal/m32/")
        else "registered_workflow"
        if path
        == (
            ".github/workflows/"
            "frp-m32-registered-target-boundary-workflow.yml"
        )
        else "unexpected"
        for path in source_paths
    )
    _require(
        source_groups
        == {
            "m31_rtl": 16,
            "m32_rtl": 11,
            "m32_formal": 1,
            "registered_workflow": 1,
        },
        "source identity group mismatch",
    )

    transcript_records = source_boundary.get("transcript_identities")
    expected_transcripts = [
        {
            "artifact_member_path": identity.artifact_member_path,
            "byte_count": identity.byte_length,
            "raw_sha256": identity.raw_sha256,
            "replay": identity.replay,
            "scheduler_mode": identity.scheduler_mode,
        }
        for identity in M32_PUBLISHED_TRANSCRIPT_IDENTITIES
    ]
    _require(
        transcript_records == expected_transcripts
        and transcript_records == manifest.get("transcript_identities"),
        "transcript identity mismatch",
    )

    manifest_keys = {
        "schema",
        "version",
        "milestone",
        "kind",
        "status",
        "source_commit",
        "generated_file_count",
        "generated_files",
        "source_identity_count",
        "source_identities",
        "transcript_identity_count",
        "transcript_identities",
        "manifest_digest_scope",
        "manifest_sha256",
    }
    _require(
        set(manifest) == manifest_keys
        and manifest.get("schema")
        == "frp.m32.deterministic_rtl_trace_manifest.v1"
        and manifest.get("version") == "1.0.0"
        and manifest.get("milestone") == "M32"
        and manifest.get("kind") == "deterministic_rtl_trace_manifest"
        and manifest.get("status") == "PASS"
        and manifest.get("source_commit") == M32_SOURCE_COMMIT
        and manifest.get("generated_file_count") == 2
        and manifest.get("generated_files")
        == [
            _identity_entry(M32PublishedDocumentRole.FORMAL_SCHEMA),
            _identity_entry(M32PublishedDocumentRole.TRACE_BUNDLE),
        ]
        and manifest.get("source_identity_count") == 29
        and manifest.get("transcript_identity_count") == 4
        and manifest.get("manifest_digest_scope")
        == "canonical_json_without_manifest_sha256"
        and manifest.get("manifest_sha256") == _MANIFEST_PAYLOAD_SHA256
        and _canonical_digest(manifest, "manifest_sha256")
        == _MANIFEST_PAYLOAD_SHA256,
        "manifest boundary mismatch",
    )

    qualification_keys = {
        "schema",
        "version",
        "milestone",
        "kind",
        "status",
        "source_commit",
        "check_count",
        "passed_count",
        "failed_count",
        "checks",
        "qualified_artifact_count",
        "qualified_artifacts",
        "qualification_digest_scope",
        "qualification_sha256",
    }
    checks = qualification.get("checks")
    _require(
        set(qualification) == qualification_keys
        and qualification.get("schema")
        == "frp.m32.deterministic_rtl_trace_qualification.v1"
        and qualification.get("version") == "1.0.0"
        and qualification.get("milestone") == "M32"
        and qualification.get("kind")
        == "deterministic_rtl_trace_qualification"
        and qualification.get("status") == "PASS"
        and qualification.get("source_commit") == M32_SOURCE_COMMIT
        and qualification.get("check_count") == 38
        and qualification.get("passed_count") == 38
        and qualification.get("failed_count") == 0
        and isinstance(checks, list)
        and [check.get("check_id") for check in checks]
        == list(_QUALIFICATION_CHECK_IDS)
        and all(
            check == {"check_id": check["check_id"], "status": "PASS"}
            for check in checks
        )
        and qualification.get("qualified_artifact_count") == 3
        and qualification.get("qualified_artifacts")
        == [
            _identity_entry(M32PublishedDocumentRole.FORMAL_SCHEMA),
            _identity_entry(M32PublishedDocumentRole.TRACE_BUNDLE),
            _identity_entry(M32PublishedDocumentRole.MANIFEST),
        ]
        and qualification.get("qualification_digest_scope")
        == "canonical_json_without_qualification_sha256"
        and qualification.get("qualification_sha256")
        == _QUALIFICATION_PAYLOAD_SHA256
        and _canonical_digest(qualification, "qualification_sha256")
        == _QUALIFICATION_PAYLOAD_SHA256,
        "qualification boundary mismatch",
    )
    return source_records, transcript_records


def _capture_source_identities(
    root: Path,
    records: Sequence[dict[str, object]],
    timestamp: datetime,
) -> tuple[M32PublishedSourceIdentity, ...]:
    sources: list[M32PublishedSourceIdentity] = []
    for record in records:
        path = _validate_relative_path(record.get("path"), "source path")
        byte_length = _validate_positive_integer(
            record.get("byte_count"),
            "source byte_count",
        )
        raw_sha256 = _validate_sha256(
            record.get("raw_sha256"),
            "source raw_sha256",
        )
        raw = _read_regular(root, path)
        _require(
            len(raw) == byte_length
            and hashlib.sha256(raw).hexdigest() == raw_sha256,
            f"source identity mismatch: {path}",
        )
        source = capture_source_bytes(
            raw,
            source_filename=PurePosixPath(path).name,
            source_path=path,
            loaded_at=timestamp,
        )
        sources.append(
            M32PublishedSourceIdentity(
                source_path=path,
                byte_length=byte_length,
                raw_sha256=raw_sha256,
                source_artifact=source,
            )
        )
    return tuple(sources)


def _capture_transcript_identities(
    records: Sequence[dict[str, object]],
) -> tuple[M32PublishedTranscriptIdentity, ...]:
    return tuple(
        M32PublishedTranscriptIdentity(
            artifact_member_path=_validate_relative_path(
                record.get("artifact_member_path"),
                "artifact_member_path",
            ),
            byte_length=_validate_positive_integer(
                record.get("byte_count"),
                "transcript byte_count",
            ),
            raw_sha256=_validate_sha256(
                record.get("raw_sha256"),
                "transcript raw_sha256",
            ),
            replay=_validate_positive_integer(
                record.get("replay"),
                "transcript replay",
            ),
            scheduler_mode=_validate_token(
                record.get("scheduler_mode"),
                "transcript scheduler_mode",
            ),
        )
        for record in records
    )


def validate_m32_published_boundary(
    upstream_root: str | Path,
    *,
    loaded_at: datetime | None = None,
) -> M32PublishedBoundaryValidation:
    """Validate and capture the exact read-only FRP M32 publication."""

    root = _root_path(upstream_root)
    timestamp = datetime.now(timezone.utc) if loaded_at is None else loaded_at
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
            for identity in M32_PUBLISHED_DOCUMENT_IDENTITIES
        )
        source_records, transcript_records = _validate_documents(documents)
        source_identities = _capture_source_identities(
            root,
            source_records,
            timestamp,
        )
        transcript_identities = _capture_transcript_identities(
            transcript_records
        )
        result = M32PublishedBoundaryValidation(
            registry_revision=M32_PUBLISHED_REGISTRY_REVISION,
            loaded_at=timestamp,
            documents=documents,
            source_identities=source_identities,
            transcript_identities=transcript_identities,
            source_commit=M32_SOURCE_COMMIT,
            trace_count=2,
            source_tick_count=33,
            record_count=396,
            active_zero_cell_observation_count=238,
            direct_opposite_transition_count=0,
            reserved_state_event_count=0,
            queue_overflow_event_count=0,
        )
        _require(
            result.total_document_bytes == 458_096,
            "published document byte total mismatch",
        )
        _require(
            result.total_source_bytes == 442_916,
            "source identity byte total mismatch",
        )
        _require(
            result.total_transcript_bytes == 436_132,
            "transcript identity byte total mismatch",
        )
        return result
    except M32PublishedBoundaryError:
        raise
    except (JsonArtifactError, SourceArtifactError) as exc:
        raise M32PublishedBoundaryError(
            f"strict M32 source intake failed: {exc}"
        ) from exc
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        raise M32PublishedBoundaryError(
            f"M32 publication structure mismatch: {exc}"
        ) from exc


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the exact FRP M32 deterministic RTL trace publication "
            "as a strictly read-only Observatory boundary."
        )
    )
    parser.add_argument("--upstream-root", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate_m32_published_boundary(arguments.upstream_root)
    print("FRP Observatory M32 published boundary intake: PASS")
    print(f"registry_revision={result.registry_revision}")
    print(f"published_documents={len(result.documents)}")
    print(f"published_document_bytes={result.total_document_bytes}")
    print(f"source_commit={result.source_commit}")
    print(f"source_identities={len(result.source_identities)}")
    print(f"source_identity_bytes={result.total_source_bytes}")
    print(f"transcript_identities={len(result.transcript_identities)}")
    print(f"transcript_identity_bytes={result.total_transcript_bytes}")
    print(f"scheduler_traces={result.trace_count}")
    print(f"source_ticks={result.source_tick_count}")
    print(f"structured_trace_records={result.record_count}")
    print(
        "active_zero_cell_observations="
        f"{result.active_zero_cell_observation_count}"
    )
    print("balanced_ternary_notation=-1/0/1")
    print("opposite_transition_routes=-1/0/1,1/0/-1")
    print(
        "direct_opposite_transitions="
        f"{result.direct_opposite_transition_count}"
    )
    print(f"reserved_state_events={result.reserved_state_event_count}")
    print(f"queue_overflow_events={result.queue_overflow_event_count}")
    print("transient_workflow_artifact_reads=forbidden")
    print("record_normalization=forbidden")
    print("source_mutation=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
