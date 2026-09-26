import io
import json
import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ["OA_MCP_TOKEN"] = ""
os.environ["OA_MCP_URL"] = "https://example.invalid"

from oa_client import OAClient


class AdapterTests(unittest.TestCase):
    def call(self, payload):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(payload.encode("utf-8"))):
            return OAClient(token="synthetic-test-token").get_skill("example")

    def test_numeric_tokens_survive_both_decoders(self):
        for value in ("1e-1000", "-1e-1000", "1.0000000000000001"):
            skill = '{"value":' + value + '}'
            responses = [
                '{"jsonrpc":"2.0","id":1,"result":{"structuredContent":' + skill + '}}',
                json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": skill}]}}),
            ]
            for payload in responses:
                with self.subTest(value=value, payload=payload):
                    result = self.call(payload)
                    self.assertIsInstance(result["value"], Decimal)
                    self.assertEqual(result["value"], Decimal(value))

    def test_unrepresentable_decimal_tokens_fail_at_both_boundaries(self):
        skill = '{"value":1e999999999999999999999}'
        responses = [
            '{"jsonrpc":"2.0","id":1,"result":{"structuredContent":' + skill + '}}',
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": skill}]}}),
        ]
        for payload in responses:
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, "invalid JSON decimal"):
                self.call(payload)

    def test_nonstandard_json_constants_are_rejected_even_in_metadata(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            skill = '{"tier":' + constant + ',"rules":{}}'
            responses = [
                '{"jsonrpc":"2.0","id":1,"result":{"structuredContent":' + skill + '}}',
                json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": skill}]}}),
            ]
            for payload in responses:
                with self.subTest(constant=constant, payload=payload), self.assertRaisesRegex(ValueError, "non-standard JSON"):
                    self.call(payload)

    def test_tool_errors_do_not_supply_successful_data(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"isError": True, "structuredContent": {"value": 0}}}
        with self.assertRaisesRegex(RuntimeError, "tool returned an error"):
            self.call(json.dumps(payload))

    def test_malformed_envelopes_fail_explicitly(self):
        malformed = [None, {}, {"result": None}, {"result": []},
                     {"result": {"content": [None]}}, {"result": {"content": [{"text": 10}]}},
                     {"result": {"content": []}}, {"result": {"structuredContent": None}}]
        for value in malformed:
            if isinstance(value, dict):
                value = {"jsonrpc": "2.0", "id": 1, **value}
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.call(json.dumps(value))

    def test_sample_mutation_does_not_change_a_later_response(self):
        oa = OAClient(token=None)
        start = oa.start("example", "US")
        slug = start["skills_to_load"][0]
        start["skills_to_load"].clear()
        self.assertEqual(oa.start("example", "US")["skills_to_load"], [slug])
        skill = oa.get_skill(slug)
        expected = dict(skill["rules"])
        skill["rules"].clear()
        self.assertEqual(oa.get_skill(slug)["rules"], expected)


if __name__ == "__main__":
    unittest.main()
