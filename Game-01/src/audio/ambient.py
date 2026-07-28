"""
Adaptive ambient bed for the Snake game: a soft synth-pad drone that
reacts to how tense the game is getting.

Two independent axes drive it, matching two different ways the game
can get tense:

  - `tension` (0 .. AMBIENT_TENSION_LEVELS - 1): rises as the snake
    grows (and would also rise if the game ever added a speed ramp --
    see sync_with_world). Moves the drone's tempo (a slow tremolo
    pulse) and pitch up, tier by tier.
  - `space_critical` (bool): true once the free cells on the board get
    scarce. Independently darkens (extra low-pass) and ducks the
    ambience -- a packed 10x10 board is tenser than the same snake
    length would be on a huge one, which `tension` alone can't tell.

Every one of the 2 x AMBIENT_TENSION_LEVELS variants is a perfect loop
rendered once at start-up (see src/audio/synth.py); switching between
them crossfades over AMBIENT_CROSSFADE_SECONDS across two ping-ponged
pygame.mixer.Channel objects, so there is never a pop or a gap.

World stays pygame-free throughout: sync_with_world() only reads plain
public attributes (grid size, snake length, move_interval) and is the
one place that turns "grid state" into "how tense the music feels".
"""
from typing import Dict, Tuple

import pygame

import settings
from src.audio import synth


def _chord_partials(tension_level: int) -> list:
    semitones_up = tension_level * settings.AMBIENT_TENSION_SEMITONE_STEP
    partials = []

    for interval, amplitude, waveform in zip(
        settings.AMBIENT_CHORD_INTERVALS_SEMITONES,
        settings.AMBIENT_CHORD_AMPLITUDES,
        settings.AMBIENT_CHORD_WAVEFORMS,
    ):
        target_hz = settings.AMBIENT_ROOT_HZ * 2 ** ((interval + semitones_up) / 12)
        cycles = synth.cycles_for(target_hz, settings.AMBIENT_LOOP_SECONDS)
        partials.append(synth.Partial(cycles=cycles, amplitude=amplitude, waveform=waveform))

    return partials


def _build_variants() -> Dict[Tuple[int, bool], pygame.mixer.Sound]:
    """Pre-renders every (tension, space_critical) combination once."""
    variants: Dict[Tuple[int, bool], pygame.mixer.Sound] = {}

    for tension in range(settings.AMBIENT_TENSION_LEVELS):
        partials = _chord_partials(tension)
        tremolo_cycles = tension + 1  # busier pulse = higher tension

        for critical in (False, True):
            cutoff = (
                settings.AMBIENT_LOWPASS_CRITICAL_HZ
                if critical
                else settings.AMBIENT_LOWPASS_HZ
            )
            volume = settings.AMBIENT_CRITICAL_VOLUME_SCALE if critical else 1.0

            variants[(tension, critical)] = synth.render_seamless_loop(
                loop_seconds=settings.AMBIENT_LOOP_SECONDS,
                partials=partials,
                tremolo_cycles=tremolo_cycles,
                tremolo_depth=settings.AMBIENT_TREMOLO_DEPTH,
                lowpass_cutoff_hz=cutoff,
                master_volume=volume,
            )

    return variants


class AmbientController:
    def __init__(self) -> None:
        self._variants = _build_variants()
        self._channel_a = pygame.mixer.Channel(settings.AMBIENT_CHANNEL_A)
        self._channel_b = pygame.mixer.Channel(settings.AMBIENT_CHANNEL_B)
        self._active_channel = self._channel_a
        self._standby_channel = self._channel_b

        self._tension = 0
        self._space_critical = False
        self._current_key: Tuple[int, bool] = (0, False)

        self._crossfade_total = 0.0
        self._crossfade_remaining = 0.0

        self._duck_remaining = 0.0

    def start(self) -> None:
        """Starts the drone at its calmest variant, looping forever."""
        self._active_channel.set_volume(settings.AMBIENT_BASE_VOLUME)
        self._active_channel.play(self._variants[self._current_key], loops=-1)

    def stop(self) -> None:
        self._active_channel.stop()
        self._standby_channel.stop()

    def duck(self, duration: float = None) -> None:
        """
        Briefly dips the ambience so a one-shot accent (eating, a
        crash) reads clearly on top instead of stacking with it.
        """
        self._duck_remaining = settings.AMBIENT_DUCK_SECONDS if duration is None else duration

    def set_tension(self, tension: int) -> None:
        tension = max(0, min(settings.AMBIENT_TENSION_LEVELS - 1, tension))

        if tension != self._tension:
            self._tension = tension
            self._begin_crossfade()

    def set_space_critical(self, critical: bool) -> None:
        if critical != self._space_critical:
            self._space_critical = critical
            self._begin_crossfade()

    def sync_with_world(self, world) -> None:
        """
        Derives tension and space pressure from the World's public
        state and applies them. Safe to call every frame -- it's a
        no-op unless something actually crossed a threshold.
        """
        length = len(world.snake.segments)

        # Tension: purely "how much snake is there to steer", capped at
        # AMBIENT_GROWTH_TENSION_REFERENCE regardless of board size.
        growth_ratio = min(1.0, length / settings.AMBIENT_GROWTH_TENSION_REFERENCE)
        # Always 1.0 today (move_interval is constant), but this keeps
        # tension correctly reactive if a speed ramp is ever added.
        speed_factor = settings.MOVE_INTERVAL / world.move_interval

        tension_score = min(1.0, growth_ratio * speed_factor)
        self.set_tension(int(tension_score * settings.AMBIENT_TENSION_LEVELS))

        # Space pressure: how full the actual board is -- independent
        # of the fixed-length tension curve above.
        total_cells = world.grid_cols * world.grid_rows
        free_ratio = 1.0 - (length / total_cells)
        self.set_space_critical(free_ratio < settings.AMBIENT_SPACE_CRITICAL_RATIO)

    def update(self, dt: float) -> None:
        if self._duck_remaining > 0:
            self._duck_remaining = max(0.0, self._duck_remaining - dt)

        duck_factor = (
            settings.AMBIENT_DUCK_VOLUME_SCALE if self._duck_remaining > 0 else 1.0
        )

        if self._crossfade_remaining > 0:
            self._crossfade_remaining = max(0.0, self._crossfade_remaining - dt)
            progress = 1.0 - (self._crossfade_remaining / self._crossfade_total)

            # active is the outgoing (old) variant: fades BASE -> 0.
            # standby is the incoming (new) one, already playing at 0
            # volume since _begin_crossfade started it: fades 0 -> BASE.
            self._active_channel.set_volume(
                settings.AMBIENT_BASE_VOLUME * (1.0 - progress) * duck_factor
            )
            self._standby_channel.set_volume(
                settings.AMBIENT_BASE_VOLUME * progress * duck_factor
            )

            if self._crossfade_remaining == 0:
                self._active_channel.stop()
                self._active_channel, self._standby_channel = (
                    self._standby_channel,
                    self._active_channel,
                )
        else:
            self._active_channel.set_volume(settings.AMBIENT_BASE_VOLUME * duck_factor)

    def _begin_crossfade(self) -> None:
        new_key = (self._tension, self._space_critical)

        if new_key == self._current_key:
            return

        self._current_key = new_key
        self._standby_channel.play(self._variants[new_key], loops=-1)
        self._standby_channel.set_volume(0.0)
        self._crossfade_total = settings.AMBIENT_CROSSFADE_SECONDS
        self._crossfade_remaining = settings.AMBIENT_CROSSFADE_SECONDS
