"""Route verified M32 publication documents to Observatory modes."""

import argparse
import json
from pathlib import Path

from artifact_auditor.m32_published_boundary_intake import (
    M32PublishedBoundaryValidation,
    M32PublishedDocument,
    M32PublishedDocumentRole,
)
from artifact_auditor.m32_revision_intake import validate_m32_revision
from schemas.registry import ObservatoryMode


def documents_for_mode(
    boundary: M32PublishedBoundaryValidation,
    mode: ObservatoryMode,
) -> tuple[M32PublishedDocument, ...]:
    """Select captured documents from a validated M32 publication."""
    if not isinstance(boundary, M32PublishedBoundaryValidation):
        raise TypeError("Expected a validated M32 publication")
    if not isinstance(mode, ObservatoryMode):
        raise TypeError("Expected an ObservatoryMode")
    if mode is ObservatoryMode.ARTIFACT_AUDITOR:
        return boundary.documents
    if mode in (
        ObservatoryMode.TRACE_EXPLORER,
        ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    ):
        return (boundary.document(M32PublishedDocumentRole.TRACE_BUNDLE),)
    raise ValueError(f"Unsupported M32 mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--publication-commit", required=True)
    args = parser.parse_args()
    boundary = validate_m32_revision(args.upstream_root, args.publication_commit)
    routes = []
    for mode in ObservatoryMode:
        for document in documents_for_mode(boundary, mode):
            identity = document.identity
            routes.append({
                "mode": mode.value,
                "role": identity.role.value,
                "path": identity.source_path,
                "identifier_field": identity.identifier_field,
                "identifier": identity.identifier_value,
                "kind": identity.kind,
                "sha256": identity.raw_sha256,
            })
    print(json.dumps({
        "publication_commit": args.publication_commit,
        "source_commit": boundary.source_commit,
        "registry_revision": boundary.registry_revision,
        "routes": routes,
    }, indent=2))


if __name__ == "__main__":
    main()
