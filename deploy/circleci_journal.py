"""Durable dispatch records for the ECS CircleCI scheduler."""

from contextlib import closing
import sqlite3


class DispatchJournal:
    def __init__(self, path):
        self.path = path
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS circleci_dispatches (
                    pr INTEGER NOT NULL,
                    head TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    pipeline_id TEXT UNIQUE,
                    delivered INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (pr, head)
                )
            """)

    def reserve(self, pr, head, payload):
        """Claim a submission before making the non-idempotent CircleCI POST."""
        with closing(sqlite3.connect(self.path)) as db, db:
            inserted = db.execute("""
                INSERT INTO circleci_dispatches (pr, head, payload)
                VALUES (?, ?, ?) ON CONFLICT(pr, head) DO NOTHING
            """, (pr, head, payload))
            return inserted.rowcount == 1

    def attach(self, pr, head, pipeline_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            updated = db.execute("""
                UPDATE circleci_dispatches SET pipeline_id = ?
                WHERE pr = ? AND head = ? AND (pipeline_id IS NULL OR pipeline_id = ?)
            """, (pipeline_id, pr, head, pipeline_id))
            if updated.rowcount != 1:
                raise ValueError("Pipeline conflicts with the recorded dispatch")

    def pending(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("""
                SELECT pr, head, payload, pipeline_id FROM circleci_dispatches
                WHERE delivered = 0 ORDER BY rowid
            """).fetchall()

    def delivered(self, pipeline_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE circleci_dispatches SET delivered = 1 WHERE pipeline_id = ?", (pipeline_id,))
