"""Build a machine-readable receipt from the trusted checker process output."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def receipt(code, output):
    lines = output.splitlines()
    manifests = [line.removeprefix("MANIFEST ") for line in lines if line.startswith("MANIFEST ")]
    if code == 0 and lines and lines[-1].startswith("ACCEPTED") and len(manifests) == 1:
        manifest = json.loads(manifests[0])
        if set(manifest) != {"rests_on", "defs"} or not manifest["rests_on"]:
            raise ValueError("Invalid acceptance manifest")
        for entries in manifest.values():
            if not isinstance(entries, list) or any(
                not isinstance(entry, dict)
                or set(entry) != {"module", "sha256"}
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*", entry["module"])
                or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"])
                for entry in entries
            ):
                raise ValueError("Invalid acceptance manifest entry")
        return "ACCEPTED", manifest
    if code == 1 and not manifests and any(line.startswith("REJECTED") for line in lines):
        return "REJECTED", None
    return "FAULT", None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr", type=int)
    for field in ("head", "base", "gap"):
        parser.add_argument(field)
    parser.add_argument("statement", type=Path)
    parser.add_argument("proof", type=Path)
    parser.add_argument("code", type=int)
    parser.add_argument("checker_stdout", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    verdict, manifest = receipt(args.code, args.checker_stdout.read_text(encoding="utf-8", errors="replace"))
    result = dict(pr=args.pr, head=args.head, base=args.base, lemma_id=args.gap, verdict=verdict, manifest=manifest,
                  statement_sha256=hashlib.sha256(args.statement.read_bytes()).hexdigest(),
                  proof_sha256=hashlib.sha256(args.proof.read_bytes()).hexdigest())
    args.destination.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    print(verdict)
    return 3 if verdict == "FAULT" else 0


if __name__ == "__main__":
    raise SystemExit(main())
