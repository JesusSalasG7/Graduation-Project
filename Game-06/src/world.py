"""
The game state: the currently active word's falling letters, score,
combo, lives, and the running clock (World.elapsed) every letter's
spawn_time/hit_time is measured against. This is the model layer --
gale/pygame only ever see the read-only state exposed here through
src/rendering/typing_renderer.py, exactly like Game-01's src/world.py
keeps Snake's grid logic pygame-free.

Falling is strictly letter-by-letter: a word's letters are NOT all
scheduled up front. Only one letter per word is ever "active" (started
falling) at a time -- the next one starts the instant the current one
resolves (hit or miss), via _activate_next_letter. This is what keeps
exactly one note on screen per word, instead of several overlapping
ones.

Each letter's hit_time is snapped onto the next tick of a real song's
detected beat (see src/audio/beat_detector.py and _pick_next_beat_time),
rather than sitting a fixed effective_travel_time away --
effective_travel_time (difficulty's travel_time, shrunk by
speed_multiplier, energy_at_elapsed, AND _song_section_multiplier
together -- see that property) acts as a floor: the next letter always
lands on the earliest beat at least that far out, no exceptions, so
difficulty/streak/energy/song-progress together control overall pacing
while every letter's actual gap from the one before it stays an exact,
constant number of beats for as long as none of those four keep
changing. Passing an empty beat schedule (the default) falls back to a
plain effective_travel_time cadence, which is what every existing
World(...) call in the test suite does.

A letter's spawn_time -- when it visually starts falling, as opposed to
hit_time, when it's supposed to land -- is deliberately NOT "the instant
the previous one resolves": see _activate_letter for why holding it back
to hit_time - effective_travel_time is what keeps every note's fall at
one constant speed (like a real rhythm game's steady scroll) instead of
crawling for however long the beat search happened to leave until the
next hit_time.

Each letter's *lane* (which of the 4 highway columns it falls down) is
likewise not a flat function of its position in the word -- see
src/entities/lane_manager.py's LaneManager, owned here and consulted
once per letter as it's built in _spawn_word.

time_since_last_beat() exposes the same beat schedule for a purpose that
has nothing to do with scoring: letting the view pulse something (see
TypingRenderer._render_hit_zone) in time with the song's main pulse, so
the sync is something a player can actually *see* on every beat, not
just feel on the handful of beats a letter happens to land on.

energy_at_elapsed() is the same idea one level up: landing letters
exactly on the beat makes the *rhythm* line up, but says nothing about
the song's own builds and drops -- a quiet verse and the loudest chorus
would otherwise drive an identical-looking highway. See
src/audio/beat_detector.py's energy curve and TypingRenderer's ambient
background/lane tint for what actually rides that.
"""
import bisect
from typing import List, Optional, Sequence, Tuple

import settings
from src import records, scoring
from src.entities.falling_letter import FallingLetter
from src.entities.lane_manager import LaneManager
from src.entities.word_stream import WordStream

LetterEvent = Tuple[FallingLetter, str, int]


class ActiveWord:
    def __init__(self, text: str, letters: List[FallingLetter]) -> None:
        self.text = text
        self.letters = letters

    @property
    def complete(self) -> bool:
        return all(letter.resolved for letter in self.letters)

    @property
    def has_miss(self) -> bool:
        return any(letter.judgement == scoring.MISS for letter in self.letters)


