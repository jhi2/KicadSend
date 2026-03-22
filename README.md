# ALERT! THE APP CORrUPTS YOUR SYM-LIB-TABLE AND FP-LIB-TABLE! I WILL SEND A FIX SOON.
# KiCad Uploader

Upload KiCad symbols, footprints, and 3D models to your local library.

## Installation

```bash
pip install -r requirements.txt
```

## GUI Version (main.py)

```bash
python main.py
```

Features:
- Select KiCad library folder (first run)
- Upload symbol files (.kicad_sym)
- Upload footprint files (.kicad_mod)
- Upload 3D models (.step/.stp)
- Custom library suffix (e.g., "mylib" creates Uploaded_mylib.pretty)
- Progress bar with file-size weighting

## CLI Version (cli.py)

```bash
# Upload a symbol
python cli.py ~/.config/kicad/9.0 -s symbol.kicad_sym

# Upload a footprint
python cli.py ~/.config/kicad/9.0 -f footprint.kicad_mod

# Upload footprint with custom suffix
python cli.py ~/.config/kicad/9.0 -f footprint.kicad_mod --suffix mylib

# Upload all three
python cli.py ~/.config/kicad/9.0 -s symbol.kicad_sym -f footprint.kicad_mod -3 model.step
```

Options:
- `-s, --symbol` - Path to .kicad_sym file
- `-f, --footprint` - Path to .kicad_mod file
- `-3, --step` - Path to .step/.stp 3D model
- `--suffix` - Suffix for library name
- `-v, --verbose` - Verbose output

## How it works

- **Symbols**: Copied directly to the KiCad symbol library folder and registered in sym-lib-table as separate libraries
- **Footprints**: Copied to `Uploaded.pretty` (or `Uploaded_suffix.pretty`) folder and registered in fp-lib-table
- **3D Models**: Copied to the same .pretty folder as the footprint

Restart KiCad after uploading to load the new libraries.
