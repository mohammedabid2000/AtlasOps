# Rebuild the handbook

The complete PDF is included as `docs/AtlasOps_DevOps_Handbook.pdf`. Its editable narrative lives in `tools/assemble_handbook.py` and the referenced Markdown documents under `docs/`. The assembler regenerates `docs/HANDBOOK.md`; edit the original sources rather than the assembled file.

On Ubuntu, install the `fonts-dejavu-core` package if DejaVu fonts are missing. Use a separate Python environment to keep document dependencies separate from the application:

```bash
python3 -m venv /tmp/atlasops-pdf-venv
/tmp/atlasops-pdf-venv/bin/pip install reportlab==4.4.9
/tmp/atlasops-pdf-venv/bin/python tools/assemble_handbook.py
/tmp/atlasops-pdf-venv/bin/python tools/build_handbook.py
```

The renderer creates an A4 PDF with clickable contents, bookmarks and vector architecture diagrams. If Poppler is installed, render it for visual review:

```bash
mkdir -p /tmp/atlasops-pdf-preview
pdftoppm -scale-to 1200 -png docs/AtlasOps_DevOps_Handbook.pdf /tmp/atlasops-pdf-preview/page
```

Review page breaks, table columns, code wrapping and links after editing. PDF code blocks may wrap for print layout; use the repository files when executing or modifying long commands.
