"""Parse and order Cargo index versions using Semantic Versioning."""

from __future__ import annotations

import re
from typing import NamedTuple


VERSION = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
    re.ASCII,
)


class Version(NamedTuple):
    """Orderable version without build metadata."""

    core: tuple[int, ...]
    stable: bool
    prerelease: tuple[tuple[bool, int | str], ...]


def prerelease_key(label: str) -> tuple[tuple[bool, int | str], ...]:
    """Put numeric identifiers before textual identifiers."""
    return tuple(
        (False, int(part)) if part.isdigit() else (True, part)
        for part in label.split(".")
    ) if label else ()


def parse_version(text: str) -> Version:
    """Return the SemVer precedence key for a complete version."""
    match = VERSION.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid version: {text!r}")
    major, minor, patch, prerelease = match.groups()
    return Version(
        (int(major), int(minor), int(patch)),
        prerelease is None,
        prerelease_key(prerelease or ""),
    )
