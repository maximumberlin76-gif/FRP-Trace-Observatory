"""Exact read-only dispatch envelopes for verified FRP M30 members.

This module begins only with a complete M4 published-member intake batch. It
creates one immutable envelope for each of the seven M3-approved member-to-mode
routes. The envelopes retain the exact M4 source and parsed-object identities;
they do not reuse the legacy schema-only dispatch registry, execute upstream
content, normalize FRP semantics, invoke a mode consumer, or write upstream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from artifact_auditor.m30_archive_intake import FRP_M30_ARCHIVE_SHA256
from parsers.json_artifact import ParsedJsonArtifact
from parsers.m30_published_member_intake import (
    PublishedMemberIntake,
    PublishedMemberIntakeBatch,
    intake_m30_published_members,
)
from parsers.source_artifact import SourceArtifact
from schemas.m30_published_registry import (
    M30_PUBLISHED_REGISTRY_REVISION,
    PublishedModeRoute,
)
from schemas.registry import ObservatoryMode


__all__ = [
    "M30PublishedDispatchError",
    "PublishedDispatchBatch",
    "PublishedModeDispatch",
    "build_m30_published_dispatch_batch",
    "dispatch_m30_published_members",
]


_HEX64: Final = re.compile(r"^[0-9a-f]{64}$")


class M30PublishedDispatchError(ValueError):
    """Raised when an M30 dispatch-envelope invariant is violated."""


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _expected_dispatch_sha256(
    member: PublishedMemberIntake,
    route: PublishedModeRoute,
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "archive_sha256": member.archive_sha256,
                "compatibility_key": (
                    member.registration.compatibility_key
                ),
                "member_id": member.registration.member_id,
                "mode": route.mode.value,
                "raw_sha256": member.registration.raw_sha256,
                "registry_revision": member.registry_revision,
                "schema_identifier": (
                    member.registration.schema_identifier
                ),
                "source_path": member.registration.source_path,
            }
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class PublishedModeDispatch:
    """One exact M4 member reference and one approved M3 mode route."""

    member: PublishedMemberIntake
    route: PublishedModeRoute
    dispatch_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.member, PublishedMemberIntake):
            raise M30PublishedDispatchError(
                "member must be PublishedMemberIntake"
            )
        if self.member.archive_sha256 != FRP_M30_ARCHIVE_SHA256:
            raise M30PublishedDispatchError(
                "dispatch member archive digest mismatch"
            )
        if self.member.registry_revision != M30_PUBLISHED_REGISTRY_REVISION:
            raise M30PublishedDispatchError(
                "dispatch member registry revision mismatch"
            )
        if not self.member.source_artifact.verify_integrity():
            raise M30PublishedDispatchError(
                "dispatch source integrity verification failed"
            )
        if (
            self.member.source_artifact.raw_bytes
            != self.member.retained_member.raw_bytes
        ):
            raise M30PublishedDispatchError(
                "dispatch source differs from retained archive bytes"
            )
        if (
            self.member.parsed_artifact.source_artifact
            is not self.member.source_artifact
        ):
            raise M30PublishedDispatchError(
                "dispatch parsed object differs from the M4 source"
            )
        if not isinstance(self.route, PublishedModeRoute):
            raise M30PublishedDispatchError(
                "route must be PublishedModeRoute"
            )
        if self.route.registration is not self.member.registration:
            raise M30PublishedDispatchError(
                "route registration is not the M4 member registration"
            )
        if not any(route is self.route for route in self.member.routes):
            raise M30PublishedDispatchError(
                "route is not exact M4 member route evidence"
            )
        if self.route.mode not in self.member.eligible_modes:
            raise M30PublishedDispatchError(
                "route mode is not eligible for this M4 member"
            )
        if (
            not isinstance(self.dispatch_sha256, str)
            or not _HEX64.fullmatch(self.dispatch_sha256)
        ):
            raise M30PublishedDispatchError(
                "dispatch_sha256 must be lowercase hexadecimal SHA-256"
            )
        expected = _expected_dispatch_sha256(self.member, self.route)
        if self.dispatch_sha256 != expected:
            raise M30PublishedDispatchError(
                "dispatch_sha256 does not bind the exact member and route"
            )

    @classmethod
    def create(
        cls,
        member: PublishedMemberIntake,
        route: PublishedModeRoute,
    ) -> PublishedModeDispatch:
        """Create one envelope from exact existing M4 route evidence."""

        if not isinstance(member, PublishedMemberIntake):
            raise M30PublishedDispatchError(
                "member must be PublishedMemberIntake"
            )
        if not isinstance(route, PublishedModeRoute):
            raise M30PublishedDispatchError(
                "route must be PublishedModeRoute"
            )
        return cls(
            member=member,
            route=route,
            dispatch_sha256=_expected_dispatch_sha256(member, route),
        )

    @property
    def member_id(self) -> str:
        """Return the exact M3 member identifier."""

        return self.member.registration.member_id

    @property
    def mode(self) -> ObservatoryMode:
        """Return the exact existing Observatory mode."""

        return self.route.mode

    @property
    def source_artifact(self) -> SourceArtifact:
        """Return the unchanged M4 source-artifact object."""

        return self.member.source_artifact

    @property
    def parsed_artifact(self) -> ParsedJsonArtifact:
        """Return the unchanged strict M4 parsed-object view."""

        return self.member.parsed_artifact

    @property
    def raw_bytes(self) -> bytes:
        """Return the unchanged retained upstream bytes."""

        return self.member.raw_bytes

    @property
    def dispatch_key(self) -> tuple[str, ObservatoryMode, str]:
        """Return the exact member, mode, and raw-digest dispatch key."""

        return (
            self.member_id,
            self.mode,
            self.member.registration.raw_sha256,
        )


@dataclass(frozen=True, slots=True)
class PublishedDispatchBatch:
    """Complete ordered seven-envelope dispatch boundary for one M4 batch."""

    intake_batch: PublishedMemberIntakeBatch
    dispatches: tuple[PublishedModeDispatch, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.intake_batch, PublishedMemberIntakeBatch):
            raise M30PublishedDispatchError(
                "intake_batch must be PublishedMemberIntakeBatch"
            )
        if not isinstance(self.dispatches, tuple):
            raise M30PublishedDispatchError(
                "dispatches must be a tuple"
            )
        if any(
            not isinstance(dispatch, PublishedModeDispatch)
            for dispatch in self.dispatches
        ):
            raise M30PublishedDispatchError(
                "dispatches must contain PublishedModeDispatch values"
            )
        expected_pairs = tuple(
            (member, route)
            for member in self.intake_batch.members
            for route in member.routes
        )
        if len(self.dispatches) != len(expected_pairs):
            raise M30PublishedDispatchError(
                "dispatch inventory length mismatch"
            )
        for dispatch, (member, route) in zip(
            self.dispatches,
            expected_pairs,
            strict=True,
        ):
            if dispatch.member is not member or dispatch.route is not route:
                raise M30PublishedDispatchError(
                    "dispatch order or M4 evidence identity mismatch"
                )
        dispatch_keys = tuple(
            dispatch.dispatch_key for dispatch in self.dispatches
        )
        if len(set(dispatch_keys)) != len(dispatch_keys):
            raise M30PublishedDispatchError(
                "dispatch keys must be unique"
            )
        dispatch_digests = tuple(
            dispatch.dispatch_sha256 for dispatch in self.dispatches
        )
        if len(set(dispatch_digests)) != len(dispatch_digests):
            raise M30PublishedDispatchError(
                "dispatch digests must be unique"
            )
        expected_mode_counts = {
            ObservatoryMode.ARTIFACT_AUDITOR: (
                self.intake_batch.registry_validation
                .artifact_auditor_route_count
            ),
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER: (
                self.intake_batch.registry_validation
                .ternary_transition_visualizer_route_count
            ),
            ObservatoryMode.TRACE_EXPLORER: (
                self.intake_batch.registry_validation
                .trace_explorer_route_count
            ),
        }
        for mode, expected_count in expected_mode_counts.items():
            observed_count = sum(
                dispatch.mode is mode for dispatch in self.dispatches
            )
            if observed_count != expected_count:
                raise M30PublishedDispatchError(
                    f"{mode.value} dispatch count mismatch"
                )

    @property
    def archive_sha256(self) -> str:
        """Return the exact upstream archive identity."""

        return self.intake_batch.archive_validation.archive_sha256

    @property
    def registry_revision(self) -> str:
        """Return the exact M3 registry revision."""

        return self.intake_batch.registry_validation.registry_revision

    @property
    def total_dispatch_count(self) -> int:
        """Return the complete approved route count."""

        return len(self.dispatches)

    def dispatches_for_mode(
        self,
        mode: ObservatoryMode,
    ) -> tuple[PublishedModeDispatch, ...]:
        """Return source-order envelopes for one exact existing mode."""

        if not isinstance(mode, ObservatoryMode):
            raise M30PublishedDispatchError(
                "mode must be ObservatoryMode"
            )
        return tuple(
            dispatch for dispatch in self.dispatches
            if dispatch.mode is mode
        )

    def dispatches_for_member(
        self,
        member_id: str,
    ) -> tuple[PublishedModeDispatch, ...]:
        """Return registered-order envelopes for one exact member id."""

        if not isinstance(member_id, str):
            raise M30PublishedDispatchError(
                "member_id must be a string"
            )
        matches = tuple(
            dispatch for dispatch in self.dispatches
            if dispatch.member_id == member_id
        )
        if not matches:
            raise M30PublishedDispatchError(
                f"unknown published dispatch member: {member_id!r}"
            )
        return matches

    def dispatch_for(
        self,
        member_id: str,
        mode: ObservatoryMode,
    ) -> PublishedModeDispatch:
        """Resolve one exact eligible member-to-mode envelope."""

        if not isinstance(mode, ObservatoryMode):
            raise M30PublishedDispatchError(
                "mode must be ObservatoryMode"
            )
        member_dispatches = self.dispatches_for_member(member_id)
        matches = tuple(
            dispatch for dispatch in member_dispatches
            if dispatch.mode is mode
        )
        if len(matches) != 1:
            raise M30PublishedDispatchError(
                f"member {member_id!r} is not eligible for {mode.value!r}"
            )
        return matches[0]


def build_m30_published_dispatch_batch(
    intake_batch: PublishedMemberIntakeBatch,
) -> PublishedDispatchBatch:
    """Create all exact envelopes without invoking any mode consumer."""

    if not isinstance(intake_batch, PublishedMemberIntakeBatch):
        raise M30PublishedDispatchError(
            "intake_batch must be PublishedMemberIntakeBatch"
        )
    dispatches = tuple(
        PublishedModeDispatch.create(member, route)
        for member in intake_batch.members
        for route in member.routes
    )
    return PublishedDispatchBatch(
        intake_batch=intake_batch,
        dispatches=dispatches,
    )


def dispatch_m30_published_members(
    archive_path: str | Path,
) -> PublishedDispatchBatch:
    """Validate M1 through M4, then create the seven M5 envelopes."""

    intake_batch = intake_m30_published_members(archive_path)
    return build_m30_published_dispatch_batch(intake_batch)


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create seven exact read-only M30 member-to-mode dispatch "
            "envelopes without invoking consumers or writing upstream."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    arguments = parser.parse_args()
    result = dispatch_m30_published_members(arguments.archive)
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
    print("FRP Observatory M30 published dispatch boundary: PASS")
    print(f"archive_sha256={result.archive_sha256}")
    print(f"registry_revision={result.registry_revision}")
    print(f"published_members={len(result.intake_batch.members)}")
    print(f"dispatch_envelopes={result.total_dispatch_count}")
    print(
        "artifact_auditor_dispatches="
        f"{auditor_count}"
    )
    print(
        "ternary_transition_visualizer_dispatches="
        f"{visualizer_count}"
    )
    print(
        "trace_explorer_dispatches="
        f"{explorer_count}"
    )
    print("legacy_schema_only_dispatch_reuse=forbidden")
    print("mode_consumer_invocation=deferred")
    print("source_execution=forbidden")
    print("semantic_normalization=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
