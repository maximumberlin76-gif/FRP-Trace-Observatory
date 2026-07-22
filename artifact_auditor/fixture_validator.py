"""Read-only validation of the committed canonical fixture inventory.

This module compares captured fixture bytes with the internal canonical
fixture manifest. It does not execute upstream validators, apply artifact
semantics, normalize source bytes, or replace artifact-specific validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from parsers.source_artifact import SourceArtifact

from .audit_report import (
    AuditValueSnapshot,
    CheckOutcome,
    SourceLocation,
    ValidationCategory,
)
from .fixture_manifest import (
    CanonicalFixtureManifest,
    CanonicalFixtureRecord,
)
from .validation_core import ValidationCheckSpec


__all__ = [
    "FixtureInventoryValidation",
    "FixtureValidationError",
    "validate_canonical_fixture_inventory",
    "validate_canonical_fixture_source",
]


class FixtureValidationError(ValueError):
    """Raised when fixture-validation inputs violate local invariants."""


def _validate_fixture_path(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise FixtureValidationError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise FixtureValidationError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if value.startswith("/") or "\\" in value or "\x00" in value:
        raise FixtureValidationError(
            f"{field_name} must be a relative POSIX path"
        )
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise FixtureValidationError(
            f"{field_name} must not contain empty or traversal segments"
        )


def _validate_source(source: SourceArtifact) -> None:
    if not isinstance(source, SourceArtifact):
        raise FixtureValidationError("source must be a SourceArtifact")


def _fixture_location(fixture_path: str) -> tuple[SourceLocation, ...]:
    return (SourceLocation(package_member=fixture_path),)


def _comparison_spec(
    *,
    check_code: str,
    category: ValidationCategory,
    expected: object,
    observed: object,
    source_locations: tuple[SourceLocation, ...],
    pass_message: str,
    fail_message: str,
) -> ValidationCheckSpec:
    matches = expected == observed
    return ValidationCheckSpec(
        check_code=check_code,
        category=category,
        outcome=(CheckOutcome.PASS if matches else CheckOutcome.FAIL),
        message=pass_message if matches else fail_message,
        source_locations=source_locations,
        expected=AuditValueSnapshot(expected),
        observed=AuditValueSnapshot(observed),
    )


def validate_canonical_fixture_source(
    record: CanonicalFixtureRecord,
    source: SourceArtifact,
) -> tuple[ValidationCheckSpec, ...]:
    """Compare one captured source with one exact manifest record."""

    if not isinstance(record, CanonicalFixtureRecord):
        raise FixtureValidationError(
            "record must be a CanonicalFixtureRecord"
        )
    _validate_source(source)
    location = _fixture_location(record.fixture_path)
    integrity_valid = source.verify_integrity()

    return (
        _comparison_spec(
            check_code="canonical_fixture_source_integrity",
            category=ValidationCategory.CONTAINER,
            expected=True,
            observed=integrity_valid,
            source_locations=location,
            pass_message=(
                "The captured fixture bytes retain their calculated "
                "raw-source identity."
            ),
            fail_message=(
                "The captured fixture bytes do not retain their "
                "calculated raw-source identity."
            ),
        ),
        _comparison_spec(
            check_code="canonical_fixture_filename",
            category=ValidationCategory.STRUCTURE,
            expected=record.source_filename,
            observed=source.source_filename,
            source_locations=location,
            pass_message=(
                "The captured source filename matches the canonical "
                "fixture record."
            ),
            fail_message=(
                "The captured source filename does not match the "
                "canonical fixture record."
            ),
        ),
        _comparison_spec(
            check_code="canonical_fixture_byte_length",
            category=ValidationCategory.CONTAINER,
            expected=record.byte_length,
            observed=source.byte_length,
            source_locations=location,
            pass_message=(
                "The captured byte length matches the canonical fixture "
                "record."
            ),
            fail_message=(
                "The captured byte length does not match the canonical "
                "fixture record."
            ),
        ),
        _comparison_spec(
            check_code="canonical_fixture_raw_digest",
            category=ValidationCategory.DIGEST,
            expected=record.raw_source_sha256,
            observed=source.content_sha256,
            source_locations=location,
            pass_message=(
                "The raw-source SHA-256 digest matches the canonical "
                "fixture record."
            ),
            fail_message=(
                "The raw-source SHA-256 digest does not match the "
                "canonical fixture record."
            ),
        ),
    )


def _presence_spec(
    fixture_path: str,
    *,
    present: bool,
) -> ValidationCheckSpec:
    return _comparison_spec(
        check_code="canonical_fixture_presence",
        category=ValidationCategory.STRUCTURE,
        expected=True,
        observed=present,
        source_locations=_fixture_location(fixture_path),
        pass_message=(
            "The canonical fixture inventory contains the required "
            "fixture member."
        ),
        fail_message=(
            "The canonical fixture inventory is missing the required "
            "fixture member."
        ),
    )


def _validate_fixture_sources(
    fixture_sources: Mapping[str, SourceArtifact],
) -> tuple[tuple[str, SourceArtifact], ...]:
    if not isinstance(fixture_sources, Mapping):
        raise FixtureValidationError(
            "fixture_sources must be a mapping"
        )

    captured_items: list[tuple[str, SourceArtifact]] = []
    for fixture_path, source in fixture_sources.items():
        _validate_fixture_path(fixture_path, "fixture source path")
        if not fixture_path.startswith("fixtures/"):
            raise FixtureValidationError(
                "fixture source paths must be below fixtures/"
            )
        _validate_source(source)
        captured_items.append((fixture_path, source))
    captured_items.sort(key=lambda item: item[0])
    return tuple(captured_items)


@dataclass(frozen=True, slots=True)
class FixtureInventoryValidation:
    """Immutable result for one canonical fixture inventory check."""

    manifest: CanonicalFixtureManifest
    check_specs: tuple[ValidationCheckSpec, ...]
    matched_fixture_paths: tuple[str, ...]
    missing_fixture_paths: tuple[str, ...]
    unexpected_fixture_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, CanonicalFixtureManifest):
            raise FixtureValidationError(
                "manifest must be a CanonicalFixtureManifest"
            )
        if not isinstance(self.check_specs, tuple) or not self.check_specs:
            raise FixtureValidationError(
                "check_specs must be a nonempty tuple"
            )
        if any(
            not isinstance(spec, ValidationCheckSpec)
            for spec in self.check_specs
        ):
            raise FixtureValidationError(
                "check_specs must contain ValidationCheckSpec values"
            )

        path_groups = (
            ("matched_fixture_paths", self.matched_fixture_paths),
            ("missing_fixture_paths", self.missing_fixture_paths),
            ("unexpected_fixture_paths", self.unexpected_fixture_paths),
        )
        for field_name, paths in path_groups:
            if not isinstance(paths, tuple):
                raise FixtureValidationError(
                    f"{field_name} must be a tuple"
                )
            for path in paths:
                _validate_fixture_path(path, field_name)
            if paths != tuple(sorted(paths)):
                raise FixtureValidationError(
                    f"{field_name} must be lexicographically ordered"
                )
            if len(set(paths)) != len(paths):
                raise FixtureValidationError(
                    f"{field_name} must contain unique paths"
                )

        matched = set(self.matched_fixture_paths)
        missing = set(self.missing_fixture_paths)
        unexpected = set(self.unexpected_fixture_paths)
        if matched & missing or matched & unexpected or missing & unexpected:
            raise FixtureValidationError(
                "fixture path result groups must be disjoint"
            )

        expected_paths = {
            record.fixture_path for record in self.manifest.fixtures
        }
        if matched | missing != expected_paths:
            raise FixtureValidationError(
                "matched and missing paths must cover the manifest"
            )

    @property
    def valid(self) -> bool:
        """Return whether every inventory check passed."""

        return all(
            spec.outcome is CheckOutcome.PASS
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


def validate_canonical_fixture_inventory(
    manifest: CanonicalFixtureManifest,
    fixture_sources: Mapping[str, SourceArtifact],
) -> FixtureInventoryValidation:
    """Validate one complete path-to-source inventory read-only."""

    if not isinstance(manifest, CanonicalFixtureManifest):
        raise FixtureValidationError(
            "manifest must be a CanonicalFixtureManifest"
        )
    captured_items = _validate_fixture_sources(fixture_sources)
    captured_by_path = dict(captured_items)

    expected_paths = tuple(
        record.fixture_path for record in manifest.fixtures
    )
    observed_paths = tuple(path for path, _ in captured_items)
    expected_set = set(expected_paths)
    observed_set = set(observed_paths)
    matched_paths = tuple(sorted(expected_set & observed_set))
    missing_paths = tuple(sorted(expected_set - observed_set))
    unexpected_paths = tuple(sorted(observed_set - expected_set))

    check_specs: list[ValidationCheckSpec] = [
        _comparison_spec(
            check_code="canonical_fixture_inventory_count",
            category=ValidationCategory.STRUCTURE,
            expected=manifest.fixture_count,
            observed=len(observed_paths),
            source_locations=(
                SourceLocation(json_path="$.fixture_count"),
            ),
            pass_message=(
                "The observed fixture count matches the canonical "
                "fixture manifest."
            ),
            fail_message=(
                "The observed fixture count does not match the "
                "canonical fixture manifest."
            ),
        ),
        _comparison_spec(
            check_code="canonical_fixture_inventory_membership",
            category=ValidationCategory.STRUCTURE,
            expected=expected_paths,
            observed=observed_paths,
            source_locations=(SourceLocation(json_path="$.fixtures"),),
            pass_message=(
                "The observed fixture paths exactly match the canonical "
                "fixture manifest."
            ),
            fail_message=(
                "The observed fixture paths do not exactly match the "
                "canonical fixture manifest."
            ),
        ),
    ]

    for record in manifest.fixtures:
        source = captured_by_path.get(record.fixture_path)
        check_specs.append(
            _presence_spec(
                record.fixture_path,
                present=source is not None,
            )
        )
        if source is not None:
            check_specs.extend(
                validate_canonical_fixture_source(record, source)
            )

    return FixtureInventoryValidation(
        manifest=manifest,
        check_specs=tuple(check_specs),
        matched_fixture_paths=matched_paths,
        missing_fixture_paths=missing_paths,
        unexpected_fixture_paths=unexpected_paths,
    )
