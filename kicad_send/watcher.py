"""Watches for downloaded SnapEDA zip files and auto-imports them."""

import os
import threading
import time
from typing import Callable, Optional

from .lib_manager import (
    get_footprint_dir,
    get_symbol_dir,
    ensure_symbol_lib,
    ensure_footprint_lib,
    ensure_footprint_lib_by_name,
)


class SnapEDAWatcher:
    """Watches download directories for new SnapEDA zip files."""

    DEFAULT_DOWNLOAD_DIRS = [
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/downloads"),
    ]

    def __init__(
        self, kicad_path: str, callback: Optional[Callable[[list[str]], None]] = None
    ):
        """Initialize watcher.

        Args:
            kicad_path: Path to KiCad user library directory
            callback: Optional callback function called with list of imported items
        """
        self.kicad_path = kicad_path
        self.callback = callback
        self.running = False
        self.known_files: set[str] = set()
        self.download_dirs = self.DEFAULT_DOWNLOAD_DIRS.copy()

        # Initialize known files
        self._scan_initial_files()

    def _scan_initial_files(self):
        """Get initial list of files in download directories."""
        for d in self.download_dirs:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    self.known_files.add(os.path.join(d, f))

    def add_watch_directory(self, path: str):
        """Add a directory to watch."""
        if os.path.isdir(path) and path not in self.download_dirs:
            self.download_dirs.append(path)

    def start(self):
        """Start watching for new downloads."""
        if self.running:
            return
        self.running = True
        thread = threading.Thread(target=self._watch_loop, daemon=True)
        thread.start()

    def stop(self):
        """Stop watching."""
        self.running = False

    def _watch_loop(self):
        """Background loop that checks for new files."""
        while self.running:
            time.sleep(2)
            self._check_for_new_files()

    def _check_for_new_files(self):
        """Check for new zip files and process them."""
        for d in self.download_dirs:
            if not os.path.isdir(d):
                continue

            for f in os.listdir(d):
                filepath = os.path.join(d, f)

                # Skip if we already know about this file
                if filepath in self.known_files:
                    continue

                # Skip non-zip files
                if not f.lower().endswith(".zip"):
                    continue

                # Skip files still being written (small size)
                try:
                    if os.path.getsize(filepath) < 1000:
                        continue
                except OSError:
                    continue

                # Found a new zip - process it
                self.known_files.add(filepath)
                imported = self._process_zip(filepath)

                if imported and self.callback:
                    self.callback(imported)

    def _process_zip(self, zip_path: str) -> list[str]:
        """Extract and import a SnapEDA zip file."""
        import zipfile
        from pathlib import Path
        import shutil

        print(f"Processing: {zip_path}")

        try:
            extract_dir = zip_path.replace(".zip", "")

            # Extract
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            extract_path = Path(extract_dir)
            kicad_sym = list(extract_path.glob("*.kicad_sym"))
            kicad_mod = list(extract_path.glob("*.kicad_mod"))
            step_files = list(extract_path.glob("*.step")) + list(
                extract_path.glob("*.stp")
            )

            if not kicad_sym and not kicad_mod:
                print("No KiCad files found in zip")
                return []

            imported = []
            symbol_dir = get_symbol_dir(self.kicad_path)

            # Import symbols - each gets its own footprint library
            for sym in kicad_sym:
                sym_name = sym.stem

                if symbol_dir:
                    dest = os.path.join(symbol_dir, sym.name)
                    if not os.path.exists(dest):
                        shutil.copy2(sym, dest)
                        imported.append(f"Symbol: {sym.name}")

                    # Register symbol
                    ensure_symbol_lib(self.kicad_path, sym_name, dest)

                # Create footprint library for this symbol
                footprint_lib = ensure_footprint_lib_by_name(self.kicad_path, sym_name)
                if footprint_lib:
                    for mod in kicad_mod:
                        mod_dest = os.path.join(footprint_lib, mod.name)
                        if not os.path.exists(mod_dest):
                            shutil.copy2(mod, mod_dest)
                            imported.append(f"Footprint: {mod.name}")

                    for step in step_files:
                        step_dest = os.path.join(footprint_lib, step.name)
                        if not os.path.exists(step_dest):
                            shutil.copy2(step, step_dest)
                            imported.append(f"3D: {step.name}")

            # Also copy to default folder
            default_lib = ensure_footprint_lib(self.kicad_path, "snapeda")
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

        except Exception as e:
            print(f"Error processing zip: {e}")
            return []
