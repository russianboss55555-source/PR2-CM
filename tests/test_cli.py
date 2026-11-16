"""Check stage-one configuration and errors through the CLI."""

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "main.py"
FIXTURE = ROOT / "tests" / "fixtures" / "simple.json"
REGISTRY = "https://index.crates.io"


class CliTests(unittest.TestCase):
    """Exercise the five command-line settings in both source modes."""

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        """Run the prototype with the current Python interpreter."""
        return subprocess.run(
            [sys.executable, str(MAIN), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_cycle_and_isolated_package(self):
        """Visit shared and cyclic nodes once in BFS order."""
        result = self.run_cli(
            "--package", "A", "--source", str(FIXTURE.with_name("cycle.json")),
            "--test-mode", "--output", "graph.svg",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "A: B, C", "B: D", "C: D", "D: A",
        ])

    def test_acyclic_graph(self):
        """Read the existing acyclic fixture and preserve all its edges."""
        result = self.run_cli(
            "--package", "A", "--source", str(FIXTURE),
            "--test-mode", "--output", "graph.svg",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "A: B, C", "B: C", "C: (none)",
        ])

    def run_reverse(self, package, fixture):
        """Find transitive dependents in an entire test repository."""
        return self.run_cli(
            "--package", package, "--source", str(FIXTURE.with_name(fixture)),
            "--test-mode", "--output", "graph.svg", "--reverse",
        )

    def test_reverse_diamond(self):
        """Find incoming paths from all branches and print shared nodes once."""
        result = self.run_reverse("D", "diamond.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "D <- B, C, A, E")

    def test_reverse_cycle(self):
        """Exclude the query package itself even when it is in a cycle."""
        result = self.run_reverse("A", "cycle.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "A <- D, B, C")

    def test_reverse_isolated_package(self):
        """Report the empty reverse graph of an isolated package."""
        result = self.run_reverse("F", "diamond.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "F <- (none)")

    def test_invalid_options(self):
        """Report an invalid input for each option."""
        valid = [
            "--package", "serde", "--source", REGISTRY, "--output", "graph.svg",
        ]
        cases = {
            "--package": ["--package", "bad name"],
            "--source": ["--source", "invalid-url"],
            "--output": ["--output", "graph.png"],
            "--test-mode": ["--test-mode=maybe"],
            "--ascii-tree": ["--ascii-tree=maybe"],
        }
        for option, override in cases.items():
            with self.subTest(option=option):
                result = self.run_cli(*valid, *override)
                self.assertEqual(result.returncode, 2)
                self.assertIn(option, result.stderr)

    def test_missing_test_file(self):
        """Report a nonexistent file in test mode."""
        missing = FIXTURE.with_name("missing.json")
        result = self.run_cli(
            "--package", "A", "--source", str(missing),
            "--output", "graph.svg", "--test-mode",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("existing test repository file", result.stderr)


if __name__ == "__main__":
    unittest.main()
