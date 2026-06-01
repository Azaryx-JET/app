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

APP_NAME = "Azaryx Offensive Tools"
CONFIG_DIR = Path.home() / ".config" / "azaryx-tools"
CONFIG_FILE = CONFIG_DIR / "settings.ini"
DEFAULT_REPORTS_DIR = Path.cwd() / "reports"
LEGAL_WARNING = (
    "Azaryx Offensive Tools regroupe des outils destinés uniquement aux audits "
    "autorisés, aux CTF, aux labs internes et aux machines dont vous êtes "
    "propriétaire ou explicitement autorisé à tester. Toute utilisation non "
    "autorisée est interdite."
)


def load_settings() -> dict[str, object]:
    config = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        config.read(CONFIG_FILE)
    return {
        "legal_notice_seen": config.getboolean("legal", "notice_seen", fallback=False),
        "timeout": config.getint("settings", "timeout", fallback=120),
        "reports_dir": config.get("settings", "reports_dir", fallback=str(DEFAULT_REPORTS_DIR)),
        "dark_mode": config.getboolean("settings", "dark_mode", fallback=False),
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
        super().__init__(parent, padding=12)
        self.log_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.is_busy = False
        self._build_widgets()
        self.after(100, self._drain_logs)
        self.check_dependencies(background=True)

    def _build_widgets(self) -> None:
        intro = ttk.Label(
            self,
            text=(
                "Vérification automatique des dépendances système. "
                "L'installation utilise apt sur Debian, Kali ou Ubuntu."
            ),
            wraplength=900,
        )
        intro.pack(anchor="w", pady=(0, 8))

        columns = ("tool", "package", "installed", "path")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=12)
        self.tree.heading("tool", text="Outil")
        self.tree.heading("package", text="Paquet apt")
        self.tree.heading("installed", text="Installé")
        self.tree.heading("path", text="Chemin binaire")
        self.tree.column("tool", width=180, anchor="w")
        self.tree.column("package", width=160, anchor="w")
        self.tree.column("installed", width=90, anchor="center")
        self.tree.column("path", width=480, anchor="w")
        self.tree.pack(fill="both", expand=True)

        button_bar = ttk.Frame(self)
        button_bar.pack(fill="x", pady=8)
        self.check_button = ttk.Button(button_bar, text="Vérifier", command=self.check_dependencies)
        self.check_button.pack(side="left")
        self.install_button = ttk.Button(
            button_bar,
            text="Installer les dépendances manquantes",
            command=self.install_dependencies,
        )
        self.install_button.pack(side="left", padx=8)
        self.status_label = ttk.Label(button_bar, text="Prêt")
        self.status_label.pack(side="left", padx=12)

        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 8))

        ttk.Label(self, text="Logs d'installation").pack(anchor="w")
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
                    "Oui" if installed else "Non",
                    status["path"] or "-",
                ),
            )
        if missing_count:
            self.status_label.configure(text=f"{missing_count} dépendance(s) manquante(s)")
            self.progress.configure(value=max(0, 100 - missing_count * 4))
        else:
            self.status_label.configure(text="Toutes les dépendances détectées")
            self.progress.configure(value=100)

    def check_dependencies(self, background: bool = False) -> None:
        if self.is_busy:
            return

        def task() -> None:
            self.log_queue.put(("busy", "true"))
            self.log_queue.put(("status", "Vérification en cours..."))
            package_manager = detect_package_manager()
            if package_manager != "apt":
                self.log_queue.put(("log", "apt introuvable : installation automatique indisponible."))
            self.log_queue.put(("refresh", None))
            missing = get_missing_tools()
            if missing:
                names = ", ".join(tool.display_name for tool in missing)
                self.log_queue.put(("log", f"Dépendances manquantes : {names}"))
            else:
                self.log_queue.put(("log", "Toutes les dépendances sont présentes."))
            self.log_queue.put(("busy", "false"))

        threading.Thread(target=task, daemon=True).start()

    def install_dependencies(self) -> None:
        if self.is_busy:
            return

        def task() -> None:
            self.log_queue.put(("busy", "true"))
            self.log_queue.put(("status", "Installation en cours..."))
            missing = get_missing_tools()
            if not missing:
                self.log_queue.put(("log", "Aucune dépendance manquante."))
            else:
                install_missing_tools(missing, logger=lambda line: self.log_queue.put(("log", line)))
            self.log_queue.put(("status", "Nouvelle vérification..."))
            self.log_queue.put(("refresh", None))
            remaining = get_missing_tools()
            if remaining:
                names = ", ".join(tool.display_name for tool in remaining)
                self.log_queue.put(("log", f"Encore manquant après installation : {names}"))
            else:
                self.log_queue.put(("log", "Toutes les dépendances sont maintenant présentes."))
            self.log_queue.put(("busy", "false"))

        threading.Thread(target=task, daemon=True).start()


class DashboardPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: AzaryxAppProtocol) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.card_labels: dict[str, ttk.Label] = {}
        self._build_widgets()
        self.refresh_dashboard()

    def _build_widgets(self) -> None:
        ttk.Label(self, text="Dashboard SOC", font=("Sans", 22, "bold")).pack(anchor="w")
        ttk.Label(
            self,
            text=(
                "Vue d'accueil pour un poste d'audit autorisé. "
                "Le mode fullscreen/kiosk reste réversible via F11, Ctrl+Q ou le bouton Quitter fullscreen."
            ),
            wraplength=900,
        ).pack(anchor="w", pady=(4, 16))

        cards = ttk.Frame(self)
        cards.pack(fill="x")
        for index, (key, title) in enumerate(
            (
                ("tools", "Outils installés"),
                ("reports", "Rapports générés"),
                ("target", "Dernière cible"),
                ("dependencies", "Statut dépendances"),
            )
        ):
            card = ttk.Frame(cards, padding=14, relief="ridge")
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=8, pady=8)
            cards.columnconfigure(index % 2, weight=1)
            ttk.Label(card, text=title, font=("Sans", 12, "bold")).pack(anchor="w")
            value = ttk.Label(card, text="-", font=("Sans", 18, "bold"), wraplength=360)
            value.pack(anchor="w", pady=(8, 0))
            self.card_labels[key] = value

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=16)
        ttk.Button(actions, text="Actualiser dashboard", command=self.refresh_dashboard).pack(side="left")
        ttk.Button(actions, text="Aller aux Tools", command=lambda: self.app.select_page("tools")).pack(side="left", padx=8)
        ttk.Button(
            actions,
            text="Vérifier dépendances",
            command=lambda: self.app.select_page("dependencies"),
        ).pack(side="left")

    def refresh_dashboard(self) -> None:
        statuses = get_tool_statuses()
        installed = sum(1 for status in statuses if status["installed"])
        missing = len(statuses) - installed
        reports_dir = ensure_reports_dir(Path(str(self.app.get_reports_dir())).expanduser())
        reports_count = len(list(reports_dir.glob("*.txt")))
        last_target = str(self.app.get_last_target()).strip() or "Aucune"
        dependency_text = "OK" if missing == 0 else f"{missing} manquante(s)"
        self.card_labels["tools"].configure(text=f"{installed}/{len(statuses)}")
        self.card_labels["reports"].configure(text=str(reports_count))
        self.card_labels["target"].configure(text=last_target)
        self.card_labels["dependencies"].configure(text=dependency_text)


class ToolsPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: AzaryxAppProtocol) -> None:
        super().__init__(parent, padding=12)
        self.app = app
        self.output_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.current_tool: ToolDefinition | None = None
        self.is_running = False
        self.tool_buttons: list[tuple[ttk.Button, ToolDefinition]] = []
        self._build_widgets()
        self.after(100, self._drain_output)
        self.refresh_tools()

    def _build_widgets(self) -> None:
        target_bar = ttk.Frame(self)
        target_bar.pack(fill="x", pady=(0, 8))
        ttk.Label(target_bar, text="Cible globale:").pack(side="left")
        self.target_var = tk.StringVar(value=self.app.get_last_target())
        ttk.Entry(target_bar, textvariable=self.target_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Label(target_bar, text="Timeout:").pack(side="left")
        self.timeout_var = tk.StringVar(value=str(self.app.get_timeout()))
        ttk.Entry(target_bar, textvariable=self.timeout_var, width=7).pack(side="left", padx=4)
        ttk.Button(target_bar, text="Rafraîchir outils", command=self.refresh_tools).pack(side="left", padx=4)

        self.command_label = ttk.Label(self, text="Commande: -", wraplength=920)
        self.command_label.pack(anchor="w", pady=(0, 8))

        content = ttk.PanedWindow(self, orient="horizontal")
        content.pack(fill="both", expand=True)

        tool_frame = ttk.Frame(content, padding=(0, 0, 8, 0))
        content.add(tool_frame, weight=1)
        self.category_notebook = ttk.Notebook(tool_frame)
        self.category_notebook.pack(fill="both", expand=True)

        terminal_frame = ttk.Frame(content)
        content.add(terminal_frame, weight=2)
        ttk.Label(terminal_frame, text="Sortie terminal").pack(anchor="w")
        self.output_text = tk.Text(terminal_frame, wrap="word", state="disabled", height=22)
        output_scroll = ttk.Scrollbar(terminal_frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=output_scroll.set)
        self.output_text.pack(side="left", fill="both", expand=True)
        output_scroll.pack(side="right", fill="y")

        self.status_label = ttk.Label(self, text="Prêt")
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
                self.command_label.configure(text=f"Commande: {value}")
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
            frame = ttk.Frame(self.category_notebook, padding=8)
            self.category_notebook.add(frame, text=category)
            for tool in (item for item in TOOL_DEFINITIONS if item.category == category):
                if tool.advanced and not show_advanced:
                    continue
                row = ttk.Frame(frame)
                row.pack(fill="x", pady=3)
                installed = tool.binary_path() is not None
                label = tool.label if installed else f"{tool.label} (absent)"
                button = ttk.Button(row, text=label, command=lambda selected=tool: self.launch_tool(selected))
                button.pack(side="left")
                ttk.Label(row, text=tool.description, wraplength=330).pack(side="left", padx=8, fill="x", expand=True)
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
            "Autorisation légale obligatoire",
            (
                f"Confirmez que vous êtes autorisé à lancer {tool.label} sur cette cible.\n\n"
                "Usage permis uniquement pour audits autorisés, CTF, labs internes et machines personnelles."
            ),
        )

    def launch_tool(self, tool: ToolDefinition) -> None:
        if self.is_running:
            return
        if not self._confirm_legal_authorization(tool):
            self.status_label.configure(text="Lancement annulé: autorisation non confirmée.")
            return
        try:
            timeout = validate_timeout(int(self.timeout_var.get().strip()))
            target_value = self.target_var.get().strip()
            self.app.set_timeout(timeout)
            command = tool.build_command(target_value, timeout)
            self.app.set_last_target(target_value)
        except ValueError:
            messagebox.showerror("Timeout invalide", "Le timeout doit être un entier entre 5 et 3600 secondes.")
            return
        except ToolExecutionError as exc:
            messagebox.showerror("Lancement impossible", str(exc))
            return

        command_text = format_command(command)
        self.command_label.configure(text=f"Commande: {command_text}")
        self._clear_output()
        self._append_output(f"$ {command_text}")
        self._append_output("Commande validée: aucune option destructive n'est exposée par l'interface.")

        def task() -> None:
            self.output_queue.put(("running", "true"))
            self.output_queue.put(("status", f"Exécution de {tool.label}..."))
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
            self.output_queue.put(("output", f"Rapport sauvegardé: {report_path}"))
            self.output_queue.put(("status", f"Terminé avec code {return_code}"))
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
                    f"Outil: {tool.label}",
                    f"Catégorie: {tool.category}",
                    f"Début: {started_at.isoformat(timespec='seconds')}",
                    f"Commande: {command_text}",
                    f"Code retour: {return_code}",
                    "",
                    output,
                ]
            ),
            encoding="utf-8",
        )
        return report_path


class ReportsPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: AzaryxAppProtocol) -> None:
        super().__init__(parent, padding=12)
        self.app = app
        self._build_widgets()
        self.refresh_reports()

    def _build_widgets(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Rapports sauvegardés").pack(side="left")
        ttk.Button(top, text="Rafraîchir", command=self.refresh_reports).pack(side="right")

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        body.add(left, weight=1)
        self.reports_list = tk.Listbox(left, height=20)
        list_scroll = ttk.Scrollbar(left, orient="vertical", command=self.reports_list.yview)
        self.reports_list.configure(yscrollcommand=list_scroll.set)
        self.reports_list.pack(side="left", fill="both", expand=True)
        list_scroll.pack(side="right", fill="y")

        right = ttk.Frame(body)
        body.add(right, weight=2)
        self.preview = tk.Text(right, wrap="word", state="disabled")
        preview_scroll = ttk.Scrollbar(right, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=preview_scroll.set)
        self.preview.pack(side="left", fill="both", expand=True)
        preview_scroll.pack(side="right", fill="y")

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Ouvrir", command=self.open_selected_report).pack(side="left")
        ttk.Button(buttons, text="Supprimer", command=self.delete_selected_report).pack(side="left", padx=8)
        ttk.Button(buttons, text="Exporter", command=self.export_selected_report).pack(side="left")
        self.status_label = ttk.Label(buttons, text="Prêt")
        self.status_label.pack(side="left", padx=12)

    def _reports_dir(self) -> Path:
        return ensure_reports_dir(Path(str(self.app.get_reports_dir())).expanduser())

    def _selected_report(self) -> Path | None:
        selection = self.reports_list.curselection()
        if not selection:
            messagebox.showinfo("Aucun rapport", "Sélectionnez un rapport.")
            return None
        return self._reports_dir() / self.reports_list.get(selection[0])

    def refresh_reports(self) -> None:
        self.reports_list.delete(0, "end")
        reports_dir = self._reports_dir()
        for path in sorted(reports_dir.glob("*.txt"), reverse=True):
            self.reports_list.insert("end", path.name)
        self.status_label.configure(text=f"Dossier: {reports_dir}")

    def open_selected_report(self) -> None:
        path = self._selected_report()
        if path is None:
            return
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror("Ouverture impossible", str(exc))
            return
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("end", content)
        self.preview.configure(state="disabled")
        self.status_label.configure(text=f"Ouvert: {path.name}")

    def delete_selected_report(self) -> None:
        path = self._selected_report()
        if path is None:
            return
        if not messagebox.askyesno("Supprimer", f"Supprimer {path.name} ?"):
            return
        try:
            path.unlink()
        except OSError as exc:
            messagebox.showerror("Suppression impossible", str(exc))
            return
        self.refresh_reports()
        self.status_label.configure(text=f"Supprimé: {path.name}")

    def export_selected_report(self) -> None:
        path = self._selected_report()
        if path is None:
            return
        destination = filedialog.asksaveasfilename(
            title="Exporter le rapport",
            initialfile=path.name,
            defaultextension=".txt",
            filetypes=(("Rapports texte", "*.txt"), ("Tous les fichiers", "*.*")),
        )
        if not destination:
            return
        try:
            shutil.copy2(path, destination)
        except OSError as exc:
            messagebox.showerror("Export impossible", str(exc))
            return
        self.status_label.configure(text=f"Exporté vers: {destination}")


class SettingsPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: AzaryxAppProtocol) -> None:
        super().__init__(parent, padding=12)
        self.app = app
        self._build_widgets()

    def _build_widgets(self) -> None:
        ttk.Label(self, text="Paramètres", font=("Sans", 16, "bold")).pack(anchor="w", pady=(0, 12))

        timeout_row = ttk.Frame(self)
        timeout_row.pack(fill="x", pady=4)
        ttk.Label(timeout_row, text="Timeout outils (secondes):", width=32).pack(side="left")
        self.timeout_var = tk.StringVar(value=str(self.app.get_timeout()))
        ttk.Entry(timeout_row, textvariable=self.timeout_var, width=10).pack(side="left")

        reports_row = ttk.Frame(self)
        reports_row.pack(fill="x", pady=4)
        ttk.Label(reports_row, text="Dossier reports:", width=32).pack(side="left")
        self.reports_var = tk.StringVar(value=str(self.app.get_reports_dir()))
        ttk.Entry(reports_row, textvariable=self.reports_var).pack(side="left", fill="x", expand=True)
        ttk.Button(reports_row, text="Parcourir", command=self.choose_reports_dir).pack(side="left", padx=6)

        self.dark_var = tk.BooleanVar(value=self.app.dark_mode_enabled())
        self.advanced_var = tk.BooleanVar(value=self.app.show_advanced_tools())
        self.legal_var = tk.BooleanVar(value=self.app.requires_legal_authorization())
        self.fullscreen_var = tk.BooleanVar(value=self.app.starts_fullscreen())
        ttk.Checkbutton(self, text="Mode sombre", variable=self.dark_var).pack(anchor="w", pady=4)
        ttk.Checkbutton(
            self,
            text="Afficher les outils offensifs avancés",
            variable=self.advanced_var,
        ).pack(anchor="w", pady=4)
        ttk.Checkbutton(
            self,
            text="Autorisation légale obligatoire avant lancement d'un outil",
            variable=self.legal_var,
        ).pack(anchor="w", pady=4)
        ttk.Checkbutton(
            self,
            text="Démarrer en fullscreen (mode OS/Kiosk réversible)",
            variable=self.fullscreen_var,
        ).pack(anchor="w", pady=4)

        ttk.Button(self, text="Enregistrer", command=self.save).pack(anchor="w", pady=12)
        self.status_label = ttk.Label(self, text="Les paramètres sont sauvegardés dans ~/.config/azaryx-tools/settings.ini")
        self.status_label.pack(anchor="w")

    def choose_reports_dir(self) -> None:
        selected = filedialog.askdirectory(title="Choisir le dossier reports")
        if selected:
            self.reports_var.set(selected)

    def save(self) -> None:
        try:
            timeout = validate_timeout(int(self.timeout_var.get().strip()))
        except (ValueError, ToolExecutionError):
            messagebox.showerror("Timeout invalide", "Le timeout doit être un entier entre 5 et 3600 secondes.")
            return
        reports_dir = Path(self.reports_var.get()).expanduser()
        try:
            ensure_reports_dir(reports_dir)
        except OSError as exc:
            messagebox.showerror("Dossier invalide", str(exc))
            return
        self.app.update_settings(
            timeout=timeout,
            reports_dir=str(reports_dir),
            dark_mode=self.dark_var.get(),
            show_advanced=self.advanced_var.get(),
            require_legal_authorization=self.legal_var.get(),
            start_fullscreen=self.fullscreen_var.get(),
        )
        self.status_label.configure(text="Paramètres enregistrés.")


