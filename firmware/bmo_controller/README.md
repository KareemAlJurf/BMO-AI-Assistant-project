# BMO button controller

`code.py` runs on the Adafruit Feather M0 Basic with CircuitPython 5.2.0.
Copy it to the root of CIRCUITPY. It uses built-in modules only.

| Control | Feather pin | USB key |
| --- | --- | --- |
| Up | D5 | F9 |
| Down | D9 | F10 |
| Left | D10 | F11 |
| Right | D6 | F12 |
| Triangle | D11 | F6 |
| Small circle | D13 | F7 |
| Big circle | D12 | F8 |

Mapping source: individual physical button tests on the assembled BMO.
All seven switches produced press and release events. A Down press once
activated two adjacent switches; a repeated straight press isolated D9.

The supplied `gerber-bmo_controller_pcb.zip` (2025-11-30 export) has named
button nets, but their assignments differ from the measured hardware.
Do not substitute the Gerber-derived mapping for the table above.
The generic PCB symbol also labels its seven digital pins D0–D6,
which are not Feather M0 GPIO numbers.
Reference: https://learn.adafruit.com/adafruit-feather-m0-basic-proto/pinouts

Each switch closes to GND. Inputs use internal pull-ups and 25 ms debounce.
The program logs named presses/releases to the USB serial console and
sends USB keyboard reports using F6–F12 keys. Other applications can bind
these keys, so keep BMO focused during normal use.
BMO application action bindings are a separate step and are not installed
by this controller program.

Initial installation: no existing code.py/main.py or external libraries
were present. The first mapping was replaced after physical testing.
`diagnostic.py` is an optional input-only program that logs pin transitions
over USB serial without emitting keyboard keys. It was used to identify
the actual wiring; production operation uses `code.py`.

To disable the program, rename CIRCUITPY/code.py to code.disabled and
restart the board. This does not replace the CircuitPython firmware.

## BMO desktop actions

The desktop application now binds the installed firmware keys while its window
has keyboard focus:

| Control | Action |
| --- | --- |
| Big circle (F8) | Single press: listen; double press within 450 ms: quit BMO |
| Small circle (F7) | Toggle BMO audio output mute (microphone stays enabled) |
| Triangle (F6) | Request a random thought, including during quiet hours |
| Up / Down (F9 / F10) | Raise / lower volume by 10 percentage points |
| Left (F11) | Stop music; cancel a song waiting for its introduction to finish |
| Right (F12) | Play a random song when BMO is available and unmuted |

Each press acts once; release before pressing again. Big circle waits 450 ms
before listening so a second press can quit without starting recording. A held
button does not count as a double press. Double press also works while busy.
The volume overlay shows the change, hides three seconds after the last
adjustment, and the setting is saved. Volume applies to speech and prerecorded
clips, including music. Stop music allows an introduction already being spoken
to finish. Busy conversation actions are ignored rather than queued.

The application accepts F6–F12 and retains the older F13–F19 action aliases.
These bindings are local to BMO, not global shortcuts.
Restart the application after installing the Python changes.

### October 2 USB descriptor correction

The installed CircuitPython 5.2 USB keyboard descriptor has both usage maximum
and logical maximum 0x65. F13–F19 (0x68–0x6e) were outside that range: the board
logged an Up press/release, but Linux emitted no keyboard event. F6–F12 use
0x3f–0x45 and fit the descriptor. The corrected program was installed and
automatically reloaded. Physical confirmation is recorded in BMO_CHANGE_HISTORY.md.

Mute is controlled by the small circle only. The old mouth and lower-left
touchscreen mute zones are ignored after unwanted screen clicks were observed
triggering mute.
