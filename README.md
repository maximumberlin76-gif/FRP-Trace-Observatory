# FRP Trace Observatory

FRP Trace Observatory is a standalone downstream project for reading,
validating, correlating, and presenting artifacts published by the Fractal
Resonance Processor project.

It is maintained outside the upstream FRP repository. Parser dependencies,
user-interface dependencies, Observatory tests, and the Observatory release
lifecycle therefore remain outside the qualified upstream boundary.

## Integration Boundary

The integration direction is strictly one-way:

```text
Fractal-Resonance-Processor
→ published artifacts
→ FRP-Trace-Observatory
```

FRP remains the sole source of truth for processor semantics. Observatory:

- reads captured source bytes without modifying them;
- resolves only exact registered schema and format identifiers;
- validates published values and recorded relations;
- preserves source provenance and validation evidence;
- constructs explicitly labeled Observatory-derived views;
- does not replace the executable semantic reference;
- does not reproduce or redefine internal processor logic;
- does not execute uploaded code, SystemVerilog, producer commands, or
  artifact content;
- does not change published metric values;
- does not combine unrelated measurement contours.

## Audited Compatibility Baseline

The current compatibility registry was derived from the audited FRP `v1.8.0`
repository state. Schema and format identifiers retained from the FRP
`v1.7.0` semantic-reference and M15 export contracts keep their published
identifiers and versions.

The registry currently contains:

- 19 exact compatibility records;
- JSON identities carried by the `schema` field;
- M15 vector identities carried by the `format_version` field;
- separate artifact-kind dispatch where one schema identifies multiple
  artifact kinds;
- explicit upstream producer, evidence, measurement-contour, and mode
  metadata;
- a distinction between committed-artifact evidence and producer-declaration
  evidence.

The exact compatibility records and upstream evidence paths are documented in
[`docs/supported_schema_registry.md`](docs/supported_schema_registry.md).

Formal upstream JSON Schema documents, canonical upstream CSV artifacts, and
machine-readable M16 schemas were not present in the audited source archive.
Observatory does not create replacements and does not present extracted
integration rules as upstream-published schemas.

## Canonical Ternary Domain

The processor domain is written consistently as:

`-1, 0, 1`

State `0` is an active neutral state.

Opposite-polarity routing is represented through the published neutral path:

- `-1 → 0 → 1`;
- `1 → 0 → -1`.

The canonical positive state is written as `1`.

## Implemented Repository Layers

### Source Capture and Parsers

The parser layer provides:

- immutable capture of original source bytes;
- SHA-256 content digests and source-byte integrity verification;
- source filename, known source path, byte length, and load timestamp
  provenance;
- safe container classification;
- deterministic JSON parsing;
- deterministic M15 headered vector parsing;
- exact compatibility-registry dispatch;
- explicit unsupported and unrecognized results without alias resolution.

The current parser boundary covers registered JSON and M15 vector-text
artifacts. CSV parsing remains outside the current implementation boundary
until a canonical upstream CSV artifact and producer contract are available.

### Artifact Auditor

Artifact Auditor provides read-only validation for:

- structured-output artifacts;
- M3 benchmark matrices;
- M15 JSON artifacts;
- M15 vector artifacts;
- deterministic M15 artifact packages;
- Comparative Architecture Benchmark Suite artifacts;
- Hardware-Informed Sensitivity Qualification artifacts;
- the canonical Observatory fixture manifest and fixture inventory.

Audit reports preserve:

- source provenance;
- declared and matched registry identities;
- producer metadata when registered;
- measurement-contour identity;
- ordered validation checks;
- expected and observed value snapshots;
- source locations;
- missing package members;
- aggregate validation status;
- digest-check identities.

Reports can be projected into an immutable mapping, deterministic compact JSON
bytes, or a complete plain-text view. These outputs are
Observatory-derived reports and do not replace the source artifact.

### Ternary Transition Visualizer

The implemented visualizer data layer provides immutable source-linked models
for:

- canonical ternary state values;
- neutralization and completion transitions;
- request-lane acceptance and rejection records;
- pending and applied route records;
- scheduler state and scheduler mode;
- transition-capacity and switching telemetry;
- event-counter snapshots;
- invariant bits and invariant vectors.

The derived-view builder supports exact tick, cell, request-lane,
scheduler-state, and event-type filters; source-order and record-identifier
projections; canonical state-transition projections; and trace-to-route
correlation. Derived views retain source record identities, validation report
identities, registry revision, source ordering, and the
`observatory_derived` origin label.

No user-interface framework or renderer is selected by the current repository.

### Trace Explorer

The implemented Trace Explorer data layer provides immutable normalized
records and deterministic dataset construction for:

- structured processor-tick traces;
- M15 cycle-exact reference traces;
- M15 primary vector traces;
- M15 per-cell vector traces;
- M15 pending-route traces routed to Ternary Transition Visualizer.

