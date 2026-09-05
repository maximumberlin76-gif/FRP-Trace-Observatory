# FRP Trace Observatory Reproducibility Contract

- **Reproducibility status:** Implemented and qualified through the FRP M31 published boundary
- **Runtime:** Python 3.12
- **Runtime dependencies:** Python standard library
- **Canonical processor notation:** `-1/0/1`
- **Current exact verification:** 655 tests, `OK`

Related documents:

- [Usage](usage.md)
- [Integration Contract](integration_contract.md)
- [Supported Schema Registry](supported_schema_registry.md)
- [Normalized Read-Only Data Model](normalized_data_model.md)
- [M31 Published Evidence Boundary](m31_published_boundary.md)

## Purpose

This document defines the inputs, commands, deterministic identities,
cardinalities, preserved values, and acceptance conditions required to
reproduce the implemented FRP Trace Observatory results.

The reproducibility boundary contains three evidence classes:

1. repository-contained base tests and six canonical fixture copies;
2. the exact immutable FRP M30 archive;
3. the exact FRP M31 publication and its provenance sources.

FRP remains the authority for all upstream source values and processor
semantics. Observatory reproduces validation and downstream source-linked
representations from exact published bytes.

## Reproduction Levels

| Level | Inputs | Reproduced result |
|---|---|---|
| Repository | Observatory checkout only | Compilation, base parsers, base registry, controlled fixtures, models, and input-independent tests |
| M30 archive | Observatory checkout plus exact M30 archive | Archive intake, four registrations, seven routes, audit batch, trace dataset, and full-core visualizer dataset |
| M31 publication | Observatory checkout plus clean exact FRP checkout | Four-document intake, six routes, audit batch, two-contour trace dataset, core declaration, 800 frames, and four thermal contours |
| Complete | Both exact upstream inputs | Complete 655-test qualification contour |

An omitted exact upstream input changes only the execution availability of its
integration contour. The test runner still discovers the complete suite and
records that contour as skipped.

## Runtime Record

Run all commands from the Observatory repository root.

Record the exact Observatory revision and Python runtime used for a
reproduction:

```
git rev-parse HEAD
python --version
python -c "import platform; print(platform.platform())"
```

The implemented runtime contract is Python 3.12. The code uses the Python
standard library and requires no installed runtime package set.

Compile the complete source and test tree before qualification:

```
python -m compileall -q \
  artifact_auditor \
  parsers \
  schemas \
  trace_explorer \
  transition_visualizer \
  tests
```

Successful compilation produces exit status `0`.

## Repository-Contained Fixture Boundary

The canonical fixture manifest is:

```
fixtures/canonical_fixture_manifest.json
```

Exact manifest-file identity:

| Property | Exact value |
|---|---:|
| Byte length | 6,219 |
| Raw SHA-256 | `5db01f8a67e7daf33eabd848205ca9cd03a5dba6f944518dfa46a8083d1b348e` |
| Fixture records | 6 |
| Ordering | Lexicographic fixture path |
| Digest scope | Raw source bytes |

Verify the manifest file itself:

```
python -c "from pathlib import Path; import hashlib; p=Path('fixtures/canonical_fixture_manifest.json'); print(len(p.read_bytes())); print(hashlib.sha256(p.read_bytes()).hexdigest())"
```

Expected output:

```
6219
5db01f8a67e7daf33eabd848205ca9cd03a5dba6f944518dfa46a8083d1b348e
```

The six canonical fixture copies are:

