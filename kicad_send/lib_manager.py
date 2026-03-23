"""Shared library management for KiCad symbols and footprints."""

import os
import shutil
import zipfile
from pathlib import Path
from typing import Optional


KIcadLibType = str  # Literal["symbol", "footprint"]


def get_symbol_dir(path_root: str) -> Optional[str]:
    """Find the symbol directory by searching for sym-lib-table."""
    if not path_root or not os.path.isdir(path_root):
        return None

    files = os.listdir(path_root)
    if "sym-lib-table" in files or "fp-lib-table" in files:
        return path_root

    # Search in subdirectories
    for item in os.listdir(path_root):
        item_path = os.path.join(path_root, item)
        if os.path.isdir(item_path):
            files = os.listdir(item_path)
            if "sym-lib-table" in files:
                return item_path

    return path_root


def get_footprint_dir(path_root: str) -> Optional[str]:
    """Find the footprint directory by searching for fp-lib-table."""
    if not path_root or not os.path.isdir(path_root):
        return None

    files = os.listdir(path_root)
    if "sym-lib-table" in files or "fp-lib-table" in files:
        return path_root

    for item in os.listdir(path_root):
        item_path = os.path.join(path_root, item)
        if os.path.isdir(item_path):
            files = os.listdir(item_path)
            if "fp-lib-table" in files:
                return item_path

    return path_root


def get_lib_name(suffix: str = "") -> str:
    """Get library name with optional suffix."""
    return f"Uploaded{suffix}" if suffix else "Uploaded"


def get_unique_filename(directory: str, filename: str) -> str:
    """Get a unique filename by appending a number if it exists."""
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(filename)
    counter = 2
    while True:
        new_name = f"{base}_{counter}{ext}"
        path = os.path.join(directory, new_name)
        if not os.path.exists(path):
            return path
        counter += 1


def ensure_footprint_lib(path_root: str, suffix: str = "") -> Optional[str]:
    """Ensure footprint library exists and is registered in fp-lib-table."""
    footprint_dir = get_footprint_dir(path_root)
    if not footprint_dir:
        return None

    lib_name = get_lib_name(suffix)
    lib_path = os.path.join(footprint_dir, f"{lib_name}.pretty")
    os.makedirs(lib_path, exist_ok=True)

    lib_table_path = os.path.join(footprint_dir, "fp-lib-table")
    if not os.path.exists(lib_table_path):
        with open(lib_table_path, "w") as f:
            f.write("(fp_lib_table\n)\n")

    with open(lib_table_path, "r") as f:
        content = f.read()

    if f'"{lib_name}"' not in content:
        entry = f'''  (lib
    (name "{lib_name}")
    (type "KiCad")
    (uri "{lib_path}")
    (options "")
    (descr "Uploaded footprints")
  )
'''
        content = content.rstrip()
        if content.endswith(")"):
            content = content[:-1] + entry + ")\n"
        with open(lib_table_path, "w") as f:
            f.write(content)

    return lib_path


def ensure_symbol_lib(path_root: str, lib_name: str, symbol_path: str) -> bool:
    """Register symbol in sym-lib-table."""
    symbol_dir = get_symbol_dir(path_root)
    if not symbol_dir:
        return False

    sym_table_path = os.path.join(symbol_dir, "sym-lib-table")
    if not os.path.exists(sym_table_path):
        with open(sym_table_path, "w") as f:
            f.write("(sym_lib_table\n)\n")

    with open(sym_table_path, "r") as f:
        content = f.read()

    if f'"{lib_name}"' not in content and os.path.basename(symbol_path) not in content:
        entry = f'  (lib (name "{lib_name}") (type "KiCad") (uri "{symbol_path}") (options "") (descr "Uploaded symbol"))\n'
        content = content.rstrip()
        if content.endswith(")"):
            content = content[:-1]
        content = content + entry + ")\n"

        with open(sym_table_path, "w") as f:
            f.write(content)
        return True

    return False


def ensure_footprint_lib_by_name(path_root: str, lib_name: str) -> Optional[str]:
    """Ensure a named footprint library exists and is registered."""
    footprint_dir = get_footprint_dir(path_root)
    if not footprint_dir:
        return None

    lib_path = os.path.join(footprint_dir, f"{lib_name}.pretty")
    os.makedirs(lib_path, exist_ok=True)

    fp_table_path = os.path.join(footprint_dir, "fp-lib-table")
    if not os.path.exists(fp_table_path):
        with open(fp_table_path, "w") as f:
            f.write("(fp_lib_table\n)\n")

    with open(fp_table_path, "r") as f:
        content = f.read()

    if f'"{lib_name}"' not in content:
        entry = f'''  (lib
    (name "{lib_name}")
    (type "KiCad")
    (uri "{lib_path}")
    (options "")
    (descr "Imported footprint")
  )
'''
        content = content.rstrip()
        if content.endswith(")"):
            content = content[:-1] + entry + ")\n"

        with open(fp_table_path, "w") as f:
            f.write(content)

    return lib_path


