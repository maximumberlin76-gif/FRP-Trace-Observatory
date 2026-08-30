"""Exact read-only dispatch envelopes for verified FRP M31 documents.

This module begins only with a complete M31 published registry validation. It
creates one immutable envelope for each of the six approved document-to-mode
routes. The envelopes retain the exact boundary document, captured source,
strict parsed object, registration, and route identities. They do not parse a
second representation, reuse the legacy schema-only dispatcher, invoke mode
consumers, execute upstream content, normalize metrics, merge measurement
contours, reimplement processor semantics, mutate FRP, or write upstream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from artifact_auditor.m31_published_boundary_intake import (
    M31_PUBLISHED_REGISTRY_REVISION,
    M31PublishedDocument,
    M31PublishedDocumentRole,
)
from parsers.json_artifact import ParsedJsonArtifact
from parsers.source_artifact import SourceArtifact
from schemas.m31_published_registry import (
    M31PublishedModeRoute,
    M31PublishedRegistryValidation,
    resolve_m31_published_document,
    validate_m31_published_registry,
)
from schemas.registry import ObservatoryMode


__all__ = [
    "M31PublishedDispatchBatch",
    "M31PublishedDispatchError",
    "M31PublishedDocumentDispatch",
    "build_m31_published_dispatch_batch",
    "dispatch_m31_published_documents",
]


_HEX64: Final = re.compile(r"^[0-9a-f]{64}$")


class M31PublishedDispatchError(ValueError):
    """Raised when an M31 dispatch-envelope invariant is violated."""


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _expected_dispatch_sha256(
    validation: M31PublishedRegistryValidation,
    document: M31PublishedDocument,
    route: M31PublishedModeRoute,
) -> str:
    registration = route.registration
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "compatibility_key": registration.compatibility_key,
                "identifier_field": registration.identifier_field,
                "identifier_value": registration.identifier_value,
                "mode": route.mode.value,
                "raw_sha256": registration.raw_sha256,
                "registry_revision": validation.registry_revision,
                "role": document.identity.role.value,
                "source_path": registration.source_path,
            }
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class M31PublishedDocumentDispatch:
    """One exact M31 document reference and one approved mode route."""

    registry_validation: M31PublishedRegistryValidation
    document: M31PublishedDocument
    route: M31PublishedModeRoute
    dispatch_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.registry_validation,
            M31PublishedRegistryValidation,
        ):
            raise M31PublishedDispatchError(
                "registry_validation must be "
                "M31PublishedRegistryValidation"
            )
        if self.registry_validation.registry_revision != (
            M31_PUBLISHED_REGISTRY_REVISION
        ):
            raise M31PublishedDispatchError(
                "dispatch registry revision mismatch"
            )
        if not isinstance(self.document, M31PublishedDocument):
            raise M31PublishedDispatchError(
                "document must be M31PublishedDocument"
            )
        if not any(
            candidate is self.document
            for candidate in self.registry_validation.boundary.documents
        ):
            raise M31PublishedDispatchError(
                "document is not exact registry boundary evidence"
            )
        if not self.document.source_artifact.verify_integrity():
            raise M31PublishedDispatchError(
                "dispatch source integrity verification failed"
            )
        if (
            self.document.parsed_artifact.source_artifact
            is not self.document.source_artifact
        ):
            raise M31PublishedDispatchError(
                "dispatch parsed object differs from boundary source"
            )
        if not isinstance(self.route, M31PublishedModeRoute):
            raise M31PublishedDispatchError(
                "route must be M31PublishedModeRoute"
            )
        if not any(
            candidate is self.route
            for candidate in self.registry_validation.routes
        ):
            raise M31PublishedDispatchError(
                "route is not exact registry route evidence"
            )
        registration = resolve_m31_published_document(self.document)
        if self.route.registration is not registration:
            raise M31PublishedDispatchError(
                "route registration does not match boundary document"
            )
        if self.route.mode not in registration.observatory_modes:
            raise M31PublishedDispatchError(
                "route mode is not eligible for this M31 document"
            )
        if (
            not isinstance(self.dispatch_sha256, str)
            or not _HEX64.fullmatch(self.dispatch_sha256)
        ):
            raise M31PublishedDispatchError(
                "dispatch_sha256 must be lowercase hexadecimal SHA-256"
            )
        expected = _expected_dispatch_sha256(
            self.registry_validation,
            self.document,
            self.route,
        )
        if self.dispatch_sha256 != expected:
            raise M31PublishedDispatchError(
                "dispatch_sha256 does not bind the exact document and route"
            )

    @classmethod
    def create(
        cls,
        registry_validation: M31PublishedRegistryValidation,
        document: M31PublishedDocument,
        route: M31PublishedModeRoute,
    ) -> M31PublishedDocumentDispatch:
        """Create one envelope from exact existing registry evidence."""

        if not isinstance(
            registry_validation,
            M31PublishedRegistryValidation,
        ):
            raise M31PublishedDispatchError(
                "registry_validation must be "
                "M31PublishedRegistryValidation"
            )
        if not isinstance(document, M31PublishedDocument):
            raise M31PublishedDispatchError(
                "document must be M31PublishedDocument"
            )
        if not isinstance(route, M31PublishedModeRoute):
            raise M31PublishedDispatchError(
                "route must be M31PublishedModeRoute"
            )
        return cls(
            registry_validation=registry_validation,
            document=document,
            route=route,
            dispatch_sha256=_expected_dispatch_sha256(
                registry_validation,
                document,
                route,
            ),
        )

    @property
    def role(self) -> M31PublishedDocumentRole:
        """Return the exact canonical M31 document role."""

        return self.document.identity.role

    @property
    def mode(self) -> ObservatoryMode:
        """Return the exact existing Observatory mode."""

        return self.route.mode

    @property
    def source_artifact(self) -> SourceArtifact:
        """Return the unchanged boundary source-artifact object."""

        return self.document.source_artifact

    @property
    def parsed_artifact(self) -> ParsedJsonArtifact:
        """Return the unchanged strict boundary parsed-object view."""

        return self.document.parsed_artifact

    @property
    def raw_bytes(self) -> bytes:
        """Return the unchanged captured upstream bytes."""

        return self.document.raw_bytes

    @property
    def dispatch_key(
        self,
    ) -> tuple[M31PublishedDocumentRole, ObservatoryMode, str]:
        """Return the exact role, mode, and raw-digest dispatch key."""

        return (
            self.role,
            self.mode,
            self.route.registration.raw_sha256,
        )


@dataclass(frozen=True, slots=True)
class M31PublishedDispatchBatch:
    """Complete ordered six-envelope M31 dispatch boundary."""

    registry_validation: M31PublishedRegistryValidation
    dispatches: tuple[M31PublishedDocumentDispatch, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.registry_validation,
            M31PublishedRegistryValidation,
        ):
            raise M31PublishedDispatchError(
                "registry_validation must be "
                "M31PublishedRegistryValidation"
            )
        if not isinstance(self.dispatches, tuple):
            raise M31PublishedDispatchError(
                "dispatches must be a tuple"
            )
        if any(
            not isinstance(dispatch, M31PublishedDocumentDispatch)
            for dispatch in self.dispatches
        ):
            raise M31PublishedDispatchError(
                "dispatches must contain M31PublishedDocumentDispatch values"
            )
        expected_pairs = tuple(
            (document, route)
            for document in self.registry_validation.boundary.documents
            for route in self.registry_validation.routes
            if route.registration.role is document.identity.role
        )
        if len(self.dispatches) != len(expected_pairs):
            raise M31PublishedDispatchError(
                "dispatch inventory length mismatch"
            )
        for dispatch, (document, route) in zip(
            self.dispatches,
            expected_pairs,
            strict=True,
        ):
            if dispatch.registry_validation is not self.registry_validation:
                raise M31PublishedDispatchError(
                    "dispatch registry evidence identity mismatch"
                )
            if dispatch.document is not document or dispatch.route is not route:
                raise M31PublishedDispatchError(
                    "dispatch order or registry evidence identity mismatch"
                )
        dispatch_keys = tuple(
            dispatch.dispatch_key for dispatch in self.dispatches
        )
        if len(set(dispatch_keys)) != len(dispatch_keys):
            raise M31PublishedDispatchError(
                "dispatch keys must be unique"
            )
        dispatch_digests = tuple(
            dispatch.dispatch_sha256 for dispatch in self.dispatches
        )
        if len(set(dispatch_digests)) != len(dispatch_digests):
            raise M31PublishedDispatchError(
                "dispatch digests must be unique"
            )
        expected_mode_counts = {
            ObservatoryMode.ARTIFACT_AUDITOR: (
                self.registry_validation.artifact_auditor_route_count
            ),
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER: (
                self.registry_validation
                .ternary_transition_visualizer_route_count
            ),
            ObservatoryMode.TRACE_EXPLORER: (
                self.registry_validation.trace_explorer_route_count
            ),
        }
        for mode, expected_count in expected_mode_counts.items():
            observed_count = sum(
                dispatch.mode is mode for dispatch in self.dispatches
            )
            if observed_count != expected_count:
                raise M31PublishedDispatchError(
                    f"{mode.value} dispatch count mismatch"
                )

    @property
    def registry_revision(self) -> str:
        """Return the exact M31 registry revision."""

        return self.registry_validation.registry_revision

    @property
    def published_document_count(self) -> int:
        """Return the exact boundary document count."""

        return len(self.registry_validation.boundary.documents)

    @property
    def total_dispatch_count(self) -> int:
        """Return the complete approved route count."""

        return len(self.dispatches)

    def dispatches_for_mode(
        self,
        mode: ObservatoryMode,
    ) -> tuple[M31PublishedDocumentDispatch, ...]:
        """Return source-order envelopes for one exact existing mode."""

        if not isinstance(mode, ObservatoryMode):
            raise M31PublishedDispatchError(
                "mode must be ObservatoryMode"
            )
        return tuple(
            dispatch
            for dispatch in self.dispatches
            if dispatch.mode is mode
        )

    def dispatches_for_role(
        self,
        role: M31PublishedDocumentRole,
    ) -> tuple[M31PublishedDocumentDispatch, ...]:
        """Return registered-order envelopes for one exact document role."""

        if not isinstance(role, M31PublishedDocumentRole):
            raise M31PublishedDispatchError(
                "role must be M31PublishedDocumentRole"
            )
        matches = tuple(
            dispatch
            for dispatch in self.dispatches
            if dispatch.role is role
        )
        if not matches:
            raise M31PublishedDispatchError(
                f"unknown M31 dispatch role: {role!r}"
            )
        return matches

    def dispatch_for(
        self,
        role: M31PublishedDocumentRole,
        mode: ObservatoryMode,
    ) -> M31PublishedDocumentDispatch:
        """Resolve one exact eligible document-to-mode envelope."""

        if not isinstance(mode, ObservatoryMode):
            raise M31PublishedDispatchError(
                "mode must be ObservatoryMode"
            )
        role_dispatches = self.dispatches_for_role(role)
        matches = tuple(
            dispatch
            for dispatch in role_dispatches
            if dispatch.mode is mode
        )
        if len(matches) != 1:
            raise M31PublishedDispatchError(
                f"role {role.value!r} is not eligible for {mode.value!r}"
            )
        return matches[0]


def build_m31_published_dispatch_batch(
    registry_validation: M31PublishedRegistryValidation,
) -> M31PublishedDispatchBatch:
    """Create all exact envelopes without invoking any mode consumer."""

    if not isinstance(
        registry_validation,
        M31PublishedRegistryValidation,
    ):
        raise M31PublishedDispatchError(
            "registry_validation must be M31PublishedRegistryValidation"
        )
    dispatches = tuple(
        M31PublishedDocumentDispatch.create(
            registry_validation,
            document,
            route,
        )
        for document in registry_validation.boundary.documents
        for route in registry_validation.routes
        if route.registration.role is document.identity.role
    )
    return M31PublishedDispatchBatch(
        registry_validation=registry_validation,
        dispatches=dispatches,
    )


def dispatch_m31_published_documents(
    upstream_root: str | Path,
    *,
    loaded_at: datetime | None = None,
) -> M31PublishedDispatchBatch:
    """Validate the M31 boundary and registry, then create six envelopes."""

    registry_validation = validate_m31_published_registry(
        upstream_root,
        loaded_at=loaded_at,
    )
    return build_m31_published_dispatch_batch(registry_validation)


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create six exact read-only M31 document-to-mode dispatch "
            "envelopes without invoking consumers or writing upstream."
        )
    )
    parser.add_argument("--upstream-root", required=True, type=Path)
    arguments = parser.parse_args()
    result = dispatch_m31_published_documents(arguments.upstream_root)
    auditor_count = len(
        result.dispatches_for_mode(ObservatoryMode.ARTIFACT_AUDITOR)
    )
    visualizer_count = len(
        result.dispatches_for_mode(
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER
        )
    )
    explorer_count = len(
        result.dispatches_for_mode(ObservatoryMode.TRACE_EXPLORER)
    )
    print("FRP Observatory M31 published dispatch boundary: PASS")
    print(f"registry_revision={result.registry_revision}")
    print(f"published_documents={result.published_document_count}")
    print(f"dispatch_envelopes={result.total_dispatch_count}")
    print(f"artifact_auditor_dispatches={auditor_count}")
    print(
        "ternary_transition_visualizer_dispatches="
        f"{visualizer_count}"
    )
    print(f"trace_explorer_dispatches={explorer_count}")
    print("legacy_schema_only_dispatch_reuse=forbidden")
    print("mode_consumer_invocation=deferred")
    print("source_execution=forbidden")
    print("metric_normalization=forbidden")
    print("semantic_reimplementation=forbidden")
    print("source_mutation=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
