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

    def test_registry_config(self):
        """Print all five values for a registry URL."""
        result = self.run_cli(
            "--package", "serde", "--source", REGISTRY, "--output", "graph.svg"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "package=serde",
                f"source={REGISTRY}",
                "test_mode=False",
                "output=graph.svg",
                "ascii_tree=False",
            ],
        )

    def test_local_config(self):
        """Accept an existing fixture and enable both switches."""
        result = self.run_cli(
            "--package", "A", "--source", str(FIXTURE),
            "--output", "graph.svg", "--test-mode", "--ascii-tree",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("test_mode=True", result.stdout)
        self.assertIn("ascii_tree=True", result.stdout)

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
