"""Bind a verified CircleCI verdict to the existing signed desk protocol."""

import hashlib
import hmac
import json
from urllib.error import HTTPError
from urllib.request import Request, build_opener

from .circleci_collect import NoRedirect, collect


SITE = "https://www.movan.tech/goldbach"
# Reserve a distinct JS-safe integer range for CircleCI jobs in the shared ledger.
CIRCLECI_RUN_START = 1 << 52


def signed_post(path, payload, secret):
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    request = Request(SITE + path, data=body, headers={
        "Content-Type": "application/json",
        "X-Goldbach-Signature": "sha256=" + signature,
    })
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            result = response.read(8193)
    except HTTPError as error:
        raise ValueError(f"Desk refused {path} (HTTP {error.code})") from None
    if len(result) > 8192:
        raise ValueError("Desk reply exceeds the size limit")
    return json.loads(result)


def publish(expected, handle, circleci_token, secret):
    """Wait for a matching receipt, then record it through the assignment gate."""
    result = collect(expected, circleci_token)
    if result is None:
        return None
    job, verdict, manifest = result
    if not 0 < job < CIRCLECI_RUN_START:
        raise ValueError("CircleCI job number is outside the ledger range")
    run_id = CIRCLECI_RUN_START + job
    authorization = {
        "pr": expected.pr, "head": expected.head, "gap": expected.lemma_id,
        "handle": handle, "statement_sha256": expected.statement_sha256, "run_id": run_id,
    }
    record = {
        "lemma_id": expected.lemma_id, "run_id": run_id, "run_attempt": 1,
        "verdict": verdict, "manifest": manifest, "provider": "circleci",
    }
    response = signed_post("/api/desk/authorize", authorization, secret)
    if response.get("authorized") is not True:
        raise ValueError("Desk did not authorize the CircleCI proof")
    saved = signed_post("/api/verdict", record, secret)
    if saved.get("status") != "stored":
        raise ValueError("Desk did not store the CircleCI verdict")
    return run_id, verdict
