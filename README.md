# GRAAL-ATTACK

**GRAAL-ATTACK** est un sanctuaire graphique Linux pour préparer et conduire des quêtes d'audit autorisées. L'interface mêle mythologie du Graal, dark fantasy et supervision cyber : reliques, missions, archives et autel de configuration.

> **Serment légal**
> Ces outils sont destinés uniquement aux audits autorisés, aux CTF, aux labs internes et aux machines personnelles ou explicitement autorisées. Toute utilisation non autorisée est interdite.

## Fonctionnalités

- Vérification automatique des **Reliques** système au lancement.
- Page **Reliques** avec tableau relique / paquet / état / chemin.
- Boutons **Scanner les reliques** et **Forger les reliques manquantes**.
- Installation avec `apt`/`apt-get` sur Debian, Kali et Ubuntu.
- Élévation via `pkexec` ou `sudo` si l'application n'est pas lancée en root.
- **Journal du Forgeron** affiché dans l'interface.
- Onglet **Missions** avec lanceurs non destructifs, cible validée et **Grimoire d'exécution**.
- Onglet **Archives** pour ouvrir, détruire et exporter les parchemins générés.
- Onglet **Autel** pour configurer timeout, dossier des archives, arts avancés, serment légal et mode sanctuaire plein écran.
- Kiosk/fullscreen réversible : **F11**, **Ctrl+Q** et bouton **Quitter le Sanctuaire** restent disponibles.

## Dépendances vérifiées

`nmap`, `whois`, `dig`, `curl`, `whatweb`, `nikto`, `gobuster`, `sqlmap`, `hydra`, `wfuzz`, `enum4linux`, `smbclient`, `netcat`, `tcpdump`, `wireshark`, `traceroute`, `iproute2`, `dnsrecon`, `feroxbuster`, `ffuf`, `amass`, `subfinder`, `nuclei`, `testssl.sh`, `zaproxy` et `openvas / gvm` si disponible.

## Lancement depuis les sources

```bash
python3 main.py
```

La configuration est sauvegardée dans `~/.config/graal-atack/settings.ini`. L'ancien chemin `~/.config/azaryx-tools/settings.ini` reste lu en compatibilité si le nouveau fichier n'existe pas.

## Build PyInstaller

```bash
./build.sh
```

Le script exécute :

```bash
pyinstaller --onefile --windowed --name graal-atack --add-data "assets:assets" main.py
```

L'exécutable est généré dans `dist/graal-atack`.

## Installation système

```bash
sudo ./install.sh
```

Le script :

- copie l'application dans `/opt/graal-atack` ;
- copie le dossier `assets/` complet dans `/opt/graal-atack/assets` pour conserver logos, bannières, dieux, portraits et polices ;
- crée `/usr/local/bin/graal-atack` ;
- conserve la compatibilité `/usr/local/bin/azaryx-tools` ;
- crée le raccourci `/usr/share/applications/graal-atack.desktop` et une copie compatible `azaryx-tools.desktop`.

## Illustrations, polices et branding optionnels

L'application est conçue pour accueillir des illustrations premium dark fantasy si elles sont ajoutées localement ou fournies par votre build. Elle affiche des placeholders Unicode élégants si elles sont absentes et ne plante jamais sur un asset manquant. La refonte typographique scanne aussi `assets/fonts/` pour privilégier Cinzel, Cormorant Garamond, Marcellus SC, Inter ou Roboto, avec fallback automatique vers Segoe UI / Arial.

Arborescence prévue :

```text
assets/
├── backgrounds/
├── logos/
├── gods/
├── icons/
├── banners/
├── portraits/
└── fonts/
```

Exemples automatiquement détectés :

- `assets/logos/graal_logo.png` pour le header, la sidebar et l'icône de fenêtre ;
- `assets/banners/sanctuary_banner.jpg` pour la bannière du Sanctuaire ;
- `assets/backgrounds/dashboard.jpg` comme bannière de secours ;
- `assets/gods/odin.png`, `hades.png`, `ares.png` pour les cartes ;
- `assets/gods/athena.png` et `assets/portraits/guardian.png` pour la sidebar et les cartes.

Pillow (`PIL.Image` et `PIL.ImageTk`) est utilisé par le vrai `AssetManager` pour charger et redimensionner les PNG/JPEG/WebP ; installez `python3-pil` et `python3-pil.imagetk` sur Debian/Kali/Ubuntu. Les emplacements prévus alimentent le header, la sidebar, la bannière du Sanctuaire, les cartes du dashboard, les Reliques, les Missions et les Archives. Voir `assets/theme_notes.md` pour les prompts, usages et recherches Google Images recommandées.

## Onglet Sanctuaire

Le **Sanctuaire** affiche les cartes : **Outils Totaux**, **Dépendances**, **Archives de Quêtes** et **Système**. La bannière rappelle : “Le Graal n’est pas un objet, mais une quête éternelle de vérité et de perfection.”

## Onglet Missions

Les catégories sont renommées : Royaume Réseau, Oracles DNS, Donjons Web, Portes SMB, Ondes Mystiques et Vision de l'Oracle. Les commandes sont affichées sous forme d'incantation :

```text
➤ Incantation exécutée : ...
```

La cible est validée avant exécution. Les commandes restent construites en listes `subprocess` et sans `shell=True`.

## Onglet Archives

Les sorties de mission sont sauvegardées dans le dossier d'archives configuré. L'interface permet d'ouvrir l'archive, de détruire l'archive ou d'exporter le parchemin.

## Mode OS/Kiosk

GRAAL-ATTACK peut fonctionner comme interface principale d'un poste Linux d'audit sans bloquer l'utilisateur.

- Menu latéral fixe avec navigation : 🛡 Sanctuaire, ⚜ Reliques, ⚔ Missions, 📜 Archives, ⚙ Autel.
- **Entrer dans le Sanctuaire** active le fullscreen.
- **Quitter le Sanctuaire**, **F11** et **Ctrl+Q** restent disponibles.
- **Ctrl+L** ouvre les Missions et place le focus sur la cible de quête.

### Autostart utilisateur

```bash
./autostart.sh
```

Pour revenir au mode normal :

```bash
rm -f ~/.config/autostart/graal-atack.desktop
```

### Installation kiosk

```bash
sudo ./kiosk-install.sh
```

Le script installe l'application, crée l'autostart utilisateur et tente de désactiver la veille écran avec `xset` si disponible.

## Sécurité d'exécution

- Usage uniquement légal : audits autorisés, CTF, labs internes et machines personnelles.
- Aucune attaque destructive n'est ajoutée.
- Les lanceurs exposent des commandes de reconnaissance non destructives.
- `subprocess` est utilisé sous forme de listes d'arguments.
- `shell=True` reste interdit.
- Les cibles sont validées.
- Le serment d'autorisation peut rester obligatoire avant lancement d'une mission.
- Les arts avancés peuvent être masqués depuis **Autel**.
