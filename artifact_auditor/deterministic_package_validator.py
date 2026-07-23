"""Read-only validation of the deterministic FRP M15 vector package.

The validator compares a registered package description with caller-captured
member bytes. It does not read directories, follow ``written_files`` paths,
execute a producer, regenerate vectors, or modify source artifacts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from parsers.artifact_dispatch import (
    ArtifactClassification,
    DispatchedArtifact,
    RegistrationStatus,
)
from parsers.json_artifact import (
    JsonArtifactError,
    JsonValue,
    ParsedJsonArtifact,
    parse_json_artifact,
)
from parsers.source_artifact import SourceArtifact

from .audit_report import (
    AuditValueSnapshot,
    CheckOutcome,
    SourceLocation,
    ValidationCategory,
)
from .validation_core import ValidationCheckSpec


__all__ = [
    "DeterministicPackageValidation",
    "DeterministicPackageValidationError",
    "validate_deterministic_package",
]


_SCHEMA = "frp.m15.rtl_comparison_vector_package.v1.7.0"
_KIND = "rtl_comparison_vector_package"
_RULE = "frp_prototype_v1_7_0.py"
_DIGEST_MANIFEST = "frp_m15_sha256_manifest.json"
_HEX = frozenset("0123456789abcdef")
_MEMBER_NAMES = tuple(
    sorted(
        (
            "frp_m15_kernel_vectors.vec",
            "frp_m15_pending_routes.trace",
            "frp_m15_scheduler_free_vectors.vec",
            "frp_m15_scheduler_7_1_vectors.vec",
            "frp_m15_scheduler_1_7_vectors.vec",
            "frp_m15_full_correlation_vectors.vec",
            "frp_m15_cell_trace.vec",
            "frp_m15_reference_preload.json",
            "frp_m15_trig_lut_q30.vec",
            _DIGEST_MANIFEST,
        )
    )
)
_INNER_MEMBER_NAMES = tuple(
    name for name in _MEMBER_NAMES if name != _DIGEST_MANIFEST
)


class DeterministicPackageValidationError(ValueError):
    """Raised when package-validation inputs violate local invariants."""


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _validate_name(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise DeterministicPackageValidationError(
            f"{field_name} must be a string"
        )
    if not value or value != value.strip():
        raise DeterministicPackageValidationError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if (
        value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise DeterministicPackageValidationError(
            f"{field_name} must be a plain package filename"
        )


def _validate_source(source: SourceArtifact) -> None:
    if not isinstance(source, SourceArtifact):
        raise DeterministicPackageValidationError(
            "package members must be SourceArtifact values"
        )


def _capture_inventory(
    member_sources: Mapping[str, SourceArtifact],
) -> tuple[tuple[str, SourceArtifact], ...]:
    if not isinstance(member_sources, Mapping):
        raise DeterministicPackageValidationError(
            "member_sources must be a mapping"
        )
    captured: list[tuple[str, SourceArtifact]] = []
    for name, source in member_sources.items():
        _validate_name(name, "package member name")
        _validate_source(source)
        captured.append((name, source))
    return tuple(sorted(captured, key=lambda item: item[0]))


def _parse_package(dispatched: DispatchedArtifact) -> ParsedJsonArtifact:
    if not isinstance(dispatched, DispatchedArtifact):
        raise DeterministicPackageValidationError(
            "dispatched must be a DispatchedArtifact"
        )
    parsed = dispatched.parsed_artifact
    record = dispatched.compatibility_record
    if (
        dispatched.classification is not ArtifactClassification.JSON
        or dispatched.registration.status
        is not RegistrationStatus.REGISTERED
        or not isinstance(parsed, ParsedJsonArtifact)
        or record is None
        or record.identifier != _SCHEMA
        or record.artifact_kind != _KIND
        or parsed.declared_schema_identifier != _SCHEMA
        or parsed.declared_kind != _KIND
    ):
        raise DeterministicPackageValidationError(
            "artifact is not the registered M15 vector package description"
        )
    return parsed


def _member_location(name: str) -> SourceLocation:
    return SourceLocation(package_member=name)


def _outer_location(index: int | None = None) -> SourceLocation:
    if index is None:
        return SourceLocation(json_path="$.manifest.files")
    return SourceLocation(
        json_path=f"$.manifest.files[{index}]",
        array_index=index,
    )


def _inner_location(name: str | None = None) -> SourceLocation:
    return SourceLocation(
        json_path=None if name is None else f'$["{name}"]',
        package_member=_DIGEST_MANIFEST,
    )


def _spec(
    code: str,
    category: ValidationCategory,
    valid: bool,
    locations: tuple[SourceLocation, ...],
    *,
    expected: object = True,
    observed: object | None = None,
) -> ValidationCheckSpec:
    relation = "matches" if valid else "does not match"
    return ValidationCheckSpec(
        check_code=code,
        category=category,
        outcome=CheckOutcome.PASS if valid else CheckOutcome.FAIL,
        message=(
            f"The {code.replace('_', ' ')} {relation} the upstream "
            "deterministic-package contract."
        ),
        source_locations=locations,
        expected=AuditValueSnapshot(expected),
        observed=AuditValueSnapshot(valid if observed is None else observed),
        upstream_rule_reference=_RULE,
    )


def _equal_spec(
    code: str,
    category: ValidationCategory,
    expected: object,
    observed: object,
    locations: tuple[SourceLocation, ...],
) -> ValidationCheckSpec:
    return _spec(
        code,
        category,
        expected == observed,
        locations,
        expected=expected,
        observed=observed,
    )


@dataclass(frozen=True, slots=True)
class _OuterEntry:
    name: str
    size_bytes: int
    sha256: str
    index: int


@dataclass(frozen=True, slots=True)
class _OuterView:
    shape_valid: bool
    file_count: int | str
    names: tuple[str, ...]
    entries: tuple[_OuterEntry, ...]

    @property
    def by_name(self) -> dict[str, _OuterEntry]:
        return {entry.name: entry for entry in self.entries}


def _invalid_name(index: int) -> str:
    return f"<invalid-name-at-index-{index}>"


def _read_outer(root: Mapping[str, JsonValue]) -> _OuterView:
    value = root.get("manifest")
    manifest = value if isinstance(value, Mapping) else None
    if manifest is None:
        return _OuterView(False, "<invalid>", (), ())

    count_value = manifest.get("file_count")
    count: int | str = count_value if _integer(count_value) else "<invalid>"
    files_value = manifest.get("files")
    files = files_value if isinstance(files_value, tuple) else None
    if files is None:
        return _OuterView(False, count, (), ())

    valid = set(manifest) == {"file_count", "files"}
    names: list[str] = []
    entries: list[_OuterEntry] = []
    for index, value in enumerate(files):
        row = value if isinstance(value, Mapping) else None
        if row is None:
            valid = False
            names.append(_invalid_name(index))
            continue
        name = row.get("name")
        size = row.get("size_bytes")
        digest = row.get("sha256")
        names.append(name if isinstance(name, str) else _invalid_name(index))
        row_valid = bool(
            set(row) == {"name", "size_bytes", "sha256"}
            and isinstance(name, str)
            and name not in {"", ".", ".."}
            and name == name.strip()
            and "/" not in name
            and "\\" not in name
            and "\x00" not in name
            and _integer(size)
            and size > 0
            and _digest(digest)
        )
        if not row_valid:
            valid = False
            continue
        entries.append(_OuterEntry(name, size, digest, index))

    valid = bool(
        valid
        and count == len(files)
        and len(entries) == len(files)
        and len({entry.name for entry in entries}) == len(entries)
    )
    return _OuterView(valid, count, tuple(names), tuple(entries))


@dataclass(frozen=True, slots=True)
class _InnerView:
    parsed: bool
    shape_valid: bool
    names: tuple[str, ...]
    digests: tuple[tuple[str, str], ...]

    @property
    def by_name(self) -> dict[str, str]:
        return dict(self.digests)


def _read_inner(source: SourceArtifact | None) -> _InnerView:
    if source is None:
        return _InnerView(False, False, (), ())
    try:
        parsed = parse_json_artifact(source)
    except JsonArtifactError:
        return _InnerView(False, False, (), ())
    names = tuple(parsed.root)
    digests = tuple(
        (name, value)
        for name, value in parsed.root.items()
        if isinstance(value, str) and _digest(value)
    )
    return _InnerView(
        parsed=True,
        shape_valid=(
            names == _INNER_MEMBER_NAMES
            and len(digests) == len(parsed.root)
        ),
        names=names,
        digests=digests,
    )


def _aggregate_digest(
    sources: Mapping[str, SourceArtifact],
) -> str | None:
    if any(name not in sources for name in _MEMBER_NAMES):
        return None
    digest = sha256()
    for name in _MEMBER_NAMES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(sources[name].raw_bytes)
    return digest.hexdigest()


def _member_specs(
    sources: Mapping[str, SourceArtifact],
    entries: Mapping[str, _OuterEntry],
) -> tuple[ValidationCheckSpec, ...]:
    specs: list[ValidationCheckSpec] = []
    for name in _MEMBER_NAMES:
        source = sources.get(name)
        entry = entries.get(name)
        member = _member_location(name)
        outer = _outer_location(entry.index if entry else None)
        specs.extend(
            (
                _spec(
                    "m15_package_member_presence",
                    ValidationCategory.DETERMINISTIC_PACKAGE,
                    source is not None,
                    (member,),
                ),
                _spec(
                    "m15_package_outer_member_declaration",
                    ValidationCategory.STRUCTURE,
                    entry is not None,
                    (outer, member),
                ),
            )
        )
        if source is None:
            continue
        specs.extend(
            (
                _spec(
                    "m15_package_member_source_integrity",
                    ValidationCategory.CONTAINER,
                    source.verify_integrity(),
                    (member,),
                ),
                _equal_spec(
                    "m15_package_member_filename",
                    ValidationCategory.STRUCTURE,
                    name,
                    source.source_filename,
                    (member,),
                ),
            )
        )
        if entry is None:
            continue
        locations = (outer, member)
        specs.extend(
            (
                _equal_spec(
                    "m15_package_member_byte_length",
                    ValidationCategory.CONTAINER,
                    entry.size_bytes,
                    source.byte_length,
                    locations,
                ),
                _equal_spec(
                    "m15_package_member_outer_digest",
                    ValidationCategory.DIGEST,
                    entry.sha256,
                    source.content_sha256,
                    locations,
                ),
            )
        )
    return tuple(specs)


def _inner_specs(
    inner: _InnerView,
    sources: Mapping[str, SourceArtifact],
) -> tuple[ValidationCheckSpec, ...]:
    location = _inner_location()
    specs: list[ValidationCheckSpec] = [
        _spec(
            "m15_package_inner_manifest_json",
            ValidationCategory.CONTAINER,
            inner.parsed,
            (location,),
        ),
        _equal_spec(
            "m15_package_inner_manifest_members",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _INNER_MEMBER_NAMES,
            inner.names,
            (location,),
        ),
        _spec(
            "m15_package_inner_manifest_shape",
            ValidationCategory.STRUCTURE,
            inner.shape_valid,
            (location,),
        ),
    ]
    digests = inner.by_name
    for name in _INNER_MEMBER_NAMES:
        source = sources.get(name)
        declared = digests.get(name)
        locations = (_inner_location(name), _member_location(name))
        if source is None or declared is None:
            specs.append(
                _spec(
                    "m15_package_inner_member_digest",
                    ValidationCategory.DIGEST,
                    False,
                    locations,
                )
            )
        else:
            specs.append(
                _equal_spec(
                    "m15_package_inner_member_digest",
                    ValidationCategory.DIGEST,
                    declared,
                    source.content_sha256,
                    locations,
                )
            )
    return tuple(specs)


@dataclass(frozen=True, slots=True)
class DeterministicPackageValidation:
    """Immutable result for one captured M15 deterministic package."""

    dispatched_artifact: DispatchedArtifact
    member_sources: tuple[tuple[str, SourceArtifact], ...]
    check_specs: tuple[ValidationCheckSpec, ...]
    matched_member_names: tuple[str, ...]
    missing_member_names: tuple[str, ...]
    unexpected_member_names: tuple[str, ...]
    computed_package_sha256: str | None

    def __post_init__(self) -> None:
        _parse_package(self.dispatched_artifact)
        if not isinstance(self.member_sources, tuple):
            raise DeterministicPackageValidationError(
                "member_sources must be a tuple"
            )
        for item in self.member_sources:
            if not isinstance(item, tuple) or len(item) != 2:
                raise DeterministicPackageValidationError(
                    "member_sources must contain name-source pairs"
                )
            _validate_name(item[0], "member_sources name")
            _validate_source(item[1])
        source_names = tuple(name for name, _ in self.member_sources)
        if source_names != tuple(sorted(source_names)):
            raise DeterministicPackageValidationError(
                "member_sources must be lexicographically ordered"
            )
        if len(set(source_names)) != len(source_names):
            raise DeterministicPackageValidationError(
                "member_sources must contain unique names"
            )
        if not isinstance(self.check_specs, tuple) or not self.check_specs:
            raise DeterministicPackageValidationError(
                "check_specs must be a nonempty tuple"
            )
        if any(
            not isinstance(spec, ValidationCheckSpec)
            for spec in self.check_specs
        ):
            raise DeterministicPackageValidationError(
                "check_specs must contain ValidationCheckSpec values"
            )

        groups = (
            ("matched_member_names", self.matched_member_names),
            ("missing_member_names", self.missing_member_names),
            ("unexpected_member_names", self.unexpected_member_names),
        )
        for field_name, names in groups:
            if not isinstance(names, tuple):
                raise DeterministicPackageValidationError(
                    f"{field_name} must be a tuple"
                )
            for name in names:
                _validate_name(name, field_name)
            if names != tuple(sorted(names)) or len(set(names)) != len(names):
                raise DeterministicPackageValidationError(
                    f"{field_name} must be ordered and unique"
                )

        matched = set(self.matched_member_names)
        missing = set(self.missing_member_names)
        unexpected = set(self.unexpected_member_names)
        if matched & missing or matched & unexpected or missing & unexpected:
            raise DeterministicPackageValidationError(
                "member-name result groups must be disjoint"
            )
        if matched | missing != set(_MEMBER_NAMES):
            raise DeterministicPackageValidationError(
                "matched and missing names must cover the package contract"
            )
        if matched | unexpected != set(source_names):
            raise DeterministicPackageValidationError(
                "result groups must cover all captured member names"
            )
        if self.computed_package_sha256 is not None and not _digest(
            self.computed_package_sha256
        ):
            raise DeterministicPackageValidationError(
                "computed_package_sha256 must be lowercase SHA-256 or None"
            )
        if bool(missing) != (self.computed_package_sha256 is None):
            raise DeterministicPackageValidationError(
                "computed digest presence must match package completeness"
            )

    @property
    def valid(self) -> bool:
        """Return whether every mandatory package check passed."""

        return all(
            not spec.mandatory or spec.outcome is CheckOutcome.PASS
            for spec in self.check_specs
        )

    @property
    def failed_check_specs(self) -> tuple[ValidationCheckSpec, ...]:
        """Return failed checks without changing execution order."""

        return tuple(
            spec
            for spec in self.check_specs
            if spec.outcome is CheckOutcome.FAIL
        )


def validate_deterministic_package(
    dispatched: DispatchedArtifact,
    member_sources: Mapping[str, SourceArtifact],
) -> DeterministicPackageValidation:
    """Compare one registered package description with captured members."""

    parsed = _parse_package(dispatched)
    captured = _capture_inventory(member_sources)
    sources = dict(captured)
    observed_names = tuple(name for name, _ in captured)
    expected = set(_MEMBER_NAMES)
    observed = set(observed_names)
    matched = tuple(sorted(expected & observed))
    missing = tuple(sorted(expected - observed))
    unexpected = tuple(sorted(observed - expected))

    outer = _read_outer(parsed.root)
    inner = _read_inner(sources.get(_DIGEST_MANIFEST))
    computed_digest = _aggregate_digest(sources)
    declared_digest = parsed.root.get("deterministic_package_digest")
    specs: list[ValidationCheckSpec] = [
        _equal_spec(
            "m15_package_captured_members",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            _MEMBER_NAMES,
            observed_names,
            (SourceLocation(json_path="$.manifest.files"),),
        ),
        _spec(
            "m15_package_outer_manifest_shape",
            ValidationCategory.STRUCTURE,
            outer.shape_valid,
            (SourceLocation(json_path="$.manifest"),),
        ),
        _equal_spec(
            "m15_package_outer_file_count",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            len(_MEMBER_NAMES),
            outer.file_count,
            (SourceLocation(json_path="$.manifest.file_count"),),
        ),
        _equal_spec(
            "m15_package_outer_member_order",
            ValidationCategory.ORDERING,
            _MEMBER_NAMES,
            outer.names,
            (SourceLocation(json_path="$.manifest.files"),),
        ),
        _spec(
            "m15_package_source_identity_uniqueness",
            ValidationCategory.CONTAINER,
            len({source.source_artifact_id for _, source in captured})
            == len(captured),
            (SourceLocation(json_path="$.manifest.files"),),
        ),
        _spec(
            "m15_package_declared_digest_syntax",
            ValidationCategory.DIGEST,
            _digest(declared_digest),
            (
                SourceLocation(
                    json_path="$.deterministic_package_digest"
                ),
            ),
        ),
    ]
    specs.extend(_member_specs(sources, outer.by_name))
    specs.extend(_inner_specs(inner, sources))
    expected_digest = (
        declared_digest
        if isinstance(declared_digest, str)
        else "<invalid-declared-digest>"
    )
    observed_digest = (
        computed_digest
        if computed_digest is not None
        else "<not-computed: missing package members>"
    )
    specs.append(
        _equal_spec(
            "m15_package_aggregate_digest",
            ValidationCategory.DETERMINISTIC_PACKAGE,
            expected_digest,
            observed_digest,
            (
                SourceLocation(
                    json_path="$.deterministic_package_digest"
                ),
            )
            + tuple(_member_location(name) for name in _MEMBER_NAMES),
        )
    )

    return DeterministicPackageValidation(
        dispatched_artifact=dispatched,
        member_sources=captured,
        check_specs=tuple(specs),
        matched_member_names=matched,
        missing_member_names=missing,
        unexpected_member_names=unexpected,
        computed_package_sha256=computed_digest,
    )
