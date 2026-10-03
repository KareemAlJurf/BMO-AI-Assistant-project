"""Exercise GUI speech startup without initializing the display or microphone."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import time

import pytest


@pytest.mark.parametrize("warmed", [False, True])
def test_speech_connects_audio_before_writing_and_reuses_pipeline(warmed):
    source = Path(__file__).resolve().parents[2] / "agent_hailo.py"
    tree = ast.parse(source.read_text())
    speak = next(node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == "speak")
    states = SimpleNamespace(DISPLAY_IMAGE="image", SPEAKING="speaking", IDLE="idle")
    namespace = {"BotStates": states, "time": time}
    exec(compile(ast.Module(body=[speak], type_ignores=[]), str(source), "exec"), namespace)
    process = Mock()
    process.poll.return_value = None
    bot = SimpleNamespace(
        _piper_proc=process if warmed else None,
        _piper_reader_thread=None, _tts_aplay=None,
        current_state=states.SPEAKING, is_muted=False,
        speak_lock=threading.Lock(), _end_tts_turn=Mock(),
    )

    def start():
        bot._piper_proc = process
        bot._piper_reader_thread = Mock()
        bot._tts_aplay = Mock()

    def write(text):
        assert bot._piper_reader_thread is not None
        assert bot._tts_aplay is not None

    bot._start_tts_turn = Mock(side_effect=start)
    bot._write_to_piper = Mock(side_effect=write)
    namespace["speak"](bot, "Hello friend!", msg=None, end_of_turn=False)
    namespace["speak"](bot, "Here is your poem.", msg=None, end_of_turn=True)
    bot._start_tts_turn.assert_called_once()
    assert bot._write_to_piper.call_count == 2
    bot._end_tts_turn.assert_called_once_with(drain=True)


def test_streamed_reply_uses_speaking_status():
    source = Path(__file__).resolve().parents[2] / "agent_hailo.py"
    tree = ast.parse(source.read_text())
    handler = next(node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef)
                   and node.name == "_handle_response_chunk")
    namespace = {"extract_json_object": lambda text: (None, None)}
    exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), "exec"), namespace)
    calls = []

    def speak(text, msg="Speaking...", end_of_turn=True):
        calls.append((text, msg, end_of_turn))

    bot = SimpleNamespace(speak=speak)
    namespace["_handle_response_chunk"](bot, "Hello friend!", is_last=False)
    namespace["_handle_response_chunk"](bot, "Let's play!", is_last=True)
    assert calls == [("Hello friend!", "Speaking...", False),
                     ("Let's play!", "Speaking...", True)]
