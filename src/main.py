"""Run the Cargo dependency visualizer from the command line."""

import sys
from argparse import Namespace
from pathlib import Path

from cargo_graph import CargoGraph
from cli import parse_config
from graph import Graph, recursive_bfs, reverse_graph
from local_index import read_test_index
from registry import CargoIndex
from visualization import make_ascii, save_graph


def build_graph(config: Namespace) -> tuple[str, Graph]:
    """Read the selected source and build the reachable graph from the root."""
    if config.test_mode:
        repository = read_test_index(config.source)
        if config.package not in repository:
            raise ValueError(f"unknown test package: {config.package}")
        if config.reverse:
            repository = reverse_graph(repository)
        graph = recursive_bfs(config.package, repository.__getitem__)
        return config.package, graph
    index = CargoIndex(config.source)
    cargo = CargoGraph(index, index.latest(config.package))
    return cargo.root, cargo.build()


def main() -> int:
    """Save the graph and print only the requested console output."""
    config = parse_config()
    output = Path(config.output)
    try:
        root, graph = build_graph(config)
        if config.reverse:
            dependents = [package for package in graph if package != root]
            print(f"{root} <- {', '.join(dependents) or '(none)'}")
            return 0
        dot_path = save_graph(output, root, graph)
    except (KeyError, OSError, RecursionError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if config.ascii_tree:
        print(make_ascii(root, graph))
    print(f"SVG: {output}")
    print(f"DOT: {dot_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
