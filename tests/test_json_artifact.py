"""Tests for safe, immutable decoding of published FRP JSON artifacts."""

from __future__ import annotations

import json
import tempfile
import unittest
from codecs import BOM_UTF8
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from parsers.json_artifact import (
    DuplicateJsonKeyError,
    JsonArtifactError,
    JsonEncodingError,
    JsonRootError,
    JsonStructureError,
    JsonSyntaxError,
    JsonTextEncoding,
    NonFiniteJsonNumberError,
    ParsedJsonArtifact,
    parse_json_artifact,
)
from parsers.source_artifact import (
    SourceArtifact,
    SourceContainerFormat,
    capture_source_bytes,
)


def _source(
    raw_bytes: bytes,
    *,
    source_filename: str = "artifact.json",
) -> SourceArtifact:
    return capture_source_bytes(
        raw_bytes,
        source_filename=source_filename,
        source_path=f"published/{source_filename}",
    )


def _parsed(
    raw_bytes: bytes = (
        b'{"schema":"frp.test.v1","kind":"trace","states":[-1,0,1]}'
    ),
) -> ParsedJsonArtifact:
    return parse_json_artifact(_source(raw_bytes))


class SuccessfulJsonParsingTests(unittest.TestCase):
    """Exercise strict decoding and immutable value preservation."""

    def test_parsing_retains_identity_and_declared_metadata(self) -> None:
        source = _source(
            (
                b'{"schema":"frp.test.v1","kind":"trace",'
                b'"states":[-1,0,1]}'
            )
        )

        parsed = parse_json_artifact(source)

        self.assertIs(parsed.source_artifact, source)
        self.assertEqual(
            parsed.source_artifact_id,
            source.source_artifact_id,
        )
        self.assertEqual(parsed.content_sha256, source.content_sha256)
        self.assertEqual(
            parsed.declared_schema_identifier,
            "frp.test.v1",
        )
        self.assertEqual(parsed.declared_kind, "trace")
        self.assertIs(parsed.text_encoding, JsonTextEncoding.UTF8)
        self.assertEqual(parsed.root["states"], (-1, 0, 1))

    def test_nested_values_are_frozen_without_type_loss(self) -> None:
        parsed = _parsed(
            (
                b'{"integer":76,"fraction":0.1,"exponent":1e-6,'
                b'"enabled":true,"absent":null,"label":"FRP",'
                b'"nested":{"states":[-1,0,1],"rows":[{"tick":0}]}}'
            )
        )

        self.assertIs(type(parsed.root["integer"]), int)
        self.assertEqual(parsed.root["integer"], 76)
        self.assertIsInstance(parsed.root["fraction"], Decimal)
        self.assertEqual(parsed.root["fraction"], Decimal("0.1"))
        self.assertEqual(parsed.root["exponent"], Decimal("1E-6"))
        self.assertIs(parsed.root["enabled"], True)
        self.assertIsNone(parsed.root["absent"])
        self.assertEqual(parsed.root["label"], "FRP")

        nested = parsed.root["nested"]
        self.assertIsInstance(nested, type(MappingProxyType({})))
        self.assertEqual(nested["states"], (-1, 0, 1))
        self.assertIsInstance(nested["rows"], tuple)
        self.assertIsInstance(
            nested["rows"][0],
            type(MappingProxyType({})),
        )

    def test_root_and_nested_collections_are_immutable(self) -> None:
        parsed = _parsed(
            b'{"metadata":{"producer":"reference"},"states":[-1,0,1]}'
        )
        metadata = parsed.root["metadata"]

        with self.assertRaises(TypeError):
            parsed.root["schema"] = "changed"
        with self.assertRaises(TypeError):
            metadata["producer"] = "changed"
        with self.assertRaises(TypeError):
            parsed.root["states"][0] = 1
        with self.assertRaises(FrozenInstanceError):
            setattr(parsed, "declared_kind", "changed")

    def test_utf8_bom_is_detected_and_removed(self) -> None:
        source = _source(
            BOM_UTF8 + b'{"schema":"frp.test.v1","tick":0}'
        )

        parsed = parse_json_artifact(source)

        self.assertIs(
            source.detected_container_format,
            SourceContainerFormat.JSON_CANDIDATE,
        )
        self.assertIs(
            parsed.text_encoding,
            JsonTextEncoding.UTF8_WITH_BOM,
        )
        self.assertEqual(
            parsed.declared_schema_identifier,
            "frp.test.v1",
        )
        self.assertEqual(parsed.root["tick"], 0)

    def test_nonstring_schema_and_kind_are_not_normalized(self) -> None:
        parsed = _parsed(b'{"schema":76,"kind":["trace"]}')

        self.assertIsNone(parsed.declared_schema_identifier)
        self.assertIsNone(parsed.declared_kind)
        self.assertEqual(parsed.root["schema"], 76)
        self.assertEqual(parsed.root["kind"], ("trace",))

    def test_json_strings_are_data_and_are_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker_path = Path(directory) / "executed.txt"
            command = (
                "from pathlib import Path; "
                f"Path({str(marker_path)!r}).write_text('executed')"
            )
            raw_bytes = json.dumps(
                {"command": command},
                separators=(",", ":"),
            ).encode("utf-8")

            parsed = parse_json_artifact(_source(raw_bytes))

            self.assertEqual(parsed.root["command"], command)
            self.assertFalse(marker_path.exists())


