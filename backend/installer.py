"""Self-installer: set Maestro up in a dedicated, self-contained folder.

When Maestro is installed from PyPI (``pip install maestro-automation``), the
``maestro`` command lives in Python's ``Scripts`` folder and shares that Python
environment. Running ``maestro setup`` (or ``maestro-setup``) instead provisions
a **dedicated folder** with its own virtual environment, installs Maestro into
it, and drops a one-click launcher — so the app, its dependencies and all its
runtime data live together in one place that's easy to back up or remove.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _prompt(question: str, default: str) -> str:
    try:
        answer = input(f"{question} [{default}]: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def run_setup() -> None:
    from backend import __version__

    print()
    print("=" * 56)
    print(f"  MAESTRO setup  -  install v{__version__} into a folder")
    print("=" * 56)
    print(
        "\nThis creates a self-contained Maestro install (its own virtual\n"
        "environment + data folder + launcher). Nothing else is touched.\n"
    )

    default_dir = str(Path.home() / "Maestro")
    dest = Path(_prompt("Install folder", default_dir)).expanduser()
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.exit(f"Could not create {dest}: {exc}")

    venv_dir = dest / "venv"
    py = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    if not py.exists():
        print(f"\nCreating virtual environment in {venv_dir} …")
        try:
            subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
        except subprocess.CalledProcessError as exc:
            sys.exit(f"venv creation failed: {exc}")

    print(f"Installing maestro-automation=={__version__} (this may take a minute) …")
    try:
        subprocess.check_call(
            [str(py), "-m", "pip", "install", "--upgrade",
             f"maestro-automation=={__version__}"]
        )
    except subprocess.CalledProcessError:
        # Fall back to whatever the latest published version is.
        print("Exact version not found on PyPI — installing the latest instead…")
        subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "maestro-automation"])

    # Launcher: runs the installed maestro with data kept inside this folder.
    if os.name == "nt":
        launcher = dest / "Maestro.cmd"
        launcher.write_text(
            "@echo off\r\n"
            f'set "MAESTRO_DATA_DIR={dest}"\r\n'
            f'"{py}" -m backend.cli %*\r\n',
            encoding="utf-8",
        )
    else:
        launcher = dest / "maestro.sh"
        launcher.write_text(
            "#!/bin/sh\n"
            f'export MAESTRO_DATA_DIR="{dest}"\n'
            f'"{py}" -m backend.cli "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)

    print()
    print("=" * 56)
    print(f"  Installed to: {dest}")
    print(f"  Launch with : {launcher}")
    print(f"  Data folder : {dest / 'data'}")
    print("=" * 56)
    print("\nDouble-click the launcher (or run it) to start Maestro.\n")


if __name__ == "__main__":
    run_setup()
