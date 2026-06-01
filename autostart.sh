#!/usr/bin/env bash
set -euo pipefail

AUTOSTART_DIR="${HOME}/.config/autostart"
DESKTOP_FILE="${AUTOSTART_DIR}/graal-atack.desktop"
APP_EXEC="${GRAAL_EXEC:-${AZARYX_EXEC:-/opt/graal-atack/graal-atack}}"
APP_ICON="${GRAAL_ICON:-${AZARYX_ICON:-applications-utilities}}"

mkdir -p "${AUTOSTART_DIR}"
cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=GRAAL-ATACK
Comment=Autostart GRAAL-ATACK in sanctuaire mode
Exec=${APP_EXEC}
Icon=${APP_ICON}
Terminal=false
X-GNOME-Autostart-enabled=true
StartupNotify=true
EOF
chmod 0644 "${DESKTOP_FILE}"
echo "Autostart créé: ${DESKTOP_FILE}"
echo "Pour revenir au mode normal: rm -f ${DESKTOP_FILE}"
