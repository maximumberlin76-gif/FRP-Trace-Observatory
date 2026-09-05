<h1 align="center">FRP Trace Observatory</h1>

<p align="center">
  <strong>Deterministic observability for published Fractal Resonance Processor evidence</strong>
</p>

<p align="center">
  <a href="https://github.com/maximumberlin76-gif/FRP-Trace-Observatory/actions/workflows/observatory-ci.yml"><img alt="FRP Trace Observatory CI" src="https://github.com/maximumberlin76-gif/FRP-Trace-Observatory/actions/workflows/observatory-ci.yml/badge.svg"></a>
  <img alt="Observatory M22 complete" src="https://img.shields.io/badge/Observatory-M22%20complete-2ea44f">
  <img alt="FRP M31 qualified" src="https://img.shields.io/badge/FRP-M31%20qualified-2ea44f">
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <a href="LICENSE"><img alt="Apache License 2.0" src="https://img.shields.io/badge/License-Apache--2.0-D22128?logo=apache"></a>
</p>

FRP Trace Observatory is the read-only validation, audit, trace, and
visualization layer for artifacts published by the
[Fractal Resonance Processor](https://github.com/maximumberlin76-gif/Fractal-Resonance-Processor-FRP-Ternary-Resonant-Coherence-Processor).
It turns exact upstream publication records into immutable audit reports,
source-linked traces, and deterministic ternary transition datasets while
preserving every source identity and measurement contour.

The current repository closes the complete Observatory M22 qualification over
the FRP M31 published boundary and retains the full earlier M30 evidence chain.

## At a Glance

| Property | Current repository state |
|---|---|
| Observatory implementation | Complete through M22 |
| Qualified FRP boundary | M31 |
| Retained earlier boundary | M30 through Observatory M8B |
| Published M31 documents | 4 exact files |
| M31 registry routes | 6 exact routes |
| M31 audit result | 4 reports, 47 checks, 0 failures |
| M31 trace result | 2 contours, 100 records, 800 cell snapshots |
| M31 visualizer result | 800 source-linked transition frames |
| M31 focused end-to-end suite | 26 tests, `OK` |
| Complete repository suite | 655 tests, `OK` with exact inputs configured |
| Workflow inventory | 27 retained workflows |
| Runtime | Python 3.12 |
| Runtime dependencies | Python standard library |
| License | Apache License 2.0 |

## What the Observatory Provides

### Exact Published-Artifact Intake

- captures source bytes without rewriting them;
- validates exact paths, byte lengths, SHA-256 values, publication roles, and
  archive membership;
- binds every supported artifact to an executable registry record;
- retains upstream milestone, version, producer, commit, and source-path
  provenance where published;
- rejects altered, incomplete, ambiguous, or unregistered boundaries.

### Artifact Auditor

- validates registered artifacts through ordered field, identity, value,
  relation, order, and digest checks;
- produces immutable reports with exact expected and observed evidence;
- preserves source locations, registry bindings, dispatch identities, and
  measurement contours;
- serializes deterministic mapping, compact JSON, and plain-text views.

### Trace Explorer

- constructs immutable source-linked trace datasets;
- retains tick order, record order, cell state, request bundles, scheduler
  snapshots, telemetry, invariants, and source coordinates;
- supports the base compatibility layer plus exact M30 and M31 publication
  contours;
- records source, normalized, and Observatory-derived identities separately.

### Ternary Transition Visualizer

- projects qualified traces into deterministic source-linked transition
  frames;
- represents neutral mediation, polarity activation, state retention, pending
  routing, and route completion explicitly;
- retains transition, scheduler, request-route, telemetry, invariant, and
  measurement-contour records;
- provides immutable derived views without changing canonical source order.

## Processing Boundary

The data path is one-way and provenance-preserving:

| Stage | Input | Output | Integrity rule |
|---|---|---|---|
| Published intake | Exact FRP archive or publication documents | Immutable source records | Path, bytes, length, digest, role, and membership remain exact |
| Registry | Immutable source identity | Support and routing record | Only audited identifiers and declared consumers are accepted |
| Dispatch | Registered artifact | Immutable consumer envelope | Route eligibility and route order remain explicit |
| Artifact Auditor | Source plus registry and dispatch identity | Immutable audit reports | Every decision retains expected, observed, and source evidence |
| Trace Explorer | Qualified source and audit result | Source-linked trace dataset | Record order, coordinates, state, request, and contour identity remain exact |
| Transition Visualizer | Qualified trace dataset | Source-linked transition frames and views | Every frame resolves to its trace, record, cell, and contour |

The upstream FRP repository remains the semantic and publication authority.
The Observatory maintains a separately versioned downstream lifecycle and
stores its normalized and derived representations under explicit provenance.

## Formal Ternary State Domain

The published processor-state domain is:

```
S = {-1, 0, 1}
```

State `0` is an active neutral mediation state. It participates in retained
state, request routing, pending-route handling, and opposite-polarity
transition completion. It is distinct from missing, absent, idle, false, or
unevaluated data.

Opposite-polarity transitions follow the neutral route:

```
-1 → 0 → 1
 1 → 0 → -1
```

The exact M31 visualizer qualifies:

| Transition class | Frames |
|---|---:|
| `active_zero_to_polarity` | 12 |
| `polarity_to_active_zero` | 5 |
| `retained_same` | 783 |
| `direct_opposite` | 0 |
| **Total** | **800** |

Scheduler modes remain separate:

| Mode | M31 trace records |
|---|---:|
| `free` | 19 |
| `7/1` | 64 |
| `1/7` | 17 |
| **Total** | **100** |

## Qualified M31 Publication Boundary

The M31 authority contains four exact upstream documents:

| Role | Observatory consumer boundary |
|---|---|
| Formal schema | Artifact Auditor |
| Phase-interference, active-neutral, thermal, and stability evidence | Artifact Auditor, Trace Explorer, Ternary Transition Visualizer |
| Publication manifest | Artifact Auditor |
| Publication qualification | Artifact Auditor |

The complete registry exposes four document records and six exact routes.
Every document is bound by path, role, kind, identity field, identity value,
byte length, raw SHA-256, and provenance membership.

### M31 Artifact Auditor

| Role | Checks | Status |
|---|---:|---|
| Formal schema | 11 | `recognized_valid` |
| Evidence | 16 | `recognized_valid` |
| Manifest | 10 | `recognized_valid` |
| Qualification | 10 | `recognized_valid` |
| **Total** | **47** | **0 failures** |

```
batch_sha256=3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591
```

### M31 Trace Explorer

| Quantity | Qualified value |
|---|---:|
| Source contours | 2 |
| Ordered trace records | 100 |
| Source-linked cell snapshots | 800 |
| Request records | 200 |
| Invariant-pass records | 100 |
| Retained observations of state `0` | 702 |

```
trace_dataset_id=0f0f0f7e-0409-5e7b-8c76-2f72bb954321
trace_dispatch_sha256=f34b867fabcaab51515ecca39f2eb7287f52aa218d3ac48596a1481326009630
dataset_sha256=ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff
```

### M31 Ternary Transition Visualizer

| Quantity | Qualified value |
|---|---:|
| Source-linked frames | 800 |
| Non-route frames | 790 |
| First route legs to state `0` | 5 |
| Pending route completions | 5 |
| Direct opposite transitions | 0 |

```
visualizer_dataset_id=63a1feb9-1835-579e-ab00-eec4569e8ff3
visualizer_dispatch_sha256=ff4597411a781c814ab8ef009d30739857411d2a31ff34839d3060b478a697e8
dataset_sha256=0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304
```

### M31 Thermal Evidence

Four published thermal evidence contours remain independently addressable:

| Contour | Group | Evidence classification | Physical temperature |
|---|---|---|---:|
| `historical_release_benchmark` | historical | source-linked benchmark | false |
| `current_comparative_baseline` | current | comparative proxy contour | false |
| `current_hardware_sensitivity` | current | hardware-sensitivity proxy contour | false |
| `current_thermal_profile` | current | thermal-profile proxy contour | false |

The historical focused comparison is retained exactly as published:

```
binary_heat_peak=0.051000
active_neutral_ternary_heat_peak=0.003250
heat_peak_ratio_binary_over_active_neutral_ternary=15.6923076923
heat_peak_relative_reduction_percent=93.63
winner_assertions=[]
```

These values remain attached to their historical benchmark contour. The
current comparative, hardware-sensitivity, and thermal-profile contours retain
their own identities and evidentiary meaning.

## Retained M30 Publication Boundary

The complete M30 chain remains qualified and available alongside M31.

| Boundary | Qualified result | SHA-256 |
|---|---|---|
| Immutable archive | 10,189,989 bytes, 519 entries, 518 manifested members | `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa` |
| Registry and dispatch | 4 registrations, 7 exact routes | Bound by registered source identities |
| Artifact Auditor | 4 reports, 69 checks, 0 failures | `aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03` |
| Trace Explorer | 4 records, 32 cell snapshots, 8 requests | `4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd` |
| Transition Visualizer | 2 contours, 100 records, 800 frames | `7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b` |

Observatory M8B closes the M30 chain. Observatory M22 closes the M31 chain.
All intermediate M1–M22 workflows and their evidence boundaries remain
retained.

## Quick Start

Clone the repository and enter its root:

```
git clone https://github.com/maximumberlin76-gif/FRP-Trace-Observatory.git
cd FRP-Trace-Observatory
```

Verify Python:

```
python --version
```

Required runtime:

```
Python 3.12
```

Compile the maintained source:

```
python -m compileall -q \
  artifact_auditor \
  parsers \
  schemas \
  trace_explorer \
  transition_visualizer \
  tests
```

Run repository-contained verification:

```
python -m unittest discover -s tests -v
```

The suite discovers 655 tests. Tests bound to exact external M30 or M31 input
are reported as skipped until that input is configured.

## Exact Full Qualification

Set the immutable M30 archive:

```
export FRP_M30_ARCHIVE_PATH=/absolute/path/to/frp-v3.2.0-m30-archival-release.tar.gz
```

Set a clean upstream FRP repository root containing the M31 publication:

```
export FRP_M31_UPSTREAM_ROOT=/absolute/path/to/Fractal-Resonance-Processor
```

Run the complete suite:

```
python -m unittest discover -s tests -p 'test_*.py' -q
```

Qualified result:

```
Ran 655 tests

OK
```

Run the focused M31 end-to-end contour:

```
python -m unittest \
  tests.test_m31_published_observatory_end_to_end \
  -v
```

Qualified result:

```
Ran 26 tests

OK
```

## Direct Boundary Commands

Validate and project M30:

```
python -m artifact_auditor.m30_archive_intake \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m schemas.m30_published_registry \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m artifact_auditor.m30_published_auditor \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m trace_explorer.m30_published_trace_explorer \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m transition_visualizer.m30_published_transition_visualizer \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

Validate and project M31:

```
python -m schemas.m31_published_registry \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m artifact_auditor.m31_published_auditor \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m trace_explorer.m31_published_trace_explorer \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m transition_visualizer.m31_published_transition_visualizer \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"
```

See [Usage](docs/usage.md) for the complete command and output contract and
[Reproducibility](docs/reproducibility.md) for exact input verification.

## Repository Structure

```
FRP-Trace-Observatory/
├── .github/
│   └── workflows/                # Routine CI and retained M1–M22 workflows
├── artifact_auditor/             # Intake, validators, reports, and serializers
├── docs/                         # Public technical and operational contracts
├── fixtures/                     # Deterministic committed qualification inputs
├── parsers/                      # Read-only JSON and vector parsers
├── schemas/                      # Base, M30, and M31 registries and dispatch
├── tests/                        # 655 unit and integration tests
├── trace_explorer/               # Source-linked trace models and builders
├── transition_visualizer/        # Transition, telemetry, invariant, and view layers
├── CHANGELOG.md                  # Completed repository history
├── CONTRIBUTING.md               # Contribution and preservation contract
├── LICENSE                       # Apache License 2.0
├── NOTICE.md                     # Attribution and provenance notice
└── README.md                     # Project entry point
```

## Documentation

| Document | Purpose |
|---|---|
| [Usage](docs/usage.md) | Supported commands, inputs, outputs, and failure behavior |
| [Reproducibility Contract](docs/reproducibility.md) | Exact environment, upstream identities, commands, and expected results |
| [CI and Manual Workflows](docs/ci.md) | Routine CI, manual milestone operation, permissions, and failure interpretation |
| [Milestone History](docs/milestones.md) | Complete retained Observatory M1–M22 implementation history |
| [Integration Contract](docs/integration_contract.md) | One-way upstream boundary, support gates, and composed acceptance |
| [Normalized Data Model](docs/normalized_data_model.md) | Source, normalized, audit, trace, transition, telemetry, invariant, and view records |
| [Supported Schema Registry](docs/supported_schema_registry.md) | Exact compatibility records, publication roles, parsers, validators, and routes |
| [M31 Published Boundary](docs/m31_published_boundary.md) | Exact four-document M31 identity, provenance, audit, trace, and visualizer result |
| [Changelog](CHANGELOG.md) | Completed changes through Observatory M22 / FRP M31 |
| [Contributing](CONTRIBUTING.md) | Test, provenance, determinism, documentation, and workflow requirements |
| [Notice](NOTICE.md) | Author attribution, license boundary, and upstream provenance |

## Continuous Integration

Routine repository verification is defined in
[`observatory-ci.yml`](.github/workflows/observatory-ci.yml). It runs on:

- pushes to `main`;
- pull requests targeting `main`;
- manual dispatch.

Routine CI checks out the repository without persisted credentials, uses
Python 3.12, compiles all maintained Python source, and runs the complete
available test suite.

The 26 retained Observatory milestone workflows use manual
`workflow_dispatch`. Run them from the GitHub Actions interface on branch
`main`. Committing or uploading a workflow file does not manually execute it.

Terminal qualification workflows:

| Boundary | Workflow |
|---|---|
| M30 | [`frp-observatory-m8b-full-core-transition-visualizer-qualification-workflow.yml`](.github/workflows/frp-observatory-m8b-full-core-transition-visualizer-qualification-workflow.yml) |
| M31 | [`frp-observatory-m22-m31-published-end-to-end-qualification-workflow.yml`](.github/workflows/frp-observatory-m22-m31-published-end-to-end-qualification-workflow.yml) |

## Evidence Preservation

The repository retains:

- every Observatory M1–M22 workflow;
- the M30 archive, registry, dispatch, audit, trace, and visualizer identities;
- the M31 publication, registry, dispatch, audit, trace, and visualizer
  identities;
- source bytes and source-linked normalized records;
- explicitly labeled Observatory-derived reports and views;
- historical benchmarks and current comparison contours;
- all four separate M31 thermal evidence contours;
- focused tests, complete tests, and deterministic failure cases;
- successful and failed GitHub Actions run history.

Later qualification composes earlier boundaries. Source evidence, benchmark
history, workflow history, and deterministic identities remain independently
addressable.

## Versioning and Releases

FRP Trace Observatory has an independent version lifecycle. An Observatory
release identifies the exact Observatory source and the precise upstream FRP
boundaries it qualifies.

Release records preserve:

- Observatory revision and release identity;
- supported upstream milestone and publication identities;
- required archive and document SHA-256 values;
- focused and complete qualification results;
- deterministic audit, trace, and visualizer identities;
- documentation and provenance state.

The current completed implementation boundary is Observatory M22 over FRP
M31. Release artifacts and tags are created only from a fully qualified
repository state.

## License and Attribution

FRP Trace Observatory is licensed under the
[Apache License, Version 2.0](LICENSE).

Attribution, upstream relationship, and evidence-provenance requirements are
recorded in [NOTICE.md](NOTICE.md).

## Author

**Maksym Marnov (Alchimist)**  
Berlin, Germany
