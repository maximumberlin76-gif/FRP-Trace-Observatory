# FRP Trace Observatory Normalized Read-Only Data Model

- **Model status:** Implemented and qualified through the FRP M31 published boundary
- **Audited upstream scopes:** FRP v1.8.0 / M16, immutable M30 archive, M31 publication
- **Base compatibility records:** 19
- **M30 published-member registrations:** 4
- **M30 exact mode routes:** 7
- **M31 published-document registrations:** 4
- **M31 exact mode routes:** 6
- **Current exact verification:** 655 tests, `OK`

Related contracts:

- [Integration Contract](integration_contract.md)
- [Supported Schema Registry](supported_schema_registry.md)
- [M31 Published Evidence Boundary](m31_published_boundary.md)

## Purpose

This document defines the implemented immutable data model between source
capture, parsers, exact registry resolution, Artifact Auditor, Trace Explorer,
and Ternary Transition Visualizer.

FRP remains the authority for processor semantics and published artifact
values. Observatory records preserve source values, add typed downstream
access, retain exact provenance, and identify every computed representation
as normalized or Observatory-derived.

The data model covers three connected boundaries:

1. the 19-record FRP v1.8.0 / M16 compatibility inventory;
2. the digest-bound M30 archive and its four published-member registrations;
3. the exact four-document M31 publication and its qualified projections.

## Layer Architecture

| Layer | Responsibility | Primary implementation |
|---|---|---|
| Source | Immutable bytes, paths, timestamps, and raw digests | `parsers/source_artifact.py` |
| Parsed | Safe, non-executable JSON and M15 vector representations | `parsers/json_artifact.py`, `parsers/m15_vector.py` |
| Registry | Exact identity, contour, and mode declarations | `schemas/registry.py`, `schemas/m30_published_registry.py`, `schemas/m31_published_registry.py` |
| Dispatch | Exact source-to-registration and registration-to-mode binding | `parsers/artifact_dispatch.py`, `parsers/m30_published_dispatch.py`, `parsers/m31_published_dispatch.py` |
| Audit | Ordered validation checks and deterministic aggregate status | `artifact_auditor/` |
| Trace | Source-ordered normalized trace records and datasets | `trace_explorer/` |
| Visualizer | Source-linked transition, route, scheduler, telemetry, invariant, and thermal views | `transition_visualizer/` |

The processing relation is:

```
source bytes
    → immutable source artifact
    → safe parsed artifact
    → exact registry binding
    → exact mode dispatch
    → immutable audit result
    → source-linked trace dataset
    → source-linked visualizer dataset
```

Every downstream layer retains the identity of its immediate authority and
the source boundary from which it was constructed.

## Base Module Boundary

| Layer | Exact implementation | Primary records |
|---|---|---|
| Source capture | `parsers/source_artifact.py` | `RawSourceDigest`, `SourceArtifact` |
| JSON parsing | `parsers/json_artifact.py` | `ParsedJsonArtifact` |
| M15 vector parsing | `parsers/m15_vector.py` | `M15VectorMetadataEntry`, `M15VectorRow`, `M15VectorArtifact` |
| Base registry | `schemas/registry.py` | `CompatibilityRecord` |
| Base dispatch | `parsers/artifact_dispatch.py` | `RegistrationResult`, `DispatchedArtifact` |
| Audit reporting | `artifact_auditor/audit_report.py` | `AuditValueSnapshot`, `SourceLocation`, `ValidationCheck`, `AuditReport` |
| Audit execution | `artifact_auditor/validation_core.py`, `artifact_auditor/auditor.py` | `ValidationCheckSpec`, ordered report construction |
| Fixture provenance | `artifact_auditor/fixture_manifest.py` | `RawDigestContract`, `CanonicalFixtureRecord`, `CanonicalFixtureManifest` |
| Trace normalization | `trace_explorer/trace_model.py` | `TraceField`, `TickRecord`, `CellTraceRecord`, `TraceDataset` |
| Trace construction | `trace_explorer/trace_builder.py` | `TraceDatasetBuilder` |
| Transition records | `transition_visualizer/*.py` | state, scheduler, request, route, telemetry, counter, and invariant records |
| Derived views | `transition_visualizer/view_model.py`, `transition_visualizer/view_builder.py` | `TransitionVisualizerDataset`, `TransitionVisualizerView` |

Base provenance and normalized-artifact responsibilities are represented by
the exact records above rather than a separate generic persistence object.

## M30 Module Boundary

| Stage | Exact implementation | Primary records |
|---|---|---|
| Archive intake | `artifact_auditor/m30_archive_intake.py` | `M30ArchiveMember`, `RetainedArchiveMember`, `M30ArchiveValidation` |
| Publication boundary | `artifact_auditor/m30_published_boundary_intake.py` | `PublishedBoundaryDocument`, `PublishedDemoMember`, `PublishedBoundaryValidation` |
| Member registry | `schemas/m30_published_registry.py` | `PublishedMemberRegistration`, `PublishedModeRoute`, `PublishedRegistryValidation` |
| Member intake | `parsers/m30_published_member_intake.py` | `PublishedIdentifierEvidence`, `PublishedMemberIntake`, `PublishedMemberIntakeBatch` |
| Mode dispatch | `parsers/m30_published_dispatch.py` | `PublishedModeDispatch`, `PublishedDispatchBatch` |
| Artifact Auditor | `artifact_auditor/m30_published_auditor.py` | `PublishedAuditReport`, `PublishedAuditBatch` |
| Trace Explorer | `trace_explorer/m30_published_trace_explorer.py` | `PublishedTraceRequest`, `PublishedSchedulerTrace`, `PublishedTraceCell`, `PublishedTraceRecord`, `PublishedExecutionEpoch`, `M30PublishedTraceDataset` |
| Transition Visualizer | `transition_visualizer/m30_published_transition_visualizer.py` | `PublishedCoreTraceSource`, `M30FullCoreTraceEvidence`, `PublishedTransitionFrame`, `PublishedTelemetrySemantic`, `M30PublishedTransitionVisualizerDataset` |

