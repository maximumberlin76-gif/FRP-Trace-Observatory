# FRP Trace Observatory Normalized Read-Only Data Model

- **Model status:** Implemented and tested
- **Upstream audit baseline:** FRP v1.8.0 / M16
- **Observatory version:** Not assigned
- **Executable compatibility records:** 19
- **Current local verification:** 275 tests, `OK`

## Purpose

This document describes the implemented immutable data boundary between source
capture, parsers, compatibility dispatch, Artifact Auditor, Trace Explorer,
and Ternary Transition Visualizer.

FRP remains the sole authority for processor semantics and published artifact
values. Observatory records preserve source values, add typed downstream
access, and label every computed representation by its origin.

The model does not rename upstream schemas, execute producers, modify source
bytes, infer absent processor events, or combine measurement contours.

## Implemented Module Boundary

| Layer | Exact implementation | Primary records |
|---|---|---|
| Source capture | `parsers/source_artifact.py` | `RawSourceDigest`, `SourceArtifact` |
| JSON parsing | `parsers/json_artifact.py` | `ParsedJsonArtifact` |
| M15 vector parsing | `parsers/m15_vector.py` | `M15VectorMetadataEntry`, `M15VectorRow`, `M15VectorArtifact` |
| Registry | `schemas/registry.py` | `CompatibilityRecord` |
| Dispatch | `parsers/artifact_dispatch.py` | `RegistrationResult`, `DispatchedArtifact` |
| Audit reporting | `artifact_auditor/audit_report.py` | `AuditValueSnapshot`, `SourceLocation`, `ValidationCheck`, `AuditReport` |
| Audit execution | `artifact_auditor/validation_core.py`, `artifact_auditor/auditor.py` | `ValidationCheckSpec`, ordered report construction |
| Fixture provenance | `artifact_auditor/fixture_manifest.py` | `RawDigestContract`, `CanonicalFixtureRecord`, `CanonicalFixtureManifest` |
| Trace normalization | `trace_explorer/trace_model.py` | `TraceField`, `TickRecord`, `CellTraceRecord`, `TraceDataset` |
| Trace construction | `trace_explorer/trace_builder.py` | `TraceDatasetBuilder` |
| Transition records | `transition_visualizer/*.py` | source-linked state, scheduler, request, route, telemetry, counter, and invariant records |
| Derived views | `transition_visualizer/view_model.py`, `transition_visualizer/view_builder.py` | `TransitionVisualizerDataset`, `TransitionVisualizerView` |

There is no separate implemented `ArtifactProvenance`, `RegistryBinding`,
`DigestRecord`, `NormalizedArtifact`, `VectorDataset`, `BenchmarkDataset`, or
`QualificationEvidenceRecord` class. Their current responsibilities are held
by the exact records listed above.

## Global Invariants

1. Captured source bytes remain unchanged.
2. Raw SHA-256 is calculated over the captured bytes before parsing.
3. Public data records are frozen, slotted dataclasses.
4. Parsed arrays use tuples and parsed JSON objects use immutable mappings.
5. Source order is retained unless a derived view explicitly records sorting.
6. Integer, `Decimal`, Boolean, string, null, and absence remain distinct.
7. A missing field is not replaced with zero, false, null, or an empty value.
8. Every normalized source record retains source-artifact, registry, audit,
   digest, ordinal, tick, and source-location provenance.
9. Encoded states remain separate from canonical states.
10. Canonical processor states are displayed only as `-1`, `0`, and `1`.
11. Scheduler mode and scheduler state remain distinct types.
12. Measurement contours are not merged.
13. Validation output remains separate from source values.
14. Derived values require explicit derivation identity and operation.
15. Artifact content, producer commands, Python, and SystemVerilog are never
    executed by parsing or auditing.

## Identity Chain

The implemented identity chain is:

1. `SourceArtifact.source_artifact_id` identifies one load.
2. `RawSourceDigest.digest_record_id` identifies its raw digest record.
3. `CompatibilityRecord` supplies the exact registered contract.
4. `AuditReport.registry_binding_id` binds one source load to one registry
   revision and compatibility record.
