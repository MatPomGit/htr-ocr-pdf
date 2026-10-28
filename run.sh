#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/bootstrap.py "$@"
elif command -v python >/dev/null 2>&1; then
  exec python scripts/bootstrap.py "$@"
else
  printf 'Brak interpretera Python 3.10+. Zainstaluj Python i ponów uruchomienie.\n' >&2
  exit 2
fi
