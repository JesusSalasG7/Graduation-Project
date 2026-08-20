"""
Analyzes a song once at load time via librosa.beat.beat_track -- the
song's actual steady pulse, the beat a listener would tap their foot to,
evenly spaced and locked to the track's tempo -- see BeatDetector.detect.

librosa.onset.onset_detect (every individual percussive transient: hi-hats,
syncopation, melody hits) was tried first and looked wrong in play: it's
denser and NOT phase-locked to the track's actual tempo, so notes landed
on musically arbitrary instants instead of the beat itself. A second
version tried mixing those onsets in as occasional shorter-floor "burst"
exceptions (see World._pick_next_beat_time in earlier history) and that
looked wrong too -- the looser floor won out far more often than an
occasional fast fill was meant to, breaking the one thing that actually
reads as "on the beat": every note falling at the same constant speed.
beat_track's output alone, used for every letter with no exceptions, is
what's left.

World only ever consumes the plain beat timestamps this returns (see
PlayState.enter, the one place a BeatDetector gets built) -- it doesn't
import librosa itself, keeping the model layer decoupled from a specific
analysis library the same way it stays free of pygame (see
src/world.py's own module docstring).

The actual librosa analysis takes several seconds -- fine once, but not
something PlayState.enter() (blocking the whole game, right as the
player presses ENTER to start) should ever have to redo. lru_cache alone
only covers repeat plays within the same process; _cache_path below adds
a JSON file next to the song itself so the very first play after a fresh
process start is instant too, as long as a previous run (or the copy
checked into assets/audio/.beat_cache/) already analyzed this exact
audio_path/delta combination.

beat_track occasionally still proposes a beat that lands in a genuinely
quiet stretch (a fade-in/fade-out tail, a breakdown) -- see
_is_audible, which drops any beat that fails BOTH an RMS-energy check
at that exact instant and a coarser librosa.effects.split pass over the
whole track, before it's ever handed to World. World's own
_pause_windows (built from whatever gaps this leaves between
consecutive beats) is what PlayState fades the highway around and holds
new letters back for -- see World.highway_visibility.

detect() also returns a coarse, downsampled "energy curve": the track's
own RMS loudness over time, smoothed (ENERGY_SMOOTHING_SECONDS) so it
tracks builds/drops/breakdowns rather than flickering with individual
onsets, and percentile-normalized to 0..1 against THIS song's own quiet-
to-loud range. Beat scheduling never touches it -- World.energy_at_elapsed
exists purely so TypingRenderer can tint the highway with the song's own
macro dynamics, the "does this feel like it's actually riding the music"
half of the sync problem that landing every letter exactly on a beat
doesn't cover by itself.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

import librosa
import numpy as np

# librosa's onset-detection default sample rate -- plenty of resolution
# for beat timing, and noticeably cheaper to analyze than the source
# file's native 44.1kHz.
SAMPLE_RATE = 22050

# A beat whose RMS energy right at that instant is quieter than this
# (dB relative to the track's single loudest frame) is treated as
# landing in silence and dropped -- see _is_audible.
SILENCE_THRESHOLD_DB = -35.0
# top_db for librosa.effects.split's coarser silence pass over the whole
# track -- a beat outside every returned non-silent interval is dropped
# even if its own single-frame RMS happened to clear SILENCE_THRESHOLD_DB.
SPLIT_TOP_DB = 30.0

# How much the RMS loudness curve is smoothed (moving average) before
# it's turned into the energy curve -- long enough to wash out individual
# hits/onsets and leave only the song's macro builds/drops/breakdowns.
ENERGY_SMOOTHING_SECONDS = 1.5
# How finely the (already-smoothed, slow-moving) energy curve is sampled
# for the cache/World -- no need for per-frame resolution on something
# that only changes meaningfully over whole seconds.
ENERGY_SAMPLE_STEP_SECONDS = 0.2
# The smoothed curve is percentile- (not min/max-) normalized to 0..1,
# so one freak silent frame or one single loudest-instant peak can't
# compress the whole rest of the song's dynamic range into a sliver.
ENERGY_NORMALIZE_PERCENTILES = (5.0, 95.0)

# Bumped whenever the analysis/cache shape below changes, so a cache
# file written by an older version of this module is never blindly
# trusted.
_CACHE_FORMAT_VERSION = 4


class BeatDetector:
    """
    Thin, per-song wrapper around the module-level cached analysis (see
    _detect_cached) -- construct one per audio path, then call detect()
    whenever PlayState needs the beat schedule. `delta` is accepted for
    cache-key/API stability but no longer changes the analysis itself
    (beat_track has no equivalent threshold) -- keeping it means callers
    that pass settings.BEAT_DETECTION_DELTA don't need to change.
    """

    def __init__(self, audio_path: str, delta: float = 0.2) -> None:
        self._audio_path = audio_path
        self._delta = delta

    def detect(self) -> Tuple[List[float], float, List[Tuple[float, float]]]:
        """(beat_times_seconds, song_duration_seconds, energy_curve)."""
        beat_times, duration, energy_curve = _detect_cached(self._audio_path, self._delta)
        return list(beat_times), duration, list(energy_curve)


@lru_cache(maxsize=None)
def _detect_cached(
    audio_path: str, delta: float
) -> Tuple[Tuple[float, ...], float, Tuple[Tuple[float, float], ...]]:
    """
    Analyzes `audio_path` once and caches the result in memory (lru_cache,
    for repeat plays in this process) and on disk (see _cache_path, for
    the very next process start too) -- beat/energy detection over a
    multi-minute song takes a handful of seconds, too slow for
    PlayState.enter() to block on more than once ever per machine.
    """
    cache_path = _cache_path(audio_path, delta)
    cached = _read_cache(cache_path, audio_path)
    if cached is not None:
        return cached

    result = _analyze(audio_path)
    _write_cache(cache_path, *result)
    return result


def _cache_path(audio_path: str, delta: float) -> Path:
    audio = Path(audio_path)
    # delta folded into the filename purely so an old cache from before
    # _CACHE_FORMAT_VERSION never gets confused for a current one.
    name = f"{audio.stem}_d{delta}_v{_CACHE_FORMAT_VERSION}.json"
    return audio.parent / ".beat_cache" / name


def _read_cache(
    cache_path: Path, audio_path: str
) -> Optional[Tuple[Tuple[float, ...], float, Tuple[Tuple[float, float], ...]]]:
    if not cache_path.exists() or cache_path.stat().st_mtime < Path(audio_path).stat().st_mtime:
        return None  # never analyzed, or the audio file itself changed since

    try:
        payload = json.loads(cache_path.read_text())
        energy_curve = tuple((float(t), float(v)) for t, v in payload["energy_curve"])
        return tuple(payload["beat_times"]), payload["duration"], energy_curve
    except (OSError, json.JSONDecodeError, KeyError):
        return None  # corrupt/partial cache file -- fall through and just re-analyze


def _write_cache(
    cache_path: Path,
    beat_times: Tuple[float, ...],
    duration: float,
    energy_curve: Tuple[Tuple[float, float], ...],
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "duration": duration,
        "beat_times": list(beat_times),
        "energy_curve": [list(point) for point in energy_curve],
    }
    cache_path.write_text(json.dumps(payload))


def _analyze(audio_path: str) -> Tuple[Tuple[float, ...], float, Tuple[Tuple[float, float], ...]]:
    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE)
    duration = librosa.get_duration(y=y, sr=sr)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    _tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    rms = librosa.feature.rms(y=y)[0]
    rms_db = librosa.amplitude_to_db(rms, ref=np.max)
    non_silent_intervals = librosa.effects.split(y, top_db=SPLIT_TOP_DB)

    beat_times = tuple(
        float(t) for t in beat_times if _is_audible(t, sr, rms_db, non_silent_intervals)
    )
    energy_curve = _build_energy_curve(rms_db, sr, duration)

    return beat_times, duration, energy_curve


def _build_energy_curve(
    rms_db: np.ndarray, sr: int, duration: float
) -> Tuple[Tuple[float, float], ...]:
    """
    The song's own loudness over time, smoothed and percentile-normalized
    to 0..1 -- see the module docstring and the ENERGY_* constants above.
    """
    hop_length = 512  # librosa's own default for both rms and onset_strength
    frame_rate = sr / hop_length
    window = max(1, round(ENERGY_SMOOTHING_SECONDS * frame_rate))
    smoothed = np.convolve(rms_db, np.ones(window) / window, mode="same")

    low, high = np.percentile(smoothed, ENERGY_NORMALIZE_PERCENTILES)
    normalized = np.clip((smoothed - low) / max(high - low, 1e-6), 0.0, 1.0)

    frame_times = librosa.frames_to_time(np.arange(len(smoothed)), sr=sr)
    sample_times = np.arange(0.0, max(duration, frame_times[-1]), ENERGY_SAMPLE_STEP_SECONDS)
    sample_values = np.interp(sample_times, frame_times, normalized)

    return tuple((float(t), float(v)) for t, v in zip(sample_times, sample_values))


def _is_audible(t: float, sr: int, rms_db: np.ndarray, non_silent_intervals: np.ndarray) -> bool:
    """
    Both silence checks have to pass, not just one -- the fine-grained
    per-frame RMS reading (SILENCE_THRESHOLD_DB) catches a beat sitting
    right on a quiet transient inside an otherwise "loud" section that
    librosa.effects.split's coarser top_db pass wouldn't isolate on its
    own, while the split intervals catch a beat in a longer quiet
    stretch (fade-in/out, breakdown) whose single frame might not
    happen to dip quite low enough on its own.
    """
    frame = int(np.clip(librosa.time_to_frames(t, sr=sr), 0, len(rms_db) - 1))
    if rms_db[frame] < SILENCE_THRESHOLD_DB:
        return False

    sample = t * sr
    return any(start <= sample <= end for start, end in non_silent_intervals)
