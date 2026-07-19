"""Immutable source-artifact capture for published FRP data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4


__all__ = [
    "LoadStatus",
    "RawSourceDigest",
    "SourceArtifact",
    "SourceArtifactError",
    "SourceContainerFormat",
    "capture_source_bytes",
    "detect_container_format",
    "load_source_file",
]


_SHA256_HEX_LENGTH: Final = 64
_LOWERCASE_HEX: Final = frozenset("0123456789abcdef")
_ZIP_SIGNATURES: Final = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
)


class SourceArtifactError(ValueError):
    """Raised when source bytes or source metadata are invalid."""


class SourceContainerFormat(StrEnum):
    """Safely detected outer format of captured source bytes."""

    EMPTY = "empty"
    JSON_CANDIDATE = "json_candidate"
    UTF8_TEXT = "utf8_text"
    ZIP = "zip"
    BINARY = "binary"


class LoadStatus(StrEnum):
    """Source-capture status stored by a completed load."""

    CAPTURED = "captured"


def _new_identifier() -> str:
    return str(uuid4())


def _validate_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise SourceArtifactError(f"{field_name} must be a string")

    try:
        UUID(value)
    except (ValueError, AttributeError) as exc:
        raise SourceArtifactError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_source_filename(value: str) -> None:
    if not isinstance(value, str):
        raise SourceArtifactError("source_filename must be a string")
    if not value.strip():
        raise SourceArtifactError("source_filename must not be empty")
    if value in {".", ".."}:
        raise SourceArtifactError("source_filename must name a file")
    if "\x00" in value:
        raise SourceArtifactError("source_filename must not contain NUL")
    if "/" in value or "\\" in value:
        raise SourceArtifactError(
            "source_filename must not contain path separators"
        )


def _coerce_source_path(value: str | Path | None) -> str | None:
    if value is None:
        return None

    path_text = str(value)
    if not path_text:
        raise SourceArtifactError("source_path must not be empty")
    if "\x00" in path_text:
        raise SourceArtifactError("source_path must not contain NUL")
    return path_text


def _normalize_loaded_at(value: datetime | None) -> datetime:
    timestamp = value if value is not None else datetime.now(timezone.utc)

    if not isinstance(timestamp, datetime):
        raise SourceArtifactError("loaded_at must be a datetime")
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise SourceArtifactError("loaded_at must include a timezone")

    return timestamp.astimezone(timezone.utc)


def detect_container_format(raw_bytes: bytes) -> SourceContainerFormat:
    """Detect an outer data container without executing source content."""

    if not isinstance(raw_bytes, bytes):
        raise SourceArtifactError("raw_bytes must be bytes")
    if not raw_bytes:
        return SourceContainerFormat.EMPTY
    if raw_bytes.startswith(_ZIP_SIGNATURES):
        return SourceContainerFormat.ZIP

    try:
        decoded = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return SourceContainerFormat.BINARY

    if "\x00" in decoded:
        return SourceContainerFormat.BINARY

    stripped = decoded.lstrip()
    if stripped.startswith(("{", "[")):
        return SourceContainerFormat.JSON_CANDIDATE
    return SourceContainerFormat.UTF8_TEXT

@dataclass(frozen=True, slots=True)
class RawSourceDigest:
    """SHA-256 identity calculated over unchanged source bytes."""

    digest_record_id: str
    value: str
    algorithm: str = "sha256"
    byte_scope: str = "raw_source_bytes"

    def __post_init__(self) -> None:
        _validate_identifier(self.digest_record_id, "digest_record_id")
        if not isinstance(self.value, str):
            raise SourceArtifactError(
                "raw source digest value must be a string"
            )
        if self.algorithm != "sha256":
            raise SourceArtifactError(
                "raw source digest algorithm must be sha256"
            )
        if self.byte_scope != "raw_source_bytes":
            raise SourceArtifactError(
                "raw source digest scope must be raw_source_bytes"
            )
        if (
            len(self.value) != _SHA256_HEX_LENGTH
            or any(character not in _LOWERCASE_HEX for character in self.value)
        ):
            raise SourceArtifactError(
                "raw source digest must be 64 lowercase hexadecimal characters"
            )


@dataclass(frozen=True, slots=True)
class SourceArtifact:
    """One immutable load of original artifact bytes and source metadata."""

    source_artifact_id: str
    source_filename: str
    source_path: str | None
    raw_bytes: bytes = field(repr=False)
    byte_length: int
    detected_container_format: SourceContainerFormat
    source_digest: RawSourceDigest
    loaded_at: datetime
    load_status: LoadStatus = LoadStatus.CAPTURED

    def __post_init__(self) -> None:
        _validate_identifier(
            self.source_artifact_id,
            "source_artifact_id",
        )
        _validate_source_filename(self.source_filename)
        if self.source_path is not None and not isinstance(
            self.source_path,
            str,
        ):
            raise SourceArtifactError(
                "source_path must be a string or None"
            )
        _coerce_source_path(self.source_path)

        if not isinstance(self.raw_bytes, bytes):
            raise SourceArtifactError("raw_bytes must be immutable bytes")
        if isinstance(self.byte_length, bool) or not isinstance(
            self.byte_length,
            int,
        ):
            raise SourceArtifactError("byte_length must be an integer")
        if self.byte_length != len(self.raw_bytes):
            raise SourceArtifactError(
                "byte_length does not match the captured source bytes"
            )
        if not isinstance(
            self.detected_container_format,
            SourceContainerFormat,
        ):
            raise SourceArtifactError(
                "detected_container_format must be a SourceContainerFormat"
            )
        if self.detected_container_format != detect_container_format(
            self.raw_bytes
        ):
            raise SourceArtifactError(
                "detected_container_format does not match source bytes"
            )
        if not isinstance(self.source_digest, RawSourceDigest):
            raise SourceArtifactError(
                "source_digest must be a RawSourceDigest"
            )
        if self.source_digest.value != sha256(self.raw_bytes).hexdigest():
            raise SourceArtifactError(
                "source digest does not match the captured source bytes"
            )
        if not isinstance(self.loaded_at, datetime):
            raise SourceArtifactError("loaded_at must be a datetime")
        if self.loaded_at.tzinfo is None or self.loaded_at.utcoffset() is None:
            raise SourceArtifactError("loaded_at must include a timezone")
        if self.loaded_at.utcoffset() != timedelta(0):
            raise SourceArtifactError("loaded_at must be normalized to UTC")
        if not isinstance(self.load_status, LoadStatus):
            raise SourceArtifactError("load_status must be a LoadStatus")
        if self.load_status is not LoadStatus.CAPTURED:
            raise SourceArtifactError(
                "completed source artifacts must have captured status"
            )

    @property
    def source_digest_id(self) -> str:
        """Return the logical digest-record identity."""

        return self.source_digest.digest_record_id

    @property
    def content_sha256(self) -> str:
        """Return the SHA-256 identity of the original source bytes."""

        return self.source_digest.value

    def verify_integrity(self) -> bool:
        """Recalculate the raw-byte digest without modifying the source."""

        return sha256(self.raw_bytes).hexdigest() == self.content_sha256
def capture_source_bytes(
    raw_bytes: bytes | bytearray | memoryview,
    *,
    source_filename: str,
    source_path: str | Path | None = None,
    loaded_at: datetime | None = None,
) -> SourceArtifact:
    """Capture one immutable source artifact from caller-provided bytes."""

    if not isinstance(raw_bytes, (bytes, bytearray, memoryview)):
        raise SourceArtifactError(
            "raw_bytes must be bytes, bytearray, or memoryview"
        )

    _validate_source_filename(source_filename)
    normalized_path = _coerce_source_path(source_path)
    normalized_timestamp = _normalize_loaded_at(loaded_at)
    immutable_bytes = bytes(raw_bytes)
    source_digest = RawSourceDigest(
        digest_record_id=_new_identifier(),
        value=sha256(immutable_bytes).hexdigest(),
    )

    return SourceArtifact(
        source_artifact_id=_new_identifier(),
        source_filename=source_filename,
        source_path=normalized_path,
        raw_bytes=immutable_bytes,
        byte_length=len(immutable_bytes),
        detected_container_format=detect_container_format(
            immutable_bytes
        ),
        source_digest=source_digest,
        loaded_at=normalized_timestamp,
    )


def load_source_file(
    path: str | Path,
    *,
    source_path: str | Path | None = None,
    loaded_at: datetime | None = None,
) -> SourceArtifact:
    """Read and capture one local regular file without changing it."""

    if not isinstance(path, (str, Path)):
        raise SourceArtifactError("path must be a string or Path")

    try:
        file_path = Path(path)
    except (TypeError, ValueError) as exc:
        raise SourceArtifactError("path is invalid") from exc

    try:
        if file_path.is_symlink():
            raise SourceArtifactError(
                "source path must not be a symbolic link"
            )
        if not file_path.is_file():
            raise SourceArtifactError(
                "source path must identify a regular file"
            )
        raw_bytes = file_path.read_bytes()
    except SourceArtifactError:
        raise
    except OSError as exc:
        raise SourceArtifactError(
            f"unable to read source artifact: {file_path}"
        ) from exc

    recorded_path = file_path if source_path is None else source_path
    return capture_source_bytes(
        raw_bytes,
        source_filename=file_path.name,
        source_path=recorded_path,
        loaded_at=loaded_at,
    )
