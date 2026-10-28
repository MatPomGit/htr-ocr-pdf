#!/usr/bin/env python3
"""Cross-platform, stdlib-only dependency bootstrap for HTR OCR PDF.

No shell piping of downloaded installers, no silent elevation, no remote model
API, and no Ollama/model download without an explicit user confirmation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
VENV = ROOT / ".venv"
MODEL = "qwen3-vl:4b"
OLLAMA_URL = "http://127.0.0.1:11434/api/tags"
MIN_PYTHON = (3, 10)


class SetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class Host:
    system: str
    manager: str | None
    distribution: str = ""


def detect_host(system: str | None = None, available=None,
                os_release: str | None = None) -> Host:
    name = (system or platform.system()).lower()
    which = available or shutil.which
    if name == "windows":
        return Host("windows", "winget" if which("winget") else None)
    if name == "darwin":
        return Host("macos", "brew" if which("brew") else None)
    if name != "linux":
        return Host(name, None)
    if os_release is None:
        try:
            os_release = Path("/etc/os-release").read_text(encoding="utf-8")
        except OSError:
            os_release = ""
    data = {}
    for line in os_release.splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            data[k] = v.strip().strip('"').lower()
    distro = data.get("id", "")
    family = (distro + " " + data.get("id_like", "")).split()
    preferred = (
        ("dnf", ("fedora", "rhel", "centos")),
        ("apt-get", ("debian", "ubuntu", "linuxmint", "pop")),
        ("pacman", ("arch", "manjaro", "endeavouros")),
        ("zypper", ("opensuse", "suse")),
        ("apk", ("alpine",)),
    )
    for manager, members in preferred:
        if any(f in members for f in family) and which(manager):
            return Host("linux", manager, distro)
    for manager in ("dnf", "apt-get", "pacman", "zypper", "apk"):
        if which(manager):
            return Host("linux", manager, distro)
    return Host("linux", None, distro)


def features_for_args(args: list[str]) -> tuple[bool, bool]:
    """Return needs_GUI, needs_HTR. Compression-only should not fetch models."""
    if "--compress-only" in args:
        return False, False
    if not args:
        return True, True  # Offer setup on first GUI launch, with consent.
    if "--help" in args or "-h" in args:
        return False, False
    return False, True


def package_names(host: Host, missing: set[str],
                  version: tuple[int, int] | None = None) -> list[str]:
    version = version or sys.version_info[:2]
    base = {
        "dnf": {"tk": "python3-tkinter", "font": "dejavu-sans-fonts",
                "venv": "python3-pip"},
        "apt-get": {"tk": "python3-tk", "font": "fonts-dejavu-core",
                    "venv": "python3-venv"},
        "pacman": {"tk": "tk", "font": "ttf-dejavu", "venv": "python-pip"},
        "zypper": {"tk": "python3-tk", "font": "dejavu-fonts",
                   "venv": "python3-pip"},
        "apk": {"tk": "py3-tkinter", "font": "ttf-dejavu", "venv": "py3-pip"},
        "brew": {"tk": f"python-tk@{version[0]}.{version[1]}"},
    }.get(host.manager or "", {})
    return sorted({base[k] for k in missing if k in base})


def package_command(host: Host, packages: list[str]) -> list[str] | None:
    if not packages or not host.manager:
        return None
    prefix = {
        "dnf": ["dnf", "install", "-y"],
        "apt-get": ["apt-get", "install", "-y"],
        "pacman": ["pacman", "-S", "--needed", "--noconfirm"],
        "zypper": ["zypper", "--non-interactive", "install"],
        "apk": ["apk", "add"],
        "brew": ["brew", "install"],
    }.get(host.manager)
    if prefix is None:
        return None
    cmd = prefix + packages
    if host.system == "linux" and getattr(os, "geteuid", lambda: 1)() != 0:
        if not shutil.which("sudo"):
            return None
        return ["sudo"] + cmd
    return cmd


def ollama_install_command(host: Host) -> list[str] | None:
    if host.system == "windows" and host.manager == "winget":
        return ["winget", "install", "--id", "Ollama.Ollama", "--exact",
                "--accept-package-agreements", "--accept-source-agreements"]
    if host.manager == "brew":
        return ["brew", "install", "ollama"]
    if host.system == "linux" and host.manager in {"dnf", "pacman", "zypper", "apk"}:
        return package_command(host, ["ollama"])
    # On Debian/Ubuntu a trusted repository package is not guaranteed.
    # Do not execute downloaded shell scripts or silently add APT sources.
    return None


def confirm(description: str, cmd: list[str], assume_yes: bool) -> bool:
    print(f"\n{description}\nPolecenie: {shutil.join_cmdline(cmd) if hasattr(shutil, 'join_cmdline') else subprocess.list2cmdline(cmd)}", flush=True)
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print("Brak terminala do potwierdzenia. Użyj --yes tylko przy świadomie zatwierdzonej instalacji.")
        return False
    try:
        return input("Wykonać operację? [t/N]: ").strip().lower() in {"t", "tak", "y", "yes"}
    except EOFError:
        return False


def run_install(cmd: list[str], description: str, assume_yes: bool) -> bool:
    if not confirm(description, cmd, assume_yes):
        return False
    try:
        subprocess.run(cmd, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SetupError(f"Nie udało się wykonać polecenia {cmd[0]}: {exc}") from exc
    return True


def font_available(system: str) -> bool:
    locations = {
        "windows": [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
                    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"],
        "macos": [Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
                  Path("/Library/Fonts/Arial.ttf"),
                  Path.home() / "Library/Fonts/DejaVuSans.ttf"],
        "linux": [Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
                  Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")],
    }
    return any(p.is_file() for p in locations.get(system, []))


def python_tk_available() -> bool:
    return importlib.util.find_spec("tkinter") is not None


def install_system_features(host: Host, missing: set[str],
                            assume_yes: bool, no_system: bool) -> None:
    if not missing:
        return
    if no_system:
        print(f"Pomijam pakiety systemowe (--no-system): {', '.join(sorted(missing))}")
        return
    packages = package_names(host, missing)
    cmd = package_command(host, packages)
    if cmd is None:
        print(f"Nie można automatycznie doinstalować: {', '.join(sorted(missing))}.")
        print("Zainstaluj brakujące składniki odpowiednim instalatorem systemu i uruchom ponownie.")
        return
    run_install(cmd, "Brakujące komponenty systemowe: " + ", ".join(sorted(missing)),
                assume_yes)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def verify_venv(host: Host, assume_yes: bool, no_system: bool) -> None:
    target = venv_python()

    def ready() -> bool:
        if not target.is_file():
            return False
        check = subprocess.run([str(target), "-m", "pip", "--version"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=False)
        return check.returncode == 0

    if ready():
        return
    creation = [sys.executable, "-m", "venv", str(VENV)]
    try:
        subprocess.run(creation, check=True)
    except (OSError, subprocess.CalledProcessError):
        install_system_features(host, {"venv"}, assume_yes, no_system)
        try:
            subprocess.run(creation, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SetupError("Nie udało się utworzyć .venv; sprawdź pakiety python3-venv i pip.") from exc
    if not ready():
        raise SetupError("Środowisko .venv nie ma sprawnego pip. Sprawdź pakiety python3-venv / python3-pip.")



def requirements_digest() -> str:
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def install_python_deps(host: Host, assume_yes: bool, no_system: bool) -> None:
    verify_venv(host, assume_yes, no_system)
    target = venv_python()
    marker = VENV / ".requirements_sha256"
    digest = requirements_digest()
    if marker.is_file() and marker.read_text(encoding="ascii").strip() == digest:
        check = subprocess.run([str(target), "-c", "import pymupdf; import PIL"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=False)
        if check.returncode == 0:
            return
    print("Instaluję lub naprawiam zależności Python w lokalnym .venv…", flush=True)
    subprocess.run([str(target), "-m", "pip", "install", "-r", str(REQUIREMENTS)], check=True)
    marker.write_text(digest, encoding="ascii")


def ollama_cli() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    # GUI installers on Windows and Homebrew can update PATH only for new shells.
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe",
        Path("/opt/homebrew/bin/ollama"),
        Path("/usr/local/bin/ollama"),
    ]
    return next((str(p) for p in candidates if p.is_file()), None)


def model_installed(model: str = MODEL) -> bool | None:
    try:
        with urlopen(OLLAMA_URL, timeout=2) as response:
            data = json.load(response)
    except (OSError, URLError, ValueError):
        return None
    tags = {entry.get("name") for entry in data.get("models", [])}
    return model in tags or (model + ":latest" in tags if ":" not in model else False)


def ensure_ollama(host: Host, assume_yes: bool, no_system: bool,
                  model: str = MODEL) -> None:
    cli = ollama_cli()
    if not cli:
        cmd = None if no_system else ollama_install_command(host)
        if not cmd:
            print("Ollama nie jest zainstalowana. Instrukcje: https://ollama.com/download")
            return
        if not run_install(cmd, "Instalacja lokalnej Ollama", assume_yes):
            return
        cli = ollama_cli()
        if not cli:
            print("Uruchom ponownie terminal po instalacji Ollama, aby odświeżyć PATH.")
            return

    installed = model_installed(model)
    if installed is None:
        # Starting a user-level server is non-privileged and does not install software.
        print("Uruchamiam lokalny serwer Ollama…")
        try:
            flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                     if os.name == "nt" else 0)
            subprocess.Popen([cli, "serve"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                             creationflags=flags, start_new_session=(os.name != "nt"))
        except OSError as exc:
            print(f"Nie można uruchomić Ollama: {exc}")
            return
        for _ in range(20):
            time.sleep(0.5)
            installed = model_installed(model)
            if installed is not None:
                break
        if installed is None:
            print("Ollama nie odpowiada na localhost:11434. Sprawdź konfigurację usługi.")
            return

    if installed:
        print(f"Model {model} jest już dostępny.")
        return
    cmd = [cli, "pull", model]
    run_install(cmd, f"Pobranie lokalnego modelu {model} (kilka GB danych)", assume_yes)


def doctor(host: Host) -> None:
    print(json.dumps({
        "system": host.system,
        "distribution": host.distribution,
        "package_manager": host.manager,
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "venv_exists": venv_python().is_file(),
        "tkinter_importable": python_tk_available(),
        "unicode_font_available": font_available(host.system),
        "ollama_executable": bool(ollama_cli()),
        "ollama_model_present": model_installed(),
    }, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Lokalny instalator zależności (bez pobierania zewnętrznych skryptów).")
    parser.add_argument("--setup", action="store_true", help="Sprawdź i skonfiguruj pełne środowisko, w tym Ollama")
    parser.add_argument("--doctor", action="store_true", help="Pokaż diagnostykę bez instalowania czegokolwiek")
    parser.add_argument("--yes", action="store_true", help="Potwierdź operacje instalacji pakietów i modelu")
    parser.add_argument("--no-system", action="store_true", help="Nie instaluj pakietów systemowych")
    parser.add_argument("--no-ollama", action="store_true", help="Nie instaluj Ollama ani modelu")
    parser.add_argument("--bootstrap-help", action="store_true", help="Pokaż pomoc instalatora")
    opts, app_args = parser.parse_known_args(argv)
    if opts.bootstrap_help:
        parser.print_help()
        return 0
    if sys.version_info < MIN_PYTHON:
        raise SetupError(f"Wymagany Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}. "
                         f"Aktualny: {sys.version.split()[0]}.")
    host = detect_host()
    if opts.doctor:
        doctor(host)
        return 0

    gui, htr = features_for_args(app_args)
    if opts.setup:
        gui, htr = True, True
    missing = set()
    if gui and not python_tk_available():
        missing.add("tk")
    if (gui or htr) and not font_available(host.system):
        missing.add("font")
    install_system_features(host, missing, opts.yes, opts.no_system)
    if gui and not python_tk_available():
        raise SetupError("Tkinter nie jest dostępny dla bieżącego interpretera Python. "
                         "Sprawdź wskazówki dla systemu w docs/installation.md.")
    install_python_deps(host, opts.yes, opts.no_system)

    if htr and not opts.no_ollama:
        ensure_ollama(host, opts.yes, opts.no_system)
    if opts.setup:
        print("Przygotowanie zakończone. Uruchom run.sh (Linux/macOS) lub run.cmd (Windows).")
        return 0
    command = [str(venv_python()), str(ROOT / "htr_compare.py"), *app_args]
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SetupError, OSError, subprocess.CalledProcessError) as error:
        print(f"Błąd instalatora: {error}", file=sys.stderr)
        raise SystemExit(2)
