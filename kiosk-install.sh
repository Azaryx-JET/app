#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUTOSTART_TARGET_USER="${SUDO_USER:-${USER}}"
AUTOSTART_HOME="$(getent passwd "${AUTOSTART_TARGET_USER}" | cut -d: -f6)"

"${SCRIPT_DIR}/install.sh"

if [[ -z "${AUTOSTART_HOME}" || ! -d "${AUTOSTART_HOME}" ]]; then
  echo "Impossible de déterminer le HOME utilisateur pour l'autostart." >&2
  exit 1
fi

run_as_user() {
  if [[ "$(id -un)" == "${AUTOSTART_TARGET_USER}" ]]; then
    HOME="${AUTOSTART_HOME}" "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo -u "${AUTOSTART_TARGET_USER}" HOME="${AUTOSTART_HOME}" "$@"
  elif command -v runuser >/dev/null 2>&1; then
    HOME="${AUTOSTART_HOME}" runuser -u "${AUTOSTART_TARGET_USER}" -- "$@"
  else
    echo "sudo/runuser indisponible: impossible de créer l'autostart utilisateur." >&2
    exit 1
  fi
}

run_as_user "${SCRIPT_DIR}/autostart.sh"

if command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
  echo "Veille écran désactivée pour la session X courante si disponible."
else
  echo "xset indisponible: impossible de désactiver automatiquement la veille écran."
fi

cat <<'EOF'

Mode kiosk installé.
Moyens de sortie conservés dans l'application:
- F11 : activer/désactiver le fullscreen
- Bouton "Quitter fullscreen" dans le menu latéral
- Ctrl+Q : quitter l'application

Retour au mode normal:
1. Désactivez "Démarrer en fullscreen" dans Settings.
2. Supprimez l'autostart utilisateur:
   rm -f ~/.config/autostart/azaryx-tools.desktop
3. Optionnel: réactivez la veille écran dans les paramètres de votre bureau.
EOF
