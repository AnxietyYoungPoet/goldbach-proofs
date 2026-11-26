"""Validate CircleCI evidence against a dispatch recorded by the ECS scheduler."""

import re
from dataclasses import dataclass


PROJECT = "gh/CGandGameEngineLearner/goldbach-proofs"
REPOSITORY = "https://github.com/CGandGameEngineLearner/goldbach-proofs"
SHA256 = re.compile(r"[a-f0-9]{64}")
MODULE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*")


@dataclass(frozen=True)
class Dispatch:
    pipeline_id: str
    branch: str
    base: str
    pr: int
    head: str
    lemma_id: str
    proof_sha256: str
    statement_sha256: str
    module: str


def checked_job(expected, pipeline, workflow, job):
    """Reject evidence from a different pipeline, checkout, or workflow."""
    vcs = pipeline.get("vcs", {})
    if (pipeline.get("id") != expected.pipeline_id
            or pipeline.get("project_slug") != PROJECT
            or vcs.get("target_repository_url") != REPOSITORY
            or vcs.get("branch") != expected.branch
            or vcs.get("revision") != expected.base
            or workflow.get("pipeline_id") != expected.pipeline_id
            or workflow.get("name") != "proof-fixture-pilot"
            or workflow.get("status") != "success"
            or job.get("name") != "lean-proof-fixtures"
            or job.get("status") != "success"):
        raise ValueError("CircleCI job does not match the recorded dispatch")
    number = job.get("job_number")
    if type(number) is not int or number < 1:
        raise ValueError("Invalid CircleCI job number")
    return number


def checked_verdict(expected, result):
    for field in ("pr", "head", "base", "lemma_id", "proof_sha256", "statement_sha256"):
        value = getattr(expected, field)
        if type(result.get(field)) is not type(value) or result[field] != value:
            raise ValueError(f"CircleCI proof receipt has a mismatched {field}")
    verdict, manifest = result.get("verdict"), result.get("manifest")
    if verdict == "REJECTED" and manifest is None:
        return verdict, manifest
    if verdict != "ACCEPTED" or not isinstance(manifest, dict) or set(manifest) != {"rests_on", "defs"}:
        raise ValueError("CircleCI did not return an authoritative verdict")
    for entries in manifest.values():
        if not isinstance(entries, list) or any(
            not isinstance(entry, dict)
            or not isinstance(entry.get("module"), str)
            or not MODULE.fullmatch(entry["module"])
            or not isinstance(entry.get("sha256"), str)
            or not SHA256.fullmatch(entry["sha256"])
            for entry in entries
        ):
            raise ValueError("Invalid CircleCI proof manifest")
    if not any(entry["module"] == expected.module and entry["sha256"] == expected.proof_sha256
               for entry in manifest["rests_on"]):
        raise ValueError("Manifest does not attest the submitted proof bytes")
    return verdict, manifest
