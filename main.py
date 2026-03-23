import tkinter
from tkinter import ttk, StringVar, PhotoImage, Scrollbar
from tkinter import filedialog
import pymsgbox
import sv_ttk
import os
import shutil
import threading
import time
import zipfile
from pathlib import Path
import webbrowser


# --- SnapEDA Download Watcher ---
class SnapEDAWatcher:
    """Watches for downloaded files and auto-imports them."""

    def __init__(self, kicad_path, callback=None):
        self.kicad_path = kicad_path
        self.callback = callback
        self.running = False
        self.known_files = set()

        # Common download directories
        self.download_dirs = [
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~/downloads"),
        ]

        # Initialize known files
        self._scan_download_dirs()

    def _scan_download_dirs(self):
        """Get initial list of files."""
        for d in self.download_dirs:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    self.known_files.add(os.path.join(d, f))

    def start(self):
        """Start watching for new downloads."""
        self.running = True
        thread = threading.Thread(target=self._watch_loop, daemon=True)
        thread.start()

    def stop(self):
        """Stop watching."""
        self.running = False

    def _watch_loop(self):
        """Watch loop that checks for new files."""
        while self.running:
            time.sleep(2)
            self._check_for_new_files()

    def _check_for_new_files(self):
        """Check for new zip files and auto-import."""
        for d in self.download_dirs:
            if not os.path.isdir(d):
                continue

            for f in os.listdir(d):
                filepath = os.path.join(d, f)

                # Skip if we already knew about it
                if filepath in self.known_files:
                    continue

                # Skip non-zip files
                if not f.lower().endswith(".zip"):
                    continue

                # Skip if still being written (check if file is stable)
                try:
                    if os.path.getsize(filepath) < 1000:
                        continue  # File still being written
                except:
                    continue

                # Found a new zip! Process it
                self.known_files.add(filepath)
                self._process_zip(filepath)

    def _process_zip(self, zip_path):
        """Extract and import a downloaded zip file."""
        print(f"Found new download: {zip_path}")

        try:
            extract_dir = zip_path.replace(".zip", "")

            # Extract
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            # Find KiCad files
            extract_path = Path(extract_dir)
            kicad_sym = list(extract_path.glob("*.kicad_sym"))
            kicad_mod = list(extract_path.glob("*.kicad_mod"))

            if not kicad_sym and not kicad_mod:
                print("No KiCad files found in zip")
                return

            # Import files
            imported = []

            # Get symbol directory
            symbol_dir = get_symbol_dir(self.kicad_path)

            # Import symbols
            for sym in kicad_sym:
                if symbol_dir:
                    dest = os.path.join(symbol_dir, sym.name)
                    if not os.path.exists(dest):
                        shutil.copy2(sym, dest)
                        imported.append(f"Symbol: {sym.name}")

                        # Register in sym-lib-table using the copied path
                        self._register_symbol(dest, symbol_dir)

            # Import footprints - create library for each symbol
            for sym in kicad_sym:
                sym_name = sym.stem
                # Create a library folder named after the symbol (like SnapEDA expects)
                footprint_dir = get_footprint_dir(self.kicad_path)
                if footprint_dir:
                    footprint_lib = os.path.join(footprint_dir, f"{sym_name}.pretty")
                    os.makedirs(footprint_lib, exist_ok=True)

                    # Register in fp-lib-table if not already
                    self._register_footprint_lib(footprint_lib, sym_name)

                    # Copy footprints matching this symbol
                    for mod in kicad_mod:
                        dest = os.path.join(footprint_lib, mod.name)
                        if not os.path.exists(dest):
                            shutil.copy2(mod, dest)
                            imported.append(f"Footprint: {mod.name}")

            # Also copy to default snapeda folder as fallback
            footprint_lib = create_uploaded_footprint_lib(self.kicad_path, "snapeda")
            if footprint_lib:
                for mod in kicad_mod:
                    dest = os.path.join(footprint_lib, mod.name)
                    if not os.path.exists(dest):
                        shutil.copy2(mod, dest)

            # Copy 3D models too
            step_files = list(extract_path.glob("*.step")) + list(
                extract_path.glob("*.stp")
            )
            for step in step_files:
                if footprint_lib:
                    dest = os.path.join(footprint_lib, step.name)
                    if not os.path.exists(dest):
                        shutil.copy2(step, dest)
                        imported.append(f"3D: {step.name}")

            # Notify user
            if imported and self.callback:
                self.callback(imported)
            elif imported:
                print(f"Imported: {imported}")

        except Exception as e:
            print(f"Error processing zip: {e}")

    def _register_symbol(self, sym_path, symbol_dir):
        """Register symbol in sym-lib-table."""
        sym_path = Path(sym_path)
        sym_table_path = os.path.join(symbol_dir, "sym-lib-table")
        if not os.path.exists(sym_table_path):
            return

        lib_name = sym_path.stem
        with open(sym_table_path, "r") as f:
            content = f.read()

        # Check if already registered
        if f'"{lib_name}"' not in content and sym_path.name not in content:
            entry = f'  (lib (name "{lib_name}") (type "KiCad") (uri "{sym_path}") (options "") (descr "Imported from SnapEDA"))\n'
            content = content.rstrip()
            if content.endswith(")"):
                content = content[:-1]
            content = content + entry + ")\n"

            with open(sym_table_path, "w") as f:
                f.write(content)

    def _register_footprint_lib(self, footprint_lib_path, lib_name):
        """Register footprint library in fp-lib-table."""
        footprint_dir = get_footprint_dir(self.kicad_path)
        if not footprint_dir:
            return

        fp_table_path = os.path.join(footprint_dir, "fp-lib-table")
        if not os.path.exists(fp_table_path):
            with open(fp_table_path, "w") as f:
                f.write("(fp_lib_table\n)\n")

        with open(fp_table_path, "r") as f:
            content = f.read()

        # Check if already registered
        if f'"{lib_name}"' not in content and f"{lib_name}.pretty" not in content:
            entry = f'''  (lib
    (name "{lib_name}")
    (type "KiCad")
    (uri "{footprint_lib_path}")
    (options "")
    (descr "Imported from SnapEDA")
  )
'''
            content = content.rstrip()
            if content.endswith(")"):
                content = content[:-1] + entry + ")\n"

            with open(fp_table_path, "w") as f:
                f.write(content)


