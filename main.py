from __future__ import annotations

import configparser
from datetime import datetime
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import Protocol

import PIL.Image
import PIL.ImageTk

from modules.dependency_manager import (
    detect_package_manager,
    get_missing_tools,
    get_tool_statuses,
    install_missing_tools,
)
from modules.tool_runner import (
    CATEGORIES,
    TOOL_DEFINITIONS,
    ToolDefinition,
    ToolExecutionError,
    ensure_reports_dir,
    format_command,
    run_command,
    validate_timeout,
)

APP_NAME = "GRAAL-ATTACK"
BRAND_TITLE = "GRAAL-ATTACK"
APP_VERSION = "v0.1"
LEGACY_CONFIG_DIR = Path.home() / ".config" / "azaryx-tools"
CONFIG_DIR = Path.home() / ".config" / "graal-atack"
CONFIG_FILE = CONFIG_DIR / "settings.ini"
LEGACY_CONFIG_FILE = LEGACY_CONFIG_DIR / "settings.ini"
DEFAULT_REPORTS_DIR = Path.cwd() / "reports"
LEGAL_WARNING = (
    "GRAAL-ATTACK rassemble des reliques d'audit destinées uniquement aux quêtes "
    "autorisées : CTF, laboratoires internes, audits validés et machines "
    "personnelles. Toute incantation non autorisée est interdite."
)
SUBTITLE = "La quête de la connaissance. La puissance de la sécurité."
QUOTE = "Par la lumière du Graal, la vérité se révèle dans chaque ligne de code."

THEME = {
    "bg": "#0a0a0a",
    "bg_alt": "#050505",
    "panel": "#141414",
    "panel_alt": "#17130f",
    "gold_dark": "#8b6f2d",
    "gold": "#d4af37",
    "gold_light": "#f4d03f",
    "text": "#f5f5f5",
    "muted": "#c3b58a",
    "violet": "#5a2ea6",
    "violet_light": "#a855f7",
    "success": "#72e06a",
    "error": "#d94b4b",
    "warning": "#d89b35",
}
TITLE_FONT = ("Cinzel", "Cormorant Garamond", "Marcellus SC", "Trajan Pro", "Georgia", "Segoe UI", "Arial")
BODY_FONT = ("Inter", "Roboto", "Segoe UI", "Arial", "Georgia")

ASSET_LOGO = "logos/graal_logo.png"
ASSET_GUARDIAN = "portraits/guardian.png"
ASSET_ODIN = "gods/odin.png"
ASSET_ARES = "gods/ares.png"
ASSET_ATHENA = "gods/athena.png"
ASSET_HADES = "gods/hades.png"
ASSET_SANCTUARY_BANNER = "banners/sanctuary_banner.jpg"
ASSET_DASHBOARD_BACKGROUND = "backgrounds/dashboard.jpg"


CATEGORY_LABELS = {
    "Network": "Royaume Réseau",
    "DNS": "Oracles DNS",
    "Web": "Donjons Web",
    "SMB": "Portes SMB",
    "Wireless": "Ondes Mystiques",
    "OSINT": "Vision de l’Oracle",
}
class AssetLogger(Protocol):
    def __call__(self, message: str) -> None:
        ...


TOOL_LABELS = {
    "nmap_safe": "✦ Nmap — Cartographier le royaume",
    "traceroute": "✧ Traceroute — Suivre la route sacrée",
    "ip_addr": "⛨ IP — Inspecter les sceaux locaux",
    "dig": "⚜ Dig — Interroger l’oracle",
    "dnsrecon": "✦ DNSRecon — Lire les constellations DNS",
    "whois": "📜 Whois — Lire les archives",
    "amass": "◉ Amass — Vision passive du royaume",
    "subfinder": "◉ Subfinder — Révéler les noms cachés",
    "curl_headers": "◉ Curl — Lire les entêtes du parchemin",
    "whatweb": "◉ WhatWeb — Identifier les runes web",
    "testssl": "⛨ testssl.sh — Éprouver le sceau TLS",
    "nikto": "🛡 Nikto — Examiner le donjon",
    "nuclei": "✦ Nuclei — Détecter les glyphes faibles",
    "smbclient_list": "⚜ SMB — Ouvrir les portes visibles",
    "enum4linux": "📜 Enum4linux — Lire le grimoire SMB",
    "tcpdump_list": "◉ Tcpdump — Observer les ondes",
    "wireshark": "♛ Wireshark — Oeil du chevalier",
}


class AssetManager:
    """Real image loader for premium GRAAL-ATTACK artwork.

    The manager uses Pillow for every supported image format, resizes images to
    the requested slot, keeps PhotoImage references in a cache, and never raises
    on missing/corrupt assets. Every lookup emits [FOUND], [LOADED], [MISSING]
    or [ERROR] logs so packaging issues are visible immediately.
    """

    def __init__(self, base_dir: Path, logger: AssetLogger | None = None) -> None:
        self.base_dir = base_dir
        self.logger = logger
        self.events: list[str] = []
        self._cache: dict[tuple[str, tuple[int, int] | None], PIL.ImageTk.PhotoImage] = {}

    def _log(self, level: str, message: str) -> None:
        event = f"[{level}] {message}"
        self.events.append(event)
        print(event)
        if self.logger is not None:
            self.logger(event)

    def _candidate(self, relative_paths: tuple[str, ...]) -> Path | None:
        for relative_path in relative_paths:
            path = self.base_dir / relative_path
            if path.exists() and path.is_file():
                self._log("FOUND", f"{relative_path} -> {path}")
                return path
        self._log("MISSING", " | ".join(relative_paths))
        return None

    def load(self, *relative_paths: str, size: tuple[int, int] | None = None) -> PIL.ImageTk.PhotoImage | None:
        path = self._candidate(tuple(relative_paths))
        if path is None:
            return None
        key = (str(path), size)
        if key in self._cache:
            self._log("LOADED", f"cache {path.name} size={size or 'original'}")
            return self._cache[key]

        try:
            with PIL.Image.open(path) as opened:
                image = opened.convert("RGBA")
                if size is not None:
                    image.thumbnail(size, PIL.Image.LANCZOS)
                photo = PIL.ImageTk.PhotoImage(image)
        except (OSError, tk.TclError, ValueError) as exc:
            self._log("ERROR", f"{path}: {exc}")
            return None

        self._cache[key] = photo
        self._log("LOADED", f"{path.name} size={photo.width()}x{photo.height()}")
        return photo

    def label(
        self,
        parent: tk.Misc,
        *relative_paths: str,
        size: tuple[int, int] | None = None,
        placeholder: str = "✦",
        style: str = "ImagePlaceholder.TLabel",
        **kwargs: object,
    ) -> ttk.Label:
        photo = self.load(*relative_paths, size=size)
        if photo is None:
            return ttk.Label(parent, text=placeholder, style=style, **kwargs)
        label = ttk.Label(parent, image=photo, style=style, **kwargs)
        label.image = photo
        return label

