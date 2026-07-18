# FRP Trace Observatory Normalized Read-Only Data Model

**Status:** Initial conceptual data contract  
**Upstream audit baseline:** FRP v1.8.0 / M16  
**Observatory version:** Not assigned  
**Serialization format:** Not assigned  
**Implementation status:** No code or framework selected

## Purpose

This document defines the normalized read-only data model used between artifact parsers, Artifact Auditor, Ternary Transition Visualizer, and Trace Explorer.

The model separates:

- original source bytes;
- source provenance;
- registry identity;
- parsed source values;
- validation results;
- normalized read-only records;
- Observatory-derived views.

This model does not define FRP processor semantics.

It does not replace any upstream schema, producer, trace, manifest, metric, or qualification record.

## Model Authority

FRP remains the sole source of truth for processor semantics and published artifact values.

The normalized model provides typed downstream access to validated source data.

A normalized record must retain enough information to locate the source artifact and source value from which it was created.

If a source value and a normalized representation conflict, the source value remains authoritative and the conflict is reported as a validation failure.

## Design Principles

The normalized model follows these principles:

1. original source bytes remain unchanged;
2. every artifact load has its own provenance record;
3. registry identity is separate from declared artifact identity;
4. absent values remain absent;
5. source values are not replaced with defaults;
6. source order is preserved;
7. numeric types remain distinguishable;
8. measurement contours remain separate;
9. encoded states remain distinguishable from canonical states;
10. validation results remain separate from source data;
11. derived views are labeled as Observatory-derived;
12. unsupported artifacts do not enter typed user modes;
13. arbitrary artifact content is never executed.

## Conceptual Scope

The logical names in this document describe data responsibilities.

They do not prescribe:

- a programming language;
- class names;
- database tables;
- storage technology;
- API serialization;
- user-interface components;
- framework dependencies.

A future implementation may map these logical records to concrete types only after the model is approved.

## Data Layers

| Layer | Primary record | Content | Mutability |
|---|---|---|---|
| Source | `SourceArtifact` | Original bytes and load identity | Immutable |
| Provenance | `ArtifactProvenance` | Origin, declarations, producer association, and validation references | Append-only |
| Registry | `RegistryBinding` | Exact compatibility-registry match | Immutable for one load |
| Parsed source | `ParsedArtifact` | Non-executable parsed representation of source values | Immutable |
| Validation | `ValidationReport` | Checks, outcomes, messages, and digest comparisons | Immutable |
| Normalized | `NormalizedArtifact` | Typed read-only records linked to source locations | Immutable |
| Derived | `DerivedView` | Filters, projections, indexes, correlations, and visual coordinates | Immutable and explicitly derived |

A source artifact may exist without a registry binding.

An unrecognized source artifact may receive safe diagnostics and a validation report, but it does not receive a typed normalized artifact.

## Identity Model

Observatory distinguishes load identity from content identity.

### Load Identity

Each artifact load receives a unique internal `source_artifact_id`.

Loading identical bytes twice creates two load identities because the following may differ:

- source filename;
- source path;
- load timestamp;
- surrounding package;
- user-provided context;
- validation registry version.

### Content Identity

Content identity is represented by a digest calculated over the original loaded bytes.

Two source artifacts may share the same content digest while retaining separate load identities and provenance records.

A digest alone must not replace provenance.

### Normalized Identity

Each normalized artifact receives a separate `normalized_artifact_id`.

It references exactly one source artifact.

Package-level normalized records may additionally reference the source artifacts of their members.

### Derived Identity

Each derived view receives a separate `derived_view_id`.

A derived view records all source and normalized records used to produce it.

## Value Presence

The model preserves the distinction between:

- an absent field;
- a field present with `null`;
- a field present with `false`;
- a field present with `0`;
- a field present with an empty string;
- a field present with an empty array;
- a field present with an empty object.

An absent optional field must not be replaced with a default inside the normalized source representation.

When a registered upstream producer defines a default, Observatory may expose that default only as an explicitly labeled derived interpretation.

## Numeric Preservation

The parsed and normalized layers preserve the source distinction between:

- integer values;
- non-integer numeric values;
- numeric strings;
- hexadecimal strings;
- packed integer encodings;
- fixed-point integer values;
- dequantized published values.

Observatory must not replace an upstream integer with a floating-point value.

A fixed-point field and its published dequantized companion remain separate fields.

A unit conversion or dequantization created by Observatory is a derived value and must identify its formula and source field.

## Source Ordering

The following source order is preserved:

- JSON array order;
- trace row order;
- vector row order;
- request-lane order;
- package manifest order when semantically declared;
- line order;
- route-event order;
- qualification-record order when relevant.

Object-key order remains available through the original source bytes but is not assigned processor semantics unless the upstream contract explicitly defines key order.

## `SourceArtifact`

