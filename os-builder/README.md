# Azaryx Offensive Tools OS Builder

Ce dossier contient les éléments nécessaires pour transformer une Debian/Kali minimale en **Azaryx Offensive Tools OS** : un environnement graphique léger Openbox/LightDM qui lance automatiquement Azaryx Offensive Tools en mode kiosk réversible.

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
- `../assets/icon.png` pour une icône applicative personnalisée ;
- `branding/wallpaper.png` pour un fond d'écran personnalisé.
```

- `packages.txt` liste les paquets système à installer.
- `postinstall.sh` installe les paquets, copie l'application dans `/opt/azaryx-tools`, crée l'utilisateur `azaryx`, configure Openbox/LightDM, applique le branding et documente la sortie kiosk.
- `autostart.desktop` lance `/usr/local/bin/azaryx-tools` après ouverture de session graphique.
- `branding/os-release` remplace `/etc/os-release` après sauvegarde dans `/etc/os-release.azaryx-backup`.
- `branding/wallpaper.png` est optionnel ; s'il est absent, `postinstall.sh` ignore le fond d'écran et utilise une couleur de fond Openbox si possible.

## Méthode 1 — Installer sur une Debian/Kali existante

Depuis la racine du dépôt :

```bash
sudo ./os-builder/postinstall.sh
```

Le script :

1. installe les paquets listés dans `packages.txt` via `apt-get` ;
2. copie l'application dans `/opt/azaryx-tools` ;
3. crée `/usr/local/bin/azaryx-tools` ;
4. crée l'utilisateur `azaryx` si absent ;
5. crée l'autostart Openbox et l'autostart desktop ;
6. configure LightDM pour l'autologin de l'utilisateur kiosk ;
7. applique le fond d'écran optionnel si `branding/wallpaper.png` et `feh` sont disponibles, sinon une couleur Openbox ;
8. installe `/etc/motd` ;
9. sauvegarde `/etc/os-release` puis installe le branding Azaryx.

Le kiosk n'est pas verrouillant : **F11** désactive le fullscreen, **Ctrl+Q** quitte l'application, et le menu latéral garde un bouton **Quitter fullscreen**.

### Désactiver le kiosk

```bash
sudo rm -f /home/azaryx/.config/autostart/azaryx-tools.desktop
sudo rm -f /home/azaryx/.config/openbox/autostart
sudo rm -f /etc/lightdm/lightdm.conf.d/50-azaryx-kiosk.conf
sudo sed -i 's/start_fullscreen = true/start_fullscreen = false/' /home/azaryx/.config/azaryx-tools/settings.ini
```

Pour restaurer l'identité système d'origine :

```bash
sudo cp /etc/os-release.azaryx-backup /etc/os-release
```

## Méthode 2 — Créer une ISO avec live-build

Sur une machine de build Debian/Kali :

```bash
sudo apt-get update
sudo apt-get install -y live-build git
mkdir -p azaryx-live/config/includes.chroot/opt/azaryx-source
cd azaryx-live
lb config --distribution bookworm --archive-areas "main contrib non-free non-free-firmware"
```

Copiez ensuite le dépôt Azaryx dans l'image chroot :

```bash
rsync -a /chemin/vers/azaryx/ config/includes.chroot/opt/azaryx-source/
mkdir -p config/hooks/live
cat > config/hooks/live/010-azaryx-postinstall.chroot <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/azaryx-source
./os-builder/postinstall.sh
EOF
chmod +x config/hooks/live/010-azaryx-postinstall.chroot
sudo lb build
```

L'ISO générée démarre sur LightDM/Openbox et lance Azaryx Offensive Tools via l'autostart configuré par `postinstall.sh`.

## Sécurité

- Usage uniquement légal : audits autorisés, CTF, labs internes et machines personnelles.
- Les outils doivent être utilisés uniquement sur des cibles autorisées.
- Le projet n'installe ni ne lance de payload destructeur.
- Les lanceurs de l'interface sont conçus pour la reconnaissance non destructive.
- Les outils avancés/offensifs peuvent être masqués depuis **Settings**.
- L'autorisation légale avant lancement d'un outil peut rester obligatoire dans **Settings**.
