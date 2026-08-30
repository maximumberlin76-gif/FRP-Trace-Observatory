"""Exact routing registry for verified FRP M31 published documents.

The registry consumes only immutable documents produced by the M31 published
boundary intake.  It binds every document to one canonical role and routes
only eligible documents into the three existing Observatory modes.  It does
not execute upstream sources, normalize metrics, merge measurement contours,
reimplement processor semantics, mutate FRP, or write upstream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Mapping

from artifact_auditor.m31_published_boundary_intake import (
    M31_PUBLISHED_DOCUMENT_IDENTITIES,
    M31_PUBLISHED_REGISTRY_REVISION,
    M31PublishedBoundaryValidation,
    M31PublishedDocument,
    M31PublishedDocumentIdentity,
    M31PublishedDocumentRole,
    validate_m31_published_boundary,
)
from schemas.registry import ObservatoryMode


__all__ = [
    "M31_PUBLISHED_DOCUMENT_REGISTRATIONS",
    "M31PublishedDocumentIdentityError",
    "M31PublishedDocumentRegistration",
    "M31PublishedMeasurementContour",
    "M31PublishedModeRoute",
    "M31PublishedRegistryError",
    "M31PublishedRegistryValidation",
    "UnknownM31PublishedDocumentRoleError",
    "registration_for_m31_role",
    "resolve_m31_published_document",
    "routes_for_m31_document",
    "validate_m31_document_registry",
    "validate_m31_published_registry",
]


_HEX64: Final = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY_BY_ROLE: Final = MappingProxyType(
    {
        identity.role: identity
        for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
    }
)


class M31PublishedMeasurementContour(StrEnum):
    """Non-interchangeable roles of the M31 publication documents."""

    FORMAL_SCHEMA_DEFINITION = "formal_schema_definition"
    PHASE_INTERFERENCE_ACTIVE_ZERO_THERMAL_EVIDENCE = (
        "phase_interference_active_zero_thermal_evidence"
    )
    PUBLICATION_MANIFEST = "publication_manifest"
    PUBLICATION_QUALIFICATION = "publication_qualification"


class M31PublishedRegistryError(ValueError):
    """Raised when the exact M31 document registry is invalid."""


class UnknownM31PublishedDocumentRoleError(LookupError):
    """Raised when no exact M31 document role is registered."""

    def __init__(self, role: M31PublishedDocumentRole) -> None:
        super().__init__(f"unknown M31 published document role: {role!r}")
        self.role = role


class M31PublishedDocumentIdentityError(LookupError):
    """Raised when a known M31 document differs from its registration."""

    def __init__(
        self,
        role: M31PublishedDocumentRole,
        field: str,
        observed: object,
        expected: object,
    ) -> None:
        super().__init__(
            f"M31 published document {role.value!r} {field} mismatch: "
            f"{observed!r} != {expected!r}"
        )
        self.role = role
        self.field = field
        self.observed = observed
        self.expected = expected


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _compatibility_key(
    identity: M31PublishedDocumentIdentity,
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "identifier_field": identity.identifier_field,
                "identifier_value": identity.identifier_value,
                "raw_sha256": identity.raw_sha256,
                "role": identity.role.value,
            }
        )
    ).hexdigest()


_EXPECTED_CONTOUR_BY_ROLE: Final = MappingProxyType(
    {
        M31PublishedDocumentRole.FORMAL_SCHEMA: (
            M31PublishedMeasurementContour.FORMAL_SCHEMA_DEFINITION
        ),
        M31PublishedDocumentRole.EVIDENCE: (
            M31PublishedMeasurementContour
            .PHASE_INTERFERENCE_ACTIVE_ZERO_THERMAL_EVIDENCE
        ),
        M31PublishedDocumentRole.MANIFEST: (
            M31PublishedMeasurementContour.PUBLICATION_MANIFEST
        ),
        M31PublishedDocumentRole.QUALIFICATION: (
            M31PublishedMeasurementContour.PUBLICATION_QUALIFICATION
        ),
    }
)

_AUDITOR_ONLY: Final = (ObservatoryMode.ARTIFACT_AUDITOR,)
_ALL_MODES: Final = (
    ObservatoryMode.ARTIFACT_AUDITOR,
    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    ObservatoryMode.TRACE_EXPLORER,
)
_EXPECTED_MODES_BY_ROLE: Final = MappingProxyType(
    {
        M31PublishedDocumentRole.FORMAL_SCHEMA: _AUDITOR_ONLY,
        M31PublishedDocumentRole.EVIDENCE: _ALL_MODES,
        M31PublishedDocumentRole.MANIFEST: _AUDITOR_ONLY,
        M31PublishedDocumentRole.QUALIFICATION: _AUDITOR_ONLY,
    }
)


@dataclass(frozen=True, slots=True)
class M31PublishedDocumentRegistration:
    """One exact M31 document identity and its eligible modes."""

    document_identity: M31PublishedDocumentIdentity
    measurement_contour: M31PublishedMeasurementContour
    observatory_modes: tuple[ObservatoryMode, ...]
    compatibility_key: str
    upstream_milestone: str = "M31"
    upstream_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not isinstance(
            self.document_identity,
            M31PublishedDocumentIdentity,
        ):
            raise M31PublishedRegistryError(
                "document_identity must be M31PublishedDocumentIdentity"
            )
        canonical = _IDENTITY_BY_ROLE.get(self.document_identity.role)
        if canonical is not self.document_identity:
            raise M31PublishedRegistryError(
                "document_identity must be the canonical M31 identity"
            )
        if not isinstance(
            self.measurement_contour,
            M31PublishedMeasurementContour,
        ):
            raise M31PublishedRegistryError(
                "measurement_contour must be "
                "M31PublishedMeasurementContour"
            )
        expected_contour = _EXPECTED_CONTOUR_BY_ROLE[
            self.document_identity.role
        ]
        if self.measurement_contour is not expected_contour:
            raise M31PublishedRegistryError(
                "measurement_contour does not match document role"
            )
        if not isinstance(self.observatory_modes, tuple):
            raise M31PublishedRegistryError(
                "observatory_modes must be a tuple"
            )
        if any(
            not isinstance(mode, ObservatoryMode)
            for mode in self.observatory_modes
        ):
            raise M31PublishedRegistryError(
                "observatory_modes must contain ObservatoryMode values"
            )
        expected_modes = _EXPECTED_MODES_BY_ROLE[
            self.document_identity.role
        ]
        if self.observatory_modes != expected_modes:
            raise M31PublishedRegistryError(
                "observatory_modes do not match document role"
            )
        if (
            not isinstance(self.compatibility_key, str)
            or not _HEX64.fullmatch(self.compatibility_key)
        ):
            raise M31PublishedRegistryError(
                "compatibility_key must be lowercase hexadecimal SHA-256"
            )
        if self.compatibility_key != _compatibility_key(
            self.document_identity
        ):
            raise M31PublishedRegistryError(
                "compatibility_key must use only role, identifier field, "
                "identifier value, and raw SHA-256"
            )
        if self.upstream_milestone != "M31":
            raise M31PublishedRegistryError(
                "upstream_milestone must be M31"
            )
        if self.upstream_version != "1.0.0":
            raise M31PublishedRegistryError(
                "upstream_version must be 1.0.0"
            )

    @property
    def role(self) -> M31PublishedDocumentRole:
        """Return the exact document role."""

        return self.document_identity.role

    @property
    def source_path(self) -> str:
        """Return the exact upstream path."""

        return self.document_identity.source_path

    @property
    def identifier_field(self) -> str:
        """Return the exact JSON identifier field."""

        return self.document_identity.identifier_field

    @property
    def identifier_value(self) -> str:
        """Return the exact JSON identifier value."""

        return self.document_identity.identifier_value

    @property
    def artifact_kind(self) -> str | None:
        """Return the exact declared kind when the document has one."""

        return self.document_identity.kind

    @property
    def byte_length(self) -> int:
        """Return the exact raw byte length."""

        return self.document_identity.byte_length

    @property
    def raw_sha256(self) -> str:
        """Return the exact raw SHA-256 identity."""

        return self.document_identity.raw_sha256

    @property
    def dispatch_key(self) -> tuple[
        M31PublishedDocumentRole,
        str,
        str,
        str,
    ]:
        """Return the exact role and raw-identity dispatch key."""

        return (
            self.role,
            self.identifier_field,
            self.identifier_value,
            self.raw_sha256,
        )


@dataclass(frozen=True, slots=True)
class M31PublishedModeRoute:
    """One immutable route into an existing Observatory mode."""

    registration: M31PublishedDocumentRegistration
    mode: ObservatoryMode

    def __post_init__(self) -> None:
        if not isinstance(
            self.registration,
            M31PublishedDocumentRegistration,
        ):
            raise M31PublishedRegistryError(
                "route registration must be "
                "M31PublishedDocumentRegistration"
            )
        if not isinstance(self.mode, ObservatoryMode):
            raise M31PublishedRegistryError(
                "route mode must be ObservatoryMode"
            )
        if self.mode not in self.registration.observatory_modes:
            raise M31PublishedRegistryError(
                "route mode is not declared by the registration"
            )


M31_PUBLISHED_DOCUMENT_REGISTRATIONS: Final = (
    M31PublishedDocumentRegistration(
        document_identity=M31_PUBLISHED_DOCUMENT_IDENTITIES[0],
        measurement_contour=(
            M31PublishedMeasurementContour.FORMAL_SCHEMA_DEFINITION
        ),
        observatory_modes=_AUDITOR_ONLY,
        compatibility_key=(
            "0a3b92c08456517bd03e5c49ed683d490"
            "869688e6a2039f021228fc8db66b8b2"
        ),
    ),
    M31PublishedDocumentRegistration(
        document_identity=M31_PUBLISHED_DOCUMENT_IDENTITIES[1],
        measurement_contour=(
            M31PublishedMeasurementContour
            .PHASE_INTERFERENCE_ACTIVE_ZERO_THERMAL_EVIDENCE
        ),
        observatory_modes=_ALL_MODES,
        compatibility_key=(
            "ac1a9fae03831d912e1b1abf42dd7371"
            "3b506a10b28c7b65041cca2e2b56e296"
        ),
    ),
    M31PublishedDocumentRegistration(
        document_identity=M31_PUBLISHED_DOCUMENT_IDENTITIES[2],
        measurement_contour=(
            M31PublishedMeasurementContour.PUBLICATION_MANIFEST
        ),
        observatory_modes=_AUDITOR_ONLY,
        compatibility_key=(
            "8263f4f97b459fcdb5defbe2d9881bd1"
            "b7b0c52a3a94830dfb5cb16a982bc59e"
        ),
    ),
    M31PublishedDocumentRegistration(
        document_identity=M31_PUBLISHED_DOCUMENT_IDENTITIES[3],
        measurement_contour=(
            M31PublishedMeasurementContour.PUBLICATION_QUALIFICATION
        ),
        observatory_modes=_AUDITOR_ONLY,
        compatibility_key=(
            "594bd40bba735ff9572cde8e6cc38cfc"
            "bb184748aaa0ce5f394a38d24737187a"
        ),
    ),
)


def _build_registration_index(
    registrations: tuple[M31PublishedDocumentRegistration, ...],
) -> Mapping[
    M31PublishedDocumentRole,
    M31PublishedDocumentRegistration,
]:
    mutable: dict[
        M31PublishedDocumentRole,
        M31PublishedDocumentRegistration,
    ] = {}
    dispatch_keys: set[
        tuple[M31PublishedDocumentRole, str, str, str]
    ] = set()
    for registration in registrations:
        if registration.role in mutable:
            raise M31PublishedRegistryError(
                f"duplicate M31 document role: {registration.role.value!r}"
            )
        if registration.dispatch_key in dispatch_keys:
            raise M31PublishedRegistryError(
                "duplicate M31 document dispatch key"
            )
        mutable[registration.role] = registration
        dispatch_keys.add(registration.dispatch_key)
    return MappingProxyType(mutable)


_REGISTRATION_BY_ROLE: Final = _build_registration_index(
    M31_PUBLISHED_DOCUMENT_REGISTRATIONS
)


def registration_for_m31_role(
    role: M31PublishedDocumentRole,
) -> M31PublishedDocumentRegistration:
    """Resolve one exact M31 document role without aliases."""

    if not isinstance(role, M31PublishedDocumentRole):
        raise M31PublishedRegistryError(
            "role must be M31PublishedDocumentRole"
        )
    try:
        return _REGISTRATION_BY_ROLE[role]
    except KeyError as exc:
        raise UnknownM31PublishedDocumentRoleError(role) from exc


def _require_document_field(
    registration: M31PublishedDocumentRegistration,
    field: str,
    observed: object,
    expected: object,
) -> None:
    if observed != expected:
        raise M31PublishedDocumentIdentityError(
            registration.role,
            field,
            observed,
            expected,
        )


def resolve_m31_published_document(
    document: M31PublishedDocument,
) -> M31PublishedDocumentRegistration:
    """Bind one verified M31 document to its exact registration."""

    if not isinstance(document, M31PublishedDocument):
        raise M31PublishedRegistryError(
            "document must be M31PublishedDocument"
        )
    registration = registration_for_m31_role(document.identity.role)
    if document.identity is not registration.document_identity:
        raise M31PublishedDocumentIdentityError(
            registration.role,
            "document_identity",
            document.identity,
            registration.document_identity,
        )
    _require_document_field(
        registration,
        "source_path",
        document.source_artifact.source_path,
        registration.source_path,
    )
    _require_document_field(
        registration,
        "byte_length",
        document.source_artifact.byte_length,
        registration.byte_length,
    )
    _require_document_field(
        registration,
        "raw_sha256",
        document.source_artifact.content_sha256,
        registration.raw_sha256,
    )
    _require_document_field(
        registration,
        "identifier_value",
        document.root.get(registration.identifier_field),
        registration.identifier_value,
    )
    if registration.artifact_kind is not None:
        _require_document_field(
            registration,
            "artifact_kind",
            document.parsed_artifact.declared_kind,
            registration.artifact_kind,
        )
    if not document.source_artifact.verify_integrity():
        raise M31PublishedDocumentIdentityError(
            registration.role,
            "captured_integrity",
            False,
            True,
        )
    return registration


def routes_for_m31_document(
    document: M31PublishedDocument,
) -> tuple[M31PublishedModeRoute, ...]:
    """Return only the existing modes declared for one verified document."""

    registration = resolve_m31_published_document(document)
    return tuple(
        M31PublishedModeRoute(registration=registration, mode=mode)
        for mode in registration.observatory_modes
    )


@dataclass(frozen=True, slots=True)
class M31PublishedRegistryValidation:
    """Successful exact routing evidence for one validated M31 boundary."""

    boundary: M31PublishedBoundaryValidation
    registry_revision: str
    registrations: tuple[M31PublishedDocumentRegistration, ...]
    routes: tuple[M31PublishedModeRoute, ...]
    artifact_auditor_route_count: int
    ternary_transition_visualizer_route_count: int
    trace_explorer_route_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.boundary, M31PublishedBoundaryValidation):
            raise M31PublishedRegistryError(
                "boundary must be M31PublishedBoundaryValidation"
            )
        if self.boundary.registry_revision != M31_PUBLISHED_REGISTRY_REVISION:
            raise M31PublishedRegistryError(
                "boundary registry revision mismatch"
            )
        if self.registry_revision != M31_PUBLISHED_REGISTRY_REVISION:
            raise M31PublishedRegistryError(
                "registry validation revision mismatch"
            )
        if self.registrations != M31_PUBLISHED_DOCUMENT_REGISTRATIONS:
            raise M31PublishedRegistryError(
                "registry validation registration inventory mismatch"
            )
        expected_registrations = tuple(
            resolve_m31_published_document(document)
            for document in self.boundary.documents
        )
        if expected_registrations != self.registrations:
            raise M31PublishedRegistryError(
                "boundary document registration order mismatch"
            )
        expected_routes = tuple(
            M31PublishedModeRoute(
                registration=registration,
                mode=mode,
            )
            for registration in M31_PUBLISHED_DOCUMENT_REGISTRATIONS
            for mode in registration.observatory_modes
        )
        if self.routes != expected_routes:
            raise M31PublishedRegistryError(
                "registry validation route inventory mismatch"
            )
        if self.artifact_auditor_route_count != 4:
            raise M31PublishedRegistryError(
                "artifact auditor route count mismatch"
            )
        if self.ternary_transition_visualizer_route_count != 1:
            raise M31PublishedRegistryError(
                "transition visualizer route count mismatch"
            )
        if self.trace_explorer_route_count != 1:
            raise M31PublishedRegistryError(
                "trace explorer route count mismatch"
            )

    def routes_for_mode(
        self,
        mode: ObservatoryMode,
    ) -> tuple[M31PublishedModeRoute, ...]:
        """Return exact routes for one existing Observatory mode."""

        if not isinstance(mode, ObservatoryMode):
            raise M31PublishedRegistryError(
                "mode must be ObservatoryMode"
            )
        return tuple(route for route in self.routes if route.mode is mode)


def validate_m31_document_registry(
    boundary: M31PublishedBoundaryValidation,
) -> M31PublishedRegistryValidation:
    """Validate exact registration and routing for one M31 boundary."""

    if not isinstance(boundary, M31PublishedBoundaryValidation):
        raise M31PublishedRegistryError(
            "boundary must be M31PublishedBoundaryValidation"
        )
    registrations = tuple(
        resolve_m31_published_document(document)
        for document in boundary.documents
    )
    if registrations != M31_PUBLISHED_DOCUMENT_REGISTRATIONS:
        raise M31PublishedRegistryError(
            "boundary document inventory mismatch"
        )
    routes = tuple(
        route
        for document in boundary.documents
        for route in routes_for_m31_document(document)
    )
    auditor_count = sum(
        route.mode is ObservatoryMode.ARTIFACT_AUDITOR
        for route in routes
    )
    visualizer_count = sum(
        route.mode is ObservatoryMode.TERNARY_TRANSITION_VISUALIZER
        for route in routes
    )
    explorer_count = sum(
        route.mode is ObservatoryMode.TRACE_EXPLORER
        for route in routes
    )
    return M31PublishedRegistryValidation(
        boundary=boundary,
        registry_revision=M31_PUBLISHED_REGISTRY_REVISION,
        registrations=registrations,
        routes=routes,
        artifact_auditor_route_count=auditor_count,
        ternary_transition_visualizer_route_count=visualizer_count,
        trace_explorer_route_count=explorer_count,
    )


def validate_m31_published_registry(
    upstream_root: str | Path,
    *,
    loaded_at: datetime | None = None,
) -> M31PublishedRegistryValidation:
    """Validate M31 bytes, then exact mode routing, without mutation."""

    boundary = validate_m31_published_boundary(
        upstream_root,
        loaded_at=loaded_at,
    )
    return validate_m31_document_registry(boundary)


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate exact FRP M31 published-document registration and "
            "routing into the three existing Observatory modes."
        )
    )
    parser.add_argument("--upstream-root", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate_m31_published_registry(arguments.upstream_root)
    print("FRP Observatory M31 published document registry: PASS")
    print(f"registry_revision={result.registry_revision}")
    print(f"published_documents={len(result.registrations)}")
    print(f"mode_routes={len(result.routes)}")
    print(
        "artifact_auditor_routes="
        f"{result.artifact_auditor_route_count}"
    )
    print(
        "ternary_transition_visualizer_routes="
        f"{result.ternary_transition_visualizer_route_count}"
    )
    print(f"trace_explorer_routes={result.trace_explorer_route_count}")
    print("schema_aliases=forbidden")
    print("metric_normalization=forbidden")
    print("source_execution=forbidden")
    print("semantic_reimplementation=forbidden")
    print("source_mutation=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