class FontManager:
    """Centralized typography resolver for the premium GRAAL-ATTACK theme.

    Tk does not reliably expose a cross-platform API for loading raw TTF/OTF
    files at runtime, so this manager scans ``assets/fonts`` and prefers
    matching installed families while always falling back to common UI fonts.
    """

    TITLE_CANDIDATES = ("Cinzel", "Cormorant Garamond", "Marcellus SC", "Georgia", "Segoe UI", "Arial")
    BODY_CANDIDATES = ("Inter", "Roboto", "Segoe UI", "Arial", "Georgia")

    def __init__(self, root: tk.Misc, fonts_dir: Path) -> None:
        self.fonts_dir = fonts_dir
        self.asset_families = self._discover_asset_font_names()
        try:
            installed = {family.lower(): family for family in tkfont.families(root)}
        except tk.TclError:
            installed = {}
        self.installed_families = installed
        self.title_family = self._resolve_family(self.TITLE_CANDIDATES)
        self.body_family = self._resolve_family(self.BODY_CANDIDATES)

    @staticmethod
    def _font_key(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def _discover_asset_font_names(self) -> set[str]:
        names: set[str] = set()
        for path in self.fonts_dir.glob("*"):
            if path.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
                continue
            stem = path.stem.replace("-", " ").replace("_", " ")
            first_token = stem.split()[0]
            names.add(self._font_key(stem))
            names.add(self._font_key(first_token))
        return names

    def _resolve_family(self, candidates: tuple[str, ...]) -> str:
        for candidate in candidates:
            if candidate.lower() in self.installed_families:
                return self.installed_families[candidate.lower()]
        for candidate in candidates:
            if self._font_key(candidate) in self.asset_families:
                return candidate
        return "Segoe UI" if "segoe ui" in self.installed_families else "Arial"

    def title(self, size: int, weight: str = "bold") -> tuple[str, int, str]:
        return (self.title_family, size, weight)

    def body(self, size: int, weight: str = "normal") -> tuple[str, int, str]:
        return (self.body_family, size, weight)


class RoundedPanel(tk.Frame):
    """Canvas-backed panel with rounded corners, gold border and subtle glow."""

    def __init__(
        self,
        parent: tk.Misc,
        padding: int = 18,
        bg: str | None = None,
        radius: int = 22,
        border: str | None = None,
        glow: str | None = None,
    ) -> None:
        super().__init__(parent, bg=THEME["bg"], highlightthickness=0, bd=0)
        self.panel_bg = bg or THEME["panel_alt"]
        self.radius = radius
        self.border = border or THEME["gold"]
        self.glow = glow or THEME["violet"]
        self.padding = padding
        self.canvas = tk.Canvas(self, bg=THEME["bg"], bd=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=self.panel_bg, bd=0)
        self.inner_window = self.canvas.create_window(
            padding,
            padding,
            window=self.inner,
            anchor="nw",
        )
        self.canvas.bind("<Configure>", self._redraw)
        self.inner.bind("<Configure>", self._sync_requested_size)

    def _sync_requested_size(self, event: tk.Event) -> None:
        requested_width = int(event.width) + (self.padding * 2) + 18
        requested_height = int(event.height) + (self.padding * 2) + 18
        self.canvas.configure(width=requested_width, height=requested_height)

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: object) -> int:
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=18, **kwargs)

    def _redraw(self, event: tk.Event) -> None:
        width = max(int(event.width), 8)
        height = max(int(event.height), 8)
        self.canvas.delete("panel")
        self._rounded_rect(5, 6, width - 1, height - 1, self.radius, fill="#050505", outline="", tags="panel")
        self._rounded_rect(1, 1, width - 5, height - 5, self.radius, fill=self.glow, outline="", tags="panel")
        self._rounded_rect(2, 2, width - 7, height - 7, self.radius, fill=self.border, outline="", tags="panel")
        self._rounded_rect(4, 4, width - 9, height - 9, max(self.radius - 2, 8), fill=self.panel_bg, outline="", tags="panel")
        inner_width = max(width - (self.padding * 2) - 14, 1)
        inner_height = max(height - (self.padding * 2) - 14, 1)
        self.canvas.coords(self.inner_window, self.padding + 3, self.padding + 3)
        self.canvas.itemconfigure(self.inner_window, width=inner_width, height=inner_height)
        self.canvas.tag_lower("panel")


def premium_panel(parent: tk.Misc, padding: int = 22, bg: str | None = None) -> tuple[RoundedPanel, tk.Frame]:
    """Return a rounded gold/glow panel and its content frame."""

    outer = RoundedPanel(parent, padding=padding, bg=bg or THEME["panel_alt"])
    return outer, outer.inner


def tk_label(parent: tk.Misc, text: str, size: int = 12, color: str | None = None, bg: str | None = None, bold: bool = False) -> tk.Label:
    weight = "bold" if bold else "normal"
    return tk.Label(
        parent,
        text=text,
        bg=bg or THEME["panel_alt"],
        fg=color or THEME["text"],
        font=(TITLE_FONT[0] if bold else BODY_FONT[0], size, weight),
        justify="left",
    )