`SourceArtifact` represents one loaded byte sequence.

Required logical fields:

| Field | Meaning |
|---|---|
| `source_artifact_id` | Unique Observatory load identity |
| `source_filename` | Filename supplied by the load source |
| `source_path` | Source path when known |
| `byte_length` | Exact original byte count |
| `raw_bytes_reference` | Read-only reference to the original bytes |
| `detected_container_format` | Safely detected data container |
| `source_digest_id` | Reference to the raw-byte digest record |
| `loaded_at` | Observatory load timestamp |
| `load_status` | Source capture result |

`source_path` is optional because an uploaded file may not provide an upstream repository path.

`source_filename` and `source_path` are provenance values. They do not establish schema identity by themselves.

### Source Capture Rules

Source capture occurs before parsing.

The source digest is calculated before:

- newline conversion;
- character decoding replacement;
- JSON parsing;
- key sorting;
- whitespace normalization;
- archive-member rewriting.

If source capture fails, parsing and normalization do not proceed.

## `SourceLocation`

`SourceLocation` identifies where a value or validation issue occurs.

A location may contain:

- `source_artifact_id`;
- byte offset;
- line number;
- column number;
- JSON path;
- array index;
- vector column name;
- package-member name;
- Markdown heading;
- Markdown table row;
- source-record ordinal.

Only location forms applicable to the source format are populated.

A source location must not be invented when the parser cannot determine it.

Validation messages may reference more than one source location when checking a relation.

## `ArtifactProvenance`

`ArtifactProvenance` records the origin and processing history of one source artifact.

Required logical fields:

| Field | Meaning |
|---|---|
| `provenance_id` | Unique provenance-record identity |
| `source_artifact_id` | Referenced source load |
| `source_filename` | Original source filename |
| `source_path` | Original source path when known |
| `declared_schema_identifier` | Exact embedded schema value when present |
| `declared_kind` | Exact embedded kind value when present |
| `declared_version` | Exact embedded version value when present |
| `declared_milestone` | Exact embedded milestone value when present |
| `declared_producer_version` | Producer version declared by the artifact when present |
| `registered_producer_version` | Producer version associated through the registry |
| `registry_binding_id` | Registry association when one is established |
| `digest_record_ids` | Source and declared digest records |
| `loaded_at` | Observatory load timestamp |
| `validation_report_id` | Validation report reference |
| `validation_status` | Overall validation outcome |
| `validation_message_ids` | Validation message references |

An absent declaration remains absent.

A registered producer version must not be represented as though the artifact declared it.

The provenance record preserves both values separately.

## `RegistryBinding`

`RegistryBinding` records how one source artifact matched `docs/supported_schema_registry.md`.

Required logical fields:

| Field | Meaning |
|---|---|
| `registry_binding_id` | Unique binding identity |
| `registry_key` | Exact registry entry |
| `match_method` | Method used to establish the match |
| `schema_identifier` | Registered schema identifier when applicable |
| `required_discriminator` | Registered `kind` or other discriminator |
| `format_identifier` | Registered non-schema format identifier when applicable |
| `package_role` | Registered package-member role when applicable |
| `upstream_contract_path` | Exact upstream contract path |
| `upstream_producer_path` | Exact upstream producer path |
| `upstream_producer_version` | Registered producer version |
| `upstream_release_association` | Registered FRP release association |
| `support_status` | Current registry implementation status |
| `measurement_contour` | Registered primary contour |
| `referenced_contours` | Additional upstream contours explicitly referenced |
| `eligible_modes` | Observatory modes allowed by the registry |

Registered match methods are:

- embedded schema identifier;
- embedded schema identifier and `kind`;
- embedded format identifier;
- verified package-member role;
- exact schema-free path and producer contract.

Filename-only matching is not a valid standalone match method.

A package-member match is valid only after the enclosing package requirements are satisfied.

## `DigestRecord`

`DigestRecord` represents one calculated or declared digest.

Required logical fields:

| Field | Meaning |
|---|---|
| `digest_record_id` | Unique digest-record identity |
| `source_artifact_id` | Source artifact associated with the digest |
| `digest_role` | Meaning and scope of the digest |
| `algorithm` | Exact digest algorithm |
| `declared_value` | Upstream-declared value when present |
| `calculated_value` | Observatory-calculated value when applicable |
| `byte_scope` | Exact bytes or logical structure covered |
| `serialization_contract` | Registered serialization rule when applicable |
| `source_location` | Location of the declared digest |
| `comparison_status` | Digest comparison result |

Registered digest roles include:

- raw source bytes;
- whole artifact;
- canonical object;
- preload;
- processor-tick trace;
- per-cell trace;
- package;
- package member;
- raw trace set;
- profile;
- comparison result.

A digest record must not compare values with different byte scopes or serialization contracts.

### Digest Comparison Outcomes

