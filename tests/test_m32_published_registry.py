"""Check M32 document routing through the registry API and CLI."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from artifact_auditor.m32_published_boundary_intake import (
    M32_SOURCE_COMMIT,
    M32PublishedDocumentRole as Role,
    validate_m32_published_boundary,
)
from schemas.m32_published_registry import documents_for_mode
from schemas.registry import ObservatoryMode as Mode


EXPECTED = {
    Mode.ARTIFACT_AUDITOR: (
        Role.FORMAL_SCHEMA, Role.TRACE_BUNDLE, Role.MANIFEST, Role.QUALIFICATION,
    ),
    Mode.TRACE_EXPLORER: (Role.TRACE_BUNDLE,),
    Mode.TERNARY_TRANSITION_VISUALIZER: (Role.TRACE_BUNDLE,),
}


class InputTests(unittest.TestCase):
    def test_rejects_an_unverified_document_collection(self):
        with self.assertRaises(TypeError):
            documents_for_mode((), Mode.ARTIFACT_AUDITOR)


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = os.environ.get("FRP_M32_UPSTREAM_ROOT")
        if not root:
            raise unittest.SkipTest("Requires the M32 publication tree")
        cls.boundary = validate_m32_published_boundary(Path(root))

    def test_each_mode_receives_its_exact_documents(self):
        self.assertEqual(set(Mode), set(EXPECTED))
        for mode, roles in EXPECTED.items():
            with self.subTest(mode=mode):
                docs = documents_for_mode(self.boundary, mode)
                self.assertEqual(tuple(doc.identity.role for doc in docs), roles)
                for doc, role in zip(docs, roles, strict=True):
                    self.assertIs(doc, self.boundary.document(role))

    def test_rejects_a_plain_string_mode(self):
        with self.assertRaises(TypeError):
            documents_for_mode(self.boundary, "trace_explorer")

    def test_cli_preserves_route_inventory_and_publication_provenance(self):
        publication = os.environ.get("FRP_PUBLICATION")
        upstream = os.environ.get("FRP_M31_UPSTREAM_ROOT")
        if not publication or not upstream:
            self.skipTest("Requires the FRP Git checkout and publication commit")
        output = subprocess.check_output([
            sys.executable, "-m", "schemas.m32_published_registry",
            "--upstream-root", upstream, "--publication-commit", publication,
        ], text=True)
        report = json.loads(output)
        self.assertEqual(report["publication_commit"], publication)
        self.assertEqual(report["source_commit"], M32_SOURCE_COMMIT)
        self.assertEqual(report["registry_revision"], self.boundary.registry_revision)

        expected = []
        for mode, roles in EXPECTED.items():
            for role in roles:
                doc = self.boundary.document(role)
                field = "$id" if role is Role.FORMAL_SCHEMA else "schema"
                expected.append({
                    "mode": mode.value,
                    "role": role.value,
                    "path": doc.source_artifact.source_path,
                    "identifier_field": field,
                    "identifier": doc.root[field],
                    "kind": doc.root.get("kind"),
                    "sha256": hashlib.sha256(doc.raw_bytes).hexdigest(),
                })
        self.assertCountEqual(report["routes"], expected)


if __name__ == "__main__":
    unittest.main()