# --- SnapEDA Search ---
snapeda_watcher = None


def open_snapeda_search():
    """Open SnapEDA in browser for searching and downloading."""
    import webbrowser

    global snapeda_watcher

    # Start watcher if we have a path
    if path:
        # Create callback that runs on main thread
        def on_import(imported_files):
            msg = "Successfully imported:\n\n" + "\n".join(imported_files)
            msg += "\n\nRestart KiCad to see the new components!"
            root.after(0, lambda: pymsgbox.alert(msg, "Import Complete"))

        snapeda_watcher = SnapEDAWatcher(path, callback=on_import)
        snapeda_watcher.start()
        print("Started watching for downloads...")

    # Show instructions to user
    pymsgbox.alert(
        "SnapEDA Component Search\n\n"
        "1. A browser will open to snapeda.com\n"
        "2. Search for your component (e.g., STM32F103)\n"
        "3. Click 'Download' and select 'KiCad V6+'\n"
        "4. The downloaded ZIP will be automatically imported!\n\n"
        "Note: Make sure to download to your Downloads folder.",
        "SnapEDA Search",
    )

    # Open in default browser
    webbrowser.open("https://www.snapeda.com/search")


# --- Custom styled file dialog using sv-ttk ---
class StyledFileDialog:
    """Custom styled file dialog using sv-ttk theme."""

    def __init__(self, title, filetypes, initial_dir=None):
        self.result = None
        self.title = title
        self.filetypes = filetypes
        self.initial_dir = initial_dir or os.path.expanduser("~")

        # Create dialog window
        self.dialog = tkinter.Toplevel(root)
        self.dialog.title(title)
        self.dialog.geometry("750x580")
        self.dialog.transient(root)
        self.dialog.grab_set()

        # Current path
        self.current_path = Path(self.initial_dir)

        # Build UI with ttk/sv-ttk
        self.build_ui()

        # Load files
        self.refresh_list()

        # Wait for dialog to close
        self.dialog.wait_window()

    def build_ui(self):
        # Path frame
        path_frame = ttk.Frame(self.dialog)
        path_frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(path_frame, text="Path:").pack(side="left")

        self.path_var = StringVar(value=str(self.current_path))
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=50)
        path_entry.pack(side="left", fill="x", expand=True, padx=5)
        path_entry.bind("<Return>", lambda e: self.navigate_to(self.path_var.get()))

        # Navigation buttons
        ttk.Button(path_frame, text="↑", command=self.go_up, width=4).pack(
            side="left", padx=2
        )
        ttk.Button(
            path_frame,
            text="Go",
            command=lambda: self.navigate_to(self.path_var.get()),
            width=6,
        ).pack(side="left", padx=2)

        # File list frame
        list_frame = ttk.Frame(self.dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Scrollbars
        yscroll = ttk.Scrollbar(list_frame, orient="vertical")
        yscroll.pack(side="right", fill="y")

        xscroll = ttk.Scrollbar(list_frame, orient="horizontal")
        xscroll.pack(side="bottom", fill="x")

        # File listbox using ttk Treeview
        columns = ("name", "size", "modified")
        self.file_list = ttk.Treeview(
            list_frame,
            columns=columns,
            show="tree headings",
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set,
        )
        yscroll.config(command=self.file_list.yview)
        xscroll.config(command=self.file_list.xview)

        self.file_list.column("#0", width=300, minwidth=200)
        self.file_list.column("size", width=80, minwidth=60)
        self.file_list.column("modified", width=150, minwidth=100)

        self.file_list.heading("#0", text="Name")
        self.file_list.heading("size", text="Size")
        self.file_list.heading("modified", text="Modified")

        self.file_list.pack(side="left", fill="both", expand=True)

        self.file_list.bind("<Double-Button-1>", self.on_double_click)
        self.file_list.bind("<Return>", self.on_double_click)

        # Search frame
        search_frame = ttk.Frame(self.dialog)
        search_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(search_frame, text="Search:").pack(side="left")

        self.search_var = StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=5, fill="x", expand=True)
        search_entry.bind("<KeyRelease>", lambda e: self.refresh_list())

        # Clear search button
        ttk.Button(search_frame, text="✕", command=self.clear_search, width=3).pack(
            side="left", padx=2
        )

        # Filter frame
        filter_frame = ttk.Frame(self.dialog)
        filter_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(filter_frame, text="Files of type:").pack(side="left")

        self.filter_var = StringVar(
            value=self.filetypes[0][1] if self.filetypes else "*"
        )
        filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_var,
            state="readonly",
            values=[ext for _, ext in self.filetypes],
            width=25,
        )
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(btn_frame, text="Open", command=self.open_file).pack(
            side="right", padx=5
        )
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(
            side="right", padx=5
        )

    def refresh_list(self):
        # Clear existing items
        for item in self.file_list.get_children():
            self.file_list.delete(item)

        try:
            search_term = self.search_var.get().lower()
            files = []
            dirs = []
            filter_ext = self.filter_var.get()

            for item in self.current_path.iterdir():
                if item.name.startswith("."):
                    continue

                # Apply search filter
                if search_term and search_term not in item.name.lower():
                    continue

                if item.is_dir():
                    dirs.append(item)
                elif item.is_file():
                    # Apply filter
                    if filter_ext == "*" or item.suffix in [
                        filter_ext,
                        filter_ext.replace("*", ""),
                    ]:
                        files.append(item)

            # Sort: directories first, then files
            for d in sorted(dirs, key=lambda x: x.name.lower()):
                size = ""
                import datetime

                mtime = datetime.datetime.fromtimestamp(d.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
                self.file_list.insert(
                    "", "end", text=d.name + "/", values=(size, mtime), tags=("dir",)
                )

            for f in sorted(files, key=lambda x: x.name.lower()):
                size = f.stat().st_size
                if size > 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f}M"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f}K"
                else:
                    size_str = f"{size}B"
                import datetime

                mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
                self.file_list.insert(
                    "", "end", text=f.name, values=(size_str, mtime), tags=("file",)
                )

        except PermissionError:
            pass

    def clear_search(self):
        self.search_var.set("")
        self.refresh_list()

    def navigate_to(self, path):
        new_path = Path(path)
        if new_path.is_dir():
            self.current_path = new_path
            self.path_var.set(str(self.current_path))
            self.refresh_list()

    def go_up(self):
        if self.current_path.parent != self.current_path:
            self.current_path = self.current_path.parent
            self.path_var.set(str(self.current_path))
            self.refresh_list()

    def on_double_click(self, event):
        selection = self.file_list.selection()
        if selection:
            item = self.file_list.item(selection[0])
            name = item["text"]
            path = self.current_path / name

            if item["tags"] and "dir" in item["tags"]:
                self.navigate_to(path)
            else:
                self.result = str(path)
                self.dialog.destroy()

    def open_file(self):
        selection = self.file_list.selection()
        if selection:
            item = self.file_list.item(selection[0])
            if item["tags"] and "file" in item["tags"]:
                name = item["text"]
                path = self.current_path / name
                self.result = str(path)
                self.dialog.destroy()


