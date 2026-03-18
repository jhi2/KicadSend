from tkinter import ttk, StringVar
from ttkthemes import ThemedTk
import os
import shutil
from tkinter.filedialog import askdirectory, askopenfilename
from tkinter.messagebox import showinfo, showerror

# --- GUI setup ---
root = ThemedTk(theme="clearlooks")
root.title("KiCad Symbol and Footprint Installer")
root.geometry("600x800")
root.resizable(False, False)

symbolpath = "No path chosen"
footprintpath = "No path chosen"
steppath = "No path chosen"
upload_count = 0

# Check if previous path saved
path_exist = os.path.exists("kicad_path.txt")


# --- Utility functions ---
def is_kicad_lib_path(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    files = os.listdir(path)
    if "sym-lib-table" in files or "fp-lib-table" in files:
        return True
    if any(f.endswith(".kicad_sym") for f in files):
        return True
    if any(f.endswith(".pretty") for f in files):
        return True
    return False


def find_kicad_subdir(root_path, table_file):
    for dirpath, dirnames, filenames in os.walk(root_path):
        if table_file in filenames:
            return dirpath
    return None


def get_symbol_dir(root_path):
    return find_kicad_subdir(root_path, "sym-lib-table")


def get_footprint_dir(root_path):
    return find_kicad_subdir(root_path, "fp-lib-table")


def get_unique_filename(dest_dir, filename):
    base, ext = os.path.splitext(filename)
    dest = os.path.join(dest_dir, filename)
    if not os.path.exists(dest):
        return dest
    counter = 1
    while True:
        new_name = f"{base}_{counter}{ext}"
        new_dest = os.path.join(dest_dir, new_name)
        if not os.path.exists(new_dest):
            return new_dest
        counter += 1


def get_lib_name(suffix=""):
    if suffix:
        return f"Uploaded_{suffix}"
    return "Uploaded"


# --- Symbol library handling ---
def create_uploaded_symbol_lib(path_root, suffix=""):
    """Ensure Uploaded[_suffix].kicad_sym exists and is registered in sym-lib-table."""
    symbol_dir = get_symbol_dir(path_root)
    if not symbol_dir:
        showerror("Error", "Could not find symbol library directory")
        return None

    lib_name = get_lib_name(suffix)
    lib_file = os.path.join(symbol_dir, f"{lib_name}.kicad_sym")

    # Create library file if it doesn't exist
    if not os.path.exists(lib_file):
        with open(lib_file, "w") as f:
            f.write(f"(kicad_symbol_lib (name {lib_name}) (type Legacy))\n")

    # Register library in sym-lib-table if missing
    sym_table_path = os.path.join(symbol_dir, "sym-lib-table")
    if os.path.exists(sym_table_path):
        with open(sym_table_path, "r") as f:
            content = f.read()
        if f'("{lib_name}"' not in content:
            entry = f"""  (lib
    (name {lib_name})
    (type Legacy)
    (uri "{lib_file}")
    (options "")
    (descr "Uploaded symbols")
  )
"""
            content = content.rstrip()
            if content.endswith(")"):
                content = content[:-1] + entry + ")\n"
            with open(sym_table_path, "w") as f:
                f.write(content)

    return lib_file


# --- Footprint library handling ---
def create_uploaded_footprint_lib(path_root, suffix=""):
    """Ensure Uploaded[_suffix].pretty exists and is registered in fp-lib-table."""
    footprint_dir = get_footprint_dir(path_root)
    if not footprint_dir:
        showerror("Error", "Could not find footprint library directory")
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

    if f'("{lib_name}"' not in content and f"{lib_name}.pretty" not in content:
        entry = f"""  (lib
    (name {lib_name})
    (type KiCad)
    (uri "{lib_path}")
    (options "")
    (descr "Uploaded footprints")
  )
"""
        content = content.rstrip()
        if content.endswith(")"):
            content = content[:-1] + entry + ")\n"
        with open(lib_table_path, "w") as f:
            f.write(content)

    return lib_path


def copy_with_progress(src, dst, progress_weight=100):
    total = os.path.getsize(src)
    copied = 0
    chunk_size = 1024 * 1024
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


# --- KiCad library path selection ---
if path_exist:
    with open("kicad_path.txt", "r") as f:
        path = f.read()
else:
    showinfo(
        "Select Your KiCad Library Folder",
        "Please select the folder containing your KiCad user libraries (sym-lib-table / fp-lib-table).",
    )
    path = askdirectory(title="Select KiCad Library Folder")
    if not is_kicad_lib_path(path):
        showerror(
            "Invalid Library Path",
            "Selected folder is not a valid KiCad library folder.",
        )
        exit()
    with open("kicad_path.txt", "w") as f:
        f.write(path)


# --- GUI callbacks ---
def upload_symbol():
    global symbolpath
    symbolpath = askopenfilename(
        title="Select Symbol File", filetypes=[("KiCad Symbol Files", "*.kicad_sym")]
    )
    if symbolpath:
        selectedfilesym.config(text=os.path.basename(symbolpath))


def upload_footprint():
    global footprintpath
    footprintpath = askopenfilename(
        title="Select Footprint File",
        filetypes=[("KiCad Footprint Files", "*.kicad_mod")],
    )
    if footprintpath:
        selectedfilefoot.config(text=os.path.basename(footprintpath))


def upload_step():
    global steppath
    steppath = askopenfilename(
        title="Select STEP 3D Model",
        filetypes=[("STEP 3D Models", "*.step"), ("STEP Models", "*.stp")],
    )
    if steppath:
        selectedfilestep.config(text=os.path.basename(steppath))


def upload_data():
    global upload_count
    if not symbolpath and not footprintpath:
        showerror("Error", "Please select at least a symbol or footprint file")
        return

    try:
        progress["value"] = 0
        root.update()

        suffix = suffix_var.get().strip()
        lib_path = None

        # --- Symbol ---
        # Copy symbol as separate file and register as library
        if symbolpath and symbolpath != "No path chosen":
            symbol_dir = get_symbol_dir(path)
            if symbol_dir:
                sym_lib_name = get_lib_name(suffix)

                # Copy symbol file directly to library directory
                if os.path.exists(symbolpath):
                    filename = os.path.basename(symbolpath)
                    dest = os.path.join(symbol_dir, filename)
                    # If file already exists, skip copying (it's already registered)
                    if not os.path.exists(dest):
                        # Read, strip leading whitespace, and write to fix encoding issues
                        with open(symbolpath, "r", encoding="utf-8") as f:
                            content = f.read().lstrip()
                        with open(dest, "w", encoding="utf-8") as f:
                            f.write(content)

                    # Register as a separate library entry for each file
                    sym_table_path = os.path.join(symbol_dir, "sym-lib-table")
                    if os.path.exists(sym_table_path):
                        with open(sym_table_path, "r") as f:
                            content = f.read()
                        lib_name = os.path.splitext(filename)[0]
                        if (
                            f'"{lib_name}"' not in content
                            and os.path.basename(dest) not in content
                        ):
                            entry = f'  (lib (name "{lib_name}") (type "KiCad") (uri "{dest}") (options "") (descr "Uploaded symbol"))\n'
                            content = content.rstrip()
                            if content.endswith(")"):
                                content = content[:-1] + entry + ")"
                            with open(sym_table_path, "w") as f:
                                f.write(content)

                    progress["value"] = 50
                    root.update()

        # --- Footprint ---
        if footprintpath and footprintpath != "No path chosen":
            lib_path = create_uploaded_footprint_lib(path, suffix)
            if lib_path:
                dest = get_unique_filename(lib_path, os.path.basename(footprintpath))
                copy_with_progress(footprintpath, dest, 40)

        # --- Optional STEP ---
        if steppath and steppath != "No path chosen":
            if lib_path:
                step_dest = get_unique_filename(lib_path, os.path.basename(steppath))
                copy_with_progress(steppath, step_dest, 10)

        progress["value"] = 100
        upload_count += 1
    except Exception as e:
        showerror("Error", f"Failed to upload files: {e}")


# --- GUI layout ---
ttk.Label(root, text="Send to KiCad", font=("Arial", 20, "bold")).pack(pady=20)

progress = ttk.Progressbar(root, orient="horizontal", mode="determinate", length=400)
progress.pack(pady=10)

ttk.Label(root, text="Library Suffix (optional)", font=("Arial", 12)).pack(pady=10)
suffix_var = StringVar()
ttk.Entry(root, textvariable=suffix_var, width=30).pack(pady=5)

ttk.Label(root, text="Symbol File", font=("Arial", 12)).pack(pady=10)
ttk.Button(root, text="Upload Symbol", command=upload_symbol).pack(pady=10)
selectedfilesym = ttk.Label(root, text=symbolpath, font=("Arial", 10))
selectedfilesym.pack(pady=10)

ttk.Label(root, text="Footprint File", font=("Arial", 12)).pack(pady=10)
ttk.Button(root, text="Upload Footprint", command=upload_footprint).pack(pady=10)
selectedfilefoot = ttk.Label(root, text=footprintpath, font=("Arial", 10))
selectedfilefoot.pack(pady=10)

ttk.Label(root, text="3D Model (STEP)", font=("Arial", 12)).pack(pady=10)
ttk.Button(root, text="Upload STEP Model", command=upload_step).pack(pady=10)
selectedfilestep = ttk.Label(root, text=steppath, font=("Arial", 10))
selectedfilestep.pack(pady=10)

ttk.Button(root, text="Send to KiCad", command=upload_data).pack(pady=20)

root.mainloop()
