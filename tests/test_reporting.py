import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from http.client import IncompleteRead
from unittest.mock import patch

os.environ["OA_MCP_TOKEN"] = ""
os.environ["OA_MCP_URL"] = "https://example.invalid"

import pipeline
from oa_client import OAClient
from test_ledger import OPEN, BUY, SELL

SAMPLE = Path(pipeline.__file__).parent / "samples/portfolio.beancount"


class ReportingTests(unittest.TestCase):
    def test_default_cli_survives_a_non_unicode_output_encoding(self):
        environment = {"PYTHONIOENCODING": "cp1252", "OA_MCP_TOKEN": "", "OA_MCP_URL": "https://example.invalid"}
        if os.name == "nt":
            environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        result = subprocess.run(
            [sys.executable, str(Path(pipeline.__file__))],
            env=environment,
            capture_output=True, text=True, encoding="cp1252", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unverified sample rules", result.stdout)

    def test_provider_text_is_escaped(self):
        oa = OAClient(token=None)
        slug = oa.start("example", "US")["skills_to_load"][0]
        skill = oa.get_skill(slug)
        skill["name"] = "Provider\x1b[2J\rname"
        output = io.StringIO()
        with patch.object(oa, "get_skill", return_value=skill), contextlib.redirect_stdout(output):
            pipeline.run(str(SAMPLE), oa)
        self.assertNotIn("\x1b", output.getvalue())
        self.assertNotIn("\r", output.getvalue())
        self.assertIn("\\x1b", output.getvalue())

    def test_truncated_live_response_returns_a_controlled_failure(self):
        oa = OAClient(token="synthetic-test-token")
        output, error = io.StringIO(), io.StringIO()
        with patch.object(pipeline, "OAClient", return_value=oa):
            with patch("urllib.request.urlopen", side_effect=IncompleteRead(b"{", 100)):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    result = pipeline.main(["pipeline.py", "--live", str(SAMPLE)])
        self.assertEqual(result, 2)
        self.assertIn("HTTP response", error.getvalue())
        self.assertNotIn("unverified sample rules", output.getvalue())

    def test_default_cli_selects_offline_mode_explicitly(self):
        with patch.object(pipeline, "OAClient", return_value=OAClient(token=None)) as constructor:
            with patch.object(pipeline, "run", return_value=True), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pipeline.main(["pipeline.py"]), 0)
        constructor.assert_called_once_with(token=None)

    def run_ledger(self, content, oa):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "example.beancount"
            source.write_text(content, encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            with patch.object(pipeline, "OAClient", return_value=oa):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    result = pipeline.main(["pipeline.py", str(source)])
        return result, output.getvalue(), error.getvalue()

    def test_late_invalid_input_never_reports_partial_gains_or_calls_provider(self):
        oa = OAClient(token=None)
        with patch.object(oa, "start", side_effect=AssertionError("No provider call for invalid input")):
            result, output, error = self.run_ledger(OPEN + BUY + SELL + "unsupported\x1b[2J\n", oa)
        self.assertEqual(result, 2)
        self.assertIn("unsupported ledger syntax", error)
        self.assertNotIn("Basis", output)
        self.assertNotIn("\x1b", output + error)

    def test_purchase_only_ledger_explains_that_no_classification_was_performed(self):
        oa = OAClient(token=None)
        with patch.object(oa, "start", side_effect=AssertionError("No provider call without disposals")):
            result, output, error = self.run_ledger(OPEN + BUY, oa)
        self.assertEqual(result, 0, error)
        self.assertIn("no gain classification was performed", output)
        self.assertNotIn("unverified sample rules", output)

    def test_unsupported_rules_preserve_known_basis_and_proceeds(self):
        oa = OAClient(token=None)
        with patch.object(oa, "get_skill", return_value={"rules": {}}):
            result, output, error = self.run_ledger(OPEN + BUY + SELL, oa)
        self.assertEqual(result, 2, error)
        self.assertIn("Basis USD 10.00", output)
        self.assertIn("proceeds USD 30.00", output)
        self.assertIn("Unsupported rule contract", output)


if __name__ == "__main__":
    unittest.main()
