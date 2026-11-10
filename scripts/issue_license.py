"""Issue a GridFork production license key. Founder-only.

The signing secret lives ONLY with the licensor: pass it via
GRIDFORK_LICENSE_SECRET (env var or password manager), never in the repo,
chat, or shell history files you keep.

Usage:
    set GRIDFORK_LICENSE_SECRET=<secret>   (Windows, this window only)
    python scripts/issue_license.py --sub buyer@example.com --days 365
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from license_gate import LicenseError, issue_license_key


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue a GridFork license key.")
    parser.add_argument("--sub", required=True, help="Licensee email.")
    parser.add_argument("--days", required=True, type=int, help="Days valid.")
    args = parser.parse_args()
    secret = os.environ.get("GRIDFORK_LICENSE_SECRET", "")
    if not secret:
        print("GRIDFORK_LICENSE_SECRET is not set.", file=sys.stderr)
        return 2
    try:
        print(issue_license_key(secret, args.sub, args.days))
    except LicenseError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
