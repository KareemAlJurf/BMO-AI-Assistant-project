"""Controller behavior without initializing AI engines, audio hardware, or Tk."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import time
import wave

import numpy as np
import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'agent_hailo.py'
TREE = ast.parse(SOURCE.read_text())
CLASS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'BotGUI')
STATES = SimpleNamespace(**{name: name for name in (
    'WARMUP', 'IDLE', 'LISTENING', 'THINKING', 'SPEAKING', 'CAPTURING', 'JAMMING')})


def bot_with(*methods, **extra):
    namespace = dict(time=time, threading=threading, BotStates=STATES,
                     np=np, wave=wave, ALSA_DEVICE='default', **extra)
    nodes = [n for n in CLASS.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    cls = ast.ClassDef(name='Bot', bases=[], keywords=[], body=nodes, decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 str(SOURCE), 'exec'), namespace)
    return namespace['Bot']()


def controller():
    bot = bot_with('_controller_key', '_controller_press', '_controller_release',
                   '_controller_focus_out', '_controller_listen')
    bot.master = Mock()
    bot.master.tk.call.return_value = 'x11'
    bot._controller_held = set()
    bot._controller_releases = {}
    bot._controller_wake_job = None
    bot.stop_event = threading.Event()
    bot.exit_fullscreen = Mock()
    bot.last_user_interaction = 0
    bot.current_state = STATES.IDLE
    bot.is_busy = False
    bot.volume = 0.5
    bot.manual_wake_event = threading.Event()
    for name in ('trigger_random_thought', 'mute_bmo', 'stop_music', 'trigger_music',
                 '_show_volume_overlay', '_on_vol_release'):
        setattr(bot, name, Mock())
    return bot


@pytest.mark.parametrize('key,action', [('F13', 'trigger_random_thought'),
    ('F14', 'mute_bmo'), ('F18', 'stop_music'), ('F19', 'trigger_music')])
def test_actions_run_once_per_physical_press(key, action):
    bot = controller()
    event = SimpleNamespace(keysym=key, keycode=0)
    bot._controller_press(event)
    bot._controller_release(event)
    bot._controller_press(event)  # X11 synthetic repeat pair
    getattr(bot, action).assert_called_once()
    bot.master.after_cancel.assert_called_once()
    bot._controller_release(event)
    bot.master.after_idle.call_args.args[0]()  # actual release
    bot._controller_press(event)
    assert getattr(bot, action).call_count == 2


def test_x11_aliases_and_unrelated_keys():
    bot = controller()
    for code, key in zip(range(191, 198), range(13, 20)):
        assert bot._controller_key(SimpleNamespace(keysym='XF86Alias', keycode=code)) == f'F{key}'
    assert bot._controller_press(SimpleNamespace(keysym='a', keycode=38)) is None
    bot.master.tk.call.return_value = 'win32'
    assert bot._controller_key(SimpleNamespace(keysym='Other', keycode=191)) is None


@pytest.mark.parametrize('state,busy,wakes', [
    ('IDLE', False, True), ('WARMUP', False, False),
    ('SPEAKING', False, False), ('IDLE', True, False)])
def test_listen_does_not_queue_a_second_conversation(state, busy, wakes):
    bot = controller()
    bot.current_state, bot.is_busy = state, busy
    bot._controller_press(SimpleNamespace(keysym='F15', keycode=0))
    assert not bot.manual_wake_event.is_set()
    bot.master.after.call_args.args[1]()
    assert bot.manual_wake_event.is_set() is wakes


@pytest.mark.parametrize('key,initial,expected', [('F16', .95, 1),
    ('F17', .05, 0), ('F16', .5, .6), ('F17', .5, .4)])
def test_volume_is_clamped_shown_and_saved(key, initial, expected):
    bot = controller()
    bot.volume = initial
    bot._controller_press(SimpleNamespace(keysym=key, keycode=0))
    assert bot.volume == expected
    bot._show_volume_overlay.assert_called_once()
    bot._on_vol_release.assert_called_once_with(None)


def test_focus_loss_clears_held_buttons():
    bot = controller()
    event = SimpleNamespace(keysym='F14', keycode=0)
    bot._controller_press(event)
    bot._controller_release(event)
    bot._controller_focus_out(None)
    assert not bot._controller_held and not bot._controller_releases
    bot._controller_press(event)
    assert bot.mute_bmo.call_count == 2


def test_stop_cancels_active_and_queued_music_only():
    bot = bot_with('stop_music', '_play_music_generation')
    bot._music_lock = threading.Lock()
    bot._music_generation = 0
    bot._music_process = process = Mock()
    bot.current_state = STATES.JAMMING
    bot.stop_event = threading.Event()
    bot.set_state = Mock()
    bot.play_sound = Mock()
    bot.stop_music()
    process.terminate.assert_called_once()
    assert bot._music_process is None
    assert bot._play_music_generation(0) is None
    bot.play_sound.assert_not_called()
    bot._play_music_generation(1)
    bot.play_sound.assert_called_once_with('music')


def test_recorded_audio_follows_volume_changes(tmp_path):
    sound = tmp_path / 'clip.wav'
    with wave.open(str(sound), 'wb') as output:
        output.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
        output.writeframes(np.full(4096, 1000, dtype='<i2').tobytes())
    process = Mock()
    subprocess = SimpleNamespace(Popen=Mock(return_value=process), PIPE=-1)
    # Run the feeding worker synchronously for deterministic sample inspection.
    class ImmediateThread:
        def __init__(self, target, **kwargs): self.target = target
        def start(self): self.target()
    bot = bot_with('_start_sound_playback', subprocess=subprocess)
    bot._start_sound_playback.__func__.__globals__['threading'] = SimpleNamespace(Thread=ImmediateThread)
    bot.stop_event = threading.Event()
    bot.is_muted = False
    bot.volume = .5
    chunks = []
    def write(data):
        chunks.append(np.frombuffer(data, dtype='<i2'))
        bot.volume = 0
    process.stdin.write.side_effect = write
    assert bot._start_sound_playback(str(sound)) is process
    assert np.all(chunks[0] == 500)
    assert np.all(chunks[1] == 0)
    process.stdin.close.assert_called_once()


@pytest.mark.parametrize('physical,action', [(6, 13), (7, 14), (8, 15),
    (9, 16), (10, 17), (11, 18), (12, 19)])
def test_supported_feather_keys_reach_existing_actions(physical, action):
    bot = controller()
    assert bot._controller_key(SimpleNamespace(keysym=f'F{physical}', keycode=0)) == f'F{action}'


@pytest.mark.parametrize('busy', [False, True])
def test_double_big_circle_quits_without_listening(busy):
    bot = controller()
    bot.is_busy = busy
    event = SimpleNamespace(keysym='F8', keycode=0)
    bot._controller_press(event)
    bot._controller_release(event)
    bot.master.after_idle.call_args.args[0]()
    bot._controller_press(event)
    bot.exit_fullscreen.assert_called_once()
    assert not bot.manual_wake_event.is_set()
    assert bot._controller_wake_job is None


def test_held_big_circle_does_not_quit():
    bot = controller()
    event = SimpleNamespace(keysym='F8', keycode=0)
    bot._controller_press(event)
    bot._controller_release(event)
    bot._controller_press(event)  # autorepeat, before idle release
    bot.exit_fullscreen.assert_not_called()
    bot.master.after.call_args.args[1]()
    assert bot.manual_wake_event.is_set()


def test_focus_loss_cancels_pending_listen():
    bot = controller()
    bot._controller_press(SimpleNamespace(keysym='F8', keycode=0))
    pending = bot._controller_wake_job
    bot._controller_focus_out(None)
    bot.master.after_cancel.assert_called_with(pending)
    assert bot._controller_wake_job is None
    assert not bot.manual_wake_event.is_set()


def test_volume_overlay_raises_widget_and_restarts_dismissal():
    import tkinter as tk
    bot = bot_with('_show_volume_overlay', '_reset_volume_hide',
                   '_hide_volume_overlay', tk=tk)
    bot.master = Mock()
    # Use an actual Canvas instance without creating its display resource.
    # Canvas.tkraise would invoke 'raise' as an item subcommand, not a window.
    canvas = object.__new__(tk.Canvas)
    canvas.tk = Mock()
    canvas._w = '.volume'
    bot._volume_overlay = canvas
    bot._volume_hide_job = None
    bot._update_volume_visual = Mock()
    bot._show_volume_overlay()
    first_timer = bot._volume_hide_job
    bot._show_volume_overlay()
    canvas.tk.call.assert_any_call('raise', '.volume', None)
    assert not any(call.args and call.args[0] == ('.volume', 'raise')
                   for call in canvas.tk.call.call_args_list)
    bot.master.after_cancel.assert_called_with(first_timer)
    assert bot.master.after.call_args.args[0] == 3000
    bot.master.after.call_args.args[1]()
    canvas.tk.call.assert_called_with('place', 'forget', '.volume')
    assert bot._volume_hide_job is None


@pytest.mark.parametrize('x,y', [(0, 479), (100, 400), (400, 320)])
@pytest.mark.parametrize('state', ['IDLE', 'SPEAKING'])
def test_former_touch_mute_zones_cannot_mute_or_wake(x, y, state):
    states = SimpleNamespace(DISPLAY_IMAGE='DISPLAY_IMAGE', IDLE='IDLE',
                             SCREENSAVER='SCREENSAVER')
    bot = bot_with('handle_click')
    bot.handle_click.__func__.__globals__['BotStates'] = states
    bot.master = Mock()
    bot.master.winfo_width.return_value = 800
    bot.master.winfo_height.return_value = 480
    bot._triple_tap_times = []
    bot.current_state = state
    bot.mute_bmo = Mock()
    bot.manual_wake_event = threading.Event()
    bot.handle_click(SimpleNamespace(x=x, y=y))
    bot.mute_bmo.assert_not_called()
    assert not bot.manual_wake_event.is_set()
