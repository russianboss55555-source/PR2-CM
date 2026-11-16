"""Read newline-delimited JSON entries from a public Cargo sparse index."""

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import urlopen

from cli import CRATE_NAME
from versions import Version, parse_version


SHORT_PREFIXES = {1: "1", 2: "2", 3: "3/{initial}"}
HTTP_TIMEOUT = 15
HTTP_NOT_FOUND = 404


@dataclass(frozen=True)
class Release:
    """A published crate release with its index metadata."""

    name: str
    version: str
    order: Version
    entry: dict[str, Any]


def index_path(package: str) -> str:
    """Build the lower-case sparse-index path for a crate name."""
    if re.fullmatch(CRATE_NAME, package) is None:
        raise ValueError(f"invalid crate name: {package!r}")
    name = package.lower()
    prefix = SHORT_PREFIXES.get(len(name), "{first}/{second}")
    directory = prefix.format(initial=name[0], first=name[:2], second=name[2:4])
    return f"{directory}/{name}"


def parse_entry(line: str) -> Release:
    """Read the crate identity and dependency declarations from one row."""
    entry = json.loads(line)
    name = entry["name"]
    version = entry["vers"]
    dependencies = entry["deps"]
    if not isinstance(dependencies, list):
        raise ValueError("deps must be an array")
    if not all(isinstance(item, dict) for item in dependencies):
        raise ValueError("dependency declarations must be objects")
    return Release(name, version, parse_version(version), entry)


class CargoIndex:
    """Cache releases by name for one HTTP(S) Cargo registry."""

    def __init__(self, source: str):
        """Use the supplied sparse-index URL as a directory."""
        self.source = source.rstrip("/")
        self.cache: dict[str, list[Release]] = {}

    def fetch(self, package: str) -> list[Release]:
        """Request and parse the index file for one crate."""
        url = f"{self.source}/{index_path(package)}"
        try:
            with urlopen(url, timeout=HTTP_TIMEOUT) as response:
                lines = response.read().decode("utf-8").splitlines()
            releases = [parse_entry(line) for line in lines if line.strip()]
        except HTTPError as error:
            if error.code == HTTP_NOT_FOUND:
                message = f"crate {package!r} was not found at {url}"
                raise ValueError(message) from error
            raise ValueError(f"cannot read {url}: {error}") from error
        except OSError as error:
            raise ValueError(f"cannot read {url}: {error}") from error
        except (KeyError, TypeError, ValueError) as error:
            message = f"invalid Cargo index entry at {url}: {error}"
            raise ValueError(message) from error
        return [item for item in releases if not item.entry.get("yanked")]

    def releases(self, package: str) -> list[Release]:
        """Return non-yanked releases, downloading a crate only once."""
        key = package.lower()
        if key not in self.cache:
            self.cache[key] = self.fetch(package)
        return self.cache[key]

    def latest(self, package: str) -> Release:
        """Select the highest stable release, or a prerelease if necessary."""
        releases = self.releases(package)
        if not releases:
            raise ValueError(f"crate {package!r} has no non-yanked releases")
        stable = [release for release in releases if release.order.stable]
        return max(stable or releases, key=lambda release: release.order)
