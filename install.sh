#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/graal-atack"
LEGACY_APP_DIR="/opt/azaryx-tools"
BIN_LINK="/usr/local/bin/graal-atack"
LEGACY_BIN_LINK="/usr/local/bin/azaryx-tools"
DESKTOP_FILE="/usr/share/applications/graal-atack.desktop"
LEGACY_DESKTOP_FILE="/usr/share/applications/azaryx-tools.desktop"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  if command -v pkexec >/dev/null 2>&1; then
    exec pkexec "$0" "$@"
  elif command -v sudo >/dev/null 2>&1; then
    exec sudo "$0" "$@"
  else
    echo "Erreur: lancez ce script en root ou installez pkexec/sudo." >&2
    exit 1
  fi
fi

mkdir -p "${APP_DIR}"

if [[ -x "${SOURCE_DIR}/dist/graal-atack" ]]; then
  install -m 0755 "${SOURCE_DIR}/dist/graal-atack" "${APP_DIR}/graal-atack"
else
  install -m 0644 "${SOURCE_DIR}/main.py" "${APP_DIR}/main.py"
  mkdir -p "${APP_DIR}/modules"
  install -m 0644 "${SOURCE_DIR}/modules/__init__.py" "${APP_DIR}/modules/__init__.py"
  install -m 0644 "${SOURCE_DIR}/modules/dependency_manager.py" "${APP_DIR}/modules/dependency_manager.py"
  install -m 0644 "${SOURCE_DIR}/modules/tool_runner.py" "${APP_DIR}/modules/tool_runner.py"
  cat > "${APP_DIR}/graal-atack" <<'EOF'
#!/usr/bin/env bash
cd /opt/graal-atack
exec python3 main.py "$@"
EOF
  chmod 0755 "${APP_DIR}/graal-atack"
fi

if [[ -f "${SOURCE_DIR}/assets/icon.png" ]]; then
  mkdir -p "${APP_DIR}/assets"
  install -m 0644 "${SOURCE_DIR}/assets/icon.png" "${APP_DIR}/assets/icon.png"
  ICON_ENTRY="Icon=${APP_DIR}/assets/icon.png"
else
  ICON_ENTRY="Icon=applications-utilities"
fi
ln -sf "${APP_DIR}/graal-atack" "${BIN_LINK}"
ln -sf "${APP_DIR}/graal-atack" "${LEGACY_BIN_LINK}"
ln -sfn "${APP_DIR}" "${LEGACY_APP_DIR}"

cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=GRAAL-ATACK
Comment=Sanctuaire dark fantasy pour audits autorisés
Exec=${APP_DIR}/graal-atack
${ICON_ENTRY}
Terminal=false
Categories=Security;Utility;
StartupNotify=true
EOF

chmod 0644 "${DESKTOP_FILE}"
cp "${DESKTOP_FILE}" "${LEGACY_DESKTOP_FILE}"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database /usr/share/applications || true
fi

echo "GRAAL-ATACK installé dans ${APP_DIR}. Lancez: graal-atack (compatibilité: azaryx-tools)"
