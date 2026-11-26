#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 || ! $1 =~ ^[a-f0-9]{40}$ ]]; then
  echo "Usage: $0 <full commit SHA> <empty output directory> <trusted check-site.sh>" >&2
  exit 2
fi
sha=$1
output=$(realpath "$2")
checker=$(realpath "$3")
test -f "$checker"
test -z "$(ls -A -- "$output")"
mirror=$(mktemp -d)
trap 'rmdir "$mirror" 2>/dev/null || rm -r -- "$mirror"' EXIT

export GIT_TERMINAL_PROMPT=0 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
git init --quiet --bare "$mirror"
git -C "$mirror" -c credential.helper= fetch --quiet --no-tags --depth=1 \
  https://github.com/CGandGameEngineLearner/goldbach-proofs.git "$sha"
test "$(git -C "$mirror" rev-parse FETCH_HEAD)" = "$sha"
git -C "$mirror" -c core.autocrlf=false archive --format=tar -o "$output/source.tar" "$sha"
install -m 644 "$checker" "$output/check-site.sh"
