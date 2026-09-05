# Contributing to FRP Trace Observatory

Thank you for improving FRP Trace Observatory. Contributions must preserve the
repository's read-only upstream boundary, deterministic identities, explicit
provenance, measurement-contour separation, and complete M1–M22 history.

- **Current Observatory boundary:** M22
- **Qualified upstream boundary:** FRP M31
- **Python runtime:** 3.12
- **Test framework:** Python `unittest`
- **Current complete suite:** 655 tests
- **License:** Apache License 2.0

## Repository Purpose

FRP Trace Observatory validates and projects published Fractal Resonance
Processor artifacts without rewriting the upstream source. Its principal
layers are:

| Layer | Repository path | Responsibility |
|---|---|---|
| Artifact Auditor | `artifact_auditor/` | Exact validation and immutable audit reports |
| Parsers | `parsers/` | Read-only source parsing and canonical field extraction |
| Schema Registry | `schemas/` | Executable support records, publication registries, and dispatch rules |
| Trace Explorer | `trace_explorer/` | Source-linked trace, cell, request, and invariant projections |
| Transition Visualizer | `transition_visualizer/` | Source-linked transition frames, telemetry, contours, and derived views |
| Fixtures | `fixtures/` | Committed deterministic qualification inputs |
| Tests | `tests/` | Unit, mutation-failure, integration, determinism, and end-to-end qualification |
| Documentation | `docs/` | Usage, reproducibility, CI, milestone, integration, data-model, and registry contracts |

## Contribution Boundary

A contribution belongs in this repository when it improves one or more of the
following without changing the upstream FRP source:

- exact artifact recognition;
- schema or publication registration;
- read-only parsing;
- validation and audit reporting;
- explicit consumer dispatch;
- source-linked trace projection;
- transition visualization;
- deterministic serialization;
- provenance or measurement-contour handling;
- qualification tests;
- current documentation.

Changes to the FRP processor implementation, upstream evidence, or upstream
publication artifacts belong in the upstream FRP repository. The Observatory
may support a new upstream artifact only after that artifact has a stable,
verifiable identity.

## Required Preservation Rules

Every contribution must preserve these invariants:

1. Upstream FRP inputs remain read-only.
2. Upstream paths, bytes, order, and identities remain distinguishable from
   Observatory records.
3. Normalized records retain exact source links.
4. Derived records retain explicit derivation identities and source links.
5. The processor-state domain is written as `-1/0/1`.
6. State `0` remains an active neutral mediation state in the published model.
7. Missing, idle, false, absent, and state `0` are not interchangeable values.
8. `free`, `1/7`, and `7/1` remain separate scheduler modes.
9. Source order remains canonical unless a derived view explicitly records a
   different order.
10. Historical, current comparative, hardware-sensitivity, thermal-profile,
    and physical-measurement contours remain separately identified.
11. Proxy or benchmark data is not relabeled as physical measurement.
12. Deterministic identifiers and SHA-256 values change only when their exact
    declared inputs change.
13. M1–M22 workflows, tests, evidence, benchmarks, and history are retained.
14. A later qualification layer does not replace an earlier evidence boundary.
15. Source, normalized, and Observatory-derived representations remain
    explicit and non-interchangeable.

## Development Environment

Use Python 3.12 from the repository root.

Verify the interpreter:

```
python --version
```

Expected major and minor version:

```
Python 3.12
```

The current implementation uses the Python standard library and does not
require a package-install step for repository-contained tests.

## Baseline Verification

Compile all maintained Python source:

```
python -m compileall -q \
  artifact_auditor \
  parsers \
  schemas \
  trace_explorer \
  transition_visualizer \
  tests
```

Run the complete available test suite:

```
python -m unittest discover -s tests -v
```

Tests requiring an exact external upstream input are skipped when that input
is not configured. A change affecting M30 or M31 must also be qualified with
the applicable exact input present.

## Exact Upstream Inputs

### M30 archive

Configure the immutable M30 archive:

```
export FRP_M30_ARCHIVE_PATH=/absolute/path/to/frp-v3.2.0-m30-archival-release.tar.gz
```

Required identity:

```
length=10189989
sha256=05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa
```

### M31 publication

Configure a clean checkout of the upstream FRP repository:

