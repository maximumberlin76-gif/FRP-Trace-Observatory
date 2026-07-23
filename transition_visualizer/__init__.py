"""Read-only models and derived views for FRP transition visualization.

This package preserves validated source provenance while presenting canonical
ternary states, transitions, scheduler records, request lanes, pending routes,
telemetry, event counters, and invariant vectors. Derived filters, projections,
and correlations remain explicitly labeled Observatory-derived views.

It does not modify source artifacts, infer absent events, redefine processor
semantics, combine measurement contours, or select a user-interface framework.
"""

from transition_visualizer.invariant_model import (
    InvariantBitRecord,
    InvariantBitValue,
    InvariantModelError,
    InvariantVectorRecord,
)
from transition_visualizer.request_route_model import (
    RequestAcceptanceStatus,
    RequestLaneRecord,
    RequestRouteModelError,
    RouteEventRecord,
    RouteStatus,
)
from transition_visualizer.scheduler_model import (
    SchedulerField,
    SchedulerFieldValue,
    SchedulerMode,
    SchedulerModelError,
    SchedulerNormalizedValue,
    SchedulerSnapshot,
    SchedulerSourceValue,
    SchedulerState,
)
from transition_visualizer.telemetry_model import (
    EventCounterName,
    EventCounterSnapshot,
    EventCounterValue,
    TelemetryModelError,
    TelemetryScalar,
    TransitionTelemetryField,
    TransitionTelemetryRecord,
    TransitionTelemetryValue,
)
from transition_visualizer.transition_model import (
    CANONICAL_TERNARY_DOMAIN,
    CanonicalTernaryState,
    RecordOrigin,
    RouteLegClassification,
    SourceRecordReference,
    SourceStateValue,
    TernaryStateValue,
    TransitionClassification,
    TransitionModelError,
    TransitionRecord,
    classify_transition,
)
from transition_visualizer.view_builder import (
    EventTypeField,
    TickField,
    TransitionViewBuilder,
    TransitionViewBuilderError,
    ViewBuildContext,
)
from transition_visualizer.view_model import (
    OBSERVATORY_DERIVED_LABEL,
    TransitionViewModelError,
    TransitionViewType,
    TransitionVisualizerDataset,
    TransitionVisualizerView,
    ViewParameter,
    ViewParameterValue,
    ViewScalar,
    VisualizerRecordType,
)


__all__ = [
    "CANONICAL_TERNARY_DOMAIN",
    "OBSERVATORY_DERIVED_LABEL",
    "CanonicalTernaryState",
    "EventCounterName",
    "EventCounterSnapshot",
    "EventCounterValue",
    "EventTypeField",
    "InvariantBitRecord",
    "InvariantBitValue",
    "InvariantModelError",
    "InvariantVectorRecord",
    "RecordOrigin",
    "RequestAcceptanceStatus",
    "RequestLaneRecord",
    "RequestRouteModelError",
    "RouteEventRecord",
    "RouteLegClassification",
    "RouteStatus",
    "SchedulerField",
    "SchedulerFieldValue",
    "SchedulerMode",
    "SchedulerModelError",
    "SchedulerNormalizedValue",
    "SchedulerSnapshot",
    "SchedulerSourceValue",
    "SchedulerState",
    "SourceRecordReference",
    "SourceStateValue",
    "TelemetryModelError",
    "TelemetryScalar",
    "TernaryStateValue",
    "TickField",
    "TransitionClassification",
    "TransitionModelError",
    "TransitionRecord",
    "TransitionTelemetryField",
    "TransitionTelemetryRecord",
    "TransitionTelemetryValue",
    "TransitionViewBuilder",
    "TransitionViewBuilderError",
    "TransitionViewModelError",
    "TransitionViewType",
    "TransitionVisualizerDataset",
    "TransitionVisualizerView",
    "ViewBuildContext",
    "ViewParameter",
    "ViewParameterValue",
    "ViewScalar",
    "VisualizerRecordType",
    "classify_transition",
]