Digest comparison outcomes are:

- `match`;
- `mismatch`;
- `declared_only`;
- `calculated_only`;
- `not_evaluated`;
- `not_applicable`.

`declared_only` does not mean that the declared digest is valid.

`calculated_only` does not create an upstream-declared digest.

## `ParsedArtifact`

`ParsedArtifact` contains the non-executable parsed representation of source data.

Required logical fields:

- `parsed_artifact_id`;
- `source_artifact_id`;
- `container_format`;
- `character_encoding`;
- parsed root value;
- source-location map;
- parse diagnostics;
- parse status.

Parsing must not:

- execute code;
- evaluate expressions;
- import artifact modules;
- invoke producer commands;
- compile SystemVerilog;
- resolve external resources;
- mutate the source artifact.

A parsing failure still permits a source-level audit report.

## `ValidationReport`

`ValidationReport` contains the validation outcome for one source artifact or one verified package.

Required logical fields:

| Field | Meaning |
|---|---|
| `validation_report_id` | Unique report identity |
| `source_artifact_id` | Primary validated source |
| `registry_binding_id` | Applied registry contract |
| `started_at` | Validation start timestamp |
| `completed_at` | Validation completion timestamp |
| `observatory_version` | Observatory version when assigned |
| `registry_revision` | Registry revision used for validation |
| `check_ids` | Ordered validation-check references |
| `overall_status` | Aggregate validation outcome |
| `message_ids` | Ordered validation-message references |

Minimum overall statuses are:

- `recognized_valid`;
- `recognized_valid_with_warnings`;
- `recognized_invalid`;
- `known_unsupported`;
- `unrecognized`;
- `incomplete_package`.

An invalid artifact remains available as source data but is not eligible for a successful typed user-mode view.

## `ValidationCheck`

`ValidationCheck` represents one validation operation.

Required logical fields:

| Field | Meaning |
|---|---|
| `check_id` | Unique check identity |
| `check_code` | Stable Observatory check identifier |
| `category` | Validation category |
| `outcome` | Check outcome |
| `severity` | Message severity when applicable |
| `source_locations` | Related source locations |
| `expected` | Registered expectation when applicable |
| `observed` | Observed source value when safely representable |
| `message` | User-facing check result |
| `upstream_rule_reference` | Producer or documentation source for the rule |

Validation categories include:

- container;
- identity;
- structure;
- type;
- allowed value;
- ternary domain;
- ordering;
- scheduler relation;
- transition capacity;
- pending route;
- invariant vector;
- digest;
- deterministic package;
- qualification evidence.

Check outcomes are:

- `pass`;
- `fail`;
- `warning`;
- `not_applicable`;
- `not_evaluated`.

A mandatory failed check cannot be replaced by a warning.

## `NormalizedArtifact`

`NormalizedArtifact` is the root of a typed read-only representation.

Required logical fields:

| Field | Meaning |
|---|---|
| `normalized_artifact_id` | Unique normalized identity |
| `source_artifact_id` | Authoritative source reference |
| `provenance_id` | Provenance reference |
| `registry_binding_id` | Exact registry contract |
| `validation_report_id` | Validation result |
| `artifact_class` | Observatory artifact classification |
| `declared_identity` | Preserved upstream identity values |
| `primary_contour` | Registered measurement or qualification contour |
| `referenced_contours` | Explicit additional contour references |
| `record_collection_ids` | Typed normalized record collections |
| `view_eligibility` | Allowed modes after validation |
| `normalization_status` | Normalization outcome |

Initial artifact classes include:

- structured trace;
- structured self-test;
- benchmark matrix;
- profile;
- comparison result;
- export map;
- cycle-exact trace;
- deterministic vector package;
- vector trace;
- qualification manifest;
- qualification evidence;
- opaque registered package member.

Artifact classes are downstream organizational labels. They do not replace upstream schema identifiers.

A recognized invalid artifact may receive a partial diagnostic normalized record for Artifact Auditor.

It must not become eligible for Trace Explorer or Ternary Transition Visualizer.

## `NormalizedField`

`NormalizedField` links a typed value to its source.

Required logical fields:

| Field | Meaning |
|---|---|
| `normalized_field_id` | Unique field identity |
| `source_artifact_id` | Source artifact reference |
| `source_location` | Exact source location |
| `source_field_name` | Original upstream field name |
| `presence` | Whether the field is present |
| `source_type` | Parsed source type |
| `source_value` | Preserved source value or immutable reference |
| `normalized_type` | Registered normalized type |
| `normalized_value` | Typed normalized representation when valid |
| `unit` | Registered upstream unit when declared |
| `encoding` | Registered upstream encoding when applicable |
| `origin` | Source, normalized, or derived origin |
| `validation_check_ids` | Checks applying to the field |

Registered origins are:

