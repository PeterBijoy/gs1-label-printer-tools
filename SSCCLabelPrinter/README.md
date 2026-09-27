# SSCC Label Printer

A Windows desktop app for generating and printing GS1-compliant logistics
labels (SSCC / content GTIN / batch / expiry / count) from an Excel sheet
of hundreds or thousands of SSCCs, in GS1-128, GS1 DataMatrix, GS1 QR
Code, or QR Code with GS1 Digital Link syntax.

## What it does

1. Load an Excel file (`.xlsx`) of SSCCs (and optional content data).
2. Map spreadsheet columns to GS1 Application Identifiers.
3. Choose a barcode symbology and (optionally) override its module size.
4. Generate one label image per row, sized to whatever width x height you
   configure -- bulk sheets of hundreds/thousands of SSCCs are processed
   and printed in sequence.
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
dist\SSCCLabelPrinter\
    SSCCLabelPrinter.exe
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
> `SSCCLabelPrinter` folder together, not a single file. `installer.iss`
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
| SSCC | AI 00 |
| Content GTIN | AI 02 |
| Batch / Lot | AI 10 |
| Expiry | AI 17 |
| Count | AI 37 |
| Header text | printed above the barcode |
| Footer text | printed below everything |
| Extra AI data | any additional bracketed AI, e.g. `(91)TEXT` |

Column names don't need to match exactly -- the app makes a best-effort
auto-mapping guess, and you can always change the mapping in section 2 of
the app.

**SSCC input format:** the SSCC column may contain either:
- **17 digits** (extension digit + GS1 Company Prefix + Serial Reference,
  no check digit) -- the app calculates and appends the GS1 Mod-10 check
  digit automatically, or
- **18 digits** (already includes a check digit) -- the app validates it
  and reports a row as skipped if the check digit doesn't match.

If your sheet has **no header row** (the first row is already an SSCC),
un-check "First row is a header row" before loading -- otherwise the first
SSCC would be mistaken for a column header and dropped. The app also warns
you if it looks like your "header" row is actually data.

**Bulk sheets:** there's no practical row limit -- sheets of hundreds or
thousands of SSCCs are loaded, previewed, generated, and printed in
sequence, row by row, with progress shown in the progress bar and a
per-row result in the log panel.

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
the app draws that text itself for those symbologies -- and never draws
duplicate text under GS1-128, since Zint already prints it there.

## Network printing (ZPL)

Enter the printer's IP address and port (default 9100, standard raw
JetDirect-style printing) and click "Send All to Network Printer". Each
label is converted to ZPL (`^GFA` graphic field) and sent directly over
TCP, with a short delay between labels so the printer's buffer keeps up
during long bulk runs.

**Calibration:** if labels start printing across the wrong physical
sticker (drifting) or the printer consumes extra blank labels, click
"Calibrate Printer" once after loading a new roll of label stock. This
sends a `~JC` media-calibration command so the printer re-measures the
gaps between labels.

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
- **SSCC check digit mismatch** -- the 18th digit in an 18-digit SSCC
  doesn't match the GS1 Mod-10 checksum of the first 17. Either supply
  only 17 digits (and let the app calculate the check digit) or fix the
  18th digit in the source data.
- **Barcode too big / doesn't fit the label** -- lower the module size, or
  increase the label width/height. The app will auto-shrink toward the
  GS1 minimum but won't go below it.
- **Only some labels print** -- check the Log panel; each row is reported
  individually as OK/sent/skipped/failed with a reason.
- **Labels print across the wrong physical label, or extra blank labels
  are consumed** -- run "Calibrate Printer".
