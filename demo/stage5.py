"""Run the stage-five visualization for a Rust crate with many dependencies."""

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Build a real Cargo graph, DOT, SVG and an ASCII tree."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="image")
    options = parser.parse_args()
    output = Path("out") / f"{options.package}.svg"
    command = [
        sys.executable, str(ROOT / "src" / "main.py"),
        "--package", options.package, "--source", "https://index.crates.io",
        "--output", str(output), "--ascii-tree",
    ]
    result = subprocess.run(command, cwd=ROOT, check=False)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
