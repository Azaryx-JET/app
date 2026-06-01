"""Safe tool launch definitions for GRAAL-ATACK.

Only allow-listed, non-destructive reconnaissance commands are exposed here. All
commands are returned as argument lists for ``subprocess``; this module never
uses shell command strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from modules.dependency_manager import check_command_exists

TARGET_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{0,252}$")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
CONTROL_CHARS = set("\r\n\t\x00")


@dataclass(frozen=True)
class ToolDefinition:
    key: str
    label: str
    category: str
    command: str
    package: str
    description: str
    target_mode: str = "host"  # host, url, smb, none
    advanced: bool = False
    extra_args: tuple[str, ...] = ()

    def binary_path(self) -> str | None:
        return check_command_exists(self.command)

    def build_command(self, raw_target: str, timeout: int) -> list[str]:
        binary = self.binary_path()
        if not binary:
            raise ToolExecutionError(f"Outil absent: {self.command}. Installez le paquet {self.package}.")

        target = normalize_target(raw_target, self.target_mode)
        if self.key == "curl_headers":
            return [binary, "-I", "--max-time", str(min(timeout, 300)), target]
        if self.key == "smbclient_list":
            return [binary, "-L", f"//{target}", "-N", "-g"]
        if self.key == "wireshark":
            return [binary]
        if self.key == "tcpdump_list":
            return [binary, "-D"]
        if self.target_mode == "none":
            return [binary, *self.extra_args]
        return [binary, *self.extra_args, target]


class ToolExecutionError(RuntimeError):
    """Raised for invalid targets, missing tools, or blocked commands."""


TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition("nmap_safe", "Nmap découverte services", "Network", "nmap", "nmap", "Scan TCP non destructif avec détection de version.", "host", False, ("-Pn", "-sV", "--top-ports", "100")),
    ToolDefinition("traceroute", "Traceroute", "Network", "traceroute", "traceroute", "Trace le chemin réseau vers la cible."),
    ToolDefinition("ip_addr", "IP addr", "Network", "ip", "iproute2", "Affiche les interfaces locales.", "none", False, ("addr", "show")),
    ToolDefinition("dig", "Dig", "DNS", "dig", "dnsutils", "Résolution DNS standard."),
    ToolDefinition("dnsrecon", "DNSRecon standard", "DNS", "dnsrecon", "dnsrecon", "Énumération DNS standard.", "host", True, ("-d",)),
    ToolDefinition("whois", "Whois", "OSINT", "whois", "whois", "Recherche WHOIS de la cible."),
    ToolDefinition("amass", "Amass passive", "OSINT", "amass", "amass", "Énumération passive uniquement.", "host", True, ("enum", "-passive", "-d")),
    ToolDefinition("subfinder", "Subfinder passive", "OSINT", "subfinder", "subfinder", "Énumération passive de sous-domaines.", "host", True, ("-silent", "-d")),
    ToolDefinition("curl_headers", "Curl headers", "Web", "curl", "curl", "Récupère uniquement les en-têtes HTTP.", "url"),
    ToolDefinition("whatweb", "WhatWeb", "Web", "whatweb", "whatweb", "Fingerprint web non destructif.", "url"),
    ToolDefinition("testssl", "testssl.sh", "Web", "testssl.sh", "testssl.sh", "Audit TLS non destructif.", "url", True, ("--fast",)),
    ToolDefinition("nikto", "Nikto basique", "Web", "nikto", "nikto", "Scan web basique; utilisez seulement sur périmètre autorisé.", "url", True, ("-nointeractive", "-h")),
    ToolDefinition("nuclei", "Nuclei safe templates", "Web", "nuclei", "nuclei", "Templates nuclei de sévérité faible/information.", "url", True, ("-severity", "info,low", "-u")),
    ToolDefinition("smbclient_list", "SMB list", "SMB", "smbclient", "smbclient", "Liste les partages SMB anonymes si autorisé.", "smb"),
    ToolDefinition("enum4linux", "Enum4linux basique", "SMB", "enum4linux", "enum4linux", "Énumération SMB basique.", "host", True, ("-a",)),
    ToolDefinition("tcpdump_list", "Tcpdump interfaces", "Wireless", "tcpdump", "tcpdump", "Liste les interfaces capturables, sans capture active.", "none"),
    ToolDefinition("wireshark", "Wireshark", "Wireless", "wireshark", "wireshark", "Ouvre Wireshark sans lancer de capture automatique.", "none"),
)

CATEGORIES: tuple[str, ...] = ("Network", "DNS", "Web", "SMB", "Wireless", "OSINT")


def validate_timeout(timeout: int) -> int:
    if timeout < 5 or timeout > 3600:
        raise ToolExecutionError("Le timeout doit être compris entre 5 et 3600 secondes.")
    return timeout


def _strip_url_to_host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}")
    host = parsed.hostname or target
    return host.strip("[]")


def _is_valid_host_or_network(value: str) -> bool:
    try:
        if "/" in value:
            ip_network(value, strict=False)
        else:
            ip_address(value)
        return True
    except ValueError:
        pass
    return bool(HOST_PATTERN.fullmatch(value)) and ".." not in value and not value.endswith(".")


def normalize_target(raw_target: str, mode: str) -> str:
    if mode == "none":
        return ""

    target = raw_target.strip()
    if not target:
        raise ToolExecutionError("Renseignez une cible avant de lancer cet outil.")
    if target.startswith("-"):
        raise ToolExecutionError("La cible ne doit pas commencer par un tiret.")
    if any(char in target for char in CONTROL_CHARS) or " " in target:
        raise ToolExecutionError("La cible ne doit pas contenir d'espaces ou caractères de contrôle.")
    if not TARGET_PATTERN.fullmatch(target):
        raise ToolExecutionError("Format de cible invalide.")

    if mode == "url":
        parsed = urlparse(target)
        if not parsed.scheme:
            target = f"https://{target}"
            parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ToolExecutionError("La cible web doit être une URL http(s) valide.")
        if not _is_valid_host_or_network(parsed.hostname):
            raise ToolExecutionError("Hôte de l'URL invalide.")
        return target

    host = _strip_url_to_host(target)
    if not _is_valid_host_or_network(host):
        raise ToolExecutionError("La cible doit être un domaine, une IP ou un réseau CIDR valide.")
    return host


def format_command(command: list[str]) -> str:
    return " ".join(command)


def ensure_reports_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_command(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    validate_timeout(timeout)
    if not command:
        raise ToolExecutionError("Commande vide bloquée.")
    if shutil.which(Path(command[0]).name) is None and not Path(command[0]).exists():
        raise ToolExecutionError(f"Binaire introuvable: {command[0]}")
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )
