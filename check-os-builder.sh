#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)/os-builder"
REQUIRED_FILES=(
  "README.md"
  "packages.txt"
  "postinstall.sh"
  "autostart.desktop"
  "motd"
  "branding/os-release"
)

for file in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "${BASE_DIR}/${file}" ]]; then
    echo "Fichier manquant: os-builder/${file}" >&2
    exit 1
  fi
done

if [[ ! -s "${BASE_DIR}/packages.txt" ]]; then
  echo "packages.txt est vide." >&2
  exit 1
fi

bash -n "${BASE_DIR}/postinstall.sh"
echo "os-builder OK"
