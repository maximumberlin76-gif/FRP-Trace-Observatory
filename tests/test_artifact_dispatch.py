"""Tests for read-only artifact classification and registry dispatch."""

from __future__ import annotations

import json
import unittest
from codecs import BOM_UTF8
from dataclasses import FrozenInstanceError, replace

from parsers.artifact_dispatch import (
    ArtifactClassification,
    ArtifactDispatchError,
    DispatchedArtifact,
    RegistrationResult,
    RegistrationStatus,
    dispatch_artifact,
)
from parsers.json_artifact import JsonSyntaxError, ParsedJsonArtifact
from parsers.m15_vector import (
    M15_VECTOR_FORMAT_VERSION,
    ROUTE_TRACE_COLUMNS,
    M15VectorArtifact,
    M15VectorMetadataError,
)
from parsers.source_artifact import SourceArtifact, capture_source_bytes
from schemas.registry import IdentifierField


_STRUCTURED_SCHEMA = "frp.structured_output.v1.7.0"
_ARCHITECTURE_SCHEMA = "frp.benchmark.architecture_comparison.v1"
_MISSING = object()


def _source(
    raw_bytes: bytes,
    filename: str = "artifact.bin",
) -> SourceArtifact:
    return capture_source_bytes(
        raw_bytes,
        source_filename=filename,
        source_path=f"tests/generated/{filename}",
    )