def image_or_placeholder(
    assets: AssetManager,
    parent: tk.Misc,
    paths: tuple[str, ...],
    size: tuple[int, int],
    placeholder: str,
    bg: str | None = None,
) -> tk.Label:
    photo = assets.load(*paths, size=size)
    if photo is not None:
        label = tk.Label(parent, image=photo, bg=bg or THEME["panel_alt"], bd=0)
        label.image = photo
        return label
    return tk.Label(
        parent,
        text=placeholder,
        bg=bg or THEME["panel_alt"],
        fg=THEME["gold_light"],
        font=(TITLE_FONT[0], max(min(size[1] // 2, 54), 24), "bold"),
        justify="center",
        wraplength=size[0],
    )


def assets_root() -> Path:
    """Return the asset directory in source or PyInstaller onefile mode."""

    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets"


def load_settings() -> dict[str, object]:
    config = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        config.read(CONFIG_FILE)
    elif LEGACY_CONFIG_FILE.exists():
        config.read(LEGACY_CONFIG_FILE)
    return {
        "legal_notice_seen": config.getboolean("legal", "notice_seen", fallback=False),
        "timeout": config.getint("settings", "timeout", fallback=120),
        "reports_dir": config.get("settings", "reports_dir", fallback=str(DEFAULT_REPORTS_DIR)),
        "dark_mode": config.getboolean("settings", "dark_mode", fallback=True),
        "show_advanced": config.getboolean("settings", "show_advanced", fallback=False),
        "require_legal_authorization": config.getboolean(
            "settings", "require_legal_authorization", fallback=True
        ),
        "start_fullscreen": config.getboolean("settings", "start_fullscreen", fallback=False),
        "last_target": config.get("settings", "last_target", fallback=""),
    }


def save_settings(settings: dict[str, object]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser()
    config["legal"] = {"notice_seen": str(bool(settings["legal_notice_seen"])).lower()}
    config["settings"] = {
        "timeout": str(int(settings["timeout"])),
        "reports_dir": str(settings["reports_dir"]),
        "dark_mode": str(bool(settings["dark_mode"])).lower(),
        "show_advanced": str(bool(settings["show_advanced"])).lower(),
        "require_legal_authorization": str(bool(settings["require_legal_authorization"])).lower(),
        "start_fullscreen": str(bool(settings["start_fullscreen"])).lower(),
        "last_target": str(settings.get("last_target", "")),
    }
    with CONFIG_FILE.open("w", encoding="utf-8") as config_file:
        config.write(config_file)


class DependencyPage(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=12, style="Page.TFrame")
        self.log_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.assets = AssetManager(assets_root())
        self.is_busy = False
        self._build_widgets()
        self.after(100, self._drain_logs)
        self.check_dependencies(background=True)

    def _build_widgets(self) -> None:
        hero_outer, hero = premium_panel(self, padding=16, bg=THEME["panel_alt"])
        hero_outer.pack(fill="x", pady=(0, 16))
        hero.columnconfigure(1, weight=1)
        image_or_placeholder(
            self.assets,
            hero,
            (ASSET_ATHENA,),
            (170, 210),
            "⚜",
            bg=THEME["panel_alt"],
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 18))
        tk_label(hero, "ATHÉNA — Analyse et Connaissance", 24, THEME["gold_light"], THEME["panel_alt"], True).grid(row=0, column=1, sticky="w")
        tk_label(
            hero,
            "Les reliques nécessaires à la quête sont vérifiées avant chaque mission. La forge utilise apt sur Debian, Kali ou Ubuntu.",
            14,
            THEME["muted"],
            THEME["panel_alt"],
        ).grid(row=1, column=1, sticky="w", pady=(8, 0))

        columns = ("tool", "package", "installed", "path")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=12)
        self.tree.heading("tool", text="Relique")
        self.tree.heading("package", text="Paquet")
        self.tree.heading("installed", text="État")
        self.tree.heading("path", text="Chemin")
        self.tree.column("tool", width=180, anchor="w")
        self.tree.column("package", width=160, anchor="w")
        self.tree.column("installed", width=90, anchor="center")
        self.tree.column("path", width=480, anchor="w")
        self.tree.pack(fill="both", expand=True)

        button_bar = ttk.Frame(self)
        button_bar.pack(fill="x", pady=8)
        self.check_button = ttk.Button(button_bar, text="Scanner les reliques", command=self.check_dependencies)
        self.check_button.pack(side="left")
        self.install_button = ttk.Button(
            button_bar,
            text="Forger les reliques manquantes",
            command=self.install_dependencies,
        )
        self.install_button.pack(side="left", padx=8)
        self.status_label = ttk.Label(button_bar, text="Statut : EN VEILLE")
        self.status_label.pack(side="left", padx=12)

        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 8))

        ttk.Label(self, text="Journal du Forgeron", style="Section.TLabel").pack(anchor="w")
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=10, wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _set_busy(self, busy: bool, status: str) -> None:
        self.is_busy = busy
        self.check_button.configure(state="disabled" if busy else "normal")
        self.install_button.configure(state="disabled" if busy else "normal")
        self.status_label.configure(text=status)
        if busy:
            self.progress.configure(mode="indeterminate")
            self.progress.start(10)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate")

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _drain_logs(self) -> None:
        while True:
            try:
                kind, value = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "log" and value is not None:
                self._append_log(value)
            elif kind == "status" and value is not None:
                self.status_label.configure(text=value)
            elif kind == "refresh":
                self._populate_table()
            elif kind == "busy":
                self._set_busy(value == "true", self.status_label.cget("text"))
        self.after(100, self._drain_logs)

    def _populate_table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        statuses = get_tool_statuses()
        missing_count = 0
        for status in statuses:
            installed = bool(status["installed"])
            if not installed:
                missing_count += 1
            self.tree.insert(
                "",
                "end",
                values=(
                    status["tool"],
                    status["package"],
                    "Présente" if installed else "Manquante",
                    status["path"] or "-",
                ),
            )
        if missing_count:
            self.status_label.configure(text=f"{missing_count} relique(s) manquante(s)")
            self.progress.configure(value=max(0, 100 - missing_count * 4))
        else:
            self.status_label.configure(text="Toutes les reliques sont présentes")
            self.progress.configure(value=100)

    def check_dependencies(self, background: bool = False) -> None:
        if self.is_busy:
            return

        def task() -> None:
            self.log_queue.put(("busy", "true"))
            self.log_queue.put(("status", "Lecture des reliques en cours..."))
            package_manager = detect_package_manager()
            if package_manager != "apt":
                self.log_queue.put(("log", "apt introuvable : la forge automatique est indisponible."))
            self.log_queue.put(("refresh", None))
            missing = get_missing_tools()
            if missing:
                names = ", ".join(tool.display_name for tool in missing)
                self.log_queue.put(("log", f"Reliques manquantes : {names}"))
            else:
                self.log_queue.put(("log", "Toutes les reliques sont présentes."))
            self.log_queue.put(("busy", "false"))

        threading.Thread(target=task, daemon=True).start()

    def install_dependencies(self) -> None:
        if self.is_busy:
            return

        def task() -> None:
            self.log_queue.put(("busy", "true"))
            self.log_queue.put(("status", "Forge des reliques en cours..."))
            missing = get_missing_tools()
            if not missing:
                self.log_queue.put(("log", "Aucune relique manquante."))
            else:
                install_missing_tools(missing, logger=lambda line: self.log_queue.put(("log", line)))
            self.log_queue.put(("status", "Nouvelle lecture des reliques..."))
            self.log_queue.put(("refresh", None))
            remaining = get_missing_tools()
            if remaining:
                names = ", ".join(tool.display_name for tool in remaining)
                self.log_queue.put(("log", f"Encore manquant après la forge : {names}"))
            else:
                self.log_queue.put(("log", "Toutes les reliques sont maintenant présentes."))
            self.log_queue.put(("busy", "false"))

        threading.Thread(target=task, daemon=True).start()


class DashboardPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: GraalAtackAppProtocol) -> None:
        super().__init__(parent, padding=0, style="Page.TFrame")
        self.app = app
        self.card_labels: dict[str, tk.Label] = {}
        self._build_widgets()
        self.refresh_dashboard()

    def _build_widgets(self) -> None:
        self.canvas = tk.Canvas(self, bg=THEME["bg"], highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.bg_photo = self.app.assets.load(
            ASSET_DASHBOARD_BACKGROUND,
            "backgrounds/dashboard.png",
            size=(1600, 900),
        )
        self.content = tk.Frame(self.canvas, bg=THEME["bg"])
        self.canvas_window = self.canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.canvas.bind("<Configure>", self._resize_canvas)

        banner_outer, banner = premium_panel(self.content, padding=10, bg=THEME["panel"])
        banner_outer.pack(fill="x", padx=24, pady=(22, 18))
        image_or_placeholder(
            self.app.assets,
            banner,
            (ASSET_SANCTUARY_BANNER, "banners/sanctuary_banner.png"),
            (1420, 250),
            "✦  Le Graal n’est pas un objet, mais une quête éternelle de vérité et de perfection.  ✦",
            bg=THEME["panel"],
        ).pack(fill="x")

        hero_outer, hero = premium_panel(self.content, padding=18, bg=THEME["panel_alt"])
        hero_outer.pack(fill="x", padx=24, pady=(0, 20))
        hero.columnconfigure(1, weight=1)
        image_or_placeholder(
            self.app.assets,
            hero,
            (ASSET_ODIN,),
            (260, 300),
            "♛",
            bg=THEME["panel_alt"],
        ).grid(row=0, column=0, rowspan=3, sticky="nsw", padx=(0, 22))
        tk_label(hero, "ODIN — Gardien de la Connaissance", 28, THEME["gold_light"], THEME["panel_alt"], True).grid(row=0, column=1, sticky="w")
        tk_label(
            hero,
            "Sanctuaire de supervision mystique : les reliques, les archives et l’état du système convergent dans la grande salle du Graal.",
            15,
            THEME["muted"],
            THEME["panel_alt"],
        ).grid(row=1, column=1, sticky="w", pady=(8, 18))
        tk_label(hero, "✧ Centre de commandement cyber-mythologique ✧", 17, THEME["violet_light"], THEME["panel_alt"], True).grid(row=2, column=1, sticky="w")

        cards = tk.Frame(self.content, bg=THEME["bg"])
        cards.pack(fill="x", padx=24, pady=(0, 18))
        card_defs = (
            ("tools", "⚔", "Outils installés", "Reliques prêtes"),
            ("dependencies", "⚜", "Dépendances", "État des reliques"),
            ("reports", "📜", "Archives", "Quêtes consignées"),
            ("target", "◉", "Dernière cible", "Cible de quête"),
            ("system", "⛨", "État système", "Mode Sanctuaire"),
        )
        for index, (key, icon, title, subtitle) in enumerate(card_defs):
            outer, card = premium_panel(cards, padding=16, bg=THEME["panel_alt"])
            outer.grid(row=0, column=index, sticky="nsew", padx=7)
            cards.columnconfigure(index, weight=1)
            top = tk.Frame(card, bg=THEME["panel_alt"])
            top.pack(fill="x")
            tk_label(top, icon, 28, THEME["gold_light"], THEME["panel_alt"], True).pack(side="left", padx=(0, 10))
            tk_label(top, title, 13, THEME["muted"], THEME["panel_alt"], True).pack(side="left", anchor="n")
            value = tk_label(card, "-", 24, THEME["violet_light"], THEME["panel_alt"], True)
            value.pack(anchor="w", pady=(14, 4))
            tk_label(card, subtitle, 10, THEME["muted"], THEME["panel_alt"]).pack(anchor="w")
            self.card_labels[key] = value

    def _resize_canvas(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)
        if self.bg_photo is not None:
            self.canvas.delete("bg")
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw", tags="bg")
            self.canvas.tag_lower("bg")

    def refresh_dashboard(self) -> None:
        statuses = get_tool_statuses()
        installed = sum(1 for status in statuses if status["installed"])
        missing = len(statuses) - installed
        reports_dir = ensure_reports_dir(Path(str(self.app.get_reports_dir())).expanduser())
        reports_count = len(list(reports_dir.glob("*.txt")))
        dependency_text = "OK" if missing == 0 else f"{missing} manquante(s)"
        system_text = "PLEIN ÉCRAN" if self.app.is_fullscreen() else "EN VEILLE"
        target_text = str(self.app.get_last_target()).strip() or "Aucune"
        self.card_labels["tools"].configure(text=f"{installed}/{len(statuses)}")
        self.card_labels["dependencies"].configure(text=dependency_text)
        self.card_labels["reports"].configure(text=str(reports_count))
        self.card_labels["target"].configure(text=target_text)
        self.card_labels["system"].configure(text=system_text)


class ToolsPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: GraalAtackAppProtocol) -> None:
        super().__init__(parent, padding=12, style="Page.TFrame")
        self.app = app
        self.output_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.current_tool: ToolDefinition | None = None
        self.is_running = False
        self.tool_buttons: list[tuple[ttk.Button, ToolDefinition]] = []
        self._build_widgets()
        self.after(100, self._drain_output)
        self.refresh_tools()

    def _build_widgets(self) -> None:
        hero_outer, hero = premium_panel(self, padding=16, bg=THEME["panel_alt"])
        hero_outer.pack(fill="x", pady=(0, 16))
        hero.columnconfigure(1, weight=1)
        image_or_placeholder(
            self.app.assets,
            hero,
            (ASSET_ARES,),
            (180, 220),
            "⚔",
            bg=THEME["panel_alt"],
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 18))
        tk_label(hero, "ARÈS — Conduite des Missions", 24, THEME["gold_light"], THEME["panel_alt"], True).grid(row=0, column=1, sticky="w")
        tk_label(hero, "Choisissez une quête non destructive et consignez son grimoire d’exécution.", 14, THEME["muted"], THEME["panel_alt"]).grid(row=1, column=1, sticky="w", pady=(8, 0))
        target_bar = ttk.Frame(self, style="Page.TFrame")
        target_bar.pack(fill="x", pady=(0, 8))
        ttk.Label(target_bar, text="Cible de quête:", style="Gold.TLabel").pack(side="left")
        self.target_var = tk.StringVar(value=self.app.get_last_target())
        ttk.Entry(target_bar, textvariable=self.target_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Label(target_bar, text="Temps:", style="Gold.TLabel").pack(side="left")
        self.timeout_var = tk.StringVar(value=str(self.app.get_timeout()))
        ttk.Entry(target_bar, textvariable=self.timeout_var, width=7).pack(side="left", padx=4)
        ttk.Button(target_bar, text="✧ Rafraîchir les missions", command=self.refresh_tools).pack(side="left", padx=4)

        self.command_label = ttk.Label(self, text="Incantation: -", wraplength=920, style="Muted.TLabel")
        self.command_label.pack(anchor="w", pady=(0, 8))

        content = ttk.PanedWindow(self, orient="horizontal")
        content.pack(fill="both", expand=True)

        tool_frame = ttk.Frame(content, padding=(0, 0, 8, 0))
        content.add(tool_frame, weight=1)
        self.category_notebook = ttk.Notebook(tool_frame)
        self.category_notebook.pack(fill="both", expand=True)

        terminal_frame = ttk.Frame(content)
        content.add(terminal_frame, weight=2)
        ttk.Label(terminal_frame, text="Grimoire d’exécution", style="Section.TLabel").pack(anchor="w")
        self.output_text = tk.Text(terminal_frame, wrap="word", state="disabled", height=22)
        output_scroll = ttk.Scrollbar(terminal_frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=output_scroll.set)
        self.output_text.pack(side="left", fill="both", expand=True)
        output_scroll.pack(side="right", fill="y")

        self.status_label = ttk.Label(self, text="Statut : EN VEILLE", style="Muted.TLabel")
        self.status_label.pack(anchor="w", pady=(8, 0))

    def _append_output(self, message: str) -> None:
        self.output_text.configure(state="normal")
        self.output_text.insert("end", message + "\n")
        self.output_text.see("end")
        self.output_text.configure(state="disabled")

    def _clear_output(self) -> None:
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")

    def _drain_output(self) -> None:
        while True:
            try:
                kind, value = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "output" and value is not None:
                self._append_output(value)
            elif kind == "status" and value is not None:
                self.status_label.configure(text=value)
            elif kind == "command" and value is not None:
                self.command_label.configure(text=f"Incantation: {value}")
            elif kind == "running":
                self.is_running = value == "true"
                self._set_buttons_state()
            elif kind == "reports_refresh":
                self.app.refresh_reports()
        self.after(100, self._drain_output)

    def refresh_tools(self) -> None:
        for tab_id in self.category_notebook.tabs():
            self.category_notebook.forget(tab_id)
        self.tool_buttons.clear()
        show_advanced = self.app.show_advanced_tools()
        for category in CATEGORIES:
            frame = ttk.Frame(self.category_notebook, padding=8, style="Page.TFrame")
            self.category_notebook.add(frame, text=CATEGORY_LABELS.get(category, category))
            for tool in (item for item in TOOL_DEFINITIONS if item.category == category):
                if tool.advanced and not show_advanced:
                    continue
                row = ttk.Frame(frame, style="Page.TFrame")
                row.pack(fill="x", pady=3)
                installed = tool.binary_path() is not None
                display_label = TOOL_LABELS.get(tool.key, f"✦ {tool.label}")
                label = display_label if installed else f"{display_label} (absente)"
                button = ttk.Button(row, text=label, command=lambda selected=tool: self.launch_tool(selected))
                button.pack(side="left")
                ttk.Label(row, text=tool.description, wraplength=330, style="Muted.TLabel").pack(side="left", padx=8, fill="x", expand=True)
                self.tool_buttons.append((button, tool))
        self._set_buttons_state()

    def _set_buttons_state(self) -> None:
        for button, tool in self.tool_buttons:
            installed = tool.binary_path() is not None
            button.configure(state="normal" if installed and not self.is_running else "disabled")

    def _confirm_legal_authorization(self, tool: ToolDefinition) -> bool:
        if not self.app.requires_legal_authorization():
            return True
        return messagebox.askyesno(
            "Serment d’autorisation obligatoire",
            (
                f"Jurez-vous être autorisé à lancer {tool.label} sur cette cible de quête ?\n\n"
                "Usage permis uniquement pour audits autorisés, CTF, labs internes et machines personnelles."
            ),
        )

    def launch_tool(self, tool: ToolDefinition) -> None:
        if self.is_running:
            return
        if not self._confirm_legal_authorization(tool):
            self.status_label.configure(text="Quête annulée : serment non prononcé.")
            return
        try:
            timeout = validate_timeout(int(self.timeout_var.get().strip()))
            target_value = self.target_var.get().strip()
            self.app.set_timeout(timeout)
            command = tool.build_command(target_value, timeout)
            self.app.set_last_target(target_value)
        except ValueError:
            messagebox.showerror("Temps d’incantation invalide", "Le temps maximal d’incantation doit être un entier entre 5 et 3600 secondes.")
            return
        except ToolExecutionError as exc:
            messagebox.showerror("Lancement impossible", str(exc))
            return

        command_text = format_command(command)
        self.command_label.configure(text=f"Incantation: {command_text}")
        self._clear_output()
        self._append_output(f"➤ Incantation exécutée : {command_text}")
        self._append_output("✦ Sceau de sûreté : aucune option destructive n'est exposée par l'interface.")

        def task() -> None:
            self.output_queue.put(("running", "true"))
            self.output_queue.put(("status", f"Quête en cours : {tool.label}..."))
            started_at = datetime.now()
            output = ""
            return_code: int | str = "timeout"
            try:
                completed = run_command(command, timeout)
                output = completed.stdout or ""
                return_code = completed.returncode
                for line in output.splitlines():
                    self.output_queue.put(("output", line))
            except subprocess.TimeoutExpired as exc:
                output = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                for line in output.splitlines():
                    self.output_queue.put(("output", line))
                self.output_queue.put(("output", f"Timeout après {timeout} secondes."))
            except ToolExecutionError as exc:
                output = str(exc)
                self.output_queue.put(("output", output))
            report_path = self._save_report(tool, command_text, started_at, return_code, output)
            self.output_queue.put(("output", f"Archive de quête sauvegardée: {report_path}"))
            self.output_queue.put(("status", f"Quête terminée avec code {return_code}"))
            self.output_queue.put(("reports_refresh", None))
            self.output_queue.put(("running", "false"))

        threading.Thread(target=task, daemon=True).start()

    def focus_target(self) -> None:
        self.target_var.set(self.app.get_last_target())
        for child in self.winfo_children():
            self._focus_first_entry(child)

    def _focus_first_entry(self, widget: tk.Misc) -> bool:
        if isinstance(widget, ttk.Entry):
            widget.focus_set()
            widget.selection_range(0, "end")
            return True
        for child in widget.winfo_children():
            if self._focus_first_entry(child):
                return True
        return False

    def _save_report(
        self,
        tool: ToolDefinition,
        command_text: str,
        started_at: datetime,
        return_code: int | str,
        output: str,
    ) -> Path:
        reports_dir = ensure_reports_dir(Path(str(self.app.get_reports_dir())).expanduser())
        safe_tool = tool.key.replace("/", "_")
        report_name = f"{started_at.strftime('%Y%m%d-%H%M%S')}_{safe_tool}.txt"
        report_path = reports_dir / report_name
        report_path.write_text(
            "\n".join(
                [
                    f"Application: {APP_NAME}",
                    f"Mission: {tool.label}",
                    f"Royaume: {CATEGORY_LABELS.get(tool.category, tool.category)}",
                    f"Début de quête: {started_at.isoformat(timespec='seconds')}",
                    f"Incantation: {command_text}",
                    f"Code retour: {return_code}",
                    "",
                    output,
                ]
            ),
            encoding="utf-8",
        )
        return report_path


class ReportsPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: GraalAtackAppProtocol) -> None:
        super().__init__(parent, padding=12, style="Page.TFrame")
        self.app = app
        self._build_widgets()
        self.refresh_reports()

    def _build_widgets(self) -> None:
        hero_outer, hero = premium_panel(self, padding=16, bg=THEME["panel_alt"])
        hero_outer.pack(fill="x", pady=(0, 16))
        hero.columnconfigure(1, weight=1)
        image_or_placeholder(
            self.app.assets,
            hero,
            (ASSET_HADES,),
            (180, 220),
            "📜",
            bg=THEME["panel_alt"],
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 18))
        tk_label(hero, "HADÈS — Gardien des Archives", 24, THEME["gold_light"], THEME["panel_alt"], True).grid(row=0, column=1, sticky="w")
        tk_label(hero, "Les parchemins des quêtes sont conservés dans les cryptes du Sanctuaire.", 14, THEME["muted"], THEME["panel_alt"]).grid(row=1, column=1, sticky="w", pady=(8, 0))
        top = ttk.Frame(self, style="Page.TFrame")
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="✧ Révéler les archives", command=self.refresh_reports).pack(side="right")

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Page.TFrame")
        body.add(left, weight=1)
        self.reports_list = tk.Listbox(left, height=20)
        list_scroll = ttk.Scrollbar(left, orient="vertical", command=self.reports_list.yview)
        self.reports_list.configure(yscrollcommand=list_scroll.set)
        self.reports_list.pack(side="left", fill="both", expand=True)
        list_scroll.pack(side="right", fill="y")

        right = ttk.Frame(body, style="Page.TFrame")
        body.add(right, weight=2)
        ttk.Label(right, text="Lecture du parchemin", style="Section.TLabel").pack(anchor="w")
        self.preview = tk.Text(right, wrap="word", state="disabled")
        preview_scroll = ttk.Scrollbar(right, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=preview_scroll.set)
        self.preview.pack(side="left", fill="both", expand=True)
        preview_scroll.pack(side="right", fill="y")

        buttons = ttk.Frame(self, style="Page.TFrame")
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Ouvrir l’archive", command=self.open_selected_report).pack(side="left")
        ttk.Button(buttons, text="Détruire l’archive", command=self.delete_selected_report).pack(side="left", padx=8)
        ttk.Button(buttons, text="Exporter le parchemin", command=self.export_selected_report).pack(side="left")
        self.status_label = ttk.Label(buttons, text="Statut : EN VEILLE", style="Muted.TLabel")
        self.status_label.pack(side="left", padx=12)

    def _reports_dir(self) -> Path:
        return ensure_reports_dir(Path(str(self.app.get_reports_dir())).expanduser())

    def _selected_report(self) -> Path | None:
        selection = self.reports_list.curselection()
        if not selection:
            messagebox.showinfo("Aucune archive", "Sélectionnez une archive.")
            return None
        return self._reports_dir() / self.reports_list.get(selection[0])

    def refresh_reports(self) -> None:
        self.reports_list.delete(0, "end")
        reports_dir = self._reports_dir()
        for path in sorted(reports_dir.glob("*.txt"), reverse=True):
            self.reports_list.insert("end", path.name)
        self.status_label.configure(text=f"Dossier des archives: {reports_dir}")

    def open_selected_report(self) -> None:
        path = self._selected_report()
        if path is None:
            return
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror("Lecture impossible", str(exc))
            return
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("end", content)
        self.preview.configure(state="disabled")
        self.status_label.configure(text=f"Archive ouverte: {path.name}")

    def delete_selected_report(self) -> None:
        path = self._selected_report()
        if path is None:
            return
        if not messagebox.askyesno("Détruire l’archive", f"Détruire l’archive {path.name} ?"):
            return
        try:
            path.unlink()
        except OSError as exc:
            messagebox.showerror("Destruction impossible", str(exc))
            return
        self.refresh_reports()
        self.status_label.configure(text=f"Archive détruite: {path.name}")

    def export_selected_report(self) -> None:
        path = self._selected_report()
        if path is None:
            return
        destination = filedialog.asksaveasfilename(
            title="Exporter le parchemin le rapport",
            initialfile=path.name,
            defaultextension=".txt",
            filetypes=(("Archives de quête", "*.txt"), ("Tous les fichiers", "*.*")),
        )
        if not destination:
            return
        try:
            shutil.copy2(path, destination)
        except OSError as exc:
            messagebox.showerror("Export du parchemin impossible", str(exc))
            return
        self.status_label.configure(text=f"Parchemin exporté vers: {destination}")


class SettingsPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: GraalAtackAppProtocol) -> None:
        super().__init__(parent, padding=12, style="Page.TFrame")
        self.app = app
        self._build_widgets()

    def _build_widgets(self) -> None:
        ttk.Label(self, text="⚙ Autel", style="PageTitle.TLabel").pack(anchor="w", pady=(0, 12))

        timeout_row = ttk.Frame(self, style="Page.TFrame")
        timeout_row.pack(fill="x", pady=4)
        ttk.Label(timeout_row, text="Temps maximal d’incantation:", width=32).pack(side="left")
        self.timeout_var = tk.StringVar(value=str(self.app.get_timeout()))
        ttk.Entry(timeout_row, textvariable=self.timeout_var, width=10).pack(side="left")

        reports_row = ttk.Frame(self, style="Page.TFrame")
        reports_row.pack(fill="x", pady=4)
        ttk.Label(reports_row, text="Dossier des archives:", width=32).pack(side="left")
        self.reports_var = tk.StringVar(value=str(self.app.get_reports_dir()))
        ttk.Entry(reports_row, textvariable=self.reports_var).pack(side="left", fill="x", expand=True)
        ttk.Button(reports_row, text="Parcourir les cryptes", command=self.choose_reports_dir).pack(side="left", padx=6)

        self.dark_var = tk.BooleanVar(value=self.app.dark_mode_enabled())
        self.advanced_var = tk.BooleanVar(value=self.app.show_advanced_tools())
        self.legal_var = tk.BooleanVar(value=self.app.requires_legal_authorization())
        self.fullscreen_var = tk.BooleanVar(value=self.app.starts_fullscreen())
        ttk.Checkbutton(self, text="Mode sombre du sanctuaire", variable=self.dark_var).pack(anchor="w", pady=4)
        ttk.Checkbutton(
            self,
            text="Révéler les arts avancés",
            variable=self.advanced_var,
        ).pack(anchor="w", pady=4)
        ttk.Checkbutton(
            self,
            text="Serment d’autorisation obligatoire",
            variable=self.legal_var,
        ).pack(anchor="w", pady=4)
        ttk.Checkbutton(
            self,
            text="Démarrer en mode sanctuaire plein écran",
            variable=self.fullscreen_var,
        ).pack(anchor="w", pady=4)

        ttk.Button(self, text="Sceller les paramètres", command=self.save).pack(anchor="w", pady=12)
        self.status_label = ttk.Label(self, text="Les sceaux sont sauvegardés dans ~/.config/graal-atack/settings.ini", style="Muted.TLabel")
        self.status_label.pack(anchor="w")

    def choose_reports_dir(self) -> None:
        selected = filedialog.askdirectory(title="Choisir le dossier des archives")
        if selected:
            self.reports_var.set(selected)

    def save(self) -> None:
        try:
            timeout = validate_timeout(int(self.timeout_var.get().strip()))
        except (ValueError, ToolExecutionError):
            messagebox.showerror("Temps d’incantation invalide", "Le temps maximal d’incantation doit être un entier entre 5 et 3600 secondes.")
            return
        reports_dir = Path(self.reports_var.get()).expanduser()
        try:
            ensure_reports_dir(reports_dir)
        except OSError as exc:
            messagebox.showerror("Crypte invalide", str(exc))
            return
        self.app.update_settings(
            timeout=timeout,
            reports_dir=str(reports_dir),
            dark_mode=self.dark_var.get(),
            show_advanced=self.advanced_var.get(),
            require_legal_authorization=self.legal_var.get(),
            start_fullscreen=self.fullscreen_var.get(),
        )
        self.status_label.configure(text="Paramètres scellés sur l’Autel.")


