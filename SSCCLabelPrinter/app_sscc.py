"""
app_sscc.py -- SSCC Label Printer (SSCC-based logistics/pallet labels)

Tkinter desktop app: load an Excel sheet of product data, map columns to
GS1 Application Identifiers (SSCC/CONTENT_GTIN/BATCH/EXPIRY/COUNT), choose a
barcode symbology, generate GS1-compliant labels, and print them either
over the network (raw ZPL) or via an installed Windows printer driver.
"""

import json
import os
import queue
import socket
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import openpyxl
from PIL import Image, ImageTk

import gs1_utils
import label_generator
import zpl_printer

try:
    import driver_printer
    DRIVER_PRINTING_AVAILABLE = True
except ImportError:
    DRIVER_PRINTING_AVAILABLE = False


APP_TITLE = "SSCC Label Printer"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".sscc_label_printer_config.json")

AI_FIELDS = list(gs1_utils.SUPPORTED_AIS_SSCC.keys())  # SSCC, CONTENT_GTIN, BATCH, EXPIRY, COUNT


def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


class SSCCLabelPrinterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x820")
        self.minsize(820, 700)

        self.cfg = load_config()

        # --- state ---
        self.excel_path = tk.StringVar()
        self.sheet_name = tk.StringVar()
        self.has_header_var = tk.BooleanVar(value=True)
        self.output_dir = tk.StringVar(value=self.cfg.get("output_dir", os.path.join(os.path.expanduser("~"), "SSCCLabels")))
        self.dpi_var = tk.IntVar(value=self.cfg.get("dpi", 300))
        self.label_width_var = tk.DoubleVar(value=self.cfg.get("label_width_in", 2.0))
        self.label_height_var = tk.DoubleVar(value=self.cfg.get("label_height_in", 2.0))
        self.save_zpl_var = tk.BooleanVar(value=False)

        self.title_col_var = tk.StringVar()
        self.footer_col_var = tk.StringVar()
        self.extra_col_var = tk.StringVar()
        self.field_vars = {name: tk.StringVar() for name in AI_FIELDS}

        self.symbology_var = tk.StringVar(value=label_generator.DEFAULT_SYMBOLOGY)
        self.dl_domain_var = tk.StringVar(value=self.cfg.get("dl_domain", "https://id.gs1.org"))
        self.module_size_var = tk.StringVar(value="")

        self.printer_host_var = tk.StringVar(value=self.cfg.get("printer_host", ""))
        self.printer_port_var = tk.IntVar(value=self.cfg.get("printer_port", zpl_printer.DEFAULT_PRINTER_PORT))
        self.printer_dpi_var = tk.IntVar(value=self.cfg.get("printer_dpi", 300))

        self.driver_printer_var = tk.StringVar(value=self.cfg.get("driver_printer", ""))

        self.sheet_names = []
        self.headers = []
        self.rows = []  # list of dict(header->value) OR list of list if no header
        self.zint_exe = None

        self.log_queue = queue.Queue()

        self._build_ui()
        self._poll_log_queue()

        try:
            self.zint_exe = label_generator.find_zint_exe()
        except FileNotFoundError as e:
            self._log(f"WARNING: {e}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        scroll_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        pad = {"padx": 10, "pady": 6}

        # 1. Load Excel Data
        f1 = ttk.LabelFrame(scroll_frame, text="1. Load Excel Data")
        f1.pack(fill="x", **pad)
        ttk.Entry(f1, textvariable=self.excel_path, width=60).grid(row=0, column=0, padx=5, pady=5, sticky="we")
        ttk.Button(f1, text="Browse...", command=self._browse_excel).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(f1, text="Sheet:").grid(row=0, column=2, padx=5)
        self.sheet_combo = ttk.Combobox(f1, textvariable=self.sheet_name, state="readonly", width=20)
        self.sheet_combo.grid(row=0, column=3, padx=5)
        ttk.Checkbutton(f1, text="First row is a header row", variable=self.has_header_var,
                         command=self._load_sheet).grid(row=1, column=0, columnspan=2, sticky="w", padx=5)
        ttk.Button(f1, text="Load Sheet", command=self._load_sheet).grid(row=1, column=3, padx=5, pady=5)
        f1.columnconfigure(0, weight=1)

        # 2. Map Columns
        f2 = ttk.LabelFrame(scroll_frame, text="2. Map Columns to GS1 AIs & Symbology")
        f2.pack(fill="x", **pad)

        ttk.Label(f2, text="Symbology:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        sym_combo = ttk.Combobox(f2, textvariable=self.symbology_var, state="readonly",
                                  values=list(label_generator.SYMBOLOGIES.keys()), width=28)
        sym_combo.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        sym_combo.bind("<<ComboboxSelected>>", lambda e: self._update_gs1_range_label())

        ttk.Label(f2, text="Digital Link domain:").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Entry(f2, textvariable=self.dl_domain_var, width=26).grid(row=0, column=3, sticky="w", padx=5)

        ttk.Label(f2, text="Module size (mm, blank = GS1 default):").grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=4)
        ttk.Entry(f2, textvariable=self.module_size_var, width=10).grid(row=1, column=2, sticky="w", padx=5)
        ttk.Button(f2, text="Use GS1 default", command=self._use_gs1_default_module_size).grid(row=1, column=3, sticky="w", padx=5)
        self.gs1_range_label = ttk.Label(f2, text="", foreground="#555555")
        self.gs1_range_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=5)

        ttk.Separator(f2).grid(row=3, column=0, columnspan=4, sticky="we", pady=6)

        ttk.Label(f2, text="Header text column:").grid(row=4, column=0, sticky="w", padx=5, pady=4)
        self.title_combo = ttk.Combobox(f2, textvariable=self.title_col_var, state="readonly", width=20)
        self.title_combo.grid(row=4, column=1, sticky="w", padx=5)

        ttk.Label(f2, text="Footer text column:").grid(row=4, column=2, sticky="w", padx=5)
        self.footer_combo = ttk.Combobox(f2, textvariable=self.footer_col_var, state="readonly", width=20)
        self.footer_combo.grid(row=4, column=3, sticky="w", padx=5)

        ttk.Label(f2, text="Extra AI data column (optional, e.g. (91)TEXT):").grid(row=5, column=0, columnspan=2, sticky="w", padx=5, pady=4)
        self.extra_combo = ttk.Combobox(f2, textvariable=self.extra_col_var, state="readonly", width=20)
        self.extra_combo.grid(row=5, column=2, sticky="w", padx=5)

        self.field_combos = {}
        row_i = 6
        for name in AI_FIELDS:
            ai = gs1_utils.SUPPORTED_AIS_SSCC[name]["ai"]
            ttk.Label(f2, text=f"{name} (AI {ai}):").grid(row=row_i, column=0, sticky="w", padx=5, pady=3)
            combo = ttk.Combobox(f2, textvariable=self.field_vars[name], state="readonly", width=20)
            combo.grid(row=row_i, column=1, sticky="w", padx=5)
            self.field_combos[name] = combo
            row_i += 1

        # 3. Output
        f3 = ttk.LabelFrame(scroll_frame, text="3. Output")
        f3.pack(fill="x", **pad)
        ttk.Label(f3, text="Output folder:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(f3, textvariable=self.output_dir, width=50).grid(row=0, column=1, sticky="we", padx=5)
        ttk.Button(f3, text="Browse...", command=self._browse_output_dir).grid(row=0, column=2, padx=5)

        ttk.Label(f3, text="DPI:").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        ttk.Spinbox(f3, textvariable=self.dpi_var, from_=150, to=1200, increment=1, width=8).grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(f3, text="Label width (in):").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        ttk.Spinbox(f3, textvariable=self.label_width_var, from_=0.5, to=12.0, increment=0.1, width=8).grid(row=2, column=1, sticky="w", padx=5)
        ttk.Label(f3, text="Label height (in):").grid(row=2, column=2, sticky="w", padx=5)
        ttk.Spinbox(f3, textvariable=self.label_height_var, from_=0.5, to=12.0, increment=0.1, width=8).grid(row=2, column=3, sticky="w", padx=5)

        ttk.Checkbutton(f3, text="Also save .zpl files", variable=self.save_zpl_var).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=4)
        f3.columnconfigure(1, weight=1)

        # 4. Network Printer
        f4 = ttk.LabelFrame(scroll_frame, text="4. Network Printer (raw ZPL)")
        f4.pack(fill="x", **pad)
        ttk.Label(f4, text="Printer IP:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(f4, textvariable=self.printer_host_var, width=18).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(f4, text="Port:").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Entry(f4, textvariable=self.printer_port_var, width=8).grid(row=0, column=3, sticky="w", padx=5)
        ttk.Label(f4, text="Printer DPI:").grid(row=0, column=4, sticky="w", padx=5)
        ttk.Combobox(f4, textvariable=self.printer_dpi_var, state="readonly", width=6,
                     values=list(zpl_printer.SUPPORTED_DPI)).grid(row=0, column=5, sticky="w", padx=5)
        ttk.Button(f4, text="Send All to Network Printer", command=self.start_printing).grid(row=1, column=0, columnspan=2, padx=5, pady=6, sticky="w")
        ttk.Button(f4, text="Calibrate Printer", command=self.calibrate_printer).grid(row=1, column=2, columnspan=2, padx=5, pady=6, sticky="w")

        # 5. Driver printer
        f5 = ttk.LabelFrame(scroll_frame, text="5. Or Print via Windows Printer Driver")
        f5.pack(fill="x", **pad)
        if DRIVER_PRINTING_AVAILABLE:
            ttk.Label(f5, text="Printer:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
            self.driver_combo = ttk.Combobox(f5, textvariable=self.driver_printer_var, state="readonly", width=35)
            self.driver_combo.grid(row=0, column=1, sticky="w", padx=5)
            ttk.Button(f5, text="Refresh List", command=self._refresh_driver_printers).grid(row=0, column=2, padx=5)
            ttk.Button(f5, text="Send All via Printer Driver", command=self.start_driver_printing).grid(row=1, column=0, columnspan=2, padx=5, pady=6, sticky="w")
            self._refresh_driver_printers()
        else:
            ttk.Label(f5, text="Windows printer-driver printing is only available when running on Windows "
                               "(pywin32 not found).").grid(row=0, column=0, sticky="w", padx=5, pady=6)

        # 6. Data Preview
        f6 = ttk.LabelFrame(scroll_frame, text="6. Data Preview")
        f6.pack(fill="both", expand=True, **pad)
        self.preview_tree = ttk.Treeview(f6, show="headings", height=8)
        self.preview_tree.pack(fill="both", expand=True, padx=5, pady=5)

        # Generate + progress
        f7 = ttk.Frame(scroll_frame)
        f7.pack(fill="x", **pad)
        ttk.Button(f7, text="Generate Labels", command=self.start_generation).pack(side="left", padx=5)
        self.progress = ttk.Progressbar(f7, orient="horizontal", mode="determinate", length=400)
        self.progress.pack(side="left", padx=10, fill="x", expand=True)

        # Log panel
        f8 = ttk.LabelFrame(scroll_frame, text="Log")
        f8.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(f8, height=10, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        self._update_gs1_range_label()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log(self, msg):
        self.log_queue.put(msg)

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(150, self._poll_log_queue)

    # ------------------------------------------------------------------
    # Excel loading
    # ------------------------------------------------------------------
    def _browse_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")])
        if path:
            self.excel_path.set(path)
            try:
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                self.sheet_names = wb.sheetnames
                self.sheet_combo["values"] = self.sheet_names
                if self.sheet_names:
                    self.sheet_name.set(self.sheet_names[0])
                wb.close()
            except Exception as e:
                messagebox.showerror("Error", f"Could not open workbook:\n{e}")
                return
            self._load_sheet()

    def _looks_like_data_row(self, row):
        """Heuristic: does this row look like actual GS1 data (long digit
        strings) rather than a descriptive header label?"""
        for cell in row:
            s = str(cell).strip() if cell is not None else ""
            if s.isdigit() and len(s) >= 8:
                return True
        return False

    def _load_sheet(self):
        path = self.excel_path.get()
        sheet = self.sheet_name.get()
        if not path or not sheet:
            return
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb[sheet]
            all_rows = [list(r) for r in ws.iter_rows(values_only=True)]
            wb.close()
        except Exception as e:
            messagebox.showerror("Error", f"Could not read sheet:\n{e}")
            return

        if not all_rows:
            self.headers, self.rows = [], []
            self._log("Sheet is empty.")
            return

        first_row = all_rows[0]

        if self.has_header_var.get():
            if self._looks_like_data_row(first_row):
                proceed = messagebox.askyesno(
                    "Possible header mismatch",
                    "The first row looks like it contains actual data (long digit "
                    "values), not column headers. If your sheet has no header row, "
                    "the first row would otherwise be silently dropped.\n\n"
                    "Un-check 'First row is a header row' and treat the first row "
                    "as data instead?"
                )
                if proceed:
                    self.has_header_var.set(False)
                    return self._load_sheet()
            headers = [str(h).strip() if h is not None else f"Column{i+1}" for i, h in enumerate(first_row)]
            data_rows = all_rows[1:]
        else:
            headers = [f"Column{i+1}" for i in range(len(first_row))]
            data_rows = all_rows

        self.headers = headers
        self.rows = [dict(zip(headers, row)) for row in data_rows]

        for combo in list(self.field_combos.values()) + [self.title_combo, self.footer_combo, self.extra_combo]:
            combo["values"] = [""] + headers

        self._auto_map_columns()
        self._refresh_preview()
        self._log(f"Loaded {len(self.rows)} data row(s) from sheet '{sheet}'.")

    def _auto_map_columns(self):
        lower_map = {h.lower(): h for h in self.headers}

        def find(*keywords):
            for kw in keywords:
                for lh, orig in lower_map.items():
                    if kw in lh:
                        return orig
            return ""

        self.field_vars["SSCC"].set(find("sscc", "pallet", "logistic unit"))
        self.field_vars["CONTENT_GTIN"].set(find("content gtin", "gtin", "ean", "upc"))
        self.field_vars["BATCH"].set(find("batch", "lot"))
        self.field_vars["EXPIRY"].set(find("expiry", "expire", "exp date", "exp"))
        self.field_vars["COUNT"].set(find("count", "qty", "quantity"))
        self.title_col_var.set(find("header", "title", "product name", "name"))
        self.footer_col_var.set(find("footer"))

    def _refresh_preview(self):
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.preview_tree["columns"] = self.headers
        for h in self.headers:
            self.preview_tree.heading(h, text=h)
            self.preview_tree.column(h, width=100, anchor="w")
        for row in self.rows[:200]:
            values = [row.get(h, "") for h in self.headers]
            self.preview_tree.insert("", "end", values=values)

    # ------------------------------------------------------------------
    # Symbology / module size helpers
    # ------------------------------------------------------------------
    def _update_gs1_range_label(self):
        sym = label_generator.SYMBOLOGIES.get(self.symbology_var.get())
        if not sym:
            self.gs1_range_label.configure(text="")
            return
        self.gs1_range_label.configure(
            text=f"GS1 range for {self.symbology_var.get()}: "
                 f"min {sym['x_dim_min']:.3f}mm, nominal {sym['x_dim_nominal']:.3f}mm, "
                 f"max {sym['x_dim_max']:.3f}mm"
        )

    def _use_gs1_default_module_size(self):
        self.module_size_var.set("")

    def _get_module_size_mm(self):
        raw = self.module_size_var.get().strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Row -> GS1 string / Digital Link URI
    # ------------------------------------------------------------------
    def _row_to_gs1(self, row):
        field_values = {}
        for name in AI_FIELDS:
            col = self.field_vars[name].get()
            if col:
                field_values[name] = row.get(col, "")

        extra_col = self.extra_col_var.get()
        raw_extra = str(row.get(extra_col, "") or "") if extra_col else ""

        title_col = self.title_col_var.get()
        title_text = str(row.get(title_col, "") or "") if title_col else ""

        footer_col = self.footer_col_var.get()
        footer_text = str(row.get(footer_col, "") or "") if footer_col else ""

        symbology = self.symbology_var.get()
        if symbology == "QR Code (GS1 Digital Link)":
            gs1_string = gs1_utils.build_digital_link_uri(
                field_values, raw_extra=raw_extra, ai_map=gs1_utils.SUPPORTED_AIS_SSCC,
                domain=self.dl_domain_var.get(),
            )
        else:
            gs1_string = gs1_utils.build_gs1_string(
                field_values, raw_extra=raw_extra, ai_map=gs1_utils.SUPPORTED_AIS_SSCC,
            )

        return gs1_string, title_text, footer_text

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def _browse_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def start_generation(self):
        if not self.rows:
            messagebox.showwarning("No data", "Load an Excel sheet first.")
            return
        if not self.zint_exe:
            try:
                self.zint_exe = label_generator.find_zint_exe()
            except FileNotFoundError as e:
                messagebox.showerror("zint not found", str(e))
                return

        os.makedirs(self.output_dir.get(), exist_ok=True)
        self._save_current_config()

        thread = threading.Thread(target=self._generate_worker, daemon=True)
        thread.start()

    def _generate_worker(self):
        total = len(self.rows)
        self.progress["maximum"] = total
        self.progress["value"] = 0

        symbology = self.symbology_var.get()
        x_dim_mm = self._get_module_size_mm()
        dpi = self.dpi_var.get()
        width_in = self.label_width_var.get()
        height_in = self.label_height_var.get()
        out_dir = self.output_dir.get()

        ok_count, fail_count = 0, 0

        for i, row in enumerate(self.rows, start=1):
            try:
                gs1_string, title_text, footer_text = self._row_to_gs1(row)
                out_png = os.path.join(out_dir, f"label_{i:05d}.png")
                _, warning = label_generator.generate_label_for_row(
                    gs1_string, title_text, footer_text, self.zint_exe, out_png,
                    dpi=dpi, width_in=width_in, height_in=height_in,
                    symbology=symbology, x_dim_mm=x_dim_mm,
                )
                if self.save_zpl_var.get():
                    self._write_zpl_file(out_png, out_dir, i)

                msg = f"Row {i}: OK -> {os.path.basename(out_png)}"
                if warning:
                    msg += f"  [WARNING: {warning}]"
                self._log(msg)
                ok_count += 1
            except Exception as e:
                self._log(f"Row {i}: SKIPPED - {e}")
                fail_count += 1

            self.progress["value"] = i
            self.update_idletasks()

        self._log(f"Done. {ok_count} label(s) generated, {fail_count} skipped/failed.")

    def _write_zpl_file(self, png_path, out_dir, index):
        img = Image.open(png_path)
        zpl_bytes = zpl_printer.image_to_zpl(img)
        zpl_path = os.path.join(out_dir, f"label_{index:05d}.zpl")
        with open(zpl_path, "wb") as f:
            f.write(zpl_bytes)

    # ------------------------------------------------------------------
    # Network printing
    # ------------------------------------------------------------------
    def start_printing(self):
        if not self.rows:
            messagebox.showwarning("No data", "Load an Excel sheet first.")
            return
        host = self.printer_host_var.get().strip()
        if not host:
            messagebox.showwarning("No printer", "Enter the printer's network IP address.")
            return
        self._save_current_config()
        thread = threading.Thread(target=self._print_worker, daemon=True)
        thread.start()

    def _print_worker(self):
        import time

        total = len(self.rows)
        self.progress["maximum"] = total
        self.progress["value"] = 0

        symbology = self.symbology_var.get()
        x_dim_mm = self._get_module_size_mm()
        dpi = self.printer_dpi_var.get()
        width_in = self.label_width_var.get()
        height_in = self.label_height_var.get()
        host = self.printer_host_var.get().strip()
        port = self.printer_port_var.get()

        ok_count, fail_count = 0, 0

        for i, row in enumerate(self.rows, start=1):
            try:
                gs1_string, title_text, footer_text = self._row_to_gs1(row)
                import tempfile
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_png = os.path.join(tmp_dir, "label.png")
                    _, warning = label_generator.generate_label_for_row(
                        gs1_string, title_text, footer_text, self.zint_exe, tmp_png,
                        dpi=dpi, width_in=width_in, height_in=height_in,
                        symbology=symbology, x_dim_mm=x_dim_mm,
                    )
                    img = Image.open(tmp_png)
                    zpl_bytes = zpl_printer.image_to_zpl(img)
                    zpl_printer.send_zpl(zpl_bytes, host, port)

                msg = f"Row {i}: sent to printer"
                if warning:
                    msg += f"  [WARNING: {warning}]"
                self._log(msg)
                ok_count += 1
            except Exception as e:
                self._log(f"Row {i}: FAILED - {e}")
                fail_count += 1

            self.progress["value"] = i
            self.update_idletasks()
            time.sleep(0.5)  # inter-label delay so the printer's buffer keeps up

        self._log(f"Done. {ok_count} label(s) sent to printer, {fail_count} skipped/failed.")

    def calibrate_printer(self):
        host = self.printer_host_var.get().strip()
        port = self.printer_port_var.get()
        if not host:
            messagebox.showwarning("No printer", "Enter the printer's network IP address.")
            return
        try:
            zpl_bytes = zpl_printer.build_calibration_zpl()
            zpl_printer.send_zpl(zpl_bytes, host, port)
            self._log("Calibration command sent. The printer should feed/measure a couple of labels.")
        except (socket.error, OSError) as e:
            messagebox.showerror("Printer error", f"Could not reach printer:\n{e}")

    # ------------------------------------------------------------------
    # Driver printing
    # ------------------------------------------------------------------
    def _refresh_driver_printers(self):
        if not DRIVER_PRINTING_AVAILABLE:
            return
        try:
            printers = driver_printer.list_printers()
            self.driver_combo["values"] = printers
            if not self.driver_printer_var.get() and printers:
                try:
                    default = driver_printer.get_default_printer()
                    if default in printers:
                        self.driver_printer_var.set(default)
                    else:
                        self.driver_printer_var.set(printers[0])
                except Exception:
                    self.driver_printer_var.set(printers[0])
        except Exception as e:
            self._log(f"Could not list printers: {e}")

    def start_driver_printing(self):
        if not DRIVER_PRINTING_AVAILABLE:
            return
        if not self.rows:
            messagebox.showwarning("No data", "Load an Excel sheet first.")
            return
        printer_name = self.driver_printer_var.get().strip()
        if not printer_name:
            messagebox.showwarning("No printer", "Choose a Windows printer.")
            return
        self._save_current_config()
        thread = threading.Thread(target=self._driver_print_worker, daemon=True)
        thread.start()

    def _driver_print_worker(self):
        total = len(self.rows)
        self.progress["maximum"] = total
        self.progress["value"] = 0

        symbology = self.symbology_var.get()
        x_dim_mm = self._get_module_size_mm()
        dpi = self.dpi_var.get()
        width_in = self.label_width_var.get()
        height_in = self.label_height_var.get()
        printer_name = self.driver_printer_var.get().strip()

        ok_count, fail_count = 0, 0
        reported_dpi = False

        for i, row in enumerate(self.rows, start=1):
            try:
                gs1_string, title_text, footer_text = self._row_to_gs1(row)
                import tempfile
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_png = os.path.join(tmp_dir, "label.png")
                    _, warning = label_generator.generate_label_for_row(
                        gs1_string, title_text, footer_text, self.zint_exe, tmp_png,
                        dpi=dpi, width_in=width_in, height_in=height_in,
                        symbology=symbology, x_dim_mm=x_dim_mm,
                    )
                    img = Image.open(tmp_png)
                    result = driver_printer.print_image_via_driver(
                        img, printer_name, width_in=width_in, height_in=height_in,
                        job_name=f"GS1 Label {i}",
                    )

                if not reported_dpi:
                    self._log(
                        f"Driver reports: {result['dpi_x']}x{result['dpi_y']} DPI, "
                        f"printable area {result['printable_width_px']}x{result['printable_height_px']}px, "
                        f"custom label size honored: {result['custom_size_honored']}"
                    )
                    reported_dpi = True

                msg = f"Row {i}: sent to printer driver"
                if warning:
                    msg += f"  [WARNING: {warning}]"
                self._log(msg)
                ok_count += 1
            except Exception as e:
                self._log(f"Row {i}: FAILED - {e}")
                fail_count += 1

            self.progress["value"] = i
            self.update_idletasks()

        self._log(f"Done. {ok_count} label(s) sent via printer driver, {fail_count} skipped/failed.")

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------
    def _save_current_config(self):
        self.cfg.update({
            "output_dir": self.output_dir.get(),
            "dpi": self.dpi_var.get(),
            "label_width_in": self.label_width_var.get(),
            "label_height_in": self.label_height_var.get(),
            "printer_host": self.printer_host_var.get(),
            "printer_port": self.printer_port_var.get(),
            "printer_dpi": self.printer_dpi_var.get(),
            "driver_printer": self.driver_printer_var.get(),
            "dl_domain": self.dl_domain_var.get(),
        })
        save_config(self.cfg)


def main():
    app = SSCCLabelPrinterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