5. `TraceDataset.trace_dataset_id` identifies one normalized trace dataset.
6. `TraceDataset.normalized_artifact_id` identifies its normalization result.
7. `SourceRecordReference.normalized_record_id` identifies one normalized
   source record.
8. Typed records receive their own UUID identifiers.
9. `TransitionVisualizerView.derived_view_id` identifies one derived view.

Loading identical bytes twice creates separate load identities. The two loads
may share the same raw SHA-256 but retain separate provenance.

## Value and Ordering Rules

`ParsedJsonArtifact` preserves JSON values as `None`, `bool`, `int`, finite
`Decimal`, `str`, nested tuples, and immutable string-key mappings.

The parser rejects duplicate object keys, non-finite numbers, invalid UTF-8,
invalid JSON syntax, array roots, unescaped control characters, and excessive
nesting.

Source order is retained for JSON arrays, M15 metadata declarations, vector
rows and columns, processor ticks, per-cell rows, request lanes, pending-route
records, invariant bits, and audit checks.

Object-key order is retained by the parsed mapping but receives no processor
semantics unless the upstream contract explicitly defines it.

## Source Capture Model

### `RawSourceDigest`

| Field | Contract |
|---|---|
| `digest_record_id` | UUID |
| `value` | 64 lowercase hexadecimal characters |
| `algorithm` | exactly `sha256` |
| `byte_scope` | exactly `raw_source_bytes` |

### `SourceArtifact`

| Field | Contract |
|---|---|
| `source_artifact_id` | UUID for one load |
| `source_filename` | nonempty filename without path separators |
| `source_path` | exact path text or `None` |
| `raw_bytes` | immutable captured bytes |
| `byte_length` | exact byte count |
| `detected_container_format` | safe outer-format classification |
| `source_digest` | matching `RawSourceDigest` |
| `loaded_at` | timezone-aware timestamp normalized to UTC |
| `load_status` | exactly `captured` |

Container formats are `empty`, `json_candidate`, `utf8_text`, `zip`, and
`binary`.

`SourceArtifact.verify_integrity()` recalculates the raw digest. File loading
accepts regular files and rejects symbolic links. Detection does not execute
source content.

## Parsed Artifact Model

### `ParsedJsonArtifact`

Fields are `source_artifact`, immutable `root`, `text_encoding`,
`declared_schema_identifier`, and `declared_kind`.

Supported encodings are `utf-8` and `utf-8-sig`. Declared schema and kind are
retained only when their exact root values are strings. Non-string declarations
remain unchanged in the parsed root and are handled by dispatch as invalid
identity data.

### `M15VectorArtifact`

| Record | Exact fields |
|---|---|
| `M15VectorMetadataEntry` | `key`, `raw_json`, `value`, `line_number` |
| `M15VectorRow` | `line_number`, ordered `fields` |
| `M15VectorArtifact` | `source_artifact`, `metadata_entries`, `column_header_line_number`, `columns`, `rows`, `text_encoding`, `format_identifier`, `declared_trace_kind` |

Recognized trace kinds are `kernel_transition_vectors`, `pending_routes`,
`scheduler_free_vectors`, `scheduler_7_1_vectors`, `scheduler_1_7_vectors`,
`full_correlation_vectors`, and `cell_trace`.

The parser preserves metadata order, raw metadata JSON, row line numbers,
column order, row field text, and optional UTF-8 BOM detection.

## Registry and Dispatch Model

### `CompatibilityRecord`

Fields are `identifier`, `identifier_field`, `schema_version`,
`artifact_format`, `artifact_kind`, `measurement_contour`, `producer_path`,
`producer_version`, `evidence_kind`, `evidence_path`,
`canonical_fixture_path`, `observatory_modes`, and `upstream_release`.

Identity fields are `schema` and `format_version`. Artifact formats are `json`
and `frp_m15_vector_text`.

### `RegistrationResult`