class World:
    def __init__(
        self,
        travel_time: float,
        beats: Optional[Sequence[float]] = None,
        song_duration: float = 0.0,
        energy_curve: Optional[Sequence[Tuple[float, float]]] = None,
        preset_words: Optional[Sequence[str]] = None,
        seed: Optional[int] = None,
    ) -> None:
        """
        `beats`/`energy_curve`, if given, are exactly what
        src.audio.beat_detector.BeatDetector.detect() returns (minus the
        duration, which is `song_duration`) -- World never imports that
        module itself, keeping the model layer decoupled from a specific
        analysis library the same way it stays free of pygame (see the
        module docstring).

        `preset_words`, if given, is handed straight to WordStream --
        drained in order before it generates anything of its own (see
        that class). PlayState is the one caller that passes anything
        here, and only with a length-sorted batch from
        src/algorithms/sort_task.py.
        """
        self.travel_time = travel_time
        self._song_duration = song_duration
        # Sorted once up front so _next_beat_after can scan it in order;
        # an empty schedule (the default) makes it fall back to a plain
        # effective_travel_time cadence -- see that method's docstring.
        self._main_beat_times: List[float] = sorted(beats) if beats else []
        # (start, end) stretches, in one-loop [0, song_duration) terms,
        # with no detected beat at all -- see highway_visibility.
        self._pause_windows: List[Tuple[float, float]] = self._compute_pause_windows()
        # Parallel, time-sorted lists (rather than a list of pairs) so
        # energy_at_elapsed can bisect the times directly -- see that
        # method. Already time-sorted coming out of BeatDetector, but
        # sorted again here since this is a public constructor param.
        ordered_energy = sorted(energy_curve) if energy_curve else []
        self._energy_times: List[float] = [t for t, _v in ordered_energy]
        self._energy_values: List[float] = [v for _t, v in ordered_energy]
        self._seed = seed
        self._word_stream = WordStream(seed=seed, preset_words=preset_words)
        self.reset()

    def _compute_pause_windows(self) -> List[Tuple[float, float]]:
        """
        Every stretch strictly longer than settings.SONG_PAUSE_GAP_SECONDS
        with no detected beat in it -- between two consecutive beats,
        before the very first one, or after the very last one (that last
        case doubling as the silence most songs have right where one
        loop's playback wraps into the next, see highway_visibility).
        """
        if len(self._main_beat_times) < 2 or self._song_duration <= 0:
            return []

        windows = [
            (a, b)
            for a, b in zip(self._main_beat_times, self._main_beat_times[1:])
            if b - a > settings.SONG_PAUSE_GAP_SECONDS
        ]

        if self._main_beat_times[0] > settings.SONG_PAUSE_GAP_SECONDS:
            windows.append((0.0, self._main_beat_times[0]))

        if self._song_duration - self._main_beat_times[-1] > settings.SONG_PAUSE_GAP_SECONDS:
            windows.append((self._main_beat_times[-1], self._song_duration))

        return windows

    def reset(self) -> None:
        self.elapsed = 0.0
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.lives = settings.STARTING_LIVES
        self.words_completed = 0
        self.game_over = False
        # Set once elapsed reaches _song_duration without game_over having
        # beaten it there first (see update()) -- "survived the whole
        # song" as a run-ending condition distinct from "ran out of
        # lives". Stays False forever when _song_duration <= 0 (e.g.
        # every existing test), same as every other song-duration-gated
        # behavior in this class.
        self.won = False

        # Climbs as the player's streak grows (see _maybe_increase_speed)
        # and divides travel_time (see effective_travel_time) -- so a
        # longer streak makes every letter both fall faster and arrive
        # sooner after the previous one resolves.
        self.speed_multiplier = settings.SPEED_MULTIPLIER_START

        # Re-seeded fresh every run (same seed as the word stream, for a
        # fully reproducible run under test) -- see _spawn_word.
        self._lane_manager = LaneManager(seed=self._seed)

        # Tallies every resolved letter by judgement, purely to compute
        # accuracy_percent -- see settings.ACCURACY_WEIGHTS.
        self._judgement_counts = {scoring.PERFECT: 0, scoring.GOOD: 0, scoring.OK: 0, scoring.MISS: 0}

        # Reloaded fresh every run so a record saved at the end of the
        # previous one is picked up immediately (see World.display_best_score).
        self.best_score = records.best_score()

        # One-shot events for the instant something happens, so callers
        # (PlayState -- popups/miss SFX) can react exactly once instead of
        # on every frame the resulting state stays around. See
        # consume_letter_event / consume_word_clean_event.
        self._letter_event: Optional[LetterEvent] = None
        self._word_clean_event = False

        # Words generated ahead of the one actually falling, so the HUD's
        # queue panel can show what's coming next -- see _ensure_lookahead
        # and the public `upcoming_words` property.
        self._upcoming_words: List[str] = []
        self._ensure_lookahead()

        self.active_word: Optional[ActiveWord] = None
        # elapsed == 0 here, so this picks the first onset at or past
        # effective_travel_time -- the same floor _activate_next_letter
        # uses for every letter after it.
        self._spawn_word(hit_time=self._pick_next_beat_time())

    @property
    def finished(self) -> bool:
        return self.game_over or self.won

    def time_since_last_beat(self) -> Optional[float]:
        """
        Seconds since the song's most recent main-pulse beat at-or-before
        `elapsed` -- None when no beat schedule was provided (see
        __init__), so callers can tell "no song" apart from "right on
        beat 0". Wraps the same way _next_beat_after does once the song
        has looped past its own duration.
        """
        if not self._main_beat_times or self._song_duration <= 0:
            return None

        loop_time = self.elapsed % self._song_duration
        index = bisect.bisect_right(self._main_beat_times, loop_time) - 1
        last_beat = (
            self._main_beat_times[index] if index >= 0 else self._main_beat_times[-1] - self._song_duration
        )
        return loop_time - last_beat

    def highway_visibility(self) -> float:
        """
        1.0 normally. Inside one of _pause_windows -- a real multi-second
        stretch of the song with no detected beat at all -- this fades to
        0.0 and stays there until effective_travel_time seconds remain
        before the window ends, then eases back up to 1.0 exactly as it
        does: a note can't legitimately be on screen before its own
        spawn_time (see _activate_letter) either, so the highway
        reappearing on that same schedule reads as one consistent rule
        rather than two unrelated ones. 1.0 whenever there's no pause
        schedule at all (no beats provided, e.g. every existing test).
        """
        if not self._pause_windows or self._song_duration <= 0:
            return 1.0

        loop_time = self.elapsed % self._song_duration
        travel = self.effective_travel_time

        for start, end in self._pause_windows:
            if start <= loop_time < end:
                remaining = end - loop_time
                return 1.0 if remaining <= 0 else min(1.0, max(0.0, 1.0 - remaining / travel))

        return 1.0

    def energy_at_elapsed(self) -> float:
        """
        The song's own macro loudness right now, 0.0 (its quietest
        stretches) to 1.0 (its loudest) -- linearly interpolated between
        the downsampled, percentile-normalized samples BeatDetector
        precomputed (see its module docstring). Read by both
        TypingRenderer's ambient highway tint AND effective_travel_time
        below (gameplay speeding up right along with the lights, not just
        looking like it does). 0.0 whenever no energy curve was provided
        (e.g. every existing test), same as "no song at all" reads as
        the quietest possible moment rather than raising.
        """
        if not self._energy_times or self._song_duration <= 0:
            return 0.0

        loop_time = self.elapsed % self._song_duration
        index = bisect.bisect_right(self._energy_times, loop_time)

        if index == 0:
            return self._energy_values[0]
        if index >= len(self._energy_times):
            return self._energy_values[-1]

        t0, t1 = self._energy_times[index - 1], self._energy_times[index]
        v0, v1 = self._energy_values[index - 1], self._energy_values[index]
        frac = (loop_time - t0) / max(t1 - t0, 1e-6)
        return v0 + (v1 - v0) * frac

    @property
    def effective_travel_time(self) -> float:
        """
        The chosen difficulty's travel_time, shortened by three
        independent, stacking multipliers -- what every hit_time
        calculation actually uses, so the fall rate and the pace new
        letters arrive at all speed up together as any of them climbs:
          - speed_multiplier: the player's own streak (see
            _maybe_increase_speed) -- can only climb, resets its climb
            (not the multiplier already earned) on a miss.
          - energy_at_elapsed: the song's loudness right now -- goes up
            AND down with the music's own builds/drops.
          - _song_section_multiplier: how far into the song this run has
            gotten -- a plain, always-forward ramp; see that method.
        """
        energy_multiplier = 1.0 + self.energy_at_elapsed() * (settings.ENERGY_SPEED_MULTIPLIER_MAX - 1.0)
        section_multiplier = self._song_section_multiplier()
        return self.travel_time / (self.speed_multiplier * energy_multiplier * section_multiplier)

    def _song_section_multiplier(self) -> float:
        """
        1.0 at the very start of the song, climbing smoothly and
        CONTINUOUSLY to settings.SONG_SECTION_SPEED_MULTIPLIER_MAX by the
        end -- conceptually still settings.SONG_SECTION_COUNT equal
        sections, each one a bit faster than the last (an earlier version
        rounded elapsed down to a section index and jumped straight to
        that section's value, which is mathematically the same ramp
        sampled at 5 points instead of read continuously -- except that
        version's letters right after a section boundary suddenly fell
        noticeably faster than the ones right before it, since
        effective_travel_time depends on this multiplier too: a real,
        visible speed discontinuity between two consecutive letters, not
        the "progressively" this was supposed to be). Plain linear
        interpolation across the whole song is that same 5-sections-worth
        of total increase with the step sanded off -- every point on it
        still lines up exactly with where each section's target value
        would be, it just no longer snaps there. Dividing by the song's
        own duration (not elapsed real-world seconds) means this always
        finishes exactly at the end of the song and restarts from 1.0 on
        every loop, regardless of which difficulty/travel_time was
        chosen. 1.0 whenever there's no song duration to divide (e.g.
        every existing test).
        """
        if self._song_duration <= 0:
            return 1.0

        loop_time = self.elapsed % self._song_duration
        progress = loop_time / self._song_duration

        return 1.0 + progress * (settings.SONG_SECTION_SPEED_MULTIPLIER_MAX - 1.0)

    @property
    def display_best_score(self) -> int:
        """
        The number the HUD's best-score readout should show. While the
        current run is at or above the saved best, this tracks the live
        score instead of the (now stale) saved value.
        """
        return max(self.best_score, self.score)

    @property
    def accuracy_percent(self) -> float:
        """
        Weighted accuracy across every letter resolved so far (see
        settings.ACCURACY_WEIGHTS) -- 100.0 before anything has been
        resolved yet, rather than dividing by zero.
        """
        total = sum(self._judgement_counts.values())

        if total == 0:
            return 100.0

        weighted = sum(
            count * settings.ACCURACY_WEIGHTS[judgement]
            for judgement, count in self._judgement_counts.items()
        )
        return (weighted / total) * 100

    @property
    def upcoming_words(self) -> List[str]:
        """Read-only preview of the words queued up after the active one."""
        return list(self._upcoming_words)

    def consume_letter_event(self) -> Optional[LetterEvent]:
        """(letter, judgement, points_awarded) for the last resolved letter, or None."""
        event = self._letter_event
        self._letter_event = None
        return event

    def consume_word_clean_event(self) -> bool:
        """Whether a word was just cleared with zero misses, cleared once read."""
        happened = self._word_clean_event
        self._word_clean_event = False
        return happened

    def handle_key(self, char: str) -> Optional[str]:
        """
        Resolves the one currently-active letter (letter-by-letter: at
        most one letter per word is ever pending, see
        is_pending/_activate_next_letter, so there's never a "which one"
        choice to make the way a multi-letter-at-once model would need).

        Every key press that lands while a letter is pending resolves
        it, one way or another -- there is no free no-op a player could
        mash through:
          - the right character, close enough to hit_time: perfecto/
            bien/ok (see scoring.classify_judgement).
          - the right character, but too far from hit_time (pressed
            before the note has actually reached the hit zone): a miss,
            same as any other.
          - the wrong character entirely: also a miss.

        Returns None only when the press doesn't concern gameplay at
        all -- the run is over, or (a brief edge case between one
        letter resolving and the next word's first letter being
        activated) there is no pending letter right now.
        """
        if self.game_over or self.active_word is None:
            return None

        char = char.upper()
        letter = next((l for l in self.active_word.letters if l.is_pending), None)

        if letter is None:
            return None

        if letter.char != char:
            judgement = scoring.MISS
        else:
            distance = abs(self.elapsed - letter.hit_time)
            judgement = scoring.classify_judgement(distance) or scoring.MISS

        self._resolve_letter(letter, judgement)
        return judgement

    def update(self, dt: float, song_time: Optional[float] = None) -> None:
        """
        `song_time`, if given (seconds since the backing song's play()
        call -- see PlayState._current_song_time), replaces dt-accumulation
        as elapsed's source of truth for this frame, keeping every
        letter's hit_time in sync with the audio actually playing rather
        than drifting away from it frame by frame. None (the default,
        and what every existing call in the test suite passes) falls
        back to plain dt accumulation.
        """
        if self.game_over or self.won:
            return

        self.elapsed = song_time if song_time is not None else self.elapsed + dt
        self._expire_missed_letter()

        # A miss that just cost the last life may have flipped game_over
        # inside _expire_missed_letter -- don't let the run's very last
        # word get silently replaced by a new one the player never sees.
        if self.game_over:
            return

        # Checked after _expire_missed_letter (so a miss right at the
        # boundary still counts) but before spawning anything new -- once
        # the song itself has played all the way through, there's no
        # letter left worth falling.
        if self._song_duration > 0 and self.elapsed >= self._song_duration:
            self.won = True
            return

        if self.active_word is not None and self.active_word.complete:
            self._advance_word()

    def _expire_missed_letter(self) -> None:
        if self.active_word is None:
            return

        letter = next((l for l in self.active_word.letters if l.is_pending), None)

        if letter is None:
            return

        # The letter's scored window (settings.OK_WINDOW_SECONDS) has
        # closed with nothing landing in it: it crossed the hit zone and
        # kept going, unpressed.
        if self.elapsed - letter.hit_time > settings.OK_WINDOW_SECONDS:
            self._resolve_letter(letter, scoring.MISS)

    def _advance_word(self) -> None:
        if not self.active_word.has_miss:
            self.score += settings.WORD_CLEAN_BONUS
            self._word_clean_event = True

        self.words_completed += 1
        self._spawn_word(hit_time=self._pick_next_beat_time())

    def _ensure_lookahead(self) -> None:
        while len(self._upcoming_words) < settings.WORD_LOOKAHEAD_COUNT:
            self._upcoming_words.append(self._word_stream.next_word())

    def _spawn_word(self, hit_time: float) -> None:
        self._ensure_lookahead()
        text = self._upcoming_words.pop(0)
        self._ensure_lookahead()

        letters = [
            FallingLetter(
                char=char,
                index_in_word=i,
                word_length=len(text),
                lane=self._lane_manager.next_lane(),
            )
            for i, char in enumerate(text)
        ]
        self.active_word = ActiveWord(text, letters)
        self._activate_letter(letters[0], hit_time)

    def _activate_letter(self, letter: FallingLetter, hit_time: float) -> None:
        """
        Starts `letter` falling -- the one letter-by-letter entry point
        for a letter to become pending (is_pending flips true right now,
        regardless of spawn_time below, same as always: a press that
        lands too early from a player's own reflexes still just scores
        as a miss, exactly like one that lands too late).

        spawn_time is NOT simply "now" -- it's held back to
        hit_time - effective_travel_time, so the note's fall always
        covers the same constant distance-over-time (a steady scroll
        speed, like a real rhythm game) instead of crawling the instant
        the previous letter resolves and covering however much real gap
        happened to separate this hit_time from that moment.
        _pick_next_beat_time's own floor guarantees that gap is always
        >= effective_travel_time when a beat schedule is in play, so
        max() here is a defensive clamp against ever going negative
        (e.g. with no beat schedule at all, where hit_time IS exactly
        elapsed + effective_travel_time already), not a regularly-hit
        branch.
        """
        travel_time = self.effective_travel_time
        letter.spawn_time = max(self.elapsed, hit_time - travel_time)
        letter.hit_time = hit_time
        letter.travel_time = hit_time - letter.spawn_time
        letter.started = True

    def _activate_next_letter(self, resolved_letter: FallingLetter) -> None:
        """
        Starts the next letter in the same word falling, the instant
        the current one resolves -- this is what makes the fall
        letter-by-letter rather than the whole word pre-scheduled at
        once.
        """
        next_index = resolved_letter.index_in_word + 1

        if next_index >= len(self.active_word.letters):
            return

        next_letter = self.active_word.letters[next_index]
        self._activate_letter(next_letter, hit_time=self._pick_next_beat_time())

    def _resolve_letter(self, letter: FallingLetter, judgement: str) -> None:
        letter.resolved = True
        letter.judgement = judgement
        self._judgement_counts[judgement] += 1

        if judgement == scoring.MISS:
            points = 0
            self.combo = 0
            self.lives -= 1

            if self.lives <= 0:
                self.game_over = True
        else:
            points = scoring.score_for_hit(judgement, self.combo)
            self.score += points
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self._maybe_increase_speed()

        self._letter_event = (letter, judgement, points)

        if not self.game_over:
            self._activate_next_letter(letter)

    def _maybe_increase_speed(self) -> None:
        """
        Every settings.SPEED_COMBO_STEP_SIZE CONSECUTIVE non-miss hits
        (self.combo, just incremented by the caller), bumps
        speed_multiplier by settings.SPEED_INCREMENT_PER_COMBO_STEP, up
        to settings.SPEED_MULTIPLIER_MAX. A miss resets self.combo (so
        the streak has to be rebuilt for the next bump) but never this
        multiplier itself -- speed only ever climbs, same as the combo
        score multiplier it mirrors (see scoring.combo_multiplier).
        """
        if self.combo % settings.SPEED_COMBO_STEP_SIZE == 0:
            self.speed_multiplier = min(
                settings.SPEED_MULTIPLIER_MAX,
                self.speed_multiplier * (1 + settings.SPEED_INCREMENT_PER_COMBO_STEP),
            )

    def _pick_next_beat_time(self) -> float:
        """
        The next moment a letter should aim to land on: the earliest
        main-pulse beat at least effective_travel_time away (see
        _next_beat_after) -- always exactly that far away when a beat
        schedule is available (never less), which is what lets
        _activate_letter give every note the same constant fall speed.
        """
        return self._next_beat_after(self.elapsed + self.effective_travel_time)

    def _next_beat_after(self, min_time: float) -> float:
        """
        Smallest scheduled main-pulse beat time >= min_time, looping the
        detected beat pattern indefinitely once the song has played
        through once (so an endless typing game never runs out of beats
        to snap to). Falls back to min_time itself -- i.e. a plain
        effective_travel_time cadence -- when no beat schedule was
        provided at all.
        """
        if not self._main_beat_times or self._song_duration <= 0:
            return min_time

        loop_index = int(min_time // self._song_duration)

        while True:
            offset = loop_index * self._song_duration

            for beat_time in self._main_beat_times:
                candidate = beat_time + offset
                if candidate >= min_time:
                    return candidate

            loop_index += 1
