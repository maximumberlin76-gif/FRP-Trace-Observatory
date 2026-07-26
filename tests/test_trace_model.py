"""Tests for immutable Trace Explorer model contracts."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

from artifact_auditor.audit_report import (
    SourceLocation,
    ValidationStatus,
)
from parsers.m15_vector import M15VectorTraceKind
from schemas.registry import MeasurementContour, ObservatoryMode
from trace_explorer import (
    AggregationClassification,
    OrderingValidationStatus,
    TraceCompletenessStatus,
    TraceDataset,
    TraceFamily,
    TraceField,
    TraceModelError,
)
from transition_visualizer import SourceRecordReference


_FORMAT_IDENTIFIER = "frp.m15.vector.v1"
_SOURCE_SHA256 = "ab" * 32


def _record_id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"frp-trace-model-test:{label}"))


def _source_location(
    *,
    vector_column: str = "cells",
) -> SourceLocation:
    return SourceLocation(
        vector_column=vector_column,
        source_record_ordinal=1,
    )


def _source_reference(
    *,
    trace_dataset_id: str | None = None,
    normalized_record_id: str | None = None,
    source_ordinal: int = 0,
    tick: int = 0,
) -> SourceRecordReference:
    dataset_id = trace_dataset_id or _record_id("dataset")
    return SourceRecordReference(
        normalized_record_id=(
            normalized_record_id or _record_id("source-record")
        ),
        source_artifact_id=_record_id("source-artifact"),
        trace_dataset_id=dataset_id,
        registry_binding_id=_record_id("registry-binding"),
        validation_report_id=_record_id("validation-report"),
        source_sha256=_SOURCE_SHA256,
        source_ordinal=source_ordinal,
        tick=tick,
        validation_status=ValidationStatus.RECOGNIZED_VALID,
        source_locations=(_source_location(),),
        format_identifier=_FORMAT_IDENTIFIER,
    )


def _configuration_field(
    reference: SourceRecordReference,
    *,
    trace_field_id: str | None = None,
) -> TraceField:
    return TraceField(
        trace_field_id=trace_field_id or _record_id("config-field"),
        source_reference=reference,
        field_name="cells",
        value=2,
        source_location=_source_location(),
        source_encoding="decimal",
        unit="cell",
        validation_check_ids=(_record_id("config-check"),),
    )


def _incomplete_route_dataset() -> TraceDataset:
    dataset_id = _record_id("dataset")
    reference = _source_reference(trace_dataset_id=dataset_id)
    return TraceDataset(
        trace_dataset_id=dataset_id,
        normalized_artifact_id=_record_id("normalized-artifact"),
        trace_family=TraceFamily.M15_PENDING_ROUTE,
        measurement_contour=(
            MeasurementContour.M15_IMPLEMENTATION_MAPPING
        ),
        source_references=(reference,),
        configuration_fields=(_configuration_field(reference),),
        ordering_validation=OrderingValidationStatus.NOT_EVALUATED,
        completeness_status=(
            TraceCompletenessStatus.REQUIRED_COLLECTIONS_MISSING
        ),
        eligible_modes=(ObservatoryMode.ARTIFACT_AUDITOR,),
        kind=M15VectorTraceKind.PENDING_ROUTES.value,
        format_identifier=_FORMAT_IDENTIFIER,
        ordering_validation_check_ids=(
            _record_id("ordering-check"),
        ),
        validation_check_ids=(_record_id("dataset-check"),),
    )


class TraceFieldTests(unittest.TestCase):
    """Exercise exact field values and their source bindings."""

    def test_field_retains_value_metadata_and_provenance(self) -> None:
        reference = _source_reference()
        location = _source_location(vector_column="switch_load_q16")
        field = TraceField(
            trace_field_id=_record_id("telemetry-field"),
            source_reference=reference,
            field_name="switch_load_q16",
            value=(Decimal("0.5"), 32768, None),
            source_location=location,
            source_encoding="S32Q16",
            unit="q16",
            aggregation=AggregationClassification.CURRENT_TICK,
            validation_check_ids=(_record_id("telemetry-check"),),
        )

        self.assertEqual(
            field.value,
            (Decimal("0.5"), 32768, None),
        )
        self.assertIs(field.source_reference, reference)
        self.assertIs(field.source_location, location)
        self.assertEqual(field.source_encoding, "S32Q16")
        self.assertEqual(field.unit, "q16")
        self.assertIs(
            field.aggregation,
            AggregationClassification.CURRENT_TICK,
        )

    def test_field_rejects_noncanonical_metadata(self) -> None:
        reference = _source_reference()
        field = TraceField(
            trace_field_id=_record_id("invalid-field"),
            source_reference=reference,
            field_name="heat_q16",
            value=0,
            source_location=_source_location(
                vector_column="heat_q16"
            ),
        )

        with self.assertRaisesRegex(
            TraceModelError,
            "field_name must not contain whitespace",
        ):
            replace(
                field,
                field_name="heat q16",
            )

        with self.assertRaisesRegex(
            TraceModelError,
            "value must be finite",
        ):
            replace(
                field,
                value=Decimal("NaN"),
            )

        duplicate_check = _record_id("duplicate-check")
        with self.assertRaisesRegex(
            TraceModelError,
            "validation_check_ids must be unique",
        ):
            replace(
                field,
                validation_check_ids=(
                    duplicate_check,
                    duplicate_check,
                ),
            )

        with self.assertRaisesRegex(
            TraceModelError,
            "aggregation must be an AggregationClassification",
        ):
            replace(
                field,
                aggregation="current_tick",
            )

    def test_field_is_frozen(self) -> None:
        field = _configuration_field(_source_reference())

        with self.assertRaises(FrozenInstanceError):
            setattr(field, "value", 4)


class TraceDatasetTests(unittest.TestCase):
    """Exercise dataset identity, completeness, and immutability."""

    def test_incomplete_dataset_is_auditor_only(self) -> None:
        dataset = _incomplete_route_dataset()

        self.assertIs(
            dataset.trace_family,
            TraceFamily.M15_PENDING_ROUTE,
        )
        self.assertIs(
            dataset.measurement_contour,
            MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        )
        self.assertEqual(
            dataset.eligible_modes,
            (ObservatoryMode.ARTIFACT_AUDITOR,),
        )
        self.assertIsNone(dataset.route_event_ids)
        self.assertIsNone(dataset.request_lane_record_ids)
        self.assertIsNone(dataset.transition_record_ids)
        self.assertIsInstance(dataset.record_counts, MappingProxyType)
        self.assertIsNone(dataset.record_counts["route_events"])

    def test_family_contour_and_identity_cannot_be_rebound(self) -> None:
        dataset = _incomplete_route_dataset()

        with self.assertRaisesRegex(
            TraceModelError,
            "measurement_contour does not match trace_family",
        ):
            replace(
                dataset,
                measurement_contour=(
                    MeasurementContour.STRUCTURED_OUTPUT
                ),
            )

        with self.assertRaisesRegex(
            TraceModelError,
            "upstream identity does not match trace_family",
        ):
            replace(
                dataset,
                kind=M15VectorTraceKind.CELL_TRACE.value,
            )

        with self.assertRaisesRegex(
            TraceModelError,
            "source format binding does not match the dataset",
        ):
            modified_reference = replace(
                dataset.source_references[0],
                format_identifier="frp.m15.vector.v2",
            )
            modified_field = replace(
                dataset.configuration_fields[0],
                source_reference=modified_reference,
            )
            replace(
                dataset,
                source_references=(modified_reference,),
                configuration_fields=(modified_field,),
            )

    def test_completeness_controls_display_mode_eligibility(self) -> None:
        dataset = _incomplete_route_dataset()

        with self.assertRaisesRegex(
            TraceModelError,
            "completeness_status does not match collection presence",
        ):
            replace(
                dataset,
                completeness_status=(
                    TraceCompletenessStatus.REQUIRED_COLLECTIONS_PRESENT
                ),
            )

        with self.assertRaisesRegex(
            TraceModelError,
            "display modes require valid order, domain, and collections",
        ):
            replace(
                dataset,
                eligible_modes=(
                    ObservatoryMode.ARTIFACT_AUDITOR,
                    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ),
            )

        with self.assertRaisesRegex(
            TraceModelError,
            "eligible_modes contains a mode unsupported by this family",
        ):
            replace(
                dataset,
                eligible_modes=(
                    ObservatoryMode.ARTIFACT_AUDITOR,
                    ObservatoryMode.TRACE_EXPLORER,
                ),
            )

    def test_source_reference_metadata_must_match_registry_entry(
        self,
    ) -> None:
        dataset = _incomplete_route_dataset()
        registered = dataset.source_references[0]
        modified = replace(registered, tick=registered.tick + 1)
        modified_field = replace(
            dataset.configuration_fields[0],
            source_reference=modified,
        )

        with self.assertRaisesRegex(
            TraceModelError,
            "source record metadata must match its registered value",
        ):
            replace(
                dataset,
                configuration_fields=(modified_field,),
            )

    def test_owned_and_referenced_ids_must_be_unique(self) -> None:
        dataset = _incomplete_route_dataset()
        duplicate_field = replace(
            dataset.configuration_fields[0],
            trace_field_id=dataset.trace_dataset_id,
        )

        with self.assertRaisesRegex(
            TraceModelError,
            "all owned and referenced record IDs must be unique",
        ):
            replace(
                dataset,
                configuration_fields=(duplicate_field,),
            )

    def test_dataset_and_count_view_are_immutable(self) -> None:
        dataset = _incomplete_route_dataset()

        with self.assertRaises(FrozenInstanceError):
            setattr(
                dataset,
                "eligible_modes",
                (ObservatoryMode.ARTIFACT_AUDITOR,),
            )

        with self.assertRaises(TypeError):
            dataset.record_counts["route_events"] = 0


if __name__ == "__main__":
    unittest.main()
