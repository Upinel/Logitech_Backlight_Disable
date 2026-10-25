#!/usr/bin/env python3
"""Turn the backlight of a Logitech MX keyboard on/off via HID++ 2.0 (feature 0x1982 Backlight2).

Works through a Logi Bolt / Unifying receiver. Byte layout follows Solaar
(lib/logitech_receiver/hidpp20.py, class Backlight).

Usage:
  logi_backlight.py status          show devices and current backlight config
  logi_backlight.py off             disable the backlight
  logi_backlight.py on              re-enable the backlight
  logi_backlight.py watch           keep it off: re-apply whenever the keyboard reconnects/wakes
"""
import sys
import time

import hid

LOGITECH_VID = 0x046D
RECEIVER_PIDS = {0xC548, 0xC52B, 0xC534, 0xC539, 0xC53F, 0xC547}  # Bolt, Unifying, nano, Lightspeed

REPORT_SHORT = 0x10
REPORT_LONG = 0x11
SW_ID = 0x0A  # arbitrary non-zero software id, lets us match our own replies

FEAT_ROOT = 0x0000
FEAT_NAME = 0x0005
FEAT_BACKLIGHT2 = 0x1982


class HidppError(Exception):
    pass


def open_receiver():
    for d in hid.enumerate(LOGITECH_VID):
        # The HID++ interface sits on vendor usage page 0xFF00.
        if d["product_id"] in RECEIVER_PIDS and d["usage_page"] == 0xFF00:
            dev = hid.device()
            dev.open_path(d["path"])
            return dev
    raise SystemExit("No Logitech receiver HID++ interface found.")


def request(dev, index, feature_index, function, params=b"", timeout_ms=1000):
    """Send a long HID++ 2.0 request and wait for the matching reply. Returns the 16 param bytes."""
    msg = bytes([REPORT_LONG, index, feature_index, (function << 4) | SW_ID]) + params
    dev.write(msg.ljust(20, b"\x00"))
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        r = dev.read(20, 100)
        if not r or r[1] != index:
            continue
        if r[2] == 0x8F:  # HID++ 1.0 error (e.g. device asleep / not connected)
            raise HidppError(f"HID++1.0 error 0x{r[5]:02x} on device {index}")
        if r[2] == 0xFF and r[3] == feature_index:  # HID++ 2.0 error
            raise HidppError(f"HID++2.0 error 0x{r[5]:02x} on device {index}")
        if r[2] == feature_index and r[3] == ((function << 4) | SW_ID):
            return bytes(r[4:20])
    raise HidppError(f"timeout talking to device {index}")


def feature_index(dev, index, feature_id):
    r = request(dev, index, 0x00, 0, feature_id.to_bytes(2, "big"))
    return r[0] or None  # 0 means "not supported"


def device_name(dev, index):
    fi = feature_index(dev, index, FEAT_NAME)
    if not fi:
        return "?"
    length = request(dev, index, fi, 0)[0]
    name = b""
    while len(name) < length:
        name += request(dev, index, fi, 1, bytes([len(name)]))
    return name[:length].decode(errors="replace")


def find_keyboards(dev):
    """Yield (device_index, name, backlight_feature_index) for paired devices that support Backlight2."""
    for index in range(1, 7):
        try:
            fi = feature_index(dev, index, FEAT_BACKLIGHT2)
        except HidppError:
            continue  # empty slot or device asleep
        if fi:
            yield index, device_name(dev, index), fi


def read_config(dev, index, fi):
    return request(dev, index, fi, 0)


def describe(cfg):
    enabled, options, supported = cfg[0], cfg[1], cfg[2]
    mode = (options >> 3) & 0x03
    return (f"enabled={enabled} mode={mode} level={cfg[5]} supported=0x{supported:02x} "
            f"raw={cfg[:12].hex(' ')}")


def write_config(dev, index, fi, enabled):
    cfg = read_config(dev, index, fi)
    options = cfg[1]
    mode = (options >> 3) & 0x03
    level = cfg[5] if mode == 0x3 else 0
    # enabled, options, effect (0xFF = keep current), level, then the three duration words unchanged
    params = bytes([1 if enabled else 0, options, 0xFF, level]) + cfg[6:12]
    request(dev, index, fi, 1, params)
    return read_config(dev, index, fi)


def cmd_status(dev):
    found = False
    for index, name, fi in find_keyboards(dev):
        found = True
        print(f"[{index}] {name}: {describe(read_config(dev, index, fi))}")
    if not found:
        print("No connected device with Backlight2 found (press a key to wake the keyboard and retry).")


def cmd_set(dev, enabled):
    found = False
    for index, name, fi in find_keyboards(dev):
        found = True
        print(f"[{index}] {name}: {describe(write_config(dev, index, fi, enabled))}")
    if not found:
        raise SystemExit("No connected device with Backlight2 found (press a key to wake the keyboard and retry).")


def cmd_watch(interval=5):
    """Poll and re-disable the backlight if the keyboard turned it back on."""
    while True:
        try:
            dev = open_receiver()
            try:
                for index, name, fi in find_keyboards(dev):
                    if read_config(dev, index, fi)[0]:
                        write_config(dev, index, fi, enabled=False)
                        print(f"{time.strftime('%F %T')} re-disabled backlight on [{index}] {name}", flush=True)
            finally:
                dev.close()
        except (HidppError, OSError, SystemExit) as e:
            print(f"{time.strftime('%F %T')} {e}", flush=True)
        time.sleep(interval)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "watch":
        cmd_watch()
        return
    dev = open_receiver()
    try:
        if cmd == "status":
            cmd_status(dev)
        elif cmd in ("off", "on"):
            cmd_set(dev, enabled=(cmd == "on"))
        else:
            raise SystemExit(__doc__)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
