# Local CPU setup on this Pi

Installed from https://github.com/moorew/be-more-hailo in `~/be-more-hailo`.
No Hailo accelerator was detected. This installation uses the Pi 5 CPU:

- Conversation: existing Ollama `qwen2.5:1.5b`.
- Camera descriptions: Ollama `moondream`.
- Speech recognition: whisper.cpp with `ggml-base.en.bin`, four threads.
- Voice: bundled BMO ONNX model with ARM64 Piper.
- Wake word: bundled ONNX model with openWakeWord.

## Start

Double-click **Be More Hailo** on the desktop, or run:

```sh
~/be-more-hailo/start_agent.sh
```

Press Escape to exit the desktop app. The launcher starts the local model
service when needed. It does not install packages on each launch.

For the optional browser interface:

```sh
~/be-more-hailo/start_web.sh
```

Then open http://127.0.0.1:8080 on this Pi. Press Ctrl+C in its terminal to stop.
The web listener and model server bind to localhost.

Device settings are in `.env`. `ALSA_DEVICE=default` follows the system's
selected speaker, including Bluetooth. The USB microphone is discovered at
startup. The camera is an imx219.

```sh
systemctl --user stop be-more-hailo-ollama.service
```

stops the model server. Neither the GUI nor the model service is enabled at boot.

## Local changes

`core/config.py` accepts model URL/name and audio overrides. `core/llm.py`
supports standard Ollama image requests when `VISION_BACKEND=ollama`.
The launch scripts use standard Ollama. The Python environment uses ONNX-only openWakeWord 0.4.0. These changes are local and can be inspected with `git diff`.
Do not run the upstream Hailo installer or upgrade scripts for this CPU setup.

Inference uses local models without an API key. The upstream app also offers
online search features, which require internet when invoked.

## Verification

- 88 unit tests passed, including CPU vision routing and failure cleanup.
- Python dependency check passed. Exact versions: `requirements-local.lock.txt`.
- Whisper transcribed the bundled JFK sample correctly in about four seconds.
- Piper produced valid 22050 Hz speech; default speaker playback returned success.
- USB microphone capture succeeded without overflow.
- Custom wake-word model loaded and scored silence as zero.
- GUI reached `idle` / `Tap to speak` with microphone listening.
- Moondream identified a synthetic red image (about 23 seconds).

The web template call was also updated for the installed Starlette API.
CPU response times depend on prompt length and other work on the Pi.

- Browser home, status, and face endpoints returned HTTP 200; model status online.
- Full app chat pipeline replied successfully in about 13 seconds.


## Recreate the local CPU configuration

These are configuration steps for a machine with Ollama, Piper, whisper.cpp,
the voice/wake-word models, and the Python virtual environment already installed.
The model binaries and virtual environment are not included in Git.

1. Create `.env` from `.env.cpu.example`, preserving your own existing settings
   if `.env` is already present.
2. Install Python dependencies in the project virtual environment with
   `venv/bin/python -m pip install -r requirements-cpu.txt`. The lock file records
   the versions used on this Pi; it is not a cross-platform installation guarantee.
3. The supplied `deploy/be-more-hailo-ollama.service` expects the Ollama binary at
   `~/.local/opt/ollama/bin/ollama`. Adjust `ExecStart` if installed elsewhere.
4. Copy that service to `~/.config/systemd/user/be-more-hailo-ollama.service`, then
   run `systemctl --user daemon-reload` and
   `systemctl --user start be-more-hailo-ollama.service`.
5. Use your Ollama executable to pull `qwen2.5:1.5b` and `moondream` if they are
   not already installed, then use `./start_agent.sh` or `./start_web.sh`.

The service binds to localhost and is started by the launchers. Installing the
service file does not enable startup at boot. See `BMO_CHANGE_HISTORY.md` for
current behavior and `firmware/bmo_controller/README.md` for button installation
and controls. Personal `.env`, settings, chat history, and conversation backups
remain local.