class AzaryxAppProtocol(Protocol):
    def get_timeout(self) -> int: ...
    def set_timeout(self, timeout: int) -> None: ...
    def get_reports_dir(self) -> str: ...
    def dark_mode_enabled(self) -> bool: ...
    def show_advanced_tools(self) -> bool: ...
    def requires_legal_authorization(self) -> bool: ...
    def starts_fullscreen(self) -> bool: ...
    def get_last_target(self) -> str: ...
    def set_last_target(self, target: str) -> None: ...
    def focus_global_target(self) -> None: ...
    def select_page(self, page_key: str) -> None: ...
    def refresh_reports(self) -> None: ...
    def update_settings(self, **kwargs: object) -> None: ...


class AzaryxApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        self.fullscreen_enabled = False
        self.title(APP_NAME)
        self.geometry("1120x760")
        self.minsize(980, 650)
        icon_path = Path(__file__).resolve().parent / "assets" / "icon.png"
        if icon_path.exists():
            try:
                self.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
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
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True)

        self.sidebar = ttk.Frame(root, padding=10, width=190)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ttk.Label(self.sidebar, text="Azaryx", font=("Sans", 18, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(self.sidebar, text="OS/Kiosk ready", font=("Sans", 9)).pack(anchor="w", pady=(0, 12))

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(side="right", fill="both", expand=True)

        self.dashboard_page = DashboardPage(self.notebook, self)
        self.dependency_page = DependencyPage(self.notebook)
        self.tools_page = ToolsPage(self.notebook, self)
        self.reports_page = ReportsPage(self.notebook, self)
        self.settings_page = SettingsPage(self.notebook, self)

        self.pages = {
            "dashboard": (self.dashboard_page, "Dashboard"),
            "dependencies": (self.dependency_page, "Dépendances"),
            "tools": (self.tools_page, "Tools"),
            "reports": (self.reports_page, "Reports"),
            "settings": (self.settings_page, "Settings"),
        }
        for page, title in self.pages.values():
            self.notebook.add(page, text=title)

        for key, (_, title) in self.pages.items():
            ttk.Button(self.sidebar, text=title, command=lambda page_key=key: self.select_page(page_key)).pack(
                fill="x", pady=3
            )
        ttk.Separator(self.sidebar).pack(fill="x", pady=10)
        self.fullscreen_button = ttk.Button(self.sidebar, text="Activer fullscreen", command=self.toggle_fullscreen)
        self.fullscreen_button.pack(fill="x", pady=3)
        ttk.Button(
            self.sidebar,
            text="Quitter fullscreen",
            command=lambda: self.set_fullscreen(False),
        ).pack(fill="x", pady=3)
        ttk.Button(self.sidebar, text="Quitter (Ctrl+Q)", command=self.safe_quit).pack(fill="x", pady=(14, 3))
        ttk.Label(
            self.sidebar,
            text="F11 fullscreen\nCtrl+L cible\nCtrl+Q quitter",
            wraplength=160,
        ).pack(anchor="w", side="bottom", pady=8)

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
        self.fullscreen_button.configure(text="Désactiver fullscreen" if enabled else "Activer fullscreen")

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
        dark = self.dark_mode_enabled()
        bg = "#1f2329" if dark else "#f0f0f0"
        fg = "#f2f2f2" if dark else "#111111"
        field_bg = "#111418" if dark else "#ffffff"
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.configure("TNotebook", background=bg)
        style.configure("TNotebook.Tab", background=bg, foreground=fg)
        style.configure("Treeview", background=field_bg, foreground=fg, fieldbackground=field_bg)
        self.configure(background=bg)
        self._apply_text_theme(self, field_bg, fg)

    def _apply_text_theme(self, widget: tk.Misc, bg: str, fg: str) -> None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Text):
                child.configure(background=bg, foreground=fg, insertbackground=fg)
            elif isinstance(child, tk.Listbox):
                child.configure(background=bg, foreground=fg)
            self._apply_text_theme(child, bg, fg)


def main() -> None:
    app = AzaryxApp()
    app.mainloop()


if __name__ == "__main__":
    main()
