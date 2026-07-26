"""Tests for read-only parsing of published FRP M15 vector text."""

from __future__ import annotations

import json
import unittest
from codecs import BOM_UTF8
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

from parsers.m15_vector import (
    CELL_TRACE_COLUMNS,
    M15_VECTOR_FORMAT_VERSION,
    PRIMARY_VECTOR_COLUMNS,
    ROUTE_TRACE_COLUMNS,
    M15VectorArtifact,
    M15VectorEncodingError,
    M15VectorError,
    M15VectorMetadataEntry,
    M15VectorMetadataError,
    M15VectorRow,
    M15VectorRowError,
    M15VectorStructureError,
    M15VectorTextEncoding,
    M15VectorTraceKind,
    expected_columns_for_trace_kind,
    parse_m15_vector,
)
from parsers.source_artifact import SourceArtifact, capture_source_bytes


_ROUTE_ROWS = (
    ("00000000", "0", "0", "1", "1", "pending"),
    ("00000001", "1", "0", "1", "1", "applied"),
)


def _metadata_items(
    *,
    trace_kind: str = M15VectorTraceKind.PENDING_ROUTES.value,
    columns: tuple[str, ...] = ROUTE_TRACE_COLUMNS,
) -> tuple[tuple[str, object], ...]:
    return (
        ("format_version", M15_VECTOR_FORMAT_VERSION),
        ("frp_version", "1.7.0"),
        ("milestone", "M15"),
        ("trace_kind", trace_kind),
        ("transition_fraction", 0.25),
        ("flags", [True, None, 76]),
        ("column_definition", list(columns)),
    )


def _replace_metadata(
    items: tuple[tuple[str, object], ...], key: str, value: object
) -> tuple[tuple[str, object], ...]:
    return tuple(
        (item_key, value if item_key == key else item_value)
        for item_key, item_value in items
    )


def _vector_bytes(
    *,
    trace_kind: str = M15VectorTraceKind.PENDING_ROUTES.value,
    columns: tuple[str, ...] = ROUTE_TRACE_COLUMNS,
    rows: tuple[tuple[str, ...], ...] = _ROUTE_ROWS,
    metadata: tuple[tuple[str, object], ...] | None = None,
    with_bom: bool = False,
) -> bytes:
    metadata_items = (
        metadata if metadata is not None
        else _metadata_items(trace_kind=trace_kind, columns=columns)
    )
    lines = [
        f"# {key}="
        + json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for key, value in metadata_items
    ]
    lines.append("# " + " | ".join(columns))
    lines.extend(" | ".join(row) for row in rows)
    encoded = ("\n".join(lines) + "\n").encode("utf-8")
    return BOM_UTF8 + encoded if with_bom else encoded


def _source(raw_bytes: bytes) -> SourceArtifact:
    return capture_source_bytes(
        raw_bytes,
        source_filename="pending_routes.txt",
        source_path="published/m15/pending_routes.txt",
    )


def _parsed() -> M15VectorArtifact:
    return parse_m15_vector(_source(_vector_bytes()))


