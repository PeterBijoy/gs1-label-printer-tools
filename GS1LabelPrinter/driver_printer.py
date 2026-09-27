"""
driver_printer.py
Windows-only: prints a rendered label image via an installed Windows
printer driver (GDI), letting the driver's own Printing Preferences own
DPI/media size, while still allowing an optional custom label size request
and reporting back what was actually honored.

This module is only importable on Windows (it depends on pywin32). Callers
should wrap the import in a try/except ImportError and disable
driver-printing UI when unavailable (e.g. when running/testing on Linux).
"""

import win32print
import win32ui
import win32con
import win32gui
from PIL import ImageWin


def list_printers():
    """Returns a list of printer names visible to Windows (local + network/connections)."""
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    printers = win32print.EnumPrinters(flags)
    return sorted(p[2] for p in printers)


def get_default_printer():
    return win32print.GetDefaultPrinter()


def _tenths_mm_from_inches(value_in):
    return int(round(value_in * 25.4 * 10))


def _open_devmode(printer_name, width_in=None, height_in=None):
    """
    Opens the printer and, if width_in/height_in are given, attempts to set
    a custom page size (PaperWidth/PaperLength, in tenths of a millimetre)
    and merges it with the driver via DocumentProperties(). If the driver
    rejects the custom size, falls back gracefully to the driver's current
    default and reports that the custom size was NOT honored.

    Returns: (hPrinter, devmode, custom_size_requested: bool)
    """
    hPrinter = win32print.OpenPrinter(printer_name)
    custom_size_requested = width_in is not None and height_in is not None

    try:
        properties = win32print.GetPrinter(hPrinter, 2)
        devmode = properties["pDevMode"]

        if devmode is None:
            devmode = win32print.DocumentProperties(
                0, hPrinter, printer_name, None, None, 0
            )

        if custom_size_requested:
            devmode.PaperSize = win32con.DMPAPER_USER
            devmode.PaperWidth = _tenths_mm_from_inches(width_in)
            devmode.PaperLength = _tenths_mm_from_inches(height_in)
            devmode.Fields |= (
                win32con.DM_PAPERSIZE | win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH
            )

            try:
                devmode = win32print.DocumentProperties(
                    0, hPrinter, printer_name, devmode, devmode,
                    win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER,
                )
            except Exception:
                # Driver rejected the custom size; fall back to its default.
                custom_size_requested = False
                devmode = win32print.DocumentProperties(
                    0, hPrinter, printer_name, None, None, 0
                )

        return hPrinter, devmode, custom_size_requested

    except Exception:
        win32print.ClosePrinter(hPrinter)
        raise


def get_printer_status(printer_name, width_in=None, height_in=None):
    """
    Diagnostic helper: opens the printer/devmode and reports the DPI and
    printable area the driver will actually use, without printing anything.
    """
    hPrinter, devmode, custom_size_honored = _open_devmode(printer_name, width_in, height_in)
    try:
        hdc = win32gui.CreateDC("WINSPOOL", printer_name, devmode)
        try:
            dpi_x = win32gui.GetDeviceCaps(hdc, win32con.LOGPIXELSX)
            dpi_y = win32gui.GetDeviceCaps(hdc, win32con.LOGPIXELSY)
            printable_w = win32gui.GetDeviceCaps(hdc, win32con.HORZRES)
            printable_h = win32gui.GetDeviceCaps(hdc, win32con.VERTRES)
        finally:
            win32gui.DeleteDC(hdc)

        return {
            "printer_name": printer_name,
            "dpi_x": dpi_x,
            "dpi_y": dpi_y,
            "printable_width_px": printable_w,
            "printable_height_px": printable_h,
            "custom_size_honored": custom_size_honored,
        }
    finally:
        win32print.ClosePrinter(hPrinter)


def print_image_via_driver(image, printer_name, width_in=None, height_in=None,
                            job_name="GS1 Label"):
    """
    Prints `image` (a PIL Image) to `printer_name` via the Windows GDI
    printing path, using the installed driver's own DPI/media handling.

    If width_in/height_in are given, attempts to request that custom label
    size from the driver first (see _open_devmode). The image is fitted to
    the printable area WITHOUT ever upscaling beyond its native resolution
    (a label rendered at 300dpi is not stretched to fill a printable area
    that implies a lower effective DPI).

    Returns a dict describing what was actually used, e.g.:
        {
            "custom_size_honored": bool,
            "dpi_x": int, "dpi_y": int,
            "printable_width_px": int, "printable_height_px": int,
        }
    """
    hPrinter, devmode, custom_size_honored = _open_devmode(printer_name, width_in, height_in)

    try:
        hdc_obj = win32ui.CreateDC()
        hdc_obj.CreatePrinterDC(printer_name)

        dpi_x = hdc_obj.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = hdc_obj.GetDeviceCaps(win32con.LOGPIXELSY)
        printable_w = hdc_obj.GetDeviceCaps(win32con.HORZRES)
        printable_h = hdc_obj.GetDeviceCaps(win32con.VERTRES)

        # Fit image into the printable area, preserving aspect ratio, never
        # upscaling beyond the image's own native pixel size.
        img_w, img_h = image.size
        scale = min(printable_w / img_w, printable_h / img_h, 1.0)
        draw_w = max(1, int(img_w * scale))
        draw_h = max(1, int(img_h * scale))
        offset_x = (printable_w - draw_w) // 2
        offset_y = (printable_h - draw_h) // 2

        hdc_obj.StartDoc(job_name)
        hdc_obj.StartPage()

        dib = ImageWin.Dib(image)
        dib.draw(hdc_obj.GetHandleOutput(),
                 (offset_x, offset_y, offset_x + draw_w, offset_y + draw_h))

        hdc_obj.EndPage()
        hdc_obj.EndDoc()
        hdc_obj.DeleteDC()

        return {
            "custom_size_honored": custom_size_honored,
            "dpi_x": dpi_x,
            "dpi_y": dpi_y,
            "printable_width_px": printable_w,
            "printable_height_px": printable_h,
        }
    finally:
        win32print.ClosePrinter(hPrinter)