- `upstream_source`;
- `observatory_normalized`;
- `observatory_derived`.

A canonical state decoded through a registered encoding map is `observatory_normalized`.

A value calculated through a new projection, formula, aggregation, or correlation is `observatory_derived`.

## `PackageRecord`

`PackageRecord` represents a registered multi-file artifact set.

Required logical fields:

- `package_record_id`;
- package source artifact or package-load identity;
- registry binding;
- expected member count;
- observed member count;
- ordered expected member roles;
- member source-artifact references;
- package manifest reference;
- package digest records;
- missing members;
- unexpected members;
- package validation report;
- completeness status.

Each loaded package member receives its own `SourceArtifact` and `ArtifactProvenance`.

A package-level provenance record references all member provenance records.

A member without an embedded identifier may be normalized only through its exact verified package role.

A missing member remains missing.

A member from another package must not be substituted.

## Measurement Contour Assignment

Every normalized artifact has one primary registered contour.

An artifact that explicitly references another contour records that reference separately without merging the contours.

Registered contour names include:

- historical transition benchmark;
- structured-output benchmark;
- M3 benchmark matrices;
- transition-pressure and feedback-stress matrix;
- thermal-survival and stability-boundary matrix;
- hierarchical scaling and hotspot-containment matrix;
- M15 implementation-mapping matrix;
- Comparative Architecture Benchmark Suite;
- Hardware-Informed Sensitivity Qualification;
- M16 RTL qualification;
- M16 FPGA preparation qualification.

A document spanning M16 RTL and FPGA preparation evidence may use one primary contour and one referenced contour, or a package-level evidence grouping containing separate contour records.

Individual measurement values remain assigned to exactly one contour.

## Read-Only Model Rules

The normalized model does not provide operations that:

- update source values;
- delete source values;
- insert missing source fields;
- change source order;
- replace declared digests;
- migrate schema versions;
- merge measurement contours;
- convert derived values into source values;
- mark an invalid artifact as valid without a new validation report.

A new load, report, or derived view creates a new record rather than mutating an existing record.

## Trace Data Model

Trace data is normalized into a `TraceDataset`.

A trace dataset may contain:

- processor-tick records;
- per-cell records;
- route-event records;
- request-lane records;
- transition records;
- scheduler records;
- telemetry records;
- event-counter records;
- package and digest references.

Only collections present in the validated source artifact are populated.

A missing collection remains absent.

## `TraceDataset`

Required logical fields:

| Field | Meaning |
|---|---|
| `trace_dataset_id` | Unique trace-dataset identity |
| `normalized_artifact_id` | Parent normalized artifact |
| `trace_family` | Registered trace format or role |
| `schema_identifier` | Upstream schema when present |
| `kind` | Upstream artifact kind when present |
| `format_identifier` | Non-schema format identifier when present |
| `configuration_fields` | Source execution configuration |
| `tick_record_ids` | Ordered processor-tick records |
| `cell_record_ids` | Ordered per-cell records |
| `route_event_ids` | Ordered route events |
| `request_lane_record_ids` | Ordered request-lane records |
| `transition_record_ids` | Source or derived transition records |
| `record_counts` | Observed collection sizes |
| `state_encoding_binding` | Registered state-encoding contract |
| `ordering_validation` | Trace-order validation result |
| `completeness_status` | Required-collection availability |
| `eligible_modes` | Modes permitted after validation |

Initial trace families include:

- structured processor-tick trace;
- cycle-exact reference trace;
- M15 primary vector trace;
- M15 per-cell vector trace;
- M15 pending-route trace.

A comparative benchmark result containing trace digests but no trace rows does not create a `TraceDataset`.

## `TickRecord`

`TickRecord` represents one source processor-tick row.

Required logical fields:

| Field | Meaning |
|---|---|
| `tick_record_id` | Unique tick-record identity |
| `trace_dataset_id` | Parent trace dataset |
| `source_location` | Source row location |
| `source_ordinal` | Original zero-based record order |
| `tick` | Published tick value |
| `scheduler_snapshot_id` | Scheduler data for the tick |
| `request_bundle_id` | Request-lane input data when present |
| `state_snapshot_id` | Retained ternary state data |
| `transition_telemetry_id` | Transition and capacity data when present |
| `telemetry_snapshot_id` | Heat, coherence, and pressure data |
| `event_counter_snapshot_id` | Published cumulative counters |
| `changes` | Published current-tick state-change count when present |
| `validation_check_ids` | Checks applying to the row |

`source_ordinal` and `tick` remain separate.

Observatory does not replace an invalid tick value with the source ordinal.

A tick record preserves only fields provided by its registered source format.

## `SchedulerSnapshot`

`SchedulerSnapshot` preserves encoded and human-readable scheduler values separately.

Logical fields include:

