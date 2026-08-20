"""
Real-time-synthesized audio for TypeBeat: the miss thud is rendered from
a raw numpy waveform and handed to pygame as a pygame.mixer.Sound via
pygame.sndarray.make_sound -- no audio file for it. A correct hit plays
no SFX of its own; the backing song (chosen per run -- see
PlayState._confirm_song_selection / settings.SONGS) is the only thing
audible for those, since every letter's hit_time already lands
squarely on it -- see src/audio/beat_detector.py and World._pick_next_beat_time.

play_miss_sound() is rendered once, up front (see __init__) -- there's
only ever the one clip, so there's no reason to redo the synthesis on
every miss.
"""
import numpy as np
import pygame

SAMPLE_RATE = 44100

# A single low fundamental (deliberately off-scale, no harmonics -- this
# is meant to read as a dull "no", never as a note) with a fast decay: a
# short, heavily damped thud for a wrong key or an expired letter.
_MISS_FREQUENCY_HZ = 95.0
_MISS_DECAY_RATE = 32.0
_MISS_DURATION_SECONDS = 0.14
_MISS_VOLUME = 0.6

# A linear fade-in this short (a few dozen samples) is inaudible as a
# ramp but keeps the waveform starting at 0 instead of jumping straight
# to its peak -- that jump is exactly what reads as a click/pop.
_FADE_IN_SECONDS = 0.002


def _exponential_envelope(t: np.ndarray, decay_rate: float) -> np.ndarray:
    """Smooth exponential decay from full amplitude, click-free at both ends."""
    envelope = np.exp(-decay_rate * t)

    fade_in_samples = min(len(t), int(_FADE_IN_SECONDS * SAMPLE_RATE))
    if fade_in_samples > 0:
        envelope[:fade_in_samples] *= np.linspace(0.0, 1.0, fade_in_samples)

    return envelope


def _render_miss_thud() -> pygame.mixer.Sound:
    n_samples = int(_MISS_DURATION_SECONDS * SAMPLE_RATE)
    t = np.arange(n_samples) / SAMPLE_RATE

    wave = np.sin(2 * np.pi * _MISS_FREQUENCY_HZ * t)
    wave *= _exponential_envelope(t, _MISS_DECAY_RATE)

    peak = np.max(np.abs(wave))
    if peak > 0:
        wave = wave / peak
    wave *= _MISS_VOLUME

    stereo = np.column_stack([wave, wave])
    pcm = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(pcm))


class SoundManager:
    def __init__(self) -> None:
        self._miss_sound = _render_miss_thud()

    def play_miss_sound(self) -> None:
        self._miss_sound.play()
