"""
Modulo C - Combate RPG.

Efectos visuales disparados por CombatManager._apply_match cuando el
elemento del match tiene uno propio:
    Fuego         -> Fireball: proyectil que vuela del atacante al
                     objetivo y termina en un estallido.
    Electricidad  -> LightningBolt: rayo que cae en linea recta sobre
                     el objetivo y termina en una chispa.
    Agua          -> WaterSplash: ola que viaja del rival hacia quien
                     se cura (Agua cura al atacante en vez de danar al
                     rival -- ver src.combat.elements) y rompe sobre
                     el al llegar.
    Tierra        -> RockSpikes: picos de roca que erupcionan a los
                     pies del objetivo.
    Aire          -> WindSlash: cuchilla curva que vuela del atacante
                     al objetivo mas rapido que las demas.
    Hielo         -> IceShard: esquirla de cristal que gira en el aire
                     y se hace anicos al llegar.
    Magia         -> ArcaneOrb: orbe con un halo de runas orbitando,
                     termina en un circulo magico geometrico.
    Oscuridad     -> VoidPortal: grieta oscura que se abre a los pies
                     del objetivo con zarcillos, y se cierra de nuevo.
El pixel-art de los ocho (ver tools/generate_effect_sprites.py, misma
tecnica que tools/generate_character_sprites.py) es 100% original: sin
imagenes de stock ni assets externos.
"""

from typing import List, Tuple

import pygame

import settings
from gale.timer import Timer

_EFFECTS_DIR = settings.BASE_DIR / "assets" / "graphics" / "effects"

_FLICKER_INTERVAL = 0.05
_IMPACT_FRAME_TIME = 0.06


def _load_sheet(name: str, frame_w: int, frame_h: int) -> List[pygame.Surface]:
    sheet = pygame.image.load(_EFFECTS_DIR / name).convert_alpha()
    count = sheet.get_width() // frame_w
    return [
        sheet.subsurface(pygame.Rect(i * frame_w, 0, frame_w, frame_h)).copy()
        for i in range(count)
    ]


# -- Fireball (Fuego) ---------------------------------------------------

_FIREBALL_FRAME_SIZE = 24
_FIREBALL_FLIGHT_COUNT = 3
_FIREBALL_FLIGHT_TIME = 0.15  # sincronizado con el impacto de Character.play_attack

_fireball_flight_frames: List[pygame.Surface] = []
_fireball_impact_frames: List[pygame.Surface] = []


def _ensure_fireball_frames_loaded() -> None:
    if _fireball_flight_frames:
        return
    frames = _load_sheet("fireball.png", _FIREBALL_FRAME_SIZE, _FIREBALL_FRAME_SIZE)
    _fireball_flight_frames.extend(frames[:_FIREBALL_FLIGHT_COUNT])
    _fireball_impact_frames.extend(frames[_FIREBALL_FLIGHT_COUNT:])


class Fireball:
    """Un solo disparo: vuela en linea recta del origen al destino y
    termina con un estallido corto antes de marcarse `done`."""

    def __init__(self, start: Tuple[int, int], end: Tuple[int, int]) -> None:
        _ensure_fireball_frames_loaded()
        self.x, self.y = start
        self.done = False
        self._exploding = False
        self._frame_index = 0

        self._flicker = Timer.every(_FLICKER_INTERVAL, self._advance_frame)
        Timer.tween(
            _FIREBALL_FLIGHT_TIME,
            [(self, {"x": end[0], "y": end[1]})],
            on_finish=self._explode,
        )

    def _advance_frame(self) -> None:
        frames = _fireball_impact_frames if self._exploding else _fireball_flight_frames
        self._frame_index = (self._frame_index + 1) % len(frames)

    def _explode(self) -> None:
        self._exploding = True
        self._frame_index = 0
        self._flicker.remove()
        Timer.every(
            _IMPACT_FRAME_TIME,
            self._advance_frame,
            limit=len(_fireball_impact_frames) - 1,
            on_finish=self._finish,
        )

    def _finish(self) -> None:
        self.done = True

    def render(self, surface: pygame.Surface) -> None:
        frames = _fireball_impact_frames if self._exploding else _fireball_flight_frames
        frame = frames[self._frame_index]
        rect = frame.get_rect(center=(round(self.x), round(self.y)))
        surface.blit(frame, rect)


