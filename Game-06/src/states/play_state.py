"""
The state that runs the actual game: wires player key presses to the
World (the model), drives the Note objects that visually fall down the
highway, and delegates drawing to the TypingRenderer (the view) -- the
same split Game-01's PlayState keeps for Snake, with the "move the
snake" input swapped for "resolve a falling letter" and the crash sound
swapped for a procedurally synthesized miss thud (see
src/audio/sound_manager.py) -- a hit plays no SFX of its own, since
World times every letter's hit_time to land right on the backing song
(see self._song_path, chosen per run -- settings.SONGS), which is what
should be audible there. Also where that song is actually played and
kept in sync with World's clock -- see _start_song / _current_song_time.

Before any of that, in order: the participant first picks which song
this run's beats come from (see _showing_song_select /
_confirm_song_selection -- settings.SONGS is discovered from
assets/audio/*.mp3, so how many choices show up there is deliberately
not fixed), then dismisses the controls screen, then types their name
(see _entering_record_name/enter()'s "world is None" branch), then
_begin_sort_task, an unrelated sorting exercise (see
src/algorithms/sort_task.py) that only ever shows its own loading
screen if that module's sort_task is actually implemented. That name is
what every run's score (and, only when sort_task turned out to be
implemented, the sort exercise's elapsed time) gets saved under once
the run ends, regardless of whether it beat the previous best -- see
_handle_game_over/_save_record and src/records.py's module docstring.
"""
import pathlib
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from src.rendering.pixel_text import render_text

import settings
from src import records, scoring
from src.algorithms.sort_task import generate_words, run_sort_task, sort_words_by_length
from src.algorithms.word_deduplication import deduplicate_words
from src.algorithms.word_length_variety import group_in_ascending_blocks
from src.audio.beat_detector import BeatDetector
from src.audio.sound_manager import SoundManager
from src.rendering.note import Note
from src.rendering.typing_renderer import TypingRenderer, lane_color, lane_x, letter_lane
from src.world import World

_MAX_RECORD_NAME_LENGTH = 12

# Shown when the typed name already has an entry on the leaderboard --
# navigated/confirmed the same way as _GAME_OVER_OPTIONS. "rename" is
# listed second and is the default selection (see enter()) so mashing
# ENTER never silently overwrites a previous run by accident.
_OVERWRITE_OPTIONS = ("overwrite", "rename")
_OVERWRITE_LABELS = ("Sobrescribir", "Cambiar nombre")

# Shown as the two selectable "buttons" once a run ends -- navigated
# with move_up/move_down and confirmed with "restart" (ENTER), same
# input vocabulary CoverState uses to dismiss its own screen.
_GAME_OVER_OPTIONS = ("restart", "cover")

# Shown as the three selectable "buttons" once a run is WON (the song
# played all the way through without running out of lives) -- same
# navigation vocabulary as _GAME_OVER_OPTIONS, just one more choice.
_WIN_OPTIONS = ("same_track", "change_track", "cover")

_INSTRUCTIONS = (
    "Las palabras pueden aparecer en espanol o en ingles.",
    "Escribe cada letra justo cuando cruce la linea de impacto.",
    "Entre mas preciso, mejor puntaje y mas rapido sube la velocidad.",
    f"{settings.STARTING_LIVES} fallos y se acaba la partida. Presiona ENTER para jugar.",
)


