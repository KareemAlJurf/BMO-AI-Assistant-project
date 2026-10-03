"""Temporary input-only pin discovery; emits serial logs, no keyboard keys."""
import board
import digitalio
import time
import usb_hid

for device in usb_hid.devices:
    if device.usage_page == 1 and device.usage == 6:
        device.send_report(bytes(8))

names = ("D5", "D6", "D9", "D10", "D11", "D12", "D13",
         "A0", "A1", "A2", "A3", "A4", "A5",
         "SDA", "SCL", "SCK", "MOSI", "MISO", "RX", "TX")
pins = []
for name in names:
    pin = digitalio.DigitalInOut(getattr(board, name))
    pin.switch_to_input(pull=digitalio.Pull.UP)
    pins.append(pin)
raw = [pin.value for pin in pins]
stable = raw[:]
changed = [time.monotonic()] * len(pins)
print("BMO DIAGNOSTIC READY; USB keyboard output disabled")
print("Initially LOW:", [names[i] for i in range(len(pins)) if not raw[i]])
while True:
    now = time.monotonic()
    for i, pin in enumerate(pins):
        value = pin.value
        if value != raw[i]:
            raw[i] = value
            changed[i] = now
        if stable[i] != raw[i] and now - changed[i] >= 0.025:
            stable[i] = raw[i]
            print("PIN", names[i], "RELEASE" if stable[i] else "PRESS")
    time.sleep(0.005)
