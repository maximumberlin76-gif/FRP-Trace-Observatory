"""Tests for immutable transition visualizer datasets and views."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from artifact_auditor.audit_report import (
    SourceLocation,
    ValidationStatus,
)
from schemas.registry import MeasurementContour
from transition_visualizer import (
    OBSERVATORY_DERIVED_LABEL,
    CanonicalTernaryState,
    RecordOrigin,
    SourceRecordReference,
    TernaryStateValue,
    TransitionViewModelError,
    TransitionViewType,
    TransitionVisualizerDataset,
    TransitionVisualizerView,
    ViewParameter,
    VisualizerRecordType,
)


_SCHEMA_IDENTIFIER = "frp.m15.cycle_exact_reference_trace.v1.7.0"
_SOURCE_SHA256 = "ef" * 32
_CREATED_AT = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)


def _record_id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"frp-view-model-test:{label}"))


def _location(index: int, field_name: str) -> SourceLocation:
    return SourceLocation(
        json_path=f"$.trace[{index}].{field_name}",
        source_record_ordinal=index + 1,
    )


def _reference(
    index: int,
    *,
    trace_dataset_id: str | None = None,
    artifact_label: str = "source-artifact",
) -> SourceRecordReference:
    dataset_id = trace_dataset_id or _record_id("trace-dataset")
    return SourceRecordReference(
        normalized_record_id=_record_id(
            f"source-{artifact_label}-{index}"
        ),
        source_artifact_id=_record_id(artifact_label),
        trace_dataset_id=dataset_id,
        registry_binding_id=_record_id("registry-binding"),
        validation_report_id=_record_id("validation-report"),
        source_sha256=_SOURCE_SHA256,
        source_ordinal=index,
        tick=index,
        validation_status=ValidationStatus.RECOGNIZED_VALID,
        source_locations=(_location(index, "tick"),),
        schema_identifier=_SCHEMA_IDENTIFIER,
    )


def _state_value(
    label: str,
    reference: SourceRecordReference,
    *,
    cell_id: int,
    state: CanonicalTernaryState,
) -> TernaryStateValue:
    return TernaryStateValue(
        state_value_id=_record_id(label),
        source_reference=reference,
        cell_id=cell_id,
        source_value=int(state),
        source_encoding="canonical_balanced_ternary",
        canonical_state=state,
        origin=RecordOrigin.UPSTREAM_SOURCE,
    )


def _dataset() -> TransitionVisualizerDataset:
    trace_dataset_id = _record_id("trace-dataset")
    references = (
        _reference(0, trace_dataset_id=trace_dataset_id),
        _reference(1, trace_dataset_id=trace_dataset_id),
    )
    return TransitionVisualizerDataset(
        visualizer_dataset_id=_record_id("visualizer-dataset"),
        trace_dataset_id=trace_dataset_id,
        measurement_contour=(
            MeasurementContour.M15_IMPLEMENTATION_MAPPING
        ),
        source_references=references,
        state_values=(
            _state_value(
                "state-zero",
                references[0],
                cell_id=0,
                state=CanonicalTernaryState.NEUTRAL,
            ),
            _state_value(
                "state-positive",
                references[1],
                cell_id=1,
                state=CanonicalTernaryState.POSITIVE,
            ),
        ),
        validation_check_ids=(_record_id("dataset-check"),),
    )


def _view(
    *,
    dataset: TransitionVisualizerDataset | None = None,
    view_type: TransitionViewType = TransitionViewType.TICK_FILTER,
    output_record_ids: tuple[str, ...] | None = None,
    source_order_preserved: bool = True,
) -> TransitionVisualizerView:
    source_dataset = dataset or _dataset()
    output_ids = (
        source_dataset.record_ids(VisualizerRecordType.STATE_VALUE)
        if output_record_ids is None
        else output_record_ids
    )
    return TransitionVisualizerView(
        derived_view_id=_record_id("derived-view"),
        source_dataset=source_dataset,
        view_type=view_type,
        record_type=VisualizerRecordType.STATE_VALUE,
        operation="select state values by validated tick",
        parameters=(ViewParameter(name="ticks", value=(0, 1)),),
        created_at=_CREATED_AT,
        registry_revision="v1.8.0-audit",
        source_artifact_ids=source_dataset.source_artifact_ids,
        normalized_record_ids=source_dataset.normalized_record_ids,
        output_record_ids=output_ids,
        source_order_preserved=source_order_preserved,
        observatory_version="0.1.0",
        validation_check_ids=(_record_id("view-check"),),
    )


class ViewParameterTests(unittest.TestCase):
    """Exercise immutable derived-view parameters."""

    def test_parameter_preserves_scalar_tuple(self) -> None:
        parameter = ViewParameter(
            name="event_values",
            value=(None, False, 0, "accepted"),
        )

        self.assertEqual(
            parameter.value,
            (None, False, 0, "accepted"),
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(parameter, "name", "changed")

    def test_parameter_rejects_noncanonical_name_and_value(self) -> None:
        with self.assertRaisesRegex(
            TransitionViewModelError,
            "parameter name must not contain whitespace",
        ):
            ViewParameter(
                name="event values",
                value=("accepted",),
            )

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "contains an unsupported scalar",
        ):
            ViewParameter(
                name="fraction",
                value=Decimal("0.5"),
            )


class TransitionVisualizerDatasetTests(unittest.TestCase):
    """Exercise typed collections and dataset provenance."""

    def test_dataset_preserves_typed_records_and_source_order(
        self,
    ) -> None:
        dataset = _dataset()
        state_ids = (
            _record_id("state-zero"),
            _record_id("state-positive"),
        )

        self.assertEqual(
            dataset.records(VisualizerRecordType.STATE_VALUE),
            dataset.state_values,
        )
        self.assertEqual(
            dataset.record_ids(VisualizerRecordType.STATE_VALUE),
            state_ids,
        )
        self.assertEqual(
            dataset.normalized_record_ids,
            tuple(
                reference.normalized_record_id
                for reference in dataset.source_references
            ),
        )
        self.assertEqual(
            dataset.source_artifact_ids,
            (_record_id("source-artifact"),),
        )
        self.assertEqual(
            dataset.records(VisualizerRecordType.TRANSITION),
            (),
        )

    def test_dataset_requires_records_and_typed_contour(self) -> None:
        dataset = _dataset()

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "visualizer dataset must contain at least one record",
        ):
            replace(
                dataset,
                state_values=(),
            )

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "measurement_contour must be a MeasurementContour",
        ):
            replace(
                dataset,
                measurement_contour="m15_implementation_mapping",
            )

    def test_dataset_requires_unique_source_records(self) -> None:
        dataset = _dataset()
        reference = dataset.source_references[0]

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "source references must identify unique records",
        ):
            replace(
                dataset,
                source_references=(reference, reference),
            )

    def test_dataset_requires_one_trace_dataset(self) -> None:
        dataset = _dataset()
        foreign_reference = _reference(
            2,
            trace_dataset_id=_record_id("foreign-trace-dataset"),
        )

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "source references must belong to one trace dataset",
        ):
            replace(
                dataset,
                source_references=(
                    dataset.source_references[0],
                    foreign_reference,
                ),
            )

    def test_dataset_requires_globally_unique_record_ids(self) -> None:
        dataset = _dataset()
        first = dataset.state_values[0]
        duplicate = replace(
            dataset.state_values[1],
            state_value_id=first.state_value_id,
        )

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "visualizer record identifiers must be globally unique",
        ):
            replace(
                dataset,
                state_values=(first, duplicate),
            )

    def test_dataset_requires_every_record_source(self) -> None:
        dataset = _dataset()
        foreign_reference = _reference(2)
        foreign_state = _state_value(
            "foreign-state",
            foreign_reference,
            cell_id=2,
            state=CanonicalTernaryState.NEGATIVE,
        )

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "every record source must appear in source_references",
        ):
            replace(
                dataset,
                state_values=dataset.state_values + (foreign_state,),
            )

    def test_selected_record_references_remain_ordered(self) -> None:
        dataset = _dataset()
        state_ids = dataset.record_ids(
            VisualizerRecordType.STATE_VALUE
        )
        references = dataset.references_for_records(
            VisualizerRecordType.STATE_VALUE,
            tuple(reversed(state_ids)),
        )

        self.assertEqual(
            references,
            tuple(reversed(dataset.source_references)),
        )
        with self.assertRaisesRegex(
            TransitionViewModelError,
            "selected record does not belong to the dataset",
        ):
            dataset.references_for_records(
                VisualizerRecordType.STATE_VALUE,
                (_record_id("unknown-state"),),
            )


class TransitionVisualizerViewTests(unittest.TestCase):
    """Exercise derived labels, provenance, and order semantics."""

    def test_view_retains_dataset_without_mutation(self) -> None:
        dataset = _dataset()
        view = _view(dataset=dataset)

        self.assertIs(view.source_dataset, dataset)
        self.assertEqual(
            view.derived_label,
            OBSERVATORY_DERIVED_LABEL,
        )
        self.assertEqual(
            view.output_record_ids,
            dataset.record_ids(VisualizerRecordType.STATE_VALUE),
        )
        self.assertTrue(view.source_order_preserved)
        with self.assertRaises(FrozenInstanceError):
            setattr(view, "operation", "changed")

    def test_view_requires_exact_derived_label(self) -> None:
        view = _view()

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "derived view requires the Observatory-derived label",
        ):
            replace(
                view,
                derived_label="source view",
            )

    def test_view_requires_timezone_aware_creation_time(self) -> None:
        view = _view()

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "created_at must be timezone-aware",
        ):
            replace(
                view,
                created_at=datetime(2026, 7, 26, 12),
            )

    def test_view_requires_unique_parameter_names(self) -> None:
        view = _view()
        duplicate = ViewParameter(name="ticks", value=(1,))

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "parameter names must be unique",
        ):
            replace(
                view,
                parameters=view.parameters + (duplicate,),
            )

    def test_view_rejects_external_output_and_provenance(self) -> None:
        view = _view()

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "view output record is outside its typed collection",
        ):
            replace(
                view,
                output_record_ids=(_record_id("unknown-state"),),
            )

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "view source record is outside the dataset",
        ):
            replace(
                view,
                normalized_record_ids=(_record_id("unknown-source"),),
            )

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "view source artifact is outside the dataset",
        ):
            replace(
                view,
                source_artifact_ids=(_record_id("unknown-artifact"),),
            )

    def test_view_requires_selected_record_provenance(self) -> None:
        dataset = _dataset()
        selected_id = dataset.state_values[1].state_value_id
        view = _view(
            dataset=dataset,
            output_record_ids=(selected_id,),
        )

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "normalized_record_ids omit selected record provenance",
        ):
            replace(
                view,
                normalized_record_ids=(
                    dataset.source_references[0].normalized_record_id,
                ),
            )

    def test_view_enforces_declared_order_semantics(self) -> None:
        dataset = _dataset()
        state_ids = dataset.record_ids(
            VisualizerRecordType.STATE_VALUE
        )
        view = _view(dataset=dataset)

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "filter and source-order projections must preserve order",
        ):
            replace(
                view,
                source_order_preserved=False,
            )

        with self.assertRaisesRegex(
            TransitionViewModelError,
            "output_record_ids do not preserve source order",
        ):
            replace(
                view,
                output_record_ids=tuple(reversed(state_ids)),
            )

        sorted_view = _view(
            dataset=dataset,
            view_type=(
                TransitionViewType.EXPLICITLY_SORTED_PROJECTION
            ),
            output_record_ids=tuple(reversed(state_ids)),
            source_order_preserved=False,
        )
        self.assertFalse(sorted_view.source_order_preserved)


if __name__ == "__main__":
    unittest.main()
