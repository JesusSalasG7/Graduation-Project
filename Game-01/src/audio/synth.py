"""
Minimal procedural audio synthesis: a few additive oscillators, a
frequency-domain low-pass filter, and a helper that renders all of it
into a pygame.mixer.Sound that loops with no audible seam.

Pure numpy + pygame.sndarray -- no files, no game state. Kept separate
from src/audio/ambient.py so "how to synthesize a tone" stays apart
from "how the game's ambience reacts to what's happening on screen".

Seamless looping, without any fades or crossfades inside the clip
itself, relies on one rule: every periodic component (each oscillator,
the tremolo) must complete a whole number of cycles within the loop's
duration. When that holds, sample 0 and the sample one loop-length
later are mathematically identical in phase for every component, so
there is nothing for the ear to catch at the wrap-around point.
cycles_for() below exists to keep callers honest about that rule.
"""
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pygame

SAMPLE_RATE = 44100


@dataclass(frozen=True)
class Partial:
    """One oscillator in an additive-synthesis chord.

    `cycles` -- not a frequency in Hz -- is what actually gets played;
    see the module docstring for why it has to be an integer.
    """

    cycles: int
    amplitude: float
    waveform: str = "sine"  # "sine" or "triangle"


def cycles_for(frequency_hz: float, loop_seconds: float) -> int:
    """
    Rounds a target frequency to the nearest integer cycle count over
    loop_seconds, i.e. the nearest frequency that will actually loop
    seamlessly. The rounding error is a fraction of a Hz -- inaudible
    on a soft pad -- and gets smaller the longer the loop is.
    """
    return max(1, round(frequency_hz * loop_seconds))


def _frequency_of(cycles: int, loop_seconds: float) -> float:
    return cycles / loop_seconds


def _oscillator(t: np.ndarray, loop_seconds: float, partial: Partial) -> np.ndarray:
    phase = 2 * np.pi * _frequency_of(partial.cycles, loop_seconds) * t

    if partial.waveform == "triangle":
        # A sine reshaped through arcsin: a soft, low-harmonic triangle
        # rather than the buzzier naive sawtooth-built version.
        wave = (2 / np.pi) * np.arcsin(np.sin(phase))
    else:
        wave = np.sin(phase)

    return partial.amplitude * wave


def _lowpass_periodic(signal: np.ndarray, cutoff_hz: float, sample_rate: int) -> np.ndarray:
    """
    Low-pass filters exactly one period of a periodic signal by
    shaping its spectrum directly (a smooth 2nd-order roll-off) and
    transforming back, instead of running a stateful time-domain
    filter over it. A stateful filter has no memory of "what came
    before sample 0", so it would reintroduce a seam at the very loop
    boundary this whole module exists to avoid; shaping the spectrum
    of an already-periodic signal can't do that -- the result is still
    exactly periodic over the same length.
    """
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(len(signal), d=1.0 / sample_rate)

    with np.errstate(divide="ignore"):
        gain = 1.0 / np.sqrt(1.0 + (freqs / cutoff_hz) ** 4)
    gain[0] = 1.0  # keep DC/offset untouched; harmless and avoids a 0/0

    return np.fft.irfft(spectrum * gain, n=len(signal))


def render_seamless_loop(
    loop_seconds: float,
    partials: Sequence[Partial],
    tremolo_cycles: int = 0,
    tremolo_depth: float = 0.0,
    lowpass_cutoff_hz: Optional[float] = None,
    master_volume: float = 1.0,
) -> pygame.mixer.Sound:
    """
    Renders `partials` (a small additive-synthesis chord) into a
    pygame.mixer.Sound, optionally amplitude-pulsed by a slow tremolo
    and smoothed by a low-pass filter. The result is normalized to
    `master_volume` and is a mathematically exact loop -- pygame can
    play it with loops=-1 and there is no seam to hear.
    """
    sample_count = int(loop_seconds * SAMPLE_RATE)
    t = np.arange(sample_count) / SAMPLE_RATE

    mix = np.zeros(sample_count, dtype=np.float64)
    for partial in partials:
        mix += _oscillator(t, loop_seconds, partial)

    if tremolo_cycles > 0 and tremolo_depth > 0:
        pulse = np.sin(2 * np.pi * _frequency_of(tremolo_cycles, loop_seconds) * t)
        envelope = 1.0 - tremolo_depth * (0.5 - 0.5 * pulse)
        mix *= envelope

    if lowpass_cutoff_hz is not None:
        mix = _lowpass_periodic(mix, lowpass_cutoff_hz, SAMPLE_RATE)

    peak = np.max(np.abs(mix))
    if peak > 0:
        mix = mix / peak

    mix *= master_volume

    stereo = np.column_stack([mix, mix])
    pcm = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(pcm))
