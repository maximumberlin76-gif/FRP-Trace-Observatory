"""Safe, read-only JSON decoding for captured FRP artifacts."""

from __future__ import annotations

import json
from codecs import BOM_UTF8
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, cast

from .source_artifact import (
    SourceArtifact,
    SourceContainerFormat,
)


__all__ = [
    "DuplicateJsonKeyError",
    "JsonArtifactError",
    "JsonEncodingError",
    "JsonObject",
    "JsonRootError",
    "JsonScalar",
    "JsonStructureError",
    "JsonSyntaxError",
    "JsonTextEncoding",
    "JsonValue",
    "NonFiniteJsonNumberError",
    "ParsedJsonArtifact",
    "parse_json_artifact",
]


type JsonScalar = None | bool | int | Decimal | str
type JsonValue = (
    JsonScalar
    | tuple[JsonValue, ...]
    | Mapping[str, JsonValue]
)
type JsonObject = Mapping[str, JsonValue]


_MAPPING_PROXY_TYPE: Final = type(MappingProxyType({}))


class JsonArtifactError(ValueError):
    """Base error raised for an invalid JSON artifact container."""


class JsonEncodingError(JsonArtifactError):
    """Raised when source bytes are not valid UTF-8 JSON text."""

    def __init__(
        self,
        message: str,
        *,
        byte_start: int,
        byte_end: int,
        reason: str,
    ) -> None:
        super().__init__(message)
        self.byte_start = byte_start
        self.byte_end = byte_end
        self.reason = reason


class JsonSyntaxError(JsonArtifactError):
    """Raised when UTF-8 source text is not valid strict JSON."""

    def __init__(
        self,
        message: str,
        *,
        line_number: int,
        column_number: int,
        character_offset: int,
    ) -> None:
        super().__init__(message)
        self.line_number = line_number
        self.column_number = column_number
        self.character_offset = character_offset


class DuplicateJsonKeyError(JsonArtifactError):
    """Raised when any JSON object repeats a member name."""

    def __init__(self, key: str) -> None:
        super().__init__(f"duplicate JSON object key: {key!r}")
        self.key = key


class NonFiniteJsonNumberError(JsonArtifactError):
    """Raised for NaN or infinity tokens outside the JSON number grammar."""

    def __init__(self, token: str) -> None:
        super().__init__(f"non-finite JSON number is not permitted: {token}")
        self.token = token


class JsonRootError(JsonArtifactError):
    """Raised when a parsed FRP JSON artifact is not an object."""


class JsonStructureError(JsonArtifactError):
    """Raised when JSON nesting exceeds the decoder's safe recursion bound."""


class JsonTextEncoding(StrEnum):
    """Accepted text encodings for published JSON artifacts."""

    UTF8 = "utf-8"
    UTF8_WITH_BOM = "utf-8-sig"


def _reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _reject_non_finite_number(token: str) -> None:
    raise NonFiniteJsonNumberError(token)

def _freeze_json_value(value: Any) -> JsonValue:
    if value is None or isinstance(value, (bool, int, Decimal, str)):
        return value
    if isinstance(value, list):
        return tuple(_freeze_json_value(item) for item in value)
    if isinstance(value, dict):
        return MappingProxyType(
            {
                key: _freeze_json_value(item)
                for key, item in value.items()
            }
        )
    raise JsonArtifactError(
        f"unsupported decoded JSON value type: {type(value).__name__}"
    )


def _is_frozen_json_value(value: object) -> bool:
    if value is None or isinstance(value, (bool, int, str)):
        return True
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, tuple):
        return all(_is_frozen_json_value(item) for item in value)
    if isinstance(value, _MAPPING_PROXY_TYPE):
        return all(
            isinstance(key, str) and _is_frozen_json_value(item)
            for key, item in value.items()
        )
    return False


def _optional_declared_string(
    root: JsonObject,
    key: str,
) -> str | None:
    value = root.get(key)
    return value if isinstance(value, str) else None


