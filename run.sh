#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
stamp="$(sha256sum requirements.txt | cut -d' ' -f1)"
if [[ ! -f .venv/.requirements_sha256 ]] || [[ "$(cat .venv/.requirements_sha256)" != "$stamp" ]]; then
  .venv/bin/python -m pip install -r requirements.txt
  printf '%s' "$stamp" > .venv/.requirements_sha256
fi
exec .venv/bin/python htr_compare.py "$@"
