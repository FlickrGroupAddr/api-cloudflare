"""Fail before hosted CI work unless dedicated credentials are configured."""

import json
import os
import re


def main() -> int:
    missing = []
    if not os.environ.get("CLOUDFLARE_API_TOKEN", "").strip():
        missing.append("FGA_CLOUDFLARE_CI_TOKEN")
    if not re.fullmatch(r"[a-f0-9]{32}", os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")):
        missing.append("FGA_CLOUDFLARE_ACCOUNT_ID")
    print(
        json.dumps(
            {
                "readyForHostedTests": not missing,
                "missingConfiguration": missing,
                "releaseEligible": False,
            }
        )
    )
    return int(bool(missing))


if __name__ == "__main__":
    raise SystemExit(main())
