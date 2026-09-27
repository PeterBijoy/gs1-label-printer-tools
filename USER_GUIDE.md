# User Guide

How to use **GS1 Label Printer** and **SSCC Label Printer** once they're
running (see [`SETUP_GUIDE.md`](SETUP_GUIDE.md) if you haven't installed
or built the app yet).

Both apps look and work almost identically — the only real difference is
which GS1 Application Identifiers (AIs) they map:

| | GS1 Label Printer | SSCC Label Printer |
|---|---|---|
| Purpose | Product labels | Logistics / pallet labels |
| Fields (AIs) | GTIN (01), Batch (10), Expiry (17), Serial (21), Quantity (30) | SSCC (00), Content GTIN (02), Batch (10), Expiry (17), Count (37) |
| Typical volume | Per-product runs | Bulk — hundreds/thousands of SSCCs in one sheet |

Everything else in this guide applies to both; screenshots/section names
reference the on-screen numbered panels, which are the same layout in
both apps.

---

## 1. Prepare your Excel file

Create an `.xlsx` file with one row per label. Column names don't need to
match exactly — the app makes a best-effort guess at mapping them — but
using clear names makes auto-mapping more reliable.

**GS1 Label Printer example:**

| GTIN | Batch | Expiry | Serial | Quantity | Header text | Footer text |
|---|---|---|---|---|---|---|
| 00012345678905 | LOT2201 | 2026-12-31 | SN001 | 12 | Acme Widget | Made in India |

**SSCC Label Printer example:**

| SSCC | Content GTIN | Batch | Expiry | Count | Header text | Footer text |
|---|---|---|---|---|---|---|
| 10012345000000001 | 00012345678905 | LOT2201 | 2026-12-31 | 24 | Acme Foods Pallet | Handle with care |

Notes on specific fields:

- **SSCC** can be given as **17 digits** (no check digit — the app
  calculates and appends one automatically) or **18 digits** (already
  includes a check digit — the app validates it and skips the row if it
  doesn't match).
- **Expiry** accepts `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, or raw
  `YYMMDD` — it's converted to the GS1-required `YYMMDD` format
  automatically.
- **Header text** / **Footer text** are plain text printed above/below
  the barcode — they are *not* part of the GS1 data, just human-readable
  labeling (e.g. a product name, or a handling instruction).
- You can add any extra AI data the app doesn't have a dedicated column
  for (e.g. `(91)internal-code`) via an **Extra AI data column** — it
  must already be in bracketed form, starting with `(`.
- If your sheet has **no header row** (row 1 is already data), you'll
  un-check a box in the app rather than change the spreadsheet — see
  Section 2 below.

---

## 2. Load your Excel file

1. Click **Browse...** in section **"1. Load Excel Data"** and select
   your `.xlsx` file.
2. If the workbook has multiple sheets, pick the right one from the
   **Sheet** dropdown.
3. Leave **"First row is a header row"** checked if row 1 contains column
   names (like the examples above). Un-check it if row 1 is already the
   first label's data.
4. Click **Load Sheet**.

The app will warn you if it looks like your "header" row is actually data
(e.g. it contains long digit strings like an SSCC) — a safety check so a
real row of data never gets silently mistaken for column headers and
dropped.

Loaded rows appear in the **"Data Preview"** table near the bottom so you
can confirm everything came in correctly before generating anything.

---

## 3. Map columns and choose a barcode type

In section **"2. Map Columns to GS1 AIs & Symbology"**:

1. **Symbology** — choose which barcode type to generate:

   | Symbology | Best for |
   |---|---|
   | **GS1-128** | The classic linear barcode — widest hardware/scanner compatibility, prints its own human-readable text automatically. |
   | **GS1 DataMatrix** | Compact 2D symbol — good when label space is tight. |
   | **GS1 QR Code** | 2D symbol, scannable by generic QR readers as well as GS1-aware scanners. |
   | **QR Code (GS1 Digital Link)** | Encodes a *resolvable web URL* (e.g. `https://id.gs1.org/01/00012345678905/10/LOT2201`) instead of raw AI data — scanning it with any phone camera opens a link, not just raw data. Set the **Digital Link domain** field if you use your own resolver instead of `https://id.gs1.org`. |

2. **Module size (mm)** — leave blank to use the GS1-recommended default
   for whichever symbology you picked (shown just below the field, e.g.
   "GS1 range for GS1-128: min 0.264mm, nominal 0.330mm, max 0.660mm").
   Only override this if you have a specific reason to (e.g. matching an
   existing label spec) — click **Use GS1 default** to clear an override.
3. Map each **AI field** (GTIN/SSCC, Batch, Expiry, etc.) to the matching
   spreadsheet column using the dropdowns. The app pre-fills its best
   guess when you load a sheet — double check these, especially if your
   column names are unusual.
4. Set **Header text column** / **Footer text column** / **Extra AI data
   column** the same way, if you're using them.

---

## 4. Set the output/label size

In section **"3. Output"**:

- **Output folder** — where generated label images are saved.
- **DPI** — resolution for the generated image (300 is a common default
  for thermal label printers; check your printer's spec if unsure).
- **Label width / height (in)** — physical label size. These are set
  independently, so labels don't have to be square — a 4in x 2in shipping
  label works the same as a 2in x 2in square one.
- **Also save .zpl files** — check this if you want a `.zpl` file saved
  alongside each label's image (useful if you'll copy files to a printer
  by other means, e.g. a USB drive or a print spooler that accepts raw
  ZPL).

---

## 5. Generate labels

Click **Generate Labels** at the bottom. The app processes every loaded
row in sequence — this is designed to handle bulk sheets of hundreds or
thousands of rows without manual intervention.

Watch the **Log** panel: each row reports one of:

- **OK** — label generated successfully, with the output filename.
- **OK, with a WARNING** — generated, but something is worth knowing
  about, most commonly that the barcode had to shrink close to (or hit)
  the GS1-specified minimum module size to fit your label dimensions. The
  label is still usable, but consider a larger label or fewer AI fields
  if this happens often.
- **SKIPPED** — the row had a data problem (e.g. an SSCC check-digit
  mismatch, or missing required data) and was not processed. The reason
  is printed next to it.

A progress bar tracks overall completion for large sheets.

---

## 6. Print the labels

You have two options — pick whichever matches your setup.

### Option A — Network printer (raw ZPL)

Use this if your label printer has a network/Wi-Fi connection (most
Zebra-style thermal printers support this out of the box on port 9100).

1. In section **"4. Network Printer"**, enter the printer's **IP address**
   (find this in the printer's own network settings menu) and confirm the
   **Port** (9100 is the standard default — leave unless you know it's
   different) and **Printer DPI** (must match your printer's actual
   resolution, e.g. 203 or 300 DPI — a mismatch here causes barcodes to
   print at the wrong physical size).
2. Click **Send All to Network Printer**. Labels print one after another
   in sequence, with a short pause between each so the printer's buffer
   keeps up.

**If labels start printing across the wrong physical label**, or the
printer feeds/wastes extra blank labels: click **Calibrate Printer**
once. This tells the printer to re-measure the gaps between labels on
your current roll of stock — do this any time you load a new roll or
switch to a different label size.

### Option B — Windows printer driver

Use this if you'd rather print through a printer already installed in
Windows (e.g. via USB, or a printer whose network setup you'd rather
manage through Windows itself).

1. In section **"5. Or Print via Windows Printer Driver"**, pick your
   printer from the dropdown (click **Refresh List** if you've just
   installed a new printer and don't see it yet).
2. Click **Send All via Printer Driver**.

The app asks the printer driver for your configured label width/height as
a custom page size. If the driver doesn't support a custom size that
small/that shape, it falls back to the driver's own default and tells you
in the log exactly what DPI and printable area were actually used, and
whether your requested size was honored — so you'll know immediately if
labels come out at the wrong size and why, rather than guessing.

> This option is only available when running on Windows (it's grayed out
> / hidden if you're testing the app on another OS, since it depends on
> the `pywin32` Windows API bindings).

---

## 7. Common questions

**Can I re-print just one label instead of the whole sheet?**
Not directly from the UI today — the simplest workaround is to make a
temporary Excel copy containing only the row(s) you need and load that
instead.

**Why does my long GS1-128 barcode look extremely dense / hard to scan?**
GS1-128 has a practical limit: the GS1 General Specifications recommend
no more than 48 characters of encoded data for reliable scanning. If
you're combining many AI fields (e.g. GTIN + batch + expiry + serial +
quantity) on a small label, the resulting string can exceed that, and the
barcode gets visually dense as the app shrinks it to fit. Options: use a
larger label, drop non-essential fields, or switch to GS1 DataMatrix / GS1
QR Code, which handle denser data far more compactly.

**The human-readable text under my QR/DataMatrix label wraps oddly or is
tiny — is that a bug?**
No — GS1 element strings and Digital Link URLs have no spaces, so the app
wraps them character-by-character rather than word-by-word to keep them
inside the label. Text size has a physical minimum built in so it stays
legible when printed, even on small labels.

**Where do I change which columns map to which AI after loading a
sheet?**
Anytime, in section 2 — the dropdowns aren't locked once you've loaded
data, and you can regenerate as many times as you like.

**Is my printer's IP address or driver choice saved for next time?**
Yes — output folder, DPI, label size, network printer IP/port/DPI, and
Windows driver printer selection are all remembered between sessions.

For install/build instructions instead of usage, see
[`SETUP_GUIDE.md`](SETUP_GUIDE.md). For deeper technical detail (Zint
provenance, GS1 module-size tables, troubleshooting build errors), see
each app's own README (`GS1LabelPrinter/README.md` /
`SSCCLabelPrinter/README.md`).