# -- Lightning bolt (Electricidad) --------------------------------------
# Authored in a tall box with the strike point at the bottom-center
# (see tools/generate_effect_sprites.py), so unlike the fireball it
# doesn't travel -- it just appears above the target and strikes down.

_BOLT_FRAME_W = 24
_BOLT_FRAME_H = 48
_BOLT_STRIKE_OFFSET = (_BOLT_FRAME_W / 2, _BOLT_FRAME_H - 6)
_BOLT_FLICKER_COUNT = 3
_BOLT_STRIKE_TIME = 0.15  # sincronizado con el impacto de Character.play_attack

_bolt_flicker_frames: List[pygame.Surface] = []
_bolt_impact_frames: List[pygame.Surface] = []


def _ensure_lightning_frames_loaded() -> None:
    if _bolt_flicker_frames:
        return
    frames = _load_sheet("lightning.png", _BOLT_FRAME_W, _BOLT_FRAME_H)
    _bolt_flicker_frames.extend(frames[:_BOLT_FLICKER_COUNT])
    _bolt_impact_frames.extend(frames[_BOLT_FLICKER_COUNT:])


class LightningBolt:
    """Un solo rayo: aparece sobre el objetivo, parpadea durante el
    impulso del ataque y termina con una chispa antes de marcarse
    `done`. A diferencia de Fireball, no viaja -- el punto de impacto
    es fijo (el objetivo)."""

    def __init__(self, target: Tuple[int, int]) -> None:
        _ensure_lightning_frames_loaded()
        self.x, self.y = target
        self.done = False
        self._striking = False
        self._frame_index = 0

        self._flicker = Timer.every(_FLICKER_INTERVAL, self._advance_frame)
        Timer.after(_BOLT_STRIKE_TIME, self._strike)

    def _advance_frame(self) -> None:
        frames = _bolt_impact_frames if self._striking else _bolt_flicker_frames
        self._frame_index = (self._frame_index + 1) % len(frames)

    def _strike(self) -> None:
        self._striking = True
        self._frame_index = 0
        self._flicker.remove()
        Timer.every(
            _IMPACT_FRAME_TIME,
            self._advance_frame,
            limit=len(_bolt_impact_frames) - 1,
            on_finish=self._finish,
        )

    def _finish(self) -> None:
        self.done = True

    def render(self, surface: pygame.Surface) -> None:
        frames = _bolt_impact_frames if self._striking else _bolt_flicker_frames
        frame = frames[self._frame_index]
        # The strike point is baked into the sprite at _BOLT_STRIKE_OFFSET
        # (see tools/generate_effect_sprites.py) -- offset the frame so
        # that point lands exactly on the target.
        x = round(self.x - _BOLT_STRIKE_OFFSET[0])
        y = round(self.y - _BOLT_STRIKE_OFFSET[1])
        surface.blit(frame, (x, y))


# -- Water wave (Agua) ---------------------------------------------------
# Agua heals the caster, but a wave that just appears in place under
# them barely reads as "an attack happening" -- so like Fireball, this
# one travels: it surges from the rival's side of the strip across to
# the caster (rolling the whole way, ground-level), then rises up and
# crests over them with a foam spray right as the heal lands.

_WAVE_FRAME_W = 44
_WAVE_FRAME_H = 52
_WAVE_RISE_COUNT = 3
_WAVE_BOTTOM_OFFSET = settings.CHARACTER_SPRITE_SIZE // 2  # lands at the caster's feet
_WAVE_TRAVEL_TIME = 0.15  # sincronizado con el impacto de Character.play_attack

_wave_rise_frames: List[pygame.Surface] = []
_wave_crest_frames: List[pygame.Surface] = []


def _ensure_wave_frames_loaded() -> None:
    if _wave_rise_frames:
        return
    frames = _load_sheet("water.png", _WAVE_FRAME_W, _WAVE_FRAME_H)
    _wave_rise_frames.extend(frames[:_WAVE_RISE_COUNT])
    _wave_crest_frames.extend(frames[_WAVE_RISE_COUNT:])