class GraalAtackAppProtocol(Protocol):
    def get_timeout(self) -> int: ...
    def set_timeout(self, timeout: int) -> None: ...
    def get_reports_dir(self) -> str: ...
    def dark_mode_enabled(self) -> bool: ...
    def show_advanced_tools(self) -> bool: ...
    def requires_legal_authorization(self) -> bool: ...
    def starts_fullscreen(self) -> bool: ...
    def is_fullscreen(self) -> bool: ...
    def get_last_target(self) -> str: ...
    def set_last_target(self, target: str) -> None: ...
    def focus_global_target(self) -> None: ...
    def select_page(self, page_key: str) -> None: ...
    def refresh_reports(self) -> None: ...
    def update_settings(self, **kwargs: object) -> None: ...


class GraalAtackApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        self.fullscreen_enabled = False
        self.title(APP_NAME)
        self.geometry("1600x900")
        self.minsize(1600, 900)
        asset_dir = assets_root()
        self.assets = AssetManager(asset_dir)
        self.fonts = FontManager(self, asset_dir / "fonts")
        window_icon = self.assets.load(
            ASSET_LOGO,
            "icons/app.png",
            "graal.png",
            "icon.png",
            size=(96, 96),
        )
        if window_icon is not None:
            self.iconphoto(True, window_icon)
        ensure_reports_dir(Path(str(self.settings["reports_dir"])).expanduser())
        self._build_ui()
        self._bind_shortcuts()
        self.apply_theme()
        if self.starts_fullscreen():
            self.after(100, lambda: self.set_fullscreen(True))
        self.after(300, self._show_legal_warning_once)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, padding=(18, 14), style="Header.TFrame")
        header.pack(side="top", fill="x")
        header_inner = ttk.Frame(header, style="Header.TFrame")
        header_inner.pack(anchor="center")
        self.assets.label(
            header_inner,
            ASSET_LOGO,
            "banners/header_sigils.png",
            "graal.png",
            size=(88, 88),
            placeholder="♕",
            style="HeaderIcon.TLabel",
        ).pack(side="left", padx=(0, 16))
        title_box = ttk.Frame(header_inner, style="Header.TFrame")
        title_box.pack(side="left")
        ttk.Label(title_box, text="♕  GRAAL-ATTACK  ♛", style="HeaderTitle.TLabel").pack(anchor="center")
        ttk.Label(title_box, text=SUBTITLE, style="HeaderSubtitle.TLabel").pack(anchor="center", pady=(3, 6))
        ttk.Label(title_box, text="✧ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ✧", style="Gold.TLabel").pack(anchor="center")

        body = ttk.Frame(root, style="Root.TFrame")
        body.pack(side="top", fill="both", expand=True)

        self.sidebar = ttk.Frame(body, padding=20, width=310, style="Sidebar.TFrame")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.assets.label(
            self.sidebar,
            ASSET_LOGO,
            ASSET_GUARDIAN,
            "graal.png",
            size=(120, 120),
            placeholder="🏆",
            style="LogoIcon.TLabel",
        ).pack(anchor="center")
        ttk.Label(self.sidebar, text="GRAAL-ATTACK", style="SidebarTitle.TLabel").pack(anchor="center", pady=(10, 4))
        ttk.Label(
            self.sidebar,
            text="Sanctuaire d'Audit et de Supervision",
            style="SidebarSubtitle.TLabel",
            wraplength=245,
            justify="center",
        ).pack(anchor="center", pady=(0, 5))
        ttk.Label(self.sidebar, text=APP_VERSION, style="Muted.TLabel").pack(anchor="center", pady=(0, 18))

        self.notebook = ttk.Notebook(body)
        self.notebook.pack(side="right", fill="both", expand=True)

        self.dashboard_page = DashboardPage(self.notebook, self)
        self.dependency_page = DependencyPage(self.notebook)
        self.tools_page = ToolsPage(self.notebook, self)
        self.reports_page = ReportsPage(self.notebook, self)
        self.settings_page = SettingsPage(self.notebook, self)

        self.pages = {
            "dashboard": (self.dashboard_page, "🛡 Sanctuaire"),
            "dependencies": (self.dependency_page, "⚜ Reliques"),
            "tools": (self.tools_page, "⚔ Missions"),
            "reports": (self.reports_page, "📜 Archives"),
            "settings": (self.settings_page, "⚙ Autel"),
        }
        for page, title in self.pages.values():
            self.notebook.add(page, text=title)

        for key, (_, title) in self.pages.items():
            ttk.Button(self.sidebar, text=title, style="Sidebar.TButton", command=lambda page_key=key: self.select_page(page_key)).pack(
                fill="x", pady=5
            )
        ttk.Separator(self.sidebar).pack(fill="x", pady=12)
        self.fullscreen_button = ttk.Button(self.sidebar, text="Entrer dans le Sanctuaire", style="Sidebar.TButton", command=self.toggle_fullscreen)
        self.fullscreen_button.pack(fill="x", pady=4)
        ttk.Button(
            self.sidebar,
            text="Quitter le Sanctuaire",
            style="Sidebar.TButton",
            command=lambda: self.set_fullscreen(False),
        ).pack(fill="x", pady=4)
        ttk.Button(self.sidebar, text="✠ Quitter (Ctrl+Q)", style="Danger.TButton", command=self.safe_quit).pack(fill="x", pady=(14, 4))
        self.assets.label(
            self.sidebar,
            ASSET_GUARDIAN,
            ASSET_ATHENA,
            size=(150, 180),
            placeholder="🛡",
            style="Portrait.TLabel",
        ).pack(anchor="center", pady=(18, 8))
        ttk.Label(self.sidebar, text=f"“{QUOTE}”", style="Quote.TLabel", wraplength=180, justify="center").pack(
            anchor="center", pady=(8, 10)
        )
        ttk.Label(self.sidebar, text="Statut : EN VEILLE", style="Status.TLabel").pack(anchor="center", pady=(0, 8))
        ttk.Label(
            self.sidebar,
            text="F11 Sanctuaire\nCtrl+L cible\nCtrl+Q quitter",
            style="Muted.TLabel",
            wraplength=170,
            justify="center",
        ).pack(anchor="center", side="bottom", pady=8)

    def _bind_shortcuts(self) -> None:
        self.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.bind("<Control-q>", lambda _event: self.safe_quit())
        self.bind("<Control-Q>", lambda _event: self.safe_quit())
        self.bind("<Control-l>", lambda _event: self.focus_global_target())
        self.bind("<Control-L>", lambda _event: self.focus_global_target())
        self.protocol("WM_DELETE_WINDOW", self.safe_quit)

    def toggle_fullscreen(self) -> None:
        self.set_fullscreen(not self.fullscreen_enabled)

    def set_fullscreen(self, enabled: bool) -> None:
        self.fullscreen_enabled = enabled
        self.attributes("-fullscreen", enabled)
        self.fullscreen_button.configure(text="Quitter le Sanctuaire" if enabled else "Entrer dans le Sanctuaire")
        self.dashboard_page.refresh_dashboard()

    def safe_quit(self) -> None:
        self.attributes("-fullscreen", False)
        self.destroy()

    def select_page(self, page_key: str) -> None:
        if page_key == "dashboard":
            self.dashboard_page.refresh_dashboard()
        elif page_key == "reports":
            self.reports_page.refresh_reports()
        self.dashboard_page.refresh_dashboard()
        page = self.pages[page_key][0]
        self.notebook.select(page)

    def focus_global_target(self) -> None:
        self.select_page("tools")
        self.tools_page.focus_target()

    def _show_legal_warning_once(self) -> None:
        if bool(self.settings["legal_notice_seen"]):
            return
        messagebox.showwarning("Avertissement légal", LEGAL_WARNING)
        self.settings["legal_notice_seen"] = True
        save_settings(self.settings)

    def is_fullscreen(self) -> bool:
        return self.fullscreen_enabled

    def get_timeout(self) -> int:
        return int(self.settings["timeout"])

    def set_timeout(self, timeout: int) -> None:
        self.settings["timeout"] = timeout
        save_settings(self.settings)

    def get_reports_dir(self) -> str:
        return str(self.settings["reports_dir"])

    def dark_mode_enabled(self) -> bool:
        return bool(self.settings["dark_mode"])

    def show_advanced_tools(self) -> bool:
        return bool(self.settings["show_advanced"])

    def requires_legal_authorization(self) -> bool:
        return bool(self.settings["require_legal_authorization"])

    def starts_fullscreen(self) -> bool:
        return bool(self.settings["start_fullscreen"])

    def get_last_target(self) -> str:
        return str(self.settings.get("last_target", ""))

    def set_last_target(self, target: str) -> None:
        self.settings["last_target"] = target
        save_settings(self.settings)
        self.dashboard_page.refresh_dashboard()

    def refresh_reports(self) -> None:
        self.reports_page.refresh_reports()
        self.dashboard_page.refresh_dashboard()

    def update_settings(self, **kwargs: object) -> None:
        self.settings.update(kwargs)
        save_settings(self.settings)
        ensure_reports_dir(Path(str(self.settings["reports_dir"])).expanduser())
        self.apply_theme()
        self.tools_page.timeout_var.set(str(self.get_timeout()))
        self.tools_page.refresh_tools()
        self.reports_page.refresh_reports()
        self.dashboard_page.refresh_dashboard()

    def apply_theme(self) -> None:
        style = ttk.Style(self)
        bg = THEME["bg"]
        panel = THEME["panel"]
        panel_alt = THEME["panel_alt"]
        text = THEME["text"]
        muted = THEME["muted"]
        gold = THEME["gold"]
        gold_light = THEME["gold_light"]
        violet = THEME["violet"]
        field_bg = "#0d0b0a"
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        fonts = getattr(self, "fonts", None)
        title_family = fonts.title_family if fonts is not None else "Georgia"
        body_family = fonts.body_family if fonts is not None else "Segoe UI"
        style.configure("Root.TFrame", background=bg)
        style.configure("Page.TFrame", background=bg)
        style.configure("Header.TFrame", background=THEME["bg_alt"], borderwidth=1, relief="ridge")
        style.configure("Sidebar.TFrame", background=panel, borderwidth=1, relief="ridge")
        style.configure("Card.TFrame", background=panel_alt, borderwidth=1, relief="ridge")
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=text, font=(body_family, 13))
        style.configure("Muted.TLabel", background=bg, foreground=muted, font=(body_family, 13))
        style.configure("Gold.TLabel", background=bg, foreground=gold_light, font=(body_family, 13, "bold"))
        style.configure("Section.TLabel", background=bg, foreground=gold_light, font=(title_family, 18, "bold"))
        style.configure("PageTitle.TLabel", background=bg, foreground=gold_light, font=(title_family, 26, "bold"))
        style.configure("HeaderTitle.TLabel", background=THEME["bg_alt"], foreground=gold_light, font=(title_family, 34, "bold"))
        style.configure("HeaderSubtitle.TLabel", background=THEME["bg_alt"], foreground=muted, font=(body_family, 17, "italic"))
        style.configure("SidebarTitle.TLabel", background=panel, foreground=gold_light, font=(title_family, 22, "bold"))
        style.configure("SidebarSubtitle.TLabel", background=panel, foreground=muted, font=(body_family, 13, "italic"))
        style.configure("LogoIcon.TLabel", background=panel, foreground=gold_light, font=(title_family, 58, "bold"))
        style.configure("HeaderIcon.TLabel", background=THEME["bg_alt"], foreground=gold_light, font=(title_family, 56, "bold"))
        style.configure("Portrait.TLabel", background=panel, foreground=THEME["violet_light"], font=(title_family, 48, "bold"))
        style.configure("ImagePlaceholder.TLabel", background=panel_alt, foreground=THEME["violet_light"], font=(title_family, 34, "bold"))
        style.configure("Quote.TLabel", background=panel, foreground=muted, font=(body_family, 12, "italic"))
        style.configure("Status.TLabel", background=panel, foreground=THEME["success"], font=(body_family, 13, "bold"))
        style.configure("Banner.TLabel", background=panel_alt, foreground=gold_light, font=(title_family, 15, "italic"))
        style.configure("CardTitle.TLabel", background=panel_alt, foreground=gold_light, font=(title_family, 16, "bold"))
        style.configure("CardValue.TLabel", background=panel_alt, foreground=THEME["violet_light"], font=(title_family, 34, "bold"))
        style.configure("CardIcon.TLabel", background=panel_alt, foreground=gold_light, font=(title_family, 34, "bold"))
        style.configure("TButton", background=panel_alt, foreground=text, bordercolor=gold, lightcolor=gold, darkcolor=THEME["gold_dark"], focusthickness=1, focuscolor=violet, padding=(20, 14), font=(body_family, 14, "bold"))
        style.map("TButton", background=[("active", violet), ("pressed", THEME["gold_dark"])], foreground=[("active", "#ffffff")])
        style.configure("Sidebar.TButton", background=panel_alt, foreground=gold_light, bordercolor=gold, lightcolor=gold_light, darkcolor=THEME["gold_dark"], focusthickness=2, focuscolor=THEME["violet_light"], padding=(18, 15), font=(body_family, 14, "bold"))
        style.map("Sidebar.TButton", background=[("active", THEME["violet"]), ("pressed", THEME["gold_dark"])], foreground=[("active", "#ffffff")])
        style.configure("Danger.TButton", background="#231010", foreground=THEME["warning"], bordercolor=THEME["gold_dark"], padding=(18, 15), font=(body_family, 14, "bold"))
        style.map("Danger.TButton", background=[("active", THEME["error"]), ("pressed", "#4a1515")], foreground=[("active", "#ffffff")])
        style.configure("TCheckbutton", background=bg, foreground=text, font=(body_family, 14))
        style.map("TCheckbutton", background=[("active", bg)], foreground=[("active", gold_light)])
        style.configure("TEntry", fieldbackground=field_bg, foreground=text, bordercolor=gold, insertcolor=text)
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=panel, foreground=muted, padding=(12, 7), font=(body_family, 14, "bold"))
        style.map("TNotebook.Tab", background=[("selected", panel_alt), ("active", violet)], foreground=[("selected", gold_light), ("active", "#ffffff")])
        style.configure("Treeview", background=field_bg, foreground=text, fieldbackground=field_bg, bordercolor=gold, rowheight=34)
        style.configure("Treeview.Heading", background=panel_alt, foreground=gold_light, font=(body_family, 13, "bold"))
        style.map("Treeview", background=[("selected", violet)], foreground=[("selected", "#ffffff")])
        style.configure("Horizontal.TProgressbar", troughcolor=field_bg, background=gold, bordercolor=THEME["gold_dark"], lightcolor=gold_light, darkcolor=THEME["gold_dark"])
        style.configure("TPanedwindow", background=bg)
        self.configure(background=bg)
        self._apply_text_theme(self, field_bg, text)

    def _apply_text_theme(self, widget: tk.Misc, bg: str, fg: str) -> None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Text):
                child.configure(background=bg, foreground=fg, insertbackground=fg)
            elif isinstance(child, tk.Listbox):
                child.configure(background=bg, foreground=fg)
            self._apply_text_theme(child, bg, fg)


def main() -> None:
    app = GraalAtackApp()
    app.mainloop()


if __name__ == "__main__":
    main()