| Local fixture | Bytes | Raw SHA-256 |
|---|---:|---|
| `fixtures/comparative_architecture/normalized_cost_profile_v1.json` | 677 | `bd2f5bfc4f0430c2764c5f1ddb1258d176b42f1667d1f0f691e40730ddc4c979` |
| `fixtures/comparative_architecture/reference_comparison_seed_76.json` | 21,988 | `c27c4ecbe755df784b6fcb25d5549b719fd98dcf3821f280b7550f1669e8d76e` |
| `fixtures/comparative_architecture/thermal_proxy_profile_v1.json` | 517 | `aeafebc3e71d1311a3445bd1528cbe7322546f79d6a5099dfed3a9590fc4a25b` |
| `fixtures/comparative_architecture/workload_profile_v1.json` | 174 | `5680c50220a751ea748e55644dd3a189321ca8e89398bb3751a471556dce94b9` |
| `fixtures/hardware_sensitivity/hardware_sensitivity_cost_profile_v1.json` | 15,360 | `79c1c17c924bde6947dce477c2b8b64600684c993e7f42c1f00f6ffca0228a1c` |
| `fixtures/hardware_sensitivity/reference_comparison_seed_76_hardware_sensitivity_v1.json` | 81,632 | `f91ae25e06f5ae8024b8847c7aa4c9ac0ae77d78b3b912b1cf882d4dc52b346d` |

Verify manifest parsing and all six source copies:

```
python -m unittest \
  tests.test_fixture_manifest \
  tests.test_fixture_validator \
  -v
```

The validator checks exact path binding, byte length, raw SHA-256, embedded
identity where present, measurement contour, mode eligibility, ordering, and
mutation-failure cases.

## M30 Input Identity

Set the M30 input to the exact immutable archive:

```
export FRP_M30_ARCHIVE_PATH=/absolute/path/to/frp-v3.2.0-m30-archival-release.tar.gz
```

Required archive identity:

| Property | Exact value |
|---|---|
| Relative FRP path | `artifacts/m30/packages/frp-v3.2.0-m30-archival-release.tar.gz` |
| Release root | `Fractal-Resonance-Processor-FRP-v3.2.0` |
| Source commit | `ff3dd434da5dcbd9e8fa62444f658ed4c495b540` |
| Byte length | 10,189,989 |
| Raw SHA-256 | `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa` |
| Archive entries | 519 |
| Manifested source members | 518 |

Verify the configured archive bytes before Observatory intake:

```
python -c "from pathlib import Path; import hashlib, os; p=Path(os.environ['FRP_M30_ARCHIVE_PATH']); b=p.read_bytes(); print(len(b)); print(hashlib.sha256(b).hexdigest())"
```

Expected output:

```
10189989
05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa
```

## M30 Reproduction Sequence

Run the exact stages in dependency order:

```
python -m artifact_auditor.m30_archive_intake \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m artifact_auditor.m30_published_boundary_intake \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m schemas.m30_published_registry \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m parsers.m30_published_member_intake \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m parsers.m30_published_dispatch \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m artifact_auditor.m30_published_auditor \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m trace_explorer.m30_published_trace_explorer \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m transition_visualizer.m30_published_transition_visualizer \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

Required M30 results:

| Stage | Required result |
|---|---|
| Registry | 4 registrations, 7 exact routes |
| Artifact Auditor | 4 reports, 69 checks, 0 failed checks |
| Trace Explorer | 4 records, 32 cell snapshots, 8 requests |
| Full-core source evidence | 2 contours, 100 trace records |
| Transition Visualizer | 800 transition frames |

Required M30 deterministic identities:

| Identity | Exact value |
|---|---|
| Audit batch SHA-256 | `aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03` |
| Trace dataset id | `4191b36e-9168-5fc7-a4b5-cbc3b480136f` |
| Trace source-record digest | `4b2e8aec64a0b3cb76d0819383ed66d306b8e50dc3feb7bb8c6c76486cd83d57` |
| Trace dataset SHA-256 | `4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd` |
| Full-core evidence id | `7c935011-c734-5f6b-b312-dc476ad99724` |
| Full-core evidence SHA-256 | `b481d787fdef17992ed3236b4a7b1b142634b944ebb0048f4b77d3def089edd2` |
| Visualizer dataset id | `68de3476-2e03-5506-93ea-062c3744e90d` |
| Visualizer dataset SHA-256 | `7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b` |

## M31 Input Identity

Set the M31 input to a clean FRP repository root:

```
export FRP_M31_UPSTREAM_ROOT=/absolute/path/to/Fractal-Resonance-Processor
```

The root must contain the exact four-document publication:

| Role | Exact relative path | Bytes | Raw SHA-256 |
|---|---|---:|---|
| Formal schema | `schemas/m31/frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json` | 1,468 | `53d79d45d70753ccd24c3dc4c97af6fee481f86a9d7cdca7ef78b486c76479f7` |
| Evidence | `artifacts/m31/evidence/m31-phase-interference-active-zero-thermal-evidence.json` | 39,993 | `bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42` |
| Manifest | `artifacts/m31/manifests/m31-phase-interference-active-zero-thermal-evidence-manifest.json` | 828 | `80f0841d0041cd22c2f76175b6139e601aede7b69823356ae1fefbce5f793e7c` |
| Qualification | `artifacts/m31/qualification/m31-phase-interference-active-zero-thermal-evidence-qualification.json` | 1,512 | `4c2446f954e01ec0aa37cc6c0fc70cf4a87ec565c450628e31b0efcac9160224` |

Verify all four publication files directly:

```
python - <<'PY'
from hashlib import sha256
from pathlib import Path
import os

