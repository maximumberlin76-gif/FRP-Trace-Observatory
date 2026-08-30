"""Read-only transition visualization for the exact FRP M31 publication.

This module starts only after the complete M31 published Artifact Auditor
batch has passed.  It uses the dedicated ``ternary_transition_visualizer``
route for the published M31 evidence and the already qualified M31 Trace
Explorer projection for its two unchanged execution contours.

The resulting immutable dataset exposes 800 source-linked transition frames,
the published phase-interference computation chain, active computational zero,
the balanced ternary domain -1/0/1, both temporal scheduler modes 1/7 and 7/1,
and four strictly separated thermal-evidence panels.  The historical release
benchmark is never merged with the current comparative baseline, hardware
sensitivity, or thermal-profile contours.

No upstream source is executed.  No metric is normalized, no thermal contour
is merged, no FRP semantic is reimplemented, no upstream byte is mutated, and
no result is written back to FRP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid5

from artifact_auditor.audit_report import SourceLocation, ValidationStatus
from artifact_auditor.m31_published_auditor import (
    M31PublishedAuditBatch,
    M31PublishedAuditReport,
    audit_m31_published_documents,
)
from artifact_auditor.m31_published_boundary_intake import (
    M31_PUBLISHED_REGISTRY_REVISION,
    M31PublishedDocumentRole,
)
from parsers.m31_published_dispatch import M31PublishedDocumentDispatch
from schemas.m31_published_registry import M31PublishedMeasurementContour
from schemas.registry import ObservatoryMode
from trace_explorer.m31_published_trace_explorer import (
    M31PublishedTraceCell,
    M31PublishedTraceContour,
    M31PublishedTraceDataset,
    M31PublishedTraceRecord,
    build_m31_published_trace_dataset,
)


__all__ = [
    "M31PublishedCoreDeclaration",
    "M31PublishedThermalContour",
    "M31PublishedTransitionFrame",
    "M31PublishedTransitionVisualizerDataset",
    "M31PublishedTransitionVisualizerError",
    "build_m31_published_transition_visualizer",
    "visualize_m31_published_documents",
]


_EVIDENCE_SCHEMA: Final = (
    "frp.m31.phase_interference_active_zero_thermal_evidence.v1"
)
_EVIDENCE_KIND: Final = "phase_interference_active_zero_thermal_evidence"
_EVIDENCE_PATH: Final = (
    "artifacts/m31/evidence/"
    "m31-phase-interference-active-zero-thermal-evidence.json"
)
_EVIDENCE_RAW_SHA256: Final = (
    "bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42"
)
_TRACE_DATASET_SHA256: Final = (
    "ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff"
)
_TRACE_DATASET_ID: Final = "0f0f0f7e-0409-5e7b-8c76-2f72bb954321"
_VISUALIZER_DISPATCH_SHA256: Final = (
    "ff4597411a781c814ab8ef009d30739857411d2a31ff34839d3060b478a697e8"
)
_CORE_SHA256: Final = (
    "05c98cfb19ec7ef85f0fab47bf80e2c2330e4595255411d366269a511b5c0b9a"
)
_CURRENT_THERMAL_PARENT_SHA256: Final = (
    "6b066bee41b791f708b166991dc29d408876c0084b13a2bd6e7eb9827e2ceb50"
)

_HEX64: Final = re.compile(r"^[0-9a-f]{64}$")
_TERNARY_DOMAIN: Final = frozenset({-1, 0, 1})
_VALID_SCHEDULER_MODES: Final = frozenset({"free", "1/7", "7/1"})
_VALID_SCHEDULER_STATES: Final = frozenset(
    {"free", "balance", "commit", "excite", "neutralize"}
)
_CORE_NAMESPACE: Final = UUID("00be4cf5-2e30-5a0a-b7ec-1e70477467b9")
_FRAME_NAMESPACE: Final = UUID("4a07a78f-ad35-5a11-814f-7feb7a29b992")
_THERMAL_NAMESPACE: Final = UUID("f4a47a25-37d5-5856-8958-891dcf8a6f85")
_DATASET_NAMESPACE: Final = UUID("5eb52bc5-ece0-58ee-ac84-1b6b44ca1d3f")

_COMPUTATION_CHAIN: Final = (
    "retained phase and frequency state",
    "relative-phase interaction",
    "phase organization and dispersion",
    "resonance selection",
    "multiscale coherence evaluation",
    "dynamic stability evaluation",
    "phase-derived ternary target",
    "distributed active-neutral commit",
    "retained coherent ternary state",
)
_OPPOSITE_TRANSITION_ROUTES: Final = ((-1, 0, 1), (1, 0, -1))
_TEMPORAL_SCHEDULER_MODES: Final = ("1/7", "7/1")
_ACTIVE_ZERO_ROLES: Final = (
    "conflict_neutralization",
    "temporal_separation",
    "balancing",
    "damping",
    "transition_buffering",
    "switching_load_distribution",
    "retained_transition_continuity",
    "pending_route_completion_preparation",
    "stabilization",
)
_TRANSITION_CLASSIFICATIONS: Final = (
    "active_zero_to_polarity",
    "direct_opposite",
    "polarity_to_active_zero",
    "retained_same",
)
_EXPECTED_TRANSITION_COUNTS: Final = (
    ("active_zero_to_polarity", 12),
    ("direct_opposite", 0),
    ("polarity_to_active_zero", 5),
    ("retained_same", 783),
)
_ROUTE_LEGS: Final = (
    "non_route_transition",
    "first_leg_to_active_zero",
    "pending_route_completion",
)
_EXPECTED_ROUTE_COUNTS: Final = (
    ("non_route_transition", 790),
    ("first_leg_to_active_zero", 5),
    ("pending_route_completion", 5),
)
_EVIDENCE_BOUNDARIES: Final = (
    ("historical_and_current_contours_separate", True),
    ("historical_heat_peak_is_not_current_rc_temperature_proxy", True),
    ("normalized_activity_cost_is_not_physical_energy", True),
    ("operation_count_is_not_thermal_load", True),
    ("physical_measurement_required_for_silicon_temperature_claim", True),
    ("scope_limited_relations_are_not_universal_winner_claims", True),
    ("thermal_proxy_is_not_physical_temperature", True),
)
_PUBLICATION_CONTRACT: Final = (
    ("direction", "upstream_published_bytes_to_downstream"),
    ("downstream_metric_normalization", "forbidden"),
    ("downstream_repository", "FRP-Trace-Observatory"),
    ("downstream_role", "read_only_validation_and_visualization"),
    ("downstream_semantic_reimplementation", "forbidden"),
    ("downstream_source_mutation", "forbidden"),
    ("downstream_writeback", "forbidden"),
    ("m29_boundary_confirmed", True),
    ("published_contours_must_remain_separate", True),
    ("upstream_repository", "FRP"),
)


@dataclass(frozen=True, slots=True)
class _ThermalContourSpec:
    name: str
    group: str
    source_json_path: str
    payload_sha256: str
    measurement_class: str
    physical_temperature_measurement: bool


_THERMAL_SPECS: Final = (
    _ThermalContourSpec(
        name="historical_release_benchmark",
        group="historical",
        source_json_path="$.historical_thermal_experiment",
        payload_sha256=(
            "8ae48a85c971d6fe8d136fd08b45ac7d801c6146c82eab2ac785c4e8318cb140"
        ),
        measurement_class="release_specific_model_thermal_load",
        physical_temperature_measurement=False,
    ),
    _ThermalContourSpec(
        name="current_comparative_baseline",
        group="current",
        source_json_path="$.current_comparative_thermal_contours.baseline",
        payload_sha256=(
            "c7a66b2a99608b51508cc249459917d23ffebc4258501afd8567ca99afff6add"
        ),
        measurement_class="shared_model_comparative_benchmark",
        physical_temperature_measurement=False,
    ),
    _ThermalContourSpec(
        name="current_hardware_sensitivity",
        group="current",
        source_json_path=(
            "$.current_comparative_thermal_contours.hardware_sensitivity"
        ),
        payload_sha256=(
            "9b8a709f65e156b160facfb977a8b7362b928344dc45c840ef4b9eae637313a0"
        ),
        measurement_class="shared_model_comparative_benchmark",
        physical_temperature_measurement=False,
    ),
    _ThermalContourSpec(
        name="current_thermal_profile",
        group="current",
        source_json_path=(
            "$.current_comparative_thermal_contours.thermal_profile"
        ),
        payload_sha256=(
            "1c92e0fbfb54f19803c70970b0dbf135c4bb37121a34407d64639ad6a3582eee"
        ),
        measurement_class="shared_model_comparative_benchmark",
        physical_temperature_measurement=False,
    ),
)
_THERMAL_SPEC_BY_NAME: Final = {spec.name: spec for spec in _THERMAL_SPECS}


class M31PublishedTransitionVisualizerError(ValueError):
    """Raised when the exact M31 visualizer boundary is violated."""


def _validate_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be a string"
        )
    if not value or value != value.strip() or "\x00" in value:
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be nonempty without outer whitespace or NUL"
        )
    return value


def _validate_nonnegative_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be an integer"
        )
    if value < 0:
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be nonnegative"
        )
    return value


def _validate_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be lowercase hexadecimal SHA-256"
        )
    return value


def _validate_uuid(value: object, field: str) -> str:
    _validate_text(value, field)
    try:
        UUID(value)
    except (ValueError, AttributeError) as exc:
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be a valid UUID"
        ) from exc
    return value


def _validate_ternary(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be an integer"
        )
    if value not in _TERNARY_DOMAIN:
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be one of -1, 0, 1"
        )
    return value


def _plain(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    return value


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        _plain(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_json_text(value: object) -> str:
    return _canonical_json_bytes(value).decode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be a mapping"
        )
    return value


def _require_sequence(value: object, field: str) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise M31PublishedTransitionVisualizerError(
            f"{field} must be an array"
        )
    return tuple(value)


def _transition_classification(before: int, after: int) -> str:
    _validate_ternary(before, "retained_state_before")
    _validate_ternary(after, "retained_state_after")
    if before == after:
        return "retained_same"
    if before == 0 and after in (-1, 1):
        return "active_zero_to_polarity"
    if before in (-1, 1) and after == 0:
        return "polarity_to_active_zero"
    raise M31PublishedTransitionVisualizerError(
        "direct opposite retained-state transitions are forbidden"
    )


def _route_leg(cell: M31PublishedTraceCell) -> str:
    if cell.neutral_routed:
        return "first_leg_to_active_zero"
    if (
        cell.pending_route_before in (-1, 1)
        and cell.retained_state_before == 0
        and cell.retained_state_after == cell.pending_route_before
        and cell.pending_route_after == 0
    ):
        return "pending_route_completion"
    return "non_route_transition"


@dataclass(frozen=True, slots=True)
class M31PublishedCoreDeclaration:
    """Exact published FRP computation and ternary-core declaration."""

    core_declaration_id: str
    processor: str
    balanced_ternary_notation: str
    semantic_values: tuple[int, int, int]
    active_neutral_state: int
    zero_role: str
    classical_bit_addition_primary_mechanism: bool
    primary_computational_organization: str
    computation_chain: tuple[str, ...]
    ternary_layer_role: str
    service_scheduler_mode: str
    temporal_scheduler_modes: tuple[str, str]
    opposite_transition_routes: tuple[tuple[int, int, int], ...]
    source_location: SourceLocation
    source_record_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.core_declaration_id, "core_declaration_id")
        for field, value in (
            ("processor", self.processor),
            ("balanced_ternary_notation", self.balanced_ternary_notation),
            ("zero_role", self.zero_role),
            (
                "primary_computational_organization",
                self.primary_computational_organization,
            ),
            ("ternary_layer_role", self.ternary_layer_role),
            ("service_scheduler_mode", self.service_scheduler_mode),
        ):
            _validate_text(value, field)
        if (
            self.processor != "Fractal Resonance Processor"
            or self.balanced_ternary_notation != "-1/0/1"
            or self.semantic_values != (-1, 0, 1)
            or self.active_neutral_state != 0
            or self.zero_role != "active_computational_state"
            or self.classical_bit_addition_primary_mechanism is not False
            or self.primary_computational_organization
            != "retained_relative_phase_interference_and_resonant_selection"
            or self.computation_chain != _COMPUTATION_CHAIN
            or self.ternary_layer_role
            != "discrete_state_target_transition_and_retained_result_boundary"
            or self.service_scheduler_mode != "free"
            or self.temporal_scheduler_modes != _TEMPORAL_SCHEDULER_MODES
            or self.opposite_transition_routes != _OPPOSITE_TRANSITION_ROUTES
        ):
            raise M31PublishedTransitionVisualizerError(
                "published FRP computation or ternary-core declaration changed"
            )
        if not isinstance(self.source_location, SourceLocation):
            raise M31PublishedTransitionVisualizerError(
                "core source_location must be SourceLocation"
            )
        if self.source_location != SourceLocation(
            json_path="$.core",
            package_member=_EVIDENCE_PATH,
        ):
            raise M31PublishedTransitionVisualizerError(
                "core source coordinate changed"
            )
        _validate_sha256(self.source_record_sha256, "source_record_sha256")
        if (
            self.source_record_sha256 != _CORE_SHA256
            or self.source_record_sha256
            != _sha256(_canonical_json_bytes(self.source_payload()))
        ):
            raise M31PublishedTransitionVisualizerError(
                "core source digest changed"
            )
        if self.core_declaration_id != str(
            uuid5(_CORE_NAMESPACE, self.source_record_sha256)
        ):
            raise M31PublishedTransitionVisualizerError(
                "core_declaration_id does not bind exact core source"
            )

    def source_payload(self) -> dict[str, object]:
        """Reconstruct the exact published ``core`` mapping."""

        return {
            "active_neutral_state": self.active_neutral_state,
            "balanced_ternary_notation": self.balanced_ternary_notation,
            "classical_bit_addition_primary_mechanism": (
                self.classical_bit_addition_primary_mechanism
            ),
            "computation_chain": list(self.computation_chain),
            "opposite_transition_routes": [
                list(route) for route in self.opposite_transition_routes
            ],
            "primary_computational_organization": (
                self.primary_computational_organization
            ),
            "processor": self.processor,
            "semantic_values": list(self.semantic_values),
            "service_scheduler_mode": self.service_scheduler_mode,
            "temporal_scheduler_modes": list(self.temporal_scheduler_modes),
            "ternary_layer_role": self.ternary_layer_role,
            "zero_role": self.zero_role,
        }


def _build_core_declaration(
    value: object,
) -> M31PublishedCoreDeclaration:
    source = _require_mapping(value, "core")
    digest = _sha256(_canonical_json_bytes(source))
    semantic_values = tuple(
        _validate_ternary(item, f"semantic_values[{index}]")
        for index, item in enumerate(
            _require_sequence(source.get("semantic_values"), "semantic_values")
        )
    )
    if len(semantic_values) != 3:
        raise M31PublishedTransitionVisualizerError(
            "semantic_values must contain exactly three values"
        )
    routes = tuple(
        tuple(
            _validate_ternary(item, f"opposite route {route_index}")
            for item in _require_sequence(route, "opposite transition route")
        )
        for route_index, route in enumerate(
            _require_sequence(
                source.get("opposite_transition_routes"),
                "opposite_transition_routes",
            )
        )
    )
    if any(len(route) != 3 for route in routes):
        raise M31PublishedTransitionVisualizerError(
            "opposite transition routes must contain three states"
        )
    return M31PublishedCoreDeclaration(
        core_declaration_id=str(uuid5(_CORE_NAMESPACE, digest)),
        processor=_validate_text(source.get("processor"), "processor"),
        balanced_ternary_notation=_validate_text(
            source.get("balanced_ternary_notation"),
            "balanced_ternary_notation",
        ),
        semantic_values=semantic_values,
        active_neutral_state=_validate_ternary(
            source.get("active_neutral_state"),
            "active_neutral_state",
        ),
        zero_role=_validate_text(source.get("zero_role"), "zero_role"),
        classical_bit_addition_primary_mechanism=source.get(
            "classical_bit_addition_primary_mechanism"
        ),
        primary_computational_organization=_validate_text(
            source.get("primary_computational_organization"),
            "primary_computational_organization",
        ),
        computation_chain=tuple(
            _validate_text(item, f"computation_chain[{index}]")
            for index, item in enumerate(
                _require_sequence(
                    source.get("computation_chain"),
                    "computation_chain",
                )
            )
        ),
        ternary_layer_role=_validate_text(
            source.get("ternary_layer_role"),
            "ternary_layer_role",
        ),
        service_scheduler_mode=_validate_text(
            source.get("service_scheduler_mode"),
            "service_scheduler_mode",
        ),
        temporal_scheduler_modes=tuple(
            _validate_text(item, f"temporal_scheduler_modes[{index}]")
            for index, item in enumerate(
                _require_sequence(
                    source.get("temporal_scheduler_modes"),
                    "temporal_scheduler_modes",
                )
            )
        ),
        opposite_transition_routes=routes,
        source_location=SourceLocation(
            json_path="$.core",
            package_member=_EVIDENCE_PATH,
        ),
        source_record_sha256=digest,
    )


def _frame_payload(
    *,
    visualizer_dispatch_sha256: str,
    trace_dataset_id: str,
    trace_dataset_sha256: str,
    trace_contour_id: str,
    trace_contour_sha256: str,
    contour_index: int,
    measurement_contour: str,
    source_path: str,
    source_trace_sha256: str,
    trace_record_id: str,
    source_record_sha256: str,
    sequence: int,
    execution_epoch: int,
    scheduler_mode: str,
    scheduler_state: str,
    cell_id: int,
    phase_derived_target: int,
    retained_state_before: int,
    retained_state_after: int,
    pending_route_before: int,
    pending_route_after: int,
    accepted: bool,
    accepted_change: bool,
    neutral_routed: bool,
    transition_classification: str,
    route_leg: str,
    source_location: SourceLocation,
) -> dict[str, object]:
    return {
        "accepted": accepted,
        "accepted_change": accepted_change,
        "cell_id": cell_id,
        "contour_index": contour_index,
        "execution_epoch": execution_epoch,
        "measurement_contour": measurement_contour,
        "neutral_routed": neutral_routed,
        "pending_route_after": pending_route_after,
        "pending_route_before": pending_route_before,
        "phase_derived_target": phase_derived_target,
        "retained_state_after": retained_state_after,
        "retained_state_before": retained_state_before,
        "route_leg": route_leg,
        "scheduler_mode": scheduler_mode,
        "scheduler_state": scheduler_state,
        "sequence": sequence,
        "source_location": {
            "array_index": source_location.array_index,
            "json_path": source_location.json_path,
            "package_member": source_location.package_member,
            "source_record_ordinal": source_location.source_record_ordinal,
        },
        "source_path": source_path,
        "source_record_sha256": source_record_sha256,
        "source_trace_sha256": source_trace_sha256,
        "trace_contour_id": trace_contour_id,
        "trace_contour_sha256": trace_contour_sha256,
        "trace_dataset_id": trace_dataset_id,
        "trace_dataset_sha256": trace_dataset_sha256,
        "trace_record_id": trace_record_id,
        "transition_classification": transition_classification,
        "visualizer_dispatch_sha256": visualizer_dispatch_sha256,
    }


@dataclass(frozen=True, slots=True)
class M31PublishedTransitionFrame:
    """One exact source-linked M31 transition cell for presentation."""

    transition_frame_id: str
    visualizer_dispatch_sha256: str
    trace_dataset_id: str
    trace_dataset_sha256: str
    trace_contour_id: str
    trace_contour_sha256: str
    contour_index: int
    measurement_contour: str
    source_path: str
    source_trace_sha256: str
    trace_record_id: str
    source_record_sha256: str
    sequence: int
    execution_epoch: int
    scheduler_mode: str
    scheduler_state: str
    cell_id: int
    phase_derived_target: int
    retained_state_before: int
    retained_state_after: int
    pending_route_before: int
    pending_route_after: int
    accepted: bool
    accepted_change: bool
    neutral_routed: bool
    transition_classification: str
    route_leg: str
    source_location: SourceLocation
    frame_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.transition_frame_id, "transition_frame_id")
        _validate_sha256(
            self.visualizer_dispatch_sha256,
            "visualizer_dispatch_sha256",
        )
        if self.visualizer_dispatch_sha256 != _VISUALIZER_DISPATCH_SHA256:
            raise M31PublishedTransitionVisualizerError(
                "transition frame lost exact M31 visualizer route"
            )
        _validate_uuid(self.trace_dataset_id, "trace_dataset_id")
        _validate_sha256(self.trace_dataset_sha256, "trace_dataset_sha256")
        if (
            self.trace_dataset_id != _TRACE_DATASET_ID
            or self.trace_dataset_sha256 != _TRACE_DATASET_SHA256
        ):
            raise M31PublishedTransitionVisualizerError(
                "transition frame lost exact M31 Trace Explorer authority"
            )
        _validate_uuid(self.trace_contour_id, "trace_contour_id")
        _validate_sha256(self.trace_contour_sha256, "trace_contour_sha256")
        _validate_nonnegative_integer(self.contour_index, "contour_index")
        if self.contour_index not in (0, 1):
            raise M31PublishedTransitionVisualizerError(
                "transition frame contour_index is out of range"
            )
        if self.measurement_contour != (
            M31PublishedMeasurementContour
            .PHASE_INTERFERENCE_ACTIVE_ZERO_THERMAL_EVIDENCE.value
        ):
            raise M31PublishedTransitionVisualizerError(
                "transition frame measurement contour changed"
            )
        _validate_text(self.source_path, "source_path")
        _validate_sha256(self.source_trace_sha256, "source_trace_sha256")
        _validate_uuid(self.trace_record_id, "trace_record_id")
        _validate_sha256(self.source_record_sha256, "source_record_sha256")
        _validate_nonnegative_integer(self.sequence, "sequence")
        _validate_nonnegative_integer(self.execution_epoch, "execution_epoch")
        if self.scheduler_mode not in _VALID_SCHEDULER_MODES:
            raise M31PublishedTransitionVisualizerError(
                "unknown transition frame scheduler mode"
            )
        if self.scheduler_state not in _VALID_SCHEDULER_STATES:
            raise M31PublishedTransitionVisualizerError(
                "unknown transition frame scheduler state"
            )
        _validate_nonnegative_integer(self.cell_id, "cell_id")
        if self.cell_id >= 8:
            raise M31PublishedTransitionVisualizerError(
                "transition frame cell_id is out of range"
            )
        for field, value in (
            ("phase_derived_target", self.phase_derived_target),
            ("retained_state_before", self.retained_state_before),
            ("retained_state_after", self.retained_state_after),
            ("pending_route_before", self.pending_route_before),
            ("pending_route_after", self.pending_route_after),
        ):
            _validate_ternary(value, field)
        for field, value in (
            ("accepted", self.accepted),
            ("accepted_change", self.accepted_change),
            ("neutral_routed", self.neutral_routed),
        ):
            if not isinstance(value, bool):
                raise M31PublishedTransitionVisualizerError(
                    f"{field} must be boolean"
                )
        expected_classification = _transition_classification(
            self.retained_state_before,
            self.retained_state_after,
        )
        if self.transition_classification != expected_classification:
            raise M31PublishedTransitionVisualizerError(
                "frame transition classification differs from source states"
            )
        if self.route_leg not in _ROUTE_LEGS:
            raise M31PublishedTransitionVisualizerError(
                "unknown transition frame route leg"
            )
        if self.route_leg == "first_leg_to_active_zero" and not (
            self.neutral_routed
            and self.retained_state_after == 0
            and self.pending_route_after in (-1, 1)
        ):
            raise M31PublishedTransitionVisualizerError(
                "first route leg must retain active zero and pending polarity"
            )
        if self.route_leg == "pending_route_completion" and not (
            self.pending_route_before in (-1, 1)
            and self.retained_state_before == 0
            and self.retained_state_after == self.pending_route_before
            and self.pending_route_after == 0
        ):
            raise M31PublishedTransitionVisualizerError(
                "pending route completion differs from source relation"
            )
        if not isinstance(self.source_location, SourceLocation):
            raise M31PublishedTransitionVisualizerError(
                "frame source_location must be SourceLocation"
            )
        expected_location = SourceLocation(
            json_path=(
                f"$.records[{self.sequence}]."
                f"retained_state_after[{self.cell_id}]"
            ),
            array_index=self.cell_id,
            package_member=self.source_path,
            source_record_ordinal=self.sequence + 1,
        )
        if self.source_location != expected_location:
            raise M31PublishedTransitionVisualizerError(
                "transition frame source coordinate changed"
            )
        _validate_sha256(self.frame_sha256, "frame_sha256")
        expected_digest = _sha256(
            _canonical_json_bytes(self.deterministic_payload())
        )
        if self.frame_sha256 != expected_digest:
            raise M31PublishedTransitionVisualizerError(
                "frame_sha256 does not bind complete frame projection"
            )
        if self.transition_frame_id != str(
            uuid5(_FRAME_NAMESPACE, self.frame_sha256)
        ):
            raise M31PublishedTransitionVisualizerError(
                "transition_frame_id does not bind frame_sha256"
            )

    def deterministic_payload(self) -> dict[str, object]:
        """Return the complete canonical transition-frame payload."""

        return _frame_payload(
            visualizer_dispatch_sha256=self.visualizer_dispatch_sha256,
            trace_dataset_id=self.trace_dataset_id,
            trace_dataset_sha256=self.trace_dataset_sha256,
            trace_contour_id=self.trace_contour_id,
            trace_contour_sha256=self.trace_contour_sha256,
            contour_index=self.contour_index,
            measurement_contour=self.measurement_contour,
            source_path=self.source_path,
            source_trace_sha256=self.source_trace_sha256,
            trace_record_id=self.trace_record_id,
            source_record_sha256=self.source_record_sha256,
            sequence=self.sequence,
            execution_epoch=self.execution_epoch,
            scheduler_mode=self.scheduler_mode,
            scheduler_state=self.scheduler_state,
            cell_id=self.cell_id,
            phase_derived_target=self.phase_derived_target,
            retained_state_before=self.retained_state_before,
            retained_state_after=self.retained_state_after,
            pending_route_before=self.pending_route_before,
            pending_route_after=self.pending_route_after,
            accepted=self.accepted,
            accepted_change=self.accepted_change,
            neutral_routed=self.neutral_routed,
            transition_classification=self.transition_classification,
            route_leg=self.route_leg,
            source_location=self.source_location,
        )


def _build_transition_frame(
    dispatch: M31PublishedDocumentDispatch,
    trace_dataset: M31PublishedTraceDataset,
    contour: M31PublishedTraceContour,
    record: M31PublishedTraceRecord,
    cell: M31PublishedTraceCell,
) -> M31PublishedTransitionFrame:
    classification = _transition_classification(
        cell.retained_state_before,
        cell.retained_state_after,
    )
    route_leg = _route_leg(cell)
    location = SourceLocation(
        json_path=(
            f"$.records[{record.sequence}]."
            f"retained_state_after[{cell.cell_id}]"
        ),
        array_index=cell.cell_id,
        package_member=contour.source_path,
        source_record_ordinal=record.sequence + 1,
    )
    payload = _frame_payload(
        visualizer_dispatch_sha256=dispatch.dispatch_sha256,
        trace_dataset_id=trace_dataset.trace_dataset_id,
        trace_dataset_sha256=trace_dataset.dataset_sha256,
        trace_contour_id=contour.trace_contour_id,
        trace_contour_sha256=contour.contour_sha256,
        contour_index=contour.contour_index,
        measurement_contour=trace_dataset.measurement_contour.value,
        source_path=contour.source_path,
        source_trace_sha256=contour.raw_sha256,
        trace_record_id=record.trace_record_id,
        source_record_sha256=record.source_record_sha256,
        sequence=record.sequence,
        execution_epoch=record.execution_epoch,
        scheduler_mode=record.scheduler.mode,
        scheduler_state=record.scheduler.state,
        cell_id=cell.cell_id,
        phase_derived_target=cell.phase_derived_target,
        retained_state_before=cell.retained_state_before,
        retained_state_after=cell.retained_state_after,
        pending_route_before=cell.pending_route_before,
        pending_route_after=cell.pending_route_after,
        accepted=cell.accepted,
        accepted_change=cell.accepted_change,
        neutral_routed=cell.neutral_routed,
        transition_classification=classification,
        route_leg=route_leg,
        source_location=location,
    )
    digest = _sha256(_canonical_json_bytes(payload))
    return M31PublishedTransitionFrame(
        transition_frame_id=str(uuid5(_FRAME_NAMESPACE, digest)),
        visualizer_dispatch_sha256=dispatch.dispatch_sha256,
        trace_dataset_id=trace_dataset.trace_dataset_id,
        trace_dataset_sha256=trace_dataset.dataset_sha256,
        trace_contour_id=contour.trace_contour_id,
        trace_contour_sha256=contour.contour_sha256,
        contour_index=contour.contour_index,
        measurement_contour=trace_dataset.measurement_contour.value,
        source_path=contour.source_path,
        source_trace_sha256=contour.raw_sha256,
        trace_record_id=record.trace_record_id,
        source_record_sha256=record.source_record_sha256,
        sequence=record.sequence,
        execution_epoch=record.execution_epoch,
        scheduler_mode=record.scheduler.mode,
        scheduler_state=record.scheduler.state,
        cell_id=cell.cell_id,
        phase_derived_target=cell.phase_derived_target,
        retained_state_before=cell.retained_state_before,
        retained_state_after=cell.retained_state_after,
        pending_route_before=cell.pending_route_before,
        pending_route_after=cell.pending_route_after,
        accepted=cell.accepted,
        accepted_change=cell.accepted_change,
        neutral_routed=cell.neutral_routed,
        transition_classification=classification,
        route_leg=route_leg,
        source_location=location,
        frame_sha256=digest,
    )


def _validate_thermal_payload(name: str, payload: Mapping[str, Any]) -> None:
    if name == "historical_release_benchmark":
        if (
            payload.get("evidence_class") != "reproduced_release_benchmark"
            or payload.get("release") != "FRP v0.9.3"
            or payload.get("measurement_class")
            != "release_specific_model_thermal_load"
            or payload.get("metric_unit") != "historical_model_heat_peak"
            or payload.get("physical_temperature_measurement") is not False
            or payload.get("source_executable")
            != "frp_prototype_v0_9_3_mobile.py"
            or payload.get("source_report") != "TEST_REPORT_v0_9_3.md"
            or _plain(payload.get("winner_assertions")) != []
        ):
            raise M31PublishedTransitionVisualizerError(
                "historical thermal contour identity changed"
            )
        focused = _require_mapping(
            payload.get("focused_binary_ternary_comparison"),
            "historical focused comparison",
        )
        if (
            focused.get("binary_architecture_id")
            != "binary_style_forced_switch"
            or focused.get("active_neutral_ternary_architecture_id")
            != "distributed_neutral_ternary"
            or focused.get("binary_heat_peak") != "0.051000"
            or focused.get("active_neutral_ternary_heat_peak") != "0.003250"
            or focused.get("heat_peak_ratio_binary_over_active_neutral_ternary")
            != "15.6923076923"
            or focused.get("heat_peak_relative_reduction_percent") != "93.63"
        ):
            raise M31PublishedTransitionVisualizerError(
                "historical focused thermal comparison changed"
            )
        return
    if name == "current_comparative_baseline":
        expected = (
            (
                "source_path",
                "benchmarks/architecture_comparison/results/"
                "reference_comparison_seed_76.json",
            ),
            (
                "raw_sha256",
                "5ba86d26dc62db36ae14ac2c1167e71dd5c06c00bbd5aa3dc21c6d11b38db064",
            ),
            ("schema", "frp.benchmark.architecture_comparison.v1"),
            ("qualification_status", "PASS"),
            ("frp_scheduler", "7/1"),
        )
        if any(payload.get(key) != value for key, value in expected) or (
            _plain(payload.get("winner_assertions")) != []
        ):
            raise M31PublishedTransitionVisualizerError(
                "current comparative baseline identity changed"
            )
        matrix = _require_sequence(
            payload.get("comparison_matrix"),
            "comparison_matrix",
        )
        if len(matrix) != 4:
            raise M31PublishedTransitionVisualizerError(
                "current comparison matrix inventory changed"
            )
        return
    if name == "current_hardware_sensitivity":
        expected = (
            (
                "source_path",
                "benchmarks/architecture_comparison/results/"
                "reference_comparison_seed_76_hardware_sensitivity_v1.json",
            ),
            (
                "raw_sha256",
                "e4785aa4c234cc7dd8e5377e5e0b41a8ec401f962400975e0cef7a88cc494680",
            ),
            (
                "schema",
                "frp.benchmark.hardware_sensitivity_comparison.v1",
            ),
            ("qualification_status", "PASS"),
        )
        if any(payload.get(key) != value for key, value in expected) or (
            _plain(payload.get("winner_assertions")) != []
        ):
            raise M31PublishedTransitionVisualizerError(
                "current hardware-sensitivity identity changed"
            )
        if _plain(payload.get("scenario_order")) != [
            "lower_bound",
            "nominal",
            "upper_bound",
        ]:
            raise M31PublishedTransitionVisualizerError(
                "hardware-sensitivity scenario order changed"
            )
        return
    if name == "current_thermal_profile":
        expected = (
            (
                "source_path",
                "benchmarks/architecture_comparison/profiles/"
                "thermal_proxy_profile_v1.json",
            ),
            (
                "raw_sha256",
                "aeafebc3e71d1311a3445bd1528cbe7322546f79d6a5099dfed3a9590fc4a25b",
            ),
            ("profile_name", "common_rc_thermal_proxy_v1"),
            ("temperature_unit", "normalized_temperature_proxy"),
        )
        if any(payload.get(key) != value for key, value in expected):
            raise M31PublishedTransitionVisualizerError(
                "current thermal-profile identity changed"
            )
        return
    raise M31PublishedTransitionVisualizerError(
        f"unknown thermal contour: {name!r}"
    )


@dataclass(frozen=True, slots=True)
class M31PublishedThermalContour:
    """One immutable, non-interchangeable M31 thermal-evidence panel."""

    thermal_contour_id: str
    visualizer_dispatch_sha256: str
    contour_name: str
    contour_group: str
    source_json_path: str
    measurement_class: str
    physical_temperature_measurement: bool
    payload_json: str
    payload_sha256: str
    source_location: SourceLocation

    def __post_init__(self) -> None:
        _validate_uuid(self.thermal_contour_id, "thermal_contour_id")
        _validate_sha256(
            self.visualizer_dispatch_sha256,
            "visualizer_dispatch_sha256",
        )
        if self.visualizer_dispatch_sha256 != _VISUALIZER_DISPATCH_SHA256:
            raise M31PublishedTransitionVisualizerError(
                "thermal contour lost exact M31 visualizer route"
            )
        spec = _THERMAL_SPEC_BY_NAME.get(self.contour_name)
        if spec is None:
            raise M31PublishedTransitionVisualizerError(
                "unknown M31 thermal contour"
            )
        if (
            self.contour_group != spec.group
            or self.source_json_path != spec.source_json_path
            or self.measurement_class != spec.measurement_class
            or self.physical_temperature_measurement
            is not spec.physical_temperature_measurement
        ):
            raise M31PublishedTransitionVisualizerError(
                "thermal contour classification or source coordinate changed"
            )
        _validate_text(self.payload_json, "payload_json")
        try:
            decoded = json.loads(self.payload_json)
        except json.JSONDecodeError as exc:
            raise M31PublishedTransitionVisualizerError(
                "thermal contour payload_json is invalid"
            ) from exc
        payload = _require_mapping(decoded, "thermal contour payload")
        if _canonical_json_text(payload) != self.payload_json:
            raise M31PublishedTransitionVisualizerError(
                "thermal contour payload_json is not canonical"
            )
        _validate_sha256(self.payload_sha256, "payload_sha256")
        if (
            self.payload_sha256 != spec.payload_sha256
            or self.payload_sha256
            != _sha256(self.payload_json.encode("utf-8"))
        ):
            raise M31PublishedTransitionVisualizerError(
                "thermal contour payload digest changed"
            )
        _validate_thermal_payload(self.contour_name, payload)
        if not isinstance(self.source_location, SourceLocation):
            raise M31PublishedTransitionVisualizerError(
                "thermal source_location must be SourceLocation"
            )
        if self.source_location != SourceLocation(
            json_path=self.source_json_path,
            package_member=_EVIDENCE_PATH,
        ):
            raise M31PublishedTransitionVisualizerError(
                "thermal contour source location changed"
            )
        expected_id = str(
            uuid5(
                _THERMAL_NAMESPACE,
                (
                    f"{self.visualizer_dispatch_sha256}:"
                    f"{self.contour_name}:{self.payload_sha256}"
                ),
            )
        )
        if self.thermal_contour_id != expected_id:
            raise M31PublishedTransitionVisualizerError(
                "thermal_contour_id does not bind exact panel"
            )

    def payload(self) -> dict[str, Any]:
        """Return a detached exact JSON value for presentation."""

        value = json.loads(self.payload_json)
        return dict(_require_mapping(value, "thermal contour payload"))


def _build_thermal_contour(
    dispatch: M31PublishedDocumentDispatch,
    spec: _ThermalContourSpec,
    value: object,
) -> M31PublishedThermalContour:
    payload = _require_mapping(value, spec.name)
    payload_json = _canonical_json_text(payload)
    digest = _sha256(payload_json.encode("utf-8"))
    contour_id = str(
        uuid5(
            _THERMAL_NAMESPACE,
            f"{dispatch.dispatch_sha256}:{spec.name}:{digest}",
        )
    )
    return M31PublishedThermalContour(
        thermal_contour_id=contour_id,
        visualizer_dispatch_sha256=dispatch.dispatch_sha256,
        contour_name=spec.name,
        contour_group=spec.group,
        source_json_path=spec.source_json_path,
        measurement_class=spec.measurement_class,
        physical_temperature_measurement=(
            spec.physical_temperature_measurement
        ),
        payload_json=payload_json,
        payload_sha256=digest,
        source_location=SourceLocation(
            json_path=spec.source_json_path,
            package_member=_EVIDENCE_PATH,
        ),
    )


def _dataset_sha256(
    audit_batch: M31PublishedAuditBatch,
    audit_report: M31PublishedAuditReport,
    visualizer_dispatch: M31PublishedDocumentDispatch,
    trace_dataset: M31PublishedTraceDataset,
    core_declaration: M31PublishedCoreDeclaration,
    transition_frames: tuple[M31PublishedTransitionFrame, ...],
    thermal_contours: tuple[M31PublishedThermalContour, ...],
    active_zero_roles: tuple[str, ...],
    evidence_boundaries: tuple[tuple[str, bool], ...],
    publication_contract: tuple[tuple[str, object], ...],
) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "active_zero_roles": list(active_zero_roles),
                "audit_batch_sha256": audit_batch.batch_sha256,
                "audit_report_sha256": audit_report.report_sha256,
                "core_declaration_id": core_declaration.core_declaration_id,
                "core_source_sha256": core_declaration.source_record_sha256,
                "current_thermal_parent_sha256": (
                    _CURRENT_THERMAL_PARENT_SHA256
                ),
                "evidence_boundaries": dict(evidence_boundaries),
                "evidence_raw_sha256": _EVIDENCE_RAW_SHA256,
                "publication_contract": dict(publication_contract),
                "registry_revision": M31_PUBLISHED_REGISTRY_REVISION,
                "thermal_contours": [
                    {
                        "contour_name": contour.contour_name,
                        "payload_sha256": contour.payload_sha256,
                        "thermal_contour_id": contour.thermal_contour_id,
                    }
                    for contour in thermal_contours
                ],
                "trace_dataset_id": trace_dataset.trace_dataset_id,
                "trace_dataset_sha256": trace_dataset.dataset_sha256,
                "transition_frames": [
                    {
                        "frame_sha256": frame.frame_sha256,
                        "transition_frame_id": frame.transition_frame_id,
                    }
                    for frame in transition_frames
                ],
                "visualizer_dispatch_sha256": (
                    visualizer_dispatch.dispatch_sha256
                ),
            }
        )
    )


@dataclass(frozen=True, slots=True)
class M31PublishedTransitionVisualizerDataset:
    """Complete deterministic transition-visualizer view of M31 evidence."""

    visualizer_dataset_id: str
    audit_batch: M31PublishedAuditBatch
    audit_report: M31PublishedAuditReport
    visualizer_dispatch: M31PublishedDocumentDispatch
    trace_dataset: M31PublishedTraceDataset
    core_declaration: M31PublishedCoreDeclaration
    transition_frames: tuple[M31PublishedTransitionFrame, ...]
    thermal_contours: tuple[M31PublishedThermalContour, ...]
    active_zero_roles: tuple[str, ...]
    evidence_boundaries: tuple[tuple[str, bool], ...]
    publication_contract: tuple[tuple[str, object], ...]
    dataset_sha256: str

    def __post_init__(self) -> None:
        _validate_uuid(self.visualizer_dataset_id, "visualizer_dataset_id")
        if not isinstance(self.audit_batch, M31PublishedAuditBatch):
            raise M31PublishedTransitionVisualizerError(
                "audit_batch must be M31PublishedAuditBatch"
            )
        if (
            self.audit_batch.overall_status
            is not ValidationStatus.RECOGNIZED_VALID
            or self.audit_batch.failed_check_count != 0
        ):
            raise M31PublishedTransitionVisualizerError(
                "M31 audit batch must pass before visualization"
            )
        if not isinstance(self.audit_report, M31PublishedAuditReport):
            raise M31PublishedTransitionVisualizerError(
                "audit_report must be M31PublishedAuditReport"
            )
        expected_report = self.audit_batch.report_for_role(
            M31PublishedDocumentRole.EVIDENCE
        )
        if self.audit_report is not expected_report:
            raise M31PublishedTransitionVisualizerError(
                "audit_report is not exact M31 evidence audit result"
            )
        if (
            self.audit_report.overall_status
            is not ValidationStatus.RECOGNIZED_VALID
            or self.audit_report.failed_count != 0
        ):
            raise M31PublishedTransitionVisualizerError(
                "M31 evidence audit report must have no failures"
            )
        if not isinstance(
            self.visualizer_dispatch,
            M31PublishedDocumentDispatch,
        ):
            raise M31PublishedTransitionVisualizerError(
                "visualizer_dispatch must be M31PublishedDocumentDispatch"
            )
        expected_dispatch = self.audit_batch.dispatch_batch.dispatch_for(
            M31PublishedDocumentRole.EVIDENCE,
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
        )
        if self.visualizer_dispatch is not expected_dispatch:
            raise M31PublishedTransitionVisualizerError(
                "visualizer_dispatch is not the exact M31 transition route"
            )
        if (
            self.visualizer_dispatch.mode
            is not ObservatoryMode.TERNARY_TRANSITION_VISUALIZER
            or self.visualizer_dispatch.dispatch_sha256
            != _VISUALIZER_DISPATCH_SHA256
        ):
            raise M31PublishedTransitionVisualizerError(
                "M31 visualizer dispatch identity changed"
            )
        if (
            self.visualizer_dispatch.document
            is not self.audit_report.dispatch.document
            or self.visualizer_dispatch.source_artifact
            is not self.audit_report.dispatch.source_artifact
        ):
            raise M31PublishedTransitionVisualizerError(
                "visualizer and auditor evidence sources differ"
            )
        route_contour = (
            self.visualizer_dispatch.route.registration.measurement_contour
        )
        if route_contour is not (
            M31PublishedMeasurementContour
            .PHASE_INTERFERENCE_ACTIVE_ZERO_THERMAL_EVIDENCE
        ):
            raise M31PublishedTransitionVisualizerError(
                "visualizer measurement contour changed"
            )
        if (
            self.visualizer_dispatch.document.identity.source_path
            != _EVIDENCE_PATH
            or self.visualizer_dispatch.source_artifact.content_sha256
            != _EVIDENCE_RAW_SHA256
            or not self.visualizer_dispatch.source_artifact.verify_integrity()
        ):
            raise M31PublishedTransitionVisualizerError(
                "M31 evidence source identity changed"
            )
        if not isinstance(self.trace_dataset, M31PublishedTraceDataset):
            raise M31PublishedTransitionVisualizerError(
                "trace_dataset must be M31PublishedTraceDataset"
            )
        if self.trace_dataset.audit_batch is not self.audit_batch:
            raise M31PublishedTransitionVisualizerError(
                "Trace Explorer and visualizer must share exact audit batch"
            )
        if (
            self.trace_dataset.trace_dataset_id != _TRACE_DATASET_ID
            or self.trace_dataset.dataset_sha256 != _TRACE_DATASET_SHA256
        ):
            raise M31PublishedTransitionVisualizerError(
                "M31 Trace Explorer dataset identity changed"
            )
        if (
            self.trace_dataset.dispatch.document
            is not self.visualizer_dispatch.document
            or self.trace_dataset.dispatch.source_artifact
            is not self.visualizer_dispatch.source_artifact
        ):
            raise M31PublishedTransitionVisualizerError(
                "Trace Explorer and visualizer do not share exact evidence"
            )
        root = _require_mapping(
            self.visualizer_dispatch.parsed_artifact.root,
            "M31 evidence root",
        )
        if (
            root.get("schema") != _EVIDENCE_SCHEMA
            or root.get("kind") != _EVIDENCE_KIND
            or root.get("milestone") != "M31"
            or root.get("version") != "1.0.0"
            or root.get("status") != "PASS"
        ):
            raise M31PublishedTransitionVisualizerError(
                "unsupported M31 evidence identity"
            )
        if not isinstance(
            self.core_declaration,
            M31PublishedCoreDeclaration,
        ):
            raise M31PublishedTransitionVisualizerError(
                "core_declaration must be M31PublishedCoreDeclaration"
            )
        if self.core_declaration.source_payload() != _plain(root.get("core")):
            raise M31PublishedTransitionVisualizerError(
                "core declaration differs from exact evidence source"
            )
        if (
            not isinstance(self.transition_frames, tuple)
            or len(self.transition_frames) != 800
            or any(
                not isinstance(frame, M31PublishedTransitionFrame)
                for frame in self.transition_frames
            )
        ):
            raise M31PublishedTransitionVisualizerError(
                "transition_frames must contain exactly 800 frames"
            )
        expected_cells = tuple(
            (contour, record, cell)
            for contour in self.trace_dataset.contours
            for record in contour.records
            for cell in record.cells
        )
        for frame, (contour, record, cell) in zip(
            self.transition_frames,
            expected_cells,
            strict=True,
        ):
            observed = (
                frame.trace_contour_id,
                frame.trace_contour_sha256,
                frame.contour_index,
                frame.source_path,
                frame.source_trace_sha256,
                frame.trace_record_id,
                frame.source_record_sha256,
                frame.sequence,
                frame.execution_epoch,
                frame.scheduler_mode,
                frame.scheduler_state,
                frame.cell_id,
                frame.phase_derived_target,
                frame.retained_state_before,
                frame.retained_state_after,
                frame.pending_route_before,
                frame.pending_route_after,
                frame.accepted,
                frame.accepted_change,
                frame.neutral_routed,
                frame.transition_classification,
                frame.route_leg,
            )
            expected = (
                contour.trace_contour_id,
                contour.contour_sha256,
                contour.contour_index,
                contour.source_path,
                contour.raw_sha256,
                record.trace_record_id,
                record.source_record_sha256,
                record.sequence,
                record.execution_epoch,
                record.scheduler.mode,
                record.scheduler.state,
                cell.cell_id,
                cell.phase_derived_target,
                cell.retained_state_before,
                cell.retained_state_after,
                cell.pending_route_before,
                cell.pending_route_after,
                cell.accepted,
                cell.accepted_change,
                cell.neutral_routed,
                _transition_classification(
                    cell.retained_state_before,
                    cell.retained_state_after,
                ),
                _route_leg(cell),
            )
            if observed != expected:
                raise M31PublishedTransitionVisualizerError(
                    "transition frame differs from exact trace source cell"
                )
        if self.transition_classification_counts != (
            _EXPECTED_TRANSITION_COUNTS
        ):
            raise M31PublishedTransitionVisualizerError(
                "transition classification inventory changed"
            )
        if self.route_leg_counts != _EXPECTED_ROUTE_COUNTS:
            raise M31PublishedTransitionVisualizerError(
                "active-zero route-leg inventory changed"
            )
        if self.active_zero_after_observation_count != 702:
            raise M31PublishedTransitionVisualizerError(
                "active-zero after-observation inventory changed"
            )
        if any(
            (frame.retained_state_before, frame.retained_state_after)
            in ((-1, 1), (1, -1))
            for frame in self.transition_frames
        ):
            raise M31PublishedTransitionVisualizerError(
                "visualizer contains a direct opposite transition"
            )
        if (
            not isinstance(self.thermal_contours, tuple)
            or tuple(
                contour.contour_name for contour in self.thermal_contours
            )
            != tuple(spec.name for spec in _THERMAL_SPECS)
            or any(
                not isinstance(contour, M31PublishedThermalContour)
                for contour in self.thermal_contours
            )
        ):
            raise M31PublishedTransitionVisualizerError(
                "thermal contour inventory or source order changed"
            )
        historical = _require_mapping(
            root.get("historical_thermal_experiment"),
            "historical_thermal_experiment",
        )
        current = _require_mapping(
            root.get("current_comparative_thermal_contours"),
            "current_comparative_thermal_contours",
        )
        if (
            _sha256(_canonical_json_bytes(current))
            != _CURRENT_THERMAL_PARENT_SHA256
            or current.get("measurement_class")
            != "shared_model_comparative_benchmark"
            or current.get("physical_temperature_measurement") is not False
            or current.get("historical_heat_peak_interchangeable") is not False
        ):
            raise M31PublishedTransitionVisualizerError(
                "current comparative thermal parent boundary changed"
            )
        exact_thermal_payloads = (
            historical,
            _require_mapping(current.get("baseline"), "current baseline"),
            _require_mapping(
                current.get("hardware_sensitivity"),
                "current hardware sensitivity",
            ),
            _require_mapping(
                current.get("thermal_profile"),
                "current thermal profile",
            ),
        )
        if any(
            contour.payload_json != _canonical_json_text(payload)
            for contour, payload in zip(
                self.thermal_contours,
                exact_thermal_payloads,
                strict=True,
            )
        ):
            raise M31PublishedTransitionVisualizerError(
                "thermal panel differs from exact M31 evidence"
            )
        if self.physical_temperature_measurement_count != 0:
            raise M31PublishedTransitionVisualizerError(
                "visualizer invented a physical temperature measurement"
            )
        if self.active_zero_roles != _ACTIVE_ZERO_ROLES or (
            self.active_zero_roles != self.trace_dataset.active_zero_roles
        ):
            raise M31PublishedTransitionVisualizerError(
                "active-zero role declaration changed"
            )
        boundaries = _require_mapping(
            root.get("evidence_boundaries"),
            "evidence_boundaries",
        )
        contract = _require_mapping(
            root.get("observatory_publication_contract"),
            "observatory_publication_contract",
        )
        if (
            self.evidence_boundaries != _EVIDENCE_BOUNDARIES
            or tuple(boundaries.items()) != self.evidence_boundaries
        ):
            raise M31PublishedTransitionVisualizerError(
                "published evidence boundaries changed"
            )
        if (
            self.publication_contract != _PUBLICATION_CONTRACT
            or tuple(contract.items()) != self.publication_contract
        ):
            raise M31PublishedTransitionVisualizerError(
                "read-only Observatory publication contract changed"
            )
        _validate_sha256(self.dataset_sha256, "dataset_sha256")
        expected_digest = _dataset_sha256(
            self.audit_batch,
            self.audit_report,
            self.visualizer_dispatch,
            self.trace_dataset,
            self.core_declaration,
            self.transition_frames,
            self.thermal_contours,
            self.active_zero_roles,
            self.evidence_boundaries,
            self.publication_contract,
        )
        if self.dataset_sha256 != expected_digest:
            raise M31PublishedTransitionVisualizerError(
                "dataset_sha256 does not bind complete M31 visualization"
            )
        if self.visualizer_dataset_id != str(
            uuid5(_DATASET_NAMESPACE, self.dataset_sha256)
        ):
            raise M31PublishedTransitionVisualizerError(
                "visualizer_dataset_id does not bind dataset_sha256"
            )

    @property
    def registry_revision(self) -> str:
        return self.audit_batch.dispatch_batch.registry_revision

    @property
    def transition_frame_count(self) -> int:
        return len(self.transition_frames)

    @property
    def active_zero_after_observation_count(self) -> int:
        return sum(
            frame.retained_state_after == 0
            for frame in self.transition_frames
        )

    @property
    def transition_classification_counts(
        self,
    ) -> tuple[tuple[str, int], ...]:
        counts = Counter(
            frame.transition_classification
            for frame in self.transition_frames
        )
        return tuple(
            (name, counts.get(name, 0))
            for name in _TRANSITION_CLASSIFICATIONS
        )

    @property
    def route_leg_counts(self) -> tuple[tuple[str, int], ...]:
        counts = Counter(frame.route_leg for frame in self.transition_frames)
        return tuple((name, counts.get(name, 0)) for name in _ROUTE_LEGS)

    @property
    def thermal_contour_count(self) -> int:
        return len(self.thermal_contours)

    @property
    def physical_temperature_measurement_count(self) -> int:
        return sum(
            contour.physical_temperature_measurement
            for contour in self.thermal_contours
        )

    def thermal_contour(self, name: str) -> M31PublishedThermalContour:
        """Resolve one exact thermal panel without aliases."""

        _validate_text(name, "thermal contour name")
        matches = tuple(
            contour
            for contour in self.thermal_contours
            if contour.contour_name == name
        )
        if len(matches) != 1:
            raise M31PublishedTransitionVisualizerError(
                f"unknown thermal contour: {name!r}"
            )
        return matches[0]


def build_m31_published_transition_visualizer(
    audit_batch: M31PublishedAuditBatch,
) -> M31PublishedTransitionVisualizerDataset:
    """Build the exact read-only M31 transition-visualizer dataset."""

    if not isinstance(audit_batch, M31PublishedAuditBatch):
        raise M31PublishedTransitionVisualizerError(
            "audit_batch must be M31PublishedAuditBatch"
        )
    if (
        audit_batch.overall_status is not ValidationStatus.RECOGNIZED_VALID
        or audit_batch.failed_check_count != 0
    ):
        raise M31PublishedTransitionVisualizerError(
            "M31 audit batch must pass before visualization"
        )
    audit_report = audit_batch.report_for_role(
        M31PublishedDocumentRole.EVIDENCE
    )
    dispatch = audit_batch.dispatch_batch.dispatch_for(
        M31PublishedDocumentRole.EVIDENCE,
        ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    )
    trace_dataset = build_m31_published_trace_dataset(audit_batch)
    if (
        dispatch.document is not audit_report.dispatch.document
        or dispatch.source_artifact is not audit_report.dispatch.source_artifact
        or trace_dataset.dispatch.document is not dispatch.document
    ):
        raise M31PublishedTransitionVisualizerError(
            "auditor, Trace Explorer, and visualizer evidence differ"
        )
    root = _require_mapping(dispatch.parsed_artifact.root, "M31 evidence root")
    core = _build_core_declaration(root.get("core"))
    frames = tuple(
        _build_transition_frame(
            dispatch,
            trace_dataset,
            contour,
            record,
            cell,
        )
        for contour in trace_dataset.contours
        for record in contour.records
        for cell in record.cells
    )
    historical = _require_mapping(
        root.get("historical_thermal_experiment"),
        "historical_thermal_experiment",
    )
    current = _require_mapping(
        root.get("current_comparative_thermal_contours"),
        "current_comparative_thermal_contours",
    )
    thermal_values = (
        historical,
        current.get("baseline"),
        current.get("hardware_sensitivity"),
        current.get("thermal_profile"),
    )
    thermal_contours = tuple(
        _build_thermal_contour(dispatch, spec, value)
        for spec, value in zip(
            _THERMAL_SPECS,
            thermal_values,
            strict=True,
        )
    )
    boundaries_source = _require_mapping(
        root.get("evidence_boundaries"),
        "evidence_boundaries",
    )
    evidence_boundaries = tuple(
        (name, boundaries_source.get(name))
        for name, _ in _EVIDENCE_BOUNDARIES
    )
    contract_source = _require_mapping(
        root.get("observatory_publication_contract"),
        "observatory_publication_contract",
    )
    publication_contract = tuple(
        (name, contract_source.get(name))
        for name, _ in _PUBLICATION_CONTRACT
    )
    digest = _dataset_sha256(
        audit_batch,
        audit_report,
        dispatch,
        trace_dataset,
        core,
        frames,
        thermal_contours,
        trace_dataset.active_zero_roles,
        evidence_boundaries,
        publication_contract,
    )
    return M31PublishedTransitionVisualizerDataset(
        visualizer_dataset_id=str(uuid5(_DATASET_NAMESPACE, digest)),
        audit_batch=audit_batch,
        audit_report=audit_report,
        visualizer_dispatch=dispatch,
        trace_dataset=trace_dataset,
        core_declaration=core,
        transition_frames=frames,
        thermal_contours=thermal_contours,
        active_zero_roles=trace_dataset.active_zero_roles,
        evidence_boundaries=evidence_boundaries,
        publication_contract=publication_contract,
        dataset_sha256=digest,
    )


def visualize_m31_published_documents(
    upstream_root: str | Path,
    *,
    loaded_at: datetime | None = None,
) -> M31PublishedTransitionVisualizerDataset:
    """Validate M31 intake through audit and build the visualizer dataset."""

    return build_m31_published_transition_visualizer(
        audit_m31_published_documents(
            upstream_root,
            loaded_at=loaded_at,
        )
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one deterministic read-only Ternary Transition Visualizer "
            "dataset from the exact audited FRP M31 publication."
        )
    )
    parser.add_argument("--upstream-root", required=True, type=Path)
    arguments = parser.parse_args()
    result = visualize_m31_published_documents(arguments.upstream_root)
    historical = result.thermal_contour(
        "historical_release_benchmark"
    ).payload()
    focused = _require_mapping(
        historical.get("focused_binary_ternary_comparison"),
        "historical focused comparison",
    )
    print("FRP Observatory M31 published Transition Visualizer: PASS")
    print(f"registry_revision={result.registry_revision}")
    print(f"evidence_raw_sha256={_EVIDENCE_RAW_SHA256}")
    print(
        "visualizer_dispatch_sha256="
        f"{result.visualizer_dispatch.dispatch_sha256}"
    )
    print(f"trace_dataset_sha256={result.trace_dataset.dataset_sha256}")
    print(f"trace_contours={result.trace_dataset.trace_contour_count}")
    print(f"transition_frames={result.transition_frame_count}")
    print(
        "active_zero_after_observations="
        f"{result.active_zero_after_observation_count}"
    )
    print(f"active_zero_roles={len(result.active_zero_roles)}")
    print(
        "primary_computational_organization="
        f"{result.core_declaration.primary_computational_organization}"
    )
    print("classical_bit_addition_primary_mechanism=false")
    print("balanced_ternary_notation=-1/0/1")
    print("active_neutral_state=0")
    print(
        "temporal_scheduler_modes="
        + ",".join(result.core_declaration.temporal_scheduler_modes)
    )
    print(
        "transition_classification_counts="
        + json.dumps(
            dict(result.transition_classification_counts),
            sort_keys=True,
        )
    )
    print(
        "route_leg_counts="
        + json.dumps(dict(result.route_leg_counts), sort_keys=True)
    )
    print(f"thermal_contours={result.thermal_contour_count}")
    print(
        "thermal_contour_names="
        + ",".join(
            contour.contour_name for contour in result.thermal_contours
        )
    )
    print("historical_and_current_contours_separate=true")
    print(
        "physical_temperature_measurements="
        f"{result.physical_temperature_measurement_count}"
    )
    print(
        "historical_binary_heat_peak="
        f"{focused['binary_heat_peak']}"
    )
    print(
        "historical_active_neutral_ternary_heat_peak="
        f"{focused['active_neutral_ternary_heat_peak']}"
    )
    print(
        "historical_heat_peak_ratio="
        f"{focused['heat_peak_ratio_binary_over_active_neutral_ternary']}"
    )
    print(
        "historical_heat_peak_relative_reduction_percent="
        f"{focused['heat_peak_relative_reduction_percent']}"
    )
    for contour in result.thermal_contours:
        physical = str(
            contour.physical_temperature_measurement
        ).lower()
        print(
            f"thermal[{contour.contour_name}]="
            f"{contour.payload_sha256}|group={contour.contour_group}|"
            f"physical_temperature={physical}"
        )
    print(f"dataset_sha256={result.dataset_sha256}")
    print(f"visualizer_dataset_id={result.visualizer_dataset_id}")
    print("source_execution=forbidden")
    print("metric_normalization=forbidden")
    print("thermal_contour_merging=forbidden")
    print("semantic_reimplementation=forbidden")
    print("source_mutation=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