## M31 Module Boundary

| Stage | Exact implementation | Primary records |
|---|---|---|
| Publication intake | `artifact_auditor/m31_published_boundary_intake.py` | `M31PublishedDocumentIdentity`, `M31PublishedDocument`, `M31PublishedProvenanceSource`, `M31PublishedBoundaryValidation` |
| Document registry | `schemas/m31_published_registry.py` | `M31PublishedDocumentRegistration`, `M31PublishedModeRoute`, `M31PublishedRegistryValidation` |
| Mode dispatch | `parsers/m31_published_dispatch.py` | `M31PublishedDocumentDispatch`, `M31PublishedDispatchBatch` |
| Artifact Auditor | `artifact_auditor/m31_published_auditor.py` | `M31PublishedAuditReport`, `M31PublishedAuditBatch` |
| Trace Explorer | `trace_explorer/m31_published_trace_explorer.py` | `M31PublishedTraceRequest`, `M31PublishedSchedulerTrace`, `M31PublishedTraceCell`, `M31PublishedTraceRecord`, `M31PublishedExecutionEpoch`, `M31PublishedTraceContour`, `M31PublishedTraceDataset` |
| Transition Visualizer | `transition_visualizer/m31_published_transition_visualizer.py` | `M31PublishedCoreDeclaration`, `M31PublishedTransitionFrame`, `M31PublishedThermalContour`, `M31PublishedTransitionVisualizerDataset` |

All public M30 and M31 records listed above are frozen, slotted dataclasses.

## Global Invariants

1. Captured source bytes remain unchanged.
2. Raw SHA-256 is calculated over captured bytes before parsing.
3. Public records are frozen, slotted dataclasses.
4. Parsed arrays use tuples and parsed JSON objects use immutable mappings.
5. Source order is retained unless a derived view explicitly records sorting.
6. Integer, `Decimal`, Boolean, string, null, and absence remain distinct.
7. A missing field is not replaced with zero, false, null, or an empty value.
8. Every normalized source record retains source, registry, audit, digest,
   ordinal, and source-location provenance applicable to its contour.
9. Encoded states remain separate from canonical states.
10. The canonical processor state domain is displayed as `-1/0/1`.
11. State `0` remains the published active computational neutral state.
12. Opposite-polarity routes remain `-1 → 0 → 1` and `1 → 0 → -1`.
13. Scheduler mode and scheduler state remain distinct values.
14. Measurement contours remain distinct.
15. Validation output remains separate from source values.
16. Derived values require explicit origin and derivation identity.
17. M30 archive members remain bound to the verified archive identity.
18. M31 documents remain bound to exact path, identifier, length, and digest.
19. Mode eligibility comes only from the exact registration.
20. Artifact content and producer commands are processed as data.

## Identity Chains

### Base compatibility identity

1. `SourceArtifact.source_artifact_id` identifies one source load.
2. `RawSourceDigest.digest_record_id` identifies its raw digest record.
3. `CompatibilityRecord` supplies the exact registered contract.
4. `AuditReport.registry_binding_id` binds the load to a registry revision and
   compatibility record.
5. `TraceDataset.trace_dataset_id` identifies one normalized trace dataset.
6. `TraceDataset.normalized_artifact_id` identifies its normalization result.
7. `SourceRecordReference.normalized_record_id` identifies one normalized
   source record.
8. Typed state, transition, scheduler, request, route, telemetry, counter, and
   invariant records receive their own UUID identifiers.
9. `TransitionVisualizerView.derived_view_id` identifies one derived view.

Loading identical bytes twice creates separate load identities. The loads may
share raw SHA-256 while retaining separate timestamps and provenance.

### M30 publication identity

```
M30ArchiveValidation
    → PublishedBoundaryValidation
    → PublishedRegistryValidation
    → PublishedMemberIntakeBatch
    → PublishedDispatchBatch
    → PublishedAuditBatch
    → M30PublishedTraceDataset
    → M30PublishedTransitionVisualizerDataset
```

The archive SHA-256 anchors every M30 stage. A registered member additionally
retains its exact member id, source path, schema identifier, byte length,
member SHA-256, upstream release, compatibility key, and mode route.

### M31 publication identity

```
M31PublishedBoundaryValidation
    → M31PublishedRegistryValidation
    → M31PublishedDispatchBatch
    → M31PublishedAuditBatch
    → M31PublishedTraceDataset
    → M31PublishedTransitionVisualizerDataset
```

Each M31 document retains one canonical role. The role selects exactly one
identity record, registration, contour, and eligible mode tuple. Every
dispatch binds the complete registry validation, exact document object,
canonical route object, and deterministic dispatch SHA-256.

## Value and Ordering Rules

`ParsedJsonArtifact` preserves JSON values as `None`, `bool`, `int`, finite
`Decimal`, `str`, nested tuples, and immutable string-key mappings.

The JSON parser rejects duplicate object keys, non-finite numbers, invalid
UTF-8, invalid JSON syntax, array roots, unescaped control characters, and
excessive nesting.

Source order is retained for:

- JSON arrays;
- M15 metadata declarations;
- vector rows and columns;
- processor records and ticks;
- execution contours and epochs;
- per-cell snapshots;
- request lanes;
- pending-route records;
- invariant bits and names;
- audit checks;
- M30 archive and manifest inventories;
- M31 publication and provenance inventories;
- transition frames and thermal contours.

Object-key order is retained by parsed mappings and receives processor meaning
only when the exact upstream contract defines it.

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
accepts regular files and applies the repository path and symbolic-link
guards before reading bytes.

## Parsed Artifact Model

### `ParsedJsonArtifact`

Fields are `source_artifact`, immutable `root`, `text_encoding`,
`declared_schema_identifier`, and `declared_kind`.

Supported encodings are `utf-8` and `utf-8-sig`. Declared schema and kind are
retained only when their exact root values are strings. Other declared values
remain unchanged in the parsed root and are evaluated as identity failures by
dispatch.

### `M15VectorArtifact`

