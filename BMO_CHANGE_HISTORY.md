# BMO local change history

## Scope and evidence

This document records the local work on BMO in `/home/kareemaljurf/be-more-hailo`, including the setup, fixes, tuning, tests, and camera investigation discussed with the owner.

Compiled after the camera investigation was put on hold, during the September 30, 2026 America/New_York session. Some file timestamps use October 1 UTC; for example, the history backup timestamp `20261001T002150Z` is September 30 at 8:21:50 PM EDT.

Sources used:

- The conversation with the owner, including observed problems and user verification.
- The working-tree diff against repository HEAD `77f8a1d`.
- [LOCAL_SETUP.md](LOCAL_SETUP.md), which records the earlier installation and verification.
- Current source, added unit tests, selected non-secret configuration settings, and the local Ollama service definition.

The exact time and order of the earlier microphone and speech fixes cannot be reconstructed from the available conversation. Those entries describe changes verified in the current diff, rather than inventing a detailed timeline. Earlier installation results are explicitly attributed to the setup notes. This is a record of local changes, not a complete history of upstream BMO development.

## Current setup at a glance

Updated through October 2, 2026. Earlier dated entries preserve the state at that time; see section 16 for the current controls and next steps.

| Component | Local setup |
| --- | --- |
| Hardware | Raspberry Pi 5; local setup notes report no Hailo accelerator detected |
| Project | `/home/kareemaljurf/be-more-hailo` |
| Upstream | `https://github.com/moorew/be-more-hailo` |
| Conversation model | Ollama `qwen2.5:1.5b` |
| Fast conversation model | Also `qwen2.5:1.5b` |
| Model API | `http://127.0.0.1:11434/api/chat` |
| Vision backend/model | Standard Ollama / `moondream` |
| Speech recognition | whisper.cpp, `ggml-base.en.bin`; setup notes specify four threads |
| Speech synthesis | ARM64 Piper with the bundled BMO ONNX voice |
| Wake word | Bundled ONNX model, openWakeWord 0.4.0 |
| Audio output | `ALSA_DEVICE=default` |
| Camera sensor | IMX219; detection confirmed 3280 × 2464 maximum sensor resolution |
| Face-button controller | Adafruit Feather M0 Basic, CircuitPython 5.2.0; seven switches mapped to USB F6–F12; all seven verified; desktop actions added October 2 |
| Main reply token cap | 384 for streaming and non-streaming conversation requests |
| Optional web interface | `http://127.0.0.1:8080` |

## 1. Local CPU installation and configuration

### Problem and outcome

The upstream application targets Hailo hardware. This Pi was configured to run conversation and image-description models on its CPU through standard Ollama.

### Configuration changes

In [core/config.py](core/config.py), fixed model settings were replaced with environment-variable overrides:

- `LLM_URL`: model chat endpoint.
- `LLM_MODEL`: main model.
- `FAST_LLM_MODEL`: fast-path model; defaults to `LLM_MODEL`.
- `VISION_MODEL`: image-description model.
- `VISION_BACKEND`: selects the vision implementation.
- `MIC_DEVICE_INDEX`: optional explicit microphone index.
- `ALSA_DEVICE`: optional explicit speaker/output device.

The source defaults retain Hailo-compatible values. This installation's `.env` selects the CPU configuration:

```dotenv
LLM_URL=http://127.0.0.1:11434/api/chat
LLM_MODEL=qwen2.5:1.5b
FAST_LLM_MODEL=qwen2.5:1.5b
VISION_BACKEND=ollama
VISION_MODEL=moondream
ALSA_DEVICE=default
```

The default ALSA output follows the system-selected speaker, including Bluetooth when selected. Microphone discovery remains available unless explicitly overridden.

### CPU image descriptions

[core/llm.py](core/llm.py), `Brain.analyze_image()`, gained an Ollama branch:

- Sends the image as base64 in the user message's `images` array.
- Uses `VISION_MODEL` through `LLM_URL` without loading the Hailo vision backend.
- Supplies a brief default description prompt when no user text is provided.
- Uses non-streaming responses, a 100-token output cap, 2048-token context, and four threads.
- Uses a 10-second connection timeout and 180-second read timeout.
- Checks HTTP errors and rejects empty model responses.
- Appends a successful description to assistant history.
- Retains failure cleanup so a failed request does not leave an unanswered user turn.

The 100-token vision cap is separate from the later 384-token conversation cap.

### Ollama service and launchers

User service: `/home/kareemaljurf/.config/systemd/user/be-more-hailo-ollama.service`.

Its current definition runs `/home/kareemaljurf/.local/opt/ollama/bin/ollama serve` with:

```text
OLLAMA_HOST=127.0.0.1:11434
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_CONTEXT_LENGTH=4096
Restart=on-failure
```

