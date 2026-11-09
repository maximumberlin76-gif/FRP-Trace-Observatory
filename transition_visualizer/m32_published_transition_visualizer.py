"""Show a cell's retained states and route legs in a published M32 trace."""

import argparse
import json
from pathlib import Path

from artifact_auditor.m32_published_boundary_intake import M32PublishedBoundaryValidation
from artifact_auditor.m32_revision_intake import validate_m32_revision
from schemas.m32_published_registry import documents_for_mode
from schemas.registry import ObservatoryMode


def cell_timeline(
    boundary: M32PublishedBoundaryValidation, scheduler_mode: str, source_cell: int
) -> dict:
    if type(source_cell) is not int or source_cell < 0:
        raise ValueError("source_cell must be a nonnegative integer")
    bundle, = documents_for_mode(boundary, ObservatoryMode.TERNARY_TRANSITION_VISUALIZER)
    for trace in bundle.root["traces"]:
        if trace["scheduler_mode"] == scheduler_mode:
            break
    else:
        raise ValueError(f"Unknown scheduler mode: {scheduler_mode!r}")

    rows = []
    previous_state = None
    for tick in trace["records"]:
        cell = next((c for c in tick["cells"] if c["source_cell"] == source_cell), None)
        if cell is None:
            raise ValueError(f"Cell {source_cell} absent at tick {tick['source_tick']}")
        row = {key: cell[key] for key in (
            "source_tick", "retained_state_value", "state_changed", "active_zero",
            "pending_active", "pending_target_value", "first_route_leg", "second_route_leg",
        )}
        row["previous_retained_state"] = previous_state
        rows.append(row)
        previous_state = cell["retained_state_value"]

    return {
        "source_commit": boundary.source_commit,
        "bundle_sha256": bundle.identity.raw_sha256,
        "scheduler_mode": scheduler_mode,
        "source_cell": source_cell,
        "timeline": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--publication-commit", required=True)
    parser.add_argument("--scheduler-mode", choices=("7/1", "1/7"), required=True)
    parser.add_argument("--source-cell", type=int, required=True)
    args = parser.parse_args()
    try:
        boundary = validate_m32_revision(args.upstream_root, args.publication_commit)
        result = cell_timeline(boundary, args.scheduler_mode, args.source_cell)
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    result["publication_commit"] = args.publication_commit
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