root = Path(os.environ["FRP_M31_UPSTREAM_ROOT"])
expected = {
    "schemas/m31/frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json": (
        1468,
        "53d79d45d70753ccd24c3dc4c97af6fee481f86a9d7cdca7ef78b486c76479f7",
    ),
    "artifacts/m31/evidence/m31-phase-interference-active-zero-thermal-evidence.json": (
        39993,
        "bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42",
    ),
    "artifacts/m31/manifests/m31-phase-interference-active-zero-thermal-evidence-manifest.json": (
        828,
        "80f0841d0041cd22c2f76175b6139e601aede7b69823356ae1fefbce5f793e7c",
    ),
    "artifacts/m31/qualification/m31-phase-interference-active-zero-thermal-evidence-qualification.json": (
        1512,
        "4c2446f954e01ec0aa37cc6c0fc70cf4a87ec565c450628e31b0efcac9160224",
    ),
}

for relative_path, (expected_length, expected_sha256) in expected.items():
    payload = (root / relative_path).read_bytes()
    observed = (len(payload), sha256(payload).hexdigest())
    required = (expected_length, expected_sha256)
    if observed != required:
        raise SystemExit(f"MISMATCH {relative_path}: {observed!r}")
    print(f"PASS {relative_path}")
PY
```

Expected output contains four `PASS` lines in the declared order.

## M31 Provenance Identity

The evidence document binds 12 provenance sources. Ten historical sources
must match members inside the exact M30 archive. The archive container and
post-archive qualification workflow retain separate roles.

| Provenance class | Records |
|---|---:|
| Verified historical M30 members | 10 |
| M30 archive container | 1 |
| Post-archive qualification source | 1 |
| Total | 12 |

The two trace-bearing historical members are:

| Contour | Relative path | Records | Raw SHA-256 |
|---|---|---:|---|
| RTL execution | `artifacts/m19/execution/m16-rtl-execution-trace.json` | 96 | `d7945e0d2b5aaa05c5fff2e4e60d3b984017f7e4ae1984c55920368a110020bd` |
| FPGA preparation | `artifacts/m19/execution/m16-fpga-preparation-execution-trace.json` | 4 | `7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f` |

The complete 12-source path, length, and digest inventory is recorded in
[M31 Published Evidence Boundary](m31_published_boundary.md).

## M31 Reproduction Sequence

Run the exact stages in dependency order:

```
python -m artifact_auditor.m31_published_boundary_intake \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m schemas.m31_published_registry \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m parsers.m31_published_dispatch \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m artifact_auditor.m31_published_auditor \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m trace_explorer.m31_published_trace_explorer \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m transition_visualizer.m31_published_transition_visualizer \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"
```

Required M31 results:

| Stage | Required result |
|---|---|
| Boundary intake | 4 documents, 12 provenance sources, 10 verified historical archive members |
| Registry | 4 registrations, 6 exact routes |
| Artifact Auditor | 4 reports, 47 checks, 0 failed checks |
| Trace Explorer | 2 contours, 100 records, 800 cell snapshots, 200 requests |
| Transition Visualizer | 800 frames, 4 separate thermal contours |

Required M31 deterministic identities:

| Identity | Exact value |
|---|---|
| Audit batch SHA-256 | `3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591` |
| Trace dispatch SHA-256 | `f34b867fabcaab51515ecca39f2eb7287f52aa218d3ac48596a1481326009630` |
| Trace dataset id | `0f0f0f7e-0409-5e7b-8c76-2f72bb954321` |
| Trace dataset SHA-256 | `ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff` |
| Core declaration id | `32490746-831a-5667-9b11-27d6673cf893` |
| Core source-record SHA-256 | `05c98cfb19ec7ef85f0fab47bf80e2c2330e4595255411d366269a511b5c0b9a` |
| Visualizer dispatch SHA-256 | `ff4597411a781c814ab8ef009d30739857411d2a31ff34839d3060b478a697e8` |
| Visualizer dataset id | `63a1feb9-1835-579e-ab00-eec4569e8ff3` |
| Visualizer dataset SHA-256 | `0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304` |

## M31 Structural Reproduction

The reproduced trace dataset must retain:

- 96 RTL records;
- 4 FPGA-preparation records;
- 800 source-linked cell snapshots;
- 200 request records;
- 100 invariant-pass records;
- 702 retained active-zero observations;
- scheduler-mode counts `free = 19`, `7/1 = 64`, `1/7 = 17`;
- scheduler-state counts `balance = 56`, `commit = 8`, `excite = 3`,
  `free = 19`, `neutralize = 14`;
- the observed state domain `-1/0/1`;
- zero direct opposite transitions.

The reproduced transition inventory must equal:

| Classification | Count |
|---|---:|
| `retained_same` | 783 |
| `polarity_to_active_zero` | 5 |
| `active_zero_to_polarity` | 12 |
| `direct_opposite` | 0 |

The reproduced route-leg inventory must equal:

| Route leg | Count |
|---|---:|
| `non_route_transition` | 790 |
| `first_leg_to_active_zero` | 5 |
| `pending_route_completion` | 5 |

## Thermal Contour Reproduction

The four M31 thermal contours remain separate source-linked records:

| Contour | Group | Payload SHA-256 |
|---|---|---|
| `historical_release_benchmark` | historical | `8ae48a85c971d6fe8d136fd08b45ac7d801c6146c82eab2ac785c4e8318cb140` |
| `current_comparative_baseline` | current | `c7a66b2a99608b51508cc249459917d23ffebc4258501afd8567ca99afff6add` |
| `current_hardware_sensitivity` | current | `9b8a709f65e156b160facfb977a8b7362b928344dc45c840ef4b9eae637313a0` |
| `current_thermal_profile` | current | `1c92e0fbfb54f19803c70970b0dbf135c4bb37121a34407d64639ad6a3582eee` |

All four records carry `physical_temperature_measurement = false`. Their
published proxy and benchmark payloads remain unmerged and unnormalized.

## Complete Test Reproduction

Configure both exact inputs:

```
export FRP_M30_ARCHIVE_PATH=/absolute/path/to/frp-v3.2.0-m30-archival-release.tar.gz
export FRP_M31_UPSTREAM_ROOT=/absolute/path/to/Fractal-Resonance-Processor
```

Run the complete suite:

```
python -m unittest discover -s tests -p 'test_*.py' -q
```

Required result:

```
Ran 655 tests

