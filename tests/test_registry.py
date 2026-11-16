"""Exercise direct Cargo index reading and failure handling over HTTP."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


MAIN = Path(__file__).resolve().parents[1] / "src" / "main.py"


class IndexHandler(SimpleHTTPRequestHandler):
    """Keep HTTP access logs out of the test output."""

    def log_message(self, format, *args):
        """Ignore routine requests from the subprocess."""


class RegistryTests(unittest.TestCase):
    """Test the real CLI against a controlled HTTP registry."""

    def setUp(self):
        """Start a loopback server with a temporary sparse index."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        handler = partial(IndexHandler, directory=folder.name)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        Thread(target=server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{server.server_port}"

    def write_index(self, path, *entries):
        """Write one JSON line for each release."""
        filename = self.folder / path
        filename.parent.mkdir(parents=True, exist_ok=True)
        data = "\n".join(json.dumps(entry) for entry in entries)
        filename.write_text(data, encoding="utf-8")

    def run_cli(self, package, *options):
        """Run the program against the loopback HTTP index."""
        return subprocess.run(
            [sys.executable, str(MAIN), "--package", package, "--source",
             self.url, "--output", str(self.folder / "graph.svg"), *options],
            capture_output=True, text=True, check=False,
        )

    def populate_demo(self):
        """Create an index with ranges, a renamed crate and optional crates."""
        required = dict(name="alias", package="ab", req="^1.5", kind="build")
        optional = dict(name="xyz", req="^1", optional=True)
        release = dict(
            name="demo", vers="1.10.0", deps=[required, optional],
            features={"default": ["extra"], "extra": ["dep:xyz"]},
        )
        self.write_index(
            "de/mo/demo", release, dict(name="demo", vers="1.9.0", deps=[]),
            dict(name="demo", vers="2.0.0", deps=[], yanked=True),
        )
        self.write_index(
            "2/ab", *(dict(name="ab", vers=v, deps=[])
                      for v in ("1.4.0", "1.10.0", "2.0.0")),
        )
        self.write_index("3/x/xyz", dict(name="xyz", vers="1.0.0", deps=[]))

    @unittest.skipUnless(shutil.which("dot"), "requires Graphviz")
    def test_registry_graph(self):
        """Resolve a version range and follow an optional default feature."""
        self.populate_demo()
        result = self.run_cli("Demo", "--ascii-tree")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[:3], [
            "demo v1.10.0", "+-- ab v1.10.0", "`-- xyz v1.0.0",
        ])
        dot = (self.folder / "graph.dot").read_text(encoding="utf-8")
        self.assertIn('"demo v1.10.0" -> "ab v1.10.0";', dot)
        self.assertIn('"demo v1.10.0" -> "xyz v1.0.0";', dot)

    def test_missing_crate(self):
        """A missing sparse-index file yields a diagnosis and exit code 1."""
        result = self.run_cli("zzz")
        self.assertEqual(result.returncode, 1)
        self.assertIn("was not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
