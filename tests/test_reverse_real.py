"""Check reverse queries on resolved Cargo package graphs."""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "demo"))

from reverse_real import find_dependents


class RealReverseTests(unittest.TestCase):
    """Preserve incoming paths, cycles and separate crate versions."""

    def test_transitive_cycle_and_unrelated_node(self):
        """Return BFS order and include shared paths once inside a cycle."""
        graph = {
            "app v1.0.0": ("left v1.0.0", "right v1.0.0"),
            "left v1.0.0": ("target v1.0.0",),
            "right v1.0.0": ("target v1.0.0",),
            "target v1.0.0": ("app v1.0.0",),
            "unrelated v1.0.0": (),
        }
        result = find_dependents(graph, "TARGET")
        self.assertEqual(result, {
            "target v1.0.0": ["left v1.0.0", "right v1.0.0", "app v1.0.0"]
        })

    def test_multiple_versions(self):
        """Keep each resolved version's incoming edges separate."""
        graph = {
            "old v1.0.0": ("target v1.0.0",),
            "new v1.0.0": ("target v2.0.0",),
            "target v1.0.0": (),
            "target v2.0.0": (),
        }
        self.assertEqual(find_dependents(graph, "target"), {
            "target v1.0.0": ["old v1.0.0"],
            "target v2.0.0": ["new v1.0.0"],
        })

    def test_absent_target(self):
        """Explain when the query is outside the selected package graph."""
        with self.assertRaisesRegex(ValueError, "absent"):
            find_dependents({"app v1.0.0": ()}, "missing")
