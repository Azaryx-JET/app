#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
pyinstaller --onefile --windowed --name graal-atack main.py
