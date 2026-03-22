#!/usr/bin/env python3
"""
CLI tool to upload KiCad symbols, footprints, and 3D models.
"""

import argparse
import os
import shutil
from pathlib import Path


def find_kicad_subdir(root_path, table_file):
    """Recursively find subdirectory containing the table_file."""
    for dirpath, dirnames, filenames in os.walk(root_path):
        if table_file in filenames:
            return dirpath
    return None


def get_symbol_dir(root_path):
    return find_kicad_subdir(root_path, "sym-lib-table")


def get_footprint_dir(root_path):
    return find_kicad_subdir(root_path, "fp-lib-table")


def get_unique_filename(dest_dir, filename):
    """Generate unique filename to prevent overwrites."""
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


def create_uploaded_symbol_lib(path_root, suffix=""):
    """Not used - kept for compatibility."""
    return None


def add_symbol_to_lib(lib_file, symbol_content):
    """Not used."""
    return False


def create_uploaded_lib(path_root, suffix=""):
    """Prepare a footprint library folder and register it in fp-lib-table."""
    footprint_dir = get_footprint_dir(path_root)
    if not footprint_dir:
        print(f"Error: Could not find footprint library directory in {path_root}")
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


def upload(
    kicad_path, symbol=None, footprint=None, step=None, suffix="", verbose=False
):
    """Upload files to KiCad library."""
    if not os.path.isdir(kicad_path):
        print(f"Error: {kicad_path} is not a valid directory")
        return False

    if not symbol and not footprint and not step:
        print("Error: No files to upload. Specify --symbol, --footprint, and/or --step")
        return False

    success = True
    lib_path = None

    # Upload symbol - individual .kicad_sym file registered in sym-lib-table
    if symbol:
        if not os.path.exists(symbol):
            print(f"Error: Symbol file not found: {symbol}")
            success = False
        else:
            symbol_dir = get_symbol_dir(kicad_path)
            if symbol_dir:
                filename = os.path.basename(symbol)
                dest = os.path.join(symbol_dir, filename)

                # Copy if doesn't exist
                if not os.path.exists(dest):
                    with open(symbol, "r", encoding="utf-8") as f:
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

                print(f"Symbol uploaded to: {dest}")
            else:
                print("Error: Could not find symbol library directory")
                success = False

    # Upload footprint
    if footprint:
        if not os.path.exists(footprint):
            print(f"Error: Footprint file not found: {footprint}")
            success = False
        else:
            lib_path = create_uploaded_lib(kicad_path, suffix)
            if lib_path:
                dest = get_unique_filename(lib_path, os.path.basename(footprint))
                shutil.copy2(footprint, dest)
                print(f"Footprint uploaded: {dest}")
            else:
                print("Error: Could not prepare footprint library")
                success = False

    # Upload 3D model
    if step:
        if not os.path.exists(step):
            print(f"Error: STEP file not found: {step}")
            success = False
        else:
            if not lib_path:
                lib_path = create_uploaded_lib(kicad_path, suffix)
            if lib_path:
                dest = get_unique_filename(lib_path, os.path.basename(step))
                shutil.copy2(step, dest)
                print(f"3D model uploaded: {dest}")
            else:
                print("Error: Could not prepare footprint library")
                success = False

    if success:
        print("Upload complete!")
    else:
        print("Upload failed!")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Upload KiCad symbols, footprints, and 3D models"
    )
    parser.add_argument(
        "kicad_path",
        help="Path to KiCad library directory (containing sym-lib-table and fp-lib-table)",
    )
    parser.add_argument("-s", "--symbol", help="Path to .kicad_sym symbol file")
    parser.add_argument("-f", "--footprint", help="Path to .kicad_mod footprint file")
    parser.add_argument("-3", "--step", help="Path to .step/.stp 3D model file")
    parser.add_argument(
        "--suffix",
        help="Suffix for library name (e.g., 'mylib' creates Uploaded_mylib.pretty)",
        default="",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()

    upload(
        args.kicad_path,
        symbol=args.symbol,
        footprint=args.footprint,
        step=args.step,
        suffix=args.suffix,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