def styled_open_file(title, filetypes, initial_dir=None):
    """Open a custom styled file dialog."""
    dialog = StyledFileDialog(title, filetypes, initial_dir)
    return dialog.result


def styled_ask_directory(title, initial_dir=None):
    """Open a custom styled directory dialog."""

    # For directory selection, we can use the same dialog but only show directories
    class DirDialog(StyledFileDialog):
        def build_ui(self):
            # Path entry
            path_frame = tkinter.Frame(self.dialog, bg="#1e1e1e")
            path_frame.pack(fill="x", padx=10, pady=5)

            tkinter.Label(path_frame, text="Path:", bg="#1e1e1e", fg="#ffffff").pack(
                side="left"
            )

            self.path_var = StringVar(value=str(self.current_path))
            path_entry = tkinter.Entry(
                path_frame,
                textvariable=self.path_var,
                bg="#2d2d2d",
                fg="#ffffff",
                insertbackground="#ffffff",
            )
            path_entry.pack(side="left", fill="x", expand=True, padx=5)
            path_entry.bind("<Return>", lambda e: self.navigate_to(self.path_var.get()))

            go_btn = tkinter.Button(
                path_frame,
                text="Go",
                command=lambda: self.navigate_to(self.path_var.get()),
                bg="#3d3d3d",
                fg="#ffffff",
                activebackground="#4d4d4d",
                relief="flat",
            )
            go_btn.pack(side="left", padx=2)

            up_btn = tkinter.Button(
                path_frame,
                text="↑",
                command=self.go_up,
                bg="#3d3d3d",
                fg="#ffffff",
                activebackground="#4d4d4d",
                relief="flat",
                width=3,
            )
            up_btn.pack(side="left", padx=2)

            # File list frame
            list_frame = tkinter.Frame(self.dialog, bg="#1e1e1e")
            list_frame.pack(fill="both", expand=True, padx=10, pady=5)

            yscroll = Scrollbar(list_frame, orient="vertical")
            yscroll.pack(side="right", fill="y")

            xscroll = Scrollbar(list_frame, orient="horizontal")
            xscroll.pack(side="bottom", fill="x")

            self.file_list = tkinter.Listbox(
                list_frame,
                bg="#2d2d2d",
                fg="#ffffff",
                selectbackground="#0d47a1",
                selectforeground="#ffffff",
                font=("Consolas", 10),
                yscrollcommand=yscroll.set,
                xscrollcommand=xscroll.set,
                borderwidth=0,
                highlightthickness=1,
                highlightbackground="#3d3d3d",
                highlightcolor="#4d4d4d",
            )
            self.file_list.pack(side="left", fill="both", expand=True)
            yscroll.config(command=self.file_list.yview)
            xscroll.config(command=self.file_list.xview)

            self.file_list.bind("<Double-Button-1>", self.on_double_click)
            self.file_list.bind("<Return>", self.on_double_click)

            # Buttons
            btn_frame = tkinter.Frame(self.dialog, bg="#1e1e1e")
            btn_frame.pack(fill="x", padx=10, pady=10)

            tkinter.Button(
                btn_frame,
                text="Select",
                command=self.select_directory,
                bg="#0d47a1",
                fg="#ffffff",
                activebackground="#1565c0",
                relief="flat",
                padx=20,
            ).pack(side="right", padx=5)

            tkinter.Button(
                btn_frame,
                text="Cancel",
                command=self.dialog.destroy,
                bg="#3d3d3d",
                fg="#ffffff",
                activebackground="#4d4d4d",
                relief="flat",
                padx=20,
            ).pack(side="right", padx=5)

        def refresh_list(self):
            self.file_list.delete(0, "end")
            try:
                for item in sorted(self.current_path.iterdir()):
                    if item.name.startswith("."):
                        continue
                    if item.is_dir():
                        self.file_list.insert("end", item.name + "/")
            except PermissionError:
                pass

        def select_directory(self):
            self.result = str(self.current_path)
            self.dialog.destroy()

    dialog = DirDialog(title, [("Folder", "*")], initial_dir)
    return dialog.result


