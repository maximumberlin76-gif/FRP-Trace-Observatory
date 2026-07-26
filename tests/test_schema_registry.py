"""Tests for the exact upstream compatibility registry."""

from __future__ import annotations

import unittest
from collections import Counter
from dataclasses import FrozenInstanceError, replace

from schemas.registry import (
    AUDITED_UPSTREAM_RELEASE,
    ArtifactFormat,
    COMPATIBILITY_RECORDS,
    CompatibilityRecord,
    IdentifierField,
    MeasurementContour,
    ObservatoryMode,
    RegistryError,
    SchemaEvidenceKind,
    UnsupportedArtifactKindError,
    UnknownArtifactIdentifierError,
    records_for_identifier,
    resolve_compatibility_record,
)


_STRUCTURED_IDENTIFIER = "frp.structured_output.v1.7.0"
_VECTOR_IDENTIFIER = "frp.m15.vector.v1"
_ARCHITECTURE_IDENTIFIER = (
    "frp.benchmark.architecture_comparison.v1"
)


def _record(
    identifier: str = "frp.test.artifact.v1",
    *,
    identifier_field: IdentifierField = IdentifierField.SCHEMA,
    schema_version: str = "1",
    artifact_format: ArtifactFormat = ArtifactFormat.JSON,
    evidence_kind: SchemaEvidenceKind = (
        SchemaEvidenceKind.PRODUCER_DECLARATION
    ),
) -> CompatibilityRecord:
    producer_path = "tools/producer.py"
    fixture_path = "fixtures/test_artifact_v1.json"
    committed = evidence_kind is SchemaEvidenceKind.COMMITTED_ARTIFACT
    return CompatibilityRecord(
        identifier=identifier,
        identifier_field=identifier_field,
        schema_version=schema_version,
        artifact_format=artifact_format,
        artifact_kind=None,
        measurement_contour=MeasurementContour.STRUCTURED_OUTPUT,
        producer_path=None if committed else producer_path,
        producer_version=None,
        evidence_kind=evidence_kind,
        evidence_path=fixture_path if committed else producer_path,
        canonical_fixture_path=fixture_path if committed else None,
        observatory_modes=(ObservatoryMode.ARTIFACT_AUDITOR,),
    )


