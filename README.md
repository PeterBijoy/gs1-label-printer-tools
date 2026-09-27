# GS1 Label Printer Tools

Two Windows desktop apps for generating and printing GS1-compliant barcode
labels from an Excel sheet, sharing a common codebase:

- **[`GS1LabelPrinter/`](GS1LabelPrinter/)** — GTIN-based product labels
  (AI 01 GTIN, 10 Batch, 17 Expiry, 21 Serial, 30 Quantity).
- **[`SSCCLabelPrinter/`](SSCCLabelPrinter/)** — SSCC-based logistics/pallet
  labels (AI 00 SSCC, 02 Content GTIN, 10 Batch, 17 Expiry, 37 Count), built
  for bulk sheets of hundreds/thousands of SSCCs processed in sequence.

Both apps support:
- GS1-128, GS1 DataMatrix, GS1 QR Code, and QR Code with GS1 Digital Link
  syntax, with per-symbology GS1-compliant module (X-dimension) sizing.
- Configurable label width x height (not just square).
- Header text and footer text fields, independent of the barcode data.
- Printing directly to a network label printer (raw ZPL over TCP/9100),
  including a media-calibration command for gap/black-mark sensed stock.
- Printing via an installed Windows printer driver, letting the driver own
  DPI/page size and reporting back what was actually used.

See each app's own README for build steps, the Excel column format, and
troubleshooting. For a guided walkthrough, see:
- **[`SETUP_GUIDE.md`](SETUP_GUIDE.md)** — installing prerequisites,
  getting the code, running from source, building the `.exe`, and
  building a distributable installer.
- **[`USER_GUIDE.md`](USER_GUIDE.md)** — preparing your Excel file,
  mapping columns, choosing a barcode symbology, generating labels, and
  printing (network ZPL or Windows driver).

## Shared modules

Both apps vendor identical copies of:
- `gs1_utils.py` — GS1 check digits, AI formatting, bracketed element
  strings, GS1 Digital Link URIs.
- `label_generator.py` — wraps the bundled `zint.exe` to render barcodes
  and composes the final label image.
- `zpl_printer.py` — image-to-ZPL conversion and raw TCP printing.
- `driver_printer.py` — Windows GDI printing via an installed driver
  (Windows-only; imported behind a try/except so the app still runs
  without it, e.g. during development on non-Windows).

If you change one of these files, mirror the change into the other app's
copy.

## Building

Each app builds independently on Windows (Python 3.10+):

```
cd GS1LabelPrinter && build.bat
cd SSCCLabelPrinter && build.bat
```

This runs PyInstaller in `--onedir` mode (a folder, not a single portable
exe — see that app's README for why) and requires `bin/zint.exe` to
already be present, a statically-linked Windows build of the
[Zint barcode library](https://github.com/zint/zint) cross-compiled from
source via mingw-w64 (see each app's README, "Zint provenance").

To package either app into a single distributable installer, open
`installer.iss` in Inno Setup (or run `iscc installer.iss`) after
building.
