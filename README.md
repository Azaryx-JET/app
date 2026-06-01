# Azaryx Offensive Tools

Azaryx Offensive Tools est une application graphique Linux qui prépare un poste d'audit en vérifiant automatiquement la présence des outils système nécessaires.

> **Avertissement légal**  
> Ces outils sont destinés uniquement aux audits autorisés, aux CTF, aux labs internes et aux machines personnelles ou explicitement autorisées. Toute utilisation non autorisée est interdite.

## Fonctionnalités

- Vérification automatique des dépendances au lancement.
- Page **Dépendances** avec tableau outil / paquet apt / état / chemin binaire.
- Boutons **Vérifier** et **Installer les dépendances manquantes**.
- Installation avec `apt`/`apt-get` sur Debian, Kali et Ubuntu.
- Élévation via `pkexec` ou `sudo` si l'application n'est pas lancée en root.
- Logs d'installation affichés dans l'interface.
- Nouvelle vérification automatique après l'installation.
- Installation paquet par paquet pour éviter qu'un paquet absent des dépôts bloque toute la procédure.

## Dépendances vérifiées

`nmap`, `whois`, `dig`, `curl`, `whatweb`, `nikto`, `gobuster`, `sqlmap`, `hydra`, `wfuzz`, `enum4linux`, `smbclient`, `netcat`, `tcpdump`, `wireshark`, `traceroute`, `iproute2`, `dnsrecon`, `feroxbuster`, `ffuf`, `amass`, `subfinder`, `nuclei`, `testssl.sh`, `zaproxy` et `openvas / gvm` si disponible.

## Lancement depuis les sources

```bash
python3 main.py
```

## Build PyInstaller

Installez PyInstaller si nécessaire, puis lancez :

```bash
./build.sh
```

Le script exécute la commande demandée :

```bash
pyinstaller --onefile --windowed --name azaryx-tools main.py
```

L'exécutable est généré dans `dist/azaryx-tools`. Même compilée avec PyInstaller, l'application vérifie les outils système au lancement et propose leur installation.

## Installation système

Après un build, installez l'application dans `/opt/azaryx-tools` :

```bash
sudo ./install.sh
```

Le script :

- copie l'exécutable dans `/opt/azaryx-tools` ;
- installe l'icône optionnelle dans `/opt/azaryx-tools/assets/icon.png` si le fichier existe ;
- crée un lien `/usr/local/bin/azaryx-tools` ;
- crée le raccourci `/usr/share/applications/azaryx-tools.desktop`.

Si `dist/azaryx-tools` n'existe pas, `install.sh` installe une version source exécutable avec `python3 main.py`.

## Branding optionnel

Les fichiers binaires de branding ne sont pas obligatoires dans le dépôt. Si `assets/icon.png` est absent, l'application continue sans icône personnalisée et les scripts utilisent une icône système générique. Si `os-builder/branding/wallpaper.png` est absent, l'installation OS/kiosk saute simplement l'installation du fond d'écran.

## Sécurité d'exécution

Le module `modules/dependency_manager.py` n'utilise jamais `shell=True`. Les commandes sont construites sous forme de listes d'arguments, limitées à `apt update` et `apt install -y` pour les paquets explicitement mappés, avec des timeouts et une gestion d'erreurs lisible.

## Onglet Tools

L'onglet **Tools** expose des lanceurs par catégorie : Network, DNS, Web, SMB, Wireless et OSINT. Chaque bouton lance uniquement une commande de reconnaissance non destructive prédéfinie, si le binaire est installé.

- Le champ **Cible globale** est validé avant chaque exécution : domaine, IP, réseau CIDR ou URL HTTP(S) selon l'outil.
- La commande exacte est affichée avant exécution dans la zone terminal.
- Les outils absents sont affichés comme indisponibles et ne sont pas lancés.
- Le timeout est configurable et appliqué à `subprocess.run`.
- Chaque sortie est automatiquement sauvegardée dans le dossier `reports/` configuré.
- Les outils avancés/offensifs visibles dans l'interface peuvent être masqués depuis **Settings**.
- Une confirmation d'autorisation légale peut être exigée avant chaque lancement.

## Onglet Reports

L'onglet **Reports** liste les rapports texte générés automatiquement. Il permet de :

- ouvrir un rapport dans l'interface ;
- supprimer un rapport ;
- exporter une copie vers un emplacement choisi.

## Onglet Settings

L'onglet **Settings** permet de configurer :

- le timeout d'exécution des outils ;
- le dossier de rapports ;
- le mode sombre ;
- l'affichage ou le masquage des outils offensifs avancés ;
- l'autorisation légale obligatoire avant lancement d'un outil.

## Mode OS/Kiosk

Azaryx peut fonctionner comme interface principale d'un poste Linux d'audit sans bloquer l'utilisateur.

- **Dashboard SOC** au démarrage avec cartes : outils installés, rapports générés, dernière cible et statut des dépendances.
- Menu latéral fixe pour naviguer entre Dashboard, Dépendances, Tools, Reports et Settings.
- Fullscreen activable/désactivable avec **F11** ou le bouton du menu latéral.
- Bouton **Quitter fullscreen** toujours visible.
- **Ctrl+Q** quitte l'application.
- **Ctrl+L** ouvre l'onglet Tools et place le focus sur la cible globale.
- L'option **Démarrer en fullscreen** est disponible dans Settings.

### Autostart utilisateur

Pour créer le lanceur utilisateur `~/.config/autostart/azaryx-tools.desktop` :

```bash
./autostart.sh
```

Pour revenir au mode normal :

```bash
rm -f ~/.config/autostart/azaryx-tools.desktop
```

### Installation kiosk

Le script `kiosk-install.sh` installe l'application, crée l'autostart utilisateur et tente de désactiver la veille écran avec `xset` si disponible :

```bash
sudo ./kiosk-install.sh
```

Le mode kiosk reste volontairement réversible : F11, le bouton **Quitter fullscreen** et Ctrl+Q restent disponibles. Pour revenir au mode normal, désactivez **Démarrer en fullscreen** dans Settings puis supprimez le fichier d'autostart.