[start_agent.sh](start_agent.sh) and [start_web.sh](start_web.sh) now:

1. Resolve and switch to the project directory.
2. Start the local user Ollama service.
3. Poll `/api/tags` for readiness, allowing up to 30 polling iterations.
4. Check readiness again before launching the application.
5. Use the project's virtual-environment Python directly.

The desktop launcher retains `DISPLAY=:0` as a fallback. The web launcher runs Uvicorn on localhost port 8080. Startup no longer installs Python packages on every launch. The desktop script no longer starts `hailo-ollama` on port 8000 with a `/tmp/ollama.log` redirect.

The setup notes report that the GUI and model service were not enabled at boot; boot enablement was not rechecked while compiling this document.

### Dependencies and browser template

- Added [requirements-cpu.txt](requirements-cpu.txt), which includes the main requirements and pins `openwakeword==0.4.0` for the ONNX-only ARM64/Python 3.13 setup.
- Added [requirements-local.lock.txt](requirements-local.lock.txt), an exact package-version record from the local installation.
- Updated the home-page template call in [web_app.py](web_app.py) to use explicit `request`, `name`, and `context` arguments compatible with the installed Starlette API.
- Added [LOCAL_SETUP.md](LOCAL_SETUP.md) with startup instructions and initial verification results.

### Initial verification recorded in LOCAL_SETUP.md

These are earlier recorded results, not fresh hardware tests performed for this document:

- 88 unit tests passed at that stage.
- Python dependency check passed.
- Whisper transcribed the bundled JFK sample in about four seconds.
- Piper generated valid 22050 Hz speech and default-speaker playback succeeded.
- USB microphone capture succeeded without overflow.
- The custom wake-word model loaded and scored silence as zero.
- The GUI reached `idle` / `Tap to speak` and listened to the microphone.
- Moondream identified a synthetic red image in about 23 seconds.
- Browser home, status, and face endpoints returned HTTP 200; model status was online.
- A full chat-pipeline response completed in about 13 seconds.

These timings are individual observations, not performance guarantees.

## 2. Microphone end-of-speech detection

### Previous behavior

Recording used the norm of each callback block and counted silent callbacks. Both the volume measurement and elapsed silence depended on how many samples the audio driver supplied per callback.

### Change

Added [core/recording.py](core/recording.py), containing `SilenceDetector`, and connected it to `BotGUI.record_audio()` in [agent_hailo.py](agent_hailo.py).

The detector:

- Converts incoming samples to floating point.
- Removes the block's DC offset before measuring volume.
- Uses RMS amplitude, making the threshold independent of callback block length.
- Counts silent samples and converts the desired silence duration into a sample count.
- Resets silence accumulation when speech resumes.
- Ignores empty input blocks.

Defaults:

| Setting | Value |
| --- | --- |
| Speech amplitude threshold | 300 |
| Quiet time after speech before stopping | 0.8 seconds |
| Initial quiet timeout when no speech starts | 5 seconds |
| Existing maximum recording length | 15 seconds |

The GUI exposes `BMO_SPEECH_THRESHOLD` and `BMO_SILENCE_SECONDS` environment overrides. A `threading.Event` communicates completion to the recording loop, and subsequent callbacks stop adding audio once completion is signaled. Existing recording retry/watchdog behavior remains in the surrounding code.

### Verification

[tests/unit/test_recording.py](tests/unit/test_recording.py) covers different sample rates and callback sizes, short pauses followed by resumed speech, and the five-second initial timeout with a DC offset.

## 3. Speech startup and visible status

### Warmed Piper pipeline

A Piper process can be alive and warmed up without being connected to its audio reader and `aplay`. Previously, `speak()` started the pipeline only when Piper was missing or had exited.

The startup condition now also checks whether `_piper_reader_thread` or `_tts_aplay` is missing. This connects the warmed process before writing speech to it, while continuing to reuse a working pipeline across sentences.

### Speaking status

`_handle_response_chunk()` now calls `speak(chunk, end_of_turn=is_last)` using the normal speaking-status message. Previously it explicitly passed `msg=None`, suppressing that status update.

### Verification

[tests/unit/test_speech_startup.py](tests/unit/test_speech_startup.py) tests warmed and cold startup, connection before text is written, reuse across consecutive sentences, final draining, and the streamed speaking-status arguments. These tests exercise extracted GUI methods without opening a display or microphone.

## 4. Response token limit increased

### Reported problem

BMO cut replies short. Saved examples included a dinosaur poem and another reply ending mid-sentence.

### Change

In both `Brain.think()` and `Brain.stream_think()` in [core/llm.py](core/llm.py):

- Increased `num_predict` from **120** to **384**.
- Kept `temperature=0.7` and `num_ctx=4096`.
- Retained the system prompt's instruction to keep ordinary answers short.

