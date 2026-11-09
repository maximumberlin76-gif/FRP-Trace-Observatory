"""Validate an M32 publication using its publication and source Git revisions."""

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from artifact_auditor.m32_published_boundary_intake import (
    M32_PUBLISHED_DOCUMENT_IDENTITIES,
    M32_SOURCE_COMMIT,
    M32PublishedBoundaryError,
    M32PublishedBoundaryValidation,
    M32PublishedDocumentRole,
    validate_m32_published_boundary,
)


def _git(repo: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "--no-replace-objects", "--literal-pathspecs", "-C", str(repo), *args],
            capture_output=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise M32PublishedBoundaryError(
            exc.stderr.decode(errors="replace").strip() or "Git object lookup failed"
        ) from exc
    except OSError as exc:
        raise M32PublishedBoundaryError(str(exc)) from exc
    return result.stdout


def _check_commit(repo: Path, commit: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise M32PublishedBoundaryError("Expected a full lowercase Git commit SHA")
    if _git(repo, "cat-file", "-t", commit).strip() != b"commit":
        raise M32PublishedBoundaryError(f"Expected a commit object: {commit}")


def _blob(repo: Path, commit: str, path: str) -> bytes:
    entry = _git(repo, "ls-tree", "-z", commit, "--", path)
    meta, _, name = entry.removesuffix(b"\0").partition(b"\t")
    if name != path.encode() or not meta.startswith((b"100644 blob ", b"100755 blob ")):
        raise M32PublishedBoundaryError(f"Expected a regular file at {commit}:{path}")
    return _git(repo, "cat-file", "blob", meta.split()[2].decode("ascii"))


@contextmanager
def m32_revision_tree(repo: Path, publication_commit: str) -> Iterator[Path]:
    """Yield the four published files and their source inputs in a temporary tree."""
    repo = Path(repo)
    _check_commit(repo, publication_commit)
    _check_commit(repo, M32_SOURCE_COMMIT)
    with TemporaryDirectory() as temp:
        root = Path(temp)
        manifest = None
        for identity in M32_PUBLISHED_DOCUMENT_IDENTITIES:
            path = identity.source_path
            data = _blob(repo, publication_commit, path)
            if len(data) != identity.byte_length or hashlib.sha256(data).hexdigest() != identity.raw_sha256:
                raise M32PublishedBoundaryError(f"Published document identity mismatch: {path}")
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            if identity.role == M32PublishedDocumentRole.MANIFEST:
                manifest = json.loads(data)
        if manifest is None or manifest["source_commit"] != M32_SOURCE_COMMIT:
            raise M32PublishedBoundaryError("Unexpected M32 manifest source commit")
        for record in manifest["source_identities"]:
            path = record["path"]
            data = _blob(repo, M32_SOURCE_COMMIT, path)
            if len(data) != record["byte_count"] or hashlib.sha256(data).hexdigest() != record["raw_sha256"]:
                raise M32PublishedBoundaryError(f"Source identity mismatch: {path}")
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        yield root


def validate_m32_revision(repo: Path, publication_commit: str) -> M32PublishedBoundaryValidation:
    """Capture and verify the published M32 documents and their pinned sources."""
    with m32_revision_tree(repo, publication_commit) as root:
        return validate_m32_published_boundary(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", required=True, type=Path)
    parser.add_argument("--publication-commit", required=True)
    args = parser.parse_args()
    try:
        result = validate_m32_revision(args.upstream_root, args.publication_commit)
    except M32PublishedBoundaryError as exc:
        parser.exit(1, f"{exc}\n")
    bundle = result.document(M32PublishedDocumentRole.TRACE_BUNDLE)
    print(json.dumps({
        "publication_commit": args.publication_commit,
        "source_commit": result.source_commit,
        "bundle_sha256": bundle.identity.raw_sha256,
        "source_files": len(result.source_identities),
        "traces": [
            {key: trace[key] for key in ("scheduler_mode", "source_tick_count", "record_count")}
            for trace in bundle.root["traces"]
        ],
        "active_zero_observations": result.active_zero_cell_observation_count,
        "direct_opposite_transitions": result.direct_opposite_transition_count,
        "reserved_state_events": result.reserved_state_event_count,
        "queue_overflow_events": result.queue_overflow_event_count,
    }, indent=2))


if __name__ == "__main__":
    main()
