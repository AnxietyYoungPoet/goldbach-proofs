"""Dispatch a pinned proof to CircleCI and retain its pipeline for collection."""

from dataclasses import asdict
import json
from urllib.request import Request, build_opener
from uuid import UUID

from .circleci_collect import API, NoRedirect
from .circleci_evidence import PROJECT


def dispatch(journal, expected, handle, token):
    """Reserve before posting. An uncertain POST remains reserved for reconciliation."""
    data = asdict(expected)
    data.pop("pipeline_id")
    data["handle"] = handle
    if not journal.reserve(expected.pr, expected.head, json.dumps(data, sort_keys=True)):
        return None

    message = {
        "branch": expected.branch,
        "parameters": {
            "pilot-pr": expected.pr,
            "pilot-head": expected.head,
            "pilot-gap": expected.lemma_id,
        },
    }
    request = Request(API + f"project/{PROJECT}/pipeline", json.dumps(message).encode(), {
        "Content-Type": "application/json",
        "Circle-Token": token,
    })
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("CircleCI dispatch response exceeds the size limit")
    pipeline = json.loads(raw)
    pipeline_id = str(UUID(pipeline["id"]))
    journal.attach(expected.pr, expected.head, pipeline_id)
    return pipeline_id