def _json_bytes(
    *,
    schema: object = _STRUCTURED_SCHEMA,
    kind: object = "demo",
) -> bytes:
    root: dict[str, object] = {"value": 76}
    if schema is not _MISSING:
        root["schema"] = schema
    if kind is not _MISSING:
        root["kind"] = kind
    return (
        json.dumps(
            root,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _dispatch_json(
    *,
    schema: object = _STRUCTURED_SCHEMA,
    kind: object = "demo",
) -> DispatchedArtifact:
    return dispatch_artifact(
        _source(
            _json_bytes(schema=schema, kind=kind),
            "artifact.json",
        )
    )


def _vector_bytes(
    *,
    format_version: str = M15_VECTOR_FORMAT_VERSION,
    with_bom: bool = False,
) -> bytes:
    metadata = (
        ("format_version", format_version),
        ("trace_kind", "pending_routes"),
        ("column_definition", list(ROUTE_TRACE_COLUMNS)),
    )
    lines = [
        f"# {key}="
        + json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for key, value in metadata
    ]
    lines.append("# " + " | ".join(ROUTE_TRACE_COLUMNS))
    lines.append("00000000 | 0 | 0 | 1 | 1 | pending")
    encoded = ("\n".join(lines) + "\n").encode("utf-8")
    return BOM_UTF8 + encoded if with_bom else encoded


class ArtifactDispatchClassificationTests(unittest.TestCase):
    """Exercise exact parsing, classification, and registry outcomes."""

    def test_registered_json_binds_exact_shared_kind(self) -> None:
        dispatched = _dispatch_json()
        parsed = dispatched.parsed_artifact
        registration = dispatched.registration

        self.assertIs(
            dispatched.classification,
            ArtifactClassification.JSON,
        )
        self.assertIsInstance(parsed, ParsedJsonArtifact)
        self.assertIs(parsed.source_artifact, dispatched.source_artifact)
        self.assertEqual(
            dispatched.content_sha256,
            dispatched.source_artifact.content_sha256,
        )
        self.assertIs(
            registration.status,
            RegistrationStatus.REGISTERED,
        )
        self.assertIs(
            registration.identifier_field,
            IdentifierField.SCHEMA,
        )
        self.assertEqual(
            registration.declared_identifier,
            _STRUCTURED_SCHEMA,
        )
        self.assertEqual(registration.declared_kind, "demo")
        self.assertEqual(
            dispatched.compatibility_record.artifact_kind,
            "demo",
        )

    def test_kind_independent_schema_preserves_declared_kind(self) -> None:
        dispatched = _dispatch_json(
            schema=_ARCHITECTURE_SCHEMA,
            kind="observatory_note",
        )
        registration = dispatched.registration

        self.assertIs(
            registration.status,
            RegistrationStatus.REGISTERED,
        )
        self.assertEqual(
            registration.declared_identifier,
            _ARCHITECTURE_SCHEMA,
        )
        self.assertEqual(
            registration.declared_kind,
            "observatory_note",
        )
        self.assertIsNone(
            registration.compatibility_record.artifact_kind
        )

    def test_identifier_failures_remain_distinct(self) -> None:
        cases = (
            (
                _MISSING,
                RegistrationStatus.MISSING_IDENTIFIER,
                None,
            ),
            (
                76,
                RegistrationStatus.INVALID_IDENTIFIER,
                None,
            ),
            (
                "frp.unknown.artifact.v1",
                RegistrationStatus.UNKNOWN_IDENTIFIER,
                "frp.unknown.artifact.v1",
            ),
        )

        for schema, status, declared_identifier in cases:
            with self.subTest(status=status):
                registration = _dispatch_json(
                    schema=schema
                ).registration

                self.assertIs(registration.status, status)
                self.assertIs(
                    registration.identifier_field,
                    IdentifierField.SCHEMA,
                )
                self.assertEqual(
                    registration.declared_identifier,
                    declared_identifier,
                )
                self.assertEqual(registration.declared_kind, "demo")
                self.assertIsNone(registration.compatibility_record)
                self.assertEqual(registration.expected_kinds, ())

    def test_unsupported_shared_kind_reports_registered_kinds(self) -> None:
        registration = _dispatch_json(kind="trace").registration

        self.assertIs(
            registration.status,
            RegistrationStatus.UNSUPPORTED_KIND,
        )
        self.assertEqual(
            registration.declared_identifier,
            _STRUCTURED_SCHEMA,
        )
        self.assertEqual(registration.declared_kind, "trace")
        self.assertEqual(
            registration.expected_kinds,
            ("demo", "self_test"),
        )
        self.assertIsNone(registration.compatibility_record)

    def test_vector_with_optional_bom_binds_format_version(self) -> None:
        for with_bom in (False, True):
            with self.subTest(with_bom=with_bom):
                source = _source(
                    _vector_bytes(with_bom=with_bom),
                    "pending_routes.vec",
                )
                dispatched = dispatch_artifact(source)
                registration = dispatched.registration

                self.assertIs(
                    dispatched.classification,
                    ArtifactClassification.M15_VECTOR,
                )
                self.assertIsInstance(
                    dispatched.parsed_artifact,
                    M15VectorArtifact,
                )
                self.assertIs(
                    registration.status,
                    RegistrationStatus.REGISTERED,
                )
                self.assertIs(
                    registration.identifier_field,
                    IdentifierField.FORMAT_VERSION,
                )
                self.assertEqual(
                    registration.declared_identifier,
                    M15_VECTOR_FORMAT_VERSION,
                )
                self.assertIsNone(registration.declared_kind)

    def test_unparsed_containers_are_registry_not_applicable(self) -> None:
        cases = (
            (b"", ArtifactClassification.EMPTY),
            (b"plain text\n", ArtifactClassification.UTF8_TEXT),
            (b"PK\x03\x04archive", ArtifactClassification.ZIP),
            (b"\xff\xfe\x00", ArtifactClassification.BINARY),
        )

        for raw_bytes, classification in cases:
            with self.subTest(classification=classification):
                dispatched = dispatch_artifact(_source(raw_bytes))
                registration = dispatched.registration

                self.assertIs(
                    dispatched.classification,
                    classification,
                )
                self.assertIsNone(dispatched.parsed_artifact)
                self.assertIs(
                    registration.status,
                    RegistrationStatus.NOT_APPLICABLE,
                )

    def test_only_leading_format_declaration_selects_vector(self) -> None:
        raw_bytes = (
            b"# producer_note=\"published\"\n"
            + _vector_bytes()
        )

        dispatched = dispatch_artifact(
            _source(raw_bytes, "late-declaration.vec")
        )

        self.assertIs(
            dispatched.classification,
            ArtifactClassification.UTF8_TEXT,
        )
        self.assertIsNone(dispatched.parsed_artifact)

    def test_parser_errors_are_not_silently_reclassified(self) -> None:
        with self.assertRaises(JsonSyntaxError):
            dispatch_artifact(
                _source(b'{"schema":', "invalid.json")
            )

        with self.assertRaisesRegex(
            M15VectorMetadataError,
            "unsupported M15 vector format_version",
        ):
            dispatch_artifact(
                _source(
                    _vector_bytes(
                        format_version="frp.m15.vector.v2"
                    ),
                    "unsupported.vec",
                )
            )

    def test_dispatch_requires_verified_source(self) -> None:
        with self.assertRaisesRegex(
            ArtifactDispatchError,
            "source must be a SourceArtifact",
        ):
            dispatch_artifact(b"artifact")

        source = _source(_json_bytes(), "tampered.json")
        object.__setattr__(source, "raw_bytes", b"changed")
        with self.assertRaisesRegex(
            ArtifactDispatchError,
            "integrity verification failed",
        ):
            dispatch_artifact(source)


class RegistrationResultValidationTests(unittest.TestCase):
    """Exercise immutable registry-result state relations."""

    def assert_invalid(
        self,
        result: RegistrationResult,
        changes: dict[str, object],
        message: str,
    ) -> None:
        with self.assertRaisesRegex(ArtifactDispatchError, message):
            replace(result, **changes)

    def test_registered_result_is_frozen_and_exact(self) -> None:
        result = _dispatch_json().registration
        record = result.compatibility_record

        with self.assertRaises(FrozenInstanceError):
            setattr(result, "declared_kind", "self_test")

        cases = (
            ({"status": "registered"}, "status must be"),
            ({"identifier_field": "schema"}, "identifier_field must be"),
            ({"declared_identifier": 76}, "declared_identifier must be"),
            ({"declared_kind": 76}, "declared_kind must be"),
            ({"compatibility_record": "record"}, "compatibility_record must"),
            ({"compatibility_record": None}, "require a compatibility"),
            ({"identifier_field": IdentifierField.FORMAT_VERSION},
             "identifier_field does not match"),
            ({"declared_identifier": "frp.changed.v1"},
             "declared_identifier does not match"),
            ({"declared_kind": "self_test"},
             "declared_kind does not match"),
            ({"expected_kinds": ("demo",)}, "must not contain expected"),
        )
        self.assertIsNotNone(record)
        for changes, message in cases:
            with self.subTest(changes=changes):
                self.assert_invalid(result, changes, message)

    def test_not_applicable_result_rejects_registry_data(self) -> None:
        result = dispatch_artifact(_source(b"plain\n")).registration
        cases = (
            ({"identifier_field": IdentifierField.SCHEMA}, "must not declare"),
            ({"declared_identifier": _STRUCTURED_SCHEMA}, "must not declare"),
            ({"declared_kind": "demo"}, "must not declare"),
            ({"expected_kinds": ("demo",)}, "must not declare"),
            ({"compatibility_record": _dispatch_json().compatibility_record},
             "only registered results"),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                self.assert_invalid(result, changes, message)

    def test_unresolved_status_relations_are_enforced(self) -> None:
        missing = _dispatch_json(schema=_MISSING).registration
        unknown = _dispatch_json(
            schema="frp.unknown.artifact.v1"
        ).registration
        unsupported = _dispatch_json(kind="trace").registration
        cases = (
            (missing, {"identifier_field": None}, "require identifier_field"),
            (
                missing,
                {"declared_identifier": _STRUCTURED_SCHEMA},
                "must not be normalized",
            ),
            (missing, {"expected_kinds": ("demo",)}, "have no expected kinds"),
            (unknown, {"declared_identifier": None}, "require an identifier"),
            (unknown, {"expected_kinds": ("demo",)}, "have no expected kinds"),
            (unsupported, {"expected_kinds": ()}, "require expected_kinds"),
        )

        for result, changes, message in cases:
            with self.subTest(status=result.status, changes=changes):
                self.assert_invalid(result, changes, message)

    def test_expected_kind_storage_is_exact(self) -> None:
        result = _dispatch_json(kind="trace").registration
        cases = (
            (["demo"], "expected_kinds must be a tuple"),
            (("",), "must contain nonempty strings"),
            ((76,), "must contain nonempty strings"),
            (("demo", "demo"), "expected_kinds must be unique"),
        )

        for expected_kinds, message in cases:
            with self.subTest(expected_kinds=expected_kinds):
                self.assert_invalid(
                    result,
                    {"expected_kinds": expected_kinds},
                    message,
                )


class DispatchedArtifactValidationTests(unittest.TestCase):
    """Exercise direct classification-envelope safeguards."""

    def assert_invalid(
        self,
        artifact: DispatchedArtifact,
        changes: dict[str, object],
        message: str,
    ) -> None:
        with self.assertRaisesRegex(ArtifactDispatchError, message):
            replace(artifact, **changes)

    def test_direct_fields_require_exact_types_and_relations(self) -> None:
        json_artifact = _dispatch_json()
        vector_artifact = dispatch_artifact(
            _source(_vector_bytes(), "pending_routes.vec")
        )
        plain_artifact = dispatch_artifact(_source(b"plain\n"))
        other_json = dispatch_artifact(
            _source(_json_bytes(), "other.json")
        )
        cases = (
            (
                json_artifact,
                {"source_artifact": "source"},
                "source_artifact must be",
            ),
            (json_artifact, {"classification": "json"},
             "classification must be"),
            (json_artifact, {"registration": "registration"},
             "registration must be"),
            (json_artifact, {"parsed_artifact": None},
             "require ParsedJsonArtifact"),
            (
                json_artifact,
                {"parsed_artifact": vector_artifact.parsed_artifact},
                "require ParsedJsonArtifact",
            ),
            (
                vector_artifact,
                {"parsed_artifact": json_artifact.parsed_artifact},
                "require M15VectorArtifact",
            ),
            (plain_artifact,
             {"parsed_artifact": json_artifact.parsed_artifact},
             "must not contain parsed artifacts"),
            (plain_artifact, {"registration": json_artifact.registration},
             "must be registry-not-applicable"),
            (
                json_artifact,
                {"source_artifact": other_json.source_artifact},
                "must reference the same source",
            ),
            (
                plain_artifact,
                {"classification": ArtifactClassification.BINARY},
                "does not match the source container",
            ),
        )

        for artifact, changes, message in cases:
            with self.subTest(changes=changes):
                self.assert_invalid(artifact, changes, message)

    def test_direct_construction_rejects_tampered_source(self) -> None:
        artifact = _dispatch_json()
        source = _source(_json_bytes(), "tampered-copy.json")
        object.__setattr__(source, "raw_bytes", b"changed")

        self.assert_invalid(
            artifact,
            {"source_artifact": source},
            "integrity verification failed",
        )


if __name__ == "__main__":
    unittest.main()
