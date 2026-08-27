"""Read-only intake for the exact FRP v3.2.0 / M30 release archive.

This module validates the fixed published archive before any downstream
artifact parser sees its contents. It verifies the raw package identity,
safe deterministic tar structure, internal manifest, every member length,
and every member SHA-256 digest. It never extracts, executes, normalizes, or
modifies upstream bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final, Iterable, Mapping, Sequence


__all__ = [
    "FRP_M30_ARCHIVE_BYTE_LENGTH",
    "FRP_M30_ARCHIVE_SHA256",
    "FRP_M30_RELEASE_ROOT",
    "FRP_M30_SOURCE_COMMIT",
    "M30ArchiveIntakeError",
    "M30ArchiveMember",
    "M30ArchiveValidation",
    "RetainedArchiveMember",
    "validate_m30_archive",
    "validate_m30_archive_bytes",
]


FRP_M30_ARCHIVE_SHA256: Final = (
    "05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa"
)
FRP_M30_ARCHIVE_BYTE_LENGTH: Final = 10_189_989
FRP_M30_RELEASE_ROOT: Final = (
    "Fractal-Resonance-Processor-FRP-v3.2.0"
)
FRP_M30_SOURCE_COMMIT: Final = (
    "ff3dd434da5dcbd9e8fa62444f658ed4c495b540"
)

_ARCHIVE_MEMBER_COUNT: Final = 519
_MANIFEST_MEMBER_COUNT: Final = 518
_INTERNAL_MANIFEST_PATH: Final = "ARCHIVE_MANIFEST_v3_2_0.json"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class M30ArchiveIntakeError(ValueError):
    """Raised when the fixed M30 published-byte boundary is violated."""


@dataclass(frozen=True, slots=True)
class M30ArchiveMember:
    """One archived member verified against the internal manifest."""

    path: str
    byte_length: int
    raw_sha256: str


@dataclass(frozen=True, slots=True)
class RetainedArchiveMember:
    """Explicitly retained bytes for one already verified member."""

    member: M30ArchiveMember
    raw_bytes: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.member, M30ArchiveMember):
            raise M30ArchiveIntakeError(
                "retained member metadata must be M30ArchiveMember"
            )
        if not isinstance(self.raw_bytes, bytes):
            raise M30ArchiveIntakeError(
                "retained member source must be immutable bytes"
            )
        if len(self.raw_bytes) != self.member.byte_length:
            raise M30ArchiveIntakeError(
                "retained member byte length differs from metadata"
            )
        if _sha256(self.raw_bytes) != self.member.raw_sha256:
            raise M30ArchiveIntakeError(
                "retained member digest differs from metadata"
            )


@dataclass(frozen=True, slots=True)
class M30ArchiveValidation:
    """Successful validation evidence for one exact M30 archive."""

    archive_sha256: str
    archive_byte_length: int
    release_root: str
    source_commit: str
    members: tuple[M30ArchiveMember, ...]
    retained_members: tuple[RetainedArchiveMember, ...]

    def __post_init__(self) -> None:
        if self.archive_sha256 != FRP_M30_ARCHIVE_SHA256:
            raise M30ArchiveIntakeError(
                "validation result archive digest is not the M30 digest"
            )
        if self.archive_byte_length != FRP_M30_ARCHIVE_BYTE_LENGTH:
            raise M30ArchiveIntakeError(
                "validation result archive byte length is not the M30 length"
            )
        if self.release_root != FRP_M30_RELEASE_ROOT:
            raise M30ArchiveIntakeError(
                "validation result release root is not the M30 root"
            )
        if self.source_commit != FRP_M30_SOURCE_COMMIT:
            raise M30ArchiveIntakeError(
                "validation result source commit is not the M30 commit"
            )
        if (
            not isinstance(self.members, tuple)
            or len(self.members) != _MANIFEST_MEMBER_COUNT
            or any(
                not isinstance(member, M30ArchiveMember)
                for member in self.members
            )
        ):
            raise M30ArchiveIntakeError(
                "validation result manifest members are invalid"
            )
        if (
            not isinstance(self.retained_members, tuple)
            or any(
                not isinstance(member, RetainedArchiveMember)
                for member in self.retained_members
            )
        ):
            raise M30ArchiveIntakeError(
                "validation result retained members are invalid"
            )
        member_paths = tuple(member.path for member in self.members)
        if member_paths != tuple(sorted(member_paths)):
            raise M30ArchiveIntakeError(
                "validation result members must be lexicographically ordered"
            )
        retained_paths = tuple(
            retained.member.path for retained in self.retained_members
        )
        if retained_paths != tuple(sorted(retained_paths)):
            raise M30ArchiveIntakeError(
                "validation result retained members must be ordered"
            )
        if len(set(retained_paths)) != len(retained_paths):
            raise M30ArchiveIntakeError(
                "validation result retained members must be unique"
            )
        known_paths = set(member_paths)
        if any(path not in known_paths for path in retained_paths):
            raise M30ArchiveIntakeError(
                "validation result retained member is not in the manifest"
            )

    @property
    def archive_member_count(self) -> int:
        """Return the tar member count, including the internal manifest."""

        return len(self.members) + 1

    def member(self, path: str) -> M30ArchiveMember:
        """Resolve one exact manifest path without aliases."""

        for member in self.members:
            if member.path == path:
                return member
        raise KeyError(path)

    def retained_member(self, path: str) -> RetainedArchiveMember:
        """Resolve explicitly retained bytes without path aliases."""

        for member in self.retained_members:
            if member.member.path == path:
                return member
        raise KeyError(path)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs_without_duplicates(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise M30ArchiveIntakeError(
                f"duplicate JSON object key: {key!r}"
            )
        result[key] = value
    return result


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise M30ArchiveIntakeError(
            f"{label} is not strict UTF-8"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
        )
    except json.JSONDecodeError as exc:
        raise M30ArchiveIntakeError(
            f"{label} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise M30ArchiveIntakeError(f"{label} must be a JSON object")
    return value


def _safe_relative_path(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\\" in value
        or "\x00" in value
    ):
        raise M30ArchiveIntakeError(f"unsafe {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(
        part in {"", ".", ".."} for part in value.split("/")
    ):
        raise M30ArchiveIntakeError(f"unsafe {label}: {value!r}")
    return value


def _require_equal(
    value: Mapping[str, Any],
    field: str,
    expected: object,
    label: str,
) -> None:
    if value.get(field) != expected:
        raise M30ArchiveIntakeError(f"{label} {field} mismatch")


def _member_bytes(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
) -> bytes:
    stream = archive.extractfile(member)
    if stream is None:
        raise M30ArchiveIntakeError(
            f"archive member is unreadable: {member.name}"
        )
    raw = stream.read(member.size + 1)
    if len(raw) != member.size:
        raise M30ArchiveIntakeError(
            f"archive member byte length mismatch: {member.name}"
        )
    return raw


def _relative_member_path(name: str) -> str:
    _safe_relative_path(name, "archive member path")
    parts = name.split("/")
    if len(parts) < 2 or parts[0] != FRP_M30_RELEASE_ROOT:
        raise M30ArchiveIntakeError(
            f"archive member is outside {FRP_M30_RELEASE_ROOT!r}: {name!r}"
        )
    return _safe_relative_path(
        "/".join(parts[1:]),
        "release-relative member path",
    )


def _validate_manifest(
    raw: bytes,
    archive_paths: tuple[str, ...],
) -> tuple[M30ArchiveMember, ...]:
    value = _json_object(raw, "M30 internal archive manifest")
    _require_equal(
        value,
        "schema",
        "frp.m30.archive_internal_manifest.v3.2.0",
        "M30 internal archive manifest",
    )
    _require_equal(
        value,
        "milestone",
        "M30",
        "M30 internal archive manifest",
    )
    _require_equal(
        value,
        "version",
        "3.2.0",
        "M30 internal archive manifest",
    )
    _require_equal(
        value,
        "source_commit",
        FRP_M30_SOURCE_COMMIT,
        "M30 internal archive manifest",
    )
    _require_equal(
        value,
        "member_count",
        _MANIFEST_MEMBER_COUNT,
        "M30 internal archive manifest",
    )
    records = value.get("members")
    if not isinstance(records, list) or len(records) != _MANIFEST_MEMBER_COUNT:
        raise M30ArchiveIntakeError(
            "M30 internal archive manifest members mismatch"
        )

    result: list[M30ArchiveMember] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != {
            "path",
            "byte_length",
            "raw_sha256",
        }:
            raise M30ArchiveIntakeError(
                f"M30 manifest member {index} has an invalid shape"
            )
        path = _safe_relative_path(record["path"], "manifest member path")
        byte_length = record["byte_length"]
        digest = record["raw_sha256"]
        if (
            not isinstance(byte_length, int)
            or isinstance(byte_length, bool)
            or byte_length < 0
        ):
            raise M30ArchiveIntakeError(
                f"M30 manifest member {path!r} has an invalid byte length"
            )
        if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
            raise M30ArchiveIntakeError(
                f"M30 manifest member {path!r} has an invalid digest"
            )
        result.append(
            M30ArchiveMember(
                path=path,
                byte_length=byte_length,
                raw_sha256=digest,
            )
        )

    manifest_paths = tuple(member.path for member in result)
    if manifest_paths != tuple(sorted(manifest_paths)):
        raise M30ArchiveIntakeError(
            "M30 internal manifest member order is not lexicographic"
        )
    if len(set(manifest_paths)) != len(manifest_paths):
        raise M30ArchiveIntakeError(
            "M30 internal manifest contains duplicate member paths"
        )
    expected_paths = tuple(
        path for path in archive_paths if path != _INTERNAL_MANIFEST_PATH
    )
    if manifest_paths != expected_paths:
        raise M30ArchiveIntakeError(
            "M30 internal manifest does not match archive members"
        )
    return tuple(result)


def _normalize_retain_paths(retain_paths: Iterable[str]) -> tuple[str, ...]:
    try:
        values = tuple(retain_paths)
    except TypeError as exc:
        raise M30ArchiveIntakeError(
            "retain_paths must be an iterable of relative paths"
        ) from exc
    normalized = tuple(
        _safe_relative_path(value, "retained member path") for value in values
    )
    if len(set(normalized)) != len(normalized):
        raise M30ArchiveIntakeError("retain_paths must be unique")
    return tuple(sorted(normalized))


def validate_m30_archive_bytes(
    raw: bytes,
    *,
    retain_paths: Iterable[str] = (),
) -> M30ArchiveValidation:
    """Validate exact M30 bytes and optionally retain selected members."""

    if not isinstance(raw, bytes):
        raise TypeError("raw must be bytes")
    retained_path_order = _normalize_retain_paths(retain_paths)
    retained_path_set = set(retained_path_order)
    if len(raw) != FRP_M30_ARCHIVE_BYTE_LENGTH:
        raise M30ArchiveIntakeError("FRP M30 archive byte length mismatch")
    archive_digest = _sha256(raw)
    if archive_digest != FRP_M30_ARCHIVE_SHA256:
        raise M30ArchiveIntakeError("FRP M30 archive digest mismatch")
    if raw[:2] != b"\x1f\x8b" or raw[4:8] != b"\x00\x00\x00\x00":
        raise M30ArchiveIntakeError(
            "FRP M30 deterministic gzip header mismatch"
        )

    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            tar_members = archive.getmembers()
            if len(tar_members) != _ARCHIVE_MEMBER_COUNT:
                raise M30ArchiveIntakeError(
                    "FRP M30 archive member count mismatch"
                )
            if any(not member.isfile() for member in tar_members):
                raise M30ArchiveIntakeError(
                    "FRP M30 archive contains a non-regular member"
                )
            names = tuple(member.name for member in tar_members)
            if names != tuple(sorted(names)):
                raise M30ArchiveIntakeError(
                    "FRP M30 archive member order is not lexicographic"
                )
            if len(set(names)) != len(names):
                raise M30ArchiveIntakeError(
                    "FRP M30 archive contains duplicate member paths"
                )
            relative_paths = tuple(_relative_member_path(name) for name in names)
            tar_by_relative = dict(zip(relative_paths, tar_members, strict=True))
            manifest_tar_member = tar_by_relative.get(_INTERNAL_MANIFEST_PATH)
            if manifest_tar_member is None:
                raise M30ArchiveIntakeError(
                    "FRP M30 internal manifest is missing"
                )
            manifest_members = _validate_manifest(
                _member_bytes(archive, manifest_tar_member),
                relative_paths,
            )
            manifest_by_path = {
                member.path: member for member in manifest_members
            }
            unknown_retain_paths = sorted(
                retained_path_set - manifest_by_path.keys()
            )
            if unknown_retain_paths:
                raise M30ArchiveIntakeError(
                    "requested retained members are not in the M30 manifest: "
                    f"{unknown_retain_paths!r}"
                )

            retained_raw: dict[str, bytes] = {}
            for manifest_member in manifest_members:
                tar_member = tar_by_relative[manifest_member.path]
                if tar_member.size != manifest_member.byte_length:
                    raise M30ArchiveIntakeError(
                        "FRP M30 member byte length differs from manifest: "
                        f"{manifest_member.path}"
                    )
                member_raw = _member_bytes(archive, tar_member)
                if _sha256(member_raw) != manifest_member.raw_sha256:
                    raise M30ArchiveIntakeError(
                        "FRP M30 member digest differs from manifest: "
                        f"{manifest_member.path}"
                    )
                if manifest_member.path in retained_path_set:
                    retained_raw[manifest_member.path] = member_raw
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise M30ArchiveIntakeError(
            f"FRP M30 tar/gzip structure is invalid: {exc}"
        ) from exc

    retained_members = tuple(
        RetainedArchiveMember(
            member=manifest_by_path[path],
            raw_bytes=retained_raw[path],
        )
        for path in retained_path_order
    )
    return M30ArchiveValidation(
        archive_sha256=archive_digest,
        archive_byte_length=len(raw),
        release_root=FRP_M30_RELEASE_ROOT,
        source_commit=FRP_M30_SOURCE_COMMIT,
        members=manifest_members,
        retained_members=retained_members,
    )


def validate_m30_archive(
    path: str | Path,
    *,
    retain_paths: Iterable[str] = (),
) -> M30ArchiveValidation:
    """Read and validate one regular, non-symlink M30 archive file."""

    archive_path = Path(path)
    if archive_path.is_symlink() or not archive_path.is_file():
        raise M30ArchiveIntakeError(
            "FRP M30 archive path must be a regular non-symlink file"
        )
    if archive_path.stat().st_size != FRP_M30_ARCHIVE_BYTE_LENGTH:
        raise M30ArchiveIntakeError("FRP M30 archive byte length mismatch")
    return validate_m30_archive_bytes(
        archive_path.read_bytes(),
        retain_paths=retain_paths,
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the exact FRP v3.2.0 / M30 published archive without "
            "extracting or executing source content."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate_m30_archive(arguments.archive)
    print("FRP M30 archival intake: PASS")
    print(f"archive_sha256={result.archive_sha256}")
    print(f"archive_members={result.archive_member_count}")
    print(f"manifest_members={len(result.members)}")
    print("source_execution=forbidden")
    print("source_mutation=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
