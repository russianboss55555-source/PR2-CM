"""Query crates.io reverse_dependencies directly for a real Rust crate."""

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cli import CRATE_NAME, is_repository_url
from reverse_api import ReverseApi


DEFAULT_PACKAGE = "itertools-num"
DEFAULT_API = "https://crates.io/api/v1"


def positive_depth(value: str) -> int:
    """Require at least one level of reverse dependencies."""
    depth = int(value)
    if depth <= 0:
        raise argparse.ArgumentTypeError("depth must be positive")
    return depth


def parse_options() -> argparse.Namespace:
    """Read the target crate, API URL and requested traversal depth."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--source", default=DEFAULT_API, help="API base URL")
    parser.add_argument("--depth", type=positive_depth, default=1)
    config = parser.parse_args()
    if re.fullmatch(CRATE_NAME, config.package) is None:
        parser.error("--package: expected a Cargo crate name")
    if not is_repository_url(config.source):
        parser.error("--source: expected an HTTP(S) API base URL")
    config.package = config.package.lower()
    return config


def main() -> int:
    """Fetch reverse dependencies from the registry API and print them."""
    config = parse_options()
    api = ReverseApi(config.source, config.depth)
    print(f"API: {api.page_url(config.package, 1)}", flush=True)
    print(f"Package: {config.package}", flush=True)
    print(f"Reverse depth: {config.depth} (all result pages)", flush=True)
    try:
        graph = api.build(config.package)
    except (KeyError, OSError, RecursionError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    dependents = [node for node in graph if node != config.package]
    print(f"Found: {len(dependents)} reverse dependents")
    for package in dependents:
        print(f"{config.package} <- {package} v{api.versions[package]}")
    if not dependents:
        print(f"{config.package} <- (none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
