"""Sample-based end-of-speech detection for microphone recordings."""
import numpy as np


class SilenceDetector:
    def __init__(self, sample_rate, threshold=300, silence_seconds=0.8,
                 initial_wait_seconds=5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.silence_seconds = silence_seconds
        self.initial_wait_seconds = initial_wait_seconds
        self.has_spoken = False
        self.silent_samples = 0

    def update(self, audio):
        samples = np.asarray(audio, dtype=np.float32)
        if not samples.size:
            return False
        # Remove DC offset and use RMS so the threshold does not depend on
        # the number of samples delivered by the microphone callback.
        samples = samples - samples.mean()
        rms = float(np.sqrt(np.mean(samples * samples)))
        if rms >= self.threshold:
            self.has_spoken = True
            self.silent_samples = 0
        else:
            self.silent_samples += len(samples)
        limit = self.silence_seconds if self.has_spoken else self.initial_wait_seconds
        return self.silent_samples >= round(self.sample_rate * limit)
