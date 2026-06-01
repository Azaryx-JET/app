from __future__ import annotations

import configparser
from datetime import datetime
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Protocol

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
CONFIG_DIR = Path.home() / ".config" / "graal-attack"
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
    "bg": "#050505",
    "bg_alt": "#080706",
    "panel": "#11100d",
    "panel_alt": "#17130f",
    "gold_dark": "#8b6f2d",
    "gold": "#b9923b",
    "gold_light": "#d8b45a",
    "text": "#e7d6a3",
    "muted": "#9c8c68",
    "violet": "#7d35d8",
    "violet_light": "#a855f7",
    "success": "#72e06a",
    "error": "#d94b4b",
    "warning": "#d89b35",
}
TITLE_FONT = ("Cinzel", "Trajan Pro", "Georgia", "serif")
BODY_FONT = ("Georgia", "Sans")

CATEGORY_LABELS = {
    "Network": "Royaume Réseau",
    "DNS": "Oracles DNS",
    "Web": "Donjons Web",
    "SMB": "Portes SMB",
    "Wireless": "Ondes Mystiques",
    "OSINT": "Vision de l’Oracle",
}
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
        self.is_busy = False
        self._build_widgets()
        self.after(100, self._drain_logs)
        self.check_dependencies(background=True)

    def _build_widgets(self) -> None:
        ttk.Label(self, text="⚜ Reliques", style="PageTitle.TLabel").pack(anchor="w")
        intro = ttk.Label(
            self,
            text=(
                "Les reliques nécessaires à la quête sont vérifiées avant chaque mission. "
                "La forge utilise apt sur Debian, Kali ou Ubuntu."
            ),
            wraplength=900,
            style="Muted.TLabel",
        )
        intro.pack(anchor="w", pady=(0, 8))

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
    def __init__(self, parent: tk.Misc, app: GraalAttackAppProtocol) -> None:
        super().__init__(parent, padding=18, style="Page.TFrame")
        self.app = app
        self.card_labels: dict[str, ttk.Label] = {}
        self._build_widgets()
        self.refresh_dashboard()

    def _build_widgets(self) -> None:
        ttk.Label(self, text="♕ Sanctuaire", style="PageTitle.TLabel").pack(anchor="w")
        banner = ttk.Frame(self, padding=16, style="Card.TFrame")
        banner.pack(fill="x", pady=(10, 18))
        ttk.Label(
            banner,
            text="✦ Le Graal n’est pas un objet, mais une quête éternelle de vérité et de perfection. ✦",
            style="Banner.TLabel",
            wraplength=980,
            justify="center",
        ).pack(fill="x")
        ttk.Label(
            self,
            text="Sanctuaire SOC mythologique : observez les reliques, les archives et l’état de la quête.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        cards = ttk.Frame(self, style="Page.TFrame")
        cards.pack(fill="x")
        card_defs = (
            ("tools", "⚔", "Outils Totaux", "Reliques prêtes au combat"),
            ("dependencies", "⚜", "Dépendances", "Statut des reliques"),
            ("reports", "📜", "Archives de Quêtes", "Parchemins générés"),
            ("system", "⛨", "Système", "Mode sanctuaire"),
        )
        for index, (key, icon, title, subtitle) in enumerate(card_defs):
            card = ttk.Frame(cards, padding=16, style="Card.TFrame")
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=8, pady=8)
            cards.columnconfigure(index % 2, weight=1)
            top = ttk.Frame(card, style="Card.TFrame")
            top.pack(fill="x")
            ttk.Label(top, text=icon, style="CardIcon.TLabel").pack(side="left", padx=(0, 12))
            title_box = ttk.Frame(top, style="Card.TFrame")
            title_box.pack(side="left", fill="x", expand=True)
            ttk.Label(title_box, text=title, style="CardTitle.TLabel").pack(anchor="w")
            value = ttk.Label(title_box, text="-", style="CardValue.TLabel")
            value.pack(anchor="w", pady=(4, 0))
            ttk.Label(card, text=subtitle, style="Muted.TLabel").pack(anchor="w", pady=(12, 0))
            self.card_labels[key] = value

        actions = ttk.Frame(self, style="Page.TFrame")
        actions.pack(fill="x", pady=18)
        ttk.Button(actions, text="✧ Actualiser le Sanctuaire", command=self.refresh_dashboard).pack(side="left")
        ttk.Button(actions, text="⚔ Ouvrir les Missions", command=lambda: self.app.select_page("tools")).pack(side="left", padx=8)
        ttk.Button(
            actions,
            text="⚜ Scanner les Reliques",
            command=lambda: self.app.select_page("dependencies"),
        ).pack(side="left")

    def refresh_dashboard(self) -> None:
        statuses = get_tool_statuses()
        installed = sum(1 for status in statuses if status["installed"])
        missing = len(statuses) - installed
        reports_dir = ensure_reports_dir(Path(str(self.app.get_reports_dir())).expanduser())
        reports_count = len(list(reports_dir.glob("*.txt")))
        dependency_text = "OK" if missing == 0 else f"{missing} manquante(s)"
        system_text = "PLEIN ÉCRAN" if self.app.is_fullscreen() else "EN VEILLE"
        self.card_labels["tools"].configure(text=f"{installed}/{len(statuses)}")
        self.card_labels["reports"].configure(text=str(reports_count))
        self.card_labels["dependencies"].configure(text=dependency_text)
        self.card_labels["system"].configure(text=system_text)


class ToolsPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: GraalAttackAppProtocol) -> None:
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
        ttk.Label(self, text="⚔ Missions", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(self, text="Choisissez une quête non destructive et consignez son grimoire d’exécution.", style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
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
    def __init__(self, parent: tk.Misc, app: GraalAttackAppProtocol) -> None:
        super().__init__(parent, padding=12, style="Page.TFrame")
        self.app = app
        self._build_widgets()
        self.refresh_reports()

    def _build_widgets(self) -> None:
        top = ttk.Frame(self, style="Page.TFrame")
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="📜 Archives", style="PageTitle.TLabel").pack(side="left")
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
    def __init__(self, parent: tk.Misc, app: GraalAttackAppProtocol) -> None:
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
        self.status_label = ttk.Label(self, text="Les sceaux sont sauvegardés dans ~/.config/graal-attack/settings.ini", style="Muted.TLabel")
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


class GraalAttackAppProtocol(Protocol):
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


class GraalAttackApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        self.fullscreen_enabled = False
        self.title(APP_NAME)
        self.geometry("1120x760")
        self.minsize(980, 650)
        asset_dir = Path(__file__).resolve().parent / "assets"
        for icon_name in ("logo.png", "graal.png", "icon.png"):
            icon_path = asset_dir / icon_name
            if icon_path.exists():
                try:
                    self.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
                    break
                except tk.TclError:
                    pass
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
        ttk.Label(header, text="♕  GRAAL-ATTACK  ♛", style="HeaderTitle.TLabel").pack(anchor="center")
        ttk.Label(header, text=SUBTITLE, style="HeaderSubtitle.TLabel").pack(anchor="center", pady=(3, 6))
        ttk.Label(header, text="✧ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ✧", style="Gold.TLabel").pack(anchor="center")

        body = ttk.Frame(root, style="Root.TFrame")
        body.pack(side="top", fill="both", expand=True)

        self.sidebar = ttk.Frame(body, padding=14, width=220, style="Sidebar.TFrame")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ttk.Label(self.sidebar, text="🏆", style="LogoIcon.TLabel").pack(anchor="center")
        ttk.Label(self.sidebar, text="GRAAL-ATTACK", style="SidebarTitle.TLabel").pack(anchor="center", pady=(0, 2))
        ttk.Label(self.sidebar, text=APP_VERSION, style="Muted.TLabel").pack(anchor="center", pady=(0, 14))

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
            ttk.Button(self.sidebar, text=title, command=lambda page_key=key: self.select_page(page_key)).pack(
                fill="x", pady=4
            )
        ttk.Separator(self.sidebar).pack(fill="x", pady=12)
        self.fullscreen_button = ttk.Button(self.sidebar, text="Entrer dans le Sanctuaire", command=self.toggle_fullscreen)
        self.fullscreen_button.pack(fill="x", pady=4)
        ttk.Button(
            self.sidebar,
            text="Quitter le Sanctuaire",
            command=lambda: self.set_fullscreen(False),
        ).pack(fill="x", pady=4)
        ttk.Button(self.sidebar, text="✠ Quitter (Ctrl+Q)", command=self.safe_quit).pack(fill="x", pady=(14, 4))
        ttk.Label(self.sidebar, text=f"“{QUOTE}”", style="Quote.TLabel", wraplength=180, justify="center").pack(
            anchor="center", pady=(18, 10)
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
        title_family = "Georgia"
        body_family = "Georgia"
        style.configure("Root.TFrame", background=bg)
        style.configure("Page.TFrame", background=bg)
        style.configure("Header.TFrame", background=THEME["bg_alt"], borderwidth=1, relief="ridge")
        style.configure("Sidebar.TFrame", background=panel, borderwidth=1, relief="ridge")
        style.configure("Card.TFrame", background=panel_alt, borderwidth=1, relief="ridge")
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=text, font=(body_family, 10))
        style.configure("Muted.TLabel", background=bg, foreground=muted, font=(body_family, 10))
        style.configure("Gold.TLabel", background=bg, foreground=gold_light, font=(body_family, 10, "bold"))
        style.configure("Section.TLabel", background=bg, foreground=gold_light, font=(title_family, 13, "bold"))
        style.configure("PageTitle.TLabel", background=bg, foreground=gold_light, font=(title_family, 20, "bold"))
        style.configure("HeaderTitle.TLabel", background=THEME["bg_alt"], foreground=gold_light, font=(title_family, 28, "bold"))
        style.configure("HeaderSubtitle.TLabel", background=THEME["bg_alt"], foreground=muted, font=(body_family, 11, "italic"))
        style.configure("SidebarTitle.TLabel", background=panel, foreground=gold_light, font=(title_family, 15, "bold"))
        style.configure("LogoIcon.TLabel", background=panel, foreground=gold_light, font=(title_family, 28, "bold"))
        style.configure("Quote.TLabel", background=panel, foreground=muted, font=(body_family, 9, "italic"))
        style.configure("Status.TLabel", background=panel, foreground=THEME["success"], font=(body_family, 10, "bold"))
        style.configure("Banner.TLabel", background=panel_alt, foreground=gold_light, font=(title_family, 15, "italic"))
        style.configure("CardTitle.TLabel", background=panel_alt, foreground=gold_light, font=(title_family, 12, "bold"))
        style.configure("CardValue.TLabel", background=panel_alt, foreground=THEME["violet_light"], font=(title_family, 24, "bold"))
        style.configure("CardIcon.TLabel", background=panel_alt, foreground=gold_light, font=(title_family, 30, "bold"))
        style.configure("TButton", background=panel_alt, foreground=text, bordercolor=gold, lightcolor=gold, darkcolor=THEME["gold_dark"], focusthickness=1, focuscolor=violet, padding=(10, 7), font=(body_family, 10, "bold"))
        style.map("TButton", background=[("active", violet), ("pressed", THEME["gold_dark"])], foreground=[("active", "#ffffff")])
        style.configure("TCheckbutton", background=bg, foreground=text, font=(body_family, 10))
        style.map("TCheckbutton", background=[("active", bg)], foreground=[("active", gold_light)])
        style.configure("TEntry", fieldbackground=field_bg, foreground=text, bordercolor=gold, insertcolor=text)
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=panel, foreground=muted, padding=(12, 7), font=(body_family, 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", panel_alt), ("active", violet)], foreground=[("selected", gold_light), ("active", "#ffffff")])
        style.configure("Treeview", background=field_bg, foreground=text, fieldbackground=field_bg, bordercolor=gold, rowheight=26)
        style.configure("Treeview.Heading", background=panel_alt, foreground=gold_light, font=(body_family, 10, "bold"))
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
    app = GraalAttackApp()
    app.mainloop()


if __name__ == "__main__":
    main()
