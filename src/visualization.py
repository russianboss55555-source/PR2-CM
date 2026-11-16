"""Render dependency graphs as Graphviz DOT, SVG and ASCII trees."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NamedTuple

from graph import Graph


class TreeLine(NamedTuple):
    """Describe one pending line and its position in the ASCII tree."""

    package: str
    prefix: str
    branch: str
    ancestors: frozenset[str]


def make_dot(root: str, graph: Graph) -> str:
    """Declare every vertex and directed edge, including back edges."""
    lines = [
        "digraph dependencies {",
        "  rankdir=LR;",
        "  node [shape=box, style=rounded];",
    ]
    lines.extend(f"  {json.dumps(package)};" for package in graph)
    lines.append(f'  {json.dumps(root)} [style="rounded,bold"];')
    for package, dependencies in graph.items():
        for dependency in dependencies:
            edge = f"{json.dumps(package)} -> {json.dumps(dependency)}"
            lines.append(f"  {edge};")
    return "\n".join([*lines, "}", ""])


def schedule_children(
    line: TreeLine, children: tuple[str, ...]
) -> Iterator[TreeLine]:
    """Return child rows in stack order with consistent ASCII connectors."""
    continuation = "|   " if line.branch == "+-- " else "    "
    prefix = line.prefix + continuation if line.branch else ""
    ancestors = line.ancestors | {line.package}
    for offset, package in enumerate(reversed(children)):
        branch = "+-- " if offset else "`-- "
        yield TreeLine(package, prefix, branch, ancestors)


def make_ascii(root: str, graph: Graph) -> str:
    """Show the graph as a tree and mark both cycles and shared packages."""
    pending = [TreeLine(root, "", "", frozenset())]
    seen = set()
    lines = []
    while pending:
        line = pending.pop()
        package = line.package
        text = f"{line.prefix}{line.branch}{package}"
        if package in line.ancestors:
            text += " [cycle]"
        elif package in seen:
            text += " [shared]"
        else:
            seen.add(package)
            pending.extend(schedule_children(line, graph[package]))
        lines.append(text)
    return "\n".join(lines)


def render_svg(dot: str) -> bytes:
    """Convert DOT to SVG using the Graphviz executable on PATH."""
    try:
        process = subprocess.run(
            ["dot", "-Tsvg"], input=dot.encode("utf-8"),
            capture_output=True, check=False,
        )
    except FileNotFoundError as error:
        raise ValueError("Graphviz 'dot' was not found on PATH") from error
    if process.returncode:
        message = process.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Graphviz failed: {message}")
    return process.stdout


def save_graph(output: Path, root: str, graph: Graph) -> Path:
    """Save the SVG and its source DOT side by side."""
    dot_path = output.with_suffix(".dot")
    if dot_path.is_dir():
        raise ValueError(f"DOT destination is a directory: {dot_path}")
    dot = make_dot(root, graph)
    svg = render_svg(dot)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as directory:
        temporary_dot = Path(directory) / "graph.dot"
        temporary_svg = Path(directory) / "graph.svg"
        temporary_dot.write_text(dot, encoding="utf-8")
        temporary_svg.write_bytes(svg)
        temporary_dot.replace(dot_path)
        temporary_svg.replace(output)
    return dot_path
