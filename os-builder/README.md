# GRAAL-ATTACK OS Builder

Ce dossier contient les éléments nécessaires pour transformer une Debian/Kali minimale en **GRAAL-ATTACK OS** : un environnement graphique léger Openbox/LightDM qui lance automatiquement GRAAL-ATTACK en mode kiosk réversible.

> Usage strictement réservé aux audits autorisés, CTF, labs internes et machines personnelles. Ne déployez pas cette image sur un système ou un réseau sans autorisation explicite.

## Contenu

```text
os-builder/
├── README.md
├── packages.txt
├── postinstall.sh
├── autostart.desktop
├── motd
└── branding/
    └── os-release

Fichiers optionnels non versionnés :
- `../assets/` pour les logos, bannières, dieux, portraits, icônes et polices optionnels ;
- `branding/wallpaper.png` pour un fond d'écran personnalisé.
```

- `packages.txt` liste les paquets système à installer.
- `postinstall.sh` installe les paquets, copie l'application dans `/opt/graal-atack`, crée l'utilisateur `graal`, configure Openbox/LightDM, applique le branding et documente la sortie kiosk.
- `autostart.desktop` lance `/usr/local/bin/graal-atack` après ouverture de session graphique.
- `branding/os-release` remplace `/etc/os-release` après sauvegarde dans `/etc/os-release.graal-backup`.
- `branding/wallpaper.png` est optionnel ; s'il est absent, `postinstall.sh` ignore le fond d'écran et utilise une couleur de fond Openbox si possible.

## Méthode 1 — Installer sur une Debian/Kali existante

Depuis la racine du dépôt :

```bash
sudo ./os-builder/postinstall.sh
```

Le script :

1. installe les paquets listés dans `packages.txt` via `apt-get` ;
2. copie l'application et le dossier `assets/` dans `/opt/graal-atack` ;
3. crée `/usr/local/bin/graal-atack` ;
4. crée l'utilisateur `graal` si absent ;
5. crée l'autostart Openbox et l'autostart desktop ;
6. configure LightDM pour l'autologin de l'utilisateur kiosk ;
7. applique le fond d'écran optionnel si `branding/wallpaper.png` et `feh` sont disponibles, sinon une couleur Openbox ;
8. installe `/etc/motd` ;
9. sauvegarde `/etc/os-release` puis installe le branding GRAAL-ATTACK.

Le kiosk n'est pas verrouillant : **F11** quitte/active le Sanctuaire plein écran, **Ctrl+Q** quitte l'application, et le menu latéral garde un bouton **Quitter le Sanctuaire**.

### Désactiver le kiosk

```bash
sudo rm -f /home/graal/.config/autostart/graal-atack.desktop
sudo rm -f /home/graal/.config/openbox/autostart
sudo rm -f /etc/lightdm/lightdm.conf.d/50-graal-kiosk.conf
sudo sed -i 's/start_fullscreen = true/start_fullscreen = false/' /home/graal/.config/graal-atack/settings.ini
```

Pour restaurer l'identité système d'origine :

```bash
sudo cp /etc/os-release.graal-backup /etc/os-release
```

## Méthode 2 — Créer une ISO avec live-build

Sur une machine de build Debian/Kali :

```bash
sudo apt-get update
sudo apt-get install -y live-build git
mkdir -p graal-live/config/includes.chroot/opt/graal-atack-source
cd graal-live
lb config --distribution bookworm --archive-areas "main contrib non-free non-free-firmware"
```

Copiez ensuite le dépôt GRAAL-ATTACK dans l'image chroot :

```bash
rsync -a /chemin/vers/graal-atack/ config/includes.chroot/opt/graal-atack-source/
mkdir -p config/hooks/live
cat > config/hooks/live/010-graal-postinstall.chroot <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/graal-atack-source
./os-builder/postinstall.sh
EOF
chmod +x config/hooks/live/010-graal-postinstall.chroot
sudo lb build
```

L'ISO générée démarre sur LightDM/Openbox et lance GRAAL-ATTACK via l'autostart configuré par `postinstall.sh`.

## Sécurité

- Usage uniquement légal : audits autorisés, CTF, labs internes et machines personnelles.
- Les outils doivent être utilisés uniquement sur des cibles autorisées.
- Le projet n'installe ni ne lance de payload destructeur.
- Les lanceurs de l'interface sont conçus pour la reconnaissance non destructive.
- Les outils avancés/offensifs peuvent être masqués depuis **Autel**.
- L'autorisation légale avant lancement d'un outil peut rester obligatoire dans **Autel**.