class PlayState(BaseState):
    def enter(
        self, *args: Tuple[Any], difficulty: str = settings.DEFAULT_DIFFICULTY, **kwargs: Dict[str, Any]
    ) -> None:
        self._travel_time = settings.DIFFICULTIES[difficulty]["travel_time"]

        # Shown first, before even the controls screen -- "A que ritmo
        # quieres ir": which of settings.SONGS this run's beats come
        # from. Everything below that depends on the chosen song (the
        # BeatDetector analysis, self._song_path) only gets filled in
        # once _confirm_song_selection runs, not here.
        self._showing_song_select = True
        self._song_select_index = settings.DEFAULT_SONG_INDEX
        self._song_path: Optional[pathlib.Path] = None
        self._beats: Optional[List[float]] = None
        self._song_duration: Optional[float] = None
        self._energy_curve = None

        # Set the instant the song select menu is confirmed, cleared once
        # _confirm_song_selection actually runs -- see _handle_song_select_input
        # for why the heavy librosa analysis is deferred a frame instead of
        # running straight from on_input.
        self._analyzing_song = False
        self._analysis_screen_shown = False
        # Set by the win screen's "cambiar pista" option -- tells
        # _confirm_song_selection to skip straight back into a run
        # instead of showing the controls screen again (see that method
        # and _handle_victory_input).
        self._song_reselect = False

        # World itself isn't built until _start_run, which needs to wait
        # for _begin_sort_task to know whether there's a preset word
        # order to seed it with.
        self.world: Optional[World] = None
        self.renderer: Optional[TypingRenderer] = None

        # Rendering-only "falling note" wrappers, keyed by id(letter) --
        # see src/rendering/note.py for why this is safe to drive with a
        # plain accumulated update(dt) without drifting out of sync with
        # World's own hit_time-based timing.
        self._notes: Dict[int, Note] = {}

        # Renders every lane/miss tone once per run (not per hit) -- see
        # src/audio/sound_manager.py.
        self._sound_manager = SoundManager()

        # Set True the instant the controls screen is dismissed (see
        # on_input) so the participant types their name BEFORE a run
        # starts, not after -- self.world is still None at that point,
        # which render()/update() use to tell "typing the name up front"
        # apart from this same flag's other use: getting reused once a run
        # ends, if that name turns out to collide with an existing saved
        # entry (see _attempt_save_record's "rename" branch) and the
        # participant has to type a different one.
        # Entirely PlayState-side UI flow, not part of World's model.
        self._entering_record_name = False
        self._record_name = ""

        # Set instead of committing the record the instant a finished
        # run's name turns out to already have a saved entry, so the
        # player can choose to overwrite that entry or pick another name.
        self._confirming_overwrite = False
        self._overwrite_selected = 1
        self._pending_record_name = ""

        self._game_over_selected = 0
        # Latches true the instant World.game_over flips on (see
        # _consume_letter_event / _handle_game_over) so that one-time
        # reaction -- stopping the song, maybe saving the record -- fires
        # exactly once per run, not on every subsequent letter event
        # while the game-over screen sits there.
        self._game_over_handled = False

        self._win_selected = 0
        # Same one-shot-latch idea as _game_over_handled, but for
        # World.won (see update() / _handle_victory).
        self._win_handled = False

        # Shown once per run, right after the song's chosen (see
        # _confirm_song_selection), before the first letter starts
        # falling, dismissed with "restart" (ENTER) -- same as
        # everywhere else.
        self._showing_controls = False

        # Set by _start_song -- None here just means "song hasn't
        # started yet" (see _current_song_time).
        self._song_start_perf: Optional[float] = None

        # Shown between "dismiss the controls" and the song actually
        # starting, only when src/algorithms/sort_task.py's sort_task is
        # actually implemented (see _begin_sort_task) -- an unimplemented
        # one (raises, or is just `pass`) skips straight past this,
        # exactly like a run before this screen existed at all.
        self._sorting_screen_active = False
        self._sort_result: Optional[List[int]] = None
        self._sort_elapsed_seconds = 0.0
        self._sort_screen_timer = 0.0
        # The length-sorted words themselves, stashed here between
        # _begin_sort_task computing them and the loading screen's timer
        # actually finishing (see update()) -- that's when _start_run
        # consumes and clears this.
        self._pending_preset_words: Optional[List[str]] = None

        # Every preset word handed out so far THIS SESSION (across every
        # restart, not just within one _begin_sort_task batch) --
        # deduplicate_words only ever sees one batch at a time, so
        # without this a restart's fresh batch could easily reintroduce
        # a word an earlier attempt already used. Cleared only by a new
        # enter() (leaving PlayState entirely), same scope as everything
        # else reset here.
        self._used_preset_words: Set[str] = set()

    def exit(self) -> None:
        # Only reachable via the "cover" game-over button today -- without
        # this the song would keep playing under the cover/title screen.
        pygame.mixer.music.stop()

    def _confirm_song_selection(self) -> None:
        """
        Called from update() once the "A que ritmo quieres ir" menu has been
        confirmed and the loading screen has had a frame to actually appear
        on screen (see _handle_song_select_input / update()'s
        self._analyzing_song handling) -- locks in
        settings.SONGS[self._song_select_index] as this run's song and runs
        the one-time beat analysis on it (cached on disk after the
        first-ever run, a few seconds otherwise -- see
        src/audio/beat_detector.py). World snaps every letter's hit_time
        onto one of these beats, so the fall is timed to the song's actual
        pulse instead of a fixed cadence.
        """
        self._song_path = settings.SONGS[self._song_select_index]

        detector = BeatDetector(str(self._song_path), delta=settings.BEAT_DETECTION_DELTA)
        self._beats, self._song_duration, self._energy_curve = detector.detect()

        if self._song_reselect:
            # "cambiar pista" from the win screen -- the participant's
            # name and the controls screen are both already behind them,
            # so drop straight back into a run on the newly picked song,
            # same as a game-over "restart" does for the same song.
            self._song_reselect = False
            self._notes.clear()
            self._begin_sort_task()
        else:
            self._showing_controls = True

    def _start_song(self) -> None:
        """
        (Re)starts the song from position 0 -- called both the instant
        gameplay actually begins and on every restart, since World's own
        elapsed clock (what every letter's hit_time is measured against)
        also starts over from 0 at exactly those same two moments; the
        song and that clock have to stay aligned for hit_time to mean
        anything relative to what's audible (see _current_song_time).

        self._song_start_perf is stamped right after play() -- that's
        the one moment "song time zero" actually means anything.
        """
        pygame.mixer.music.load(str(self._song_path))
        pygame.mixer.music.set_volume(settings.SONG_VOLUME)
        # Plays once (not loops=-1) -- World.won now fires the instant
        # elapsed reaches the song's own duration (see World.update), so
        # looping the audio underneath that would leave it playing on
        # into the victory screen.
        pygame.mixer.music.play()
        self._song_start_perf = time.perf_counter()

    def _current_song_time(self) -> Optional[float]:
        """
        Seconds since _start_song's play() call, measured with
        time.perf_counter() -- a monotonic, high-resolution clock read
        entirely on the Python side, rather than polling
        pygame.mixer.music.get_pos() every frame. get_pos() was tried
        first and is accurate on this machine/backend, but it's a known
        source of rhythm-game desync in general: its update granularity
        is tied to the audio backend's buffer size (not necessarily
        smooth frame-to-frame), it returns -1 on some backends/codecs
        entirely, and nothing about it guarantees it keeps counting up
        cleanly forever the way World._next_beat_after's own looping math
        (beat_time + loop_index * song_duration) needs once the song
        wraps past its own duration -- perf_counter() - start does, by
        construction, with no backend-specific behavior to depend on.
        None only while the song genuinely hasn't started yet (see
        enter()), in which case World falls back to dt-accumulation for
        that one frame.
        """
        if self._song_start_perf is None:
            return None
        return time.perf_counter() - self._song_start_perf

    def _begin_sort_task(self) -> None:
        """
        Called the instant a run is about to start (dismissing the
        controls screen, or restarting after game over) -- generates
        settings.SORT_TASK_WORD_COUNT real words, deduplicates them (see
        src/algorithms/word_deduplication.py -- Faker's limited provider
        pools mean the same word routinely comes back dozens of times in
        one batch), and hands what's left to sort_task via run_sort_task
        (see src/algorithms/sort_task.py for why that never lets an
        unimplemented sort_task crash this). Only once that's confirmed
        to actually be implemented does it sort those SAME words by
        length too (sort_words_by_length), so the words a run falls in
        are visibly in the order the loading screen is about to claim,
        not just a number sitting apart from what's on screen. That
        sorted batch then goes through group_in_ascending_blocks -- an
        unrelated presentation filter (see
        src/algorithms/word_length_variety.py) that turns "every word of
        the shortest length, then every word of the next, ..." into
        settings.WORD_LENGTH_BLOCK_SIZE words of one length before moving
        up to the next -- still strictly ascending lap by lap, just paced
        instead of one long same-length block per length.

        A real sorted result shows the loading screen (see update()),
        which is what actually calls _start_run once its timer runs out.
        None (not implemented) calls _start_run right away with no
        preset, exactly as every run behaved before this existed.
        """
        words = deduplicate_words(generate_words(settings.SORT_TASK_WORD_COUNT))
        # Also drop anything an earlier attempt THIS SESSION already used
        # -- deduplicate_words above only sees this one batch, so without
        # this a restart's independently-generated batch could easily
        # repeat a word from before the game over (see _used_preset_words).
        words = [word for word in words if word not in self._used_preset_words]
        self._used_preset_words.update(words)

        lengths = [len(word) for word in words]
        sorted_lengths, elapsed = run_sort_task(lengths)

        if sorted_lengths is None:
            self._start_run(preset_words=None)
            self._start_song()
            return

        sorted_words = sort_words_by_length(words)
        self._pending_preset_words = group_in_ascending_blocks(sorted_words, settings.WORD_LENGTH_BLOCK_SIZE)
        self._sort_result = sorted_lengths
        self._sort_elapsed_seconds = elapsed
        self._sort_screen_timer = 0.0
        self._sorting_screen_active = True

    def _start_run(self, preset_words: Optional[List[str]]) -> None:
        self.world = World(
            self._travel_time,
            beats=self._beats,
            song_duration=self._song_duration,
            energy_curve=self._energy_curve,
            preset_words=preset_words,
        )
        self.renderer = TypingRenderer(self.world)

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not input_data.pressed:
            return

        if self._analyzing_song:
            # Swallow every input while the (blocking) beat analysis runs --
            # otherwise a held ENTER's autorepeat piles up in the event
            # queue during the freeze and all fires at once the instant it
            # unblocks, cascading straight through the controls/name
            # screens instead of stopping on each one.
            return

        if self._showing_song_select:
            self._handle_song_select_input(input_id)
            return

        if self._showing_controls:
            if input_id == "restart":
                self._showing_controls = False
                self._entering_record_name = True
            return

        if self._entering_record_name:
            self._handle_record_name_input(input_id, input_data)
            return

        if self._sorting_screen_active:
            return  # update() advances on its own once SORT_LOADING_DISPLAY_SECONDS passes

        if self._confirming_overwrite:
            self._handle_overwrite_confirm_input(input_id)
            return

        if self.world.finished:
            if self.world.won:
                self._handle_victory_input(input_id)
            else:
                self._handle_game_over_input(input_id)
            return

        if input_id == "text_char" and input_data.unicode.isalpha():
            self.world.handle_key(input_data.unicode)
            self._consume_letter_event()

    def _handle_song_select_input(self, input_id: str) -> None:
        # Wraps both ways, not clamps -- settings.SONGS is however many
        # .mp3 files happen to be under assets/audio (see
        # settings._discover_songs), not a fixed count, so this can't
        # assume there are only ever two choices the way
        # _handle_game_over_input's "1 - selected" toggle does.
        if input_id == "move_up":
            self._song_select_index = (self._song_select_index - 1) % len(settings.SONGS)
        elif input_id == "move_down":
            self._song_select_index = (self._song_select_index + 1) % len(settings.SONGS)
        elif input_id == "restart":
            # Don't call _confirm_song_selection() straight from here -- it
            # runs a several-seconds-long librosa analysis the first time a
            # given song is picked, and calling it inline would block this
            # very on_input dispatch before a single frame of feedback ever
            # gets drawn, making the game look frozen/stuck. Flipping this
            # flag instead lets update()/render() show a loading screen for
            # (at least) one frame first -- see update().
            self._showing_song_select = False
            self._analyzing_song = True
            self._analysis_screen_shown = False

    def _handle_game_over_input(self, input_id: str) -> None:
        if input_id in ("move_up", "move_down"):
            self._game_over_selected = 1 - self._game_over_selected
        elif input_id == "restart":
            if _GAME_OVER_OPTIONS[self._game_over_selected] == "restart":
                # A fresh World (see _begin_sort_task/_start_run), not
                # world.reset() -- restarting is "a run is about to
                # start" too, and deserves its own freshly-sorted preset
                # word batch the same way the very first run does.
                self._notes.clear()
                self._game_over_selected = 0
                self._game_over_handled = False
                self._begin_sort_task()
            else:
                self.state_machine.change("cover")

    def _handle_victory_input(self, input_id: str) -> None:
        if input_id in ("move_up", "move_down"):
            step = -1 if input_id == "move_up" else 1
            self._win_selected = (self._win_selected + step) % len(_WIN_OPTIONS)
        elif input_id == "restart":
            choice = _WIN_OPTIONS[self._win_selected]

            if choice == "same_track":
                # Same song already cached on self (self._song_path/
                # _beats/_song_duration/_energy_curve) -- a fresh World
                # and a fresh sorted preset batch, exactly like a
                # game-over restart.
                self._notes.clear()
                self._win_selected = 0
                self._win_handled = False
                self._begin_sort_task()
            elif choice == "change_track":
                self._notes.clear()
                self._win_selected = 0
                self._win_handled = False
                self.world = None
                self.renderer = None
                self._showing_song_select = True
                self._song_reselect = True
            else:
                self.state_machine.change("cover")

    def _handle_record_name_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "text_backspace":
            self._record_name = self._record_name[:-1]
        elif input_id == "text_char" and len(self._record_name) < _MAX_RECORD_NAME_LENGTH:
            # Names are shown/stored upper-case regardless of the shift
            # state the player actually typed with.
            self._record_name += input_data.unicode.upper()
        elif input_id == "restart":
            self._record_name = self._record_name.strip() or "JUGADOR"
            self._entering_record_name = False

            # self.world is only ever None here the FIRST time this
            # prompt is submitted -- right after the controls screen,
            # before a run exists. Reaching this prompt any other time
            # (self.world set and finished) means _attempt_save_record
            # sent the player back here to pick a different name after a
            # collision (see _handle_overwrite_confirm_input's "rename"
            # branch), so it's that save attempt that has to run again,
            # not a fresh run.
            if self.world is None:
                self._begin_sort_task()
            else:
                self._attempt_save_record()

    def _attempt_save_record(self) -> None:
        """
        Called once a run ends (see _handle_game_over -- every run now,
        regardless of score) -- the name is already known by then (typed
        right after the controls screen, see _handle_record_name_input),
        so this either saves straight away or, if that name already has
        an entry, defers to _confirming_overwrite the same choice
        _handle_record_name_input used to ask about immediately.
        """
        name = self._record_name

        if records.name_exists(name):
            self._pending_record_name = name
            self._overwrite_selected = 1
            self._confirming_overwrite = True
        else:
            self._save_record(name, overwrite=False)

    def _save_record(self, name: str, overwrite: bool) -> None:
        # None (not len(...)) whenever sort_task wasn't implemented for
        # this run -- self._sort_elapsed_seconds never leaves its enter()
        # default of 0.0 in that case (see _begin_sort_task), and 0.0
        # would misleadingly read as "sorted instantly" rather than
        # "didn't run".
        sort_time = self._sort_elapsed_seconds if self._sort_result is not None else None

        if overwrite:
            records.overwrite(name, self.world.score, sort_time)
        else:
            records.add(name, self.world.score, sort_time)

    def _handle_overwrite_confirm_input(self, input_id: str) -> None:
        if input_id in ("move_up", "move_down"):
            self._overwrite_selected = 1 - self._overwrite_selected
        elif input_id == "restart":
            if _OVERWRITE_OPTIONS[self._overwrite_selected] == "overwrite":
                self._save_record(self._pending_record_name, overwrite=True)
            else:
                # "rename": back to the name prompt with a clean slate
                # so the player doesn't just resubmit the same duplicate.
                self._record_name = ""
                self._entering_record_name = True

            self._confirming_overwrite = False

    def update(self, dt: float) -> None:
        if self._analyzing_song:
            if not self._analysis_screen_shown:
                # First tick after the flag flipped -- render() hasn't drawn
                # the loading screen yet this frame (update() always runs
                # before render() within a frame, see gale's Game.exec), so
                # wait one more tick before actually blocking on the
                # analysis. That way the loading screen is already on
                # screen (from the previous frame's flip) once the freeze
                # hits, instead of the song-select screen looking stuck.
                self._analysis_screen_shown = True
                return
            self._confirm_song_selection()
            self._analyzing_song = False
            return

        if self._showing_song_select or self._showing_controls:
            return

        # Only true the first time this prompt is up -- self.world
        # doesn't exist yet (see _start_run), so there's nothing below
        # to update. A collision-driven rename after a finished run (see
        # _handle_overwrite_confirm_input) also sets _entering_record_name,
        # but world is set by then, so that leg falls through and still
        # updates the (finished, so effectively idle) world as before.
        if self._entering_record_name and self.world is None:
            return

        if self._sorting_screen_active:
            self._sort_screen_timer += dt
            if self._sort_screen_timer >= settings.SORT_LOADING_DISPLAY_SECONDS:
                self._sorting_screen_active = False
                self._start_run(preset_words=self._pending_preset_words)
                self._pending_preset_words = None
                self._start_song()
            return

        self.world.update(dt, song_time=self._current_song_time())
        self._consume_letter_event()
        self._sync_notes()

        self.world.consume_word_clean_event()  # bonus already landed in World.score

        # Unlike game_over (only ever flipped from inside a letter event,
        # see _consume_letter_event), World.won flips here -- purely from
        # elapsed crossing song_duration, with no letter involved at all.
        if self.world.won and not self._win_handled:
            self._handle_victory()

    def _sync_notes(self) -> None:
        """
        Keeps self._notes in sync with the model: spawns a Note once a
        pending letter has both no Note yet AND has reached its own
        spawn_time (see World._activate_letter -- that's held back from
        "immediately" so every note's fall covers the same constant
        distance-over-time, the steady scroll a real rhythm game has,
        rather than starting the instant the previous letter resolves
        and crawling however long the gap to this one's hit_time happens
        to be), resyncs every note's y straight from World.elapsed (see
        Note.sync -- why that, and not a per-frame dt of its own, is what
        keeps a note's fall from drifting out of step with the audio it's
        supposed to land on), and drops whichever ones have finished
        their post-resolve flash (or, as a safety net, gone unresolved
        long past their hit_time). Deliberately keyed on the letter
        itself rather than "the active word", so a note that just
        finished flashing after the word it belonged to already advanced
        isn't cut off early.
        """
        word = self.world.active_word
        elapsed = self.world.elapsed

        if word is not None:
            for letter in word.letters:
                key = id(letter)
                if key not in self._notes and letter.is_pending and elapsed >= letter.spawn_time:
                    lane = letter_lane(letter)
                    self._notes[key] = Note(
                        letter.char, lane_x(lane), lane_color(lane), letter.spawn_time, letter.hit_time
                    )

        for key in list(self._notes.keys()):
            note = self._notes[key]
            note.sync(elapsed)

            if note.expired(elapsed):
                del self._notes[key]

    def _consume_letter_event(self) -> None:
        event = self.world.consume_letter_event()

        if event is None:
            return

        letter, judgement, _points = event

        note = self._notes.get(id(letter))
        if note is not None:
            note.resolve(judgement, self.world.elapsed)

        lane = letter_lane(letter)
        self.renderer.push_judgement_popup(lane, judgement)

        # No SFX on a hit -- the backing song is what should be audible
        # there, since hit_time already lands right on it. A miss still
        # gets its own thud: negative feedback that isn't music.
        if judgement == scoring.MISS:
            self._sound_manager.play_miss_sound()

        # A letter event is the ONLY way World.game_over can flip to
        # True (see World._resolve_letter) -- checking for the
        # transition right here, rather than comparing World.finished
        # across two update() calls, is what catches it even when the
        # fatal miss came from a keypress: on_input() (where a wrong-key
        # miss resolves) always runs before update() within the same
        # frame (see gale's Game.exec), so by the time update() would
        # have compared "was it finished last frame", it already was.
        if self.world.finished and not self._game_over_handled:
            self._handle_game_over()

    def _handle_game_over(self) -> None:
        self._game_over_handled = True

        # Nothing left to land on a beat -- the song has no reason to
        # keep playing under the game-over screen. (exit() still covers
        # leaving PlayState entirely, e.g. via the "cover" button, in
        # case a restart never happens first.)
        pygame.mixer.music.stop()

        # Every run gets saved now, not just ones that beat the previous
        # best -- the sort_time each run carries is data this project
        # needs from every participant (see src/records.py's module
        # docstring), not only whoever currently tops the leaderboard.
        self._attempt_save_record()

    def _handle_victory(self) -> None:
        self._win_handled = True

        # The song already stopped on its own (see _start_song -- it no
        # longer loops), but this covers the same "leaving PlayState
        # entirely" edge case exit() does for game over.
        pygame.mixer.music.stop()

        self._attempt_save_record()

    def render(self, surface: pygame.Surface) -> None:
        if self._analyzing_song:
            self._render_analyzing_song(surface)
            return

        if self._showing_song_select:
            self._render_song_select(surface)
            return

        if self._showing_controls:
            self._render_instructions(surface)
            return

        # world is None only the first time this prompt is up (right
        # after the controls screen, before a run exists) -- self.renderer
        # below needs a World to draw, so this has to be its own standalone
        # screen rather than an overlay in that case. A later, world-set
        # visit (the collision-driven rename branch) falls through to the
        # overlay below instead, same as before this prompt moved here.
        if self._entering_record_name and self.world is None:
            self._render_participant_name_prompt(surface)
            return

        if self._sorting_screen_active:
            self._render_sort_loading(surface)
            return

        self.renderer.render(
            surface,
            notes=list(self._notes.values()),
            awaiting_record_name=self._entering_record_name or self._confirming_overwrite,
            game_over_selected=self._game_over_selected,
            win_selected=self._win_selected,
        )

        if self._entering_record_name or self._confirming_overwrite:
            self._render_record_name_prompt(surface)

    def _render_song_select(self, surface: pygame.Surface) -> None:
        """
        First screen of a run, before even the controls -- one "> "-prefixed
        row per settings.SONG_TITLES entry, navigated with move_up/move_down
        (wrapping, see _handle_song_select_input) and confirmed with
        "restart" (ENTER), same input vocabulary every other menu here uses.
        """
        surface.fill(settings.BACKGROUND_COLOR)

        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        render_text(
            surface,
            "¿A que ritmo quieres ir?",
            settings.FONTS["menu"],
            center_x,
            center_y - 60,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )

        line_height = 20
        start_y = center_y - (len(settings.SONG_TITLES) - 1) * line_height // 2

        for i, title in enumerate(settings.SONG_TITLES):
            selected = i == self._song_select_index
            color = settings.UI_ACCENT_COLOR if selected else settings.UI_TEXT_COLOR
            prefix = "> " if selected else "  "
            render_text(
                surface,
                prefix + title,
                settings.FONTS["menu"],
                center_x,
                start_y + i * line_height,
                color,
                center=True,
                shadowed=selected,
            )

        render_text(
            surface,
            "Flechas para elegir, ENTER para confirmar",
            settings.FONTS["hud"],
            center_x,
            settings.VIRTUAL_HEIGHT - 20,
            settings.UI_MUTED_COLOR,
            center=True,
        )

    def _render_analyzing_song(self, surface: pygame.Surface) -> None:
        """
        Shown for the (at least one-frame-long, several-seconds the first
        time a given song is picked) gap between confirming the song select
        menu and the beat analysis actually finishing -- see
        self._analyzing_song. Without this the screen would just sit frozen
        on the song select menu for however long BeatDetector.detect() takes,
        which read as the game hanging/looping.
        """
        surface.fill(settings.BACKGROUND_COLOR)

        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        render_text(
            surface,
            "Analizando el ritmo...",
            settings.FONTS["menu"],
            center_x,
            center_y,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )

    def _render_instructions(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)

        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        render_text(
            surface,
            "Como jugar",
            settings.FONTS["menu"],
            center_x,
            center_y - 60,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )

        for i, line in enumerate(_INSTRUCTIONS):
            render_text(
                surface,
                line,
                settings.FONTS["hud"],
                center_x,
                center_y - 10 + i * 20,
                settings.UI_TEXT_COLOR,
                center=True,
            )

    def _render_participant_name_prompt(self, surface: pygame.Surface) -> None:
        """
        Standalone screen (own background fill, like _render_instructions)
        shown once, right after the controls screen and before
        _begin_sort_task runs -- self.world doesn't exist yet at this
        point, so unlike _render_record_name_prompt this can't overlay a
        gameplay/game-over screen that isn't there.
        """
        surface.fill(settings.BACKGROUND_COLOR)

        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        render_text(
            surface,
            "Escribe tu nombre",
            settings.FONTS["menu"],
            center_x,
            center_y - 20,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            self._record_name + "_",
            settings.FONTS["hud"],
            center_x,
            center_y + 10,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            "Presiona ENTER para continuar",
            settings.FONTS["hud"],
            center_x,
            settings.VIRTUAL_HEIGHT - 20,
            settings.UI_MUTED_COLOR,
            center=True,
        )

    def _render_sort_loading(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)

        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        # len(self._sort_result), not settings.SORT_TASK_WORD_COUNT --
        # deduplicate_words (see _begin_sort_task) routinely drops a good
        # chunk of the generated batch, so the count actually sorted is
        # usually smaller than what was originally requested.
        render_text(
            surface,
            f"Ordenando {len(self._sort_result)} palabras...",
            settings.FONTS["menu"],
            center_x,
            center_y - 20,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            f"Completado en {self._sort_elapsed_seconds * 1000:.3f} ms",
            settings.FONTS["hud"],
            center_x,
            center_y + 10,
            settings.UI_TEXT_COLOR,
            center=True,
        )

    def _render_record_name_prompt(self, surface: pygame.Surface) -> None:
        """
        Overlay on top of the (finished) gameplay screen -- unlike
        _render_participant_name_prompt, only ever reachable post-game,
        when a finished run's already-typed name collides with an
        existing saved entry and _handle_overwrite_confirm_input's
        "rename" branch sends the player back here for a different one.
        """
        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2 + 60

        if self._confirming_overwrite:
            self._render_overwrite_confirm(surface, center_x, center_y)
            return

        render_text(
            surface,
            "Entraste a los records! Escribe tu nombre:",
            settings.FONTS["hud"],
            center_x,
            center_y,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            self._record_name + "_",
            settings.FONTS["hud"],
            center_x,
            center_y + 18,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )

    def _render_overwrite_confirm(self, surface: pygame.Surface, center_x: int, center_y: int) -> None:
        render_text(
            surface,
            f"Ya existe el nombre '{self._pending_record_name}' en los records",
            settings.FONTS["hud"],
            center_x,
            center_y,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )

        for i, label in enumerate(_OVERWRITE_LABELS):
            selected = i == self._overwrite_selected
            color = settings.UI_ACCENT_COLOR if selected else settings.UI_TEXT_COLOR
            prefix = "> " if selected else "  "
            render_text(
                surface,
                prefix + label,
                settings.FONTS["menu"],
                center_x,
                center_y + 20 + i * 20,
                color,
                center=True,
                shadowed=selected,
            )