Registration statuses are `registered`, `missing_identifier`,
`invalid_identifier`, `unknown_identifier`, `unsupported_kind`, and
`not_applicable`.

The record retains the identifier field, declared identifier, declared kind,
matched compatibility record, and exact expected kinds when applicable.

### `DispatchedArtifact`

Fields are `source_artifact`, `classification`, `parsed_artifact`, and
`registration`.

Classifications are `empty`, `json`, `m15_vector`, `utf8_text`, `zip`, and
`binary`. Parser errors remain parser errors and are not silently reclassified.
Only a verified parsed artifact can receive a registered compatibility result.

## Audit Model

### Validation Enumerations

Overall statuses are `recognized_valid`, `recognized_valid_with_warnings`,
`recognized_invalid`, `known_unsupported`, `unrecognized`, and
`incomplete_package`.

Check outcomes are `pass`, `fail`, `warning`, `not_applicable`, and
`not_evaluated`. Message severities are `info`, `warning`, and `error`.

Validation categories are `container`, `identity`, `structure`, `type`,
`allowed_value`, `ternary_domain`, `ordering`, `scheduler_relation`,
`transition_capacity`, `pending_route`, `invariant_vector`, `digest`,
`deterministic_package`, and `qualification_evidence`.

### `SourceLocation`

Optional coordinates are `line_number`, `column_number`, `json_path`,
`array_index`, `vector_column`, `package_member`, `markdown_heading`,
`markdown_table_row`, and `source_record_ordinal`.

At least one coordinate is required. Locations are recorded only when known.

### `ValidationCheck`

Fields are `check_id`, `check_code`, `category`, `outcome`, `severity`,
`source_locations`, `expected`, `observed`, `message`,
`upstream_rule_reference`, and `mandatory`.

`fail` requires error severity, `warning` requires warning severity, and other
outcomes carry no severity. Expected and observed values are immutable
`AuditValueSnapshot` records.

### `AuditReport`

The report retains:

- audit and source identities;
- filename, path, raw SHA-256, byte length, and load time;
- detected classification and declared schema and kind;
- registry binding, matched identifier, and matched kind;
- producer path and version;
- measurement contour;
- audit start and completion timestamps;
- Observatory version when assigned;
- registry revision;
- ordered checks;
- missing package members;
- derived overall status.

Recognized status is never inferred without exact registry association.
Incomplete package status requires explicit missing members. Report origin is
`observatory_derived`.

Audit reports have implemented immutable mapping, deterministic compact JSON,
and text serializers. These serializers do not serialize source bytes.

## Canonical Fixture Model

`CanonicalFixtureManifest` retains its own captured source and parsed JSON,
manifest identity, upstream repository, release, milestone, ordering rule,
fixture count, raw digest contract, copy requirement, and ordered fixture
records.

`CanonicalFixtureRecord` retains local and upstream paths, filename, embedded
identity when present, producer and validator associations, measurement
contour, eligible Observatory modes, byte length, and raw SHA-256.

Identification bases are:

- `embedded_schema_identifier_and_raw_source_digest`;
- `exact_upstream_path_and_raw_source_digest`.

Schema-free fixtures therefore remain identifiable without inventing an
embedded schema.

## Trace Model

### Trace Families

| Trace family | Exact contract | Contour | Maximum eligible modes |
|---|---|---|---|
| `structured_processor_tick_trace` | `frp.structured_output.v1.7.0`, kind `demo` | structured output | A, V, T |
| `cycle_exact_reference_trace` | `frp.m15.cycle_exact_reference_trace.v1.7.0` | M15 mapping | A, V, T |
| `m15_primary_vector_trace` | `frp.m15.vector.v1`, primary vector kind | M15 mapping | A, V, T |
| `m15_per_cell_vector_trace` | `frp.m15.vector.v1`, kind `cell_trace` | M15 mapping | A, T |
| `m15_pending_route_trace` | `frp.m15.vector.v1`, kind `pending_routes` | M15 mapping | A, V |