# --- GUI setup ---
root = tkinter.Tk()
root.title("KiCad Symbol and Footprint Installer")
root.geometry("600x900")
root.resizable(False, False)

# Set modern theme (light or dark)


# Set window icon (will use first available)
icon_paths = [
    "/usr/share/icons/hicolor/48x48/apps/kicad.png",
    "/usr/share/pixmaps/kicad.png",
    "/usr/share/icons/Zorin/scalable/apps/utilities-terminal.svg",
]
for icon_path in icon_paths:
    if os.path.exists(icon_path):
        try:
            root.iconphoto(False, PhotoImage(file=icon_path))
            break
        except Exception:
            pass

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
    """Not used - kept for compatibility."""
    return None


def add_symbol_to_lib(lib_file, symbol_content):
    """Not used."""
    return False


# --- Footprint library handling ---
def create_uploaded_footprint_lib(path_root, suffix=""):
    """Ensure Uploaded[_suffix].pretty exists and is registered in fp-lib-table."""
    footprint_dir = get_footprint_dir(path_root)
    if not footprint_dir:
        pymsgbox.alert(
            "Could not find footprint library directory",
            "Error",
            # iconType not supported by pymsgbox
        )
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
path = None  # Global variable to store KiCad library path


def setup_kicad_path():
    """Setup KiCad path after GUI is ready."""
    global path

    if path_exist:
        with open("kicad_path.txt", "r") as f:
            path = f.read()
        return

    # Show message and prompt for directory after window is ready
    pymsgbox.alert(
        "Please select the folder containing your KiCad user libraries (sym-lib-table / fp-lib-table).",
        "Select Your KiCad Library Folder",
    )

    # Use tkinter's built-in directory picker (more reliable)
    path = filedialog.askdirectory(title="Select KiCad Library Folder")

    if not path or not is_kicad_lib_path(path):
        pymsgbox.alert(
            "Selected folder is not a valid KiCad library folder.",
            "Invalid Library Path",
            # iconType not supported by pymsgbox
        )
        exit()

    with open("kicad_path.txt", "w") as f:
        f.write(path)


