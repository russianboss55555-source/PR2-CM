"""Build reachable adjacency lists with recursive breadth-first traversal."""

from collections.abc import Callable


Graph = dict[str, tuple[str, ...]]


def recursive_bfs(
    root: str, neighbors: Callable[[str], tuple[str, ...]]
) -> Graph:
    """Recurse over breadth-first layers and keep edges to visited nodes."""
    graph: Graph = {}
    scheduled = {root}

    def visit_layer(layer: list[str]) -> None:
        """Expand this layer and pass newly discovered vertices forward."""
        if not layer:
            return
        following = []
        for package in layer:
            graph[package] = neighbors(package)
            for dependency in graph[package]:
                if dependency in scheduled:
                    continue
                scheduled.add(dependency)
                following.append(dependency)
        visit_layer(following)

    visit_layer([root])
    return graph
