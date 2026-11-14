"""Command-line prototype for the Cargo dependency visualizer."""

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit


def is_repository_url(source: str) -> bool:
    """Check the syntax of an HTTP or HTTPS registry URL."""
    if any(character.isspace() for character in source):
        return False
    try:
        url = urlsplit(source)
        port = url.port
    except ValueError:
        return False
    return (
        url.scheme in {"http", "https"}
        and bool(url.hostname)
        and port != 0
    )


def validate_config(
    parser: argparse.ArgumentParser, config: argparse.Namespace
) -> None:
    """Report invalid option values before printing the configuration."""
    package_pattern = r"[A-Z]" if config.test_mode else r"[A-Za-z0-9_-]+"
    if not re.fullmatch(package_pattern, config.package):
        parser.error("--package: expected a crate name or, in test mode, A-Z")

    if config.test_mode:
        if not Path(config.source).is_file():
            parser.error("--source: expected an existing test repository file")
    elif not is_repository_url(config.source):
        parser.error("--source: expected an HTTP or HTTPS registry URL")

    output = Path(config.output)
    if output.suffix.lower() != ".svg" or output.is_dir():
        parser.error("--output: expected an SVG filename with the .svg suffix")


def parse_config() -> argparse.Namespace:
    """Read all five configuration options from the command line."""
    parser = argparse.ArgumentParser(
        description="Stage 1: print the Cargo dependency graph configuration."
    )
    parser.add_argument("--package", required=True, help="crate name")
    parser.add_argument("--source", required=True, help="registry URL or file")
    parser.add_argument(
        "--test-mode",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="use a local test repository file",
    )
    parser.add_argument("--output", required=True, help="SVG output filename")
    parser.add_argument(
        "--ascii-tree",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="enable ASCII tree output",
    )
    config = parser.parse_args()
    validate_config(parser, config)
    return config


def main() -> None:
    """Print the validated command-line configuration as key-value pairs."""
    for key, value in vars(parse_config()).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
