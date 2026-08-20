"""
Draws a World (plus the Note objects PlayState is driving) onto a
pygame surface: the 4-lane highway, the hit zone and its targets, the
target word with the current letter highlighted, the upcoming-words
queue, and the HUD. All rendering concerns live here so the model in
src/world.py never has to know pygame exists -- the same split Game-01's
WorldRenderer keeps for Snake's grid.
"""
from typing import Dict, List, Tuple

import pygame

import settings
from src import scoring
from src.entities.falling_letter import FallingLetter
from src.rendering.note import Note
from src.rendering.pixel_text import render_text
from src.world import ActiveWord, World


def lane_x(lane_index: int) -> float:
    """Center x of lane `lane_index`, the LANE_COUNT lanes centered as a block."""
    total_width = (settings.LANE_COUNT - 1) * settings.LANE_SPACING
    start_x = (settings.VIRTUAL_WIDTH - total_width) / 2
    return start_x + lane_index * settings.LANE_SPACING


def letter_lane(letter: FallingLetter) -> int:
    """
    Which of the LANE_COUNT fixed lanes `letter` falls down -- assigned
    once by World's LaneManager (see src/entities/lane_manager.py) when
    the letter was built, not derived from its position in the word.
    """
    return letter.lane


def lane_color(lane_index: int) -> pygame.Color:
    return settings.LANE_COLORS[lane_index % len(settings.LANE_COLORS)]


def _blend(color: pygame.Color, target: pygame.Color, amount: float) -> pygame.Color:
    """`color` lerped `amount` (0..1) of the way towards `target`."""
    return pygame.Color(
        round(color.r + (target.r - color.r) * amount),
        round(color.g + (target.g - color.g) * amount),
        round(color.b + (target.b - color.b) * amount),
    )


def _brighten(color: pygame.Color, amount: float) -> pygame.Color:
    """`color` lerped towards white by `amount` (0..1) -- see the beat pulse in _render_hit_zone."""
    return _blend(color, pygame.Color(255, 255, 255), amount)


def _dim(color: pygame.Color, visibility: float) -> pygame.Color:
    """
    `color` lerped towards settings.BACKGROUND_COLOR as `visibility`
    (0..1) drops -- how the highway fades out during a World.highway_visibility
    song pause instead of just vanishing on a hard cutoff.
    """
    return _blend(color, settings.BACKGROUND_COLOR, 1.0 - visibility)


def _disco_color(elapsed: float) -> pygame.Color:
    """
    Continuously crossfades around settings.DISCO_COLORS' yellow -> red ->
    blue -> yellow loop, `elapsed` seconds in -- a steady real-time
    rotation (not locked to the beat) is what actually reads as "disco
    lights" cycling rather than a jarring per-beat color swap.
    """
    colors = settings.DISCO_COLORS
    phase = (elapsed / settings.DISCO_CYCLE_SECONDS_PER_COLOR) % len(colors)
    index = int(phase)
    return _blend(colors[index], colors[(index + 1) % len(colors)], phase - index)


