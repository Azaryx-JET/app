#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="/opt/azaryx-tools"
APP_BIN="/usr/local/bin/azaryx-tools"
KIOSK_USER="${AZARYX_KIOSK_USER:-azaryx}"
PACKAGES_FILE="${SCRIPT_DIR}/packages.txt"
AUTOSTART_SOURCE="${SCRIPT_DIR}/autostart.desktop"
WALLPAPER_SOURCE="${SCRIPT_DIR}/branding/wallpaper.png"
OS_RELEASE_SOURCE="${SCRIPT_DIR}/branding/os-release"
MOTD_SOURCE="${SCRIPT_DIR}/motd"

echo "== Azaryx Offensive Tools OS postinstall =="

if [[ "${EUID}" -ne 0 ]]; then
  echo "Erreur: lancez ce script en root (sudo ./os-builder/postinstall.sh)." >&2
  exit 1
fi

if [[ ! -s "${PACKAGES_FILE}" ]]; then
  echo "Erreur: ${PACKAGES_FILE} est vide ou introuvable." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
while IFS= read -r package; do
  [[ -z "${package}" || "${package}" =~ ^# ]] && continue
  if apt-get install -y --no-install-recommends "${package}"; then
    echo "OK: paquet installé ou déjà présent: ${package}"
  else
    echo "AVERTISSEMENT: impossible d'installer ${package}; poursuite de l'installation." >&2
  fi
done < "${PACKAGES_FILE}"

mkdir -p "${APP_DIR}/modules" "${APP_DIR}/assets" "${APP_DIR}/reports"
install -m 0644 "${REPO_DIR}/main.py" "${APP_DIR}/main.py"
install -m 0644 "${REPO_DIR}/modules/__init__.py" "${APP_DIR}/modules/__init__.py"
install -m 0644 "${REPO_DIR}/modules/dependency_manager.py" "${APP_DIR}/modules/dependency_manager.py"
install -m 0644 "${REPO_DIR}/modules/tool_runner.py" "${APP_DIR}/modules/tool_runner.py"
if [[ -f "${REPO_DIR}/assets/icon.png" ]]; then
  install -m 0644 "${REPO_DIR}/assets/icon.png" "${APP_DIR}/assets/icon.png"
else
  echo "Icône optionnelle absente: poursuite sans assets/icon.png."
fi
if [[ -f "${WALLPAPER_SOURCE}" ]]; then
  install -m 0644 "${WALLPAPER_SOURCE}" "${APP_DIR}/assets/wallpaper.png"
else
  echo "Wallpaper optionnel absent: aucun fond d'écran ne sera installé."
fi

cat > "${APP_DIR}/azaryx-tools" <<'EOF'
#!/usr/bin/env bash
cd /opt/azaryx-tools
exec python3 main.py "$@"
EOF
chmod 0755 "${APP_DIR}/azaryx-tools"
ln -sf "${APP_DIR}/azaryx-tools" "${APP_BIN}"

if ! id "${KIOSK_USER}" >/dev/null 2>&1; then
  EXTRA_GROUPS=()
  for group in audio video netdev; do
    if getent group "${group}" >/dev/null 2>&1; then
      EXTRA_GROUPS+=("${group}")
    fi
  done
  if [[ "${#EXTRA_GROUPS[@]}" -gt 0 ]]; then
    GROUPS_CSV="$(IFS=,; echo "${EXTRA_GROUPS[*]}")"
    useradd --create-home --shell /bin/bash --groups "${GROUPS_CSV}" "${KIOSK_USER}"
  else
    useradd --create-home --shell /bin/bash "${KIOSK_USER}"
  fi
  echo "Utilisateur ${KIOSK_USER} créé. Définissez un mot de passe si nécessaire: passwd ${KIOSK_USER}"
fi
KIOSK_HOME="$(getent passwd "${KIOSK_USER}" | cut -d: -f6)"

mkdir -p "${KIOSK_HOME}/.config/autostart" "${KIOSK_HOME}/.config/openbox" "${KIOSK_HOME}/.config/azaryx-tools"
install -m 0644 "${AUTOSTART_SOURCE}" "${KIOSK_HOME}/.config/autostart/azaryx-tools.desktop"
cat > "${KIOSK_HOME}/.config/openbox/autostart" <<'EOF'
# Azaryx Offensive Tools OS autostart. Remove this file to disable kiosk autostart.
xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
xset s noblank 2>/dev/null || true
if command -v feh >/dev/null 2>&1 && [[ -f /opt/azaryx-tools/assets/wallpaper.png ]]; then
  feh --bg-scale /opt/azaryx-tools/assets/wallpaper.png || true
elif command -v xsetroot >/dev/null 2>&1; then
  xsetroot -solid '#101827' || true
fi
/usr/local/bin/azaryx-tools &
EOF
chmod 0755 "${KIOSK_HOME}/.config/openbox/autostart"
cat > "${KIOSK_HOME}/.config/azaryx-tools/settings.ini" <<EOF
[legal]
notice_seen = false

[settings]
timeout = 120
reports_dir = ${APP_DIR}/reports
dark_mode = true
show_advanced = false
require_legal_authorization = true
start_fullscreen = true
last_target =
EOF
chown -R "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_HOME}/.config"
chown -R "${KIOSK_USER}:${KIOSK_USER}" "${APP_DIR}/reports"

if [[ -d /etc/lightdm ]]; then
  mkdir -p /etc/lightdm/lightdm.conf.d
  cat > /etc/lightdm/lightdm.conf.d/50-azaryx-kiosk.conf <<EOF
[Seat:*]
autologin-user=${KIOSK_USER}
autologin-user-timeout=0
user-session=openbox
EOF
fi

if [[ -f "${MOTD_SOURCE}" ]]; then
  install -m 0644 "${MOTD_SOURCE}" /etc/motd
fi

if [[ -f /etc/os-release && ! -f /etc/os-release.azaryx-backup ]]; then
  cp /etc/os-release /etc/os-release.azaryx-backup
fi
install -m 0644 "${OS_RELEASE_SOURCE}" /etc/os-release

if command -v update-alternatives >/dev/null 2>&1 && command -v openbox-session >/dev/null 2>&1; then
  update-alternatives --set x-session-manager "$(command -v openbox-session)" >/dev/null 2>&1 || true
fi

cat <<EOF

Azaryx Offensive Tools OS est installé.
L'utilisateur kiosk est: ${KIOSK_USER}
L'application démarre via Openbox/autostart et peut démarrer en fullscreen.

Le kiosk reste réversible et ne bloque pas l'utilisateur:
- F11 : activer/désactiver le fullscreen
- Ctrl+Q : quitter Azaryx Offensive Tools
- Bouton "Quitter fullscreen" dans le menu latéral

Pour désactiver le kiosk/autostart:
  sudo rm -f ${KIOSK_HOME}/.config/autostart/azaryx-tools.desktop
  sudo rm -f ${KIOSK_HOME}/.config/openbox/autostart
  sudo rm -f /etc/lightdm/lightdm.conf.d/50-azaryx-kiosk.conf
  sudo sed -i 's/start_fullscreen = true/start_fullscreen = false/' ${KIOSK_HOME}/.config/azaryx-tools/settings.ini

Pour restaurer /etc/os-release si besoin:
  sudo cp /etc/os-release.azaryx-backup /etc/os-release
EOF
