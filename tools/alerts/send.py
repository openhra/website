#!/usr/bin/env python3
"""Sign and post a JSON alert using only the Python standard library."""

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 8192


def sign(body, timestamp, secret):
    return (
        "sha256="
        + hmac.new(
            secret, str(timestamp).encode("ascii") + b"." + body, hashlib.sha256
        ).hexdigest()
    )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--event",
        default="-",
        help="JSON file, or - for stdin; bytes are sent unchanged",
    )
    parser.add_argument(
        "--secret-file",
        type=Path,
        help="Read the secret from this private file instead of the environment",
    )
    parser.add_argument(
        "--url",
        default="https://plans.openhra.com/api/alerts",
        help="HTTPS receiver URL",
    )
    args = parser.parse_args(argv)
    try:
        url = urllib.parse.urlsplit(args.url)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.fragment
        ):
            raise ValueError()
        secret = (
            args.secret_file.read_bytes().rstrip(b"\r\n")
            if args.secret_file
            else os.environ.get("OPENHRA_ALERT_SECRET", "").encode("utf-8")
        )
        if not secret:
            raise ValueError()
        if args.event == "-":
            body = sys.stdin.buffer.read(MAX_BYTES + 1)
        else:
            with open(args.event, "rb") as stream:
                body = stream.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES or not isinstance(
            json.loads(body.decode("utf-8")), dict
        ):
            raise ValueError()
    except (OSError, ValueError):
        print("alert sender: invalid configuration or event", file=sys.stderr)
        return 1

    timestamp = str(int(time.time()))
    request = urllib.request.Request(
        args.url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-OpenHRA-Timestamp": timestamp,
            "X-OpenHRA-Signature": sign(body, timestamp, secret),
        },
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=10
        ) as response:
            if response.status != 204:
                print("alert sender: unexpected HTTP status", file=sys.stderr)
                return 1
    except urllib.error.HTTPError as error:
        print("alert sender: HTTP " + str(error.code), file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print("alert sender: delivery failed", file=sys.stderr)
        return 1
    print("alert sender: accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