class TypingRenderer:
    def __init__(self, world: World) -> None:
        self.world = world
        # Fading "PERFECTO"/"BIEN"/"OK"/"FALLO" callouts, appended by
        # PlayState (push_judgement_popup) whenever World resolves a
        # letter -- kept here rather than in World since they're pure
        # cosmetic feedback the model doesn't need to know about.
        self._popups: List[Dict] = []

    def push_judgement_popup(self, lane: int, judgement: str) -> None:
        self._popups.append(
            {"x": lane_x(lane), "judgement": judgement, "started_at": self.world.elapsed}
        )

    def render(
        self,
        surface: pygame.Surface,
        notes: List[Note],
        awaiting_record_name: bool = False,
        game_over_selected: int = 0,
        win_selected: int = 0,
    ) -> None:
        # The song's own macro loudness (World.energy_at_elapsed), not
        # just its beat -- a quiet verse and the loudest drop shouldn't
        # look the same. Read once per frame and threaded through below
        # rather than re-queried per element.
        energy = self.world.energy_at_elapsed()
        disco = _disco_color(self.world.elapsed)
        background = _blend(settings.BACKGROUND_COLOR, disco, energy * settings.DISCO_BACKGROUND_TINT_MAX)

        surface.fill(background)
        self._render_lanes(surface, energy)
        self._render_combo_watermark(surface)
        self._render_hit_zone(surface)

        # Same fade the highway/hit zone/target word already get during a
        # long song pause (see World.highway_visibility) -- without this a
        # falling note would sit fully bright over an otherwise
        # blacked-out highway while the music is silent.
        visibility = self.world.highway_visibility()
        for note in notes:
            note.render(surface, visibility)

        self._render_popups(surface)

        word = self.world.active_word
        if word is not None:
            self._render_target_word(surface, word)

        self._render_word_queue(surface)
        self._render_hud(surface)

        if self.world.game_over:
            self._render_game_over(surface, awaiting_record_name, game_over_selected)
        elif self.world.won:
            self._render_victory(surface, awaiting_record_name, win_selected)

    def _render_lanes(self, surface: pygame.Surface, energy: float) -> None:
        top = settings.FALL_START_Y - 10
        bottom = settings.HIT_ZONE_Y + settings.HIT_TARGET_RADIUS + 6

        base = _brighten(settings.LANE_SEPARATOR_COLOR, energy * settings.ENERGY_LANE_BRIGHTEN_MAX)
        color = _dim(base, self.world.highway_visibility())

        for lane in range(settings.LANE_COUNT):
            x = lane_x(lane)
            pygame.draw.line(surface, color, (x, top), (x, bottom), 1)

    def _render_combo_watermark(self, surface: pygame.Surface) -> None:
        combo = self.world.combo

        if combo < settings.COMBO_WATERMARK_MIN_COMBO:
            return

        text_surface = settings.FONTS["combo_watermark"].render(
            str(combo), True, settings.COMBO_WATERMARK_COLOR
        )
        text_surface.set_alpha(settings.COMBO_WATERMARK_ALPHA)
        center = (settings.VIRTUAL_WIDTH // 2, (settings.FALL_START_Y + settings.HIT_ZONE_Y) // 2)
        surface.blit(text_surface, text_surface.get_rect(center=center))

    def _beat_pulse_strength(self) -> float:
        """
        1.0 exactly on a main song beat, decaying linearly to 0.0 over
        settings.BEAT_PULSE_DURATION_SECONDS -- 0.0 whenever World has no
        beat schedule at all (see World.time_since_last_beat). This is
        what makes the hit zone visibly pulse in time with the music
        (see _render_hit_zone), independent of how sparsely letters
        themselves actually land on any one beat.
        """
        since_last_beat = self.world.time_since_last_beat()

        if since_last_beat is None:
            return 0.0

        return max(0.0, 1.0 - since_last_beat / settings.BEAT_PULSE_DURATION_SECONDS)

    def _render_hit_zone(self, surface: pygame.Surface) -> None:
        pulse = self._beat_pulse_strength()
        visibility = self.world.highway_visibility()

        left = lane_x(0) - settings.HIT_TARGET_RADIUS - 12
        right = lane_x(settings.LANE_COUNT - 1) + settings.HIT_TARGET_RADIUS + 12
        pygame.draw.line(
            surface,
            _dim(_brighten(settings.HIT_ZONE_COLOR, pulse * 0.6), visibility),
            (left, settings.HIT_ZONE_Y),
            (right, settings.HIT_ZONE_Y),
            settings.HIT_ZONE_HEIGHT + round(pulse * 3),
        )

        for lane in range(settings.LANE_COUNT):
            pygame.draw.circle(
                surface,
                _dim(_brighten(lane_color(lane), pulse * 0.6), visibility),
                (round(lane_x(lane)), settings.HIT_ZONE_Y),
                settings.HIT_TARGET_RADIUS + round(pulse * settings.BEAT_PULSE_RADIUS_BONUS),
                width=2,
            )

    def _render_target_word(self, surface: pygame.Surface, word: ActiveWord) -> None:
        font = settings.FONTS["letter"]
        char_width = font.size("W")[0]
        spacing = 10
        total_width = len(word.letters) * char_width + spacing * (len(word.letters) - 1)
        start_x = (settings.VIRTUAL_WIDTH - total_width) / 2

        current_index = next(
            (letter.index_in_word for letter in word.letters if letter.is_pending), None
        )
        # Fades the whole target word out during a song pause, right
        # alongside the highway and the falling note itself -- see
        # World.highway_visibility -- rather than leaving it sitting
        # there with nothing audible to type it against.
        visibility = self.world.highway_visibility()

        x = start_x
        for letter in word.letters:
            is_current = letter.index_in_word == current_index

            if letter.resolved and letter.judgement == scoring.MISS:
                color = settings.TARGET_SLOT_MISSED_COLOR
            elif letter.resolved:
                color = settings.TARGET_SLOT_DONE_COLOR
            elif is_current:
                color = settings.TARGET_SLOT_CURRENT_COLOR
            else:
                color = settings.TARGET_SLOT_PENDING_COLOR

            color = _dim(color, visibility)

            render_text(
                surface,
                letter.char,
                font,
                x + char_width / 2,
                settings.TARGET_WORD_Y,
                color,
                center=True,
                shadowed=is_current,
            )
            x += char_width + spacing

    def _render_word_queue(self, surface: pygame.Surface) -> None:
        """
        The next QUEUE_PREVIEW_COUNT words waiting in World's lookahead
        (see World.upcoming_words), stacked one below another underneath
        the target word -- a pile of what's coming up after the current
        word, not the letters within it.
        """
        words = self.world.upcoming_words[: settings.QUEUE_PREVIEW_COUNT]

        if not words:
            return

        font = settings.FONTS["queue"]
        center_x = settings.VIRTUAL_WIDTH // 2
        y = settings.QUEUE_START_Y

        for word_text in words:
            render_text(surface, word_text, font, center_x, y, settings.QUEUE_TEXT_COLOR, center=True)
            y += settings.QUEUE_LINE_HEIGHT

    def _render_popups(self, surface: pygame.Surface) -> None:
        still_active = []

        for popup in self._popups:
            age = self.world.elapsed - popup["started_at"]
            if age > settings.JUDGEMENT_POPUP_SECONDS:
                continue

            still_active.append(popup)
            progress = age / settings.JUDGEMENT_POPUP_SECONDS
            rise = -14 * progress
            alpha = max(0, 255 - int(255 * progress))

            color = settings.JUDGEMENT_COLORS[popup["judgement"]]
            label = settings.JUDGEMENT_LABELS[popup["judgement"]]

            popup_surface = settings.FONTS["popup"].render(label, True, color)
            popup_surface.set_alpha(alpha)
            rect = popup_surface.get_rect(center=(popup["x"], settings.HIT_ZONE_Y - 34 + rise))
            surface.blit(popup_surface, rect)

        self._popups = still_active

    def _render_hud(self, surface: pygame.Surface) -> None:
        render_text(
            surface,
            f"SCORE {self.world.score:06d}",
            settings.FONTS["hud"],
            10,
            8,
            settings.UI_ACCENT_COLOR,
            shadowed=True,
        )

        multiplier = scoring.combo_multiplier(self.world.combo)
        render_text(
            surface,
            f"COMBO x{self.world.combo}  ({multiplier:.2f}x)",
            settings.FONTS["hud"],
            10,
            24,
            settings.UI_ACCENT_COLOR,
        )

        self._render_lives(surface)

        right_x = settings.VIRTUAL_WIDTH - 10
        self._render_right_aligned(
            surface,
            f"PRECISION: {self.world.accuracy_percent:.1f}%",
            settings.FONTS["hud"],
            right_x,
            8,
            settings.UI_MUTED_COLOR,
        )
        self._render_right_aligned(
            surface,
            f"SPEED: {self.world.speed_multiplier:.2f}x",
            settings.FONTS["hud"],
            right_x,
            22,
            settings.UI_ACCENT_COLOR,
        )

    @staticmethod
    def _render_right_aligned(
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        right_x: float,
        y: float,
        color: pygame.Color,
    ) -> None:
        width, _height = font.size(text)
        render_text(surface, text, font, right_x - width, y, color)

    def _render_lives(self, surface: pygame.Surface) -> None:
        heart = settings.SPRITES["heart_full"]
        spacing = heart.get_width() + 3

        for i in range(settings.STARTING_LIVES):
            sprite = (
                settings.SPRITES["heart_full"] if i < self.world.lives else settings.SPRITES["heart_empty"]
            )
            surface.blit(sprite, (10 + i * spacing, 42))

    # Labels for PlayState's _GAME_OVER_OPTIONS ("restart", "cover"), in
    # the same order -- kept here since this module owns everything
    # drawn on screen, while PlayState owns which one is selected.
    _GAME_OVER_LABELS = ("Volver a jugar", "Volver al inicio")

    # Labels for PlayState's _WIN_OPTIONS ("same_track", "change_track",
    # "cover"), in the same order.
    _WIN_LABELS = ("Usar misma pista", "Cambiar pista", "Menu principal")

    def _render_game_over(
        self, surface: pygame.Surface, awaiting_record_name: bool, selected_index: int
    ) -> None:
        self._render_end_screen(surface, "GAME OVER", self._GAME_OVER_LABELS, awaiting_record_name, selected_index)

    def _render_victory(
        self, surface: pygame.Surface, awaiting_record_name: bool, selected_index: int
    ) -> None:
        self._render_end_screen(
            surface, "CANCION COMPLETADA", self._WIN_LABELS, awaiting_record_name, selected_index
        )

    def _render_end_screen(
        self,
        surface: pygame.Surface,
        title: str,
        labels: Tuple[str, ...],
        awaiting_record_name: bool,
        selected_index: int,
    ) -> None:
        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        overlay = pygame.Surface((settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*settings.BACKGROUND_COLOR[:3], 215))
        surface.blit(overlay, (0, 0))

        render_text(
            surface,
            title,
            settings.FONTS["title"],
            center_x,
            center_y - 60,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            f"Puntaje: {self.world.score}   Precision: {self.world.accuracy_percent:.1f}%   Racha maxima: {self.world.max_combo}",
            settings.FONTS["hud"],
            center_x,
            center_y - 32,
            settings.UI_TEXT_COLOR,
            center=True,
        )

        # While PlayState has the new-record name prompt up, ENTER
        # submits the name rather than confirming a button -- skip the
        # buttons below so they don't contradict what the key is about
        # to do (same rule Game-01's WorldRenderer follows).
        if awaiting_record_name:
            return

        for i, label in enumerate(labels):
            selected = i == selected_index
            color = settings.UI_ACCENT_COLOR if selected else settings.UI_TEXT_COLOR
            prefix = "> " if selected else "  "
            render_text(
                surface,
                prefix + label,
                settings.FONTS["menu"],
                center_x,
                center_y + 10 + i * 22,
                color,
                center=True,
                shadowed=selected,
            )

        render_text(
            surface,
            "Flechas arriba/abajo para elegir, ENTER para confirmar",
            settings.FONTS["hud"],
            center_x,
            center_y + 10 + len(labels) * 22 + 10,
            settings.UI_MUTED_COLOR,
            center=True,
        )
