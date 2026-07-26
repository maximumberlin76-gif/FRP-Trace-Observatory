"""Tests for read-only canonical fixture inventory validation."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

from artifact_auditor.audit_report import (
    CheckOutcome,
    ValidationCategory,
)
from artifact_auditor.fixture_manifest import (
    CanonicalFixtureManifest,
    parse_canonical_fixture_manifest,
)
from artifact_auditor.fixture_validator import (
    FixtureInventoryValidation,
    FixtureValidationError,
    validate_canonical_fixture_inventory,
    validate_canonical_fixture_source,
)
from parsers.source_artifact import (
    SourceArtifact,
    capture_source_bytes,
    load_source_file,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = (
    _REPOSITORY_ROOT / "fixtures/canonical_fixture_manifest.json"
)
_LOADED_AT = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)


def _manifest() -> CanonicalFixtureManifest:
    source = load_source_file(
        _MANIFEST_PATH,
        source_path="fixtures/canonical_fixture_manifest.json",
        loaded_at=_LOADED_AT,
    )
    return parse_canonical_fixture_manifest(source)


def _fixture_source(fixture_path: str) -> SourceArtifact:
    path = _REPOSITORY_ROOT / fixture_path
    return load_source_file(
        path,
        source_path=fixture_path,
        loaded_at=_LOADED_AT,
    )


def _fixture_sources(
    manifest: CanonicalFixtureManifest,
) -> dict[str, SourceArtifact]:
    return {
        record.fixture_path: _fixture_source(record.fixture_path)
        for record in manifest.fixtures
    }


def _failed_codes(
    validation: FixtureInventoryValidation,
) -> tuple[str, ...]:
    return tuple(
        spec.check_code for spec in validation.failed_check_specs
    )


class FixtureSourceValidationTests(unittest.TestCase):
    """Exercise exact source identity comparisons."""

    def test_matching_source_produces_four_ordered_passes(self) -> None:
        manifest = _manifest()
        record = manifest.fixtures[0]
        source = _fixture_source(record.fixture_path)

        specs = validate_canonical_fixture_source(record, source)

        self.assertEqual(
            tuple(spec.check_code for spec in specs),
            (
                "canonical_fixture_source_integrity",
                "canonical_fixture_filename",
                "canonical_fixture_byte_length",
                "canonical_fixture_raw_digest",
            ),
        )
        self.assertEqual(
            tuple(spec.category for spec in specs),
            (
                ValidationCategory.CONTAINER,
                ValidationCategory.STRUCTURE,
                ValidationCategory.CONTAINER,
                ValidationCategory.DIGEST,
            ),
        )
        self.assertTrue(
            all(spec.outcome is CheckOutcome.PASS for spec in specs)
        )
        self.assertTrue(
            all(
                spec.source_locations[0].package_member
                == record.fixture_path
                for spec in specs
            )
        )
        self.assertEqual(specs[1].expected.value, record.source_filename)
        self.assertEqual(specs[1].observed.value, source.source_filename)
        self.assertEqual(specs[2].expected.value, record.byte_length)
        self.assertEqual(specs[2].observed.value, source.byte_length)
        self.assertEqual(
            specs[3].expected.value,
            record.raw_source_sha256,
        )
        self.assertEqual(specs[3].observed.value, source.content_sha256)

    def test_each_source_mismatch_remains_a_distinct_failure(self) -> None:
        manifest = _manifest()
        record = manifest.fixtures[0]
        raw_bytes = (
            _REPOSITORY_ROOT / record.fixture_path
        ).read_bytes()
        wrong_name = capture_source_bytes(
            raw_bytes,
            source_filename="other.json",
            loaded_at=_LOADED_AT,
        )
        wrong_bytes = capture_source_bytes(
            raw_bytes + b" ",
            source_filename=record.source_filename,
            loaded_at=_LOADED_AT,
        )
        tampered = capture_source_bytes(
            raw_bytes,
            source_filename=record.source_filename,
            loaded_at=_LOADED_AT,
        )
        object.__setattr__(tampered, "raw_bytes", b"changed")
        cases = (
            (
                wrong_name,
                ("canonical_fixture_filename",),
            ),
            (
                wrong_bytes,
                (
                    "canonical_fixture_byte_length",
                    "canonical_fixture_raw_digest",
                ),
            ),
            (
                tampered,
                ("canonical_fixture_source_integrity",),
            ),
        )

        for source, expected_codes in cases:
            with self.subTest(expected_codes=expected_codes):
                specs = validate_canonical_fixture_source(
                    record,
                    source,
                )
                failed_codes = tuple(
                    spec.check_code
                    for spec in specs
                    if spec.outcome is CheckOutcome.FAIL
                )

                self.assertEqual(failed_codes, expected_codes)

    def test_source_validation_rejects_wrong_input_types(self) -> None:
        manifest = _manifest()
        record = manifest.fixtures[0]
        source = _fixture_source(record.fixture_path)
        cases = (
            (
                "record",
                source,
                "record must be a CanonicalFixtureRecord",
            ),
            (
                record,
                b"source",
                "source must be a SourceArtifact",
            ),
        )

        for target_record, target_source, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    FixtureValidationError,
                    message,
                ):
                    validate_canonical_fixture_source(
                        target_record,
                        target_source,
                    )


class CompleteInventoryValidationTests(unittest.TestCase):
    """Exercise the committed complete inventory."""

    def test_complete_inventory_produces_all_ordered_passes(self) -> None:
        manifest = _manifest()
        sources = _fixture_sources(manifest)
        original_bytes = {
            path: source.raw_bytes
            for path, source in sources.items()
        }

        validation = validate_canonical_fixture_inventory(
            manifest,
            sources,
        )

        expected_paths = tuple(
            record.fixture_path for record in manifest.fixtures
        )
        self.assertIs(validation.manifest, manifest)
        self.assertTrue(validation.valid)
        self.assertEqual(validation.failed_check_specs, ())
        self.assertEqual(validation.matched_fixture_paths, expected_paths)
        self.assertEqual(validation.missing_fixture_paths, ())
        self.assertEqual(validation.unexpected_fixture_paths, ())
        self.assertEqual(len(validation.check_specs), 32)
        self.assertEqual(
            validation.check_specs[0].check_code,
            "canonical_fixture_inventory_count",
        )
        self.assertEqual(
            validation.check_specs[1].check_code,
            "canonical_fixture_inventory_membership",
        )
        self.assertEqual(
            tuple(
                spec.check_code for spec in validation.check_specs
            ).count("canonical_fixture_presence"),
            6,
        )
        self.assertTrue(
            all(
                spec.outcome is CheckOutcome.PASS
                for spec in validation.check_specs
            )
        )
        self.assertEqual(
            {
                path: source.raw_bytes
                for path, source in sources.items()
            },
            original_bytes,
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(validation, "matched_fixture_paths", ())

    def test_mapping_order_is_normalized_lexicographically(self) -> None:
        manifest = _manifest()
        sources = _fixture_sources(manifest)
        reversed_sources = dict(reversed(tuple(sources.items())))

        validation = validate_canonical_fixture_inventory(
            manifest,
            reversed_sources,
        )

        self.assertTrue(validation.valid)
        self.assertEqual(
            validation.matched_fixture_paths,
            tuple(sorted(sources)),
        )
        self.assertEqual(
            validation.check_specs[1].observed.value,
            tuple(sorted(sources)),
        )


class IncompleteInventoryValidationTests(unittest.TestCase):
    """Exercise missing, unexpected, and mismatched fixture results."""

    def test_missing_fixture_is_reported_without_source_checks(self) -> None:
        manifest = _manifest()
        sources = _fixture_sources(manifest)
        missing_path = manifest.fixtures[0].fixture_path
        sources.pop(missing_path)

        validation = validate_canonical_fixture_inventory(
            manifest,
            sources,
        )

        self.assertFalse(validation.valid)
        self.assertEqual(
            validation.matched_fixture_paths,
            tuple(sorted(sources)),
        )
        self.assertEqual(
            validation.missing_fixture_paths,
            (missing_path,),
        )
        self.assertEqual(validation.unexpected_fixture_paths, ())
        self.assertEqual(
            _failed_codes(validation),
            (
                "canonical_fixture_inventory_count",
                "canonical_fixture_inventory_membership",
                "canonical_fixture_presence",
            ),
        )
        self.assertEqual(len(validation.check_specs), 28)

    def test_unexpected_fixture_is_separated_from_manifest_paths(self) -> None:
        manifest = _manifest()
        sources = _fixture_sources(manifest)
        unexpected_path = "fixtures/unexpected.json"
        sources[unexpected_path] = capture_source_bytes(
            b"{}\n",
            source_filename="unexpected.json",
            source_path=unexpected_path,
            loaded_at=_LOADED_AT,
        )

        validation = validate_canonical_fixture_inventory(
            manifest,
            sources,
        )

        self.assertFalse(validation.valid)
        self.assertEqual(validation.missing_fixture_paths, ())
        self.assertEqual(
            validation.unexpected_fixture_paths,
            (unexpected_path,),
        )
        self.assertEqual(
            _failed_codes(validation),
            (
                "canonical_fixture_inventory_count",
                "canonical_fixture_inventory_membership",
            ),
        )
        self.assertEqual(len(validation.check_specs), 32)

    def test_mismatched_source_fails_only_raw_identity_checks(self) -> None:
        manifest = _manifest()
        sources = _fixture_sources(manifest)
        record = manifest.fixtures[0]
        sources[record.fixture_path] = capture_source_bytes(
            b"{}\n",
            source_filename=record.source_filename,
            source_path=record.fixture_path,
            loaded_at=_LOADED_AT,
        )

        validation = validate_canonical_fixture_inventory(
            manifest,
            sources,
        )

        self.assertFalse(validation.valid)
        self.assertEqual(validation.missing_fixture_paths, ())
        self.assertEqual(validation.unexpected_fixture_paths, ())
        self.assertEqual(
            _failed_codes(validation),
            (
                "canonical_fixture_byte_length",
                "canonical_fixture_raw_digest",
            ),
        )


class InventoryInputValidationTests(unittest.TestCase):
    """Exercise mapping and fixture-path input guards."""

    def test_inventory_rejects_invalid_manifest_and_mapping(self) -> None:
        manifest = _manifest()
        sources = _fixture_sources(manifest)
        path, source = next(iter(sources.items()))
        cases = (
            (
                "manifest",
                sources,
                "manifest must be a CanonicalFixtureManifest",
            ),
            (
                manifest,
                [source],
                "fixture_sources must be a mapping",
            ),
            (
                manifest,
                {76: source},
                "fixture source path must be a string",
            ),
            (
                manifest,
                {"/fixtures/file.json": source},
                "relative POSIX path",
            ),
            (
                manifest,
                {"fixtures/../file.json": source},
                "traversal segments",
            ),
            (
                manifest,
                {"outside/file.json": source},
                "must be below fixtures",
            ),
            (
                manifest,
                {path: "source"},
                "source must be a SourceArtifact",
            ),
        )

        for target_manifest, target_sources, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    FixtureValidationError,
                    message,
                ):
                    validate_canonical_fixture_inventory(
                        target_manifest,
                        target_sources,
                    )


class FixtureInventoryValidationModelTests(unittest.TestCase):
    """Exercise immutable result-group invariants."""

    def test_direct_model_rejects_invalid_result_relations(self) -> None:
        manifest = _manifest()
        validation = validate_canonical_fixture_inventory(
            manifest,
            _fixture_sources(manifest),
        )
        matched = validation.matched_fixture_paths
        cases = (
            ({"manifest": "manifest"}, "manifest must be"),
            ({"check_specs": []}, "check_specs must be a nonempty tuple"),
            ({"check_specs": ()}, "check_specs must be a nonempty tuple"),
            (
                {"check_specs": ("spec",)},
                "must contain ValidationCheckSpec",
            ),
            (
                {"matched_fixture_paths": list(matched)},
                "matched_fixture_paths must be a tuple",
            ),
            (
                {"matched_fixture_paths": tuple(reversed(matched))},
                "must be lexicographically ordered",
            ),
            (
                {"matched_fixture_paths": (matched[0],) * len(matched)},
                "must contain unique paths",
            ),
            (
                {
                    "missing_fixture_paths": (matched[0],),
                },
                "result groups must be disjoint",
            ),
            (
                {
                    "matched_fixture_paths": matched[:-1],
                },
                "must cover the manifest",
            ),
            (
                {
                    "unexpected_fixture_paths":
                        ("fixtures/../unexpected.json",),
                },
                "traversal segments",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    FixtureValidationError,
                    message,
                ):
                    replace(validation, **changes)


if __name__ == "__main__":
    unittest.main()
