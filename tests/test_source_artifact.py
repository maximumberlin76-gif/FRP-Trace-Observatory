"""Tests for immutable capture of published FRP source artifacts."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID, NAMESPACE_URL, uuid5

from parsers.source_artifact import (
    LoadStatus,
    RawSourceDigest,
    SourceArtifactError,
    SourceContainerFormat,
    capture_source_bytes,
    detect_container_format,
    load_source_file,
)


def _record_id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"frp-source-artifact-test:{label}"))


def _digest() -> RawSourceDigest:
    return RawSourceDigest(
        digest_record_id=_record_id("digest"),
        value="ab" * 32,
    )


class ContainerFormatDetectionTests(unittest.TestCase):
    """Exercise non-executing outer-container detection."""

    def test_json_objects_and_arrays_are_candidates(self) -> None:
        payloads = (
            b'{"schema":"frp.test.v1"}',
            b" \n\t[0, -1, 1]",
            b"\xef\xbb\xbf \n{}",
        )

        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertIs(
                    detect_container_format(payload),
                    SourceContainerFormat.JSON_CANDIDATE,
                )

    def test_invalid_utf8_and_nul_text_are_binary(self) -> None:
        payloads = (
            b"\xff\xfe\xfd",
            b"valid\x00utf8",
        )

        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertIs(
                    detect_container_format(payload),
                    SourceContainerFormat.BINARY,
                )

    def test_all_supported_zip_signatures_are_detected(self) -> None:
        signatures = (
            b"PK\x03\x04",
            b"PK\x05\x06",
            b"PK\x07\x08",
        )

        for signature in signatures:
            with self.subTest(signature=signature):
                self.assertIs(
                    detect_container_format(signature + b"payload"),
                    SourceContainerFormat.ZIP,
                )

    def test_detection_requires_immutable_bytes(self) -> None:
        for value in (bytearray(b"{}"), memoryview(b"{}"), "{}"):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(
                    SourceArtifactError,
                    "raw_bytes must be bytes",
                ):
                    detect_container_format(value)


class RawSourceDigestTests(unittest.TestCase):
    """Exercise exact raw-byte digest metadata."""

    def test_digest_retains_canonical_frozen_metadata(self) -> None:
        digest = _digest()

        self.assertEqual(digest.value, "ab" * 32)
        self.assertEqual(digest.algorithm, "sha256")
        self.assertEqual(digest.byte_scope, "raw_source_bytes")
        UUID(digest.digest_record_id)
        with self.assertRaises(FrozenInstanceError):
            setattr(digest, "value", "cd" * 32)

    def test_digest_rejects_invalid_metadata(self) -> None:
        digest = _digest()
        cases = (
            (
                {"digest_record_id": "not-a-uuid"},
                "digest_record_id must be a valid UUID",
            ),
            (
                {"digest_record_id": 7},
                "digest_record_id must be a string",
            ),
            (
                {"value": b"ab" * 32},
                "raw source digest value must be a string",
            ),
            (
                {"value": "ab" * 31},
                "64 lowercase hexadecimal characters",
            ),
            (
                {"value": "AB" * 32},
                "64 lowercase hexadecimal characters",
            ),
            (
                {"value": ("ab" * 31) + "gg"},
                "64 lowercase hexadecimal characters",
            ),
            (
                {"algorithm": "SHA-256"},
                "algorithm must be sha256",
            ),
            (
                {"byte_scope": "normalized_bytes"},
                "scope must be raw_source_bytes",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    SourceArtifactError,
                    message,
                ):
                    replace(digest, **changes)


class SourceCaptureTests(unittest.TestCase):
    """Exercise immutable capture and provenance normalization."""

    def test_capture_records_bytes_identity_and_provenance(self) -> None:
        raw_bytes = b'{"schema":"frp.test.v1","states":[-1,0,1]}'
        loaded_at = datetime(
            2026,
            7,
            26,
            14,
            30,
            tzinfo=timezone(timedelta(hours=2)),
        )

        source = capture_source_bytes(
            raw_bytes,
            source_filename="trace.json",
            source_path=Path("published/trace.json"),
            loaded_at=loaded_at,
        )

        self.assertEqual(source.raw_bytes, raw_bytes)
        self.assertEqual(source.byte_length, len(raw_bytes))
        self.assertEqual(source.source_filename, "trace.json")
        self.assertEqual(source.source_path, "published/trace.json")
        self.assertEqual(
            source.loaded_at,
            datetime(2026, 7, 26, 12, 30, tzinfo=timezone.utc),
        )
        self.assertIs(
            source.detected_container_format,
            SourceContainerFormat.JSON_CANDIDATE,
        )
        self.assertIs(source.load_status, LoadStatus.CAPTURED)
        self.assertEqual(
            source.content_sha256,
            sha256(raw_bytes).hexdigest(),
        )
        self.assertEqual(
            source.source_digest_id,
            source.source_digest.digest_record_id,
        )
        UUID(source.source_artifact_id)
        UUID(source.source_digest_id)
        self.assertNotEqual(
            source.source_artifact_id,
            source.source_digest_id,
        )
        self.assertTrue(source.verify_integrity())
        with self.assertRaises(FrozenInstanceError):
            setattr(source, "source_filename", "changed.json")

    def test_mutable_inputs_are_captured_as_immutable_snapshots(self) -> None:
        mutable_inputs = (
            bytearray(b"tick,state\n0,-1\n"),
            memoryview(bytearray(b"pending_routes=0\n")),
        )

        for raw_input in mutable_inputs:
            expected = bytes(raw_input)
            source = capture_source_bytes(
                raw_input,
                source_filename="trace.txt",
            )
            raw_input[0] = ord("X")

            self.assertEqual(source.raw_bytes, expected)
            self.assertIsInstance(source.raw_bytes, bytes)
            self.assertTrue(source.verify_integrity())

    def test_default_timestamp_is_current_utc(self) -> None:
        before = datetime.now(timezone.utc)
        source = capture_source_bytes(
            b"",
            source_filename="empty.json",
        )
        after = datetime.now(timezone.utc)

        self.assertLessEqual(before, source.loaded_at)
        self.assertLessEqual(source.loaded_at, after)
        self.assertEqual(source.loaded_at.utcoffset(), timedelta(0))
        self.assertIs(
            source.detected_container_format,
            SourceContainerFormat.EMPTY,
        )

    def test_capture_rejects_unsupported_byte_input(self) -> None:
        with self.assertRaisesRegex(
            SourceArtifactError,
            "raw_bytes must be bytes, bytearray, or memoryview",
        ):
            capture_source_bytes(
                [0, 1],
                source_filename="trace.json",
            )

    def test_capture_rejects_invalid_source_filenames(self) -> None:
        invalid_names = (
            "",
            "   ",
            ".",
            "..",
            "published/trace.json",
            "published\\trace.json",
            "trace\x00.json",
            7,
        )

        for source_filename in invalid_names:
            with self.subTest(source_filename=source_filename):
                with self.assertRaises(SourceArtifactError):
                    capture_source_bytes(
                        b"{}",
                        source_filename=source_filename,
                    )

    def test_capture_rejects_invalid_source_paths(self) -> None:
        for source_path in ("", "published/\x00trace.json"):
            with self.subTest(source_path=source_path):
                with self.assertRaisesRegex(
                    SourceArtifactError,
                    "source_path must",
                ):
                    capture_source_bytes(
                        b"{}",
                        source_filename="trace.json",
                        source_path=source_path,
                    )

    def test_capture_requires_timezone_aware_datetime(self) -> None:
        invalid_timestamps = (
            datetime(2026, 7, 26, 12, 30),
            "2026-07-26T12:30:00Z",
        )

        for loaded_at in invalid_timestamps:
            with self.subTest(loaded_at=loaded_at):
                with self.assertRaisesRegex(
                    SourceArtifactError,
                    "loaded_at must",
                ):
                    capture_source_bytes(
                        b"{}",
                        source_filename="trace.json",
                        loaded_at=loaded_at,
                    )

    def test_integrity_check_detects_forced_byte_replacement(self) -> None:
        source = capture_source_bytes(
            b"original",
            source_filename="trace.txt",
        )

        object.__setattr__(source, "raw_bytes", b"changed")

        self.assertFalse(source.verify_integrity())


class SourceArtifactValidationTests(unittest.TestCase):
    """Exercise direct model construction safeguards."""

    def setUp(self) -> None:
        self.source = capture_source_bytes(
            b'{"schema":"frp.test.v1"}',
            source_filename="trace.json",
            source_path="published/trace.json",
            loaded_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
        )

    def test_direct_construction_rejects_invalid_fields(self) -> None:
        mismatched_digest = replace(
            self.source.source_digest,
            value="00" * 32,
        )
        cases = (
            (
                {"source_artifact_id": "invalid"},
                "source_artifact_id must be a valid UUID",
            ),
            (
                {"source_path": Path("trace.json")},
                "source_path must be a string or None",
            ),
            (
                {"raw_bytes": bytearray(self.source.raw_bytes)},
                "raw_bytes must be immutable bytes",
            ),
            (
                {"byte_length": True},
                "byte_length must be an integer",
            ),
            (
                {"byte_length": "27"},
                "byte_length must be an integer",
            ),
            (
                {"byte_length": self.source.byte_length + 1},
                "byte_length does not match",
            ),
            (
                {"detected_container_format": "json_candidate"},
                "must be a SourceContainerFormat",
            ),
            (
                {
                    "detected_container_format": (
                        SourceContainerFormat.UTF8_TEXT
                    )
                },
                "does not match source bytes",
            ),
            (
                {"source_digest": self.source.content_sha256},
                "source_digest must be a RawSourceDigest",
            ),
            (
                {"source_digest": mismatched_digest},
                "source digest does not match",
            ),
            (
                {"loaded_at": "2026-07-26T00:00:00Z"},
                "loaded_at must be a datetime",
            ),
            (
                {"loaded_at": datetime(2026, 7, 26)},
                "loaded_at must include a timezone",
            ),
            (
                {
                    "loaded_at": datetime(
                        2026,
                        7,
                        26,
                        tzinfo=timezone(timedelta(hours=1)),
                    )
                },
                "loaded_at must be normalized to UTC",
            ),
            (
                {"load_status": "captured"},
                "load_status must be a LoadStatus",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    SourceArtifactError,
                    message,
                ):
                    replace(self.source, **changes)


class SourceFileLoadingTests(unittest.TestCase):
    """Exercise read-only loading of local regular files."""

    def test_regular_file_is_loaded_without_modification(self) -> None:
        raw_bytes = b'{"schema":"frp.test.v1","tick":0}'
        loaded_at = datetime(2026, 7, 26, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "trace.json"
            file_path.write_bytes(raw_bytes)
            before = file_path.read_bytes()

            source = load_source_file(
                file_path,
                loaded_at=loaded_at,
            )

            self.assertEqual(file_path.read_bytes(), before)
            self.assertEqual(source.raw_bytes, raw_bytes)
            self.assertEqual(source.source_filename, "trace.json")
            self.assertEqual(source.source_path, str(file_path))
            self.assertEqual(source.loaded_at, loaded_at)
            self.assertTrue(source.verify_integrity())
            overridden = load_source_file(
                file_path,
                source_path="published/traces/trace.json",
            )
            self.assertEqual(
                overridden.source_path,
                "published/traces/trace.json",
            )

    def test_loader_rejects_invalid_or_nonfile_paths(self) -> None:
        with self.assertRaisesRegex(
            SourceArtifactError,
            "path must be a string or Path",
        ):
            load_source_file(7)

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            missing_path = directory_path / "missing.json"

            for path in (directory_path, missing_path):
                with self.subTest(path=path):
                    with self.assertRaisesRegex(
                        SourceArtifactError,
                        "must identify a regular file",
                    ):
                        load_source_file(path)

    def test_loader_rejects_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            target_path = directory_path / "trace.json"
            link_path = directory_path / "trace-link.json"
            target_path.write_bytes(b"{}")

            try:
                link_path.symlink_to(target_path)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")

            with self.assertRaisesRegex(
                SourceArtifactError,
                "must not be a symbolic link",
            ):
                load_source_file(link_path)

    def test_loader_never_executes_source_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            source_path = directory_path / "untrusted.py"
            marker_path = directory_path / "executed.txt"
            source_path.write_text(
                (
                    "from pathlib import Path\n"
                    f"Path({str(marker_path)!r}).write_text('executed')\n"
                ),
                encoding="utf-8",
            )

            source = load_source_file(source_path)

            self.assertFalse(marker_path.exists())
            self.assertEqual(
                source.raw_bytes,
                source_path.read_bytes(),
            )
            self.assertIs(
                source.detected_container_format,
                SourceContainerFormat.UTF8_TEXT,
            )


if __name__ == "__main__":
    unittest.main()