class WaterSplash:
    """Una ola: surge desde el rival y viaja en linea recta hasta quien
    se cura, rodando (frames de 'rise') durante el trayecto, y rompe
    con espuma (frames de 'crest') justo al llegar, cuando la curacion
    se aplica."""

    def __init__(self, start: Tuple[int, int], end: Tuple[int, int]) -> None:
        _ensure_wave_frames_loaded()
        self.x, self.y = start
        self.done = False
        self._cresting = False
        self._frame_index = 0

        self._flicker = Timer.every(_FLICKER_INTERVAL, self._advance_frame)
        Timer.tween(
            _WAVE_TRAVEL_TIME,
            [(self, {"x": end[0], "y": end[1]})],
            on_finish=self._crest,
        )

    def _advance_frame(self) -> None:
        frames = _wave_crest_frames if self._cresting else _wave_rise_frames
        self._frame_index = (self._frame_index + 1) % len(frames)

    def _crest(self) -> None:
        self._cresting = True
        self._frame_index = 0
        self._flicker.remove()
        Timer.every(
            _IMPACT_FRAME_TIME,
            self._advance_frame,
            limit=len(_wave_crest_frames) - 1,
            on_finish=self._finish,
        )

    def _finish(self) -> None:
        self.done = True

    def render(self, surface: pygame.Surface) -> None:
        frames = _wave_crest_frames if self._cresting else _wave_rise_frames
        frame = frames[self._frame_index]
        rect = frame.get_rect()
        rect.centerx = round(self.x)
        rect.bottom = round(self.y + _WAVE_BOTTOM_OFFSET)
        surface.blit(frame, rect)


# -- Rock spikes (Tierra) -------------------------------------------------
# Tierra damages the opponent, so this erupts at the defender's feet
# (bottom-aligned like the wave) and stays put -- like LightningBolt,
# a fixed point rather than something thrown, since bursting well past
# chest height right where the target stands already reads as a hit.

_ROCK_FRAME_W = 44
_ROCK_FRAME_H = 52
_ROCK_ERUPT_COUNT = 3
_ROCK_BOTTOM_OFFSET = settings.CHARACTER_SPRITE_SIZE // 2  # erupts at the target's feet
_ROCK_ERUPT_TIME = 0.15  # sincronizado con el impacto de Character.play_attack

_rock_erupt_frames: List[pygame.Surface] = []
_rock_impact_frames: List[pygame.Surface] = []


def _ensure_rock_frames_loaded() -> None:
    if _rock_erupt_frames:
        return
    frames = _load_sheet("rocks.png", _ROCK_FRAME_W, _ROCK_FRAME_H)
    _rock_erupt_frames.extend(frames[:_ROCK_ERUPT_COUNT])
    _rock_impact_frames.extend(frames[_ROCK_ERUPT_COUNT:])


class RockSpikes:
    """Picos de roca que erupcionan a los pies del objetivo: crecen
    durante el impulso del ataque y estallan con polvo justo cuando el
    dano se aplica, antes de desmoronarse. No viaja -- el punto es
    fijo (el objetivo, no el atacante)."""

    def __init__(self, target: Tuple[int, int]) -> None:
        _ensure_rock_frames_loaded()
        self.x, self.y = target
        self.done = False
        self._impacting = False
        self._frame_index = 0

        self._flicker = Timer.every(_FLICKER_INTERVAL, self._advance_frame)
        Timer.after(_ROCK_ERUPT_TIME, self._impact)

    def _advance_frame(self) -> None:
        frames = _rock_impact_frames if self._impacting else _rock_erupt_frames
        self._frame_index = (self._frame_index + 1) % len(frames)

    def _impact(self) -> None:
        self._impacting = True
        self._frame_index = 0
        self._flicker.remove()
        Timer.every(
            _IMPACT_FRAME_TIME,
            self._advance_frame,
            limit=len(_rock_impact_frames) - 1,
            on_finish=self._finish,
        )

    def _finish(self) -> None:
        self.done = True

    def render(self, surface: pygame.Surface) -> None:
        frames = _rock_impact_frames if self._impacting else _rock_erupt_frames
        frame = frames[self._frame_index]
        rect = frame.get_rect()
        rect.centerx = round(self.x)
        rect.bottom = round(self.y + _ROCK_BOTTOM_OFFSET)
        surface.blit(frame, rect)


# -- Wind slash (Aire) ---------------------------------------------------

_WIND_FRAME_W = 30
_WIND_FRAME_H = 22
_WIND_BLADE_COUNT = 3
_WIND_FLIGHT_TIME = 0.15  # sincronizado con el impacto de Character.play_attack

_wind_blade_frames: List[pygame.Surface] = []
_wind_gust_frames: List[pygame.Surface] = []


