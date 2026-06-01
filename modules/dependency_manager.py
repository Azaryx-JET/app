"""Dependency discovery and installation helpers for Azaryx Offensive Tools.

The functions in this module deliberately avoid ``shell=True`` and execute only
allow-listed package-manager commands built as subprocess argument lists.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
from typing import Callable, Iterable

LogCallback = Callable[[str], None]

APT_INSTALL_TIMEOUT_SECONDS = 900
APT_UPDATE_TIMEOUT_SECONDS = 600
CHECK_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class ToolSpec:
    """Description of an external audit tool required by the application."""

    command: str
    package: str
    aliases: tuple[str, ...] = ()
    label: str | None = None

    @property
    def display_name(self) -> str:
        return self.label or self.command

    @property
    def candidates(self) -> tuple[str, ...]:
        return (self.command, *self.aliases)


APT_TOOL_MAP: dict[str, ToolSpec] = {
    "nmap": ToolSpec("nmap", "nmap"),
    "whois": ToolSpec("whois", "whois"),
    "dig": ToolSpec("dig", "dnsutils"),
    "curl": ToolSpec("curl", "curl"),
    "whatweb": ToolSpec("whatweb", "whatweb"),
    "nikto": ToolSpec("nikto", "nikto"),
    "gobuster": ToolSpec("gobuster", "gobuster"),
    "sqlmap": ToolSpec("sqlmap", "sqlmap"),
    "hydra": ToolSpec("hydra", "hydra"),
    "wfuzz": ToolSpec("wfuzz", "wfuzz"),
    "enum4linux": ToolSpec("enum4linux", "enum4linux"),
    "smbclient": ToolSpec("smbclient", "smbclient"),
    "netcat": ToolSpec("netcat", "netcat-openbsd", aliases=("nc",)),
    "tcpdump": ToolSpec("tcpdump", "tcpdump"),
    "wireshark": ToolSpec("wireshark", "wireshark"),
    "traceroute": ToolSpec("traceroute", "traceroute"),
    "ip": ToolSpec("ip", "iproute2", label="iproute2"),
    "dnsrecon": ToolSpec("dnsrecon", "dnsrecon"),
    "feroxbuster": ToolSpec("feroxbuster", "feroxbuster"),
    "ffuf": ToolSpec("ffuf", "ffuf"),
    "amass": ToolSpec("amass", "amass"),
    "subfinder": ToolSpec("subfinder", "subfinder"),
    "nuclei": ToolSpec("nuclei", "nuclei"),
    "testssl.sh": ToolSpec("testssl.sh", "testssl.sh", aliases=("testssl",)),
    "zaproxy": ToolSpec("zaproxy", "zaproxy", aliases=("zap",)),
    "gvm": ToolSpec("gvm", "gvm", aliases=("openvas",), label="openvas / gvm"),
}


def _log(logger: LogCallback | None, message: str) -> None:
    if logger:
        logger(message)


def check_command_exists(command: str) -> str | None:
    """Return the binary path for *command* if it exists in PATH, else None."""

    if not command or any(separator in command for separator in ("/", "\\", "\x00")):
        return None
    path = shutil.which(command)
    if not path:
        return None

    try:
        # A tiny non-destructive command confirms that the binary can at least be
        # executed. Some tools return non-zero for --version, so timeout and OS
        # errors are the only hard failures here.
        subprocess.run(
            [path, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=CHECK_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return path
    return path


def detect_package_manager() -> str | None:
    """Detect the supported package manager, currently apt/apt-get only."""

    if shutil.which("apt-get"):
        return "apt"
    if shutil.which("apt"):
        return "apt"
    return None


def get_tool_statuses() -> list[dict[str, str | bool]]:
    """Return table-ready status dictionaries for every known tool."""

    statuses: list[dict[str, str | bool]] = []
    for spec in APT_TOOL_MAP.values():
        found_path = None
        found_command = None
        for candidate in spec.candidates:
            found_path = check_command_exists(candidate)
            if found_path:
                found_command = candidate
                break
        statuses.append(
            {
                "tool": spec.display_name,
                "command": spec.command,
                "package": spec.package,
                "installed": bool(found_path),
                "path": found_path or "",
                "found_command": found_command or "",
            }
        )
    return statuses


def get_missing_tools() -> list[ToolSpec]:
    """Return all configured tools whose binary is missing from PATH."""

    missing: list[ToolSpec] = []
    for spec in APT_TOOL_MAP.values():
        if not any(check_command_exists(candidate) for candidate in spec.candidates):
            missing.append(spec)
    return missing


def _privilege_prefix() -> list[str]:
    if os.geteuid() == 0:
        return []
    if shutil.which("pkexec"):
        return ["pkexec"]
    if shutil.which("sudo"):
        return ["sudo"]
    raise RuntimeError("Aucun mécanisme d'élévation trouvé (pkexec ou sudo requis).")


def _apt_binary() -> str:
    apt_get = shutil.which("apt-get")
    if apt_get:
        return apt_get
    apt = shutil.which("apt")
    if apt:
        return apt
    raise RuntimeError("apt/apt-get introuvable : seules les distributions Debian/Kali/Ubuntu sont prises en charge.")


def _run_command(command: list[str], logger: LogCallback | None, timeout: int) -> int:
    _log(logger, f"$ {' '.join(command)}")
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.stdout:
            for line in completed.stdout.splitlines():
                _log(logger, line)
        return completed.returncode
    except subprocess.TimeoutExpired as exc:
        if exc.stdout:
            output = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout
            for line in output.splitlines():
                _log(logger, line)
        _log(logger, f"Timeout après {timeout} secondes.")
        return 124
    except FileNotFoundError as exc:
        _log(logger, f"Commande introuvable : {exc}")
        return 127
    except OSError as exc:
        _log(logger, f"Erreur d'exécution : {exc}")
        return 1


def _unique_packages(tools: Iterable[ToolSpec]) -> list[str]:
    packages: list[str] = []
    for tool in tools:
        if tool.package not in packages:
            packages.append(tool.package)
    return packages


def install_missing_tools(
    tools: Iterable[ToolSpec] | None = None,
    logger: LogCallback | None = None,
) -> dict[str, object]:
    """Install missing tools with apt and return a readable result summary.

    Installation is intentionally attempted package-by-package so an unavailable
    package does not abort the complete dependency repair process.
    """

    if detect_package_manager() != "apt":
        message = "Gestionnaire de paquets non pris en charge : apt est requis."
        _log(logger, message)
        return {"ok": False, "installed": [], "failed": [], "message": message}

    selected_tools = list(tools) if tools is not None else get_missing_tools()
    packages = _unique_packages(selected_tools)
    if not packages:
        message = "Aucune dépendance manquante à installer."
        _log(logger, message)
        return {"ok": True, "installed": [], "failed": [], "message": message}

    try:
        prefix = _privilege_prefix()
        apt_binary = _apt_binary()
    except RuntimeError as exc:
        _log(logger, str(exc))
        return {"ok": False, "installed": [], "failed": packages, "message": str(exc)}

    env_options = ["-o", "Dpkg::Options::=--force-confnew"]
    update_command = [*prefix, apt_binary, "update"]
    update_code = _run_command(update_command, logger, APT_UPDATE_TIMEOUT_SECONDS)
    if update_code != 0:
        _log(logger, f"apt update a retourné {update_code}; tentative d'installation malgré tout.")

    installed: list[str] = []
    failed: list[str] = []
    for package in packages:
        command = [*prefix, apt_binary, "install", "-y", *env_options, package]
        code = _run_command(command, logger, APT_INSTALL_TIMEOUT_SECONDS)
        if code == 0:
            installed.append(package)
            _log(logger, f"OK: paquet installé ou déjà présent: {package}")
        else:
            failed.append(package)
            _log(logger, f"AVERTISSEMENT: impossible d'installer {package} (code {code}).")

    ok = not failed
    message = "Installation terminée." if ok else "Installation terminée avec des erreurs non bloquantes."
    _log(logger, message)
    return {"ok": ok, "installed": installed, "failed": failed, "message": message}
