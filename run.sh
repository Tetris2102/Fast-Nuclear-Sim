#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${HOME}/openmc/openmc:${HOME}/openmc:${PYTHONPATH:-}"
exec "${HOME}/miniconda3/bin/python3" "${ROOT}/simulate.py" "$@"