- source scheduler-mode value;
- normalized scheduler-mode value;
- source scheduler-state value;
- normalized scheduler-state value;
- published scheduler-state name;
- encoding-map reference;
- source locations;
- validation checks.

Registered M15 scheduler modes are:

- `free`;
- `7/1`;
- `1/7`.

Registered M15 scheduler-state names are:

- `free`;
- `balance`;
- `commit`;
- `excite`;
- `neutralize`.

An encoded scheduler value is normalized only through its registered upstream encoding map.

Scheduler state, scheduler mode, and scheduler counters remain distinct values.

## `TernaryStateSnapshot`

`TernaryStateSnapshot` represents retained processor state at one source record.

Logical fields include:

- `state_snapshot_id`;
- source artifact and record references;
- packed integer state when present;
- packed hexadecimal state when present;
- human state string when present;
- ordered per-cell state references;
- state-encoding binding;
- reserved-state observations;
- state-domain validation result.

The canonical processor domain is:

`-1, 0, 1`

State `0` is an active neutral state.

The canonical positive state is displayed as `1`.

Packed, textual, and canonical representations remain separately accessible.

## `TernaryStateValue`

Each per-cell state uses a `TernaryStateValue`.

Logical fields include:

- cell identifier;
- source representation;
- source encoding;
- canonical state when decoding succeeds;
- encoding-map reference;
- source location;
- normalization origin;
- validation result.

A source state is mapped to a canonical value only when the registry provides the exact encoding contract.

A reserved or unknown encoding is not coerced into a canonical state.

Its source value is preserved and its validation failure is recorded.

## `RequestBundle`

`RequestBundle` represents request information published for one tick or vector row.

Logical fields include:

- source request-valid mask;
- source request cell identifiers;
- source request target states;
- request-lane count;
- ordered request-lane references;
- request encoding binding;
- source locations;
- validation checks.

Expanding a valid-mask and parallel arrays into individual lane records is an Observatory normalization operation.

The expansion must follow the registered lane-order and encoding contract.

## `RequestLaneRecord`

`RequestLaneRecord` represents one request lane at one tick.

Logical fields include:

| Field | Meaning |
|---|---|
| `request_lane_record_id` | Unique lane-record identity |
| `tick_record_id` | Parent tick record |
| `lane_index` | Published or normalized lane position |
| `valid` | Lane-valid state |
| `cell_id` | Requested cell when present |
| `source_target_state` | Original target representation |
| `canonical_target_state` | Decoded target when valid |
| `acceptance_status` | Accepted, rejected, or unavailable |
| `rejection_reason` | Published reason when present |
| `scheduler_decision` | Published scheduler decision when present |
| `capacity_decision` | Published capacity decision when present |
| `source_locations` | Related source fields |
| `origin` | Source or normalized origin |

Initial acceptance-status values are:

- `accepted`;
- `rejected`;
- `not_recorded`;
- `not_applicable`.

`not_recorded` is not equivalent to `rejected`.

The audited M15 processor-tick trace records request inputs but does not publish a complete per-lane acceptance, rejection, and reason trace.

Observatory must not infer those decisions from aggregate counters.

## `TransitionRecord`

`TransitionRecord` represents a source transition or an explicitly identified Observatory-derived transition.

Logical fields include:

- `transition_record_id`;
- source artifact and trace references;
- cell identifier;
- source tick or tick range;
- source state;
- target state;
- transition classification;
- route-leg classification;
- related request-lane reference;
- related route-event references;
- scheduler decision when published;
- capacity decision when published;
- source locations;
- origin;
- derivation record when applicable;
- validation checks.

Registered transition classifications may distinguish:

- same-state retention;
- polarity-to-neutral transition;
- neutral-to-polarity transition;
- observed opposite-polarity transition;
- unknown transition.

An observed state change must not be labeled as an `actual_direct_events` occurrence unless the registered source contract establishes that relation.

### Route-Leg Classification

A transition may be classified as:

- first-leg neutralization;
- pending-route completion;
- non-route transition;
- not determined.

First-leg neutralization and pending-route completion require validated source relations.

They must not be assigned solely because a state sequence visually resembles a neutral route.

## `RouteEventRecord`

`RouteEventRecord` preserves one source route event.

Logical fields include:

- `route_event_record_id`;
- source artifact and trace references;
- source ordinal;
- tick;
- route index when present;
- cell identifier;
- source target representation;
- canonical target state when valid;
- ready tick;
- route status;
- source location;
- related transition references;
- validation checks.

Registered structured-output route statuses are:

- `pending`;
- `applied`.

A pending event and an applied event may be linked only through the registered route relation and unambiguous validated source values.

A missing applied event remains missing.

## `CellTraceRecord`

`CellTraceRecord` represents one cell at one processor tick.

Logical fields include:

