"""Process persisted CircleCI dispatches on ECS."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import URLError

from .circleci_collect import collect, fetch_json
from .circleci_evidence import Dispatch
from .circleci_journal import DispatchJournal
from .circleci_register import publish


def process(journal, token, secret=None):
    failures = 0
    for pr, head, payload, pipeline_id in journal.pending():
        if pipeline_id is None:
            print(f"PR {pr}: dispatch requires reconciliation")
            continue
        try:
            values = json.loads(payload)
            handle = values.pop("handle")
            expected = Dispatch(pipeline_id=pipeline_id, **values)
            if (expected.pr, expected.head) != (pr, head):
                raise ValueError("Dispatch journal identity mismatch")
            if secret is None:
                result = collect(expected, token)
            else:
                pull = fetch_json(
                    f"https://api.github.com/repos/CGandGameEngineLearner/goldbach-proofs/pulls/{pr}",
                    {"Accept": "application/vnd.github+json"}, 2 * 1024 * 1024,
                )
                if (pull["state"] != "open" or pull["head"]["sha"] != head
                        or pull["base"]["ref"] != "main"
                        or pull["user"]["login"].casefold() != handle.casefold()):
                    raise ValueError("Pull request changed after dispatch")
                result = publish(expected, handle, token, secret)
        except (ValueError, KeyError, TypeError, URLError) as error:
            # Never print request headers, tokens or an artifact download URL.
            print(f"PR {pr}: receipt unavailable ({type(error).__name__})")
            failures += 1
            continue
        if result is None:
            print(f"PR {pr}: pending")
            continue
        print(f"PR {pr}: {result[1]}")
        if secret is not None:
            journal.delivered(pipeline_id)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journal", type=Path)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    directory = Path(os.environ["CREDENTIALS_DIRECTORY"])
    token = (directory / "circleci-token").read_text().strip()
    secret = (directory / "webhook").read_bytes().strip() if args.publish else None
    if not token or secret == b"":
        raise SystemExit("Missing CircleCI or desk credential")
    return int(bool(process(DispatchJournal(args.journal), token, secret)))


if __name__ == "__main__":
    raise SystemExit(main())