# --- GUI callbacks ---
def upload_symbol():
    global symbolpath
    symbolpath = filedialog.askopenfilename(
        title="Select Symbol File",
        filetypes=[("KiCad Symbol Files", "*.kicad_sym"), ("All Files", "*.*")],
    )
    if symbolpath:
        selectedfilesym.config(text=os.path.basename(symbolpath))


def upload_footprint():
    global footprintpath
    footprintpath = filedialog.askopenfilename(
        title="Select Footprint File",
        filetypes=[("KiCad Footprint Files", "*.kicad_mod"), ("All Files", "*.*")],
    )
    if footprintpath:
        selectedfilefoot.config(text=os.path.basename(footprintpath))


def upload_step():
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
    global upload_count
    if not symbolpath and not footprintpath:
        pymsgbox.alert(
            "Please select at least a symbol or footprint file",
            "Error",
            # iconType not supported by pymsgbox
        )
        return

    try:
        progress["value"] = 0
        root.update()

        suffix = suffix_var.get().strip()
        lib_path = None

        # --- Symbol ---
        # Upload as individual .kicad_sym file registered in sym-lib-table
        if symbolpath and symbolpath != "No path chosen":
            symbol_dir = get_symbol_dir(path)
            if symbol_dir and os.path.exists(symbolpath):
                filename = os.path.basename(symbolpath)
                dest = os.path.join(symbol_dir, filename)

                # Copy if doesn't exist
                if not os.path.exists(dest):
                    with open(symbolpath, "r", encoding="utf-8") as f:
                        content = f.read().lstrip()
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write(content)

                # Register in sym-lib-table
                sym_table_path = os.path.join(symbol_dir, "sym-lib-table")
                lib_name = os.path.splitext(filename)[0]
                if os.path.exists(sym_table_path):
                    with open(sym_table_path, "r") as f:
                        content = f.read()
                    if (
                        f'"{lib_name}"' not in content
                        and os.path.basename(dest) not in content
                    ):
                        entry = f'  (lib (name "{lib_name}") (type "KiCad") (uri "{dest}") (options "") (descr "Uploaded symbol"))\n'
                        content = content.rstrip()
                        if content.endswith(")"):
                            content = content[:-1]
                        content = content + entry + ")\n"
                        with open(sym_table_path, "w") as f:
                            f.write(content)

                progress["value"] = 50
                root.update()

        # --- Footprint ---
        if footprintpath and footprintpath != "No path chosen":
            lib_path = create_uploaded_footprint_lib(path, suffix)
            if lib_path:
                # Check if footprint already exists in library by comparing content
                footprint_basename = os.path.basename(footprintpath)
                existing_files = os.listdir(lib_path)
                file_exists = False
                for f in existing_files:
                    f_path = os.path.join(lib_path, f)
                    if os.path.isfile(f_path):
                        try:
                            with (
                                open(footprintpath, "rb") as sf,
                                open(f_path, "rb") as df,
                            ):
                                if sf.read() == df.read():
                                    file_exists = True
                                    break
                        except:
                            pass

                if not file_exists:
                    dest = get_unique_filename(lib_path, footprint_basename)
                    copy_with_progress(footprintpath, dest, 40)

        # --- Optional STEP ---
        if steppath and steppath != "No path chosen":
            if lib_path:
                step_dest = get_unique_filename(lib_path, os.path.basename(steppath))
                copy_with_progress(steppath, step_dest, 10)

        progress["value"] = 100
        upload_count += 1
    except Exception as e:
        pymsgbox.alert(f"Failed to upload files: {e}", "Error")


# --- GUI layout ---
sv_ttk.set_theme("dark")
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

# --- SnapEDA Search Section ---
ttk.Separator(root, orient="horizontal").pack(fill="x", pady=20)

ttk.Label(root, text="SnapEDA Component Search", font=("Arial", 14, "bold")).pack(
    pady=10
)
ttk.Label(
    root,
    text="Search & download components from snapeda.com",
    font=("Arial", 9),
    foreground="gray",
).pack(pady=5)
ttk.Button(
    root,
    text="🔍 Open SnapEDA Search",
    command=open_snapeda_search,
    style="Accent.TButton",
).pack(pady=10)

ttk.Separator(root, orient="horizontal").pack(fill="x", pady=20)

ttk.Button(root, text="Send to KiCad", command=upload_data).pack(pady=20)

# Setup KiCad path (show dialog if first run) - must be after GUI is ready
setup_kicad_path()

root.mainloop()
