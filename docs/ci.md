# FRP Trace Observatory CI and Manual Qualification Workflows

- **CI status:** Implemented and passing through the FRP M31 published boundary
- **Workflow inventory:** 27 retained workflows
- **Routine repository CI:** push, pull request, and manual dispatch
- **Milestone publication workflows:** manual dispatch from `main`
- **Runtime:** Python 3.12
- **Current exact verification:** 655 tests, `OK`

Related documents:

- [Usage](usage.md)
- [Reproducibility Contract](reproducibility.md)
- [Integration Contract](integration_contract.md)
- [Supported Schema Registry](supported_schema_registry.md)
- [M31 Published Evidence Boundary](m31_published_boundary.md)

## Purpose

This document defines the continuous-integration boundary, manual workflow
operation, permissions, retained milestone history, exact upstream checkout,
verification gates, and failure behavior of FRP Trace Observatory.

The repository contains two workflow classes:

1. one routine read-only repository-verification workflow;
2. 26 retained milestone workflows that installed or qualified the exact M30
   and M31 Observatory implementation in ordered manual stages.

The milestone workflows remain part of the implementation and evidence
history. Routine commits use the repository-verification workflow.

## Workflow Classes

| Class | Workflows | Trigger | Repository permission | Function |
|---|---:|---|---|---|
| Routine repository CI | 1 | `push`, `pull_request`, `workflow_dispatch` | `contents: read` | Compile and test the current repository |
| M30 milestone publication | 12 | `workflow_dispatch` | `contents: write` | Install and qualify M1–M8B increments |
| M31 boundary qualification | 1 | `workflow_dispatch` | `contents: read` | Qualify the exact M31 publication before source installation |
| M31 milestone publication | 13 | `workflow_dispatch` | `contents: write` | Install and qualify M10–M22 increments |
| **Total** | **27** | Mixed as declared above | Per-workflow minimum | Complete retained CI history |

The M30 milestone count includes M7A, M7B, M8A1, M8A2, M8A3, and M8B as
separate ordered increments. The M31 publication count includes source, test,
and terminal end-to-end stages.

## Routine Repository CI

Workflow path:

```
.github/workflows/observatory-ci.yml
```

Workflow name:

```
FRP Trace Observatory CI
```

Triggers:

- push to `main`;
- pull request targeting `main`;
- manual `workflow_dispatch`.

Permissions:

```
contents: read
```

Job environment:

| Property | Exact value |
|---|---|
| Runner | `ubuntu-latest` |
| Python | `3.12` |
| Timeout | 10 minutes |
| Job name | `Verify repository` |
| Persisted checkout credentials | false |

The job performs two verification stages:

```
python -m compileall -q \
  artifact_auditor \
  parsers \
  schemas \
  trace_explorer \
  transition_visualizer \
  tests
```

```
python -m unittest discover -s tests -v
```

The current repository discovers 655 tests. Tests bound to an unavailable
external exact upstream input are marked skipped; all repository-contained
and configured contours execute normally.

## Manual GitHub Operation

Every M1–M22 milestone workflow uses `workflow_dispatch`. Run it through the
GitHub Actions interface:

1. open the repository;
2. open **Actions**;
3. select the exact workflow name;
4. select **Run workflow**;
5. select branch `main`;
6. start the run once;
7. wait for the complete run result;
8. inspect the first failed step when the result is red.

A commit or file upload does not start a milestone workflow. Pushes to `main`
start only workflows that declare a `push` trigger, including routine
`FRP Trace Observatory CI`.

## Manual Main-Branch Gate

All milestone workflows are declared with:

```
on:
  workflow_dispatch:
```

Each milestone workflow verifies execution from branch `main`. M10–M22 also
verify the GitHub event name explicitly before installation or publication.

An incorrect branch or event terminates the job before source installation,
qualification, commit, or publication.

## Upstream Checkout Boundary

Milestone workflows check out the FRP upstream repository from:

```
maximumberlin76-gif/Fractal-Resonance-Processor-FRP-Ternary-Resonant-Coherence-Processor
```

Upstream ref:

```
main
```

Checkout layout:

| Repository | Workflow path | Credential behavior |
|---|---|---|
| FRP Trace Observatory | `observatory` | Write credentials retained only by publication workflows |
| FRP upstream | `upstream` | `persist-credentials: false` |

The upstream checkout supplies exact published source bytes. Publication
workflows commit only their declared Observatory files. M9 and routine CI use
read-only Observatory credentials.

## M30 Milestone Workflow Inventory