`A` is Artifact Auditor, `V` is Ternary Transition Visualizer, and `T` is
Trace Explorer.

Display-mode eligibility requires validated source order, all
family-required collections, and a valid ternary state domain. Every trace
dataset remains eligible for Artifact Auditor.

### Trace Records

| Record | Exact responsibility |
|---|---|
| `TraceField` | one exact field, value, location, encoding, unit, aggregation, and validation links |
| `TernaryStateSnapshot` | packed, hexadecimal, human, and per-cell state representations without replacement |
| `RequestBundle` | request mask, source arrays, lane count, ordered lane records, and encoding binding |
| `TraceTelemetrySnapshot` | published heat, coherence, pressure, and related trace fields |
| `CellTraceRecord` | one source-ordered tick and cell row with optional canonical state |
| `TickRecord` | one source tick with links to scheduler, request, state, telemetry, and counter records |
| `TraceDataset` | one source-ordered normalized trace boundary |

Aggregation classifications are `instantaneous`, `current_tick`,
`cumulative`, `final_summary`, `minimum_summary`, `maximum_summary`, and
`package_aggregate`.

Ordering statuses are `validated_source_order`, `invalid_source_order`, and
`not_evaluated`. Completeness statuses are `required_collections_present` and
`required_collections_missing`.

`TraceDatasetBuilder` accepts only a registered artifact with a matching valid
audit report. It deterministically builds datasets for the five trace families
without executing source content.

## Canonical Ternary and Transition Model

The canonical domain is exactly `-1, 0, 1`. `CanonicalTernaryState` contains
`NEGATIVE = -1`, `NEUTRAL = 0`, and `POSITIVE = 1`. Display values never add a
positive sign.

Origins are `upstream_source`, `observatory_normalized`, and
`observatory_derived`.

Transition classifications are `same_state_retention`,
`polarity_to_neutral_transition`, `neutral_to_polarity_transition`,
`observed_opposite_polarity_transition`, and `unknown_transition`.

The opposite-polarity classification records an observed state pair. It does
not assert `actual_direct_events`.

Route-leg classifications are `first_leg_neutralization`,
`pending_route_completion`, `non_route_transition`, and `not_determined`.
Route-leg attribution requires published request or route evidence.

### `SourceRecordReference`

Each reference contains normalized record, source artifact, trace dataset,
registry binding, validation report, raw SHA-256, source ordinal, tick,
validation status, source locations, and exactly one schema or format
identifier.

Only `recognized_valid` and `recognized_valid_with_warnings` records can enter
visualization models.

### `TernaryStateValue` and `TransitionRecord`

`TernaryStateValue` keeps source value, source encoding, canonical state,
cell identifier, origin, encoding-map identifier, and validation links.
Normalized decoding requires an encoding-map identifier.

`TransitionRecord` keeps source and target ticks and states, classification,
route leg, request and route links, scheduler and capacity decisions, origin,
derivation information, and validation links. Derived transitions require
both a derivation record and an operation.

## Scheduler, Request, and Route Models

Scheduler modes are `free`, `7/1`, and `1/7`. Scheduler states are `free`,
`balance`, `commit`, `excite`, and `neutralize`.

`SchedulerFieldValue` keeps the source representation distinct from the
registered mode or state. Encoded normalized values require an encoding map.
`SchedulerSnapshot` requires a state and retains a mode only when published.

Request acceptance statuses are `accepted`, `rejected`, `not_recorded`, and
`not_applicable`. A published accepted or rejected decision requires a source
location. No acceptance decision is inferred when it was not published.

`RequestBundle` preserves zero-based lane order and requires its source cell
and target arrays to match the declared lane count.

Route statuses are `pending` and `applied`. A pending route requires
`ready_tick` after its source tick. An applied route cannot occur before its
`ready_tick`.

## Telemetry and Counter Models

Transition telemetry fields are `transition_fraction`, `request_lane_count`,
`current_tick_changes`, `switch_load`, `transition_capacity`,
`remaining_capacity`, `capacity_exhausted`, `scheduler_deferral`, and
`capacity_deferral`.