```
export FRP_M31_UPSTREAM_ROOT=/absolute/path/to/Fractal-Resonance-Processor
```

The M31 intake validates all four publication documents and their provenance
members by exact path, role, identity, byte length, and SHA-256.

### Complete exact verification

With both inputs configured:

```
python -m unittest discover -s tests -p 'test_*.py' -q
```

Qualified result:

```
Ran 655 tests

OK
```

The complete setup and independent reproduction sequence is defined in
[docs/reproducibility.md](docs/reproducibility.md).

## Focused Test Requirements

Run the closest focused tests before the complete suite.

| Change area | Minimum focused command |
|---|---|
| Base parser | `python -m unittest tests.test_json_artifact tests.test_m15_vector -v` |
| Base validator | `python -m unittest tests.test_m15_artifact_validator tests.test_m15_vector_validator tests.test_structured_output_validator -v` |
| Registry or dispatch | `python -m unittest tests.test_schema_registry tests.test_artifact_dispatch -v` |
| Artifact Auditor | `python -m unittest tests.test_validation_core tests.test_audit_report tests.test_audit_report_serializer tests.test_auditor -v` |
| Trace Explorer | `python -m unittest tests.test_trace_model tests.test_trace_builder tests.test_cycle_exact_trace_builder -v` |
| Transition Visualizer | `python -m unittest tests.test_transition_models tests.test_telemetry_models tests.test_invariant_models tests.test_transition_view_model tests.test_transition_view_builder -v` |
| M30 publication | `python -m unittest discover -s tests -p 'test_m30_*.py' -v` with `FRP_M30_ARCHIVE_PATH` configured |
| M31 publication | `python -m unittest discover -s tests -p 'test_m31_*.py' -v` with `FRP_M31_UPSTREAM_ROOT` configured |
| End-to-end M31 boundary | `python -m unittest tests.test_m31_published_observatory_end_to_end -v` |

## Test Design Rules

New behavior requires tests for the applicable success and failure boundaries.

Include, where relevant:

- canonical success input;
- missing required field;
- unexpected field;
- wrong field type;
- wrong enumeration value;
- altered source path;
- altered source bytes or digest;
- wrong archive member;
- wrong publication identity;
- invalid role or consumer route;
- reordered canonical records;
- duplicate identity;
- mutable collection or record attempts;
- source-provenance mismatch;
- derived-record provenance mismatch;
- measurement-contour conflation;
- repeated-run deterministic identity;
- upstream and repository preservation.

A failure test must assert the specific rejected boundary. A broad exception
check is insufficient when the exact validation error is part of the public
contract.

## Deterministic Output Rules

Deterministic outputs must be constructed from declared canonical inputs.

Contributions must:

1. use explicit field order;
2. preserve source record order;
3. define any derived sorting in the derived-view record;
4. serialize with stable separators and encoding;
5. retain terminal-newline rules where byte identity requires them;
6. derive UUIDs and SHA-256 values from documented canonical material;
7. test repeated construction for identical output;
8. test a meaningful input mutation for changed or rejected output;
9. avoid timestamps, random values, environment-specific paths, or iteration
   order in deterministic identity material;
10. retain the source identity used to derive every aggregate identity.

## Data-Origin Rules

Every record must have an unambiguous origin.

| Origin | Meaning |
|---|---|
| Upstream source | Value and identity are retained directly from FRP material |
| Normalized | Canonical Observatory representation with exact source linkage |
| Observatory-derived | New projection or aggregate with explicit derivation linkage |

An Observatory-derived field must not claim an upstream field name. A source
record must not be marked as derived. A normalized record must retain enough
identity and location data to resolve its exact source.

## Measurement and Claim Rules

Changes involving performance, heat, power, thermal behavior, stability, or
hardware sensitivity must identify the exact measurement contour.

Record at least:

- source artifact and path;
- source identity or SHA-256;
- upstream milestone and version;
- measurement or derivation method;
- units or explicit dimensionless classification;
- scheduler mode and processor-state domain;
- sample, tick, record, or frame cardinality;
- whether the value is measured, modeled, proxied, or derived;
- limitations encoded by the source record;
- any winner or superiority assertion present in the source.

Historical benchmark values remain historical benchmark values. Current proxy
values remain current proxy values. Physical-temperature status follows the
source declaration for that exact contour.

## Schema and Registry Changes

