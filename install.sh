#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/azaryx-tools"
BIN_LINK="/usr/local/bin/azaryx-tools"
DESKTOP_FILE="/usr/share/applications/azaryx-tools.desktop"
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

if [[ -x "${SOURCE_DIR}/dist/azaryx-tools" ]]; then
  install -m 0755 "${SOURCE_DIR}/dist/azaryx-tools" "${APP_DIR}/azaryx-tools"
else
  install -m 0644 "${SOURCE_DIR}/main.py" "${APP_DIR}/main.py"
  mkdir -p "${APP_DIR}/modules"
  install -m 0644 "${SOURCE_DIR}/modules/__init__.py" "${APP_DIR}/modules/__init__.py"
  install -m 0644 "${SOURCE_DIR}/modules/dependency_manager.py" "${APP_DIR}/modules/dependency_manager.py"
  install -m 0644 "${SOURCE_DIR}/modules/tool_runner.py" "${APP_DIR}/modules/tool_runner.py"
  cat > "${APP_DIR}/azaryx-tools" <<'EOF'
#!/usr/bin/env bash
cd /opt/azaryx-tools
exec python3 main.py "$@"
EOF
  chmod 0755 "${APP_DIR}/azaryx-tools"
fi

if [[ -f "${SOURCE_DIR}/assets/icon.png" ]]; then
  mkdir -p "${APP_DIR}/assets"
  install -m 0644 "${SOURCE_DIR}/assets/icon.png" "${APP_DIR}/assets/icon.png"
  ICON_ENTRY="Icon=${APP_DIR}/assets/icon.png"
else
  ICON_ENTRY="Icon=applications-utilities"
fi
ln -sf "${APP_DIR}/azaryx-tools" "${BIN_LINK}"

cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=Azaryx Offensive Tools
Comment=Gestionnaire graphique de dépendances pour audits autorisés
Exec=${APP_DIR}/azaryx-tools
${ICON_ENTRY}
Terminal=false
Categories=Security;Utility;
StartupNotify=true
EOF

chmod 0644 "${DESKTOP_FILE}"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database /usr/share/applications || true
fi

echo "Azaryx Offensive Tools installé dans ${APP_DIR}. Lancez: azaryx-tools"