| Record | Exact fields |
|---|---|
| `M15VectorMetadataEntry` | `key`, `raw_json`, `value`, `line_number` |
| `M15VectorRow` | `line_number`, ordered `fields` |
| `M15VectorArtifact` | `source_artifact`, `metadata_entries`, `column_header_line_number`, `columns`, `rows`, `text_encoding`, `format_identifier`, `declared_trace_kind` |

Recognized trace kinds are:

- `kernel_transition_vectors`;
- `pending_routes`;
- `scheduler_free_vectors`;
- `scheduler_7_1_vectors`;
- `scheduler_1_7_vectors`;
- `full_correlation_vectors`;
- `cell_trace`.

The parser preserves metadata order, raw metadata JSON, row line numbers,
column order, row field text, and optional UTF-8 BOM detection.

## Base Registry and Dispatch Model

### `CompatibilityRecord`

Fields are `identifier`, `identifier_field`, `schema_version`,
`artifact_format`, `artifact_kind`, `measurement_contour`, `producer_path`,
`producer_version`, `evidence_kind`, `evidence_path`,
`canonical_fixture_path`, `observatory_modes`, and `upstream_release`.

Identity fields are `schema` and `format_version`. Artifact formats are `json`
and `frp_m15_vector_text`.

### `RegistrationResult`

Registration statuses are:

- `registered`;
- `missing_identifier`;
- `invalid_identifier`;
- `unknown_identifier`;
- `unsupported_kind`;
- `not_applicable`.

The record retains the identifier field, declared identifier, declared kind,
matched compatibility record, and exact expected kinds when applicable.

### `DispatchedArtifact`

Fields are `source_artifact`, `classification`, `parsed_artifact`, and
`registration`.

Classifications are `empty`, `json`, `m15_vector`, `utf8_text`, `zip`, and
`binary`. Parser errors remain parser errors. Only a verified parsed artifact
can receive a registered compatibility result.

## Base Audit Model

### Validation Enumerations

Overall statuses are `recognized_valid`,
`recognized_valid_with_warnings`, `recognized_invalid`,
`known_unsupported`, `unrecognized`, and `incomplete_package`.

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

Recognized status requires exact registry association. Incomplete-package
status requires explicit missing members. Report origin is
`observatory_derived`.

Audit reports serialize to immutable mappings, deterministic compact JSON,
and plain text. The serializers omit source bytes.

## Canonical Fixture Model

`CanonicalFixtureManifest` retains its captured source and parsed JSON,
manifest identity, upstream repository, release, milestone, ordering rule,
fixture count, raw digest contract, copy requirement, and ordered fixture
records.

`CanonicalFixtureRecord` retains local and upstream paths, filename, embedded
identity when present, producer and validator associations, measurement
contour, eligible Observatory modes, byte length, and raw SHA-256.

Identification bases are:

- `embedded_schema_identifier_and_raw_source_digest`;
- `exact_upstream_path_and_raw_source_digest`.

Schema-free fixtures remain identifiable through exact path and raw digest
without adding an embedded schema.

## Base Trace Model

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

Display-mode eligibility requires validated source order, all required trace
collections, and a valid ternary state domain. Every trace dataset remains
eligible for Artifact Auditor.

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
`not_evaluated`. Completeness statuses are
`required_collections_present` and `required_collections_missing`.

`TraceDatasetBuilder` accepts a registered artifact with a matching valid
audit report and deterministically builds the five trace families.

## Canonical Ternary and Transition Model

The canonical state domain is:

```
S = {-1, 0, 1}
```

`CanonicalTernaryState` contains `NEGATIVE = -1`, `NEUTRAL = 0`, and
`POSITIVE = 1`.

State `0` is active. It mediates the published opposite-polarity routes:

```
-1 → 0 → 1
 1 → 0 → -1
```

Origins are `upstream_source`, `observatory_normalized`, and
`observatory_derived`.

Base transition classifications are:

- `same_state_retention`;
- `polarity_to_neutral_transition`;
- `neutral_to_polarity_transition`;
- `observed_opposite_polarity_transition`;
- `unknown_transition`.

Base route-leg classifications are:

- `first_leg_neutralization`;
- `pending_route_completion`;
- `non_route_transition`;
- `not_determined`.

Route-leg attribution requires published request or route evidence.

### `SourceRecordReference`

Each reference contains normalized record, source artifact, trace dataset,
registry binding, validation report, raw SHA-256, source ordinal, tick,
validation status, source locations, and exactly one schema or format
identifier.

Only `recognized_valid` and `recognized_valid_with_warnings` records can enter
base visualization models.

### `TernaryStateValue` and `TransitionRecord`

`TernaryStateValue` keeps source value, source encoding, canonical state,
cell identifier, origin, encoding-map identifier, and validation links.
Normalized decoding requires an encoding-map identifier.

`TransitionRecord` keeps source and target ticks and states, classification,
route leg, request and route links, scheduler and capacity decisions, origin,
derivation information, and validation links. Derived transitions require a
derivation record and operation.

## Scheduler, Request, and Route Models

Scheduler modes are `free`, `7/1`, and `1/7`. Scheduler states are `free`,
`balance`, `commit`, `excite`, and `neutralize`.

`SchedulerFieldValue` keeps the source representation distinct from the
registered mode or state. Encoded normalized values require an encoding map.
`SchedulerSnapshot` requires a state and retains a mode when published.

Request acceptance statuses are `accepted`, `rejected`, `not_recorded`, and
`not_applicable`. A published accepted or rejected decision requires a source
location. An absent decision remains `not_recorded`.

`RequestBundle` preserves zero-based lane order and requires its source cell
and target arrays to match the declared lane count.

Route statuses are `pending` and `applied`. A pending route requires
`ready_tick` after its source tick. An applied route occurs at or after its
`ready_tick`.

## Telemetry and Counter Models

Transition telemetry fields are:

- `transition_fraction`;
- `request_lane_count`;
- `current_tick_changes`;
- `switch_load`;
- `transition_capacity`;
- `remaining_capacity`;
- `capacity_exhausted`;
- `scheduler_deferral`;
- `capacity_deferral`.

