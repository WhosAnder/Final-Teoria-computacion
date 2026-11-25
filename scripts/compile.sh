#!/usr/bin/env sh
# Usage: scripts/compile.sh input.src -o out.tac
exec python3 "$(dirname "$0")/compile.py" "$@"
