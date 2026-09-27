# Setup Guide

This guide covers getting **GS1 Label Printer** (GTIN-based product labels)
and **SSCC Label Printer** (SSCC-based logistics/pallet labels) running on
a Windows computer from this repository, whether you want to run them
from source (for development/testing) or build the standalone `.exe`.

Both apps live in this one repository and share the same setup steps:
- [`GS1LabelPrinter/`](GS1LabelPrinter/) — product labels (GTIN, batch,
  expiry, serial, quantity)
- [`SSCCLabelPrinter/`](SSCCLabelPrinter/) — logistics/pallet labels
  (SSCC, content GTIN, batch, expiry, count)

Everything below applies to either folder — just swap the folder name and
the app filename (`app.py` vs `app_sscc.py`) as you go.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Windows 10 or 11 | The apps use Tkinter (built into Python) and, for driver printing, `pywin32` — both Windows-specific for the printing features, though the barcode-generation logic itself is plain Python. |
| Python 3.10 or later | [python.org/downloads](https://www.python.org/downloads/) — during install, check **"Add python.exe to PATH"**. |
| Git (optional, for cloning) | [git-scm.com](https://git-scm.com/downloads) — or just download the repo as a ZIP from GitHub instead. |
| Inno Setup (optional) | Only needed if you want to build a distributable installer `Setup.exe`. [jrsoftware.org/isinfo.php](https://jrsoftware.org/isinfo.php) |

**Checking your Python install:**

Open **Command Prompt** and run:

```
python --version
```

You should see `Python 3.10.x` or higher. If you instead see an error or
it opens the Microsoft Store, Python isn't installed correctly — reinstall
from python.org and make sure "Add to PATH" was checked.

---

## 2. Get the code

**Option A — clone with Git:**

```
git clone https://github.com/PeterBijoy/gs1-label-printer-tools.git
cd gs1-label-printer-tools
```

**Option B — download as ZIP:**

On the repo's GitHub page, click **Code → Download ZIP**, then extract it
anywhere on your computer (e.g. `C:\Users\<you>\Documents\`).

Either way, you should end up with a folder containing `GS1LabelPrinter\`
and `SSCCLabelPrinter\` as subfolders.

---

## 3. Running the app from source (no build needed)

This is the fastest way to try the app or make changes to it.

1. Open Command Prompt and navigate into the app folder you want to run,
   e.g.:
   ```
   cd gs1-label-printer-tools\SSCCLabelPrinter
   ```
2. Install the Python dependencies:
   ```
   python -m pip install -r requirements.txt
   ```
3. Run the app directly:
   ```
   python app_sscc.py
   ```
   (For the GTIN app, `cd GS1LabelPrinter` and run `python app.py` instead.)

The app window should open. `bin\zint.exe` is already included in the
repo, so no separate barcode-library install is needed.

> If step 3 fails with `ModuleNotFoundError: No module named 'tkinter'`,
> your Python install is missing Tkinter — reinstall Python from
> python.org (the official installer includes it by default; some
> minimal/embeddable distributions strip it out).

---

## 4. Building a standalone `.exe`

This packages the app (plus the bundled `zint.exe` and all Python
dependencies) into a folder you can run without Python installed, using
[PyInstaller](https://pyinstaller.org/).

1. Open Command Prompt in the app folder (e.g. `SSCCLabelPrinter\`).
2. Run:
   ```
   build.bat
   ```
   This installs dependencies (if not already installed) and runs
   PyInstaller in `--onedir` mode.
3. When it finishes, you'll find:
   ```
   dist\SSCCLabelPrinter\SSCCLabelPrinter.exe
   ```
   (or `dist\GS1LabelPrinter\GS1LabelPrinter.exe` for the other app.)

**Important:** `--onedir` mode produces a *folder*, not a single portable
file — `SSCCLabelPrinter.exe` depends on the other files sitting next to
it in that same folder. Keep the whole `dist\SSCCLabelPrinter\` folder
together when you copy it to another machine; don't just copy the `.exe`
by itself.

> **Why a folder instead of one file?** PyInstaller's alternative
> `--onefile` mode bundles everything into a single exe that
> self-extracts to a temp folder every time it runs — a pattern commonly
> flagged by antivirus software as suspicious. `--onedir` avoids that
> self-extraction step, which is friendlier to Windows Defender and
> similar tools when you hand the app to someone else.

**If `build.bat` fails at the PyInstaller step** with `'pyinstaller' is
not recognized`, it usually means Python's `Scripts` folder isn't on your
PATH. `build.bat` already works around this by calling
`python -m PyInstaller` rather than the bare `pyinstaller` command, so if
you still hit this, confirm `python -m pip install -r requirements.txt`
actually completed successfully first.

---

## 5. Building a distributable installer (optional)

If you want to hand the app to someone else as a single `Setup.exe`
(rather than a folder they have to keep together), use the included Inno
Setup script:

1. Complete step 4 above first (you need `dist\...\` to already exist).
2. Install [Inno Setup](https://jrsoftware.org/isinfo.php) if you haven't
   already.
3. Open `installer.iss` (in the same app folder) by double-clicking it —
   this opens the Inno Setup Compiler.
4. Click **Build → Compile** (or press F9).
5. The finished installer appears in an `Output\` folder as
   `GS1LabelPrinter_Setup.exe` or `SSCCLabelPrinter_Setup.exe`.

Anyone who runs that `Setup.exe` gets a normal Windows install: Start Menu
shortcut, optional desktop icon, and an uninstaller — without needing
Python or any of the build tooling above.

> If Windows SmartScreen or your antivirus flags the installer as
> unrecognized when you first run it (common for any newly-built,
> unsigned executable — this is not specific to this app), see each app's
> own README ("Zint provenance" / troubleshooting sections) for more on
> why that happens and how to get it cleared.

---

## 6. Updating an existing local copy

If you already cloned the repo and want to pull the latest changes:

```
cd gs1-label-printer-tools
git pull
```

Then repeat step 3 or step 4 above to run or rebuild.

---

## Quick troubleshooting

| Problem | Likely cause / fix |
|---|---|
| `python` not recognized | Python isn't on PATH — reinstall with "Add to PATH" checked, or use the full path to `python.exe`. |
| `No module named 'tkinter'` | Reinstall Python from python.org (not a minimal distribution). |
| `zint.exe` not found when running the app | Make sure you're running from inside the app's own folder (`GS1LabelPrinter\` or `SSCCLabelPrinter\`) — it looks for `bin\zint.exe` relative to itself. |
| `build.bat` says `dist\...\....exe` was not created | Scroll up in the Command Prompt output for the actual PyInstaller error — usually a missing dependency; re-run `python -m pip install -r requirements.txt`. |
| App window opens but printer features are grayed out | Windows-driver printing needs `pywin32`, which only installs/works on Windows — this is expected if you're testing on another OS. |

For how to actually use the app once it's running — loading Excel data,
mapping columns, choosing a barcode type, and printing — see
[`USER_GUIDE.md`](USER_GUIDE.md).