- `cell_trace_record_id`;
- parent trace dataset;
- source location;
- source ordinal;
- tick;
- cell identifier;
- source state code;
- canonical state when valid;
- phase word;
- target frequency;
- current frequency;
- frequency lag;
- generated power;
- local model heat;
- thermal overload;
- gamma-noise state;
- effective gamma word;
- thermal node factor;
- coupling field;
- validation checks.

The current structured-output and M15 cell-trace fields are preserved as separate values:

- `state_code`;
- `phase_word`;
- `frequency_target_q16`;
- `frequency_current_q16`;
- `frequency_lag_q16`;
- `generated_power_q16`;
- `heat_q16`;
- `thermal_overload_q16`;
- `gamma_noise_state_q16`;
- `gamma_effective_word`;
- `thermal_node_factor_q30`;
- `coupling_field_q16`.

Model heat and thermal proxy values must not be presented as physical temperature measurements.

## `TelemetrySnapshot`

`TelemetrySnapshot` groups published telemetry without merging its fields.

Logical fields may include:

- `switch_load_q16`;
- `heat_global_q16`;
- `global_phase_coherence_q30`;
- `C_q16`;
- `P_q16`;
- `C_minus_P_q16`;
- published dequantized companion values;
- source locations;
- field-level units and encodings;
- aggregation classification;
- validation checks.

Each telemetry field remains an independent `NormalizedField`.

The presence of both quantized and dequantized values does not permit one to replace the other.

## Aggregation Classification

A metric or counter may be classified through its registered upstream contract as:

- instantaneous;
- current tick;
- cumulative;
- final summary;
- minimum summary;
- maximum summary;
- package aggregate.

Observatory must not calculate a per-tick value from a cumulative value unless the result is explicitly labeled as Observatory-derived.

The original cumulative value remains available.

## `EventCounterSnapshot`

`EventCounterSnapshot` preserves published processor event counters.

Logical fields may include:

- `requested_direct_events`;
- `prevented_direct_events`;
- `neutral_routed_events`;
- `neutralized_conflicts`;
- `actual_direct_events`;
- `reserved_state_events`;
- `queue_overflow_events`;
- source locations;
- accumulation classifications;
- validation checks.

A missing counter remains unavailable.

A missing counter must not be represented as zero.

A zero value remains associated with its source tick, summary, or qualification scope.

## `TransitionTelemetry`

`TransitionTelemetry` represents published transition-capacity information.

Logical fields may include:

- transition fraction;
- request-lane count;
- current-tick changes;
- switch load;
- transition capacity;
- remaining capacity;
- capacity-exhausted state;
- deferral state;
- source locations;
- validation checks.

Only fields present in the source contract are populated.

A capacity value calculated from configuration is Observatory-derived unless the source artifact publishes the value directly.

Scheduler deferral and transition-capacity deferral remain unavailable when the source artifact does not publish the decision.

## Vector Data Model

A registered vector artifact is normalized into a `VectorDataset`.

## `VectorDataset`

Required logical fields:

- `vector_dataset_id`;
- normalized artifact reference;
- package record reference;
- exact package-member role;
- format identifier;
- producer version;
- trace kind;
- parsed header fields;
- declared column definition;
- ordered vector rows;
- row count;
- ordering validation;
- column validation;
- digest records;
- eligible modes.

The original line text and parsed column values remain separately accessible.

A malformed vector row is not padded or truncated to match the declared column count.

## `VectorRow`

`VectorRow` contains:

- source line location;
- source ordinal;
- original line reference;
- ordered source tokens;
- declared column names;
- typed normalized fields;
- row-level validation checks.

Hexadecimal source tokens remain available in their original representation.

A decoded integer or ternary value is a normalized companion value.

## Package-Bound Non-Trace Records

The following package members remain separate normalized artifact classes:

- reference preload;
- trigonometric lookup table;
- SHA-256 manifest.

A preload object is not a processor-tick trace.

A lookup-table row is not a physical measurement.

A digest manifest is not a qualification result by itself.

## Benchmark and Measurement Data Model

Benchmark profiles and results are normalized without converting them into trace datasets.

## `MeasurementRecord`

`MeasurementRecord` represents one published measurement or aggregate.

Required logical fields:

| Field | Meaning |
|---|---|
| `measurement_record_id` | Unique measurement identity |
| `normalized_artifact_id` | Parent artifact |
| `source_location` | Exact source field or row |
| `contour` | Registered measurement contour |
| `metric_name` | Original upstream metric name |
| `source_value` | Published value |
| `source_type` | Published value type |
| `unit` | Published unit when present |
| `aggregation` | Registered aggregation classification |
| `dimensions` | Architecture, scenario, tick, cell, or other published dimensions |
| `qualification_status` | Published status when directly associated |
| `origin` | Source or derived origin |

A measurement without a published unit remains unit-unspecified.

Observatory must not assign a physical unit based on the metric name alone.