def _ensure_wind_frames_loaded() -> None:
    if _wind_blade_frames:
        return
    frames = _load_sheet("wind.png", _WIND_FRAME_W, _WIND_FRAME_H)
    _wind_blade_frames.extend(frames[:_WIND_BLADE_COUNT])
    _wind_gust_frames.extend(frames[_WIND_BLADE_COUNT:])


class WindSlash:
    """Una cuchilla de viento: vuela en linea recta del atacante al
    objetivo (mismo tiempo de vuelo que Fireball, pero se percibe mas
    rapida por ser delgada y dejar lineas de velocidad) y termina en
    un remolino corto antes de marcarse `done`."""

    def __init__(self, start: Tuple[int, int], end: Tuple[int, int]) -> None:
        _ensure_wind_frames_loaded()
        self.x, self.y = start
        self.done = False
        self._gusting = False
        self._frame_index = 0

        self._flicker = Timer.every(_FLICKER_INTERVAL, self._advance_frame)
        Timer.tween(
            _WIND_FLIGHT_TIME,
            [(self, {"x": end[0], "y": end[1]})],
            on_finish=self._gust,
        )

    def _advance_frame(self) -> None:
        frames = _wind_gust_frames if self._gusting else _wind_blade_frames
        self._frame_index = (self._frame_index + 1) % len(frames)

    def _gust(self) -> None:
        self._gusting = True
        self._frame_index = 0
        self._flicker.remove()
        Timer.every(
            _IMPACT_FRAME_TIME,
            self._advance_frame,
            limit=len(_wind_gust_frames) - 1,
            on_finish=self._finish,
        )

    def _finish(self) -> None:
        self.done = True

    def render(self, surface: pygame.Surface) -> None:
        frames = _wind_gust_frames if self._gusting else _wind_blade_frames
        frame = frames[self._frame_index]
        rect = frame.get_rect(center=(round(self.x), round(self.y)))
        surface.blit(frame, rect)


# -- Ice shard (Hielo) ----------------------------------------------------

_ICE_FRAME_W = 28
_ICE_FRAME_H = 18
_ICE_SHARD_COUNT = 3
_ICE_FLIGHT_TIME = 0.15  # sincronizado con el impacto de Character.play_attack

_ice_shard_frames: List[pygame.Surface] = []
_ice_shatter_frames: List[pygame.Surface] = []


def _ensure_ice_frames_loaded() -> None:
    if _ice_shard_frames:
        return
    frames = _load_sheet("ice.png", _ICE_FRAME_W, _ICE_FRAME_H)
    _ice_shard_frames.extend(frames[:_ICE_SHARD_COUNT])
    _ice_shatter_frames.extend(frames[_ICE_SHARD_COUNT:])


class IceShard:
    """Una esquirla de hielo: vuela girando del atacante al objetivo y
    se hace anicos (fragmentos rigidos, no un estallido redondo) justo
    cuando el dano se aplica."""

    def __init__(self, start: Tuple[int, int], end: Tuple[int, int]) -> None:
        _ensure_ice_frames_loaded()
        self.x, self.y = start
        self.done = False
        self._shattering = False
        self._frame_index = 0

        self._flicker = Timer.every(_FLICKER_INTERVAL, self._advance_frame)
        Timer.tween(
            _ICE_FLIGHT_TIME,
            [(self, {"x": end[0], "y": end[1]})],
            on_finish=self._shatter,
        )

    def _advance_frame(self) -> None:
        frames = _ice_shatter_frames if self._shattering else _ice_shard_frames
        self._frame_index = (self._frame_index + 1) % len(frames)

    def _shatter(self) -> None:
        self._shattering = True
        self._frame_index = 0
        self._flicker.remove()
        Timer.every(
            _IMPACT_FRAME_TIME,
            self._advance_frame,
            limit=len(_ice_shatter_frames) - 1,
            on_finish=self._finish,
        )

    def _finish(self) -> None:
        self.done = True

    def render(self, surface: pygame.Surface) -> None:
        frames = _ice_shatter_frames if self._shattering else _ice_shard_frames
        frame = frames[self._frame_index]
        rect = frame.get_rect(center=(round(self.x), round(self.y)))
        surface.blit(frame, rect)


# -- Arcane orb (Magia) ----------------------------------------------------

_ARCANE_FRAME_SIZE = 30
_ARCANE_ORB_COUNT = 3
_ARCANE_FLIGHT_TIME = 0.15  # sincronizado con el impacto de Character.play_attack

_arcane_orb_frames: List[pygame.Surface] = []
_arcane_flash_frames: List[pygame.Surface] = []