The model enforces:

- `0 <= transition_fraction <= 1`;
- nonnegative numeric telemetry;
- integer lane, change, capacity, and remaining-capacity values;
- Boolean exhausted and deferral values;
- `current_tick_changes <= transition_capacity`;
- `remaining_capacity <= transition_capacity`;
- `remaining_capacity = transition_capacity - current_tick_changes` when all
  three fields are present;
- `capacity_exhausted = (remaining_capacity == 0)` when both fields are
  present.

Event counters remain separate:

- `requested_direct_events`;
- `prevented_direct_events`;
- `neutral_routed_events`;
- `neutralized_conflicts`;
- `actual_direct_events`;
- `reserved_state_events`;
- `queue_overflow_events`.

Counter values are nonnegative integers. Zero remains distinct from absence.

## Invariant Vector Model

`InvariantBitRecord` preserves bit position, source form, source location,
optional registered name, published status, rule reference, and validation
links.

Supported source bit forms are Boolean, integer `0` or `1`, and string `"0"`
or `"1"`.

`InvariantVectorRecord` preserves the original representation, positive bit
count, ordered unique bit positions, qualification contour, optional
bit-order contract, optional published aggregate status, and source
locations. Registered bit names require an explicit bit-order contract.

## Derived Base Visualizer Views

`TransitionVisualizerDataset` contains records from exactly one trace dataset
and one measurement contour. Its typed collections are state values,
transitions, scheduler snapshots, request lanes, route events, transition
telemetry, event-counter snapshots, and invariant vectors.

Every record identifier is globally unique within the dataset. Every used
source reference appears in its retained source-reference collection.

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

## M30 Archive Data Model

### Archive records

| Record | Exact fields |
|---|---|
| `M30ArchiveMember` | `path`, `byte_length`, `raw_sha256` |
| `RetainedArchiveMember` | `member`, `raw_bytes` |
| `M30ArchiveValidation` | `archive_sha256`, `archive_byte_length`, `release_root`, `source_commit`, `members`, `retained_members` |

`M30ArchiveValidation` represents the exact 10,189,989-byte M30 archive with
SHA-256
`05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa`,
release root `Fractal-Resonance-Processor-FRP-v3.2.0`, source commit
`ff3dd434da5dcbd9e8fa62444f658ed4c495b540`, 519 archive entries, and
518 manifested source members.

`members` is the complete immutable manifest inventory.
`retained_members` contains only the exact byte payloads required by the
current downstream contour.

### Published-boundary records

| Record | Exact fields |
|---|---|
| `PublishedBoundaryDocument` | `path`, `schema`, `kind`, `raw_sha256`, `byte_length` |
| `PublishedDemoMember` | `member_id`, `source_path`, `schema_identifier`, `observatory_modes`, `raw_sha256`, `byte_length` |
| `PublishedBoundaryValidation` | `archive_sha256`, `documents`, `supported_artifact_count`, `demo_members`, `accepted_vector_count`, `rejected_vector_count` |

The archive SHA-256 in `PublishedBoundaryValidation` must equal the archive
intake identity. Demo-member records remain immutable projections of exact
archive members.

## M30 Registry, Intake, and Dispatch Model

### `PublishedMemberRegistration`

Fields are `member_id`, `source_path`, `schema_identifier`,
`measurement_contour`, `observatory_modes`, `byte_length`, `raw_sha256`,
`compatibility_key`, and `upstream_release`.

Measurement contours are:

- `m16_fpga_preparation_execution`;
- `m27_long_run_telemetry_semantics`;
- `m28_upstream_integration_contract`;
- `m28_hierarchical_scaling_qualification`.

The compatibility key is the SHA-256 of canonical JSON containing exact
`member_id`, `schema_identifier`, and `raw_sha256`.

### `PublishedRegistryValidation`

Fields are `archive_sha256`, `registry_revision`, `registrations`, `routes`,
`artifact_auditor_route_count`,
`ternary_transition_visualizer_route_count`, and
`trace_explorer_route_count`.

### `PublishedModeRoute`

Fields are `registration` and `mode`. The route retains the canonical
registration object. Four registrations produce seven exact routes:

- Artifact Auditor: 4;
- Trace Explorer: 1;
- Ternary Transition Visualizer: 2.

### Member intake

`PublishedIdentifierBinding` values are `schema_field` and
`artifact_id_schema_version_fields`.

| Record | Exact fields |
|---|---|
| `PublishedIdentifierEvidence` | `field_name`, `value` |
| `PublishedMemberIntake` | `archive_sha256`, `registry_revision`, `registration`, `routes`, `retained_member`, `source_artifact`, `parsed_artifact`, `identifier_binding`, `identifier_evidence` |
| `PublishedMemberIntakeBatch` | `archive_validation`, `registry_validation`, `members` |

The retained archive bytes, captured `SourceArtifact`, parsed JSON, exact
registration, and exact routes remain connected by object identity and digest
checks.

### Mode dispatch

| Record | Exact fields |
|---|---|
| `PublishedModeDispatch` | `member`, `route`, `dispatch_sha256` |
| `PublishedDispatchBatch` | `intake_batch`, `dispatches` |

Each dispatch represents one registered member-to-mode route. Its SHA-256
binds the exact source and canonical route.

## M30 Audit Data Model

### `PublishedAuditReport`

Fields are `audit_report_id`, `dispatch`, `measurement_contour`, `checks`,
`overall_status`, and `report_sha256`.

### `PublishedAuditBatch`

Fields are `dispatch_batch`, `reports`, `overall_status`, and `batch_sha256`.

The qualified M30 batch contains four reports, 69 ordered checks, zero failed
checks, and batch SHA-256:

```
aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03
```

Reports remain keyed by member and share the exact dispatch objects from the
batch.

## M30 Trace Explorer Data Model

### Source-linked trace records

