# GRAAL-ATACK Theme Notes

## Palette

- Fond profond : `#050505`, `#080706`, `#0d0b0a`
- Panels : `#11100d`, `#17130f`
- Or ancien / bordures : `#8b6f2d`, `#b9923b`, `#d8b45a`
- Texte principal : `#e7d6a3`
- Texte secondaire : `#9c8c68`
- Violet magique : `#7d35d8`, `#a855f7`
- Succès : `#72e06a`
- Erreur : `#d94b4b`
- Warning : `#d89b35`

## Symboles de fallback

- Graal / couronne : `♕`, `♛`, `🏆`
- Bouclier : `🛡`
- Épées : `⚔`
- Parchemin : `📜`
- Runes / étoiles : `✦`, `✧`, `✠`, `⚜`
- Oeil / oracle : `◉`
- Sceau : `⛨`

## Noms des sections

- Dashboard : **Sanctuaire**
- Dépendances : **Reliques**
- Tools : **Missions**
- Reports : **Archives** / **Archives de Quêtes**
- Settings/Paramètres : **Autel**
- Terminal : **Grimoire d'exécution**
- Logs d'installation : **Journal du Forgeron**

## Arborescence d'illustrations optionnelles

Aucun fichier image n'est requis dans le dépôt. L'application charge automatiquement les images si elles existent et affiche un placeholder Unicode élégant sinon.

```text
assets/
├── backgrounds/
├── logos/
├── gods/
├── icons/
├── banners/
└── portraits/
```

> PNG/GIF fonctionnent via Tk. Les formats JPEG/WebP et le redimensionnement haut de gamme sont activés automatiquement si Pillow est installé dans l'environnement.

## Images recommandées

### 1. Grande salle principale

- **Nom du fichier** : `main_hall.jpg`
- **Emplacement exact** : `assets/backgrounds/main_hall.jpg`
- **Utilisation dans l'interface** : illustration d'ambiance principale pour futurs fonds d'écran/header fullscreen.
- **Prompt recommandé** : `Grand sacred Grail hall, black marble cathedral, ancient gold ornaments, violet mystical light, cyber security temple, dark fantasy AAA game concept art, ultra detailed, cinematic lighting.`
- **Recherche Google Images** : `Grail cathedral dark fantasy black gold violet hall artwork`

### 2. Fond du Sanctuaire

- **Nom du fichier** : `dashboard.jpg`
- **Emplacement exact** : `assets/backgrounds/dashboard.jpg`
- **Utilisation dans l'interface** : fallback de bannière du Sanctuaire si `assets/banners/sanctuary_banner.jpg` est absent.
- **Prompt recommandé** : `Dark temple dashboard, black and ancient gold, violet magical energy, sacred cybersecurity command center, mythological SOC, high-end fantasy OS UI background.`
- **Recherche Google Images** : `dark fantasy temple black gold violet dashboard background`

### 3. Logo du Graal

- **Nom du fichier** : `graal_logo.png`
- **Emplacement exact** : `assets/logos/graal_logo.png`
- **Utilisation dans l'interface** : logo du header, logo de sidebar, icône de fenêtre si disponible.
- **Prompt recommandé** : `Golden holy grail chalice, violet halo, black background, sacred runes, luxury dark fantasy emblem, clean centered icon, transparent background.`
- **Recherche Google Images** : `golden grail violet halo fantasy logo transparent`

### 4. Icône d'application

- **Nom du fichier** : `app.png`
- **Emplacement exact** : `assets/icons/app.png`
- **Utilisation dans l'interface** : icône de fenêtre/desktop alternative si `assets/logos/graal_logo.png` est absent.
- **Prompt recommandé** : `GRAAL-ATTACK app icon, golden shield and grail, violet runes, black background, premium fantasy cyber security icon.`
- **Recherche Google Images** : `fantasy cybersecurity shield grail icon gold violet`

### 5. Bannière du Sanctuaire