def _detect_text_encoding(source: SourceArtifact) -> JsonTextEncoding:
    if source.raw_bytes.startswith(BOM_UTF8):
        return JsonTextEncoding.UTF8_WITH_BOM
    return JsonTextEncoding.UTF8


@dataclass(frozen=True, slots=True)
class ParsedJsonArtifact:
    """Immutable decoded view linked to unchanged source bytes."""

    source_artifact: SourceArtifact
    root: JsonObject
    text_encoding: JsonTextEncoding
    declared_schema_identifier: str | None
    declared_kind: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.source_artifact, SourceArtifact):
            raise JsonArtifactError(
                "source_artifact must be a SourceArtifact"
            )
        if not self.source_artifact.verify_integrity():
            raise JsonArtifactError(
                "source artifact integrity verification failed"
            )
        if (
            self.source_artifact.detected_container_format
            is not SourceContainerFormat.JSON_CANDIDATE
        ):
            raise JsonArtifactError(
                "source artifact is not a JSON object or array candidate"
            )
        if not isinstance(self.root, _MAPPING_PROXY_TYPE):
            raise JsonArtifactError(
                "root must be an immutable JSON object"
            )
        if not _is_frozen_json_value(self.root):
            raise JsonArtifactError(
                "root contains a mutable or unsupported JSON value"
            )
        if not isinstance(self.text_encoding, JsonTextEncoding):
            raise JsonArtifactError(
                "text_encoding must be a JsonTextEncoding"
            )
        if self.text_encoding is not _detect_text_encoding(
            self.source_artifact
        ):
            raise JsonArtifactError(
                "text_encoding does not match the source bytes"
            )
        if self.declared_schema_identifier != _optional_declared_string(
            self.root,
            "schema",
        ):
            raise JsonArtifactError(
                "declared_schema_identifier does not match the schema field"
            )
        if self.declared_kind != _optional_declared_string(
            self.root,
            "kind",
        ):
            raise JsonArtifactError(
                "declared_kind does not match the kind field"
            )

    @property
    def source_artifact_id(self) -> str:
        """Return the identity of the captured source artifact."""

        return self.source_artifact.source_artifact_id

    @property
    def content_sha256(self) -> str:
        """Return the digest of the original, unchanged source bytes."""

        return self.source_artifact.content_sha256

  def parse_json_artifact(source: SourceArtifact) -> ParsedJsonArtifact:
    """Decode one captured JSON artifact without executing its content."""

    if not isinstance(source, SourceArtifact):
        raise JsonArtifactError("source must be a SourceArtifact")
    if not source.verify_integrity():
        raise JsonArtifactError(
            "source artifact integrity verification failed"
        )

    encoding = _detect_text_encoding(source)
    try:
        text = source.raw_bytes.decode(encoding.value)
    except UnicodeDecodeError as exc:
        raise JsonEncodingError(
            "source bytes are not valid UTF-8 JSON text",
            byte_start=exc.start,
            byte_end=exc.end,
            reason=exc.reason,
        ) from exc

    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_non_finite_number,
            strict=True,
        )
    except (DuplicateJsonKeyError, NonFiniteJsonNumberError):
        raise
    except json.JSONDecodeError as exc:
        raise JsonSyntaxError(
            exc.msg,
            line_number=exc.lineno,
            column_number=exc.colno,
            character_offset=exc.pos,
        ) from exc
    except RecursionError as exc:
        raise JsonStructureError(
            "JSON nesting exceeds the decoder recursion bound"
        ) from exc

    if not isinstance(decoded, dict):
        raise JsonRootError(
            "published FRP JSON artifact root must be an object"
        )

    try:
        frozen_root = cast(JsonObject, _freeze_json_value(decoded))
        return ParsedJsonArtifact(
            source_artifact=source,
            root=frozen_root,
            text_encoding=encoding,
            declared_schema_identifier=_optional_declared_string(
                frozen_root,
                "schema",
            ),
            declared_kind=_optional_declared_string(
                frozen_root,
                "kind",
            ),
        )
    except RecursionError as exc:
        raise JsonStructureError(
            "JSON nesting exceeds the immutable-view recursion bound"
        ) from exc
