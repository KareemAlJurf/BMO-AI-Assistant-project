# Be More Agent — Hailo-10H Edition

<p align="center">
  <img src="bmo_irl.jpg" height="300" alt="BMO On-Device" />
  <img src="bmo-web.png" height="300" alt="BMO Web Interface" />
</p>

A fork of [@brenpoly's be-more-agent](https://github.com/brenpoly/be-more-agent) project, built to run fully on-device on a **Raspberry Pi 5** with the **Raspberry Pi AI HAT 2+** (Hailo-10H). BMO listens for its wake word, understands what you say, thinks about it locally, and talks back.

This fork adds a browser-based **web interface**, a shared `core/` module layer used by both interfaces, updated support for the Hailo NPU hardware, and additional hardware features for my physical BMO build.

---

## My Additions

I added custom battery and power-management support for my physical BMO build using the **Geekworm X1203 UPS**.

My additions include:

- Battery percentage monitoring
- Battery voltage monitoring
- X1203 fuel-gauge communication over I²C
- Low and critical battery-state detection
- Low-battery BMO face integration
- Spoken low-battery warnings
- Safe shutdown protection before the battery is fully depleted
- A standalone battery test utility

I added the following files:

```text
battery_manager.py
battery_integration.py
test_battery.py
```

The battery system uses the `smbus2` Python package to communicate with the X1203 fuel gauge.

---

## What runs where

| Component | Where it runs | Notes |
|-----------|--------------|-------|
| LLM (`qwen3:1.7b`) | Hailo-10H NPU | via `hailo-ollama` on port 8000 |
| Vision (`Qwen3-VL-2B-Instruct`) | Hailo-10H NPU | via HailoRT Python API |
| STT (`whisper.cpp`) | CPU | Local speech-to-text |
| TTS (Piper) | CPU | Streams speech locally |
| Wake word (openWakeWord) | CPU | "Hey BMO" custom model |
| Battery Monitor | X1203 / Raspberry Pi | Reads battery percentage and voltage over I²C |

### The NPU is single-tenant

HailoRT can only share one physical device between processes under certain configurations, while `hailo-ollama` requests exclusive access to the Hailo device.

Because of this, the main NPU workload is the LLM.

- **Speech-to-text runs on the CPU by default** using `whisper.cpp`.
- **The vision model temporarily uses the NPU** when a photo needs to be analyzed.
- The main LLM uses the Hailo NPU through `hailo-ollama`.

---

## Interfaces

### On-Device (`agent_hailo.py`)

BMO's main physical interface.

With a screen, microphone, speaker, and camera connected, BMO can:

- Display animated faces
- Detect the wake word
- Listen to speech
- Transcribe speech locally
- Generate responses using the local LLM
- Speak responses through Piper TTS
- Analyze images using the camera
- Respond to touchscreen interaction

### Web (`web_app.py`)

A FastAPI-based browser interface for interacting with BMO remotely on the local network.

The web interface includes:

- Conversation history
- Server logs
- Pronunciation overrides
- LLM status
- Hands-free mode
- Pi audio output control

---

## Interactive Features

BMO includes several interactive capabilities beyond basic conversation:

- **Timers & Alarms:** Ask BMO to set timers or reminders.
- **Minigames:** BMO can host trivia and guessing games.
- **Vision Analysis:** BMO can take a photo and analyze what the camera sees.
- **Music:** BMO can play local music and display its `jamming` animation.
- **Tap to Speak:** Tap the screen after a response to speak again without repeating the wake word.
- **Animated Expressions:** BMO changes facial expressions based on its current state and response.
- **Persistent Chat History:** Conversations can be stored locally and restored after restarting.

---

## Hardware

My physical BMO build uses:

- Raspberry Pi 5
- Raspberry Pi AI HAT 2+ / Hailo-10H
- Geekworm X1203 UPS
- Rechargeable battery
- 5-inch DSI touchscreen
- Raspberry Pi Camera Module
- USB microphone
- USB speaker
- Active cooling
- Custom BMO enclosure and controls

---

## Battery & Power Management

This fork adds battery awareness using the **Geekworm X1203 UPS**.

The X1203 fuel gauge is accessed through I²C at:

```text
0x36
```

The battery manager can read:

- Battery percentage
- Battery voltage
- Battery state
- Timestamp of the reading

### Battery Behavior

| Battery Level | BMO Behavior |
|---------------|--------------|
| Above 20% | Normal operation |
| 20% | Low-battery state |
| 15% | Spoken low-battery warning |
| 5% | Safe shutdown after repeated critical readings |

At low battery, BMO can display its existing:

```text
low_battery
```

face.

At approximately 15%, BMO can say:

```text
I'm getting tired. I need to be charged.
```

At approximately 5%, the integration can trigger a safe Raspberry Pi shutdown after confirming multiple critical readings.

### Battery Files

#### `battery_manager.py`

Handles communication with the X1203 fuel gauge.

It reads:

- Battery voltage
- Battery percentage
- Battery state

It can also run independently from the main BMO application.

Example:

```bash
python battery_manager.py
```

Continuous monitoring:

```bash
python battery_manager.py --monitor
```

JSON output:

```bash
python battery_manager.py --json
```

---

#### `battery_integration.py`

Connects the battery monitor to BMO's behavior.

It handles:

- Low-battery face activation
- Spoken battery warnings
- Critical battery detection
- Safe shutdown behavior

The integration is callback-based so it can connect to the existing BMO application without tightly coupling the battery code to the GUI.

---

#### `test_battery.py`

A simple standalone test for verifying that the Raspberry Pi can communicate with the X1203.

Run:

```bash
python test_battery.py
```

Example output:

```text
Charge: 82.5%
Voltage: 4.05 V
State: normal
```

---

## Features & Recent Updates

- **Gapless TTS:** Piper remains active during the speaking turn so sentences flow naturally.
- **Lip-Sync:** BMO uses multiple mouth shapes while speaking.
- **Touch-Friendly Volume Control:** Volume can be adjusted through the touchscreen interface.
- **Tap to Speak:** Tap the screen to start another conversation without repeating the wake word.
- **Persistent Chat History:** Conversations are stored locally.
- **Web Interface:** Browser-based interface for interacting with BMO.
- **Vision:** Camera-based image analysis using the Hailo NPU.
- **Wake Word Detection:** BMO listens locally for "Hey BMO."
- **Battery Monitoring:** X1203 battery percentage and voltage monitoring.
- **Low-Battery Behavior:** BMO can react visually and verbally when power is running low.
- **Safe Shutdown:** Protects the Raspberry Pi from losing power unexpectedly.

---

## Project Structure

```text
be-more-agent/
├── agent_hailo.py             # Main on-device BMO application
├── web_app.py                 # FastAPI web interface
│
├── battery_manager.py         # X1203 battery percentage and voltage reader
├── battery_integration.py     # Battery behavior and shutdown integration
├── test_battery.py            # Standalone battery test
│
├── core/
│   ├── config.py              # Configuration and hardware settings
│   ├── llm.py                 # LLM inference and conversation logic
│   ├── tts.py                 # Piper text-to-speech
│   └── stt.py                 # Speech-to-text
│
├── templates/                 # Web interface templates
├── static/                    # Web interface assets
│
├── start_web.sh               # Starts web interface
├── start_agent.sh             # Starts physical BMO interface
├── setup_services.sh          # System service configuration
│
├── requirements.txt           # Python dependencies
├── wakeword.onnx              # OpenWakeWord model
│
├── piper/                     # Piper TTS engine
├── models/                    # AI model files
├── whisper.cpp/               # CPU speech-to-text
│
├── generate_faces.py          # Face animation generator
├── svg_faces/                 # Original SVG face assets
├── faces/                     # Generated BMO face animations
└── sounds/                    # Audio and music assets
```

---

## Running

### On-Device BMO

Activate the Python environment:

```bash
source venv/bin/activate
```

Start BMO:

```bash
./start_agent.sh
```

---

### Web Interface

Start the web interface:

```bash
./start_web.sh
```

The web interface normally runs on:

```text
http://localhost:8080
```

The Hailo LLM backend normally runs on:

```text
http://localhost:8000
```

---

### Battery Test

Test the X1203 independently:

```bash
source venv/bin/activate
python test_battery.py
```

Monitor the battery continuously:

```bash
python battery_manager.py --monitor
```

---

## Configuration

Most hardware and model configuration is located in:

```text
core/config.py
```

Important settings include:

```python
LLM_MODEL = "qwen3:1.7b"
FAST_LLM_MODEL = "qwen3:1.7b"

VLM_HEF_PATH = "./models/Qwen3-VL-2B-Instruct.hef"

MIC_DEVICE_INDEX = 1
MIC_SAMPLE_RATE = 48000
```

The USB microphone and speaker configuration may need to be adjusted depending on the hardware connected to the Raspberry Pi.

---

## Camera and Vision

BMO supports a Raspberry Pi Camera Module for visual interaction.

Example requests include:

```text
Hey BMO, what am I holding?
```

or:

```text
Hey BMO, take a picture and tell me what you see.
```

BMO captures an image using the Raspberry Pi camera and processes it using the local vision model.

The vision model temporarily uses the Hailo NPU when analyzing an image.

---

## Credits & Acknowledgments

- **Original Project:** This project is based on [@brenpoly's be-more-agent](https://github.com/brenpoly/be-more-agent).
- **Hailo Fork:** This project builds on the Hailo version developed by [@moorew](https://github.com/moorew/be-more-hailo).
- **Custom BMO Voice:** Credit to **Brenpoly** for the custom BMO neural voice model.
- **Face Artwork:** BMO's face artwork is based on SVG artwork by **Cherry Honey**, shared through the Figma Community.
- **Lip-Sync:** Additional lip-sync animation work was created by **moorew**.
- **Hardware Additions:** I added battery and power-management support for my physical BMO build using the Geekworm X1203 UPS.

---

## Credits

The original BMO assistant concept and implementation come from:

[@brenpoly/be-more-agent](https://github.com/brenpoly/be-more-agent)

The Hailo-based Raspberry Pi implementation is based on:

[@moorew/be-more-hailo](https://github.com/moorew/be-more-hailo)

My fork adds additional hardware-focused features for my physical BMO build, including **battery monitoring, low-battery behavior, and power-management support**.

BMO's face artwork is based on artwork by **Cherry Honey**, shared through the Figma Community.

**"BMO"** and **"Adventure Time"** are trademarks of Cartoon Network / Warner Bros. Discovery.

This is a fan-made project created for personal and educational use and is not affiliated with or endorsed by Cartoon Network.

---

## License

MIT — see [LICENSE](LICENSE).