class CompatibilityRecordTests(unittest.TestCase):
    """Exercise one immutable registry entry."""

    def test_record_retains_exact_dispatch_identity(self) -> None:
        record = _record()

        self.assertEqual(
            record.dispatch_key,
            (
                IdentifierField.SCHEMA,
                "frp.test.artifact.v1",
                None,
            ),
        )
        self.assertEqual(
            record.upstream_release,
            AUDITED_UPSTREAM_RELEASE,
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(record, "schema_version", "2")

    def test_identifier_requires_frp_prefix_and_version_suffix(
        self,
    ) -> None:
        record = _record()

        with self.assertRaisesRegex(
            RegistryError,
            "identifier must begin with 'frp.'",
        ):
            replace(
                record,
                identifier="external.test.artifact.v1",
            )

        with self.assertRaisesRegex(
            RegistryError,
            "schema_version must match the identifier suffix",
        ):
            replace(
                record,
                schema_version="2",
            )

    def test_repository_paths_require_relative_posix_form(self) -> None:
        record = _record()
        invalid_paths = (
            "/tools/producer.py",
            "tools\\producer.py",
            "tools//producer.py",
            "tools/../producer.py",
            "tools/./producer.py",
        )

        for invalid_path in invalid_paths:
            with self.subTest(invalid_path=invalid_path):
                with self.assertRaisesRegex(
                    RegistryError,
                    "producer_path must",
                ):
                    replace(
                        record,
                        producer_path=invalid_path,
                    )

    def test_producer_declaration_requires_producer_path(self) -> None:
        record = _record()

        with self.assertRaisesRegex(
            RegistryError,
            "producer declarations require producer_path",
        ):
            replace(
                record,
                producer_path=None,
            )

    def test_committed_evidence_requires_matching_fixture(self) -> None:
        record = _record(
            evidence_kind=SchemaEvidenceKind.COMMITTED_ARTIFACT
        )

        with self.assertRaisesRegex(
            RegistryError,
            "committed artifacts require canonical_fixture_path",
        ):
            replace(
                record,
                canonical_fixture_path=None,
            )

        with self.assertRaisesRegex(
            RegistryError,
            "committed artifact evidence must be its fixture path",
        ):
            replace(
                record,
                evidence_path="fixtures/other.json",
            )

    def test_modes_require_nonempty_unique_enum_values(self) -> None:
        record = _record()

        with self.assertRaisesRegex(
            RegistryError,
            "observatory_modes must not be empty",
        ):
            replace(
                record,
                observatory_modes=(),
            )

        with self.assertRaisesRegex(
            RegistryError,
            "observatory_modes must be unique",
        ):
            replace(
                record,
                observatory_modes=(
                    ObservatoryMode.ARTIFACT_AUDITOR,
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
            )

        with self.assertRaisesRegex(
            RegistryError,
            "must contain ObservatoryMode values",
        ):
            replace(
                record,
                observatory_modes=("artifact_auditor",),
            )

    def test_outer_format_controls_identifier_field(self) -> None:
        json_record = _record()
        vector_record = _record(
            identifier=_VECTOR_IDENTIFIER,
            identifier_field=IdentifierField.FORMAT_VERSION,
            artifact_format=ArtifactFormat.M15_VECTOR_TEXT,
        )

        with self.assertRaisesRegex(
            RegistryError,
            "registered JSON artifacts must use the schema field",
        ):
            replace(
                json_record,
                identifier_field=IdentifierField.FORMAT_VERSION,
            )

        with self.assertRaisesRegex(
            RegistryError,
            "M15 vector text must use the format_version field",
        ):
            replace(
                vector_record,
                identifier_field=IdentifierField.SCHEMA,
            )


class RegistryInventoryTests(unittest.TestCase):
    """Exercise the audited compatibility inventory."""

    def test_inventory_has_exact_release_and_dispatch_keys(self) -> None:
        dispatch_keys = tuple(
            record.dispatch_key for record in COMPATIBILITY_RECORDS
        )

        self.assertEqual(AUDITED_UPSTREAM_RELEASE, "v1.8.0")
        self.assertEqual(len(COMPATIBILITY_RECORDS), 19)
        self.assertEqual(
            len(set(dispatch_keys)),
            len(dispatch_keys),
        )
        self.assertTrue(
            all(
                record.upstream_release == AUDITED_UPSTREAM_RELEASE
                for record in COMPATIBILITY_RECORDS
            )
        )

    def test_inventory_keeps_measurement_contours_separate(self) -> None:
        counts = Counter(
            record.measurement_contour
            for record in COMPATIBILITY_RECORDS
        )

        self.assertEqual(
            counts,
            {
                MeasurementContour.STRUCTURED_OUTPUT: 2,
                MeasurementContour.M3_BENCHMARK_MATRIX: 1,
                MeasurementContour.M15_IMPLEMENTATION_MAPPING: 11,
                MeasurementContour.COMPARATIVE_ARCHITECTURE: 3,
                MeasurementContour.HARDWARE_SENSITIVITY: 2,
            },
        )

    def test_inventory_keeps_evidence_classes_separate(self) -> None:
        counts = Counter(
            record.evidence_kind
            for record in COMPATIBILITY_RECORDS
        )

        self.assertEqual(
            counts,
            {
                SchemaEvidenceKind.PRODUCER_DECLARATION: 14,
                SchemaEvidenceKind.COMMITTED_ARTIFACT: 5,
            },
        )
        committed = tuple(
            record
            for record in COMPATIBILITY_RECORDS
            if record.evidence_kind
            is SchemaEvidenceKind.COMMITTED_ARTIFACT
        )
        self.assertTrue(
            all(
                record.evidence_path
                == record.canonical_fixture_path
                for record in committed
            )
        )

    def test_cycle_trace_routes_to_all_three_modes(self) -> None:
        record = resolve_compatibility_record(
            "frp.m15.cycle_exact_reference_trace.v1.7.0",
            declared_kind="cycle_exact_reference_trace",
        )

        self.assertEqual(
            record.observatory_modes,
            (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ObservatoryMode.TRACE_EXPLORER,
            ),
        )
        self.assertIs(
            record.measurement_contour,
            MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        )


class RegistryResolutionTests(unittest.TestCase):
    """Exercise exact identifier and kind resolution."""

    def test_shared_identifier_returns_both_registered_kinds(self) -> None:
        records = records_for_identifier(_STRUCTURED_IDENTIFIER)

        self.assertEqual(
            tuple(record.artifact_kind for record in records),
            ("demo", "self_test"),
        )
        self.assertIs(
            resolve_compatibility_record(
                _STRUCTURED_IDENTIFIER,
                declared_kind="demo",
            ),
            records[0],
        )
        self.assertIs(
            resolve_compatibility_record(
                _STRUCTURED_IDENTIFIER,
                declared_kind="self_test",
            ),
            records[1],
        )

    def test_shared_identifier_rejects_unsupported_kind(self) -> None:
        with self.assertRaises(UnsupportedArtifactKindError) as context:
            resolve_compatibility_record(
                _STRUCTURED_IDENTIFIER,
                declared_kind="benchmark_matrix",
            )

        error = context.exception
        self.assertEqual(error.identifier, _STRUCTURED_IDENTIFIER)
        self.assertEqual(error.declared_kind, "benchmark_matrix")
        self.assertEqual(
            error.expected_kinds,
            ("demo", "self_test"),
        )

    def test_kind_independent_identifier_ignores_declared_kind(
        self,
    ) -> None:
        record = resolve_compatibility_record(
            _ARCHITECTURE_IDENTIFIER,
            declared_kind="published_result",
        )

        self.assertIsNone(record.artifact_kind)
        self.assertIs(
            record.measurement_contour,
            MeasurementContour.COMPARATIVE_ARCHITECTURE,
        )

    def test_vector_identifier_uses_format_version_only(self) -> None:
        vector_record = resolve_compatibility_record(
            _VECTOR_IDENTIFIER,
            identifier_field=IdentifierField.FORMAT_VERSION,
        )

        self.assertIs(
            vector_record.artifact_format,
            ArtifactFormat.M15_VECTOR_TEXT,
        )
        self.assertIs(
            vector_record.identifier_field,
            IdentifierField.FORMAT_VERSION,
        )
        self.assertEqual(
            records_for_identifier(_VECTOR_IDENTIFIER),
            (),
        )

    def test_unknown_identifier_retains_exact_lookup_identity(
        self,
    ) -> None:
        identifier = "frp.unknown.schema.v1"

        with self.assertRaises(UnknownArtifactIdentifierError) as context:
            resolve_compatibility_record(identifier)

        error = context.exception
        self.assertEqual(error.identifier, identifier)
        self.assertIs(
            error.identifier_field,
            IdentifierField.SCHEMA,
        )
        self.assertEqual(
            str(error),
            f"unknown schema identifier: {identifier!r}",
        )

    def test_lookup_does_not_create_aliases(self) -> None:
        self.assertEqual(
            records_for_identifier(_STRUCTURED_IDENTIFIER.upper()),
            (),
        )
        self.assertEqual(
            records_for_identifier(
                f" {_STRUCTURED_IDENTIFIER}"
            ),
            (),
        )


if __name__ == "__main__":
    unittest.main()
