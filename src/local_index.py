"""Load a small repository of letter-named packages from JSON."""

import json
import re
from pathlib import Path

from cli import TEST_NAME
from graph import Graph


def letter(value: object) -> bool:
    """Check whether a test package name is one capital Latin letter."""
    return isinstance(value, str) and re.fullmatch(TEST_NAME, value) is not None


def read_test_index(source: str) -> Graph:
    """Read A-Z adjacency lists and add any implicit leaf packages."""
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("test repository must be a JSON object")
    graph: Graph = {}
    for package, dependencies in data.items():
        if not letter(package) or not isinstance(dependencies, list):
            raise ValueError(f"expected an adjacency list for {package!r}")
        if not all(letter(dependency) for dependency in dependencies):
            raise ValueError(f"dependencies of {package} must be letters A-Z")
        graph[package] = tuple(sorted(set(dependencies)))
    leaves = {
        target for dependencies in graph.values() for target in dependencies
    } - graph.keys()
    graph.update((leaf, ()) for leaf in sorted(leaves))
    return graph
