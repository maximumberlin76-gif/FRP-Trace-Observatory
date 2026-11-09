# FRP Trace Observatory

FRP Trace Observatory reads published [Fractal Resonance Processor (FRP)](https://github.com/maximumberlin76-gif/Fractal-Resonance-Processor-FRP-Ternary-Resonant-Coherence-Processor) artifacts. The Artifact Auditor checks publication identities, Trace Explorer exposes ordered records, and the Ternary Transition Visualizer reconstructs cell timelines from captured states and route markers.

## Qualification and release

| Scope | Evidence |
|---|---|
| Observatory M26 on `main` | [Run 42709869404, attempt 1](https://github.com/maximumberlin76-gif/FRP-Trace-Observatory/actions/runs/42709869404/attempts/1) at `1cb3feb6f78ce319ff3257a1c2fcab49eaf25da6`. Python 3.12, 691 tests passed, zero skips, failures or errors. |
| Archived Observatory release | [v1.0.3](https://github.com/maximumberlin76-gif/FRP-Trace-Observatory/releases/tag/v1.0.3), Observatory M22 over FRP M31, including the M30 evidence chain. The release suite passed 655 tests. |

## M32 publication and trace data

M26 reads the formal schema, trace bundle, manifest and qualification document from FRP publication commit `874dbb954f690e405e8ce702ae3b40ea5a77d078`. It reads the 29 source files from the commit recorded in that manifest, `c0bc0fbc2c1c2e500b19d0ba84b3431a813e3941`. The raw trace bundle SHA-256 is `62d8c1e6d205b9262a5c950883d3259275d5049f7a896ae12956a210cb75b7e0`.

The M32 publication registry routes all four documents to the auditor and the trace bundle to both viewing modes. Each source tick in this eight-cell publication contains one sample, one bank record, two request records and eight cell records.

| Scheduler | Source ticks | Monitor records | Cell observations | Cell 0 enters active zero | Cell 0 completes the route |
|---|---:|---:|---:|---:|---:|
| `7/1` | 0–15 | 192 | 128 | Tick 9 | Tick 15 |
| `1/7` | 0–16 | 204 | 136 | Tick 10 | Tick 16 |

Across both traces, 238 of 264 cell observations carry `active_zero`. In each mode, cell 0 takes the route `+1 → 0 → −1`, retaining a pending target of `−1` at active zero until the second leg. The published trace reports zero direct opposite transitions, reserved-state events and queue overflow events.

## Reproduce M26

Open the [manual M26 workflow](.github/workflows/frp-observatory-m26-m32-revision-intake.yml) in Actions, select the branch and choose **Run workflow**. The artifact includes the Observatory commit, Python version, intake report, intake error log, test counts, verbose test log and a SHA-256 manifest. From the extracted artifact directory, run:

    sha256sum -c SHA256SUMS

To inspect M32 locally, use Python 3.12 and Git. Run the following commands from the Observatory repository root with an FRP checkout at `../frp` containing both commits above.

    export FRP_ROOT=../frp
    export FRP_PUBLICATION=874dbb954f690e405e8ce702ae3b40ea5a77d078

    python -m artifact_auditor.m32_revision_intake \
      --upstream-root "$FRP_ROOT" --publication-commit "$FRP_PUBLICATION"

    python -m schemas.m32_published_registry \
      --upstream-root "$FRP_ROOT" --publication-commit "$FRP_PUBLICATION"

    python -m trace_explorer.m32_published_trace_explorer \
      --upstream-root "$FRP_ROOT" --publication-commit "$FRP_PUBLICATION" \
      --scheduler-mode 7/1 --source-tick 9

    python -m transition_visualizer.m32_published_transition_visualizer \
      --upstream-root "$FRP_ROOT" --publication-commit "$FRP_PUBLICATION" \
      --scheduler-mode 1/7 --source-cell 0

Omit `--source-tick` to read the entire selected trace. The cell timeline includes the previous and current retained states, active zero, pending status and target, and both route-leg flags. At the first observation the previous retained state is JSON `null`; retained state `0` denotes an observed processor state.

The [routine CI workflow](.github/workflows/observatory-ci.yml) compiles the Python modules and runs repository test discovery. M26 configures the external M30 archive, the M31 publication and the M32 source and publication revisions for the complete suite.

## Earlier qualification records

| Boundary | Qualified result | Reference |
|---|---|---|
| M31 / Observatory M22 | 4 documents, 6 routes, 47 audit checks, 100 trace records and 800 transition frames. The 26 focused tests passed. | [M31 published boundary](docs/m31_published_boundary.md) |
| M30 / Observatory M8B | 519 archive entries, 518 manifested members, 7 registry routes and 69 audit checks. | [M8B workflow](.github/workflows/frp-observatory-m8b-full-core-transition-visualizer-qualification-workflow.yml) |

The [historical qualification tables](https://github.com/maximumberlin76-gif/FRP-Trace-Observatory/blob/b8d04323f620df9011215004a0eab9f4c1a3f341/README.md) retain the M30 and M31 dataset hashes, M31 thermal evidence contours, exact commands and release metadata.

## Documentation and citation

- [Usage](docs/usage.md), [reproducibility](docs/reproducibility.md) and [CI](docs/ci.md)
- [Integration contract](docs/integration_contract.md), [normalized data model](docs/normalized_data_model.md) and [schema registry](docs/supported_schema_registry.md)
- [Milestone history](docs/milestones.md), [changelog](CHANGELOG.md) and [contributing](CONTRIBUTING.md)

**Maksym Marnov (Alchimist)** · Berlin, Germany. [Apache License 2.0](LICENSE) · [Attribution](NOTICE.md).

Cite the archived v1.0.3 release using its [version DOI](https://doi.org/10.5281/zenodo.22537600) and [citation metadata](CITATION.cff). The [concept DOI](https://doi.org/10.5281/zenodo.22537599) identifies the Observatory release series.