OK
```

Run the 26-test M31 end-to-end contour independently:

```
python -m unittest \
  tests.test_m31_published_observatory_end_to_end \
  -v
```

Run the M30 exact publication contour independently:

```
python -m unittest \
  tests.test_m30_published_registry \
  tests.test_m30_published_member_intake \
  tests.test_m30_published_dispatch \
  tests.test_m30_published_auditor \
  tests.test_m30_published_trace_explorer \
  tests.test_m30_published_transition_visualizer \
  -v
```

## Deterministic and Run-Scoped Values

| Value class | Reproduction rule |
|---|---|
| Raw source SHA-256 | Identical for identical source bytes |
| Registry compatibility key | Identical for the same exact registered identity |
| M30 and M31 dispatch SHA-256 | Identical for the same canonical source and route |
| M30 and M31 report SHA-256 | Identical for the same qualified report payload |
| Source-record and contour SHA-256 | Identical for the same ordered source records |
| M30 and M31 dataset SHA-256 | Identical for the same complete canonical dataset |
| Deterministic dataset UUID | Identical for the same registered identity material |
| Base `SourceArtifact.source_artifact_id` | New load identity for each capture |
| Base `RawSourceDigest.digest_record_id` | New digest-record identity for each capture |
| Base audit identity and timestamps | Run-scoped unless explicitly supplied by the caller |
| Audit serialization | Deterministic for one complete immutable report object |
| GitHub Actions run number and wall-clock time | Execution metadata, outside semantic identity |

Two loads of identical bytes therefore share the raw SHA-256 while retaining
separate load identities. Reproduction compares deterministic content and
contract identities, not per-load or wall-clock metadata.

## Mutation and Negative Controls

The test matrix requires failure for applicable mutations of:

- source bytes;
- byte length;
- raw SHA-256;
- schema, format, kind, role, milestone, version, or status;
- registered source path;
- archive membership;
- provenance membership;
- registry route or mode eligibility;
- canonical-object identity;
- record ordering;
- record, frame, contour, or route cardinality;
- scheduler counts;
- ternary state domain;
- active-zero role inventory;
- transition classification;
- thermal-contour identity;
- deterministic aggregate digest.

A failed exact check stops the applicable downstream construction. The source
is retained as observed and is not repaired or assigned a replacement
identity.

## Reproducibility Acceptance Matrix

| Gate | Acceptance condition |
|---|---|
| Runtime | Python reports major/minor version 3.12 |
| Compilation | Complete source and test tree compiles with exit status `0` |
| Base fixtures | Six records match exact paths, lengths, identities, and raw digests |
| M30 archive | Length, archive digest, 519 entries, and 518 manifested members match |
| M30 registry | Four canonical registrations and seven routes match |
| M30 audit | Four reports, 69 checks, zero failures, exact batch digest |
| M30 trace and visualizer | Exact record counts, dataset ids, and dataset digests match |
| M31 publication | Four documents and all exact path, length, identity, and digest bindings match |
| M31 provenance | 12 sources and ten verified historical archive members match |
| M31 registry | Four canonical registrations and six routes match |
| M31 audit | Four reports, 47 checks, zero failures, exact batch digest |
| M31 trace | Two contours, 100 records, 800 cells, 200 requests, exact dataset identity |
| M31 visualizer | 800 frames, four thermal contours, exact dataset identity |
| Complete suite | 655 tests complete with `OK` |

## Preservation Requirements

Every accepted reproduction preserves:

1. original source bytes;
2. raw source digests;
3. source and archive paths;
4. registry and route identities;
5. source ordering and source coordinates;
6. the canonical state notation `-1/0/1`;
7. active computational state `0`;
8. separate `-1 → 0 → 1` and `1 → 0 → -1` route legs;
9. separate scheduler modes and scheduler states;
10. separate RTL and FPGA-preparation contours;
11. separate historical and current thermal contours;
12. complete M30 and M31 evidence ancestry;
13. distinct source, normalized, and Observatory-derived representations;
14. the one-way FRP-to-Observatory integration boundary.

## Reproduction Record Template

Record these values with each independent reproduction:

```
observatory_commit=<git rev-parse HEAD>
python_version=<python --version>
platform=<python platform string>
m30_archive_bytes=10189989
m30_archive_sha256=05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa
m31_registry_revision=m31-published-boundary-v1
m31_audit_batch_sha256=3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591
m31_trace_dataset_sha256=ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff
m31_visualizer_dataset_sha256=0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304
tests_run=655
test_result=OK
```

## Author

Maksym Marnov (Alchimist)  
Berlin, Germany