This gives replies and expression JSON more space to finish. It is still a fixed upper bound: unusually long answers can still hit it.

Streaming completion handling also gained:

- An info log containing `done_reason` and `eval_count`.
- A warning when `done_reason` is `length`.

Adding logging calls did not establish persistent file logging; no persistent application runtime log was found in the later investigation.

## 5. Repeated generated replies diagnosed and guarded

### Reported problem and evidence

After the token increase, the owner reported that BMO continuously repeated his last line.

The saved conversation contained a reply to “Who is your best friend?” that repeatedly generated “I'm your BMO, and I'll always be by your side,” with varying follow-up wording.

This demonstrated repetition in the generated text itself. It supported the diagnosis that the speaker was reading repeated model output, rather than establishing an audio-player replay fault. The larger cap allowed the repeating generation to continue longer. Earlier truncated, poem-like history was a possible influence, not a proven cause.

### Generation settings

Both main conversation request paths now send:

```text
num_predict: 384
repeat_penalty: 1.15
repeat_last_n: 256
num_ctx: 4096
temperature: 0.7
```

The penalty discourages repetition. A separate text guard handles substantial exact repeated sentences even if generation still loops.

### Detection and streaming behavior

Added `truncate_repeated_sentences(text)`:

- Scans sentence/line segments delimited by periods, exclamation marks, question marks, or newlines, including a final remaining segment.
- Normalizes case and compares word sequences, ignoring punctuation differences.
- Requires at least **8 words** and **35 normalized characters** before considering a segment a loop candidate.
- Masks `<think>...</think>` reasoning, including an unclosed reasoning block, and simple non-nested JSON objects during comparison.
- Returns the original text prefix before the first repeated qualifying segment.
- Leaves short cheers such as “Yay! Yay!” alone.

Streaming integration checks accumulated cleaned speech before yielding a buffered chunk. When a repeat is found, it closes the HTTP response, exits the stream, trims the accumulated raw response, and avoids yielding the duplicate. It also checks the final buffered text and applies the helper when salvaging interrupted response history.

The non-streaming path trims the initial model response before its normal action and speech processing. In that path, generation has already finished before filtering happens.

Warnings identify repeated text detected in the normal response, active stream, or stream tail.

### Limits

This is an exact normalized sentence/line guard, not semantic similarity detection. It may not catch paraphrased repetition or loops made only of short phrases. Deliberately repeating a sufficiently long line in a poem can trigger it. It stops at the repeat; it does not regenerate a replacement ending. It is primarily protection for the main conversation paths, not a universal filter over every model request in the application.

### History cleanup and backup

Before changing `memory.json`, a full backup was made:

[memory.before-loop-cleanup.20261001T002150Z.json](memory.before-loop-cleanup.20261001T002150Z.json)

The cleanup removed **one looping assistant reply and its paired preceding user question**. Other messages, including the older truncated replies, were retained. BMO was confirmed not running before the cleanup, preventing an active process from overwriting it with stale in-memory history.

The backup contains the original conversation. It is currently an untracked file; the existing `.gitignore` rule for `memory.json` does not also match this backup filename. It should be treated as local conversation data when preparing any future commit or shared archive.

### Verification and owner feedback

Added [tests/unit/test_repetition.py](tests/unit/test_repetition.py), with 11 cases covering the observed loop, ordinary text, short cheers, reasoning and JSON, different streaming chunk boundaries, a final unpunctuated duplicate, saved history, request settings, and non-streaming filtering.

All **107 unit tests passed** after this work. The owner subsequently reported: **“everything is working as expected.”** That feedback preceded the thinking-phrase pacing change below.

## 6. Thinking phrases: slower pacing and fewer repeats

### Reported problem

While thinking, BMO repeated many of the same words and played them too quickly one after another.

The existing controller randomly selected each prerecorded thinking clip independently and left only **0.4–1.2 seconds** between clips.

### Pacing change

`BotGUI._thinking_sound_loop()` now waits before the first thinking clip, after the acknowledgement, and between subsequent clips:

```python
gap_total = random.uniform(3.0, 5.0) + min(clips_played * 1.5, 7.0)
```

| Thinking clips already played in this loop | Next quiet gap |
| --- | --- |
| 0 | 3–5 seconds |
| 1 | 4.5–6.5 seconds |
| 2 | 6–8 seconds |
| 3 | 7.5–9.5 seconds |
| 4 | 9–11 seconds |
| 5 or more | 10–12 seconds |

These are quiet gaps after playback completes, not start-to-start intervals. A fresh thinking loop resets the pacing counter. The waits use a monotonic clock and check the state, playing flag, and shutdown event at roughly 0.1-second intervals so a pending gap can end promptly.

### Selection change

