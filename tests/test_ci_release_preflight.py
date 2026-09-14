"""CI configuration failures are explicit and never disclose credentials."""

import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

from scripts import ci_release_preflight as preflight


class CiPreflightTests(unittest.TestCase):
    def run_preflight(self, environment):
        output = io.StringIO()
        with patch.dict(os.environ, environment, clear=True), contextlib.redirect_stdout(output):
            code = preflight.main()
        return code, json.loads(output.getvalue()), output.getvalue()

    def test_missing_configuration_blocks_hosted_work(self):
        code, report, _ = self.run_preflight({})
        self.assertEqual(code, 1)
        self.assertFalse(report["readyForHostedTests"])
        self.assertEqual(len(report["missingConfiguration"]), 2)

    def test_configured_credentials_do_not_become_release_evidence_or_output(self):
        credential = "synthetic-private-ci-token"
        account = "a" * 32
        code, report, text = self.run_preflight(
            {"CLOUDFLARE_API_TOKEN": credential, "CLOUDFLARE_ACCOUNT_ID": account}
        )
        self.assertEqual(code, 0)
        self.assertTrue(report["readyForHostedTests"])
        self.assertFalse(report["releaseEligible"])
        self.assertNotIn(credential, text)
        self.assertNotIn(account, text)


if __name__ == "__main__":
    unittest.main()