class M15VectorParsingTests(unittest.TestCase):
    """Exercise exact parsing, ordering, and immutable raw fields."""

    def test_route_vector_retains_source_and_order(self) -> None:
        source = _source(_vector_bytes())

        artifact = parse_m15_vector(source)

        self.assertIs(artifact.source_artifact, source)
        self.assertEqual(
            artifact.source_artifact_id,
            source.source_artifact_id,
        )
        self.assertEqual(artifact.content_sha256, source.content_sha256)
        self.assertEqual(artifact.format_identifier, M15_VECTOR_FORMAT_VERSION)
        self.assertEqual(
            artifact.declared_trace_kind,
            M15VectorTraceKind.PENDING_ROUTES.value,
        )
        self.assertIs(
            artifact.recognized_trace_kind,
            M15VectorTraceKind.PENDING_ROUTES,
        )
        self.assertTrue(artifact.columns_match_recognized_trace_kind)
        self.assertEqual(artifact.columns, ROUTE_TRACE_COLUMNS)
        self.assertEqual(
            tuple(entry.key for entry in artifact.metadata_entries),
            tuple(key for key, _ in _metadata_items()),
        )
        self.assertEqual(
            artifact.column_header_line_number,
            len(_metadata_items()) + 1,
        )
        self.assertEqual(
            tuple(row.fields for row in artifact.rows),
            _ROUTE_ROWS,
        )
        self.assertEqual(artifact.value_at(1, "ROUTE_STATUS"), "applied")

    def test_metadata_values_preserve_exact_json_types(self) -> None:
        artifact = _parsed()

        self.assertEqual(
            artifact.metadata_value("transition_fraction"),
            Decimal("0.25"),
        )
        self.assertEqual(artifact.metadata_value("flags"), (True, None, 76))
        self.assertIsInstance(artifact.metadata_entries, tuple)
        self.assertIsInstance(artifact.rows, tuple)
        self.assertIsInstance(artifact.rows[0].fields, tuple)
        with self.assertRaises(KeyError):
            artifact.metadata_value("missing")
        with self.assertRaises(FrozenInstanceError):
            setattr(artifact, "declared_trace_kind", "changed")
        with self.assertRaisesRegex(
            M15VectorError,
            "row_index must be an integer",
        ):
            artifact.value_at(True, "TICK")
        with self.assertRaisesRegex(
            M15VectorError,
            "column must be a string",
        ):
            artifact.value_at(0, 76)
        with self.assertRaises(KeyError):
            artifact.value_at(0, "UNKNOWN")

    def test_utf8_bom_is_recorded(self) -> None:
        artifact = parse_m15_vector(
            _source(_vector_bytes(with_bom=True))
        )

        self.assertIs(
            artifact.text_encoding,
            M15VectorTextEncoding.UTF8_WITH_BOM,
        )
        self.assertEqual(
            artifact.value_at(0, "TARGET_STATE_CODE"),
            "1",
        )

    def test_unknown_trace_kind_remains_explicit(self) -> None:
        artifact = parse_m15_vector(
            _source(
                _vector_bytes(
                    trace_kind="experimental_trace",
                    columns=("TICK", "VALUE"),
                    rows=(("00000000", "raw"),),
                )
            )
        )

        self.assertEqual(
            artifact.declared_trace_kind,
            "experimental_trace",
        )
        self.assertIsNone(artifact.recognized_trace_kind)
        self.assertFalse(artifact.columns_match_recognized_trace_kind)
        self.assertEqual(artifact.value_at(0, "VALUE"), "raw")

    def test_expected_columns_follow_exact_trace_kind(self) -> None:
        primary_kinds = (
            M15VectorTraceKind.KERNEL_TRANSITION_VECTORS,
            M15VectorTraceKind.SCHEDULER_FREE_VECTORS,
            M15VectorTraceKind.SCHEDULER_7_1_VECTORS,
            M15VectorTraceKind.SCHEDULER_1_7_VECTORS,
            M15VectorTraceKind.FULL_CORRELATION_VECTORS,
        )
        cases = tuple(
            (trace_kind, PRIMARY_VECTOR_COLUMNS)
            for trace_kind in primary_kinds
        ) + (
            (M15VectorTraceKind.CELL_TRACE, CELL_TRACE_COLUMNS),
            (M15VectorTraceKind.PENDING_ROUTES, ROUTE_TRACE_COLUMNS),
            ("unknown_trace", None),
        )
        for trace_kind, expected in cases:
            with self.subTest(trace_kind=trace_kind):
                self.assertEqual(
                    expected_columns_for_trace_kind(trace_kind), expected
                )
        with self.assertRaisesRegex(
            M15VectorError,
            "trace_kind must be a string",
        ):
            expected_columns_for_trace_kind(76)


