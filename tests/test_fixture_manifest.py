"""Tests for the canonical fixture manifest and immutable records."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from artifact_auditor.fixture_manifest import (
    CANONICAL_FIXTURE_MANIFEST_OWNER,
    CANONICAL_FIXTURE_MANIFEST_TYPE,
    CANONICAL_FIXTURE_MANIFEST_VERSION,
    CanonicalFixtureManifest,
    FixtureIdentificationBasis,
    FixtureManifestError,
    parse_canonical_fixture_manifest,
)
from parsers.source_artifact import (
    capture_source_bytes,
    load_source_file,
)
from schemas.registry import MeasurementContour, ObservatoryMode


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = (
    _REPOSITORY_ROOT / "fixtures/canonical_fixture_manifest.json"
)
_LOADED_AT = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)


def _manifest_data() -> dict[str, object]:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _source_from_data(data: dict[str, object]):
    raw_bytes = (
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    return capture_source_bytes(
        raw_bytes,
        source_filename="canonical_fixture_manifest.json",
        source_path="fixtures/canonical_fixture_manifest.json",
        loaded_at=_LOADED_AT,
    )


def _parse_data(data: dict[str, object]) -> CanonicalFixtureManifest:
    return parse_canonical_fixture_manifest(_source_from_data(data))


def _committed_manifest() -> CanonicalFixtureManifest:
    source = load_source_file(
        _MANIFEST_PATH,
        source_path="fixtures/canonical_fixture_manifest.json",
        loaded_at=_LOADED_AT,
    )
    return parse_canonical_fixture_manifest(source)


class CommittedManifestTests(unittest.TestCase):
    """Exercise the committed manifest and fixture byte contract."""

    def test_committed_manifest_preserves_inventory_metadata(self) -> None:
        manifest = _committed_manifest()

        self.assertEqual(
            manifest.manifest_type,
            CANONICAL_FIXTURE_MANIFEST_TYPE,
        )
        self.assertEqual(
            manifest.manifest_version,
            CANONICAL_FIXTURE_MANIFEST_VERSION,
        )
        self.assertEqual(
            manifest.manifest_owner,
            CANONICAL_FIXTURE_MANIFEST_OWNER,
        )
        self.assertEqual(manifest.upstream_release, "v1.8.0")
        self.assertEqual(manifest.upstream_milestone, "M16")
        self.assertEqual(
            manifest.fixture_order,
            "fixture_path_lexicographic",
        )
        self.assertEqual(manifest.fixture_count, 6)
        self.assertEqual(
            manifest.copy_requirement,
            "unchanged_upstream_bytes",
        )
        self.assertEqual(manifest.raw_digest_contract.algorithm, "sha256")
        self.assertEqual(
            manifest.raw_digest_contract.scope,
            "raw_source_bytes",
        )
        self.assertEqual(
            manifest.raw_digest_contract.origin,
            "observatory_calculated",
        )
        self.assertIs(
            manifest.parsed_artifact.source_artifact,
            manifest.source_artifact,
        )
        self.assertEqual(
            manifest.content_sha256,
            manifest.source_artifact.content_sha256,
        )

    def test_every_fixture_matches_committed_raw_bytes(self) -> None:
        manifest = _committed_manifest()

        for record in manifest.fixtures:
            with self.subTest(fixture_path=record.fixture_path):
                path = _REPOSITORY_ROOT / record.fixture_path
                source = load_source_file(
                    path,
                    source_path=record.fixture_path,
                    loaded_at=_LOADED_AT,
                )

                self.assertTrue(record.matches_source(source))
                self.assertEqual(record.byte_length, path.stat().st_size)
                self.assertEqual(
                    record.raw_source_sha256,
                    source.content_sha256,
                )

    def test_lookups_and_schema_free_view_are_exact(self) -> None:
        manifest = _committed_manifest()
        schema_free = manifest.schema_free_fixtures

        self.assertEqual(len(schema_free), 1)
        self.assertEqual(
            schema_free[0].fixture_path,
            "fixtures/comparative_architecture/"
            "workload_profile_v1.json",
        )
        self.assertIs(
            schema_free[0].identification_basis,
            FixtureIdentificationBasis.EXACT_PATH_AND_RAW_DIGEST,
        )
        for record in manifest.fixtures:
            self.assertIs(
                manifest.fixture_for_path(record.fixture_path),
                record,
            )
            self.assertIs(
                manifest.fixture_for_upstream_path(
                    record.upstream_source_path
                ),
                record,
            )
        with self.assertRaises(KeyError):
            manifest.fixture_for_path("fixtures/missing.json")
        with self.assertRaisesRegex(
            FixtureManifestError,
            "fixture_path must be a string",
        ):
            manifest.fixture_for_path(76)

    def test_measurement_contours_remain_separate(self) -> None:
        manifest = _committed_manifest()
        contours = tuple(
            fixture.measurement_contour
            for fixture in manifest.fixtures
        )

        self.assertEqual(
            contours.count(MeasurementContour.COMPARATIVE_ARCHITECTURE),
            4,
        )
        self.assertEqual(
            contours.count(MeasurementContour.HARDWARE_SENSITIVITY),
            2,
        )
        self.assertTrue(
            all(
                fixture.observatory_modes
                == (ObservatoryMode.ARTIFACT_AUDITOR,)
                for fixture in manifest.fixtures
            )
        )


class CanonicalFixtureRecordTests(unittest.TestCase):
    """Exercise identity, provenance, and raw-source matching."""

    def test_identification_basis_relations_are_enforced(self) -> None:
        manifest = _committed_manifest()
        embedded = manifest.fixtures[0]
        schema_free = manifest.schema_free_fixtures[0]
        cases = (
            (
                embedded,
                {"fixture_path": "other/file.json"},
                "must be below fixtures",
            ),
            (
                embedded,
                {"source_filename": "other.json"},
                "must match the fixture path basename",
            ),
            (
                embedded,
                {"upstream_source_path": "/absolute.json"},
                "relative POSIX path",
            ),
            (
                embedded,
                {"upstream_schema_identifier": None},
                "requires identifier and version",
            ),
            (
                embedded,
                {"upstream_schema_version": "2"},
                "version must match",
            ),
            (
                embedded,
                {
                    "identification_basis":
                        FixtureIdentificationBasis
                        .EXACT_PATH_AND_RAW_DIGEST,
                },
                "must not assign upstream schema metadata",
            ),
            (
                schema_free,
                {
                    "identification_basis":
                        FixtureIdentificationBasis
                        .EMBEDDED_SCHEMA_AND_RAW_DIGEST,
                },
                "requires identifier and version",
            ),
            (
                embedded,
                {"producer_path": None, "producer_version": "1"},
                "producer_version requires producer_path",
            ),
        )

        for record, changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    FixtureManifestError,
                    message,
                ):
                    replace(record, **changes)

    def test_record_fields_require_exact_types_and_values(self) -> None:
        record = _committed_manifest().fixtures[0]
        mode = ObservatoryMode.ARTIFACT_AUDITOR
        cases = (
            (
                {"identification_basis": "embedded"},
                "identification_basis must be",
            ),
            (
                {"measurement_contour": "comparative"},
                "measurement_contour must be",
            ),
            ({"observatory_modes": [mode]}, "must be a tuple"),
            ({"observatory_modes": ()}, "must not be empty"),
            (
                {"observatory_modes": (mode, mode)},
                "observatory_modes must be unique",
            ),
            ({"byte_length": True}, "byte_length must be an integer"),
            ({"byte_length": 0}, "byte_length must be positive"),
            (
                {"raw_source_sha256": "A" * 64},
                "64 lowercase hexadecimal",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    FixtureManifestError,
                    message,
                ):
                    replace(record, **changes)

    def test_source_matching_rejects_each_identity_mismatch(self) -> None:
        record = _committed_manifest().fixtures[0]
        path = _REPOSITORY_ROOT / record.fixture_path
        raw_bytes = path.read_bytes()
        matching = capture_source_bytes(
            raw_bytes,
            source_filename=record.source_filename,
            loaded_at=_LOADED_AT,
        )
        wrong_name = capture_source_bytes(
            raw_bytes,
            source_filename="other.json",
            loaded_at=_LOADED_AT,
        )
        wrong_bytes = capture_source_bytes(
            b"{}\n",
            source_filename=record.source_filename,
            loaded_at=_LOADED_AT,
        )

        self.assertTrue(record.matches_source(matching))
        self.assertFalse(record.matches_source(wrong_name))
        self.assertFalse(record.matches_source(wrong_bytes))
        object.__setattr__(matching, "raw_bytes", b"changed")
        self.assertFalse(record.matches_source(matching))
        with self.assertRaisesRegex(
            FixtureManifestError,
            "source must be a SourceArtifact",
        ):
            record.matches_source(raw_bytes)


class CanonicalFixtureManifestTests(unittest.TestCase):
    """Exercise manifest-level ordering and source relations."""

    def test_direct_model_rejects_invalid_inventory_relations(self) -> None:
        manifest = _committed_manifest()
        fixtures = manifest.fixtures
        cases = (
            ({"source_artifact": "source"}, "source_artifact must be"),
            ({"parsed_artifact": "parsed"}, "parsed_artifact must be"),
            ({"manifest_type": "other"}, "unsupported canonical"),
            ({"fixture_count": 7}, "fixture_count does not match"),
            ({"fixtures": ()}, "fixtures must be a nonempty tuple"),
            (
                {"fixtures": tuple(reversed(fixtures))},
                "lexicographic order",
            ),
            (
                {"fixtures": (fixtures[0],) * len(fixtures)},
                "fixture paths must be unique",
            ),
            (
                {"raw_digest_contract": "contract"},
                "must be a RawDigestContract",
            ),
            (
                {"copy_requirement": "normalized"},
                "copy_requirement must be",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    FixtureManifestError,
                    message,
                ):
                    replace(manifest, **changes)


class ManifestParsingTests(unittest.TestCase):
    """Exercise strict JSON fields, types, enums, and error paths."""

    def test_parser_requires_exact_fields_at_each_level(self) -> None:
        cases = []

        missing_root = _manifest_data()
        missing_root.pop("manifest_owner")
        cases.append((missing_root, "$", "missing fields"))

        extra_root = _manifest_data()
        extra_root["unexpected"] = True
        cases.append((extra_root, "$", "unexpected fields"))

        missing_digest = _manifest_data()
        missing_digest["raw_digest_contract"].pop("scope")
        cases.append(
            (
                missing_digest,
                "$.raw_digest_contract",
                "missing fields",
            )
        )

        extra_fixture = _manifest_data()
        extra_fixture["fixtures"][0]["unexpected"] = 76
        cases.append(
            (
                extra_fixture,
                "$.fixtures[0]",
                "unexpected fields",
            )
        )

        for data, json_path, message in cases:
            with self.subTest(json_path=json_path):
                with self.assertRaises(FixtureManifestError) as caught:
                    _parse_data(data)

                self.assertEqual(caught.exception.json_path, json_path)
                self.assertIn(message, caught.exception.message)

    def test_parser_reports_enum_errors_at_exact_json_paths(self) -> None:
        cases = (
            (
                "identification_basis",
                "unknown_basis",
                "$.fixtures[0].identification_basis",
                "unknown identification basis",
            ),
            (
                "measurement_contour",
                "unknown_contour",
                "$.fixtures[0].measurement_contour",
                "unknown measurement contour",
            ),
        )

        for field, value, json_path, message in cases:
            with self.subTest(field=field):
                data = _manifest_data()
                data["fixtures"][0][field] = value

                with self.assertRaises(FixtureManifestError) as caught:
                    _parse_data(data)

                self.assertEqual(caught.exception.json_path, json_path)
                self.assertIn(message, caught.exception.message)

        data = _manifest_data()
        data["fixtures"][0]["observatory_modes"][0] = "unknown_mode"
        with self.assertRaises(FixtureManifestError) as caught:
            _parse_data(data)

        self.assertEqual(
            caught.exception.json_path,
            "$.fixtures[0].observatory_modes[0]",
        )
        self.assertIn("unknown Observatory mode", caught.exception.message)

    def test_parser_reports_type_errors_at_exact_json_paths(self) -> None:
        cases = (
            (
                "fixtures",
                {},
                "$.fixtures",
                "value must be an array",
            ),
            (
                "fixture_count",
                True,
                "$.fixture_count",
                "value must be an integer",
            ),
        )

        for field, value, json_path, message in cases:
            with self.subTest(field=field):
                data = _manifest_data()
                data[field] = value

                with self.assertRaises(FixtureManifestError) as caught:
                    _parse_data(data)

                self.assertEqual(caught.exception.json_path, json_path)
                self.assertEqual(caught.exception.message, message)

        data = _manifest_data()
        data["fixtures"][0]["observatory_modes"] = "artifact_auditor"
        with self.assertRaises(FixtureManifestError) as caught:
            _parse_data(data)

        self.assertEqual(
            caught.exception.json_path,
            "$.fixtures[0].observatory_modes",
        )
        self.assertEqual(
            caught.exception.message,
            "value must be an array",
        )

    def test_parser_rejects_wrong_source_type_and_integrity(self) -> None:
        with self.assertRaisesRegex(
            FixtureManifestError,
            "source must be a SourceArtifact",
        ):
            parse_canonical_fixture_manifest(b"{}")

        source = _source_from_data(_manifest_data())
        object.__setattr__(source, "raw_bytes", b"changed")
        with self.assertRaisesRegex(
            FixtureManifestError,
            "integrity verification failed",
        ):
            parse_canonical_fixture_manifest(source)


if __name__ == "__main__":
    unittest.main()