`load_sounds()` initializes a thinking-clip bag and remembers the last selected clip. `play_sound()` shuffles the thinking clips and consumes that bag before refilling it.

- The directory currently contains **20 thinking clips**.
- Each file is selected once per bag cycle.
- When refilling, the first selection is adjusted to avoid immediately repeating the last clip from the previous cycle, when multiple clips exist.
- The bag persists across thinking turns within the running app, and resets on restart.
- Acknowledgement, greeting, and music selection retain their existing behavior.

The recordings themselves and their speaking speed were not changed. The adjustment is to clip selection and the silence between clips. Different recordings can still contain similar words.

### Verification

Python compilation succeeded and all **107 existing unit tests passed**. No dedicated listening test or timing/selection unit test was added for this adjustment. The owner was told to restart BMO to load it; explicit listening confirmation for this particular change was not recorded.

## 7. Camera quality and website investigation — on hold

### Quality question

The owner reported blur. Hardware detection confirmed an IMX219 camera with modes including 640 × 480, 1640 × 1232, 1920 × 1080, and 3280 × 2464.

BMO's existing capture command still requests **640 × 480**, a two-second startup timeout, no preview, and continuous autofocus. A 1640 × 1232 capture size was suggested for more detail, along with checking lighting, lens cleanliness, and physical focus. The standard Camera Module 2 does not provide motorized autofocus; sensor identification alone does not establish every detail of a third-party lens assembly.

**No BMO capture-resolution or focus change was implemented.**

### webcamtests.com

The owner then reported that `https://webcamtests.com/` no longer showed an image.

Investigation found:

- Chromium was running, including its video capture service.
- Its saved site camera permission for webcamtests.com was set to allow.
- V4L2 listed the Pi's camera/frontend and image-processing devices.
- No `v4l2loopback` module appeared in the checked module listing.
- A direct local capture through `rpicam-still` completed successfully at **1640 × 1232**.

Diagnostic command:

```sh
rpicam-still --nopreview --timeout 1500 --width 1640 --height 1232 -o /tmp/bmo-camera-diagnostic.jpg
```

The tool reported `Still capture image received`. The resulting photo was linked to the owner. Its visual sharpness was not assessed in this investigation. The `/tmp` file is temporary and may disappear after a reboot or cleanup.

This confirmed a working direct capture path, while leaving the website/browser issue unresolved. The site's selected camera name and exact error/black-preview behavior were requested but not provided before the owner said to forget the camera for now.

No browser settings were changed, camera bridge installed, or camera hardware adjustment made. Camera work is on hold at the owner's request.

## 8. Files involved

| File | Purpose of local change |
| --- | --- |
| `agent_hailo.py` | Sample-based recording stop; warmed speech startup; speaking status; thinking-clip pacing and selection |
| `core/config.py` | Model/backend and audio environment overrides |
| `core/llm.py` | CPU vision path; 384-token replies; completion logs; repetition settings and guard |
| `core/recording.py` | New sample-based silence detector |
| `start_agent.sh` | CPU Ollama readiness and desktop launch |
| `start_web.sh` | CPU Ollama readiness and localhost Uvicorn launch |
| `web_app.py` | Updated Starlette template invocation |
| `requirements-cpu.txt` | CPU-compatible wake-word dependency selection |
| `requirements-local.lock.txt` | Recorded package versions |
| `LOCAL_SETUP.md` | Initial setup and verification notes |
| `tests/unit/test_cpu_vision.py` | CPU vision routing and failure-history cleanup |
| `tests/unit/test_recording.py` | Recording threshold and silence timing behavior |
| `tests/unit/test_speech_startup.py` | Speech pipeline startup and status behavior |
| `tests/unit/test_repetition.py` | Repetition filtering and streaming/history regressions |
| `memory.json` | Removed one looping exchange |
| `memory.before-loop-cleanup.20261001T002150Z.json` | Full history backup before cleanup |
| `.env` | Local model/audio selections; ignored by Git |
| `~/.config/systemd/user/be-more-hailo-ollama.service` | User model-service configuration outside the repo |
| `BMO_CHANGE_HISTORY.md` | This history document |

At compilation time, implementation changes were still local working-tree changes and added files, rather than individual commits. Do not assume the repository commit log contains these changes.

Existing upstream mechanisms such as persistent Piper playback, lip-sync scheduling, reasoning stripping, memory throttling, and web/desktop memory isolation are referenced by the current code and tests. Their existence alone is not evidence that they were newly implemented during this local work.

## 9. Running and checking the current version

Desktop:

```sh
cd /home/kareemaljurf/be-more-hailo
./start_agent.sh
```

Optional browser interface:

```sh
cd /home/kareemaljurf/be-more-hailo
./start_web.sh
```

