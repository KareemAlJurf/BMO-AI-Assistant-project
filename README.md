# Be More Agent — Hailo-10H Edition

<p align="center">
  <img src="bmo_irl.jpg" height="300" alt="BMO On-Device" />
  <img src="bmo-web.png" height="300" alt="BMO Web Interface" />
</p>

A fork of [@brenpoly's be-more-agent](https://github.com/brenpoly/be-more-agent) project, built to run fully on-device on a **Raspberry Pi 5** with the **Raspberry Pi AI HAT 2+** (Hailo-10H). BMO listens for its wake word, understands what you say, thinks about it locally, and talks back — no cloud, no subscriptions, no data leaving your house.

This fork adds a browser-based **web interface**, a shared `core/` module layer used by both interfaces, and updated support for the Hailo NPU hardware.

---

## What runs where

| Component | Where it runs | Notes |
|-----------|--------------|-------|
| LLM (`qwen3:1.7b`) | Hailo-10H NPU | via `hailo-ollama` on port 8000 |
| Vision (`Qwen3-VL-2B-Instruct`) | Hailo-10H NPU | via HailoRT Python API; optional, requires camera; borrows the NPU per photo |
| STT (`whisper.cpp`, `ggml-base.en`) | CPU | ~2.7 s per utterance; NPU Whisper is opt-in, see below |
| TTS (Piper) | CPU | streams sentence-by-sentence while LLM generates |
| Wake word (openWakeWord) | CPU | "Hey BMO" custom model |

### The NPU is single-tenant

This is the most important thing to know about this machine. HailoRT can only
share one physical device between processes via `multi_process_service`, which
needs a `hailort` daemon that isn't installed — and `hailo-ollama` requests an
**exclusive** VDevice regardless. Whichever process opens `/dev/hailo0` first
owns it until that process exits.

So the NPU budget is: **the LLM gets it.** Consequences:

- **NPU speech-to-text is off by default.** `hailo_platform.genai.Speech2Text`
  holds its VDevice for the life of the process, so the first thing BMO ever
  transcribed would permanently starve `hailo-ollama` — BMO could hear you but
  never think again. Set `BMO_NPU_STT=1` to enable it anyway (and accept that
  the LLM will stop working). CPU `whisper.cpp` with `ggml-base.en` is the
  default: ~2.7 s for a 3 s utterance, against ~22 s for `ggml-small.en`.
- **The VLM borrows the NPU per photo** and releases it immediately afterwards,
  paying ~3 s of init each time so the LLM survives. Photos are rare; thinking
  is not.
- If everything suddenly stops working, the driver is the first suspect — see
  [docs/MAINTENANCE.md](docs/MAINTENANCE.md).

---

## Interfaces

### On-Device (`agent_hailo.py`)
BMO in its natural habitat. Plug in a screen, a USB mic, and a USB speaker and you get the full experience: animated faces, wake word detection, and the whole listen → think → speak loop running locally. After a response, tap the screen (or the tap button) to speak again without repeating the wake word — the screen shows "Tap to speak" when BMO is ready.

### Web (`web_app.py`)
A FastAPI server with a browser-based UI — useful if you want to talk to BMO from another room, or you'd rather not have a screen hanging off your Pi. Hold a button to record, and BMO responds with audio in your browser.

The web interface includes:
- **Debug panel** — conversation history and live server logs
- **Pronunciation override** — corrects how Piper pronounces specific words
- **LLM status indicator** — shows whether the NPU model is ready
- **Hands-free mode** — enables wake word detection so you don't need to hold the button
- **Pi Audio toggle** — routes audio to the Pi's physical speaker instead of browser playback

---

## Interactive Features

BMO includes several dynamic, interactive capabilities beyond basic conversation:

- **Timers & Alarms:** Ask BMO to *"Set a timer for 10 minutes"* or *"Remind me to check the oven"*. BMO will happily interrupt you later when the time is up!
- **Minigames:** BMO is a living game console. Say *"Let's play Trivia"* or *"Let's play a guessing game"* — BMO will act as the host, wait for your answers, and keep score.
- **Vision Analysis:** Hold an object up to the camera and say *"What am I holding?"* or *"Does this look good?"*. BMO will snap a photo, analyze it using the local VLM, and give you its opinion.
- **Musical Talent:** Ask BMO to *"Play some music"* or *"Sing a song"*, and BMO will cycle into a dancing `Jamming` face while playing chiptunes (add your own `.wav` files to `sounds/music/`).
- **Idle Pet Animations:** When left alone in Screensaver mode, BMO will periodically (and silently) show affection by flashing pixelated hearts, getting dizzy, or falling asleep to keep your desk feeling alive.

---

## Hardware

- Raspberry Pi 5 (4GB or 8GB recommended)
- Raspberry Pi AI HAT 2+ (Hailo-10H, required for NPU features)
- USB microphone and speaker (for on-device mode)
- HDMI or DSI display (for on-device GUI)
- Raspberry Pi Camera Module (optional, for vision/photo features)

---

## Credits & Acknowledgments

- **Original Project:** This is a fork of [@brenpoly's be-more-agent](https://github.com/brenpoly/be-more-agent).
- **Custom BMO Voice:** Huge thanks to **Brenpoly** for his work fine-tuning the custom BMO neural voice model (`v1.0-voice`). This model provides the more accurate, charming BMO voice you hear today!
- **Face Artwork:** BMO's face animations are rendered from SVG artwork by **Cherry Honey**, published as a free community resource on Figma. Thank you for the pixel-perfect expressions that bring BMO to life! [Cherry Honey BMO Faces on Figma Community](https://www.figma.com/community/file/1379945530999597632)
- **Lip-Sync Visemes:** BMO's 6 talking mouth shapes were hand-animated by **moorew** using Rhubarb Lip Sync and After Effects — properly articulated visemes trained on real speech, replacing the original procedurally-generated shapes.
- **Community Features:** This fork imports several interactivity and utility features from the upstream `be-more-agent` project, including DuckDuckGo News search, fast nearest-neighbor audio resampling, and robust silence detection (VAD).
- **Hardware Support:** Built for the Raspberry Pi 5 + Raspberry Pi AI HAT 2+ (Hailo-10H).

---

## Features & Recent Updates

- **Gapless TTS:** Piper is held open for the entire speaking turn — sentences stream out one after another with no startup gap between them, so long answers sound natural rather than staccato.
- **Articulate Lip-Sync:** Talking drives a 6-shape viseme palette (closed → tiny lip-crack → small open → round /o/ → wide /a/ → full open) derived from Rhubarb-animated, artist-drawn frames.
- **Touch-Friendly Volume Slider:** Tap the top-centre of BMO's face to bring up a chunky, BMO-styled volume slider.
- **Tap to Speak:** After BMO answers, tap the screen to speak again immediately without re-saying the wake word.
- **Persistent Chat History:** Conversations are saved to `memory.json` and reloaded on restart.
- **Web UI Refactor:** Fully responsive, mobile-friendly interface.
- **Improved Aliveness:** Interactive pondering mode.
- **Enhanced Search:** BMO can search for current news and regional information.
- **Audio Stability:** Improved ALSA contention handling for more reliable wake-word detection and voice recording.
- **Desktop Ready:** Includes a `.desktop` launcher.

---

## Project structure

```text
be-more-agent/
├── agent_hailo.py
├── web_app.py
├── battery_manager.py
├── battery_integration.py
├── test_battery.py
├── core/
│   ├── config.py
│   ├── llm.py
│   ├── tts.py
│   └── stt.py
├── templates/
├── static/
├── install.sh
├── setup_services.sh
├── start_web.sh
├── start_agent.sh
├── requirements.txt
├── wakeword.onnx
├── piper/
├── models/
├── whisper.cpp/
├── generate_faces.py
├── svg_faces/
├── faces/
└── sounds/
