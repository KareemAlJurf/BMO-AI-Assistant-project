"""BMO PCB USB buttons, Feather M0 Basic / CircuitPython 5.2.

Uses the built-in USB keyboard interface; no external libraries required.
Pin mapping was measured on the assembled BMO with individual presses.
It differs from the supplied Gerber design's labelled button nets.
"""
import time
import board
import digitalio
import usb_hid

# CircuitPython 5.2 advertises keyboard usages only through 0x65.
# Use supported F6-F12; F13-F19 are outside that USB descriptor range.
BUTTONS = (
    ("up", board.D5, 0x42),
    ("down", board.D9, 0x43),
    ("left", board.D10, 0x44),
    ("right", board.D6, 0x45),
    ("triangle", board.D11, 0x3F),
    ("small_circle", board.D13, 0x40),
    ("big_circle", board.D12, 0x41),
)
keyboard = None
for device in usb_hid.devices:
    if device.usage_page == 1 and device.usage == 6:
        keyboard = device
        break
if keyboard is None:
    raise RuntimeError("USB keyboard interface unavailable")

pins = []
for name, pin, key in BUTTONS:
    switch = digitalio.DigitalInOut(pin)
    switch.switch_to_input(pull=digitalio.Pull.UP)
    pins.append(switch)

raw = [False] * len(pins)
stable = [False] * len(pins)
changed_at = [time.monotonic()] * len(pins)
report = bytearray(8)
dirty = True
print("BMO buttons ready: up=F9 down=F10 left=F11 right=F12 triangle=F6 small_circle=F7 big_circle=F8")

try:
    while True:
        now = time.monotonic()
        for i, pin in enumerate(pins):
            pressed = not pin.value
            if pressed != raw[i]:
                raw[i] = pressed
                changed_at[i] = now
            if raw[i] != stable[i] and now - changed_at[i] >= 0.025:
                stable[i] = raw[i]
                dirty = True
                print("BMO", BUTTONS[i][0], "DOWN" if stable[i] else "UP")
        if dirty:
            keys = [BUTTONS[i][2] for i in range(len(pins)) if stable[i]]
            for i in range(6):
                # Standard boot keyboards have six key slots. HID rollover
                # signals all seven held; releasing a key restores the report.
                report[i + 2] = 1 if len(keys) > 6 else (keys[i] if i < len(keys) else 0)
            try:
                keyboard.send_report(report)
                dirty = False
            except OSError:
                # Retry the current state if the USB host is temporarily busy.
                time.sleep(0.05)
        time.sleep(0.005)
finally:
    try:
        keyboard.send_report(bytes(8))
    finally:
        for pin in pins:
            pin.deinit()