def copy_with_progress(
    src: str, dst: str, progress_callback=None, progress_weight: float = 100
):
    """Copy file with optional progress callback."""
    total = os.path.getsize(src)
    copied = 0
    chunk_size = 8192

    with open(src, "rb") as fsrc:
        with open(dst, "wb") as fdst:
            while True:
                chunk = fsrc.read(chunk_size)
                if not chunk:
                    break
                fdst.write(chunk)
                copied += len(chunk)
                if progress_callback:
                    progress_callback((copied / total) * progress_weight)

    return dst


def import_symbol(
    path_root: str,
    symbol_path: str,
    progress_callback=None,
    progress_weight: float = 50,
) -> bool:
    """Import a symbol file to KiCad library."""
    symbol_dir = get_symbol_dir(path_root)
    if not symbol_dir:
        return False

    if not os.path.exists(symbol_path):
        return False

    filename = os.path.basename(symbol_path)
    dest = os.path.join(symbol_dir, filename)

    # Copy if doesn't exist
    if not os.path.exists(dest):
        copy_with_progress(symbol_path, dest, progress_callback, progress_weight)

    # Register in sym-lib-table
    lib_name = os.path.splitext(filename)[0]
    return ensure_symbol_lib(path_root, lib_name, dest)


def import_footprint(
    path_root: str,
    footprint_path: str,
    suffix: str = "",
    progress_callback=None,
    progress_weight: float = 50,
) -> bool:
    """Import a footprint file to KiCad library."""
    footprint_lib = ensure_footprint_lib(path_root, suffix)
    if not footprint_lib:
        return False

    if not os.path.exists(footprint_path):
        return False

    filename = os.path.basename(footprint_path)
    dest = os.path.join(footprint_lib, filename)

    # Copy if doesn't exist
    if not os.path.exists(dest):
        copy_with_progress(footprint_path, dest, progress_callback, progress_weight)

    return True


def import_step_model(
    path_root: str,
    step_path: str,
    suffix: str = "",
    progress_callback=None,
    progress_weight: float = 10,
) -> bool:
    """Import a STEP 3D model to KiCad library."""
    footprint_lib = ensure_footprint_lib(path_root, suffix)
    if not footprint_lib or not os.path.exists(step_path):
        return False

    filename = os.path.basename(step_path)
    dest = os.path.join(footprint_lib, filename)

    if not os.path.exists(dest):
        copy_with_progress(step_path, dest, progress_callback, progress_weight)

    return True


def process_snapeda_zip(zip_path: str, kicad_path: str) -> list[str]:
    """Process a SnapEDA zip file and import to KiCad.

    Returns list of imported items.
    """
    extract_dir = zip_path.replace(".zip", "")

    imported = []

    # Extract
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    extract_path = Path(extract_dir)
    kicad_sym = list(extract_path.glob("*.kicad_sym"))
    kicad_mod = list(extract_path.glob("*.kicad_mod"))
    step_files = list(extract_path.glob("*.step")) + list(extract_path.glob("*.stp"))

    if not kicad_sym and not kicad_mod:
        return imported


def get_recent_project_path(kicad_version: str = "9.0") -> Optional[str]:
    """Get the most recent KiCad project path from kicad.json.

    Returns the path to the .kicad_pro file, or None if not found.
    """
    import json

    kicad_config_dir = os.path.expanduser(f"~/.config/kicad/{kicad_version}")
    kicad_json = os.path.join(kicad_config_dir, "kicad.json")

    if not os.path.exists(kicad_json):
        return None

    try:
        with open(kicad_json, "r") as f:
            config = json.load(f)

        # Get mru_path (most recently used path)
        mru_path = None

        # Try different KiCad versions for the setting
        for key in ["window", "eeschema", "pcbnew"]:
            if key in config:
                mru_path = config[key].get("mru_path")
                if mru_path:
                    break

        if not mru_path or not os.path.isdir(mru_path):
            return None

        # Find .kicad_pro file in that directory
        for f in os.listdir(mru_path):
            if f.endswith(".kicad_pro"):
                return os.path.join(mru_path, f)

        return None

    except (json.JSONDecodeError, IOError):
        return None