def _ensure_arcane_frames_loaded() -> None:
    if _arcane_orb_frames:
        return
    frames = _load_sheet("arcane.png", _ARCANE_FRAME_SIZE, _ARCANE_FRAME_SIZE)
    _arcane_orb_frames.extend(frames[:_ARCANE_ORB_COUNT])
    _arcane_flash_frames.extend(frames[_ARCANE_ORB_COUNT:])


class ArcaneOrb:
    """Un orbe arcano con un halo de runas orbitando: vuela del
    atacante al objetivo y termina en un circulo magico (doble anillo
    concentrico) justo cuando el dano se aplica."""

    def __init__(self, start: Tuple[int, int], end: Tuple[int, int]) -> None:
        _ensure_arcane_frames_loaded()
        self.x, self.y = start
        self.done = False
        self._flashing = False
        self._frame_index = 0

        self._flicker = Timer.every(_FLICKER_INTERVAL, self._advance_frame)
        Timer.tween(
            _ARCANE_FLIGHT_TIME,
            [(self, {"x": end[0], "y": end[1]})],
            on_finish=self._flash,
        )

    def _advance_frame(self) -> None:
        frames = _arcane_flash_frames if self._flashing else _arcane_orb_frames
        self._frame_index = (self._frame_index + 1) % len(frames)

    def _flash(self) -> None:
        self._flashing = True
        self._frame_index = 0
        self._flicker.remove()
        Timer.every(
            _IMPACT_FRAME_TIME,
            self._advance_frame,
            limit=len(_arcane_flash_frames) - 1,
            on_finish=self._finish,
        )

    def _finish(self) -> None:
        self.done = True

    def render(self, surface: pygame.Surface) -> None:
        frames = _arcane_flash_frames if self._flashing else _arcane_orb_frames
        frame = frames[self._frame_index]
        rect = frame.get_rect(center=(round(self.x), round(self.y)))
        surface.blit(frame, rect)


# -- Void portal (Oscuridad) -----------------------------------------------

_VOID_FRAME_W = 44
_VOID_FRAME_H = 40
_VOID_RISE_COUNT = 3
_VOID_BOTTOM_OFFSET = settings.CHARACTER_SPRITE_SIZE // 2  # se abre a los pies del objetivo
_VOID_RISE_TIME = 0.15  # sincronizado con el impacto de Character.play_attack

_void_rise_frames: List[pygame.Surface] = []
_void_impact_frames: List[pygame.Surface] = []


def _ensure_void_frames_loaded() -> None:
    if _void_rise_frames:
        return
    frames = _load_sheet("void.png", _VOID_FRAME_W, _VOID_FRAME_H)
    _void_rise_frames.extend(frames[:_VOID_RISE_COUNT])
    _void_impact_frames.extend(frames[_VOID_RISE_COUNT:])


class VoidPortal:
    """Una grieta oscura que se abre a los pies del objetivo con
    zarcillos que se estiran hacia arriba: crecen durante el impulso
    del ataque y, justo cuando el dano se aplica, la grieta se abre al
    maximo antes de cerrarse de nuevo. No viaja -- el punto es fijo
    (el objetivo, no el atacante)."""

    def __init__(self, target: Tuple[int, int]) -> None:
        _ensure_void_frames_loaded()
        self.x, self.y = target
        self.done = False
        self._closing = False
        self._frame_index = 0

        self._flicker = Timer.every(_FLICKER_INTERVAL, self._advance_frame)
        Timer.after(_VOID_RISE_TIME, self._close)

    def _advance_frame(self) -> None:
        frames = _void_impact_frames if self._closing else _void_rise_frames
        self._frame_index = (self._frame_index + 1) % len(frames)

    def _close(self) -> None:
        self._closing = True
        self._frame_index = 0
        self._flicker.remove()
        Timer.every(
            _IMPACT_FRAME_TIME,
            self._advance_frame,
            limit=len(_void_impact_frames) - 1,
            on_finish=self._finish,
        )

    def _finish(self) -> None:
        self.done = True

    def render(self, surface: pygame.Surface) -> None:
        frames = _void_impact_frames if self._closing else _void_rise_frames
        frame = frames[self._frame_index]
        rect = frame.get_rect()
        rect.centerx = round(self.x)
        rect.bottom = round(self.y + _VOID_BOTTOM_OFFSET)
        surface.blit(frame, rect)
