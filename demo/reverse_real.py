"""Find reverse dependencies inside a real Cargo package's graph."""

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cargo_graph import CargoGraph
from cli import is_repository_url
from graph import Graph, recursive_bfs, reverse_graph
from registry import CargoIndex


def find_dependents(graph: Graph, package: str) -> dict[str, list[str]]:
    """Find transitive incoming paths to every version of a crate."""
    reversed_graph = reverse_graph(graph)
    prefix = f"{package.lower()} v"
    targets = [node for node in graph if node.lower().startswith(prefix)]
    if not targets:
        raise ValueError(f"{package!r} is absent from the selected graph")
    results = {}
    for target in targets:
        reached = recursive_bfs(target, reversed_graph.__getitem__)
        results[target] = [node for node in reached if node != target]
    return results


def parse_options() -> argparse.Namespace:
    """Read the graph root, reverse query and sparse index URL."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="itertools")
    parser.add_argument("--reverse-of", default="either")
    parser.add_argument("--source", default="https://index.crates.io")
    config = parser.parse_args()
    if not is_repository_url(config.source):
        parser.error("--source: expected an HTTP or HTTPS index URL")
    return config


def main() -> int:
    """Download a real graph and query it using the shared recursive BFS."""
    config = parse_options()
    try:
        index = CargoIndex(config.source)
        cargo = CargoGraph(index, index.latest(config.package))
        results = find_dependents(cargo.build(), config.reverse_of)
    except (KeyError, OSError, RecursionError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Repository: {config.source}")
    print(f"Scope: dependency graph of {cargo.root}")
    for target, dependents in results.items():
        print(f"{target} <- {', '.join(dependents) or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