## `BenchmarkDataset`

`BenchmarkDataset` represents one benchmark profile, matrix, or result package.

Logical fields include:

- benchmark dataset identity;
- normalized artifact reference;
- schema identifier when present;
- benchmark kind;
- suite name;
- FRP reference version;
- scheduler;
- architecture order;
- scenario order;
- profile references;
- comparison rows;
- measurement records;
- declared rankings;
- integrity checks;
- qualification checks;
- digest records;
- contour.

Operation count, normalized cost, thermal proxy, latency, throughput, logical transitions, encoded toggles, and physical measurements remain separate fields.

A published ranking may be displayed exactly as recorded.

Observatory must not create a winner assertion or ranking that is absent from the upstream artifact.

## Trace-Digest Ledgers

A benchmark package may contain a ledger of trace digests.

A trace-digest ledger records trace identity and package relations.

It does not create trace rows.

A ledger entry may be correlated with a separately loaded trace only when:

- the digest scope is registered;
- the calculated digest matches;
- the producer and version are compatible;
- the measurement contours remain visible.

## Qualification Evidence Data Model

Human-readable and machine-readable qualification evidence use separate source-format contracts but share a normalized evidence model.

## `QualificationEvidenceRecord`

Logical fields include:

- `qualification_evidence_id`;
- source artifact reference;
- source location;
- upstream release;
- qualification contour;
- evidence type;
- subject artifact or component;
- published status;
- workflow name when recorded;
- run identifier when recorded;
- commit identifier when recorded;
- branch when recorded;
- duration when recorded;
- artifact count when recorded;
- declared digest references;
- zero-event record references;
- invariant-vector references;
- linked evidence records;
- extraction method;
- validation checks.

Markdown extraction must use an exact registered document contract.

A value extracted from Markdown remains linked to its heading, table row, or line.

A Markdown qualification document does not become a machine-readable processor trace.

## `QualificationStatusRecord`

`QualificationStatusRecord` preserves:

- exact published status text;
- status scope;
- source location;
- associated check or workflow;
- associated contour;
- validation result.

Published `PASS` and `SUCCESS` values remain distinct strings.

Observatory does not replace either value with its own qualification terminology.

## `ZeroEventRecord`

`ZeroEventRecord` contains:

- event-counter name;
- published zero value;
- source location;
- qualification scope;
- upstream release;
- associated run or manifest when recorded;
- validation checks.

A zero-event record is valid only when the source explicitly records the event name and zero value.

A zero value from one qualification contour must not be applied to another contour.

## `InvariantVectorRecord`

`InvariantVectorRecord` contains:

- original vector representation;
- bit count;
- source location;
- registered bit-order contract when available;
- ordered invariant-bit records;
- published aggregate status;
- qualification contour;
- validation checks.

Each invariant bit contains:

- source bit position;
- source bit value;
- registered invariant name when available;
- published or normalized status;
- upstream rule reference.

Unknown bit meanings remain unknown.

Bit order must not be reversed for display.

## Observatory-Derived Views

A derived view is represented by `DerivedView`.

Required logical fields:

| Field | Meaning |
|---|---|
| `derived_view_id` | Unique derived-view identity |
| `view_type` | Filter, projection, correlation, transition, or visual layout |
| `source_artifact_ids` | All source artifacts used |
| `normalized_record_ids` | All normalized records used |
| `operation` | Exact deterministic operation |
| `parameters` | Filter or transformation parameters |
| `created_at` | View creation timestamp |
| `observatory_version` | Producing Observatory version when assigned |
| `registry_revision` | Registry revision used |
| `output_record_ids` | Derived output records |
| `source_order_preserved` | Whether the view retains source order |
| `derived_label` | Required Observatory-derived identification |

Derived-view types may include:

- tick filter;
- cell filter;
- request-lane filter;
- scheduler-state filter;
- event-type filter;
- source-order-preserving projection;
- explicitly sorted projection;
- state-transition projection;
- trace-to-route correlation;
- digest correlation;
- qualification-evidence summary;
- visual coordinate layout.

A derived view does not become an upstream artifact.

## Filter Semantics

A filter selects records without modifying them.

Default filtered views preserve source order.

Filter parameters and selected source-record identities are retained in the derived-view record.

An empty filter result means that no source records matched.

It does not mean that the source artifact contained no records.

## Mode Projections

The three Observatory modes consume the shared normalized model through separate read-only projections.

### Trace Explorer Projection

Trace Explorer may consume:

- valid trace datasets;
- tick records;
- scheduler snapshots;
- request bundles;
- state snapshots;
- per-cell records;
- route events;
- telemetry snapshots;
- event counters;
- source provenance;
- validation summaries.

Trace Explorer does not consume aggregate comparison packages as tick traces.

### Ternary Transition Visualizer Projection

