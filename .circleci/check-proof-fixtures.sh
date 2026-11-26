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

# Give the compiler access to its module outputs, while keeping verdict files
# and the checked statement under the verifier account.
sudo useradd --system --create-home --shell /usr/sbin/nologin outsider
export PNP_TC_BIN
PNP_TC_BIN=$(cd lean && dirname "$(elan which lake)")
# The VM image restricts traversal of the runner's home by default.
# Expose only the directory traversal required by the locked compiler.
chmod o+x "$HOME" "$HOME/.elan" "$HOME/.elan/toolchains" "$(dirname "$PNP_TC_BIN")" "$PNP_TC_BIN"
sudo -u outsider "$PNP_TC_BIN/lake" --version
export PNP_GITCONFIG="$PWD/.circleci/pilot-gitconfig"
printf '[safe]\n\tdirectory = *\n' > "$PNP_GITCONFIG"
export PNP_BUILD_LOGS="$work"
export PEQUALNP_REAL_LAKE="$PWD/.github/scripts/lake-locked.sh"
export PEQUALNP_HOME="$work/queue"
mkdir "$PEQUALNP_HOME"
printf '2\n' > "$PEQUALNP_HOME/build-jobs.conf"
(cd lean && LAKE_ARTIFACT_CACHE=false PEQUALNP_REAL_LAKE="$PNP_TC_BIN/lake" ../tools/bin/lake build checklemma +Mathlib +PEqualNP.Defs)
chmod -R a+rX,go-w lean
for dir in lib/lean ir; do
    target="lean/.lake/build/$dir/CheckerSuite"
    mkdir -p "$target"
    sudo chown outsider:outsider "$target"
done
node tools/check-lean.mjs lean/CheckerSuite/Pilot.lean "$work/true" > "$work/accepted"
grep '^MANIFEST {' "$work/accepted"
status=0
node tools/check-lean.mjs lean/CheckerSuite/Pilot.lean "$work/false" > "$work/rejected" || status=$?
test "$status" -eq 1
grep '^REJECTED' "$work/rejected"
node tools/check-lean.mjs lean/CheckerSuite/Refutation.lean "$work/false" refute > "$work/refuted"
grep '^MANIFEST {' "$work/refuted"
echo 'Proof, rejection and refutation fixtures passed'
