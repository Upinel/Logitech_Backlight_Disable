# Logitech_Backlight_Disable

Turn the keyboard backlight **fully off** on Logitech MX keyboards, and keep it off.

On keyboards like the **MX Mechanical Mini**, setting brightness to the lowest level with the
backlight keys doesn't last. The backlight comes back after sleep, charging, reconnecting, or
when your hands approach the keyboard ("smart illumination"). That drains the battery fast.

This script talks to the keyboard over Logitech's **HID++ 2.0** protocol and switches the backlight
off with the keyboard's own **Backlight2** setting (feature `0x1982`). That's a separate off
switch, not brightness 0. It **does not modify firmware** and you can undo it at any time with `on`.

## Tested on

| Keyboard            | Connection       | OS    | Result  |
|---------------------|------------------|-------|---------|
| MX Mechanical Mini  | Logi Bolt receiver | macOS | ✅ Works |

Other Logitech keyboards that support Backlight2 (MX Keys, MX Keys Mini, MX Mechanical, etc.)
should also work through a Bolt or Unifying receiver, but haven't been tested. Reports are welcome.

## Requirements

- Python 3.8+
- [`hidapi`](https://pypi.org/project/hidapi/) Python package
- A Logitech **Bolt** or **Unifying** USB receiver with the keyboard paired to it

## Install

```bash
git clone https://github.com/Upinel/Logitech_Backlight_Disable.git
cd Logitech_Backlight_Disable
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
.venv/bin/python logi_backlight.py status   # show paired keyboards and their backlight config
.venv/bin/python logi_backlight.py off      # disable the backlight
.venv/bin/python logi_backlight.py on       # re-enable the backlight
.venv/bin/python logi_backlight.py watch    # keep it off: re-disable it if it gets turned back on
```

Example:

```
$ .venv/bin/python logi_backlight.py off
[1] MX Mechanical Mini: enabled=0 mode=0 level=0 supported=0x05 raw=00 05 05 7f 00 00 00 00 00 00 00 00
```

`enabled=0` means the backlight is switched off. If no keyboard is found, press a key to wake
it and run the command again.

### Keeping it off

Some events, like waking from deep sleep, can make the keyboard reset the backlight to on.
`watch` checks every 5 seconds and switches it back off when that happens. Run it in a terminal,
or start it at login with a launchd agent (macOS) or a systemd user service (Linux).

## Limitations

- **Receiver only.** A keyboard connected directly over Bluetooth isn't supported yet.
- **Logi Options+** may push its own backlight settings when the keyboard reconnects. If the
  backlight keeps coming back, quit Options+ or remove the keyboard from it.
- Linux and Windows should work with `hidapi`, but only macOS has been tested. On Linux you may
  need a udev rule (or `sudo`) to access the receiver.

## How it works

1. Opens the receiver's HID++ interface (vendor usage page `0xFF00`).
2. Checks pairing slots 1–6 and asks each device whether it supports feature `0x1982` (Backlight2).
3. Reads the current backlight config (function 0). Then it writes it back with the enable byte
   cleared (function 1) and leaves the effect, mode, and timeout values as they were.

The byte layout comes from [Solaar](https://github.com/pwr-Solaar/Solaar)'s implementation of
Backlight2.

## Disclaimer

Not affiliated with or endorsed by Logitech. Use at your own risk. The script only changes a
backlight setting the keyboard already exposes, and `on` restores it.
