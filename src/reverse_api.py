"""Read reverse dependencies directly from the crates.io HTTP API."""

import json
import re
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from cli import CRATE_NAME
from graph import Graph, recursive_bfs


API_TIMEOUT = 30
PAGE_SIZE = 100
REQUEST_INTERVAL = 1.0
USER_AGENT = "PR2-CM/1.0 (github.com/russianboss55555-source/PR2-CM)"


def decode_page(payload: dict) -> tuple[dict[str, str], int, int]:
    """Join dependency version IDs to the dependent crates in versions."""
    versions = {item["id"]: item for item in payload["versions"]}
    dependents = {}
    for dependency in payload["dependencies"]:
        version = versions[dependency["version_id"]]
        name = version["crate"]
        if re.fullmatch(CRATE_NAME, name) is None:
            raise ValueError("API response contains an invalid crate name")
        dependents[name] = version["num"]
    total = int(payload["meta"]["total"])
    if total < 0:
        raise ValueError("API response contains a negative total")
    return dependents, len(payload["dependencies"]), total


class ReverseApi:
    """Fetch all pages for each visited crate and bound traversal by depth."""

    def __init__(self, source: str, depth: int = 1):
        """Use an API base URL and the requested reverse traversal depth."""
        self.source = source.rstrip("/")
        self.depth = depth
        self.levels: dict[str, int] = {}
        self.versions: dict[str, str] = {}
        self.cache: dict[str, tuple[str, ...]] = {}
        self.last_request = 0.0

    def page_url(self, package: str, page: int) -> str:
        """Build the official reverse_dependencies URL with pagination."""
        query = urlencode({"page": page, "per_page": PAGE_SIZE})
        name = quote(package, safe="")
        return f"{self.source}/crates/{name}/reverse_dependencies?{query}"

    def read_page(self, package: str, page: int) -> dict:
        """Read JSON with an identifying User-Agent and spaced requests."""
        url = self.page_url(package, page)
        pause = REQUEST_INTERVAL - (time.monotonic() - self.last_request)
        if pause > 0:
            time.sleep(pause)
        request = Request(url, headers={
            "User-Agent": USER_AGENT, "Accept": "application/json",
        })
        self.last_request = time.monotonic()
        try:
            with urlopen(request, timeout=API_TIMEOUT) as response:
                return json.load(response)
        except HTTPError as error:
            raise ValueError(f"API HTTP {error.code}: {url}") from error
        except OSError as error:
            raise ValueError(f"cannot read API {url}: {error}") from error

    def fetch(self, package: str) -> tuple[str, ...]:
        """Collect every page, checking the server's meta.total value."""
        page, received = 1, 0
        dependents = {}
        while True:
            entries, count, total = decode_page(self.read_page(package, page))
            dependents.update(entries)
            received += count
            if received >= total:
                break
            if not count:
                raise ValueError(f"incomplete API pagination for {package}")
            page += 1
        self.versions.update(dependents)
        return tuple(sorted(dependents))

    def neighbors(self, package: str) -> tuple[str, ...]:
        """Read incoming edges until the requested BFS depth is reached."""
        level = self.levels[package]
        if level >= self.depth:
            return ()
        if package not in self.cache:
            self.cache[package] = self.fetch(package)
        for dependent in self.cache[package]:
            self.levels.setdefault(dependent, level + 1)
        return self.cache[package]

    def build(self, package: str) -> Graph:
        """Traverse API reverse edges using the common recursive BFS."""
        self.levels = {package: 0}
        return recursive_bfs(package, self.neighbors)
