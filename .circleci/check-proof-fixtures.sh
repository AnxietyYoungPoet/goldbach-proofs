#!/usr/bin/env bash
set -euo pipefail
work=$(mktemp -d)
test ! -e lean/CheckerSuite
trap 'rm -rf -- "$work" lean/CheckerSuite' EXIT
mkdir lean/CheckerSuite
printf 'import Mathlib\ntheorem CheckerSuite.Pilot : True := True.intro\n' > lean/CheckerSuite/Pilot.lean
printf 'True' > "$work/true"
printf 'False' > "$work/false"
printf 'import Mathlib\ntheorem CheckerSuite.Refutation : ¬ False := not_false\n' > lean/CheckerSuite/Refutation.lean
curl --retry 4 -fsSL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --no-modify-path --default-toolchain none
export PATH="$HOME/.elan/bin:$PATH"
(cd lean && elan toolchain install "$(cat lean-toolchain)" && lake exe cache get)
node tools/check-lean.mjs lean/CheckerSuite/Pilot.lean "$work/true" > "$work/accepted"
grep '^MANIFEST {' "$work/accepted"
status=0
node tools/check-lean.mjs lean/CheckerSuite/Pilot.lean "$work/false" > "$work/rejected" || status=$?
test "$status" -eq 1
grep '^REJECTED' "$work/rejected"
node tools/check-lean.mjs lean/CheckerSuite/Refutation.lean "$work/false" refute > "$work/refuted"
grep '^MANIFEST {' "$work/refuted"
echo 'Proof, rejection and refutation fixtures passed'