A schema or publication role may be marked supported only when all applicable
implementation gates are present:

1. exact schema or publication identity;
2. exact producer and version evidence;
3. required, optional, order, value, relation, and digest rules;
4. read-only parser and validator;
5. canonical success fixture or exact external source;
6. mandatory identity and mutation-failure cases;
7. provenance and immutability tests;
8. mode-routing and consumer-integration tests;
9. deterministic output checks;
10. synchronized registry, integration, data-model, usage, reproducibility,
    milestone, CI, and changelog documentation.

An upstream release does not update the registry automatically. Add a new
registration only after auditing its exact published boundary.

## Workflow Rules

Routine repository CI is defined by:

```
.github/workflows/observatory-ci.yml
```

It runs on pushes to `main`, pull requests targeting `main`, and manual
dispatch.

The retained M1–M22 milestone workflows are manually dispatched through the
GitHub Actions interface. Creating, uploading, or committing a workflow file
does not manually run it.

Workflow changes must preserve:

- the historical role of the milestone;
- manual `workflow_dispatch` for milestone qualification;
- explicit branch and event gates;
- minimum required permissions;
- `persist-credentials: false` for upstream checkout;
- Python 3.12;
- exact predecessor verification;
- focused and complete tests;
- declared commit scope;
- source and repository preservation checks;
- `cancel-in-progress: false` for milestone concurrency.

Run a milestone workflow once from `main`, wait for its complete result, and
inspect the first red step when qualification fails. Later skipped steps are
consequences of the first failure.

Full workflow operation is documented in [docs/ci.md](docs/ci.md).

## Documentation Changes

Documentation is part of the executable contract. Update every document whose
facts change.

| Changed fact | Documents to review |
|---|---|
| User command or supported operation | `README.md`, `docs/usage.md` |
| Input identity or reproduction step | `docs/reproducibility.md`, `docs/ci.md` |
| Milestone completion or workflow | `docs/milestones.md`, `docs/ci.md`, `CHANGELOG.md` |
| Integration boundary | `docs/integration_contract.md` |
| Record, field, origin, or relation | `docs/normalized_data_model.md` |
| Schema support or route | `docs/supported_schema_registry.md` |
| M31 publication identity or result | `docs/m31_published_boundary.md` |
| Attribution or provenance notice | `NOTICE.md` |

Use exact paths, commands, counts, identities, and qualification results.
Retain historical results when adding a later boundary.

Repository Markdown code fences use plain triple backticks without language
tags. Processor state is always written `-1/0/1`.

## Commit Scope

Keep each commit reviewable and limited to one coherent change.

A commit should include:

- the implementation change;
- its focused tests;
- required deterministic fixtures;
- synchronized documentation;
- no unrelated formatting or generated-file changes.

Use an imperative English commit subject that states the completed change.
Examples:

```
Add exact M31 registry mutation checks
Preserve source contour identity in trace views
Document completed Observatory milestones through M22
```

## Pull Request Evidence

A pull request description should state:

1. the exact boundary changed;
2. the source or upstream identity involved;
3. files intentionally changed;
4. focused tests executed;
5. complete tests executed;
6. configured external inputs;
7. deterministic identities added or changed;
8. provenance and measurement-contour impact;
9. documentation synchronized;
10. preservation checks performed.

Attach concise command output or GitHub Actions results sufficient to identify
the executed suite and final status. Preserve detailed evidence in committed
fixtures, deterministic serialized output, or the applicable workflow summary.

## Issue Reports

A reproducible issue report should include:

- Observatory revision;
- Python version and operating system;
- exact command;
- first failing step or exception;
- applicable upstream milestone and identity;
- applicable archive or document SHA-256;
- expected and observed cardinality or identity;
- smallest non-sensitive input that reproduces the boundary;
- whether the upstream and Observatory working trees were clean.

Do not include credentials, access tokens, private repository contents, or
unredacted sensitive paths.

## Licensing

Contributions accepted into this repository are provided under the Apache
License, Version 2.0, supplied in [LICENSE](LICENSE). Retain applicable
copyright, attribution, patent, trademark, and third-party notices.

Project attribution and upstream provenance are recorded in
[NOTICE.md](NOTICE.md).

## Author

Maksym Marnov (Alchimist)  
Berlin, Germany
