"""KicadSend GUI - Upload KiCad symbols, footprints, and 3D models."""

import tkinter
from tkinter import ttk, StringVar
from tkinter import filedialog
import pymsgbox
import sv_ttk
import os
import webbrowser

from kicad_send import (
    get_symbol_dir,
    get_footprint_dir,
    ensure_footprint_lib,
    import_symbol,
    import_footprint,
    import_step_model,
    get_recent_project_path,
    restart_kicad,
)
from kicad_send.watcher import SnapEDAWatcher


# --- GUI Setup ---
root = tkinter.Tk()
root.title("KicadSend - KiCad Library Manager")
root.geometry("600x900")
root.resizable(False, False)

sv_ttk.set_theme("dark")

# Global state
symbolpath = "No path chosen"
footprintpath = "No path chosen"
steppath = "No path chosen"
upload_count = 0
path = None
snapeda_watcher = None
progress = None
auto_restart_var = None  # Will be set after GUI is created


# --- Utility Functions ---
def is_kicad_lib_path(path: str) -> bool:
    """Check if path is a valid KiCad library directory."""
    if not os.path.isdir(path):
        return False
    files = os.listdir(path)
    return "sym-lib-table" in files or "fp-lib-table" in files


def get_unique_filename(directory: str, filename: str) -> str:
    """Get unique filename by appending number if exists."""
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


def copy_with_progress(src: str, dst: str, progress_weight: float = 100):
    """Copy file with progress."""
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
                progress["value"] = (copied / total) * progress_weight
                root.update()


def setup_kicad_path():
    """Setup KiCad path after GUI is ready."""
    global path

    path_file = "kicad_path.txt"

    if os.path.exists(path_file):
        with open(path_file, "r") as f:
            path = f.read()
        return

    pymsgbox.alert(
        "Please select the folder containing your KiCad user libraries (sym-lib-table / fp-lib-table).",
        "Select Your KiCad Library Folder",
    )

    path = filedialog.askdirectory(title="Select KiCad Library Folder")

    if not path or not is_kicad_lib_path(path):
        pymsgbox.alert(
            "Selected folder is not a valid KiCad library folder.",
            "Invalid Library Path",
        )
        os._exit(1)

    with open(path_file, "w") as f:
        f.write(path)


# --- GUI Callbacks ---
def upload_symbol():
    """Select symbol file."""
    global symbolpath
    symbolpath = filedialog.askopenfilename(
        title="Select Symbol File",
        filetypes=[("KiCad Symbol Files", "*.kicad_sym"), ("All Files", "*.*")],
    )
    if symbolpath:
        selectedfilesym.config(text=os.path.basename(symbolpath))


def upload_footprint():
    """Select footprint file."""
    global footprintpath
    footprintpath = filedialog.askopenfilename(
        title="Select Footprint File",
        filetypes=[("KiCad Footprint Files", "*.kicad_mod"), ("All Files", "*.*")],
    )
    if footprintpath:
        selectedfilefoot.config(text=os.path.basename(footprintpath))


def upload_step():
    """Select STEP file."""
    global steppath
    steppath = filedialog.askopenfilename(
        title="Select STEP 3D Model",
        filetypes=[
            ("STEP Models", "*.step"),
            ("STEP Models", "*.stp"),
            ("All Files", "*.*"),
        ],
    )
    if steppath:
        selectedfilestep.config(text=os.path.basename(steppath))


def upload_data():
    """Upload selected files to KiCad."""
    global upload_count

    try:
        progress["value"] = 0
        root.update()

        suffix = suffix_var.get().strip()

        # Symbol
        if symbolpath and symbolpath != "No path chosen":
            import_symbol(path, symbolpath, lambda w: _update_progress(w, 50))

        # Footprint
        if footprintpath and footprintpath != "No path chosen":
            lib_path = ensure_footprint_lib(path, suffix)
            if lib_path:
                dest = get_unique_filename(lib_path, os.path.basename(footprintpath))
                copy_with_progress(footprintpath, dest, 40)

        # STEP
        if steppath and steppath != "No path chosen":
            lib_path = ensure_footprint_lib(path, suffix)
            if lib_path:
                dest = get_unique_filename(lib_path, os.path.basename(steppath))
                copy_with_progress(steppath, dest, 10)

        progress["value"] = 100
        upload_count += 1

        # Auto-restart KiCad if enabled
        if auto_restart_var.get():
            project_path = get_recent_project_path()
            if project_path:
                pymsgbox.alert(
                    "Successfully uploaded!\n\nRestarting KiCad...",
                    "Upload Complete",
                )
                restart_kicad(project_path)
            else:
                pymsgbox.alert(
                    "Successfully uploaded!\n\nRestart KiCad to see the new components.",
                    "Upload Complete",
                )
        else:
            pymsgbox.alert(
                "Successfully uploaded!\n\nRestart KiCad to see the new components.",
                "Upload Complete",
            )

    except Exception as e:
        pymsgbox.alert(f"Failed to upload files: {e}", "Error")