Open `http://127.0.0.1:8080` on the Pi. Python source changes take effect when the relevant application is restarted.

Unit tests and syntax check:

```sh
cd /home/kareemaljurf/be-more-hailo
venv/bin/python -m pytest tests/unit -q
venv/bin/python -m py_compile agent_hailo.py core/llm.py core/config.py core/recording.py
```

Inspect local changes:

```sh
git status --short
git diff -- agent_hailo.py core/config.py core/llm.py start_agent.sh start_web.sh web_app.py
```

`git diff` alone does not include the contents of newly added, untracked files. Preserve those files, the local configuration, and the service definition when backing up this setup. Restoring the original history backup would also restore the looping exchange.

The earlier setup notes advise against running the upstream Hailo installer or Hailo upgrade scripts on this CPU installation.

## 10. Future entries

For each future change, append the local date, the reported problem, files changed, before/after behavior, exact settings, tests performed, whether the running app was restarted, owner feedback, and any remaining uncertainty. Preserve previous entries so this file remains a useful history rather than only a description of the latest configuration.

## 11. September 30, 2026 — Physical button controller

### Initial state and investigation

The owner asked whether the D-pad, triangle, small circle, and big circle had functions in the current BMO code. The desktop application had screen-click actions but no dedicated bindings for these physical controls. The random-thought function's reference to a red button did not establish a physical-button binding.

Linux identified the connected board as an Adafruit Feather M0 with keyboard, mouse, and joystick interfaces. Its mounted drive, `/media/kareemaljurf/CIRCUITPY1`, reported **CircuitPython 5.2.0, Feather M0 Basic, SAMD21G18**. No `code.py` or `main.py` was present, and `lib` was empty. An initial test of the physical buttons produced no USB input events.

The owner's recording, `~/Videos/bmo-wiring.mp4`, showed seven switches and a Feather plugged directly into the custom PCB's two header sockets. The supplied `~/Downloads/gerber-bmo_controller_pcb.zip` contained Gerber manufacturing files with button net names and header-pad metadata. Mapping those nets to Feather pins provided an initial implementation, but subsequent physical tests showed that the supplied design's button assignments did **not** match this assembled controller. The reason for that discrepancy was not established.

### Implementation and corrected wiring

Added:

- [firmware/bmo_controller/code.py](firmware/bmo_controller/code.py): production controller program using built-in `board`, `digitalio`, and `usb_hid`; no external libraries.
- [firmware/bmo_controller/diagnostic.py](firmware/bmo_controller/diagnostic.py): temporary input-only diagnostic that logs pin transitions over USB serial without sending keyboard keys.
- [firmware/bmo_controller/README.md](firmware/bmo_controller/README.md): installation, measured wiring, behavior, and disable instructions.

The owner pressed controls individually while USB events and then serial pin transitions were monitored. The final mapping is based on those measurements:

| Physical control | Measured Feather pin | Final USB key |
| --- | --- | --- |
| D-pad Up | D5 | F16 |
| D-pad Down | D9 | F17 |
| D-pad Left | D10 | F18 |
| D-pad Right | D6 | F19 |
| Triangle | D11 | F13 |
| Small circle | D13 | F14 |
| Big circle | D12 | F15 |

Each switch closes to ground. The program enables internal pull-ups, filters transitions with 25 ms debounce, supports simultaneous keys within the USB keyboard's six-key limit, reports press/release names over serial, and retries USB reports after an `OSError`.

The initial program sent arrow keys from four mapped pins. The owner reported that a press opened a settings screen in Codex. Testing then temporarily captured the Adafruit keyboard, followed by the input-only diagnostic. The final program uses **F13–F19**, avoiding ordinary arrow-key desktop navigation. Other applications could still explicitly bind these function keys.

A Down test activated D9 and D10 together. A later clean Down press isolated D9; the owner clarified that one requested Left test had actually been Down. The subsequent explicit Left test isolated D10. Do not infer the final directions from the earlier grouped tests.

### Deployment and validation

- Installed the final program as `/media/kareemaljurf/CIRCUITPY1/code.py`.
- Verified that the installed file exactly matched the repository copy.
- CircuitPython automatically reloaded and printed the final startup mapping without an observed startup error.
- Python syntax compilation passed for both controller scripts.
- Individual physical tests observed presses and releases for all seven switch inputs. The final F13–F19 mapping was installed afterward; a complete USB event test of that final mapping remains to be done.
- The CircuitPython firmware itself was not upgraded or replaced.
- No BMO application action bindings were added, and the BMO application was not restarted as part of this controller work.

### Resume here

The final controller program is installed; the temporary diagnostic is retained in the repository for future troubleshooting. The owner requested a pause after updating this history.

