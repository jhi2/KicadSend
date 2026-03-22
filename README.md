# KicadSend

Upload KiCad symbols, footprints, and 3D models to your local library with ease.

## What is KicadSend?

KicadSend is a simple tool to help you quickly add custom components to your KiCad libraries without manually managing library tables. Just select your files, click upload, and they're registered and ready to use.

## Features

- **Dual Interface**: Choose between GUI or CLI based on your workflow
- **Smart Library Management**: Auto-detects your KiCad library location
- **Multiple File Types**: Supports `.kicad_sym`, `.kicad_mod`, and `.step`/.stp` 3D models
- **Custom Libraries**: Create separate footprint libraries with custom suffixes
- **Duplicate Prevention**: Won't re-upload files that already exist in your library
- **Progress Feedback**: Visual progress bar for large files

## Requirements

- Python 3.10+
- KiCad 9.0+ installed

## Installation

```bash
pip install -r requirements.txt
```

## GUI Version (main.py)

Launch the graphical interface:

```bash
python main.py
```

On first run, select your KiCad user library folder (contains `sym-lib-table` and `fp-lib-table`).

### GUI Features:
- Styled dark-themed file browser
- Drag-and-drop style file selection
- Progress tracking during upload

## CLI Version (cli.py)

For automation or scripting:

```bash
# Upload a symbol
python cli.py ~/.config/kicad/9.0 -s symbol.kicad_sym

# Upload a footprint
python cli.py ~/.config/kicad/9.0 -f footprint.kicad_mod

# Upload with custom library suffix
python cli.py ~/.config/kicad/9.0 -f footprint.kicad_mod --suffix mylib

# Upload all at once
python cli.py ~/.config/kicad/9.0 -s symbol.kicad_sym -f footprint.kicad_mod -3 model.step
```

### CLI Options

| Option | Description |
|--------|-------------|
| `-s, --symbol` | Path to `.kicad_sym` symbol file |
| `-f, --footprint` | Path to `.kicad_mod` footprint file |
| `-3, --step` | Path to `.step`/`.stp` 3D model |
| `--suffix` | Suffix for library (e.g., `mylib` creates `Uploaded_mylib.pretty`) |
| `-v, --verbose` | Enable verbose output |

## How It Works

### Architecture
```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Symbol Files  │────▶│   KiCad User     │────▶│  sym-lib-table  │
│  (.kicad_sym)  │     │   Library Dir    │     │   Registration │
└─────────────────┘     └──────────────────┘     └─────────────────┘

┌──────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Footprint Files │────▶│ Uploaded.pretty  │────▶│ fp-lib-table   │
│  (.kicad_mod)    │     │   (or custom)    │     │ Registration   │
└──────────────────┘     └──────────────────┘     └────────────────┘
```

### What Gets Created

- **Symbols**: Copied to your KiCad symbol directory and registered in `sym-lib-table` as individual libraries
- **Footprints**: Copied to `Uploaded.pretty` (or `Uploaded_suffix.pretty`) folder and registered in `fp-lib-table`
- **3D Models**: Copied to the same `.pretty` folder as the footprint

##⚠️ Important

After uploading, **restart KiCad** to see your new libraries.

The tool creates or updates the following in your KiCad user directory:
- `Uploaded.pretty/` - footprint library folder
- `sym-lib-table` - updated with new symbol entries
- `fp-lib-table` - updated with new footprint library

## Troubleshooting

### "Could not find footprint library directory"
Your selected folder isn't a valid KiCad library folder. It must contain either `sym-lib-table` or `fp-lib-table`.

### Libraries not appearing in KiCad
Make sure to restart KiCad after uploading. Library tables are read at startup.

### Duplicate files
The tool automatically checks if files already exist by comparing content, so won't re-upload duplicates.

## License

MIT License