def _update_progress(value: float, max_value: float):
    """Update progress bar."""
    progress["value"] = (value / 100) * max_value
    root.update()


def open_snapeda_search():
    """Open SnapEDA in browser."""
    global snapeda_watcher

    # Get recent project path for auto-restart
    project_path = get_recent_project_path()

    if path:

        def on_import(imported_files):
            # Show success message
            msg = "Successfully imported:\n\n" + "\n".join(imported_files)

            if auto_restart_var.get() and project_path:
                msg += "\n\nRestarting KiCad with your project..."
                root.after(0, lambda: pymsgbox.alert(msg, "Import Complete"))
                # Restart KiCad with project
                root.after(100, lambda: restart_kicad(project_path))
            else:
                msg += "\n\nRestart KiCad to see the new components!"
                root.after(0, lambda: pymsgbox.alert(msg, "Import Complete"))

        snapeda_watcher = SnapEDAWatcher(path, callback=on_import)
        snapeda_watcher.start()

    pymsgbox.alert(
        "SnapEDA Component Search\n\n"
        "1. A browser will open to snapeda.com\n"
        "2. Search for your component (e.g., STM32F103)\n"
        "3. Click 'Download' and select 'KiCad V6+'\n"
        "4. The downloaded ZIP will be automatically imported!\n\n"
        f"Auto-restart: {'Enabled' if auto_restart_var.get() else 'Disabled'}\n"
        f"Project: {os.path.basename(project_path) if project_path else 'Not detected'}\n\n"
        "Note: Make sure to download to your Downloads folder.",
        "SnapEDA Search",
    )

    webbrowser.open("https://www.snapeda.com/search")


# --- GUI Layout ---
ttk.Label(root, text="KicadSend", font=("Arial", 20, "bold")).pack(pady=20)

progress = ttk.Progressbar(root, orient="horizontal", mode="determinate", length=400)
progress.pack(pady=10)

ttk.Label(root, text="Library Suffix (optional)", font=("Arial", 12)).pack(pady=10)
suffix_var = StringVar()
ttk.Entry(root, textvariable=suffix_var, width=30).pack(pady=5)

auto_restart_var = tkinter.BooleanVar(value=True)
ttk.Checkbutton(
    root,
    text="Auto-restart KiCad after import",
    variable=auto_restart_var,
).pack(pady=5)

ttk.Label(root, text="Symbol File", font=("Arial", 12)).pack(pady=10)
ttk.Button(root, text="Upload Symbol", command=upload_symbol).pack(pady=5)
selectedfilesym = ttk.Label(root, text=symbolpath, font=("Arial", 10))
selectedfilesym.pack(pady=5)

ttk.Label(root, text="Footprint File", font=("Arial", 12)).pack(pady=10)
ttk.Button(root, text="Upload Footprint", command=upload_footprint).pack(pady=5)
selectedfilefoot = ttk.Label(root, text=footprintpath, font=("Arial", 10))
selectedfilefoot.pack(pady=5)

ttk.Label(root, text="3D Model (STEP)", font=("Arial", 12)).pack(pady=10)
ttk.Button(root, text="Upload STEP Model", command=upload_step).pack(pady=5)
selectedfilestep = ttk.Label(root, text=steppath, font=("Arial", 10))
selectedfilestep.pack(pady=5)

ttk.Button(root, text="Send to KiCad", command=upload_data).pack(pady=20)

# --- SnapEDA Section ---
ttk.Separator(root, orient="horizontal").pack(fill="x", pady=20)

ttk.Label(root, text="SnapEDA Component Search", font=("Arial", 14, "bold")).pack(
    pady=10
)
ttk.Label(
    root,
    text="Search & download from snapeda.com",
    font=("Arial", 9),
    foreground="gray",
).pack(pady=5)

ttk.Button(
    root,
    text="🔍 Open SnapEDA Search",
    command=open_snapeda_search,
    style="Accent.TButton",
).pack(pady=10)

# Setup path and run
setup_kicad_path()
root.mainloop()
