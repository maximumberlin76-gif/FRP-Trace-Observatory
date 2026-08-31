"""Tests for the exact read-only FRP M31 Transition Visualizer."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from collections import Counter
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifact_auditor.audit_report import SourceLocation, ValidationStatus
from artifact_auditor.m31_published_auditor import (
    audit_m31_published_documents,
)
from artifact_auditor.m31_published_boundary_intake import (
    M31PublishedDocumentRole,
)
from schemas.registry import ObservatoryMode
from transition_visualizer.m31_published_transition_visualizer import (
    M31PublishedTransitionVisualizerError,
    build_m31_published_transition_visualizer,
    visualize_m31_published_documents,
)


_UPSTREAM_ENVIRONMENT_VARIABLE = "FRP_M31_UPSTREAM_ROOT"
_EXACT_LOADED_AT = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
_LATER_LOADED_AT = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)

_ACTIVE_ZERO_ROLES = (
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
_COMPUTATION_CHAIN = (
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
_TRANSITION_COUNTS = (
    ("active_zero_to_polarity", 12),
    ("direct_opposite", 0),
    ("polarity_to_active_zero", 5),
    ("retained_same", 783),
)
_ROUTE_COUNTS = (
    ("non_route_transition", 790),
    ("first_leg_to_active_zero", 5),
    ("pending_route_completion", 5),
)
_THERMAL_IDENTITIES = (
    (
        "historical_release_benchmark",
        "historical",
        "$.historical_thermal_experiment",
        "release_specific_model_thermal_load",
        "1e671e21-1961-56ee-863c-c1d14ebab354",
        "8ae48a85c971d6fe8d136fd08b45ac7d801c6146c82eab2ac785c4e8318cb140",
    ),
    (
        "current_comparative_baseline",
        "current",
        "$.current_comparative_thermal_contours.baseline",
        "shared_model_comparative_benchmark",
        "73399143-b18d-59b7-8853-4a4a1e2131c6",
        "c7a66b2a99608b51508cc249459917d23ffebc4258501afd8567ca99afff6add",
    ),
    (
        "current_hardware_sensitivity",
        "current",
        "$.current_comparative_thermal_contours.hardware_sensitivity",
        "shared_model_comparative_benchmark",
        "20feabf0-61fa-5eb2-8a1c-f760e9dca562",
        "9b8a709f65e156b160facfb977a8b7362b928344dc45c840ef4b9eae637313a0",
    ),
    (
        "current_thermal_profile",
        "current",
        "$.current_comparative_thermal_contours.thermal_profile",
        "shared_model_comparative_benchmark",
        "3f91f028-e0e7-5c22-9b6d-35abdc0644c5",
        "1c92e0fbfb54f19803c70970b0dbf135c4bb37121a34407d64639ad6a3582eee",
    ),
)
_FIRST_ROUTE_LEGS = (
    (0, 1, 0, 1, 0, -1),
    (0, 3, 0, -1, 0, 1),
    (0, 24, 0, 1, 0, -1),
    (0, 81, 0, 1, 0, -1),
    (1, 1, 0, 1, 0, -1),
)
_ROUTE_COMPLETIONS = (
    (0, 2, 0, 0, -1, -1, 0),
    (0, 4, 0, 0, 1, 1, 0),
    (0, 31, 0, 0, -1, -1, 0),
    (0, 88, 0, 0, -1, -1, 0),
    (1, 2, 0, 0, -1, -1, 0),
)
_EVIDENCE_BOUNDARIES = (
    ("historical_and_current_contours_separate", True),
    ("historical_heat_peak_is_not_current_rc_temperature_proxy", True),
    ("normalized_activity_cost_is_not_physical_energy", True),
    ("operation_count_is_not_thermal_load", True),
    ("physical_measurement_required_for_silicon_temperature_claim", True),
    ("scope_limited_relations_are_not_universal_winner_claims", True),
    ("thermal_proxy_is_not_physical_temperature", True),
)
_PUBLICATION_CONTRACT = (
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


def _plain_json_value(value: Any) -> Any:
    """Return a mutable JSON-shaped value for lossless comparison."""

    if isinstance(value, Mapping):
        return {
            str(key): _plain_json_value(member)
            for key, member in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_plain_json_value(member) for member in value]
    return value


class M31PublishedTransitionVisualizerGuardTests(unittest.TestCase):
    """Exercise the dedicated M20 public type boundary."""

    def test_builder_requires_exact_m31_audit_batch_type(self) -> None:
        for value in (None, "batch", ()):  # type: ignore[arg-type]
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M31PublishedTransitionVisualizerError,
                    "audit_batch must be M31PublishedAuditBatch",
                ):
                    build_m31_published_transition_visualizer(value)


@unittest.skipUnless(
    os.environ.get(_UPSTREAM_ENVIRONMENT_VARIABLE),
    f"{_UPSTREAM_ENVIRONMENT_VARIABLE} is not configured",
)
class ExactM31PublishedTransitionVisualizerIntegrationTests(
    unittest.TestCase
):
    """Exercise the exact M31 transition and thermal presentation boundary."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.upstream_root = Path(
            os.environ[_UPSTREAM_ENVIRONMENT_VARIABLE]
        ).resolve(strict=True)
        cls.audit_batch = audit_m31_published_documents(
            cls.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        cls.dataset = build_m31_published_transition_visualizer(
            cls.audit_batch
        )

    def test_dataset_is_green_and_retains_exact_m31_identity(self) -> None:
        self.assertIs(
            self.dataset.audit_batch.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertEqual(self.dataset.audit_batch.failed_check_count, 0)
        self.assertEqual(
            self.dataset.registry_revision,
            "m31-published-boundary-v1",
        )
        self.assertEqual(
            self.dataset.visualizer_dataset_id,
            "63a1feb9-1835-579e-ab00-eec4569e8ff3",
        )
        self.assertEqual(
            self.dataset.dataset_sha256,
            "0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304",
        )

    def test_auditor_visualizer_and_trace_share_exact_evidence(self) -> None:
        report = self.audit_batch.report_for_role(
            M31PublishedDocumentRole.EVIDENCE
        )
        dispatch = self.audit_batch.dispatch_batch.dispatch_for(
            M31PublishedDocumentRole.EVIDENCE,
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
        )
        self.assertIs(self.dataset.audit_report, report)
        self.assertIs(self.dataset.visualizer_dispatch, dispatch)
        self.assertIs(
            self.dataset.visualizer_dispatch.document,
            self.dataset.audit_report.dispatch.document,
        )
        self.assertIs(
            self.dataset.visualizer_dispatch.source_artifact,
            self.dataset.trace_dataset.dispatch.source_artifact,
        )

    def test_registry_contains_one_exact_transition_visualizer_route(self) -> None:
        routes = self.audit_batch.dispatch_batch.dispatches_for_mode(
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER
        )
        self.assertEqual(len(routes), 1)
        self.assertIs(routes[0], self.dataset.visualizer_dispatch)
        self.assertEqual(
            routes[0].dispatch_sha256,
            "ff4597411a781c814ab8ef009d30739857411d2a31ff34839d3060b478a697e8",
        )

    def test_trace_explorer_authority_is_exact_and_shared(self) -> None:
        self.assertIs(
            self.dataset.trace_dataset.audit_batch,
            self.dataset.audit_batch,
        )
        self.assertEqual(
            self.dataset.trace_dataset.trace_dataset_id,
            "0f0f0f7e-0409-5e7b-8c76-2f72bb954321",
        )
        self.assertEqual(
            self.dataset.trace_dataset.dataset_sha256,
            "ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff",
        )

    def test_core_declaration_preserves_phase_interference_computation(self) -> None:
        core = self.dataset.core_declaration
        self.assertEqual(core.processor, "Fractal Resonance Processor")
        self.assertEqual(core.balanced_ternary_notation, "-1/0/1")
        self.assertEqual(core.semantic_values, (-1, 0, 1))
        self.assertEqual(core.active_neutral_state, 0)
        self.assertEqual(core.zero_role, "active_computational_state")
        self.assertFalse(core.classical_bit_addition_primary_mechanism)
        self.assertEqual(
            core.primary_computational_organization,
            "retained_relative_phase_interference_and_resonant_selection",
        )
        self.assertEqual(core.computation_chain, _COMPUTATION_CHAIN)
        self.assertEqual(core.temporal_scheduler_modes, ("1/7", "7/1"))
        self.assertEqual(
            core.opposite_transition_routes,
            ((-1, 0, 1), (1, 0, -1)),
        )

    def test_core_declaration_round_trips_exact_source_mapping(self) -> None:
        source = self.dataset.visualizer_dispatch.parsed_artifact.root["core"]
        self.assertEqual(
            self.dataset.core_declaration.source_payload(),
            _plain_json_value(source),
        )
        self.assertEqual(
            self.dataset.core_declaration.core_declaration_id,
            "32490746-831a-5667-9b11-27d6673cf893",
        )
        self.assertEqual(
            self.dataset.core_declaration.source_record_sha256,
            "05c98cfb19ec7ef85f0fab47bf80e2c2330e4595255411d366269a511b5c0b9a",
        )

    def test_complete_frame_inventory_is_unique_and_source_ordered(self) -> None:
        frames = self.dataset.transition_frames
        self.assertEqual(self.dataset.transition_frame_count, 800)
        self.assertEqual(len({frame.transition_frame_id for frame in frames}), 800)
        self.assertEqual(len({frame.frame_sha256 for frame in frames}), 800)
        self.assertEqual(
            Counter(frame.contour_index for frame in frames),
            Counter({0: 768, 1: 32}),
        )

    def test_representative_frame_identity_ledger_is_exact(self) -> None:
        observed = tuple(
            (
                index,
                self.dataset.transition_frames[index].transition_frame_id,
                self.dataset.transition_frames[index].frame_sha256,
            )
            for index in (0, 8, 799)
        )
        self.assertEqual(
            observed,
            (
                (
                    0,
                    "4b9228a3-4cd6-570c-a94b-055a54448cea",
                    "34f13b2b139d416e0a875cffa164ecf9e0ecdb533ba4ec16e427b295b83c359e",
                ),
                (
                    8,
                    "b09822ce-6413-5853-81c0-23e42063dc34",
                    "b4ebdcbe913eb5d7342f804b3fcde1bb2911228d5907ed42a016c9f27c0d5450",
                ),
                (
                    799,
                    "5890bf13-1331-5ce8-9072-a7682d2cf0bb",
                    "6180d566bbb7088ac8b78a74948ea063665fc7669685a154e51ed7ecd88d1197",
                ),
            ),
        )

    def test_every_frame_retains_exact_trace_cell_relation(self) -> None:
        expected = tuple(
            (contour, record, cell)
            for contour in self.dataset.trace_dataset.contours
            for record in contour.records
            for cell in record.cells
        )
        for frame, (contour, record, cell) in zip(
            self.dataset.transition_frames,
            expected,
            strict=True,
        ):
            self.assertEqual(frame.trace_contour_id, contour.trace_contour_id)
            self.assertEqual(frame.trace_record_id, record.trace_record_id)
            self.assertEqual(frame.cell_id, cell.cell_id)
            self.assertEqual(
                (
                    frame.phase_derived_target,
                    frame.retained_state_before,
                    frame.retained_state_after,
                    frame.pending_route_before,
                    frame.pending_route_after,
                ),
                (
                    cell.phase_derived_target,
                    cell.retained_state_before,
                    cell.retained_state_after,
                    cell.pending_route_before,
                    cell.pending_route_after,
                ),
            )

    def test_every_frame_has_exact_source_coordinate(self) -> None:
        for frame in self.dataset.transition_frames:
            self.assertEqual(
                frame.source_location,
                SourceLocation(
                    json_path=(
                        f"$.records[{frame.sequence}]."
                        f"retained_state_after[{frame.cell_id}]"
                    ),
                    array_index=frame.cell_id,
                    package_member=frame.source_path,
                    source_record_ordinal=frame.sequence + 1,
                ),
            )

    def test_balanced_ternary_domain_is_exactly_minus1_0_1(self) -> None:
        observed: set[int] = set()
        for frame in self.dataset.transition_frames:
            states = (
                frame.phase_derived_target,
                frame.retained_state_before,
                frame.retained_state_after,
                frame.pending_route_before,
                frame.pending_route_after,
            )
            observed.update(states)
            self.assertTrue(set(states).issubset({-1, 0, 1}))
        self.assertEqual(observed, {-1, 0, 1})

    def test_no_frame_contains_direct_opposite_transition(self) -> None:
        for frame in self.dataset.transition_frames:
            self.assertNotIn(
                (frame.retained_state_before, frame.retained_state_after),
                ((-1, 1), (1, -1)),
            )

    def test_transition_classification_inventory_is_exact(self) -> None:
        self.assertEqual(
            self.dataset.transition_classification_counts,
            _TRANSITION_COUNTS,
        )

    def test_active_zero_route_leg_inventory_is_exact(self) -> None:
        self.assertEqual(self.dataset.route_leg_counts, _ROUTE_COUNTS)

    def test_first_route_legs_retain_zero_and_pending_polarity(self) -> None:
        observed = tuple(
            (
                frame.contour_index,
                frame.sequence,
                frame.cell_id,
                frame.retained_state_before,
                frame.retained_state_after,
                frame.pending_route_after,
            )
            for frame in self.dataset.transition_frames
            if frame.route_leg == "first_leg_to_active_zero"
        )
        self.assertEqual(observed, _FIRST_ROUTE_LEGS)

    def test_pending_route_completions_start_from_active_zero(self) -> None:
        observed = tuple(
            (
                frame.contour_index,
                frame.sequence,
                frame.cell_id,
                frame.retained_state_before,
                frame.retained_state_after,
                frame.pending_route_before,
                frame.pending_route_after,
            )
            for frame in self.dataset.transition_frames
            if frame.route_leg == "pending_route_completion"
        )
        self.assertEqual(observed, _ROUTE_COMPLETIONS)

    def test_active_zero_roles_and_observation_count_are_exact(self) -> None:
        self.assertEqual(self.dataset.active_zero_roles, _ACTIVE_ZERO_ROLES)
        self.assertEqual(
            self.dataset.active_zero_after_observation_count,
            702,
        )

    def test_scheduler_modes_and_states_preserve_record_multiplicity(self) -> None:
        self.assertEqual(
            Counter(frame.scheduler_mode for frame in self.dataset.transition_frames),
            Counter({"free": 152, "7/1": 512, "1/7": 136}),
        )
        self.assertEqual(
            Counter(frame.scheduler_state for frame in self.dataset.transition_frames),
            Counter(
                {
                    "balance": 448,
                    "commit": 64,
                    "excite": 24,
                    "free": 152,
                    "neutralize": 112,
                }
            ),
        )

    def test_thermal_contours_remain_four_separate_ordered_panels(self) -> None:
        self.assertEqual(self.dataset.thermal_contour_count, 4)
        self.assertEqual(
            tuple(
                (
                    contour.contour_name,
                    contour.contour_group,
                    contour.source_json_path,
                    contour.measurement_class,
                    contour.thermal_contour_id,
                    contour.payload_sha256,
                )
                for contour in self.dataset.thermal_contours
            ),
            _THERMAL_IDENTITIES,
        )
        self.assertEqual(
            len({id(contour) for contour in self.dataset.thermal_contours}),
            4,
        )

    def test_historical_thermal_comparison_is_exact(self) -> None:
        payload = self.dataset.thermal_contour(
            "historical_release_benchmark"
        ).payload()
        focused = payload["focused_binary_ternary_comparison"]
        self.assertEqual(payload["release"], "FRP v0.9.3")
        self.assertEqual(payload["winner_assertions"], [])
        self.assertEqual(focused["binary_heat_peak"], "0.051000")
        self.assertEqual(
            focused["active_neutral_ternary_heat_peak"],
            "0.003250",
        )
        self.assertEqual(
            focused["heat_peak_ratio_binary_over_active_neutral_ternary"],
            "15.6923076923",
        )
        self.assertEqual(
            focused["heat_peak_relative_reduction_percent"],
            "93.63",
        )

    def test_current_comparative_baseline_is_not_historical_panel(self) -> None:
        payload = self.dataset.thermal_contour(
            "current_comparative_baseline"
        ).payload()
        self.assertEqual(
            payload["schema"],
            "frp.benchmark.architecture_comparison.v1",
        )
        self.assertEqual(payload["qualification_status"], "PASS")
        self.assertEqual(payload["frp_scheduler"], "7/1")
        self.assertEqual(payload["winner_assertions"], [])
        self.assertEqual(len(payload["comparison_matrix"]), 4)

    def test_current_hardware_sensitivity_is_exact(self) -> None:
        payload = self.dataset.thermal_contour(
            "current_hardware_sensitivity"
        ).payload()
        self.assertEqual(
            payload["schema"],
            "frp.benchmark.hardware_sensitivity_comparison.v1",
        )
        self.assertEqual(payload["qualification_status"], "PASS")
        self.assertEqual(
            payload["scenario_order"],
            ["lower_bound", "nominal", "upper_bound"],
        )
        self.assertEqual(payload["winner_assertions"], [])

    def test_current_thermal_profile_is_exact(self) -> None:
        payload = self.dataset.thermal_contour(
            "current_thermal_profile"
        ).payload()
        self.assertEqual(payload["profile_name"], "common_rc_thermal_proxy_v1")
        self.assertEqual(
            payload["temperature_unit"],
            "normalized_temperature_proxy",
        )
        self.assertEqual(
            payload["raw_sha256"],
            "aeafebc3e71d1311a3445bd1528cbe7322546f79d6a5099dfed3a9590fc4a25b",
        )

    def test_no_thermal_panel_claims_physical_temperature(self) -> None:
        self.assertEqual(
            self.dataset.physical_temperature_measurement_count,
            0,
        )
        self.assertTrue(
            all(
                contour.physical_temperature_measurement is False
                for contour in self.dataset.thermal_contours
            )
        )

    def test_evidence_boundaries_are_exact(self) -> None:
        self.assertEqual(self.dataset.evidence_boundaries, _EVIDENCE_BOUNDARIES)

    def test_publication_contract_is_read_only_and_one_way(self) -> None:
        self.assertEqual(self.dataset.publication_contract, _PUBLICATION_CONTRACT)

    def test_repeated_visualization_is_deterministic_across_loaded_at(self) -> None:
        repeated = visualize_m31_published_documents(
            self.upstream_root,
            loaded_at=_LATER_LOADED_AT,
        )
        self.assertNotEqual(
            repeated.audit_batch.dispatch_batch.registry_validation
            .boundary.loaded_at,
            self.dataset.audit_batch.dispatch_batch.registry_validation
            .boundary.loaded_at,
        )
        self.assertEqual(repeated.dataset_sha256, self.dataset.dataset_sha256)
        self.assertEqual(
            repeated.visualizer_dataset_id,
            self.dataset.visualizer_dataset_id,
        )
        self.assertEqual(
            tuple(frame.transition_frame_id for frame in repeated.transition_frames),
            tuple(
                frame.transition_frame_id
                for frame in self.dataset.transition_frames
            ),
        )
        self.assertEqual(
            tuple(contour.thermal_contour_id for contour in repeated.thermal_contours),
            tuple(
                contour.thermal_contour_id
                for contour in self.dataset.thermal_contours
            ),
        )

    def test_command_line_summary_is_exact(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "transition_visualizer.m31_published_transition_visualizer",
                "--upstream-root",
                str(self.upstream_root),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        lines = completed.stdout.splitlines()
        for expected in (
            "FRP Observatory M31 published Transition Visualizer: PASS",
            "transition_frames=800",
            "active_zero_after_observations=702",
            "classical_bit_addition_primary_mechanism=false",
            "balanced_ternary_notation=-1/0/1",
            "active_neutral_state=0",
            "temporal_scheduler_modes=1/7,7/1",
            "thermal_contours=4",
            "physical_temperature_measurements=0",
            "source_execution=forbidden",
            "metric_normalization=forbidden",
            "thermal_contour_merging=forbidden",
            "semantic_reimplementation=forbidden",
            "source_mutation=forbidden",
            "downstream_writeback=forbidden",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, lines)

    def test_dataset_and_nested_projection_values_are_frozen(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset, "dataset_sha256", "0" * 64)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset.core_declaration, "active_neutral_state", 1)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset.transition_frames[0], "cell_id", 1)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset.thermal_contours[0], "contour_group", "current")

    def test_forged_dataset_digest_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "dataset_sha256 does not bind complete M31 visualization",
        ):
            replace(self.dataset, dataset_sha256="0" * 64)

    def test_core_cannot_be_relabelled_as_classical_bit_addition(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "published FRP computation or ternary-core declaration changed",
        ):
            replace(
                self.dataset.core_declaration,
                classical_bit_addition_primary_mechanism=True,
            )

    def test_core_active_zero_cannot_be_relabelled(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "published FRP computation or ternary-core declaration changed",
        ):
            replace(self.dataset.core_declaration, active_neutral_state=1)

    def test_direct_opposite_frame_is_rejected(self) -> None:
        frame = self.dataset.transition_frames[0]
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "direct opposite retained-state transitions are forbidden",
        ):
            replace(
                frame,
                retained_state_before=-1,
                retained_state_after=1,
            )

    def test_frame_transition_classification_cannot_be_relabelled(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "frame transition classification differs from source states",
        ):
            replace(
                self.dataset.transition_frames[0],
                transition_classification="retained_same",
            )

    def test_frame_source_coordinate_cannot_be_invented(self) -> None:
        frame = self.dataset.transition_frames[0]
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "transition frame source coordinate changed",
        ):
            replace(
                frame,
                source_location=SourceLocation(
                    json_path="$.records[1].retained_state_after[0]",
                    array_index=0,
                    package_member=frame.source_path,
                    source_record_ordinal=1,
                ),
            )

    def test_frame_digest_cannot_be_forged(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "frame_sha256 does not bind complete frame projection",
        ):
            replace(self.dataset.transition_frames[0], frame_sha256="0" * 64)

    def test_frame_order_cannot_be_swapped_or_merged(self) -> None:
        frames = self.dataset.transition_frames
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "transition frame differs from exact trace source cell",
        ):
            replace(self.dataset, transition_frames=(frames[1], frames[0]) + frames[2:])
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "transition frame differs from exact trace source cell",
        ):
            replace(self.dataset, transition_frames=(frames[0], frames[0]) + frames[2:])

    def test_thermal_payload_digest_cannot_be_forged(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "thermal contour payload digest changed",
        ):
            replace(self.dataset.thermal_contours[0], payload_sha256="0" * 64)

    def test_thermal_contours_cannot_be_swapped_or_merged(self) -> None:
        contours = self.dataset.thermal_contours
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "thermal contour inventory or source order changed",
        ):
            replace(self.dataset, thermal_contours=tuple(reversed(contours)))
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "thermal contour inventory or source order changed",
        ):
            replace(
                self.dataset,
                thermal_contours=(contours[0], contours[0]) + contours[2:],
            )

    def test_thermal_payload_is_detached_from_dataset_state(self) -> None:
        contour = self.dataset.thermal_contours[0]
        payload = contour.payload()
        payload["release"] = "forged"
        self.assertEqual(contour.payload()["release"], "FRP v0.9.3")

    def test_unknown_thermal_contour_alias_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "unknown thermal contour",
        ):
            self.dataset.thermal_contour("historical")

    def test_active_zero_roles_cannot_be_truncated(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "active-zero role declaration changed",
        ):
            replace(
                self.dataset,
                active_zero_roles=self.dataset.active_zero_roles[:-1],
            )

    def test_evidence_boundary_cannot_be_removed(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "published evidence boundaries changed",
        ):
            replace(
                self.dataset,
                evidence_boundaries=self.dataset.evidence_boundaries[:-1],
            )

    def test_read_only_publication_contract_cannot_be_changed(self) -> None:
        altered = tuple(
            (
                name,
                "allowed" if name == "downstream_writeback" else value,
            )
            for name, value in self.dataset.publication_contract
        )
        with self.assertRaisesRegex(
            M31PublishedTransitionVisualizerError,
            "read-only Observatory publication contract changed",
        ):
            replace(self.dataset, publication_contract=altered)


if __name__ == "__main__":
    unittest.main()
