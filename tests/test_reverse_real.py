"""Check crates.io reverse API pagination, identity mapping and traversal."""

import json
import subprocess
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reverse_api import ReverseApi, decode_page


def payload(target: str, names: tuple[str, ...], total=None) -> dict:
    """Represent the API where crate_id identifies the requested target."""
    dependencies = [
        {"crate_id": target, "version_id": index, "kind": "normal"}
        for index, _ in enumerate(names)
    ]
    versions = [
        {"id": index, "crate": name, "num": "1.2.3"}
        for index, name in enumerate(names)
    ]
    return {
        "dependencies": dependencies, "versions": list(reversed(versions)),
        "meta": {"total": len(names) if total is None else total},
    }


class ApiHandler(BaseHTTPRequestHandler):
    """Serve a controlled JSON response using the real URL structure."""

    def log_message(self, format, *args):
        """Keep loopback access logs out of test output."""

    def do_GET(self):
        """Record the path and headers, then return the fixture response."""
        self.server.recorded.append((self.path, self.headers))
        parsed = urlsplit(self.path)
        if parsed.path != "/api/v1/crates/root/reverse_dependencies":
            self.send_error(404)
            return
        data = json.dumps(payload("root", ("left", "right"))).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ReverseApiTests(unittest.TestCase):
    """Read actual dependent identities and preserve shared BFS behavior."""

    def test_all_pages_and_version_id_join(self):
        """Read beyond the first page and join IDs to dependent versions."""
        pages = [payload("root", ("left", "right"), 3),
                 payload("root", ("tail",), 3)]
        api = ReverseApi("https://crates.io/api/v1")
        with patch.object(api, "read_page", side_effect=pages) as read:
            graph = api.build("root")
        self.assertEqual(graph["root"], ("left", "right", "tail"))
        self.assertNotIn("root", api.versions)
        self.assertEqual(api.versions["tail"], "1.2.3")
        self.assertEqual(read.call_args_list[1].args, ("root", 2))

    def test_recursive_bfs_depth_cycles_and_shared_nodes(self):
        """Bound network expansion by levels and query shared nodes once."""
        entries = {
            "root": payload("root", ("left", "right")),
            "left": payload("left", ("leaf", "root")),
            "right": payload("right", ("leaf",)),
        }
        api = ReverseApi("https://crates.io/api/v1", depth=2)
        with patch.object(api, "read_page") as read:
            read.side_effect = lambda package, page: entries[package]
            graph = api.build("root")
        self.assertEqual(list(graph), ["root", "left", "right", "leaf"])
        self.assertEqual(graph["left"], ("leaf", "root"))
        self.assertEqual(read.call_count, 3)
        self.assertEqual(graph["leaf"], ())

    def test_empty_result(self):
        """An existing crate with no dependents returns a one-node graph."""
        api = ReverseApi("https://crates.io/api/v1")
        with patch.object(api, "read_page", return_value=payload("root", ())):
            self.assertEqual(api.build("root"), {"root": ()})

    def test_incomplete_pagination_is_an_error(self):
        """Reject an empty page if the API still promises more results."""
        api = ReverseApi("https://crates.io/api/v1")
        empty_page = payload("root", (), 2)
        with patch.object(api, "read_page", return_value=empty_page):
            with self.assertRaisesRegex(ValueError, "incomplete"):
                api.build("root")

    def test_broken_version_id_is_an_error(self):
        """Expose malformed API identities instead of reporting the root."""
        data = payload("root", ("left",))
        data["versions"] = []
        with self.assertRaises(KeyError):
            decode_page(data)


class ApiCliTests(unittest.TestCase):
    """Execute the real launcher code against a loopback API endpoint."""

    def setUp(self):
        """Start a server and retain received requests for assertions."""
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.server.recorded = []
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/v1"

    def run_cli(self, package="root", *options):
        """Run the API demo using the active Python interpreter."""
        return subprocess.run([
            sys.executable, str(ROOT / "demo" / "reverse_real.py"),
            "--package", package, "--source", self.url, *options,
        ], capture_output=True, text=True, check=False)

    def test_http_url_headers_and_reverse_output(self):
        """Call reverse_dependencies and print actual incoming crate names."""
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("root <- left v1.2.3", result.stdout)
        self.assertIn("root <- right v1.2.3", result.stdout)
        self.assertIn("Found: 2 reverse dependents", result.stdout)
        path, headers = self.server.recorded[0]
        query = parse_qs(urlsplit(path).query)
        self.assertEqual(query, {"page": ["1"], "per_page": ["100"]})
        self.assertIn("PR2-CM", headers["User-Agent"])

    def test_http_not_found(self):
        """Report an API failure with an unsuccessful exit code."""
        result = self.run_cli("missing")
        self.assertEqual(result.returncode, 1)
        self.assertIn("API HTTP 404", result.stderr)
        self.assertNotIn("Found:", result.stdout)

    def test_bad_depth(self):
        """Validate the depth before performing any HTTP requests."""
        result = self.run_cli("root", "--depth", "0")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.server.recorded)