Next session: confirm the final USB keys, agree on BMO actions for each control, and implement the corresponding application bindings. Listening, mute, volume, music, and random thoughts were discussed as possible actions, but no final action layout was selected. Existing camera follow-up remains separate and pending.

## 12. October 2, 2026 — BMO application button actions

The owner approved this layout: big circle listens, small circle toggles BMO
mute, triangle requests a random thought, Up/Down adjusts volume, Left stops
music, and Right plays music.

### Changes

- `agent_hailo.py` binds F13–F19 while the BMO window has keyboard focus. X11
  keycodes 191–197 are also recognized for desktops that give these keys XF86
  names. Held keys act once, with release/press autorepeat pairs suppressed;
  losing focus clears held-key tracking.
- Big circle requests listening when BMO is available. Busy conversation
  presses are ignored instead of starting a second conversation.
- Small circle uses the existing **audio output mute**. It does not disable the
  microphone or wake-word recognition.
- Up/Down changes volume by 10 percentage points, clamps it to 0–100%, shows
  the existing overlay, and schedules saving through the existing settings path.
- Prerecorded clips now stream through the same software volume setting, so
  volume buttons also affect music. All 50 current WAV assets were checked and
  use supported uncompressed 16-bit PCM. Changes can take a short time to reach
  the speaker because playback is buffered.
- Left stops the tracked music process and invalidates pending music starts,
  including those requested by the conversation model. A spoken introduction
  already in progress is allowed to finish, but its song is cancelled. Muting
  also cancels pending music.
- Triangle uses the existing random-thought flow. Explicit requests now work
  during quiet hours; the separate automatic screensaver quiet-hours behavior
  is unchanged.
- Updated `firmware/bmo_controller/README.md`; controller firmware was unchanged.

### Verification and remaining checks

Added `tests/unit/test_controller.py` covering action routing, autorepeat,
release and focus handling, X11 aliases, busy/warmup listening guards, volume
bounds and saving, active/pending music cancellation, and PCM volume changes.
All **123 unit tests passed**. Python compilation and `git diff --check` passed.

Physical button presses and listening checks remain pending. The application
has not yet been restarted for this change. Desktop key-map inspection from the
sandbox could not connect to display `:0`. The approved host-side check confirmed
keycodes 191–196 use XF86 aliases and 197 has no symbol, validating the need to
accept the raw X11 keycodes. No desktop key mappings were changed.


## 13. October 2, 2026 — Diagnose missing USB button events

The owner reported that buttons did not work and requested testing without BMO.
BMO remains off for these tests. A raw keyboard monitor saw no Up event. A
combined Feather serial and USB monitor then recorded `BMO up DOWN` and
`BMO up UP`, with no corresponding USB keyboard event. This confirms the board
detects that switch; the failure was downstream of pin detection.

The connected device's actual HID report descriptor advertises keyboard usage
maximum **0x65** and logical maximum **0x65** (`29 65` and `25 65`). The old
F13–F19 usages were 0x68–0x6e, outside the advertised range. The earlier firmware
key selection was incompatible with CircuitPython 5.2 on this board.

Changed controller keys to **Triangle=F6, Small circle=F7, Big circle=F8,
Up=F9, Down=F10, Left=F11, Right=F12** (0x3f–0x45). Installed the corrected
`code.py`, verified it matches the repository, and observed the automatic reload
print the new mapping without a startup error. No CircuitPython upgrade.

Updated the desktop key normalizer to accept the new keys while preserving the
approved actions and older aliases. Updated controller documentation and added
seven normalization regression cases. Physical verification of the corrected
keys is pending in a dedicated raw monitor that captures only the Feather
keyboard, preventing test presses from triggering other applications. BMO has
not been started for this test.

Corrected-key verification: the owner's next Up test produced **F9 PRESS**, hold
repeat events, and **F9 RELEASE** in the raw Linux keyboard monitor. Up now
works from the switch through USB to Linux, with BMO off. The remaining six
buttons still need raw-event confirmation. All **130 unit tests passed** after
the key-normalization update; compilation and whitespace checks passed.

Remaining-button verification: after reopening an expired capture, the owner
pressed Down, Left, Right, Triangle, Small circle, and Big circle. The raw Linux
monitor recorded press and release for each: **F10, F11, F12, F6, F7, F8**,
respectively. Together with the preceding F9 test, **all seven controls now
register from the switches through USB to Linux with BMO off**. Hold/repeat
events were also observed. One transition included Down and Left simultaneously,
followed by a separate clean Left press and release; this does not establish why
both switches activated. The test monitor was stopped to release its exclusive
keyboard capture. BMO application action testing remains pending; BMO was not
launched during these raw-button tests.


## 14. October 2, 2026 — Volume dismissal and button exit

The owner confirmed the buttons work in BMO, then reported that the volume bar
stays visible and requested a button gesture to quit.