| Stage | Workflow file | Published or qualified increment |
|---|---|---|
| M1 | `frp-observatory-m1-m30-archive-intake-workflow.yml` | Exact immutable M30 archive intake source |
| M2 | `frp-observatory-m2-published-boundary-intake-workflow.yml` | Exact M28–M30 published-boundary intake source |
| M3 | `frp-observatory-m3-published-registry-routing-workflow.yml` | Four-member M30 registry, seven routes, and tests |
| M4 | `frp-observatory-m4-published-member-intake-workflow.yml` | Strict read-only intake of four M30 members and tests |
| M5 | `frp-observatory-m5-published-dispatch-boundary-workflow.yml` | Seven immutable member-to-mode dispatch envelopes and tests |
| M6 | `frp-observatory-m6-published-artifact-auditor-workflow.yml` | Four-report M30 Artifact Auditor source and tests |
| M7A | `frp-observatory-m7a-published-trace-explorer-source-workflow.yml` | M30-published M16 Trace Explorer source |
| M7B | `frp-observatory-m7b-published-trace-explorer-qualification-workflow.yml` | M30-published M16 Trace Explorer qualification tests |
| M8A1 | `frp-observatory-m8a-full-core-transition-visualizer-source-workflow.yml` | Full-core visualizer payload segment 1 of 3 |
| M8A2 | `frp-observatory-m8a2-full-core-transition-visualizer-source-workflow.yml` | Full-core visualizer payload segment 2 of 3 |
| M8A3 | `frp-observatory-m8a3-full-core-transition-visualizer-source-workflow.yml` | Exact full-core source assembly and staged-payload removal |
| M8B | `frp-observatory-m8b-full-core-transition-visualizer-qualification-workflow.yml` | Full-core Transition Visualizer qualification tests |

The M8 source payload was divided into three workflow stages to preserve exact
transport and assembly boundaries. M8A3 validates the assembled source before
removing only the temporary staged payload segments.

## M30 Qualification Gates

The M30 workflow chain verifies:

- the 10,189,989-byte archive;
- archive SHA-256
  `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa`;
- 519 archive entries and 518 manifested source members;
- four exact published-member registrations;
- seven exact member-to-mode routes;
- four Artifact Auditor reports and 69 ordered checks;
- four Trace Explorer records, 32 cell snapshots, and eight requests;
- two full-core trace contours and 100 trace records;
- 800 transition frames;
- the `-1/0/1` state domain;
- separate `free`, `1/7`, and `7/1` scheduler modes;
- deterministic M30 dataset identities and digests.

## M31 Milestone Workflow Inventory

| Stage | Workflow file | Published or qualified increment |
|---|---|---|
| M9 | `frp-observatory-m9-m31-published-boundary-intake-workflow.yml` | Read-only qualification of the exact M31 publication boundary |
| M10 | `frp-observatory-m10-m31-published-boundary-source-workflow.yml` | Integrity-bound M31 publication-intake source |
| M11 | `frp-observatory-m11-m31-published-boundary-tests-workflow.yml` | M31 publication-intake tests |
| M12 | `frp-observatory-m12-m31-published-registry-source-workflow.yml` | Exact four-document M31 registry source |
| M13 | `frp-observatory-m13-m31-published-registry-tests-workflow.yml` | M31 registry and route tests |
| M14 | `frp-observatory-m14-m31-published-dispatch-source-workflow.yml` | Exact M31 document-to-mode dispatch source |
| M15 | `frp-observatory-m15-m31-published-dispatch-tests-workflow.yml` | M31 dispatch tests |
| M16 | `frp-observatory-m16-m31-published-auditor-source-workflow.yml` | Four-report M31 Artifact Auditor source |
| M17 | `frp-observatory-m17-m31-published-auditor-tests-workflow.yml` | M31 Artifact Auditor tests |
| M18 | `frp-observatory-m18-m31-published-trace-explorer-source-workflow.yml` | Two-contour M31 Trace Explorer source |
| M19 | `frp-observatory-m19-m31-published-trace-explorer-tests-workflow.yml` | M31 Trace Explorer tests |
| M20 | `frp-observatory-m20-m31-published-transition-visualizer-source-workflow.yml` | M31 Ternary Transition Visualizer source |
| M21 | `frp-observatory-m21-m31-published-transition-visualizer-tests-workflow.yml` | M31 Ternary Transition Visualizer tests |
| M22 | `frp-observatory-m22-m31-published-end-to-end-qualification-workflow.yml` | Complete 26-test M31 end-to-end qualification |

M9 is a read-only boundary gate. M10–M22 publish ordered source or test
increments only after verifying the exact preceding boundary.

## M31 Qualification Gates

The M31 workflow chain verifies:

- four exact publication documents;
- exact path, identity field, identity value, kind, byte length, and raw
  SHA-256 for each document;
- 12 provenance sources;
- ten verified historical members of the immutable M30 archive;
- four registry records and six exact document-to-mode routes;
- four Artifact Auditor reports and 47 ordered checks;
- two trace contours, 100 records, 800 cell snapshots, and 200 requests;
- 100 invariant-pass records;
- 702 retained active-zero observations;
- 800 source-linked transition frames;
- four separate thermal evidence contours;
- zero direct opposite transitions;
- the complete 26-test M31 end-to-end contour;
- deterministic audit, dispatch, trace, core, contour, frame, and visualizer
  identities.

## M31 Route Matrix

