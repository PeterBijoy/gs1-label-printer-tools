# GS1 Label Printer

A Windows desktop app for generating and printing GS1-compliant product
labels (GTIN / batch / expiry / serial / quantity) from an Excel sheet, in
GS1-128, GS1 DataMatrix, GS1 QR Code, or QR Code with GS1 Digital Link
syntax.

## What it does

1. Load an Excel file (`.xlsx`) of product data.
2. Map spreadsheet columns to GS1 Application Identifiers.
3. Choose a barcode symbology and (optionally) override its module size.
4. Generate one label image per row, sized to whatever width x height you
   configure.
5. Print all labels in sequence -- either straight to a network label
   printer (ZPL) or via an installed Windows printer driver.

## Building

Requires Python 3.10+ on Windows.

```
build.bat
```

This installs dependencies and runs PyInstaller in **`--onedir`** mode. The
result is a folder:

```
dist\GS1LabelPrinter\
    GS1LabelPrinter.exe
    ... (supporting DLLs/files -- keep them together)
```

> **Why `--onedir` instead of a single portable exe?** PyInstaller's
> `--onefile` mode bundles everything into one exe that self-extracts to a
> temp folder every time it runs. That self-extraction step is a common
> antivirus heuristic trigger, and is the main reason a freshly-built
> `--onefile` exe can get flagged/quarantined by Windows Defender or other
> AV products on a machine that hasn't seen it before. `--onedir` ships the
> same files already unpacked, so there's no runtime self-extraction step,
> which meaningfully reduces false-positive risk when you hand the app to
> someone else. The trade-off: you now distribute/move the whole
> `GS1LabelPrinter` folder together, not a single file. `installer.iss`
> (below) packages that folder into a normal one-file Setup.exe for
> distribution, so end users still only ever handle one file.

`bin\zint.exe` must exist before building (a statically-linked, portable
Windows build of the [Zint barcode library](https://github.com/zint/zint),
cross-compiled from source via mingw-w64 -- see "Zint provenance" below).

## Zint provenance

`bin\zint.exe` is built from the unmodified Zint source
(https://github.com/zint/zint) using a mingw-w64 cross-compiler, with:

```
cmake .. -DCMAKE_TOOLCHAIN_FILE=toolchain-mingw64.cmake \
  -DZINT_SHARED=OFF -DZINT_STATIC=ON -DZINT_FRONTEND=ON \
  -DZINT_USE_QT=OFF -DZINT_USE_PNG=OFF -DZINT_USE_GS1SE=OFF
```

This produces a genuinely portable executable that depends only on
`KERNEL32.dll` and `msvcrt.dll` (both present on every Windows install --
no separate Zint installation, Qt runtime, or Visual C++ redistributable
needed).

## Excel format

| Column example | Maps to |
|---|---|
| GTIN | AI 01 |
| Batch / Lot | AI 10 |
| Expiry | AI 17 |
| Serial | AI 21 |
| Quantity | AI 30 |
| Header text | printed above the barcode |
| Footer text | printed below everything |
| Extra AI data | any additional bracketed AI, e.g. `(91)TEXT` |

Column names don't need to match exactly -- the app makes a best-effort
auto-mapping guess, and you can always change the mapping in section 2 of
the app.

If your sheet has **no header row** (the first row is already data),
un-check "First row is a header row" before loading -- otherwise the first
row of real data would be mistaken for column headers and dropped. The app
also warns you if it looks like your "header" row is actually data.

## Symbology & module size

| Symbology | GS1 min X-dim | GS1 nominal X-dim | GS1 max X-dim |
|---|---|---|---|
| GS1-128 | 0.264mm | 0.330mm | 0.660mm |
| GS1 DataMatrix | 0.255mm | 0.495mm | 0.990mm |
| GS1 QR Code | 0.396mm | 0.495mm | 0.990mm |
| QR Code (GS1 Digital Link) | 0.396mm | 0.495mm | 0.990mm |

(Source: GS1 General Specifications, section 5.12.3.1. GS1 requires 2D
symbols to use an X-dimension at least 1.5x the linear minimum.)

Leave "Module size" blank to use each symbology's GS1 nominal value. If a
barcode doesn't fit the configured label width, the app automatically
shrinks the X-dimension in small steps -- but never below the symbology's
GS1-specified minimum -- and will warn you if it still doesn't fit.

**Human-readable text:** Zint natively prints human-readable text under
GS1-128 barcodes. It does not do this for 2D symbols (DataMatrix, QR), so
the app draws that text itself for those symbologies.

## Network printing (ZPL)

Enter the printer's IP address and port (default 9100, standard raw
JetDirect-style printing) and click "Send All to Network Printer". Each
label is converted to ZPL (`^GFA` graphic field) and sent directly over
TCP, with a short delay between labels so the printer's buffer keeps up.

**Calibration:** if labels start printing across the wrong physical
sticker (drifting), click "Calibrate Printer" once after loading a new
roll of label stock. This sends a `~JC` media-calibration command so the
printer re-measures the gaps between labels.

## Printing via a Windows printer driver

As an alternative to raw ZPL, choose an installed Windows printer from the
dropdown and click "Send All via Printer Driver". This uses the driver's
own Printing Preferences to own DPI and page size -- the app requests your
configured label width/height as a custom page size, but if the driver
doesn't support that, it falls back to the driver's own default and tells
you (in the log) what DPI and printable area were actually used, and
whether your custom size was honored. The rendered label is never
upscaled beyond its native resolution.

## Troubleshooting

- **"zint failed" / barcode not generated** -- check that `bin\zint.exe`
  is present next to the exe (or, when built, inside the `_internal`
  folder PyInstaller creates in `--onedir` mode).
- **Barcode too big / doesn't fit the label** -- lower the module size, or
  increase the label width/height. The app will auto-shrink toward the
  GS1 minimum but won't go below it.
- **Only some labels print** -- check the Log panel; each row is reported
  individually as OK/sent/skipped/failed with a reason.
- **Labels print across the wrong physical label** -- run "Calibrate
  Printer".
