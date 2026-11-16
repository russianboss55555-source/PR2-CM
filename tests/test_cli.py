"""Check the final CLI in normal, test, and reverse modes."""

import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as element_tree
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "main.py"
FIXTURES = ROOT / "tests" / "fixtures"
REGISTRY = "https://index.crates.io"


class CliTests(unittest.TestCase):
    """Exercise error handling and local graphs through the CLI."""

    def setUp(self):
        """Use an isolated output directory for each run."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.svg = Path(directory.name) / "nested" / "graph.svg"

    def run_cli(self, *args):
        """Run the program with the active Python interpreter."""
        return subprocess.run(
            [sys.executable, str(MAIN), "--output", str(self.svg), *args],
            capture_output=True, text=True, check=False,
        )

    def run_test_graph(self, package, fixture, *options):
        """Select a local repository and pass any extra flags."""
        return self.run_cli(
            "--package", package, "--source", str(FIXTURES / fixture),
            "--test-mode", *options,
        )

    @unittest.skipUnless(shutil.which("dot"), "requires Graphviz")
    def test_svg_dot_and_cycle_tree(self):
        """Render a real SVG and keep the cycle and both shared edges."""
        result = self.run_test_graph("A", "cycle.json", "--ascii-tree")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[:6], [
            "A", "+-- B", "|   `-- D", "|       `-- A [cycle]",
            "`-- C", "    `-- D [shared]",
        ])
        dot = self.svg.with_suffix(".dot").read_text(encoding="utf-8")
        self.assertIn('"B" -> "D";', dot)
        self.assertIn('"C" -> "D";', dot)
        self.assertIn('"D" -> "A";', dot)
        self.assertNotIn('"E"', dot)
        svg = element_tree.parse(self.svg).getroot()
        self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")

    @unittest.skipUnless(shutil.which("dot"), "requires Graphviz")
    def test_isolated_node_without_ascii_flag(self):
        """Write a node-only SVG and keep the ASCII tree out of stdout."""
        result = self.run_test_graph("F", "diamond.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            f"SVG: {self.svg}", f"DOT: {self.svg.with_suffix('.dot')}"
        ])
        dot = self.svg.with_suffix(".dot").read_text(encoding="utf-8")
        self.assertIn('"F";', dot)
        self.assertNotIn("->", dot)

    def test_reverse_graphs(self):
        """Use the shared traversal on a diamond, cycle and isolated node."""
        cases = (
            ("D", "diamond.json", "D <- B, C, A, E"),
            ("A", "cycle.json", "A <- D, B, C"),
            ("F", "diamond.json", "F <- (none)"),
        )
        for package, filename, expected in cases:
            with self.subTest(package=package):
                result = self.run_test_graph(package, filename, "--reverse")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)
                self.assertFalse(self.svg.exists())

    def test_invalid_options(self):
        """Reject bad input for all settings and test-only reverse mode."""
        valid = ["--package", "serde", "--source", REGISTRY]
        cases = {
            "--package": ["--package", "bad name"],
            "--source": ["--source", "invalid-url"],
            "--output": ["--output", "graph.png"],
            "--test-mode": ["--test-mode=maybe"],
            "--ascii-tree": ["--ascii-tree=maybe"],
            "--reverse": ["--reverse"],
        }
        for option, override in cases.items():
            with self.subTest(option=option):
                result = self.run_cli(*valid, *override)
                self.assertEqual(result.returncode, 2)
                self.assertIn(option, result.stderr)

    def test_missing_test_file(self):
        """Reject a nonexistent file during configuration validation."""
        result = self.run_test_graph("A", "missing.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("existing test repository file", result.stderr)

    def test_unknown_start_node(self):
        """Report a missing root without producing output files."""
        result = self.run_test_graph("Z", "cycle.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown test package: Z", result.stderr)
        self.assertFalse(self.svg.exists())

    def test_bad_test_repository(self):
        """Report invalid package references in a local JSON graph."""
        self.svg.parent.mkdir()
        source = self.svg.parent / "bad.json"
        source.write_text('{"A": ["bb"]}', encoding="utf-8")
        result = self.run_cli(
            "--package", "A", "--source", str(source), "--test-mode",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must be letters A-Z", result.stderr)


if __name__ == "__main__":
    unittest.main()