- Fixed `_show_volume_overlay()` in `agent_hailo.py`: `Canvas.tkraise()` raises
  canvas items and requires an item/tag; calling it without one can raise a
  Tcl error before the dismissal timer is reset. The code now explicitly uses
  `tk.Misc.tkraise()` to raise the widget window.
- Volume dismissal now runs **three seconds after the last adjustment**, through
  the shared touch/controller timer.
- **Double-press Big circle within 450 ms to quit BMO** through its existing
  graceful exit handler (audio cleanup and conversation save). Single press
  waits 450 ms before requesting listening; a double press cancels that request
  before quitting. This exit gesture also works when busy. Held-key autorepeat
  does not count as another press. Losing focus cancels a pending single press.
- Updated controller documentation. Firmware and physical key mapping unchanged.

All **135 unit tests passed**, including new coverage for window raising and
volume dismissal, double-press exit while idle/busy, held-key suppression, and
focus cancellation. Python compilation and `git diff --check` passed. The app
was not restarted during this change; on-device timing and exit feedback remain
pending after restart.

## 15. October 2, 2026 — Unexpected mute investigation

The owner reported that wake-word detection was fine again, then reported BMO
muting without a deliberate press. No wake-word code/settings were changed in
the preceding investigation.

Code inspection found one mute-state toggle, reachable through the small-circle
key and two legacy touchscreen regions (mouth and lower-left). No timer or
model action toggles `is_muted`. Existing observed BMO output from this session
included `[CLICK] Bottom-Left: Toggle Mute (0,479)` followed by `SHHH: Muted`,
then another such click/unmute and a triple-tap exit. These logs establish that
screen clicks triggered those mute changes; they do not identify what generated
the clicks or prove that every reported occurrence has the same cause.

A 45-second raw monitor of only the ft5x06 touchscreen and Feather input devices
recorded no input during the requested untouched check. BMO was not running.
The unexpected input was not reproduced. Persisted software volume was 100%.

Removed the two touchscreen mute actions in `agent_hailo.py`. Those former mute
zones now ignore clicks instead of muting or waking BMO. The small-circle key
retains the agreed mute toggle. Other screen controls, including triple-tap
exit, remain as before. Added a console message on each mute-control toggle and
updated controller documentation. No hardware or firmware changes.

All **141 unit tests passed**, including six regression cases for former touch
mute zones while idle and speaking. Python compilation and `git diff --check`
passed. BMO was not launched or restarted for this change; owner confirmation
that unexpected mute has stopped remains pending after restart.


## 16. October 2, 2026 — End-of-session summary and resume point

This section consolidates today's work. Sections 12–15 retain the intermediate
changes, failures, evidence, and test results. Earlier references to F13–F19 as
the installed keys are historical; the installed controller now sends F6–F12.

### Current physical controls

| Control | Feather pin | Installed USB key | BMO action |
| --- | --- | --- | --- |
| Triangle | D11 | F6 | Request a random thought |
| Small circle | D13 | F7 | Toggle audio output mute; microphone stays enabled |
| Big circle, single press | D12 | F8 | Start listening after a 450 ms double-press window, when available |
| Big circle, double press | D12 | F8 | Quit through the existing graceful exit handler; second press within 450 ms |
| D-pad Up | D5 | F9 | Raise volume by 10 percentage points |
| D-pad Down | D9 | F10 | Lower volume by 10 percentage points |
| D-pad Left | D10 | F11 | Stop music and cancel pending song starts |
| D-pad Right | D6 | F12 | Play a random song when available and unmuted |

Bindings require the BMO window to have keyboard focus. Held buttons act once;
a release is required before another press. Volume is limited to 0–100%, saved
through the existing settings path, and applies to speech and prerecorded
music/clips. Its overlay disappears three seconds after the last adjustment.
Stopping music allows an introduction already being spoken to finish, but
prevents its song from starting. Explicit random-thought requests work during
quiet hours; automatic screensaver quiet hours remain unchanged.

The desktop still accepts the original F13–F19 aliases, but the board cannot
send those keys reliably with its installed USB descriptor. The corrected
F6–F12 program was copied to `/media/kareemaljurf/CIRCUITPY1/code.py`, compared
with the repository copy, and observed reloading successfully. CircuitPython
itself was not upgraded. All seven physical switches were confirmed to produce
USB press and release events. The owner subsequently reported that the BMO
button actions worked.

### Fixes completed today

1. Added application actions for the seven physical controls, held-key
   suppression, and focus-loss cleanup.
2. Diagnosed the incompatible F13–F19 HID usages using both serial pin messages
   and the connected device's actual USB descriptor; installed F6–F12 instead.
3. Connected prerecorded music and clips to BMO's software volume setting and
   added cancellation of active/pending music.
