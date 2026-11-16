"""Resolve the transitive graph from the already parsed Cargo index."""

from graph import Graph, recursive_bfs
from registry import CargoIndex, Release
from requirements import matches, parse_requirement


def label(release: Release) -> str:
    """Distinguish separate versions of the same package in graph output."""
    return f"{release.name} v{release.version}"


def default_optional_names(release: Release) -> set[str]:
    """Collect optional aliases activated by the default feature group."""
    features = release.entry.get("features", {}) | release.entry.get(
        "features2", {}
    )
    optional = {
        item["name"] for item in release.entry["deps"] if item.get("optional")
    }
    pending = ["default"]
    visited = set()
    enabled = set()
    while pending:
        feature = pending.pop()
        if feature in visited:
            continue
        visited.add(feature)
        if feature in features:
            pending.extend(features[feature])
            continue
        name = feature.removeprefix("dep:").partition("/")[0]
        if name in optional:
            enabled.add(name)
    return enabled


class CargoGraph:
    """Connect resolved package versions through index metadata."""

    def __init__(self, index: CargoIndex, release: Release):
        """Use the requested release as the starting node."""
        self.index = index
        self.root = label(release)
        self.selected = {self.root: release}

    def resolve(self, name: str, requirement: str) -> Release:
        """Select the highest permitted non-yanked version of a dependency."""
        bounds = parse_requirement(requirement)
        candidates = [
            release for release in self.index.releases(name)
            if matches(release.order, bounds)
        ]
        if not candidates:
            message = f"no version of {name!r} satisfies {requirement!r}"
            raise ValueError(message)
        return max(candidates, key=lambda release: release.order)

    def neighbors(self, package: str) -> tuple[str, ...]:
        """Resolve normal and build edges, including default optional edges."""
        release = self.selected[package]
        enabled = default_optional_names(release)
        children = set()
        for dependency in release.entry["deps"]:
            if dependency.get("kind") == "dev":
                continue
            name = dependency["name"]
            if dependency.get("optional") and name not in enabled:
                continue
            if dependency.get("registry"):
                raise ValueError(f"{package} requires another registry: {name}")
            child = self.resolve(
                dependency.get("package") or name, dependency["req"]
            )
            child_label = label(child)
            self.selected[child_label] = child
            children.add(child_label)
        return tuple(sorted(children))

    def build(self) -> Graph:
        """Traverse the reachable graph with the shared BFS."""
        return recursive_bfs(self.root, self.neighbors)