| Record | Exact fields |
|---|---|
| `PublishedTraceRequest` | `lane`, `valid`, `cell_index`, `target_state`, `accepted`, `rejected` |
| `PublishedSchedulerTrace` | `mode`, `state`, `ticks_before`, `ticks_after`, `counters_after` |
| `PublishedTraceCell` | `cell_id`, `phase_derived_target`, `retained_state_before`, `retained_state_after`, `pending_route_before`, `pending_route_after`, `accepted`, `accepted_change`, `neutral_routed` |
| `PublishedTraceRecord` | complete source-linked processor record defined below |
| `PublishedExecutionEpoch` | `epoch`, `mode`, `record_count`, `source_location` |

`M30PublishedTraceDataset` fields are `trace_dataset_id`, `audit_batch`,
`audit_report`, `dispatch`, `measurement_contour`, `epochs`, `records`,
`source_record_digest`, `m15_correlation_status`,
`physical_measurement_availability`,
`physical_measurement_correlation_status`, and `dataset_sha256`.

`PublishedTraceRecord` fields are `trace_record_id`, `sequence`,
`execution_epoch`, `core_ready`, `scheduler`, `requests`, `cells`,
`accepted_cell_ids`, `accepted_change_cell_ids`, `neutral_routed_cell_ids`,
`capacity_limit`, `accepted_changes`, `capacity_remaining`,
`capacity_exhausted`, `switch_load_numerator`, `switch_load_denominator`,
`switch_load_q16`, `event_counts`, `invariant_names`, `invariant_all_pass`,
`source_location`, and `source_record_sha256`.

Qualified cardinality and identity:

| Property | Exact value |
|---|---|
| Trace dataset id | `4191b36e-9168-5fc7-a4b5-cbc3b480136f` |
| Records | 4 |
| Cell snapshots | 32 |
| Request records | 8 |
| Source-record digest | `4b2e8aec64a0b3cb76d0819383ed66d306b8e50dc3feb7bb8c6c76486cd83d57` |
| Dataset SHA-256 | `4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd` |

Every projected trace record round-trips to its exact source JSON record.

## M30 Transition Visualizer Data Model

### Full-core source records

| Record | Exact fields |
|---|---|
| `PublishedCoreTraceSource` | `trace_source_id`, `dataset_id`, `retained_member`, `parsed_artifact`, `epochs`, `records`, `source_record_digest` |
| `M30FullCoreTraceEvidence` | `evidence_id`, `archive_validation`, `canonical_bundle`, `fixture_manifest`, `trace_sources`, `evidence_sha256` |

The full-core evidence retains separate RTL and FPGA-preparation sources:

| Dataset id | Contour | Records |
|---|---|---:|
| `m16-rtl-execution` | `m16_rtl_execution` | 96 |
| `m16-fpga-preparation-execution` | `m16_fpga_preparation_execution` | 4 |

Evidence identity:

| Property | Exact value |
|---|---|
| Evidence id | `7c935011-c734-5f6b-b312-dc476ad99724` |
| Evidence SHA-256 | `b481d787fdef17992ed3236b4a7b1b142634b944ebb0048f4b77d3def089edd2` |

### `PublishedTransitionFrame`

Fields are `transition_frame_id`, `route_authority_sha256`,
`trace_source_id`, `source_dataset_id`, `source_path`, `source_trace_sha256`,
`measurement_contour`, `trace_record_id`, `source_record_sha256`, `sequence`,
`execution_epoch`, `scheduler_mode`, `scheduler_state`, `cell_id`,
`phase_derived_target`, `retained_state_before`, `retained_state_after`,
`pending_route_before`, `pending_route_after`, `accepted`, `accepted_change`,
`neutral_routed`, `transition_classification`, `route_leg`, `source_location`,
and `frame_sha256`.

M30 classifications are `same_state_retention`,
`polarity_to_neutral_transition`, and `neutral_to_polarity_transition`.
Route legs are `non_route_transition`, `first_leg_neutralization`, and
`pending_route_completion`.

### `PublishedTelemetrySemantic`

Fields are `semantic_record_id`, `visualizer_dispatch_sha256`, `ordinal`,
`telemetry_id`, `classification`, `domain_minimum`, `domain_maximum`,
`relation`, `storage_type`, `source_location`, and `source_record_sha256`.

### `M30PublishedTransitionVisualizerDataset`

Fields are `visualizer_dataset_id`, `audit_batch`, `trace_dataset`,
`full_core_evidence`, `m16_audit_report`, `m27_audit_report`, `m16_dispatch`,
`m27_dispatch`, `transition_frames`, `telemetry_semantics`,
`validated_relations`, `interpretation_boundary`, `semantics_digest`, and
`dataset_sha256`.

Qualified cardinality and identity:

| Property | Exact value |
|---|---|
| Trace records | 100 |
| Transition frames | 800 |
| `same_state_retention` | 783 |
| `polarity_to_neutral_transition` | 5 |
| `neutral_to_polarity_transition` | 12 |
| `non_route_transition` | 790 |
| `first_leg_neutralization` | 5 |
| `pending_route_completion` | 5 |
| Visualizer dataset id | `68de3476-2e03-5506-93ea-062c3744e90d` |
| Dataset SHA-256 | `7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b` |

## M31 Publication Intake Data Model

### `M31PublishedDocumentIdentity`

Fields are `role`, `source_path`, `identifier_field`, `identifier_value`,
`kind`, `byte_length`, and `raw_sha256`.

Canonical roles are:

- `formal_schema`;
- `evidence`;
- `manifest`;
- `qualification`.

Exactly one immutable identity exists for each role.

### Published document and provenance records

| Record | Exact fields |
|---|---|
| `M31PublishedDocument` | `identity`, `source_artifact`, `parsed_artifact` |
| `M31PublishedProvenanceSource` | `source_artifact`, `m30_archive_member_verified`, `role` |
| `M31PublishedBoundaryValidation` | `registry_revision`, `loaded_at`, `documents`, `provenance_sources`, `m30_archive_sha256`, `m30_archive_member_count` |