class M15VectorRejectionTests(unittest.TestCase):
    """Exercise encoding, metadata, structure, and row failures."""

    def test_parser_requires_verified_source(self) -> None:
        with self.assertRaisesRegex(
            M15VectorError,
            "source must be a SourceArtifact",
        ):
            parse_m15_vector(b"vector")

        source = _source(_vector_bytes())
        object.__setattr__(source, "raw_bytes", b"changed")
        with self.assertRaisesRegex(
            M15VectorError,
            "integrity verification failed",
        ):
            parse_m15_vector(source)

    def test_invalid_utf8_retains_byte_coordinates(self) -> None:
        source = _source(b"# format_version=\xff\n")

        with self.assertRaises(M15VectorEncodingError) as context:
            parse_m15_vector(source)

        error = context.exception
        self.assertEqual(error.byte_start, 17)
        self.assertEqual(error.byte_end, 18)
        self.assertEqual(error.reason, "invalid start byte")

    def test_invalid_line_structure_is_rejected(self) -> None:
        valid_lines = _vector_bytes().decode("utf-8").splitlines()
        cases = (
            (b"", "vector text must not be empty"),
            (b"\n", "blank lines are not permitted"),
            (b"00000000 | 0\n", "data appeared before"),
            (b"# unsupported comment\n", "neither metadata nor columns"),
            (
                b'# format_version="frp.m15.vector.v1"\n',
                "column header is missing",
            ),
            (
                (
                    "\n".join(
                        valid_lines[: len(_metadata_items()) + 1]
                        + ["# late comment"]
                    )
                    + "\n"
                ).encode("utf-8"),
                "comments are not permitted",
            ),
        )

        for raw_bytes, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    M15VectorStructureError,
                    message,
                ):
                    parse_m15_vector(_source(raw_bytes))

    def test_metadata_json_failures_retain_key_and_line(self) -> None:
        cases = (
            (
                b'# format_version=not-json\n# TICK | VALUE\n',
                "format_version",
                "invalid metadata JSON",
            ),
            (
                b'# value=NaN\n# TICK | VALUE\n',
                "value",
                "non-finite metadata number",
            ),
            (
                b'# value={"nested":1}\n# TICK | VALUE\n',
                "value",
                "unsupported metadata JSON value type",
            ),
            (
                b'# bad key=1\n# TICK | VALUE\n',
                "bad key",
                "metadata key contains unsupported characters",
            ),
        )

        for raw_bytes, key, message in cases:
            with self.subTest(key=key):
                with self.assertRaises(
                    M15VectorMetadataError
                ) as context:
                    parse_m15_vector(_source(raw_bytes))

                self.assertEqual(context.exception.key, key)
                self.assertEqual(context.exception.line_number, 1)
                self.assertIn(message, str(context.exception))

    def test_duplicate_and_missing_metadata_are_rejected(self) -> None:
        duplicate = (
            b'# format_version="frp.m15.vector.v1"\n'
            b'# format_version="frp.m15.vector.v1"\n'
            b"# TICK | VALUE\n"
        )
        with self.assertRaisesRegex(
            M15VectorMetadataError,
            "duplicate metadata key",
        ):
            parse_m15_vector(_source(duplicate))

        required_keys = (
            "format_version",
            "trace_kind",
            "column_definition",
        )
        base_items = _metadata_items()
        for missing_key in required_keys:
            metadata = tuple(
                item for item in base_items if item[0] != missing_key
            )
            with self.subTest(missing_key=missing_key):
                with self.assertRaisesRegex(
                    M15VectorMetadataError,
                    missing_key,
                ):
                    parse_m15_vector(
                        _source(_vector_bytes(metadata=metadata))
                    )

    def test_format_and_column_contracts_are_rejected(self) -> None:
        base_items = _metadata_items()
        unsupported_format = _replace_metadata(
            base_items,
            "format_version",
            "frp.m15.vector.v2",
        )
        with self.assertRaisesRegex(
            M15VectorMetadataError,
            "unsupported M15 vector format_version",
        ):
            parse_m15_vector(
                _source(_vector_bytes(metadata=unsupported_format))
            )

        wrong_definition = _replace_metadata(
            base_items,
            "column_definition",
            ["TICK", "VALUE"],
        )
        with self.assertRaisesRegex(
            M15VectorMetadataError,
            "column_definition does not match",
        ):
            parse_m15_vector(
                _source(_vector_bytes(metadata=wrong_definition))
            )

    def test_row_error_retains_line_and_field_counts(self) -> None:
        source = _source(
            _vector_bytes(rows=(("00000000", "pending"),))
        )

        with self.assertRaises(M15VectorRowError) as context:
            parse_m15_vector(source)

        error = context.exception
        self.assertEqual(
            error.line_number,
            len(_metadata_items()) + 2,
        )
        self.assertEqual(
            error.expected_field_count,
            len(ROUTE_TRACE_COLUMNS),
        )
        self.assertEqual(error.actual_field_count, 2)


class M15VectorModelValidationTests(unittest.TestCase):
    """Exercise direct immutable model construction safeguards."""

    def test_metadata_entry_and_row_validate_storage(self) -> None:
        entry = _parsed().metadata_entries[0]
        entry_cases = (
            ({"key": ""}, "metadata key must be"),
            ({"key": "bad key"}, "unsupported characters"),
            ({"raw_json": ""}, "JSON text must be nonempty"),
            ({"value": []}, "mutable or unsupported"),
            ({"line_number": 0}, "line_number must be positive"),
        )

        for changes, message in entry_cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M15VectorError,
                    message,
                ):
                    replace(entry, **changes)

        row = M15VectorRow(line_number=1, fields=("raw",))
        row_cases = (
            ({"line_number": True}, "line_number must be an integer"),
            ({"fields": ["raw"]}, "fields must be a tuple"),
            ({"fields": (76,)}, "fields must contain strings"),
        )
        for changes, message in row_cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M15VectorError,
                    message,
                ):
                    replace(row, **changes)

    def test_artifact_rejects_invalid_direct_fields(self) -> None:
        artifact = _parsed()
        duplicate_columns = (
            artifact.columns[0],
            artifact.columns[0],
        ) + artifact.columns[2:]
        short_row = replace(
            artifact.rows[0],
            fields=artifact.rows[0].fields[:-1],
        )
        json_source = _source(b'{"schema":"frp.test.v1"}')
        cases = (
            (
                {"source_artifact": "source"},
                "source_artifact must be a SourceArtifact",
            ),
            (
                {"source_artifact": json_source},
                "not a UTF-8 text container",
            ),
            (
                {"metadata_entries": list(artifact.metadata_entries)},
                "metadata_entries must be a tuple",
            ),
            (
                {"columns": duplicate_columns},
                "column names must be unique",
            ),
            (
                {"rows": (short_row,)},
                "field count does not match",
            ),
            (
                {"text_encoding": M15VectorTextEncoding.UTF8_WITH_BOM},
                "text_encoding does not match",
            ),
            (
                {"format_identifier": "frp.m15.vector.v2"},
                "format_identifier does not match",
            ),
            (
                {"declared_trace_kind": "cell_trace"},
                "declared_trace_kind does not match",
            ),
            (
                {"columns": tuple(reversed(artifact.columns))},
                "column_definition does not match",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M15VectorError,
                    message,
                ):
                    replace(artifact, **changes)


if __name__ == "__main__":
    unittest.main()
