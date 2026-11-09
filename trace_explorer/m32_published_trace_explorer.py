"""Read published M32 tick records by scheduler mode and source tick."""

import argparse
import json
from pathlib import Path

from artifact_auditor.m32_published_boundary_intake import M32PublishedBoundaryValidation
from artifact_auditor.m32_revision_intake import validate_m32_revision
from schemas.m32_published_registry import documents_for_mode
from schemas.registry import ObservatoryMode


def explore_m32_trace(
    boundary: M32PublishedBoundaryValidation,
    scheduler_mode: str,
    source_tick: int | None = None,
) -> dict:
    """Return complete captured tick groups for the selected coordinates."""
    if source_tick is not None and (type(source_tick) is not int or source_tick < 0):
        raise ValueError("source_tick must be a nonnegative integer")
    bundle, = documents_for_mode(boundary, ObservatoryMode.TRACE_EXPLORER)
    for trace in bundle.root["traces"]:
        if trace["scheduler_mode"] == scheduler_mode:
            break
    else:
        raise ValueError(f"Unknown scheduler mode: {scheduler_mode!r}")

    ticks = trace["records"]
    if source_tick is not None:
        ticks = tuple(group for group in ticks if group["source_tick"] == source_tick)
        if not ticks:
            raise ValueError(f"No source tick {source_tick} in mode {scheduler_mode}")

    return {
        "source_commit": boundary.source_commit,
        "bundle_sha256": bundle.identity.raw_sha256,
        "scheduler_mode": scheduler_mode,
        "selected_tick_count": len(ticks),
        "selected_record_count": sum(
            2 + len(group["requests"]) + len(group["cells"]) for group in ticks
        ),
        "ticks": ticks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", required=True, type=Path)
    parser.add_argument("--publication-commit", required=True)
    parser.add_argument("--scheduler-mode", required=True, choices=("7/1", "1/7"))
    parser.add_argument("--source-tick", type=int)
    args = parser.parse_args()
    try:
        boundary = validate_m32_revision(args.upstream_root, args.publication_commit)
        result = explore_m32_trace(boundary, args.scheduler_mode, args.source_tick)
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    result["publication_commit"] = args.publication_commit
    print(json.dumps(result, default=dict, indent=2))


if __name__ == "__main__":
    main()