The boundary contains four documents and 12 provenance sources. Ten
historical provenance sources are verified as members of the immutable M30
archive. The M30 archive container and post-archive qualification workflow
retain separate provenance roles.

The M31 boundary retains the exact M30 archive SHA-256 and
`m30_archive_member_count = 10` for the verified historical provenance
members used by the publication.

## M31 Registry and Dispatch Data Model

### `M31PublishedDocumentRegistration`

Fields are `document_identity`, `measurement_contour`, `observatory_modes`,
`compatibility_key`, `upstream_milestone`, and `upstream_version`.

Measurement contours are:

- `formal_schema_definition`;
- `phase_interference_active_zero_thermal_evidence`;
- `publication_manifest`;
- `publication_qualification`.

The formal schema, manifest, and qualification registrations route to Artifact
Auditor. The evidence registration routes to Artifact Auditor, Trace Explorer,
and Ternary Transition Visualizer. Four registrations therefore produce six
exact routes.

The compatibility key is the SHA-256 of canonical JSON containing exact
`role`, `identifier_field`, `identifier_value`, and `raw_sha256`.

### Registry and dispatch records

| Record | Exact fields |
|---|---|
| `M31PublishedModeRoute` | `registration`, `mode` |
| `M31PublishedRegistryValidation` | `boundary`, `registry_revision`, `registrations`, `routes`, `artifact_auditor_route_count`, `ternary_transition_visualizer_route_count`, `trace_explorer_route_count` |
| `M31PublishedDocumentDispatch` | `registry_validation`, `document`, `route`, `dispatch_sha256` |
| `M31PublishedDispatchBatch` | `registry_validation`, `dispatches` |

Each route and dispatch retains the canonical registration and document
objects. Reconstructed equivalents do not replace those canonical objects.

## M31 Audit Data Model

### `M31PublishedAuditReport`

Fields are `audit_report_id`, `dispatch`, `measurement_contour`, `checks`,
`overall_status`, and `report_sha256`.

### `M31PublishedAuditBatch`

Fields are `dispatch_batch`, `reports`, `overall_status`, and `batch_sha256`.

Qualified report inventory:

| Role | Checks | Status | Report SHA-256 |
|---|---:|---|---|
| Formal schema | 11 | `recognized_valid` | `5f18fd174e02f19adcac1809624a2c205b94ae6c226e05a20eaac4f896c6bb36` |
| Evidence | 16 | `recognized_valid` | `e7c6163954973aa60994d2fa76f6f7edfdc6429fcbb397cf7e403a4e64f2f130` |
| Manifest | 10 | `recognized_valid` | `e0ef32073524cd41ea2cf0b7b273ef3c63c61080e5ff72ae9e5432a81609d652` |
| Qualification | 10 | `recognized_valid` | `5374a6b6e0def38ae5a50bb216c9be0396f6139f4a07e982b47e86b719414b53` |

The batch contains 47 ordered checks, zero failed checks, and SHA-256:

```
3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591
```

## M31 Trace Explorer Data Model

### Per-record types

| Record | Exact fields |
|---|---|
| `M31PublishedTraceRequest` | `lane`, `valid`, `cell_index`, `target_state`, `accepted`, `rejected` |
| `M31PublishedSchedulerTrace` | `mode`, `state`, `ticks_before`, `ticks_after`, `counters_after` |
| `M31PublishedTraceCell` | `cell_id`, `phase_derived_target`, `retained_state_before`, `retained_state_after`, `pending_route_before`, `pending_route_after`, `accepted`, `accepted_change`, `neutral_routed` |
| `M31PublishedTraceRecord` | complete source-linked processor record defined below |
| `M31PublishedExecutionEpoch` | `contour_index`, `epoch`, `mode`, `record_count`, `source_location` |

`M31PublishedTraceRecord` fields are `trace_record_id`, `contour_index`,
`sequence`, `execution_epoch`, `core_ready`, `scheduler`, `requests`, `cells`,
`accepted_cell_ids`, `accepted_change_cell_ids`, `neutral_routed_cell_ids`,
`capacity_limit`, `accepted_changes`, `capacity_remaining`,
`capacity_exhausted`, `switch_load_numerator`, `switch_load_denominator`,
`switch_load_q16`, `event_counts`, `invariant_names`, `invariant_all_pass`,
`source_location`, and `source_record_sha256`.

### `M31PublishedTraceContour`

Fields are `trace_contour_id`, `trace_dispatch_sha256`, `contour_index`,
`provenance_source`, `parsed_artifact`, `source_path`, `raw_sha256`,
`schema_identifier`, `trace_kind`, `layer`, `epochs`, `records`,
`source_record_digest`, `m15_correlation_status`,
`physical_measurement_availability`,
`physical_measurement_correlation_status`, and `contour_sha256`.

The dataset retains two distinct source contours:

| Index | Layer | Source path | Records | Trace contour id | Contour SHA-256 |
|---:|---|---|---:|---|---|
| 0 | `rtl` | `artifacts/m19/execution/m16-rtl-execution-trace.json` | 96 | `ee01676e-76f9-5197-9ed9-e80d9b5187a1` | `23a0af37356389dc6ffd4ab2bac4a0cf64a418583ed43195b44193dacc3c4600` |
| 1 | `fpga_preparation` | `artifacts/m19/execution/m16-fpga-preparation-execution-trace.json` | 4 | `9bc92fca-0db1-57ae-8951-398a7f059336` | `3e06ba60c8fb3bab08eabd83b9a3d83dee0176c6a682bb2825d2bba9d62dee94` |

### `M31PublishedTraceDataset`

Fields are `trace_dataset_id`, `audit_batch`, `audit_report`, `dispatch`,
`measurement_contour`, `contours`, `active_zero_roles`,
`published_event_totals`, `published_transition_totals`,
`published_scheduler_mode_counts`, `published_scheduler_state_counts`, and
`dataset_sha256`.

Qualified cardinality and identity:

