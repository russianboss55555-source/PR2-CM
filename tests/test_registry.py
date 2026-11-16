"""Exercise direct Cargo index reading and failure handling over HTTP."""

import json
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

    def test_direct_dependencies(self):
        """Use SemVer and keep renamed, optional, and target declarations."""
        older = dict(name="demo", vers="1.9.0", deps=[])
        yanked = dict(name="demo", vers="2.0.0", deps=[], yanked=True)
        dependency = dict(
            name="alias", package="ab", req="^2", kind="build",
            target="cfg(unix)", optional=True,
        )
        latest = dict(name="demo", vers="1.10.0", deps=[dependency])
        self.write_index("de/mo/demo", latest, older, yanked)
        result = self.run_cli("Demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "demo v1.10.0",
            "ab as alias ^2 [build, optional, cfg(unix)]",
        ])

    def test_missing_crate(self):
        """A missing sparse-index file yields a diagnosis and exit code 1."""
        result = self.run_cli("zzz")
        self.assertEqual(result.returncode, 1)
        self.assertIn("was not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