| Published role | Artifact Auditor | Trace Explorer | Ternary Transition Visualizer |
|---|---:|---:|---:|
| Formal schema | 1 | 0 | 0 |
| Evidence | 1 | 1 | 1 |
| Manifest | 1 | 0 | 0 |
| Qualification | 1 | 0 | 0 |
| **Total** | **4** | **1** | **1** |

## Workflow Dependency Order

The retained workflow order is:

```
M1
→ M2
→ M3
→ M4
→ M5
→ M6
→ M7A
→ M7B
→ M8A1
→ M8A2
→ M8A3
→ M8B
→ M9
→ M10
→ M11
→ M12
→ M13
→ M14
→ M15
→ M16
→ M17
→ M18
→ M19
→ M20
→ M21
→ M22
```

Every publication workflow verifies the files or evidence required from its
preceding stage before adding the next declared increment.

## Permissions Model

### Routine CI

```
permissions:
  contents: read
```

Routine CI compiles and tests without repository publication.

### M9 boundary qualification

```
permissions:
  contents: read
```

M9 validates both repository checkouts and proves they remain unchanged.

### Publication workflows

```
permissions:
  contents: write
```

Write permission is used only to commit and push the exact Observatory files
declared by that workflow. The FRP upstream checkout retains no credentials.

## Concurrency Model

Every milestone workflow declares a stage-specific concurrency group and:

```
cancel-in-progress: false
```

This preserves an active qualification run and prevents a later invocation
from cancelling its evidence-generating predecessor. Concurrency groups are
separate between milestone stages.

## Commit and Publication Boundary

Publication workflows follow this order:

1. check out Observatory `main`;
2. check out FRP upstream `main` read-only;
3. set up Python 3.12;
4. enforce manual execution from `main`;
5. verify the exact preceding Observatory boundary;
6. verify the applicable upstream identity;
7. install only the declared source or test increment;
8. compile and run focused plus complete tests;
9. commit only the declared Observatory files;
10. publish the milestone summary.

M9 performs qualification without a commit stage. M8A1 and M8A2 stage exact
payload segments; M8A3 assembles the final source and removes those temporary
segments after exact verification.

## Current Acceptance Identities

| Boundary | Exact identity |
|---|---|
| M30 archive SHA-256 | `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa` |
| M30 audit batch SHA-256 | `aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03` |
| M30 trace dataset SHA-256 | `4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd` |
| M30 visualizer dataset SHA-256 | `7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b` |
| M31 audit batch SHA-256 | `3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591` |
| M31 trace dataset SHA-256 | `ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff` |
| M31 visualizer dataset SHA-256 | `0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304` |

## Local Equivalence Command

With both exact upstream inputs configured:

```
export FRP_M30_ARCHIVE_PATH=/absolute/path/to/frp-v3.2.0-m30-archival-release.tar.gz
export FRP_M31_UPSTREAM_ROOT=/absolute/path/to/Fractal-Resonance-Processor
python -m unittest discover -s tests -p 'test_*.py' -q
```

Qualified result:

```
Ran 655 tests

OK
```

Detailed input verification and independent reproduction commands are defined
in [Reproducibility Contract](reproducibility.md).

## Failure Interpretation

| Failure location | Meaning |
|---|---|
| Checkout | Required repository or ref was unavailable |
| Manual branch gate | Workflow was not run manually from `main` |
| Predecessor verification | Required prior milestone file or digest differed |
| Upstream identity | Required FRP path, length, digest, or publication identity differed |
| Payload installation | Embedded source transport or assembly failed integrity validation |
| Compilation | Installed or existing Python source did not compile |
| Focused tests | The current milestone contract failed |
| Complete tests | A repository regression was detected |
| Preservation check | Observatory or upstream changed outside the declared boundary |
| Commit and push | Publication permission or concurrent repository state prevented publication |

The first red step is the primary failure location. Later skipped steps are a
consequence of that earlier failure and do not form independent evidence.

## History Preservation

The workflow inventory preserves:

- every M1–M22 implementation increment;
- the split M7 and M8 stages;
- exact predecessor digests and cardinalities;
- exact upstream M30 and M31 identities;
- focused qualification commands;
- complete regression commands;
- commit boundaries;
- GitHub Actions run summaries;
- successful and failed historical runs.

Later qualification does not replace earlier workflow history. M22 closes the
complete M31 route while retaining M1–M21 as its ordered evidence chain.

## Workflow Change Requirements

A workflow change requires:

1. preservation of its historical milestone role;
2. an explicit trigger and branch boundary;
3. minimum required permissions;
4. read-only FRP upstream checkout;
5. exact predecessor verification where applicable;
6. exact upstream path, length, and digest verification where applicable;
7. Python 3.12 compilation;
8. focused qualification tests;
9. complete repository regression;
10. declared commit scope for publication workflows;
11. preservation checks before publication;
12. synchronized CI, usage, reproducibility, integration, registry, and data
    model documentation.

## Author

Maksym Marnov (Alchimist)  
Berlin, Germany