def find_kicad_executable() -> Optional[str]:
    """Auto-detect KiCad installation across different platforms.

    Returns:
        Path to KiCad executable or None if not found
    """
    import subprocess

    system = platform.system()

    if system == "Linux":
        # Try: which kicad
        try:
            result = subprocess.run(["which", "kicad"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass

        # Try: find in common locations
        linux_paths = [
            "/usr/bin/kicad",
            "/usr/local/bin/kicad",
            "/opt/kicad/bin/kicad",
        ]
        for p in linux_paths:
            if os.path.exists(p):
                return p

        # Try: find AppImage in home directory
        home = os.path.expanduser("~")
        try:
            for f in os.listdir(home):
                if f.lower().startswith("kicad") and f.endswith(".appimage"):
                    appimage = os.path.join(home, f)
                    os.chmod(appimage, 0o755)
                    return appimage
        except:
            pass

        # Try: flatpak
        try:
            result = subprocess.run(
                ["flatpak", "list", "--app"], capture_output=True, text=True
            )
            if "kicad" in result.stdout.lower():
                return "flatpak run org.kicad.KiCad"
        except:
            pass

        # Try: snap
        try:
            result = subprocess.run(["snap", "list"], capture_output=True, text=True)
            if "kicad" in result.stdout.lower():
                return "snap run kicad"
        except:
            pass

        return None

    elif system == "Darwin":
        # Check /Applications
        if os.path.exists("/Applications/KiCad.app"):
            return "/Applications/KiCad.app"
        return None

    elif system == "Windows":
        # Try: find in Program Files
        pf = os.environ.get("ProgramFiles", "C:/Program Files")
        pf_x86 = os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")

        for base in [pf, pf_x86]:
            kicad_dir = os.path.join(base, "KiCad")
            if os.path.isdir(kicad_dir):
                for root, dirs, files in os.walk(kicad_dir):
                    if "kicad.exe" in files:
                        return os.path.join(root, "kicad.exe")

        return None

    return None


def restart_kicad(project_path: Optional[str] = None, delay: float = 2.0) -> bool:
    """Kill running KiCad instance and optionally reopen a project.

    Args:
        project_path: Optional path to .kicad_pro file to reopen
        delay: Seconds to wait before restarting (default 2)

    Returns:
        True if successful, False otherwise
    """
    import platform
    import subprocess
    import time

    system = platform.system()

    # Kill KiCad processes
    try:
        if system == "Linux":
            subprocess.run(["pkill", "-f", "kicad"], capture_output=True)
        elif system == "Darwin":  # macOS
            subprocess.run(["osascript", "-e", 'quit app "KiCad"'], capture_output=True)
        elif system == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "kicad.exe"], capture_output=True)
    except Exception as e:
        print(f"Warning: Could not kill KiCad: {e}")

    # Wait for cleanup
    time.sleep(delay)

    # Find KiCad executable
    kicad_cmd = find_kicad_executable()

    # Restart KiCad
    try:
        if system == "Linux":
            if kicad_cmd:
                # If it's a flatpak or snap command
                if " " in kicad_cmd:
                    parts = kicad_cmd.split()
                    if project_path:
                        subprocess.Popen(parts + [project_path])
                    else:
                        subprocess.Popen(parts)
                else:
                    # It's a path
                    if project_path:
                        subprocess.Popen([kicad_cmd, project_path])
                    else:
                        subprocess.Popen([kicad_cmd])
            else:
                # Fallback: try xdg-open on project directory
                if project_path:
                    proj_dir = os.path.dirname(project_path)
                    subprocess.Popen(["xdg-open", proj_dir])
                else:
                    subprocess.Popen(["xdg-open", "."])
            return True

        elif system == "Darwin":
            if project_path:
                subprocess.Popen(["open", "-a", "KiCad", project_path])
            else:
                subprocess.Popen(["open", "-a", "KiCad"])
            return True

        elif system == "Windows":
            if project_path:
                # Use os.startfile which opens with associated app
                if hasattr(os, "startfile"):
                    os.startfile(project_path)
                else:
                    subprocess.Popen(["start", "", project_path], shell=True)
            elif kicad_cmd:
                subprocess.Popen([kicad_cmd])
            else:
                # Try to find and launch
                subprocess.Popen(["start", "kicad"], shell=True)
            return True

    except Exception as e:
        print(f"Warning: Could not restart KiCad: {e}")
        return False

    return False

    symbol_dir = get_symbol_dir(kicad_path)

    # Import symbols - each symbol gets its own footprint library
    for sym in kicad_sym:
        sym_name = sym.stem

        if symbol_dir:
            dest = os.path.join(symbol_dir, sym.name)
            if not os.path.exists(dest):
                shutil.copy2(sym, dest)
                imported.append(f"Symbol: {sym.name}")

            # Register symbol
            ensure_symbol_lib(kicad_path, sym_name, dest)

        # Create footprint library for this symbol
        footprint_lib = ensure_footprint_lib_by_name(kicad_path, sym_name)
        if footprint_lib:
            # Copy footprints matching this symbol
            for mod in kicad_mod:
                dest = os.path.join(footprint_lib, mod.name)
                if not os.path.exists(dest):
                    shutil.copy2(mod, dest)
                    imported.append(f"Footprint: {mod.name}")

            # Copy step models
            for step in step_files:
                dest = os.path.join(footprint_lib, step.name)
                if not os.path.exists(dest):
                    shutil.copy2(step, dest)
                    imported.append(f"3D: {step.name}")

    # Also copy to default folder as fallback
    default_lib = ensure_footprint_lib(kicad_path, "snapeda")
    if default_lib:
        for mod in kicad_mod:
            dest = os.path.join(default_lib, mod.name)
            if not os.path.exists(dest):
                shutil.copy2(mod, dest)

        for step in step_files:
            dest = os.path.join(default_lib, step.name)
            if not os.path.exists(dest):
                shutil.copy2(step, dest)

    return imported
