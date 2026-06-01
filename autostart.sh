#!/usr/bin/env bash
set -euo pipefail

AUTOSTART_DIR="${HOME}/.config/autostart"
DESKTOP_FILE="${AUTOSTART_DIR}/azaryx-tools.desktop"
APP_EXEC="${AZARYX_EXEC:-/opt/azaryx-tools/azaryx-tools}"
APP_ICON="${AZARYX_ICON:-applications-utilities}"

mkdir -p "${AUTOSTART_DIR}"
cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=Azaryx Offensive Tools
Comment=Autostart Azaryx Offensive Tools in kiosk-ready mode
Exec=${APP_EXEC}
Icon=${APP_ICON}
Terminal=false
X-GNOME-Autostart-enabled=true
StartupNotify=true
EOF
chmod 0644 "${DESKTOP_FILE}"
echo "Autostart créé: ${DESKTOP_FILE}"
echo "Pour revenir au mode normal: rm -f ${DESKTOP_FILE}"
