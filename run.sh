#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || { echo "Сначала выполните ./install.sh"; exit 1; }
source .venv/bin/activate
python -m analyzer --config config.yaml "$@"