| Property | Exact value |
|---|---|
| Trace dataset id | `0f0f0f7e-0409-5e7b-8c76-2f72bb954321` |
| Source contours | 2 |
| Trace records | 100 |
| Cell snapshots | 800 |
| Request records | 200 |
| Invariant-pass records | 100 |
| Retained active-zero observations | 702 |
| Dataset SHA-256 | `ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff` |

Published event totals are:

| Event | Count |
|---|---:|
| `actual_direct_events` | 0 |
| `neutral_routed_events` | 5 |
| `prevented_direct_events` | 5 |
| `queue_overflow_events` | 0 |
| `requested_direct_events` | 5 |
| `reserved_state_events` | 0 |

Published scheduler counts are:

| Type | Value | Count |
|---|---|---:|
| Mode | `free` | 19 |
| Mode | `7/1` | 64 |
| Mode | `1/7` | 17 |
| State | `balance` | 56 |
| State | `commit` | 8 |
| State | `excite` | 3 |
| State | `free` | 19 |
| State | `neutralize` | 14 |

The exact active-zero role tuple is:

1. `conflict_neutralization`;
2. `temporal_separation`;
3. `balancing`;
4. `damping`;
5. `transition_buffering`;
6. `switching_load_distribution`;
7. `retained_transition_continuity`;
8. `pending_route_completion_preparation`;
9. `stabilization`.

## M31 Core Declaration Model

`M31PublishedCoreDeclaration` fields are:

- `core_declaration_id`;
- `processor`;
- `balanced_ternary_notation`;
- `semantic_values`;
- `active_neutral_state`;
- `zero_role`;
- `classical_bit_addition_primary_mechanism`;
- `primary_computational_organization`;
- `computation_chain`;
- `ternary_layer_role`;
- `service_scheduler_mode`;
- `temporal_scheduler_modes`;
- `opposite_transition_routes`;
- `source_location`;
- `source_record_sha256`.

Exact declaration values:

| Field | Exact value |
|---|---|
| `processor` | `Fractal Resonance Processor` |
| `balanced_ternary_notation` | `-1/0/1` |
| `semantic_values` | `(-1, 0, 1)` |
| `active_neutral_state` | `0` |
| `zero_role` | `active_computational_state` |
| `classical_bit_addition_primary_mechanism` | `false` |
| `primary_computational_organization` | `retained_relative_phase_interference_and_resonant_selection` |
| `ternary_layer_role` | `discrete_state_target_transition_and_retained_result_boundary` |
| `service_scheduler_mode` | `free` |
| `temporal_scheduler_modes` | `1/7`, `7/1` |
| `opposite_transition_routes` | `(-1, 0, 1)`, `(1, 0, -1)` |

The computation chain is:

1. retained phase and frequency state;
2. relative-phase interaction;
3. phase organization and dispersion;
4. resonance selection;
5. multiscale coherence evaluation;
6. dynamic stability evaluation;
7. phase-derived ternary target;
8. distributed active-neutral commit;
9. retained coherent ternary state.

Deterministic core identity:

| Property | Exact value |
|---|---|
| Core declaration id | `32490746-831a-5667-9b11-27d6673cf893` |
| Source JSON path | `$.core` |
| Source-record SHA-256 | `05c98cfb19ec7ef85f0fab47bf80e2c2330e4595255411d366269a511b5c0b9a` |

## M31 Transition Visualizer Data Model

### `M31PublishedTransitionFrame`

Fields are `transition_frame_id`, `visualizer_dispatch_sha256`,
`trace_dataset_id`, `trace_dataset_sha256`, `trace_contour_id`,
`trace_contour_sha256`, `contour_index`, `measurement_contour`, `source_path`,
`source_trace_sha256`, `trace_record_id`, `source_record_sha256`, `sequence`,
`execution_epoch`, `scheduler_mode`, `scheduler_state`, `cell_id`,
`phase_derived_target`, `retained_state_before`, `retained_state_after`,
`pending_route_before`, `pending_route_after`, `accepted`, `accepted_change`,
`neutral_routed`, `transition_classification`, `route_leg`, `source_location`,
and `frame_sha256`.

M31 transition inventory:

| Classification | Count |
|---|---:|
| `active_zero_to_polarity` | 12 |
| `direct_opposite` | 0 |
| `polarity_to_active_zero` | 5 |
| `retained_same` | 783 |

M31 route-leg inventory:

| Route leg | Count |
|---|---:|
| `non_route_transition` | 790 |
| `first_leg_to_active_zero` | 5 |
| `pending_route_completion` | 5 |

The frame inventory contains 800 unique frame ids and 800 unique frame
SHA-256 values. Contour 0 contributes 768 frames; contour 1 contributes 32.

### `M31PublishedThermalContour`

Fields are `thermal_contour_id`, `visualizer_dispatch_sha256`,
`contour_name`, `contour_group`, `source_json_path`, `measurement_class`,
`physical_temperature_measurement`, `payload_json`, `payload_sha256`, and
`source_location`.

The four records remain separate:

| Contour | Group | Source JSON path | Measurement class | Payload SHA-256 |
|---|---|---|---|---|
| `historical_release_benchmark` | `historical` | `$.historical_thermal_experiment` | `release_specific_model_thermal_load` | `8ae48a85c971d6fe8d136fd08b45ac7d801c6146c82eab2ac785c4e8318cb140` |
| `current_comparative_baseline` | `current` | `$.current_comparative_thermal_contours.baseline` | `shared_model_comparative_benchmark` | `c7a66b2a99608b51508cc249459917d23ffebc4258501afd8567ca99afff6add` |
| `current_hardware_sensitivity` | `current` | `$.current_comparative_thermal_contours.hardware_sensitivity` | `shared_model_comparative_benchmark` | `9b8a709f65e156b160facfb977a8b7362b928344dc45c840ef4b9eae637313a0` |
| `current_thermal_profile` | `current` | `$.current_comparative_thermal_contours.thermal_profile` | `shared_model_comparative_benchmark` | `1c92e0fbfb54f19803c70970b0dbf135c4bb37121a34407d64639ad6a3582eee` |

