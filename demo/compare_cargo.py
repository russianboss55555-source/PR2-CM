"""Compare three SVG graphs with Cargo using temporary Rust projects."""

import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
INDEX = "https://index.crates.io"
PACKAGES = ("either", "itertools", "aho-corasick")
DOT_NODE = re.compile(r'  "([^"]+)";')
DOT_EDGE = re.compile(r'  "([^"]+)" -> "([^"]+)";')
CARGO_ROW = re.compile(r"(\d+)\s*\|([^ ]+ v[^ ]+)$")


def visualize(package: str) -> tuple[list[str], set[tuple[str, str]]]:
    """Run the submitted CLI and read the package labels from its DOT."""
    output = ROOT / "out" / f"{package}.svg"
    command = [
        sys.executable, str(ROOT / "src" / "main.py"),
        "--package", package, "--source", INDEX, "--output", str(output),
        "--ascii-tree",
    ]
    subprocess.run(command, check=True)
    lines = output.with_suffix(".dot").read_text(encoding="utf-8").splitlines()
    node_matches = (DOT_NODE.fullmatch(line) for line in lines)
    edge_matches = (DOT_EDGE.fullmatch(line) for line in lines)
    nodes = [match.group(1) for match in node_matches if match]
    edges = {match.groups() for match in edge_matches if match}
    return nodes, edges


def cargo_tree(package: str, version: str) -> str:
    """Ask Cargo to resolve a temporary project pinned to the same root."""
    with TemporaryDirectory() as directory:
        project = Path(directory)
        source = project / "src"
        source.mkdir()
        (source / "lib.rs").touch()
        manifest = (
            '[package]\nname = "compare_graph"\nversion = "0.1.0"\n'
            'edition = "2021"\n\n'
            f'[dependencies]\n{package} = "={version}"\n'
        )
        (project / "Cargo.toml").write_text(manifest, encoding="utf-8")
        command = [
            "cargo", "tree", "--color", "never", "--prefix", "depth",
            "--format", "|{p}", "--no-dedupe",
            "--edges", "normal,build", "--target", "all",
        ]
        return subprocess.check_output(command, cwd=project, text=True)


def cargo_graph(tree: str) -> tuple[set[str], set[tuple[str, str]]]:
    """Convert Cargo depth rows to a crate graph, omitting the wrapper crate."""
    nodes = set()
    edges = set()
    ancestors = []
    for line in tree.splitlines():
        match = CARGO_ROW.fullmatch(line.strip())
        if match is None:
            continue
        depth = int(match.group(1))
        package = match.group(2)
        if not depth:
            continue
        del ancestors[depth - 1:]
        if ancestors:
            edges.add((ancestors[-1], package))
        ancestors.append(package)
        nodes.add(package)
    return nodes, edges


def compare(package: str) -> bool:
    """Print both results and list unmatched package versions and edges."""
    print(f"\n=== {package} ===", flush=True)
    nodes, edges = visualize(package)
    root = nodes[0]
    version = root.partition(" v")[2]
    tree = cargo_tree(package, version)
    print("cargo tree (0 = temporary project):", tree, sep="\n")
    cargo_nodes, cargo_edges = cargo_graph(tree)
    if root not in cargo_nodes:
        raise ValueError(f"Cargo output did not contain {root}")
    actual = set(nodes)
    print(f"Visualizer: {len(actual)} vertices, {len(edges)} edges")
    print(f"Cargo:      {len(cargo_nodes)} vertices, {len(cargo_edges)} edges")
    if actual == cargo_nodes and edges == cargo_edges:
        print("MATCH")
        return True
    print("Only in the visualizer:", sorted(actual - cargo_nodes),
          sorted(edges - cargo_edges))
    print("Only in Cargo:", sorted(cargo_nodes - actual),
          sorted(cargo_edges - edges))
    return False


def main() -> int:
    """Run every comparison and return a failing status for any mismatch."""
    try:
        matches = [compare(package) for package in PACKAGES]
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0 if all(matches) else 1


if __name__ == "__main__":
    sys.exit(main())
