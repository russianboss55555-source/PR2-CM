"""Check Cargo range syntax and version ordering with edge cases."""

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from requirements import matches, parse_requirement
from versions import parse_version


class RequirementTests(unittest.TestCase):
    """Cover version selection for common Cargo declarations."""

    def test_comparators(self):
        """Recognize strict bounds, partial versions and compatibility."""
        cases = (
            ("^0.2.3", "0.2.9", True),
            ("^0.2.3", "0.3.0", False),
            ("^0.0.3", "0.0.4", False),
            ("^1.2.3", "1.10.0", True),
            ("~1.2", "1.3.0", False),
            ("1.2.*", "1.2.9", True),
            (">1.2", "1.2.9", False),
            ("<=1.2", "1.2.9", True),
            (">=1.2, <2", "2.0.0", False),
            ("=1.2", "1.2.2", True),
            ("*", "2.0.0-beta", False),
            ("^2.0.0-beta.2", "2.0.0-beta.10", True),
            ("^2.0.0-beta.2", "2.1.0-beta.10", False),
        )
        for requirement, version, expected in cases:
            with self.subTest(requirement=requirement, version=version):
                result = matches(
                    parse_version(version), parse_requirement(requirement)
                )
                self.assertEqual(result, expected)
