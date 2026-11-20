# FRP Trace Observatory v1.1.0 — M32 Trace Qualification

FRP Trace Observatory v1.1.0 adds support for the M32 trace publication from [FRP 3.4.0-rc.2](https://doi.org/10.5281/zenodo.24392460). The previous Observatory release, v1.0.3, qualified the M31 publication. This version adds M32 to the complete suite alongside M30 and M31.

## What changed

- The Artifact Auditor reads four M32 documents from a specified FRP commit: the schema, trace bundle, manifest and qualification report. It verifies the 29 source files against the revision recorded in the manifest.
- The M32 registry routes all four documents to the auditor and the trace bundle to both viewing tools.
- Trace Explorer selects monitor records by scheduler mode and source tick. The Ternary Transition Visualizer reconstructs a selected cell's retained state, active zero, pending target and route legs over time.

## Qualification

[Observatory M26, run 44696283039, attempt 1](https://github.com/maximumberlin76-gif/FRP-Trace-Observatory/actions/runs/44696283039/attempts/1) ran at Observatory commit `185417190701ada0c177671302d8e8341d5e052f` with Python 3.12.16. All **691/691** discovered tests passed. The inventory and verbose log contain the same 691 distinct test IDs in the same order. Skips, failures, errors, expected failures and unexpected successes were all zero.

| M32 input | Verified identity |
|---|---|
| FRP commit supplying the four published documents | `1eaca5c65c771dea750a1c2b772e559ca2c5e3b2` |
| Source commit recorded in the M32 manifest | `c0bc0fbc2c1c2e500b19d0ba84b3431a813e3941` |
| Published trace bundle SHA-256 | `62d8c1e6d205b9262a5c950883d3259275d5049f7a896ae12956a210cb75b7e0` |

## Observed M32 traces

| Scheduler | Source ticks | Monitor records | Cell observations | Cell 0 enters active zero | Cell 0 reaches −1 |
|---|---:|---:|---:|---:|---:|
| `7/1` | 16 | 192 | 128 | Tick 9 | Tick 15 |
| `1/7` | 17 | 204 | 136 | Tick 10 | Tick 16 |

The two eight-cell traces contain 396 monitor records across 33 source ticks. Active zero occurs in 238 of 264 cell observations. In both modes, cell 0 follows `+1 → 0 → −1` and retains the pending target `−1` at active zero. Across the two traces, the auditor reports zero direct opposite transitions, zero reserved-state events and zero queue overflows.

The qualification archive `frp-observatory-m26-44696283039-1.zip` has SHA-256 `79aaae12fa95653fb69294c70fcf6efbc7eaab0d1429f6d873122bc963158e0f`. To verify all eight files after extraction, run `sha256sum -c SHA256SUMS`. The [README](README.md#reproduce-m26) gives the commands for reproducing the intake and inspecting either trace.
