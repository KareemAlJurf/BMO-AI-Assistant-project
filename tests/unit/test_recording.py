import numpy as np
import pytest

from core.recording import SilenceDetector


def audio(count, amplitude):
    return np.resize(np.array([-amplitude, amplitude], dtype=np.int16), count)


@pytest.mark.parametrize("rate,block", [(16000,320), (48000,960), (48000,2400)])
def test_stops_after_quiet_independent_of_callback_size(rate, block):
    detector = SilenceDetector(rate)
    assert not detector.update(audio(block, 1000))
    elapsed = 0
    while elapsed < round(rate * 0.8):
        done = detector.update(audio(block, 110))
        elapsed += block
        assert done == (elapsed >= round(rate * 0.8))


def test_short_pause_does_not_end_sentence():
    detector = SilenceDetector(16000)
    assert not detector.update(audio(3200, 1000))
    assert not detector.update(audio(8000, 100))
    assert not detector.update(audio(3200, 1000))
    assert not detector.update(audio(8000, 100))
    assert detector.update(audio(4800, 100))


def test_initial_quiet_times_out_after_five_seconds():
    detector = SilenceDetector(16000)
    for _ in range(4):
        assert not detector.update(audio(16000, 100) + 700)
    assert detector.update(audio(16000, 100) + 700)
    assert not detector.has_spoken
