"""
zpl_printer.py
Converts a rendered label image into ZPL (Zebra Programming Language) and
sends it directly to a network label printer over raw TCP (JetDirect-style,
port 9100), plus a calibration helper for gap/media-sensed label stock.
"""

import socket

DEFAULT_PRINTER_PORT = 9100
SUPPORTED_DPI = (203, 300, 600)


def image_to_zpl(image, media_tracking="Y"):
    """
    Converts a PIL image into a ZPL ^GFA graphic field.

    ZPL's ^GFA format packs 1 bit per pixel, MSB first, 1 = black.
    Pillow's 1-bit image mode packs 0 = black, 1 = white -- the inverse --
    so the packed bytes are bit-inverted before embedding.

    `media_tracking`: "Y" for gap/black-mark sensed (die-cut) labels,
    "N" for continuous stock.
    """
    img = image.convert("L")
    # Hard black/white threshold -- printers have no gray levels.
    img = img.point(lambda p: 255 if p > 127 else 0)
    img = img.convert("1")

    width, height = img.size
    bytes_per_row = (width + 7) // 8
    raw = bytearray(img.tobytes())

    # Bit-invert: Pillow's 1-bit packing is 0=black; ZPL wants 1=black.
    for i in range(len(raw)):
        raw[i] = (~raw[i]) & 0xFF

    total_bytes = bytes_per_row * height
    hex_data = raw.hex().upper()

    zpl = []
    zpl.append("^XA")
    zpl.append(f"^MN{media_tracking}")
    zpl.append("^LH0,0")
    zpl.append(f"^FO0,0^GFA,{total_bytes},{total_bytes},{bytes_per_row},{hex_data}^FS")
    zpl.append("^XZ")

    return ("\n".join(zpl)).encode("ascii")


def build_calibration_zpl(media_tracking="Y"):
    """
    Builds a ZPL job that forces the printer to re-run its media/gap
    calibration feed cycle. Run once whenever a new roll of labels is
    loaded, or if labels start printing across the wrong physical sticker.
    """
    zpl = []
    zpl.append("^XA")
    zpl.append(f"^MN{media_tracking}")
    zpl.append("^JUS")
    zpl.append("^XZ")
    zpl.append("~JC")
    return ("\n".join(zpl)).encode("ascii")


def zpl_to_image(zpl_bytes):
    """
    Reverse-decodes a ^GFA ZPL graphic field back into a PIL image.
    Used only for round-trip testing; not called by the app itself.
    """
    from PIL import Image
    import re

    text = zpl_bytes.decode("ascii", errors="ignore")
    m = re.search(r"\^GFA,(\d+),(\d+),(\d+),([0-9A-Fa-f]+)", text)
    if not m:
        raise ValueError("No ^GFA field found in ZPL data")

    total_bytes = int(m.group(1))
    bytes_per_row = int(m.group(3))
    hex_data = m.group(4)

    raw = bytearray.fromhex(hex_data)
    for i in range(len(raw)):
        raw[i] = (~raw[i]) & 0xFF

    height = total_bytes // bytes_per_row
    width = bytes_per_row * 8

    img = Image.frombytes("1", (width, height), bytes(raw))
    return img


def send_zpl(zpl_bytes, host, port=DEFAULT_PRINTER_PORT, timeout=10.0):
    """Sends raw ZPL bytes to a network printer over a plain TCP socket."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(zpl_bytes)
