"""Print the direct dependency declarations for stage 2."""

import sys

from cli import parse_config
from registry import CargoIndex, describe_dependency


def main() -> int:
    """Read the selected release and print its direct dependencies."""
    config = parse_config()
    if config.test_mode:
        print("error: the local graph is supported starting at stage 3",
              file=sys.stderr)
        return 1
    try:
        release = CargoIndex(config.source).latest(config.package)
        lines = [describe_dependency(item) for item in release.entry["deps"]]
    except (KeyError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{release.name} v{release.version}")
    print("\n".join(lines) or "(no direct dependencies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