The model enforces:

- `0 <= transition_fraction <= 1`;
- nonnegative numeric telemetry;
- integer lane, change, capacity, and remaining-capacity values;
- Boolean exhausted and deferral values;
- `current_tick_changes <= transition_capacity`;
- `remaining_capacity <= transition_capacity`;
- `remaining_capacity = transition_capacity - current_tick_changes` when all
  three values are present;
- `capacity_exhausted = (remaining_capacity == 0)` when both are present.

Event counters remain separate: `requested_direct_events`,
`prevented_direct_events`, `neutral_routed_events`, `neutralized_conflicts`,
`actual_direct_events`, `reserved_state_events`, and `queue_overflow_events`.

Counter values are nonnegative integers. Zero remains distinct from absence.

## Invariant Vector Model

`InvariantBitRecord` preserves bit position, source form, source location,
optional registered name, published status, rule reference, and validation
links.

Supported source bit forms are Boolean, integer `0` or `1`, and string `"0"`
or `"1"`.

`InvariantVectorRecord` preserves the original representation, positive bit
count, ordered unique bit positions, qualification contour, optional bit-order
contract, optional published aggregate status, and source locations.
Registered bit names require an explicit bit-order contract. No bit meaning is
invented.

## Derived Visualizer Views

`TransitionVisualizerDataset` contains records from exactly one trace dataset
and one measurement contour. Its typed collections are state values,
transitions, scheduler snapshots, request lanes, route events, transition
telemetry, event-counter snapshots, and invariant vectors.

Every record identifier is globally unique within the dataset, and every used
source reference must appear in its retained source-reference collection.

Implemented view operations are:

- tick filter;
- cell filter;
- request-lane filter;
- scheduler-state filter;
- event-type filter;
- source-order-preserving projection;
- explicit record-ID sorting;
- canonical state-transition projection;
- trace-to-route correlation through published route links.

Every `TransitionVisualizerView` retains its source dataset, exact operation,
parameters, creation time, registry revision, source artifact IDs, normalized
record IDs, output record IDs, ordering declaration, validation links, and
the exact label `Observatory-derived view`.

Filters preserve source order. Explicit sorting records
`source_order_preserved = false`.

## Current Implementation Boundary

`TraceDatasetBuilder` does not create `TransitionRecord` collections, and no
automatic `TraceDataset` to `TransitionVisualizerDataset` projection or
invariant extraction builder is implemented. Audit-report serialization is
implemented; general trace and visualizer serialization is not yet defined.
No database, persistence layer, API protocol, or UI framework is selected.
Comparative artifacts are audited without a generic benchmark-dataset class.
M16 Markdown remains outside machine-readable trace normalization. Missing
upstream canonical trace and M15 package fixtures are not reconstructed.

## Acceptance Evidence

The current 275-test suite verifies:

- immutable source capture and raw-byte integrity;
- safe JSON and M15 vector parsing;
- exact registry dispatch;
- audit status, checks, provenance, and serializers;
- canonical fixture and deterministic package validation;
- structured-output, M3, M15, comparative, and sensitivity validators;
- trace-family construction, ordering, completeness, and mode eligibility;
- ternary state, scheduler, request, route, telemetry, counter, and invariant
  model relations;
- deterministic transition-view filters, projections, and correlations.

Passing local tests do not assign an Observatory release version or establish
the separate CI support gate.

## Prohibited Behavior

The model must not:

- mutate or replace source bytes;
- execute uploaded content or upstream producers;
- infer schema identity from filenames alone;
- convert absent data into defaults;
- rewrite canonical states or add a positive sign to `1`;
- treat encoded values as canonical without an encoding binding;
- infer accepted or rejected requests;
- infer route legs without source evidence;
- equate an observed opposite-polarity pair with a direct-event counter;
- combine scheduler state with scheduler mode;
- combine source and derived values without origin labels;
- combine measurement contours;
- convert FPGA preparation evidence into physical-chip evidence.

## Author

Maksym Marnov
