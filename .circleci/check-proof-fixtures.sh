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
target_dir=CheckerSuite
if [[ "${PILOT_PR:-0}" != 0 ]]; then
    bash .circleci/prepare-proof.sh "$PILOT_PR" "$PILOT_HEAD" "$PILOT_GAP" "$work/input"
    proof_path=$(cat "$work/input/pr.file")
    target_dir=PEqualNP/Outside
fi
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
(
    cd lean
    # Hide the outside tree during trusted prebuild, including any previously
    # accepted dependencies that still compile with the locked account.
    if [[ -d PEqualNP/Outside ]]; then
        mv PEqualNP/Outside "$work/Outside"
        restore_outside() {
            [[ ! -e PEqualNP/Outside && ! -L PEqualNP/Outside ]] || exit 3
            mv "$work/Outside" PEqualNP/Outside
        }
        trap restore_outside EXIT
    fi
    targets=(checklemma +Mathlib +PEqualNP.Defs)
    if [[ -f "$work/input/base-imports.txt" ]]; then
        while IFS= read -r dependency; do
            [[ -z "$dependency" ]] || targets+=("+$dependency")
        done < "$work/input/base-imports.txt"
    fi
    LAKE_ARTIFACT_CACHE=false PEQUALNP_REAL_LAKE="$PNP_TC_BIN/lake" ../tools/bin/lake build "${targets[@]}"
)
chmod -R a+rX,go-w lean
for dir in lib/lean ir; do
    target="lean/.lake/build/$dir/$target_dir"
    mkdir -p "$target"
    sudo chown outsider:outsider "$target"
done
if [[ "$target_dir" == PEqualNP/Outside ]]; then
    install -m 0644 "$work/input/proof.lean" "$proof_path"
    printf 'PR %s head %s base %s\n' "$PILOT_PR" "$PILOT_HEAD" "$(git rev-parse HEAD)"
    sha256sum "$work/input/statement.txt" "$proof_path"
    result_dir=/tmp/goldbach-proof-receipt
    mkdir -m 700 "$result_dir"
    sha256sum "$work/input/statement.txt" "$proof_path" .github/scripts/lake-locked.sh \
        lean/.lake/build/bin/checklemma > "$work/inputs.sha256"
    while IFS= read -r dependency; do
        [[ -z "$dependency" ]] || sha256sum "$dependency" >> "$work/inputs.sha256"
    done < "$work/input/outside-sources.txt"
    touch "$work/build.marker"
    status=0
    timeout -k 30 2700 node tools/check-lean.mjs "$proof_path" "$work/input/statement.txt" \
        > "$work/checker.stdout" 2> "$work/checker.stderr" || status=$?
    sudo pkill -KILL -u outsider || true
    sha256sum -c "$work/inputs.sha256"
    module=${proof_path#lean/}
    bash .github/scripts/build-ownership.sh lean/.lake/build "$work/build.marker" \
        "lean/.lake/build/lib/lean/${module%.lean}.olean" "$status"
    python3 .circleci/proof-receipt.py "$PILOT_PR" "$PILOT_HEAD" "$(git rev-parse HEAD)" "$PILOT_GAP" \
        "$work/input/statement.txt" "$proof_path" "$status" "$work/checker.stdout" "$result_dir/verdict.json"
    exit
fi
node tools/check-lean.mjs lean/CheckerSuite/Pilot.lean "$work/true" > "$work/accepted"
grep '^MANIFEST {' "$work/accepted"
status=0
node tools/check-lean.mjs lean/CheckerSuite/Pilot.lean "$work/false" > "$work/rejected" || status=$?
test "$status" -eq 1
grep '^REJECTED' "$work/rejected"
node tools/check-lean.mjs lean/CheckerSuite/Refutation.lean "$work/false" refute > "$work/refuted"
grep '^MANIFEST {' "$work/refuted"
echo 'Proof, rejection and refutation fixtures passed'
