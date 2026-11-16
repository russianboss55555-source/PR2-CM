"""Match Cargo version requirements against Semantic Versioning keys."""

import operator as ops
import re
from typing import NamedTuple

from versions import Version, prerelease_key


COMPARATOR = re.compile(
    r"(>=|<=|>|<|=|~|\^)?\s*"
    r"(0|[1-9][0-9]*|\*)(?:\.(0|[1-9][0-9]*|\*))?"
    r"(?:\.(0|[1-9][0-9]*|\*))?"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?",
    re.ASCII,
)
CORE_SIZE = 3
ZERO_CORE = (0, 0, 0)
ORDERING = {"=": ops.eq, ">": ops.gt, ">=": ops.ge, "<": ops.lt, "<=": ops.le}
PARTIAL_ORDERING = {">": ops.ge, "<=": ops.lt}


class Comparator(NamedTuple):
    """One parsed bound or compatible range in a Cargo requirement."""

    operator: str
    parts: tuple[int, ...]
    start: Version
    wildcard: bool


def parse_comparator(text: str) -> Comparator:
    """Read one comparison and record its written version precision."""
    match = COMPARATOR.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"unsupported Cargo version requirement: {text!r}")
    operator, major, minor, patch, prerelease = match.groups()
    raw = tuple(part for part in (major, minor, patch) if part is not None)
    wildcard = "*" in raw
    numbers = raw[:raw.index("*")] if wildcard else raw
    parts = tuple(map(int, numbers))
    core = (parts + ZERO_CORE)[:CORE_SIZE]
    start = Version(core, prerelease is None, prerelease_key(prerelease or ""))
    return Comparator(operator or "^", parts, start, wildcard)


def ceiling(parts: tuple[int, ...]) -> Version:
    """Return the first stable version outside a numeric prefix."""
    bumped = parts[:-1] + (parts[-1] + 1,)
    return Version((bumped + ZERO_CORE)[:CORE_SIZE], True, ())


def caret_prefix(parts: tuple[int, ...]) -> tuple[int, ...]:
    """Keep the prefix through its first nonzero component."""
    for index, part in enumerate(parts):
        if part:
            return parts[:index + 1]
    return parts


def compare(version: Version, bound: Comparator) -> bool:
    """Apply one exact, wildcard, inequality, caret or tilde condition."""
    operator, parts, start, wildcard = bound
    if not parts:
        return True
    partial = len(parts) < CORE_SIZE
    if wildcard or (operator == "=" and partial):
        return version.core[:len(parts)] == parts
    if partial and operator in PARTIAL_ORDERING:
        return PARTIAL_ORDERING[operator](version, ceiling(parts))
    if operator in ORDERING:
        return ORDERING[operator](version, start)
    prefix = parts[:2] if operator == "~" else caret_prefix(parts)
    return start <= version < ceiling(prefix)


def parse_requirement(text: str) -> tuple[Comparator, ...]:
    """Split a Cargo requirement into the comparators joined by commas."""
    return tuple(parse_comparator(part) for part in text.split(","))


def matches(version: Version, bounds: tuple[Comparator, ...]) -> bool:
    """Apply Cargo prerelease admission and all comparator conditions."""
    if not version.stable:
        allows_prerelease = any(
            not bound.start.stable and bound.start.core == version.core
            for bound in bounds
        )
        if not allows_prerelease:
            return False
    return all(compare(version, bound) for bound in bounds)
