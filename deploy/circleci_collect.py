"""Collect a proof receipt from a recorded CircleCI pipeline."""

import json
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from .circleci_evidence import PROJECT, checked_job, checked_verdict


API = "https://circleci.com/api/v2/"
ARTIFACT = "proof-receipt/verdict.json"
RUNNING = {"running", "queued", "not_run", "on_hold", "created", "pending"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def fetch_json(url, headers, limit):
    with build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=20) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError("CircleCI response exceeds the size limit")
    return json.loads(body)


def artifact_json(url):
    location = urlsplit(url)
    if (location.scheme != "https" or location.hostname != "output.circle-artifacts.com"
            or location.username is not None or location.port is not None):
        raise ValueError("Unexpected CircleCI artifact origin")
    # The public project's artifact is fetched without the ECS API credential.
    return fetch_json(url, {}, 256 * 1024)


def collect(expected, token):
    """Return (job number, verdict, manifest), or None while the run is pending."""
    def api(path):
        return fetch_json(API + path, {"Circle-Token": token, "Accept": "application/json"}, 2 * 1024 * 1024)

    pipeline_id = str(UUID(expected.pipeline_id))
    pipeline = api(f"pipeline/{pipeline_id}")
    if pipeline["state"] == "errored":
        raise ValueError("CircleCI pipeline could not be created")
    workflows = [item for item in api(f"pipeline/{pipeline_id}/workflow")["items"]
                 if item["name"] == "proof-fixture-pilot"]
    if not workflows or all(item["status"] in RUNNING for item in workflows):
        return None
    if len(workflows) != 1:
        raise ValueError("CircleCI returned an ambiguous proof workflow")
    workflow = workflows[0]
    if workflow["status"] != "success":
        raise ValueError("CircleCI workflow ended without a verified receipt")
    workflow_id = str(UUID(workflow["id"]))
    jobs = [item for item in api(f"workflow/{workflow_id}/job")["items"]
            if item["name"] == "lean-proof-fixtures"]
    if len(jobs) != 1:
        raise ValueError("CircleCI returned an ambiguous proof job")
    number = checked_job(expected, pipeline, workflow, jobs[0])
    artifacts = api(f"project/{PROJECT}/{number}/artifacts")["items"]
    urls = [item["url"] for item in artifacts if item["path"] == ARTIFACT]
    if len(urls) != 1:
        raise ValueError("CircleCI proof job did not store exactly one verdict receipt")
    verdict, manifest = checked_verdict(expected, artifact_json(urls[0]))
    return number, verdict, manifest