- **Nom du fichier** : `sanctuary_banner.jpg`
- **Emplacement exact** : `assets/banners/sanctuary_banner.jpg`
- **Utilisation dans l'interface** : grande bannière du dashboard Sanctuaire.
- **Prompt recommandé** : `Mythological landscape of the Grail quest, sacred temple, knights silhouettes, black gold violet palette, cinematic dark fantasy banner, ultra wide.`
- **Recherche Google Images** : `holy grail quest dark fantasy banner knights temple`

### 6. Runes de header

- **Nom du fichier** : `header_sigils.png`
- **Emplacement exact** : `assets/banners/header_sigils.png`
- **Utilisation dans l'interface** : image secondaire du header si le logo principal est absent.
- **Prompt recommandé** : `Ornamental golden sacred sigils, violet glow, dark transparent background, fantasy cyber runes, horizontal header decoration.`
- **Recherche Google Images** : `gold violet fantasy runes transparent header ornament`

### 7. Odin

- **Nom du fichier** : `odin.png`
- **Emplacement exact** : `assets/gods/odin.png`
- **Utilisation dans l'interface** : carte **Système** du Sanctuaire / figure de connaissance.
- **Prompt recommandé** : `Dark fantasy Odin, black and gold armor, glowing violet eyes, sacred cyber temple, ultra detailed, AAA character portrait.`
- **Recherche Google Images** : `Norse god Odin dark fantasy artwork black gold violet`

### 8. Athéna

- **Nom du fichier** : `athena.png`
- **Emplacement exact** : `assets/gods/athena.png`
- **Utilisation dans l'interface** : portrait de sidebar secondaire / future section OSINT Vision de l'Oracle.
- **Prompt recommandé** : `Athena goddess of wisdom, dark fantasy armor, gold and ivory details, violet cyber oracle aura, sacred temple background, premium game portrait.`
- **Recherche Google Images** : `Athena goddess wisdom dark fantasy armor violet artwork`

### 9. Hadès

- **Nom du fichier** : `hades.png`
- **Emplacement exact** : `assets/gods/hades.png`
- **Utilisation dans l'interface** : carte **Archives de Quêtes**, gardien des archives.
- **Prompt recommandé** : `Hades guardian of forbidden archives, dark fantasy black gold armor, violet underworld flame, sacred library, ultra detailed character art.`
- **Recherche Google Images** : `Hades dark fantasy guardian archives violet flame artwork`

### 10. Arès

- **Nom du fichier** : `ares.png`
- **Emplacement exact** : `assets/gods/ares.png`
- **Utilisation dans l'interface** : carte **Outils Totaux** / section Missions offensives autorisées.
- **Prompt recommandé** : `Ares god of war, black and gold battle armor, violet magical energy, cyber runes, dark fantasy AAA portrait, dramatic lighting.`
- **Recherche Google Images** : `Ares god of war dark fantasy black gold violet armor`

### 11. Gardien du Graal

- **Nom du fichier** : `guardian.png`
- **Emplacement exact** : `assets/portraits/guardian.png`
- **Utilisation dans l'interface** : portrait de sidebar et carte **Dépendances/Reliques**.
- **Prompt recommandé** : `Guardian knight of the Holy Grail, black steel armor with ancient gold engravings, violet sacred glow, cathedral background, ultra detailed fantasy portrait.`
- **Recherche Google Images** : `holy grail guardian knight dark fantasy gold violet portrait`

### 12. Icône Reliques

- **Nom du fichier** : `relics.png`
- **Emplacement exact** : `assets/icons/relics.png`
- **Utilisation dans l'interface** : future icône dédiée pour la page Reliques ou sa carte dashboard.
- **Prompt recommandé** : `Ancient golden reliquary icon, sacred artifact, violet glow, dark transparent background, fantasy UI asset.`
- **Recherche Google Images** : `gold reliquary icon dark fantasy violet transparent`
