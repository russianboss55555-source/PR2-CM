"""Build and inspect a transitive Cargo dependency graph."""

import sys
from argparse import Namespace

from cargo_graph import CargoGraph
from cli import parse_config
from graph import Graph, recursive_bfs
from local_index import read_test_index
from registry import CargoIndex


def build_graph(config: Namespace) -> tuple[str, Graph]:
    """Read the selected source and build the reachable graph from the root."""
    if config.test_mode:
        repository = read_test_index(config.source)
        if config.package not in repository:
            raise ValueError(f"unknown test package: {config.package}")
        graph = recursive_bfs(config.package, repository.__getitem__)
        return config.package, graph
    index = CargoIndex(config.source)
    cargo = CargoGraph(index, index.latest(config.package))
    return cargo.root, cargo.build()


def main() -> int:
    """Print the graph in BFS order, including original cycle edges."""
    config = parse_config()
    try:
        _, graph = build_graph(config)
    except (KeyError, OSError, RecursionError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for package, dependencies in graph.items():
        print(f"{package}: {', '.join(dependencies) or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