Trace datasets preserve tick order, source record order, cell records,
request bundles, scheduler snapshots, ternary state snapshots, event counters,
published telemetry, provenance references, completeness state, and ordering
validation state.

Only artifacts with a registered compatibility record and a valid or
valid-with-warnings audit report may enter trace-dataset construction.

No user-interface framework or renderer is selected by the current repository.

## Artifact Integrity and Provenance

Original source bytes remain unchanged.

Normalized records, audit reports, and visualizer views are stored as separate
representations. Every derived representation retains links to its source
artifact and applicable validation evidence.

The implemented provenance boundary includes:

- source filename;
- known source path;
- source artifact identity;
- schema or format identifier;
- producer path and producer version when registered;
- source SHA-256 digest;
- source byte length;
- load timestamp;
- validation report identity;
- validation status;
- validation messages and source locations.

Unknown, unsupported, absent, or not-evaluated data remains explicit. It is not
reconstructed from documentation and is not converted into a zero value.

## Canonical Fixtures

The repository contains six unchanged upstream JSON fixture copies:

- four Comparative Architecture Benchmark Suite artifacts;
- two Hardware-Informed Sensitivity Qualification artifacts.

The [canonical fixture manifest](fixtures/canonical_fixture_manifest.json)
records their upstream paths, exact identities, measurement contours, byte
lengths, and raw-source SHA-256 digests.

The manifest digest contract is:

- algorithm: `sha256`;
- scope: `raw_source_bytes`;
- origin: `observatory_calculated`;
- copy requirement: `unchanged_upstream_bytes`.

The current fixture inventory does not claim committed canonical M15 vector
fixtures.

## Measurement Boundaries

The compatibility registry keeps these measurement contours separate:

- `structured_output`;
- `m3_benchmark_matrix`;
- `m15_implementation_mapping`;
- `comparative_architecture_benchmark_suite`;
- `hardware_informed_sensitivity_qualification`.

Operation count, thermal proxy, transition pressure, heat, scheduler timing,
latency, throughput, RTL execution, FPGA preparation evidence, and physical
measurements remain distinct fields and evidence classes.

Target-independent FPGA preparation evidence is not presented as
physical-chip measurement evidence.

## Repository Structure

```text
FRP-Trace-Observatory/
├── .github/
│   └── workflows/
│       └── observatory-ci.yml
├── artifact_auditor/
├── docs/
├── fixtures/
├── parsers/
├── schemas/
├── tests/
├── trace_explorer/
└── transition_visualizer/
```

## Documentation

- [`docs/integration_contract.md`](docs/integration_contract.md) defines the
  one-way downstream boundary and support gates.
- [`docs/supported_schema_registry.md`](docs/supported_schema_registry.md)
  records audited identifiers, formats, producers, fields, evidence paths,
  fixtures, and mode routing.
- [`docs/normalized_data_model.md`](docs/normalized_data_model.md) defines the
  source, audit, trace, transition, telemetry, invariant, and derived-view
  records.

## Verification

The current implementation uses Python 3.12 and the Python standard library.

Run the complete test suite from the repository root:

```bash
python -m unittest discover -s tests -q
```

Current local verification result:

```text
Ran 275 tests

OK
```

The tests cover source-byte immutability, provenance, exact registry dispatch,
parsers, validators, deterministic packages, canonical fixtures, audit report
construction and serialization, trace construction, transition records,
telemetry, invariant vectors, and derived-view builders.

Repository verification is also executed by
[`FRP Trace Observatory CI`](.github/workflows/observatory-ci.yml). The
workflow runs on pushes and pull requests targeting `main` and by manual
dispatch. It:

- checks out the repository without persisting credentials;
- sets up Python 3.12;
- compiles all Python source and test directories;
- runs the complete test suite.

GitHub Actions run `FRP Trace Observatory CI #3` completed with `SUCCESS` for
commit `a719b08`.

A release package is not yet declared.

## Project Status

The integration contract, compatibility registry, normalized read-only data
model, parsers, canonical fixture inventory, Artifact Auditor core, Ternary
Transition Visualizer data layer, Trace Explorer data layer, repository tests,
documentation, and repository verification workflow are implemented.

No Observatory release version, release qualification status, UI framework,
hosted service, or release package is declared by the current repository
state.

## Versioning

FRP Trace Observatory has an independent version lifecycle.

Its version does not automatically match an FRP release version. Supported FRP
releases, schema identifiers, format identifiers, artifact kinds, and mode
routing are recorded explicitly in the compatibility registry.

## Out of Scope

The following remain outside FRP Trace Observatory:

- AI inference engines;
- training pipelines;
- autonomous agent logic;
- changes to FRP processor semantics;
- new FRP execution claims;
- execution of uploaded artifact content;
- modification of published FRP artifacts.

## Author

Maksym Marnov ( Alchimist)