`payload_json` is the deterministic canonical JSON representation of the
source contour. `payload_sha256` binds that exact representation.

### `M31PublishedTransitionVisualizerDataset`

Fields are `visualizer_dataset_id`, `audit_batch`, `audit_report`,
`visualizer_dispatch`, `trace_dataset`, `core_declaration`,
`transition_frames`, `thermal_contours`, `active_zero_roles`,
`evidence_boundaries`, `publication_contract`, and `dataset_sha256`.

Qualified dataset identity:

| Property | Exact value |
|---|---|
| Visualizer dataset id | `63a1feb9-1835-579e-ab00-eec4569e8ff3` |
| Transition frames | 800 |
| Thermal contours | 4 |
| Visualizer dispatch SHA-256 | `ff4597411a781c814ab8ef009d30739857411d2a31ff34839d3060b478a697e8` |
| Dataset SHA-256 | `0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304` |

`active_zero_roles` must equal the trace-dataset tuple.
`evidence_boundaries` retains the exact published evidence-boundary mapping.
`publication_contract` retains the exact one-way FRP-to-Observatory contract.

## Cross-Layer Cardinality Rules

### M30

- one archive validation anchors one published-boundary validation;
- one registry validation contains four registrations and seven routes;
- one member-intake batch contains four canonical member intakes;
- one dispatch batch contains seven member-to-mode dispatches;
- one audit batch contains four member reports;
- one M30 Trace Explorer dataset consumes the single trace-explorer route;
- one full-core evidence record retains two source trace contours;
- one M30 visualizer dataset retains 100 trace records and 800 frames.

### M31

- one boundary validation contains four canonical documents;
- one registry validation contains four registrations and six routes;
- one dispatch batch contains six document-to-mode dispatches;
- one audit batch contains four role reports;
- one Trace Explorer dataset consumes the evidence trace-explorer route;
- one trace dataset retains two source contours and 100 records;
- one visualizer dataset consumes the evidence visualizer route;
- one visualizer dataset retains one core declaration, 800 frames, and four
  thermal contours.

Cardinality changes alter deterministic identities and fail validation.

## Deterministic Identity Rules

Deterministic identifiers use fixed UUID namespaces and exact registered
identity material. Deterministic SHA-256 values use canonical JSON with:

- sorted object keys where the implementation declares canonical JSON;
- compact separators;
- ASCII-safe encoding;
- source-defined array order;
- exact strings, integers, Booleans, and null values;
- complete required record inventories.

Source raw SHA-256 and canonical-record SHA-256 remain different scopes.
Changing a source byte, identity field, source coordinate, ordering value,
route, frame, contour, or required aggregate changes the applicable digest.

## Preservation Rules

The normalized model preserves:

- original source bytes and raw digests;
- exact source paths and package-member paths;
- schema, kind, role, release, milestone, and version identities;
- source ordering and source coordinates;
- integer and Boolean types;
- canonical and encoded states as separate values;
- scheduler modes and states as separate fields;
- request lanes and acceptance decisions;
- pending polarity and route legs;
- transition-capacity relations;
- event and scheduler counters;
- invariant names and published bit order;
- measurement contours and their source groups;
- archive, manifest, qualification, and provenance ancestry;
- historical M30 and M31 dataset identities.

Normalized and derived records add identity and validation metadata while
leaving source values unchanged.

## Current Implementation Boundary

The base `TraceDatasetBuilder` constructs the five registered base trace
families. Dedicated M30 and M31 builders construct their publication-specific
trace and visualizer datasets.

Audit-report serialization is implemented as immutable mappings,
deterministic compact JSON, and plain text. Publication-specific datasets
expose deterministic source payloads, counts, identifiers, and digests through
their typed APIs and command-line summaries.

Comparative artifacts remain represented by exact audit records and fixture
provenance rather than a generic benchmark-dataset class. Human-readable M16
Markdown remains evidence associated with the base scope rather than a
machine-readable trace source.

## Acceptance Evidence

The 655-test repository suite verifies:

- immutable source capture and raw-byte integrity;
- safe JSON and M15 vector parsing;
- exact base registry dispatch;
- audit status, ordered checks, provenance, and serializers;
- canonical fixture and deterministic-package validation;
- structured-output, M3, M15, comparative, and sensitivity validators;
- base trace-family construction, ordering, completeness, and mode
  eligibility;
- canonical ternary, scheduler, request, route, telemetry, counter, invariant,
  transition, and view relations;
- exact M30 archive identity, manifest, members, and retained bytes;
- four M30 registrations and seven exact mode routes;
- M30 member intake, dispatch, four-report audit batch, trace dataset, and
  full-core visualizer dataset;
- exact M31 paths, identifiers, byte lengths, raw digests, and provenance;
- four M31 registrations and six exact mode routes;
- M31 dispatch, four-report audit batch, two-contour trace dataset, core
  declaration, 800 transition frames, and four thermal contours;
- deterministic IDs and digests at every M30 and M31 stage;
- mandatory mutation, substitution, ordering, cardinality, path, identity,
  route, and digest failure cases;
- the complete 26-test M31 end-to-end qualification contour.

With both exact upstream inputs configured, the complete command is:

```
FRP_M30_ARCHIVE_PATH=<exact M30 archive> \
FRP_M31_UPSTREAM_ROOT=<clean FRP checkout> \
python -m unittest discover -s tests -p 'test_*.py' -q
```

Qualified result:

```
Ran 655 tests

OK
```

## Excluded Transformations

The data model excludes:

- mutation or replacement of source bytes;
- execution of uploaded content or upstream producer commands;
- filename-only schema inference;
- implicit aliases or schema upgrades;
- replacement of absence with a default source value;
- conversion of encoded states without an encoding binding;
- addition of a positive sign to canonical state `1`;
- inferred request decisions or route legs without source evidence;
- conflation of scheduler mode and scheduler state;
- conflation of source, normalized, and derived origins;
- merging of measurement contours;
- writeback into FRP.

## Author

MMaksym Marnov (Alchimist)  
Berlin, Germany
