#!/usr/bin/env python3
"""CLI tool to upload KiCad symbols, footprints, and 3D models."""

import argparse
import os

from kicad_send import (
    get_symbol_dir,
    get_footprint_dir,
    ensure_footprint_lib,
    import_symbol,
    import_footprint,
    import_step_model,
)


def upload(
    kicad_path: str,
    symbol=None,
    footprint=None,
    step=None,
    suffix: str = "",
    verbose: bool = False,
) -> bool:
    """Upload files to KiCad library."""
    if not os.path.isdir(kicad_path):
        print(f"Error: {kicad_path} is not a valid directory")
        return False

    if not symbol and not footprint and not step:
        print("Error: No files to upload. Specify --symbol, --footprint, and/or --step")
        return False

    success = True

    # Upload symbol
    if symbol:
        if os.path.exists(symbol):
            if import_symbol(kicad_path, symbol):
                print(f"Symbol uploaded: {os.path.basename(symbol)}")
            else:
                print("Error: Could not upload symbol")
                success = False
        else:
            print(f"Error: Symbol file not found: {symbol}")
            success = False

    # Upload footprint
    if footprint:
        if os.path.exists(footprint):
            lib_path = ensure_footprint_lib(kicad_path, suffix)
            if lib_path:
                dest = os.path.join(lib_path, os.path.basename(footprint))
                if not os.path.exists(dest):
                    with open(footprint, "rb") as src, open(dest, "wb") as dst:
                        dst.write(src.read())
                print(f"Footprint uploaded: {dest}")
            else:
                print("Error: Could not prepare footprint library")
                success = False
        else:
            print(f"Error: Footprint file not found: {footprint}")
            success = False

    # Upload 3D model
    if step:
        if os.path.exists(step):
            lib_path = ensure_footprint_lib(kicad_path, suffix)
            if lib_path:
                dest = os.path.join(lib_path, os.path.basename(step))
                if not os.path.exists(dest):
                    with open(step, "rb") as src, open(dest, "wb") as dst:
                        dst.write(src.read())
                print(f"3D model uploaded: {dest}")
            else:
                print("Error: Could not prepare footprint library")
                success = False
        else:
            print(f"Error: STEP file not found: {step}")
            success = False

    if success:
        print("Upload complete!")
    else:
        print("Upload failed with errors.")

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