Ternary Transition Visualizer may consume:

- validated canonical state values;
- state snapshots;
- source or derived transition records;
- route-event records;
- request-lane records when decisions are published;
- scheduler records;
- transition-capacity records when published;
- event counters;
- invariant vectors;
- source provenance.

Every visual transition retains links to its source or derivation records.

A missing decision or event is displayed as unavailable rather than inferred.

### Artifact Auditor Projection

Artifact Auditor may consume:

- every source artifact;
- provenance records;
- registry bindings;
- parsed artifacts;
- digest records;
- package records;
- validation checks;
- validation messages;
- normalized records when available;
- qualification evidence;
- unsupported and unrecognized artifact diagnostics.

Artifact Auditor reports invalidity without modifying the artifact.

## Cross-Artifact Correlation

Cross-artifact correlation requires explicit compatible identities.

Possible correlation keys include:

- exact source digest;
- exact declared artifact digest;
- exact trace digest;
- exact cell-trace digest;
- exact package-member digest;
- exact schema identifier;
- exact producer version;
- exact workload digest;
- exact profile digest;
- exact run or commit identifier.

A filename match alone is insufficient.

A correlation result is Observatory-derived and retains all participating provenance records.

Correlation does not merge measurement contours.

## Determinism

For the same:

- original source bytes;
- registry revision;
- validation rules;
- Observatory version;
- derivation parameters;

the parsed values, validation results, normalized values, and derived content must be deterministic.

The following runtime metadata may differ between loads:

- internal load identity;
- load timestamp;
- report timestamp;
- derived-view timestamp.

Runtime metadata must not be included in comparisons intended to establish deterministic normalized content unless the comparison contract explicitly includes it.

## Serialization Boundary

This document does not assign a machine-readable Observatory schema identifier.

A future serialization contract must define:

- exact Observatory schema identifier;
- exact Observatory version;
- required and optional fields;
- timestamp representation;
- internal identifier representation;
- source-byte storage reference;
- source-location representation;
- ordering guarantees;
- null and absence handling;
- numeric serialization;
- validation-report serialization;
- derived-view serialization.

The future Observatory schema version remains independent of all FRP schema versions.

## Minimum MVP Record Set

The MVP normalized model requires implementations for:

1. `SourceArtifact`;
2. `SourceLocation`;
3. `ArtifactProvenance`;
4. `RegistryBinding`;
5. `DigestRecord`;
6. `ParsedArtifact`;
7. `ValidationReport`;
8. `ValidationCheck`;
9. `NormalizedArtifact`;
10. `NormalizedField`;
11. `PackageRecord`;
12. `TraceDataset`;
13. `TickRecord`;
14. `SchedulerSnapshot`;
15. `TernaryStateSnapshot`;
16. `TernaryStateValue`;
17. `RequestBundle`;
18. `RequestLaneRecord`;
19. `TransitionRecord`;
20. `RouteEventRecord`;
21. `CellTraceRecord`;
22. `TelemetrySnapshot`;
23. `EventCounterSnapshot`;
24. `TransitionTelemetry`;
25. `VectorDataset`;
26. `VectorRow`;
27. `MeasurementRecord`;
28. `BenchmarkDataset`;
29. `QualificationEvidenceRecord`;
30. `QualificationStatusRecord`;
31. `ZeroEventRecord`;
32. `InvariantVectorRecord`;
33. `DerivedView`.

Implementation may combine storage structures only when all logical responsibilities and boundaries remain preserved.

## Model Acceptance Criteria

The normalized model is ready for parser implementation when:

- every MVP record has an approved responsibility;
- source and normalized identities are separate;
- source-byte immutability is testable;
- absent and null values remain distinguishable;
- source locations can represent JSON, vector, package, and Markdown inputs;
- schema and `kind` dispatch are representable;
- package-bound identification is representable;
- declared and calculated digests remain separate;
- trace order and source ordinal remain separate;
- encoded and canonical state values remain separate;
- accepted, rejected, and unavailable request decisions remain distinct;
- cumulative and per-tick values remain distinct;
- measurement contours cannot be merged implicitly;
- qualification evidence cannot become a processor trace;
- every derived record retains its derivation and source references;
- mode eligibility can be denied after validation failure.

## Prohibited Model Behavior

A conforming implementation must not:

- discard original source bytes;
- use normalized data as replacement provenance;
- identify a schema-free artifact by filename alone;
- treat a missing value as zero;
- treat a missing request decision as rejection;
- infer per-tick events from aggregate counters;
- reorder an invalid trace without labeling the result as derived;
- decode an unregistered state encoding;
- convert a reserved encoding into a canonical state;
- combine benchmark contours into one metric series;
- represent FPGA preparation evidence as physical-chip evidence;
- execute artifact content;
- mutate an existing normalized record.

## Author

Maksym Marnov
