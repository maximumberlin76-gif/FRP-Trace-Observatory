"""Exact routing registry for verified FRP M30 published demo members.

This registry is deliberately separate from the audited v1.8.0 compatibility
inventory.  It consumes only identities already verified by the M30 published
boundary intake, reuses the three existing Observatory modes, and records no
processor behavior.  Resolution is exact: member id, source path, schema
identifier, byte length, raw SHA-256, and mode routing must all match.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Final, Mapping

from artifact_auditor.m30_archive_intake import FRP_M30_ARCHIVE_SHA256
from artifact_auditor.m30_published_boundary_intake import (
    PublishedBoundaryValidation,
    PublishedDemoMember,
    validate_m30_published_boundary,
)
from schemas.registry import ObservatoryMode


__all__ = [
    "M30_PUBLISHED_MEMBER_REGISTRATIONS",
    "M30_PUBLISHED_REGISTRY_REVISION",
    "M30PublishedRegistryError",
    "PublishedMeasurementContour",
    "PublishedMemberIdentityError",
    "PublishedMemberRegistration",
    "PublishedModeRoute",
    "PublishedRegistryValidation",
    "UnknownPublishedMemberError",
    "registration_for_member_id",
    "resolve_published_member",
    "routes_for_published_member",
    "validate_m30_published_registry",
    "validate_published_registry",
]


M30_PUBLISHED_REGISTRY_REVISION: Final = "m30-published-boundary-v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PublishedMeasurementContour(StrEnum):
    """Separate published measurement contours; no contour is conflated."""

    M16_FPGA_PREPARATION_EXECUTION = "m16_fpga_preparation_execution"
    M27_LONG_RUN_TELEMETRY_SEMANTICS = "m27_long_run_telemetry_semantics"
    M28_UPSTREAM_INTEGRATION_CONTRACT = "m28_upstream_integration_contract"
    M28_HIERARCHICAL_SCALING_QUALIFICATION = (
        "m28_hierarchical_scaling_qualification"
    )


class M30PublishedRegistryError(ValueError):
    """Raised when published registry metadata is internally invalid."""


class UnknownPublishedMemberError(LookupError):
    """Raised when no exact published member id is registered."""

    def __init__(self, member_id: str) -> None:
        super().__init__(f"unknown published member id: {member_id!r}")
        self.member_id = member_id


class PublishedMemberIdentityError(LookupError):
    """Raised when a known member differs from its fixed identity."""

    def __init__(
        self,
        member_id: str,
        field: str,
        observed: object,
        expected: object,
    ) -> None:
        super().__init__(
            f"published member {member_id!r} {field} mismatch: "
            f"{observed!r} != {expected!r}"
        )
        self.member_id = member_id
        self.field = field
        self.observed = observed
        self.expected = expected


def _validate_text(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(character.isspace() for character in value)
    ):
        raise M30PublishedRegistryError(
            f"{field} must be nonempty without whitespace"
        )
    return value


def _validate_relative_path(value: object, field: str) -> str:
    text = _validate_text(value, field)
    if "\\" in text or "\x00" in text:
        raise M30PublishedRegistryError(
            f"{field} must be a relative POSIX path"
        )
    path = PurePosixPath(text)
    if path.is_absolute() or any(
        part in {"", ".", ".."} for part in text.split("/")
    ):
        raise M30PublishedRegistryError(
            f"{field} must be a safe relative POSIX path"
        )
    return text


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _compatibility_key(
    member_id: str,
    schema_identifier: str,
    raw_sha256: str,
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "member_id": member_id,
                "schema_identifier": schema_identifier,
                "raw_sha256": raw_sha256,
            }
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class PublishedMemberRegistration:
    """One exact M29 package member and its allowed Observatory modes."""

    member_id: str
    source_path: str
    schema_identifier: str
    measurement_contour: PublishedMeasurementContour
    observatory_modes: tuple[ObservatoryMode, ...]
    byte_length: int
    raw_sha256: str
    compatibility_key: str
    upstream_release: str

    def __post_init__(self) -> None:
        _validate_text(self.member_id, "member_id")
        _validate_relative_path(self.source_path, "source_path")
        _validate_text(self.schema_identifier, "schema_identifier")
        _validate_text(self.upstream_release, "upstream_release")
        if not isinstance(
            self.measurement_contour,
            PublishedMeasurementContour,
        ):
            raise M30PublishedRegistryError(
                "measurement_contour must be PublishedMeasurementContour"
            )
        if not isinstance(self.observatory_modes, tuple):
            raise M30PublishedRegistryError(
                "observatory_modes must be a tuple"
            )
        if not self.observatory_modes:
            raise M30PublishedRegistryError(
                "observatory_modes must not be empty"
            )
        if any(
            not isinstance(mode, ObservatoryMode)
            for mode in self.observatory_modes
        ):
            raise M30PublishedRegistryError(
                "observatory_modes must contain ObservatoryMode values"
            )
        if len(set(self.observatory_modes)) != len(self.observatory_modes):
            raise M30PublishedRegistryError(
                "observatory_modes must be unique"
            )
        if (
            not isinstance(self.byte_length, int)
            or isinstance(self.byte_length, bool)
            or self.byte_length <= 0
        ):
            raise M30PublishedRegistryError(
                "byte_length must be a positive integer"
            )
        if not isinstance(self.raw_sha256, str) or not _HEX64.fullmatch(
            self.raw_sha256
        ):
            raise M30PublishedRegistryError(
                "raw_sha256 must be lowercase hexadecimal SHA-256"
            )
        if not isinstance(
            self.compatibility_key,
            str,
        ) or not _HEX64.fullmatch(self.compatibility_key):
            raise M30PublishedRegistryError(
                "compatibility_key must be lowercase hexadecimal SHA-256"
            )
        expected_key = _compatibility_key(
            self.member_id,
            self.schema_identifier,
            self.raw_sha256,
        )
        if self.compatibility_key != expected_key:
            raise M30PublishedRegistryError(
                "compatibility_key must use only member_id, "
                "schema_identifier, and raw_sha256"
            )

    @property
    def dispatch_key(self) -> tuple[str, str, str]:
        """Return the exact release-independent identity key."""

        return (
            self.member_id,
            self.schema_identifier,
            self.raw_sha256,
        )


@dataclass(frozen=True, slots=True)
class PublishedModeRoute:
    """One immutable eligibility route into an existing Observatory mode."""

    registration: PublishedMemberRegistration
    mode: ObservatoryMode

    def __post_init__(self) -> None:
        if not isinstance(
            self.registration,
            PublishedMemberRegistration,
        ):
            raise M30PublishedRegistryError(
                "route registration must be PublishedMemberRegistration"
            )
        if not isinstance(self.mode, ObservatoryMode):
            raise M30PublishedRegistryError(
                "route mode must be ObservatoryMode"
            )
        if self.mode not in self.registration.observatory_modes:
            raise M30PublishedRegistryError(
                "route mode is not declared by the registration"
            )


@dataclass(frozen=True, slots=True)
class PublishedRegistryValidation:
    """Successful exact routing evidence for one validated M30 boundary."""

    archive_sha256: str
    registry_revision: str
    registrations: tuple[PublishedMemberRegistration, ...]
    routes: tuple[PublishedModeRoute, ...]
    artifact_auditor_route_count: int
    ternary_transition_visualizer_route_count: int
    trace_explorer_route_count: int

    def __post_init__(self) -> None:
        if self.archive_sha256 != FRP_M30_ARCHIVE_SHA256:
            raise M30PublishedRegistryError(
                "registry validation archive digest mismatch"
            )
        if self.registry_revision != M30_PUBLISHED_REGISTRY_REVISION:
            raise M30PublishedRegistryError(
                "registry validation revision mismatch"
            )
        if self.registrations != M30_PUBLISHED_MEMBER_REGISTRATIONS:
            raise M30PublishedRegistryError(
                "registry validation registration inventory mismatch"
            )
        expected_routes = tuple(
            PublishedModeRoute(registration=registration, mode=mode)
            for registration in M30_PUBLISHED_MEMBER_REGISTRATIONS
            for mode in registration.observatory_modes
        )
        if self.routes != expected_routes:
            raise M30PublishedRegistryError(
                "registry validation route inventory mismatch"
            )
        if self.artifact_auditor_route_count != 4:
            raise M30PublishedRegistryError(
                "artifact auditor route count mismatch"
            )
        if self.ternary_transition_visualizer_route_count != 2:
            raise M30PublishedRegistryError(
                "transition visualizer route count mismatch"
            )
        if self.trace_explorer_route_count != 1:
            raise M30PublishedRegistryError(
                "trace explorer route count mismatch"
            )

    def routes_for_mode(
        self,
        mode: ObservatoryMode,
    ) -> tuple[PublishedModeRoute, ...]:
        """Return exact routes for one existing Observatory mode."""

        if not isinstance(mode, ObservatoryMode):
            raise M30PublishedRegistryError(
                "mode must be ObservatoryMode"
            )
        return tuple(route for route in self.routes if route.mode is mode)


M30_PUBLISHED_MEMBER_REGISTRATIONS: Final = (
    PublishedMemberRegistration(
        member_id="m16-fpga-preparation-execution-trace",
        source_path=(
            "artifacts/m19/execution/"
            "m16-fpga-preparation-execution-trace.json"
        ),
        schema_identifier=(
            "frp.m16.fpga_preparation_execution_trace.v2.1.0"
        ),
        measurement_contour=(
            PublishedMeasurementContour.M16_FPGA_PREPARATION_EXECUTION
        ),
        observatory_modes=(
            ObservatoryMode.ARTIFACT_AUDITOR,
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            ObservatoryMode.TRACE_EXPLORER,
        ),
        byte_length=9013,
        raw_sha256=(
            "7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f"
        ),
        compatibility_key=(
            "a221aecb0d24518c8a2dd562405dad9b47ff53be5b4b2f6a972b6ecedc066ff2"
        ),
        upstream_release="frp-v2.1.0-m19",
    ),
    PublishedMemberRegistration(
        member_id="m27-telemetry-semantics",
        source_path="artifacts/m27/telemetry/m27-telemetry-semantics.json",
        schema_identifier="m27-telemetry-semantics-v2.9.0",
        measurement_contour=(
            PublishedMeasurementContour.M27_LONG_RUN_TELEMETRY_SEMANTICS
        ),
        observatory_modes=(
            ObservatoryMode.ARTIFACT_AUDITOR,
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
        ),
        byte_length=2789,
        raw_sha256=(
            "813ae5c66ceaddabc77734d44f1ebf971ca3bd7e11c1984e2e0c8f0204dfd1bc"
        ),
        compatibility_key=(
            "06c74930ea2d928fa07c0f2ca86ee886b67ce6846cdea855dba66acff0bb82b6"
        ),
        upstream_release="frp-v2.9.0-m27",
    ),
    PublishedMemberRegistration(
        member_id="m28-trace-observatory-upstream-contract",
        source_path=(
            "artifacts/m28/contracts/"
            "m28-trace-observatory-upstream-contract.json"
        ),
        schema_identifier=(
            "frp.m28.trace_observatory_upstream_contract.v3.0.0"
        ),
        measurement_contour=(
            PublishedMeasurementContour.M28_UPSTREAM_INTEGRATION_CONTRACT
        ),
        observatory_modes=(ObservatoryMode.ARTIFACT_AUDITOR,),
        byte_length=2735,
        raw_sha256=(
            "556cd2921014d78184dad625438e053632c2650164f95787f39a6fc871b4a3f0"
        ),
        compatibility_key=(
            "c5d60d4b37f669cc650b56be99bf61eb42ef837491e50cb9081cebc94cea14b0"
        ),
        upstream_release="frp-v3.0.0-m28",
    ),
    PublishedMemberRegistration(
        member_id="m28-hierarchical-scaling-contract",
        source_path=(
            "artifacts/m28/hierarchy/contracts/"
            "m28-hierarchical-scaling-contract.json"
        ),
        schema_identifier=(
            "frp.m28.hierarchical_scaling_contract.v3.0.0"
        ),
        measurement_contour=(
            PublishedMeasurementContour.M28_HIERARCHICAL_SCALING_QUALIFICATION
        ),
        observatory_modes=(ObservatoryMode.ARTIFACT_AUDITOR,),
        byte_length=3560,
        raw_sha256=(
            "13f85ac82b63d0191157bd2cfa04dd37358ef66d8e69bdb96bb1892abb77dbae"
        ),
        compatibility_key=(
            "737e7e29b051a0928575508e506d31b0b275933a490f161b16de0264d4d01746"
        ),
        upstream_release="frp-v3.0.0-m28",
    ),
)


def _build_index(
    registrations: tuple[PublishedMemberRegistration, ...],
) -> Mapping[str, PublishedMemberRegistration]:
    mutable: dict[str, PublishedMemberRegistration] = {}
    dispatch_keys: set[tuple[str, str, str]] = set()
    for registration in registrations:
        if registration.member_id in mutable:
            raise M30PublishedRegistryError(
                f"duplicate published member id: {registration.member_id!r}"
            )
        if registration.dispatch_key in dispatch_keys:
            raise M30PublishedRegistryError(
                f"duplicate published dispatch key: {registration.dispatch_key!r}"
            )
        mutable[registration.member_id] = registration
        dispatch_keys.add(registration.dispatch_key)
    return MappingProxyType(mutable)


_MEMBER_INDEX: Final = _build_index(M30_PUBLISHED_MEMBER_REGISTRATIONS)


def registration_for_member_id(
    member_id: str,
) -> PublishedMemberRegistration:
    """Resolve exactly one published member id without aliases."""

    if not isinstance(member_id, str):
        raise M30PublishedRegistryError("member_id must be a string")
    try:
        return _MEMBER_INDEX[member_id]
    except KeyError as exc:
        raise UnknownPublishedMemberError(member_id) from exc


def _require_member_field(
    member: PublishedDemoMember,
    registration: PublishedMemberRegistration,
    field: str,
) -> None:
    observed = getattr(member, field)
    expected = getattr(registration, field)
    if observed != expected:
        raise PublishedMemberIdentityError(
            registration.member_id,
            field,
            observed,
            expected,
        )


def resolve_published_member(
    member: PublishedDemoMember,
) -> PublishedMemberRegistration:
    """Bind one M2-verified member to its exact M3 registration."""

    if not isinstance(member, PublishedDemoMember):
        raise M30PublishedRegistryError(
            "member must be PublishedDemoMember"
        )
    registration = registration_for_member_id(member.member_id)
    for field in (
        "source_path",
        "schema_identifier",
        "observatory_modes",
        "raw_sha256",
        "byte_length",
    ):
        _require_member_field(member, registration, field)
    return registration


def routes_for_published_member(
    member: PublishedDemoMember,
) -> tuple[PublishedModeRoute, ...]:
    """Return only the existing modes declared for one verified member."""

    registration = resolve_published_member(member)
    return tuple(
        PublishedModeRoute(registration=registration, mode=mode)
        for mode in registration.observatory_modes
    )


def validate_published_registry(
    boundary: PublishedBoundaryValidation,
) -> PublishedRegistryValidation:
    """Validate exact registration and mode routing for one M2 result."""

    if not isinstance(boundary, PublishedBoundaryValidation):
        raise M30PublishedRegistryError(
            "boundary must be PublishedBoundaryValidation"
        )
    if boundary.archive_sha256 != FRP_M30_ARCHIVE_SHA256:
        raise M30PublishedRegistryError(
            "boundary archive digest is not the exact M30 digest"
        )
    if len(boundary.demo_members) != len(M30_PUBLISHED_MEMBER_REGISTRATIONS):
        raise M30PublishedRegistryError(
            "boundary demo member inventory mismatch"
        )
    registrations = tuple(
        resolve_published_member(member) for member in boundary.demo_members
    )
    if registrations != M30_PUBLISHED_MEMBER_REGISTRATIONS:
        raise M30PublishedRegistryError(
            "boundary demo member order mismatch"
        )
    routes = tuple(
        route
        for member in boundary.demo_members
        for route in routes_for_published_member(member)
    )
    auditor_count = sum(
        route.mode is ObservatoryMode.ARTIFACT_AUDITOR for route in routes
    )
    visualizer_count = sum(
        route.mode is ObservatoryMode.TERNARY_TRANSITION_VISUALIZER
        for route in routes
    )
    explorer_count = sum(
        route.mode is ObservatoryMode.TRACE_EXPLORER for route in routes
    )
    return PublishedRegistryValidation(
        archive_sha256=boundary.archive_sha256,
        registry_revision=M30_PUBLISHED_REGISTRY_REVISION,
        registrations=registrations,
        routes=routes,
        artifact_auditor_route_count=auditor_count,
        ternary_transition_visualizer_route_count=visualizer_count,
        trace_explorer_route_count=explorer_count,
    )


def validate_m30_published_registry(
    archive_path: str | Path,
) -> PublishedRegistryValidation:
    """Validate M2 bytes, then exact M3 mode routing, without extraction."""

    boundary = validate_m30_published_boundary(archive_path)
    return validate_published_registry(boundary)


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate exact FRP M30 published-member registration and "
            "routing into the three existing Observatory modes."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate_m30_published_registry(arguments.archive)
    print("FRP Observatory M30 published member registry: PASS")
    print(f"archive_sha256={result.archive_sha256}")
    print(f"registry_revision={result.registry_revision}")
    print(f"published_members={len(result.registrations)}")
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
    print("source_execution=forbidden")
    print("semantic_reimplementation=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