4. Fixed the volume overlay's incorrect Canvas raise call and changed its
   dismissal delay to three seconds.
5. Added the big-circle double-press exit without starting a listening turn
   first. Single-press listening remains available after the 450 ms delay.
6. Removed the legacy mouth/lower-left touchscreen mute shortcuts after logs
   showed lower-left clicks toggling mute. Those zones now ignore clicks;
   mute remains available through the small-circle key. Other touchscreen
   actions, including triple-tap exit, were retained.

### Wake-word investigation: no settings changed

The owner briefly reported that the wake word was no longer recognized.
Inspection found the USB microphone enabled, its capture level at 62%, automatic
gain control on, and the wake-word threshold still **0.35**. The model remained
`wakeword.onnx`, with 48 kHz microphone capture resampled to 16 kHz. The recent
control changes had not altered this detection path.

A standalone 45-second diagnostic compared the existing detector, which skips
very quiet frames, with a detector fed every frame. It saved no audio. Both
maximum scores were about **0.000965**; the captured peak was **1631**, with
518 frames, two quiet frames skipped, and 21 input overflows. This diagnostic
ran two models at once, so its overflow count does not establish the behavior
of the normal single-model application. There was no confirmed spoken-test
response during the capture, so these scores do not prove that the model
failed on an intentional wake phrase.

The owner then reported **“its fine now.”** No microphone level, wake-word
threshold, model, or wake-word implementation was changed, and no cause for
the temporary problem was established.

### Files changed today

| File | Today's changes |
| --- | --- |
| `agent_hailo.py` | Controller bindings and key normalization; audio clip volume; music cancellation; volume overlay fix; double-press exit; removal of touchscreen mute |
| `firmware/bmo_controller/code.py` | Supported F6–F12 USB key mapping |
| `firmware/bmo_controller/README.md` | Corrected key mapping, current actions, timing, descriptor findings, and mute behavior |
| `tests/unit/test_controller.py` | Controller, audio-volume, gesture, overlay, and touchscreen-mute regressions |
| `BMO_CHANGE_HISTORY.md` | Today's changes, diagnostic evidence, verification, and resume notes |

The other existing modified files and conversation-history backup predate
these changes. Work remains local; no commit or publication was made. Temporary
scripts under `/tmp/bmo_*` were used for USB, serial, microphone, and input
checks. They are diagnostic helpers, not required application components, and
may disappear after cleanup or reboot. The exclusive keyboard test capture was
released after button testing.

### Validation, owner feedback, and resume here

- Latest implementation verification: **141 unit tests passed**, Python
  compilation passed, and `git diff --check` passed. This final history update
  changes documentation only.
- BMO was launched during the initial button investigation. One observed run
  exited after three lower-left screen clicks. At the owner's request, subsequent
  raw controller tests were performed with BMO off.
- The owner confirmed the application button actions worked before requesting
  the volume-dismissal and quit-gesture changes, and later confirmed wake-word
  behavior was fine again.
- The later volume/exit and touchscreen-mute changes were not restarted or
  physically verified by the assistant. The owner's “ok great” acknowledged
  the mute fix but did not explicitly confirm a new on-device test.
- After restarting BMO, confirm that the volume bar hides after three seconds,
  single big-circle press listens, double press quits, and unexpected mute has
  stopped. If unexpected input recurs, investigate the touchscreen/input source;
  the 45-second untouched input check did not reproduce it. One Down/Left
  overlap was seen in button testing, followed by a clean Left press.
- Camera quality and browser-camera work remain on hold from the earlier
  session. No camera work was performed today.


## 17. October 2, 2026 — Prepare complete project updates for GitHub

At the owner's request, gathered all local implementation changes from the CPU
setup through the controller and mute fixes for the owner's GitHub fork:
`https://github.com/KareemAlJurf/BMO-AI-Assistant-project`.

Fetched the fork's main branch and fast-forwarded the local checkout to its
existing README commit `7632725`, preserving that README work. Added a short
current-CPU-setup section linking the new setup notes and controller guide.
The original upstream remote remains `origin`; the owner's fork is `fork`.

Added `.env.cpu.example` with the non-secret CPU configuration, and
`deploy/be-more-hailo-ollama.service` reproducing the installed user service with
`%h` in place of the local home-directory path. Extended `LOCAL_SETUP.md` with
configuration steps and prerequisites. Added ignore rules for conversation
backup JSON files so the original history backup cannot be uploaded accidentally.

The intended upload includes application/core changes, launchers, new recording
logic, controller firmware and documentation, all added unit tests, CPU
requirements/recorded package versions, setup examples, and this change history.
Private `.env`, chat history and its backup, volume preferences, virtual
environments, generated bytecode, and downloaded model binaries remain local.
The GitHub push result will be reported after the upload attempt.
