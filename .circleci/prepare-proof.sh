#!/usr/bin/env bash
# Run on the trusted account before launching the isolated Lean compiler.
set -euo pipefail

pr=${1:?PR number required}
head=${2:?expected PR commit required}
gap=${3:?lemma ID required}
out=${4:?private output directory required}
repo=CGandGameEngineLearner/goldbach-proofs
api="https://api.github.com/repos/$repo"
guard=.github/scripts/outside-guard.mjs

[[ "$pr" =~ ^[1-9][0-9]{0,6}$ && "$head" =~ ^[0-9a-f]{40}$ && "$gap" =~ ^L-[a-z0-9]+(-[a-z0-9]+)*$ ]]
umask 077
mkdir -- "$out"
get() {
    curl --fail --silent --show-error --proto '=https' --max-time 30 --max-filesize "$4" \
        -H "Accept: $3" -o "$2" "$api/$1"
}
get "pulls/$pr" "$out/pr.json" application/vnd.github+json 2097152
jq -e --arg head "$head" '.state == "open" and .head.sha == $head and .changed_files == 1' "$out/pr.json" >/dev/null
get "pulls/$pr/files?per_page=2" "$out/files.json" application/vnd.github+json 2097152
get "git/trees/$head?recursive=1" "$out/tree.json" application/vnd.github+json 20000000
node "$guard" pr "$out/pr.json" "$out/files.json" "$out/tree.json" "$repo" main "$out"
file=$(cat "$out/pr.file")
test ! -e "$file"
test ! -L "$file"
blob=$(cat "$out/pr.blob")
get "git/blobs/$blob" "$out/proof.lean" application/vnd.github.raw+json 524288
test "$(git hash-object "$out/proof.lean")" = "$blob"
jq -s '{gaps: (.[0].gaps + (.[1] | map(.gaps) | add // []))}' research/gaps.json research/problems.json > "$out/gaps.json"
node "$guard" gap "$out/gaps.json" "$gap" "$file" "$out"
node "$guard" imports "$out/proof.lean" "$out/imports.json"
node "$guard" closure "$PWD" "$out/imports.json" "$file" "$out"
# Guard against a PR update between reading the head and its changed-file list.
get "pulls/$pr" "$out/pr-confirm.json" application/vnd.github+json 2097152
jq -e --arg head "$head" '.state == "open" and .head.sha == $head and .changed_files == 1' "$out/pr-confirm.json" >/dev/null
