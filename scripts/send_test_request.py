#!/usr/bin/env python3
"""Send a test classification request to the Guardian backend.

Usage:
    python scripts/send_test_request.py [--url URL] [--token TOKEN]

The script sends a sample payload to POST /api/v1/classify and prints
the response.
"""

import argparse
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def main() -> None:
    parser = argparse.ArgumentParser(description="Test /api/v1/classify endpoint")
    parser.add_argument(
        "--url",
        default="http://localhost:5000/api/v1/classify",
        help="Full URL of the classify endpoint",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Firebase ID token for the Authorization header",
    )
    args = parser.parse_args()

    payload = {
        "dedup_key": "test-dedup-001",
        "app_package": "com.whatsapp",
        "app_name": "WhatsApp",
        "sender": "TestUser",
        "text": "Dasar bodoh kamu, gak pantes sekolah di sini",
        "posted_at": "2025-01-15T10:30:00Z",
    }

    headers = {"Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    body = json.dumps(payload).encode("utf-8")
    req = Request(args.url, data=body, headers=headers, method="POST")

    try:
        with urlopen(req) as resp:
            status = resp.status
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        status = exc.code
        data = json.loads(exc.read().decode("utf-8"))

    print(f"Status: {status}")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    sys.exit(0 if 200 <= status < 300 else 1)


if __name__ == "__main__":
    main()