class JsonRejectionTests(unittest.TestCase):
    """Exercise malformed, unsafe, and unsupported JSON inputs."""

    def test_parser_requires_source_artifact(self) -> None:
        with self.assertRaisesRegex(
            JsonArtifactError,
            "source must be a SourceArtifact",
        ):
            parse_json_artifact(b"{}")

    def test_parser_rejects_failed_source_integrity(self) -> None:
        source = _source(b'{"tick":0}')
        object.__setattr__(source, "raw_bytes", b'{"tick":1}')

        with self.assertRaisesRegex(
            JsonArtifactError,
            "source artifact integrity verification failed",
        ):
            parse_json_artifact(source)

    def test_invalid_utf8_retains_byte_error_coordinates(self) -> None:
        source = _source(b'{"x":"\xff"}')

        with self.assertRaises(JsonEncodingError) as context:
            parse_json_artifact(source)

        error = context.exception
        self.assertEqual(error.byte_start, 6)
        self.assertEqual(error.byte_end, 7)
        self.assertEqual(error.reason, "invalid start byte")
        self.assertEqual(
            str(error),
            "source bytes are not valid UTF-8 JSON text",
        )

    def test_syntax_error_retains_text_coordinates(self) -> None:
        source = _source(b'{"tick": }')

        with self.assertRaises(JsonSyntaxError) as context:
            parse_json_artifact(source)

        error = context.exception
        self.assertEqual(error.line_number, 1)
        self.assertEqual(error.column_number, 10)
        self.assertEqual(error.character_offset, 9)
        self.assertEqual(str(error), "Expecting value")

    def test_unescaped_control_character_is_rejected(self) -> None:
        source = _source(b'{"label":"FRP\ntrace"}')

        with self.assertRaisesRegex(
            JsonSyntaxError,
            "Invalid control character",
        ):
            parse_json_artifact(source)

    def test_duplicate_object_key_is_rejected_at_any_depth(self) -> None:
        payloads = (
            b'{"tick":0,"tick":1}',
            b'{"outer":{"state":-1,"state":1}}',
        )

        for raw_bytes in payloads:
            with self.subTest(raw_bytes=raw_bytes):
                with self.assertRaises(
                    DuplicateJsonKeyError
                ) as context:
                    parse_json_artifact(_source(raw_bytes))

                self.assertIn(context.exception.key, {"tick", "state"})
                self.assertIn(
                    "duplicate JSON object key",
                    str(context.exception),
                )

    def test_nonfinite_numbers_are_rejected(self) -> None:
        tokens = ("NaN", "Infinity", "-Infinity")

        for token in tokens:
            with self.subTest(token=token):
                source = _source(
                    f'{{"value":{token}}}'.encode("utf-8")
                )
                with self.assertRaises(
                    NonFiniteJsonNumberError
                ) as context:
                    parse_json_artifact(source)

                self.assertEqual(context.exception.token, token)
                self.assertIn(token, str(context.exception))

    def test_array_root_is_rejected(self) -> None:
        source = _source(b'[{"tick":0}]')

        with self.assertRaisesRegex(
            JsonRootError,
            "root must be an object",
        ):
            parse_json_artifact(source)

    def test_excessive_nesting_is_rejected(self) -> None:
        raw_bytes = (
            b'{"value":'
            + (b"[" * 2000)
            + b"0"
            + (b"]" * 2000)
            + b"}"
        )

        with self.assertRaisesRegex(
            JsonStructureError,
            "JSON nesting exceeds",
        ):
            parse_json_artifact(_source(raw_bytes))


class ParsedJsonArtifactValidationTests(unittest.TestCase):
    """Exercise direct immutable-view construction safeguards."""

    def setUp(self) -> None:
        self.parsed = _parsed()

    def test_source_must_be_matching_verified_json_candidate(self) -> None:
        text_source = _source(b"tick,state\n0,-1\n")

        cases = (
            (
                {"source_artifact": "source"},
                "source_artifact must be a SourceArtifact",
            ),
            (
                {"source_artifact": text_source},
                "not a JSON object or array candidate",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    JsonArtifactError,
                    message,
                ):
                    replace(self.parsed, **changes)

        tampered = _source(b'{"tick":0}')
        object.__setattr__(tampered, "raw_bytes", b'{"tick":1}')
        with self.assertRaisesRegex(
            JsonArtifactError,
            "integrity verification failed",
        ):
            replace(self.parsed, source_artifact=tampered)

    def test_root_requires_recursive_immutable_json_values(self) -> None:
        invalid_roots = (
            {"schema": "frp.test.v1"},
            MappingProxyType({"items": []}),
            MappingProxyType({"value": 0.5}),
            MappingProxyType({"value": Decimal("NaN")}),
        )

        for root in invalid_roots:
            with self.subTest(root=root):
                with self.assertRaisesRegex(
                    JsonArtifactError,
                    "root must|root contains",
                ):
                    replace(self.parsed, root=root)

    def test_text_encoding_requires_matching_enum(self) -> None:
        cases = (
            (
                {"text_encoding": "utf-8"},
                "text_encoding must be a JsonTextEncoding",
            ),
            (
                {"text_encoding": JsonTextEncoding.UTF8_WITH_BOM},
                "text_encoding does not match",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    JsonArtifactError,
                    message,
                ):
                    replace(self.parsed, **changes)

    def test_declared_metadata_must_match_exact_root_fields(self) -> None:
        cases = (
            (
                {"declared_schema_identifier": "frp.other.v1"},
                "declared_schema_identifier does not match",
            ),
            (
                {"declared_kind": "other"},
                "declared_kind does not match",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    JsonArtifactError,
                    message,
                ):
                    replace(self.parsed, **changes)


if __name__ == "__main__":
    unittest.main()
