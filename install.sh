#!/usr/bin/env bash
set -e
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
echo "Установка завершена. Укажите сайт в config.yaml и запустите ./run.sh"
