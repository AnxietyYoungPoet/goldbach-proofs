import unittest
from dataclasses import asdict

from deploy.circleci_evidence import Dispatch, PROJECT, REPOSITORY, checked_job, checked_verdict


class CircleCIEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.expected = Dispatch("pipeline", "worker", "a"*40, 2546, "b"*40,
                                 "L-example", "c"*64, "d"*64, "PEqualNP.Outside.L_example")
        self.result = asdict(self.expected)
        self.result.update(verdict="ACCEPTED", manifest={
            "rests_on": [{"module": self.expected.module, "sha256": self.expected.proof_sha256}], "defs": [],
        })

    def test_success_and_mismatches(self):
        self.assertEqual(checked_verdict(self.expected, self.result)[0], "ACCEPTED")
        for field in ("head", "base", "lemma_id", "proof_sha256", "statement_sha256"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                checked_verdict(self.expected, {**self.result, field: "different"})
        with self.assertRaises(ValueError):
            checked_verdict(self.expected, {**self.result, "manifest": {"rests_on": [], "defs": []}})

    def test_fault_and_rejection(self):
        self.assertEqual(checked_verdict(self.expected, {**self.result, "verdict": "REJECTED", "manifest": None}),
                         ("REJECTED", None))
        with self.assertRaises(ValueError):
            checked_verdict(self.expected, {**self.result, "verdict": "FAULT", "manifest": None})

    def test_job_identity(self):
        pipeline = dict(id="pipeline", project_slug=PROJECT, vcs={
            "target_repository_url": REPOSITORY, "branch": "worker", "revision": self.expected.base,
        })
        workflow = dict(pipeline_id="pipeline", name="proof-fixture-pilot", status="success")
        job = dict(name="lean-proof-fixtures", status="success", job_number=17)
        self.assertEqual(checked_job(self.expected, pipeline, workflow, job), 17)
        with self.assertRaises(ValueError):
            checked_job(self.expected, pipeline, workflow, {**job, "status": "failed"})
        with self.assertRaises(ValueError):
            checked_job(self.expected, pipeline, {**workflow, "pipeline_id": "other"}, job)
