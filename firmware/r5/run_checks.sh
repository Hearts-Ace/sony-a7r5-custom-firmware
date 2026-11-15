#!/bin/sh
# Host fixtures for the staging source; this command does not build a DAT.
set -eu
cd "$(dirname "$0")"
check_dir=$(mktemp -d "${TMPDIR:-/tmp}/r5-465-checks.XXXXXX")
trap 'rm -rf "$check_dir"' EXIT HUP INT TERM
cc -std=c11 -O1 -g -fsanitize=address,undefined -Wall -Wextra -Werror -pthread \
   -Icp -Icommon cp/generation.c tests/generation.c -o "$check_dir/generation"
cc -std=c11 -O1 -g -fsanitize=address,undefined -Wall -Wextra -Werror \
   -Icp -Icommon cp/generation.c cp/submit.c tests/submit.c -o "$check_dir/submit"
"$check_dir/generation"
"$check_dir/submit"
