"""
One-off generator for combat visual effects (src/combat/effects.py).
Same authoring convention as tools/generate_portraits.py and
tools/generate_character_sprites.py: pixel art authored on a fixed
grid, each grid cell one final pixel, computed procedurally in Python
-- no photo/AI/ripped source image involved.

The fireball (thrown whenever a Fuego match resolves, see
CombatManager._apply_match) is drawn as concentric color bands around
a center point (radial "distance from center" gradient) plus a
handful of jittered flame-tip pixels poking past the rim, reseeded
per frame for a flicker loop. The explosion is the same idea at a
growing radius with falling alpha, so it reads as a quick burst that
fades out.

Saved as one horizontal sheet of 6 frames in
assets/graphics/effects/fireball.png:
    0-2: flight loop (flicker)
    3-5: impact burst (grows, fades)
src/combat/effects.py slices the sheet back into those two groups.

Run once with the project's venv (needs pygame, already a dependency):
    python tools/generate_effect_sprites.py
Re-run any time a design below changes; it overwrites the PNG in
assets/graphics/effects/.
"""

import math
import random

from pathlib import Path

import pygame

pygame.init()

GRID = 24
CENTER = (GRID - 1) / 2

OUT_DIR = Path(__file__).parent.parent / "assets" / "graphics" / "effects"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WHITE = (255, 250, 210, 255)
YELLOW = (255, 195, 60, 255)
ORANGE = (240, 120, 30, 255)
RED = (200, 55, 20, 255)


class Canvas:
    def __init__(self, width: int = GRID, height: int = GRID) -> None:
        self.width = width
        self.height = height
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA)

    def px(self, x: int, y: int, color) -> None:
        if color is None or not (0 <= x < self.width and 0 <= y < self.height):
            return
        self.surface.set_at((x, y), color)


def _flight_frame(seed: int) -> pygame.Surface:
    c = Canvas()
    for y in range(GRID):
        for x in range(GRID):
            dist = math.hypot(x - CENTER, y - CENTER)
            if dist <= 2.6:
                c.px(x, y, WHITE)
            elif dist <= 4.6:
                c.px(x, y, YELLOW)
            elif dist <= 6.8:
                c.px(x, y, ORANGE)
            elif dist <= 8.2:
                c.px(x, y, RED)

    # Flame tips flicker: a handful of jittered pixels just past the
    # rim, reseeded per frame so consecutive frames look "alive".
    rng = random.Random(seed)
    for _ in range(7):
        angle = rng.uniform(0, 2 * math.pi)
        length = rng.uniform(7.5, 10.5)
        x = round(CENTER + math.cos(angle) * length)
        y = round(CENTER + math.sin(angle) * length * 0.9)
        c.px(x, y, rng.choice([ORANGE, RED, YELLOW]))

    return c.surface


def _explosion_frame_1() -> pygame.Surface:
    # Impact flash: a bright filled disc, same hot-core banding as the
    # fireball itself but bigger -- the burst at the instant of hit.
    c = Canvas()
    for y in range(GRID):
        for x in range(GRID):
            dist = math.hypot(x - CENTER, y - CENTER)
            if dist <= 3.2:
                c.px(x, y, WHITE)
            elif dist <= 6.2:
                c.px(x, y, YELLOW)
            elif dist <= 8.8:
                c.px(x, y, ORANGE)
    return c.surface


def _explosion_frame_2() -> pygame.Surface:
    # Shockwave expanding outward from the flash, still bright enough
    # to read clearly against the dark combat-strip background.
    c = Canvas()
    ring_out = (250, 140, 40, 235)
    ring_in = (255, 210, 110, 160)
    for y in range(GRID):
        for x in range(GRID):
            dist = math.hypot(x - CENTER, y - CENTER)
            if 6.5 <= dist <= 9.5:
                c.px(x, y, ring_out)
            elif 4 <= dist < 6.5:
                c.px(x, y, ring_in)
    return c.surface


def _explosion_frame_3() -> pygame.Surface:
    # Final thin ring, fading out as it reaches its widest point.
    c = Canvas()
    ring = (230, 90, 40, 150)
    for y in range(GRID):
        for x in range(GRID):
            dist = math.hypot(x - CENTER, y - CENTER)
            if 9 <= dist <= 11.5:
                c.px(x, y, ring)
    return c.surface


def fireball() -> None:
    flight = [_flight_frame(seed) for seed in (1, 2, 3)]
    explosion = [_explosion_frame_1(), _explosion_frame_2(), _explosion_frame_3()]
    frames = flight + explosion

    sheet = pygame.Surface((GRID * len(frames), GRID), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame, (index * GRID, 0))

    path = OUT_DIR / "fireball.png"
    pygame.image.save(sheet, str(path))
    print(f"saved {path} ({len(frames)} frames)")


# -- Lightning bolt ----------------------------------------------------
# Thrown whenever an Electricidad match resolves (see
# CombatManager._apply_match). Unlike the fireball, this one doesn't
# travel between the two characters -- it strikes straight down onto
# the target, so it's authored in a tall box (BOLT_W x BOLT_H) with the
# strike point at the bottom-center. The jagged path itself is a
# random midpoint-walk from top to bottom (classic pixel-lightning
# technique): pick a handful of waypoints, jitter their x each frame,
# and draw thick glowing segments between them plus a couple of short
# side forks. The impact is a radiating "spark star" (spikes fired out
# at even angles from the strike point) instead of the fireball's
# round burst, so the two elements read as visually distinct.

BOLT_W = 24
BOLT_H = 48
STRIKE_POINT = (BOLT_W / 2, BOLT_H - 6)

BOLT_CORE = (235, 250, 255, 255)
BOLT_GLOW = (110, 200, 255, 150)
BOLT_FORK_CORE = (200, 230, 255, 255)
BOLT_FORK_GLOW = (90, 170, 230, 110)


def _bolt_path(rng: random.Random, segments: int = 9) -> list:
    x = STRIKE_POINT[0]
    points = [(x, 0.0)]
    step = STRIKE_POINT[1] / segments
    for i in range(1, segments + 1):
        x += rng.uniform(-BOLT_W * 0.22, BOLT_W * 0.22)
        x = max(2.0, min(BOLT_W - 2.0, x))
        points.append((x, i * step))
    points[-1] = STRIKE_POINT
    return points


def _draw_glowing_segment(c: Canvas, p0, p1, core, glow, glow_radius: int = 1) -> None:
    steps = max(1, round(math.dist(p0, p1)))
    for s in range(steps + 1):
        t = s / steps
        x = round(p0[0] + (p1[0] - p0[0]) * t)
        y = round(p0[1] + (p1[1] - p0[1]) * t)
        for dx in range(-glow_radius, glow_radius + 1):
            for dy in range(-glow_radius, glow_radius + 1):
                if dx or dy:
                    c.px(x + dx, y + dy, glow)
        c.px(x, y, core)


def _bolt_frame(seed: int) -> pygame.Surface:
    rng = random.Random(seed)
    c = Canvas(BOLT_W, BOLT_H)
    path = _bolt_path(rng)

    for p0, p1 in zip(path, path[1:]):
        _draw_glowing_segment(c, p0, p1, BOLT_CORE, BOLT_GLOW)

    # A couple of short forks branching off the main path, dimmer and
    # thinner than the trunk.
    for _ in range(2):
        bx, by = path[rng.randint(2, len(path) - 2)]
        length = rng.uniform(5, 9)
        angle = rng.uniform(-1.1, 1.1)
        end = (bx + math.sin(angle) * length, by + math.cos(angle) * length * 0.7)
        _draw_glowing_segment(c, (bx, by), end, BOLT_FORK_CORE, BOLT_FORK_GLOW, glow_radius=0)

    return c.surface


def _spark_frame(spike_length: float, alpha: int, spikes: int = 8) -> pygame.Surface:
    c = Canvas(BOLT_W, BOLT_H)
    cx, cy = STRIKE_POINT

    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx * dx + dy * dy <= 5:
                c.px(round(cx + dx), round(cy + dy), (255, 255, 255, min(255, alpha + 30)))

    for i in range(spikes):
        angle = (2 * math.pi / spikes) * i
        for r in range(1, round(spike_length) + 1):
            x = round(cx + math.cos(angle) * r)
            y = round(cy + math.sin(angle) * r * 0.85)
            fade = max(0, alpha - round(alpha * 0.6 * r / spike_length))
            color = (190, 225, 255, fade) if i % 2 == 0 else (255, 235, 140, fade)
            c.px(x, y, color)

    return c.surface


def lightning() -> None:
    bolt = [_bolt_frame(seed) for seed in (11, 12, 13)]
    spark = [
        _spark_frame(9, 255),
        _spark_frame(12, 170),
        _spark_frame(15, 90),
    ]
    frames = bolt + spark

    sheet = pygame.Surface((BOLT_W * len(frames), BOLT_H), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame, (index * BOLT_W, 0))

    path = OUT_DIR / "lightning.png"
    pygame.image.save(sheet, str(path))
    print(f"saved {path} ({len(frames)} frames)")


# -- Water wave (Agua) ---------------------------------------------------
# Agua heals the caster instead of damaging the opponent (see
# src.combat.elements), so this is anchored on the attacker rather
# than thrown at the opponent -- CombatManager positions it so the
# wave's bottom edge sits at the caster's feet and rises up over them.
#
# The water surface is a sum of two sines (a long roll plus a shorter
# ripple) evaluated per column, filled downward in depth bands (foam
# skin, then progressively deeper blue) -- a wave rises from the feet,
# crests with a foam spray at the top, and recedes/fades.

WAVE_W = 44
WAVE_H = 52

FOAM = (235, 250, 255)
SHALLOW = (140, 210, 250)
MID = (70, 160, 230)
DEEP = (35, 100, 190)


def _wave_surface_y(x: float, base_y: float, amplitude: float, phase: float) -> float:
    return (
        base_y
        - amplitude * math.sin(x * 0.42 + phase)
        - amplitude * 0.35 * math.sin(x * 0.9 + phase * 1.6)
    )


def _wave_frame(
    base_y: float,
    amplitude: float,
    phase: float,
    alpha: int = 255,
    spray_seed: int = None,
) -> pygame.Surface:
    c = Canvas(WAVE_W, WAVE_H)
    # The crest/foam edge stays crisp at full alpha so the wave reads
    # clearly, but the body of the water is deliberately more
    # translucent -- at full opacity a wave tall enough to be visible
    # also fully hides the character behind it, which reads as "the
    # character vanished" instead of "a wave washed over them".
    body_alpha = round(alpha * 0.72)

    for x in range(WAVE_W):
        surf = _wave_surface_y(x, base_y, amplitude, phase)
        for y in range(WAVE_H):
            depth = y - surf
            if depth < 0:
                continue
            if depth < 1.8:
                color = (*FOAM, alpha)
            elif depth < 6:
                color = (*SHALLOW, alpha)
            elif depth < 15:
                color = (*MID, body_alpha)
            else:
                color = (*DEEP, body_alpha)
            c.px(x, int(y), color)

    if spray_seed is not None:
        # A handful of foam droplets flung up off the crest.
        rng = random.Random(spray_seed)
        for _ in range(9):
            x = rng.uniform(2, WAVE_W - 2)
            surf = _wave_surface_y(x, base_y, amplitude, phase)
            dy = rng.uniform(1, 7)
            spray_alpha = max(0, alpha - round(dy * 28))
            c.px(round(x + rng.uniform(-1.5, 1.5)), round(surf - dy), (*FOAM, spray_alpha))

    return c.surface


def water() -> None:
    # Rising: the water climbs from the caster's feet towards their
    # chest, rolling as it goes (base_y drops, amplitude/phase build).
    # Capped well short of the head -- the point is to wash *over* the
    # character, not bury them completely.
    rise = [
        _wave_frame(base_y=46, amplitude=2.0, phase=0.0),
        _wave_frame(base_y=36, amplitude=3.0, phase=0.9),
        _wave_frame(base_y=26, amplitude=3.6, phase=1.8),
    ]
    # Crest: breaks at chest height with a foam spray, then settles
    # back down and fades out as the heal finishes landing.
    crest = [
        _wave_frame(base_y=18, amplitude=4.2, phase=2.7, spray_seed=7),
        _wave_frame(base_y=23, amplitude=3.4, phase=3.4, alpha=200, spray_seed=8),
        _wave_frame(base_y=33, amplitude=2.4, phase=4.1, alpha=120),
    ]
    frames = rise + crest

    sheet = pygame.Surface((WAVE_W * len(frames), WAVE_H), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame, (index * WAVE_W, 0))

    path = OUT_DIR / "water.png"
    pygame.image.save(sheet, str(path))
    print(f"saved {path} ({len(frames)} frames)")


# -- Rock spikes (Tierra) -------------------------------------------------
# Tierra damages the opponent (see src.combat.elements), so this
# erupts at the defender's feet and shoots jagged rock spikes straight
# up through them -- a fixed point like the lightning bolt, not a
# travelling shot, since bursting to well past chest height at the
# target's own position already reads clearly as an impact. The
# silhouette reuses the wave's "per-column height function" approach,
# just swapped from a smooth sine to a jagged piecewise-linear profile
# (a handful of randomized peaks) so it reads as broken rock instead
# of rolling water.

ROCK_W = 44
ROCK_H = 52

ROCK_HIGHLIGHT = (206, 168, 112)
ROCK_MID = (146, 104, 64)
ROCK_DARK = (88, 62, 40)
DUST = (188, 160, 126)


def _rock_profile(rng: random.Random, base_y: float, max_rise: float, segments: int = 7) -> list:
    waypoints = []
    for i in range(segments + 1):
        x = i * (ROCK_W - 1) / segments
        # Taller spikes near the center, shorter towards the edges,
        # each jittered so no two peaks match.
        center_bias = max(0.15, 1 - abs((i / segments) - 0.5) * 1.6)
        height = max_rise * center_bias * rng.uniform(0.55, 1.0)
        waypoints.append((x, base_y - height))
    return waypoints


def _profile_y(x: float, waypoints: list) -> float:
    for (x0, y0), (x1, y1) in zip(waypoints, waypoints[1:]):
        if x0 <= x <= x1:
            t = 0 if x1 == x0 else (x - x0) / (x1 - x0)
            return y0 + (y1 - y0) * t
    return waypoints[-1][1]


def _rock_frame(
    seed: int,
    base_y: float,
    max_rise: float,
    alpha: int = 255,
    dust_seed: int = None,
) -> pygame.Surface:
    rng = random.Random(seed)
    waypoints = _rock_profile(rng, base_y, max_rise)
    c = Canvas(ROCK_W, ROCK_H)
    body_alpha = round(alpha * 0.92)

    for x in range(ROCK_W):
        surf = _profile_y(x, waypoints)
        for y in range(ROCK_H):
            depth = y - surf
            if depth < 0:
                continue
            if depth < 2:
                color = (*ROCK_HIGHLIGHT, alpha)
            elif depth < 9:
                color = (*ROCK_MID, body_alpha)
            else:
                color = (*ROCK_DARK, body_alpha)
            c.px(x, int(y), color)

    if dust_seed is not None:
        drng = random.Random(dust_seed)
        for _ in range(10):
            x = drng.uniform(2, ROCK_W - 2)
            surf = _profile_y(x, waypoints)
            dy = drng.uniform(1, 8)
            dust_alpha = max(0, alpha - round(dy * 22))
            c.px(round(x + drng.uniform(-2, 2)), round(surf - dy), (*DUST, dust_alpha))

    return c.surface


def rocks() -> None:
    # Erupting: spikes punch up out of the ground faster and taller
    # each frame -- same seed throughout so it reads as one formation
    # growing, not different rocks each frame.
    erupt = [
        _rock_frame(101, base_y=48, max_rise=8),
        _rock_frame(101, base_y=48, max_rise=18),
        _rock_frame(101, base_y=48, max_rise=28),
    ]
    # Impact: full height with a dust burst, then crumbles back down
    # (new seed each frame -- it's breaking apart, not just shrinking)
    # and fades out.
    impact = [
        _rock_frame(101, base_y=48, max_rise=34, dust_seed=55),
        _rock_frame(202, base_y=48, max_rise=27, alpha=205, dust_seed=56),
        _rock_frame(303, base_y=48, max_rise=17, alpha=115),
    ]
    frames = erupt + impact

    sheet = pygame.Surface((ROCK_W * len(frames), ROCK_H), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame, (index * ROCK_W, 0))

    path = OUT_DIR / "rocks.png"
    pygame.image.save(sheet, str(path))
    print(f"saved {path} ({len(frames)} frames)")


# -- Wind slash (Aire) -----------------------------------------------------
# Aire damages the opponent (see src.combat.elements) -- a thin curved
# blade (two overlapping discs, the overlap cut away) that streaks
# from attacker to defender much faster than the other projectiles,
# trailing speed lines. Impact is a small swirl of curved gust lines,
# not a filled burst -- wind has nothing solid to explode.

WIND_W = 30
WIND_H = 22

WIND_RIM = (245, 248, 250, 255)
WIND_BODY = (196, 208, 216, 230)
WIND_TRAIL = (210, 218, 224)


def _wind_blade_frame(tilt: float) -> pygame.Surface:
    c = Canvas(WIND_W, WIND_H)
    c1 = (13.0, WIND_H / 2)
    r1 = 9.5
    c2 = (13.0 + 5 + tilt, WIND_H / 2 - tilt * 0.6)
    r2 = 8.5

    for y in range(WIND_H):
        for x in range(WIND_W):
            d1 = math.hypot(x - c1[0], y - c1[1])
            d2 = math.hypot(x - c2[0], y - c2[1])
            if d1 <= r1 and d2 > r2:
                c.px(x, y, WIND_RIM if d1 >= r1 - 1.6 else WIND_BODY)

    for ly in (WIND_H / 2 - 5, WIND_H / 2, WIND_H / 2 + 5):
        for lx in range(0, 7):
            alpha = max(0, 150 - lx * 22)
            c.px(lx, round(ly), (*WIND_TRAIL, alpha))

    return c.surface


def _wind_gust_frame(radius: float, alpha: int) -> pygame.Surface:
    # Three short spiral arms unwinding from the center -- a gust
    # swirl, not a shockwave.
    c = Canvas(WIND_W, WIND_H)
    cx, cy = WIND_W / 2, WIND_H / 2
    for i in range(3):
        start_angle = i * (2 * math.pi / 3)
        for t in range(14):
            angle = start_angle + t * 0.35
            r = radius * (t / 14)
            x = cx + math.cos(angle) * r
            y = cy + math.sin(angle) * r * 0.7
            fade = max(0, alpha - t * (alpha // 14))
            c.px(round(x), round(y), (*WIND_TRAIL, fade))
    return c.surface


def wind() -> None:
    blade = [_wind_blade_frame(t) for t in (-1.5, 0.0, 1.5)]
    gust = [
        _wind_gust_frame(5, 235),
        _wind_gust_frame(8, 160),
        _wind_gust_frame(11, 90),
    ]
    frames = blade + gust

    sheet = pygame.Surface((WIND_W * len(frames), WIND_H), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame, (index * WIND_W, 0))

    path = OUT_DIR / "wind.png"
    pygame.image.save(sheet, str(path))
    print(f"saved {path} ({len(frames)} frames)")


# -- Ice shard (Hielo) -------------------------------------------------------
# Hielo damages the opponent (see src.combat.elements) -- a tumbling
# crystal shard (a rotated ellipse, rim/body/core bands) thrown
# attacker to defender that shatters into rigid straight fragments on
# impact -- broken-glass lines, unlike any of the other bursts.

ICE_W = 28
ICE_H = 18

ICE_RIM = (235, 250, 255, 255)
ICE_BODY = (110, 205, 235, 255)
ICE_CORE = (200, 240, 250, 255)


def _ice_shard_frame(angle: float) -> pygame.Surface:
    c = Canvas(ICE_W, ICE_H)
    cx, cy = ICE_W / 2, ICE_H / 2
    a, b = 12.0, 4.6
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    for y in range(ICE_H):
        for x in range(ICE_W):
            dx, dy = x - cx, y - cy
            rx = dx * cos_a + dy * sin_a
            ry = -dx * sin_a + dy * cos_a
            v = (rx / a) ** 2 + (ry / b) ** 2
            if v <= 1.0:
                if v <= 0.08:
                    c.px(x, y, ICE_CORE)
                elif v >= 0.72:
                    c.px(x, y, ICE_RIM)
                else:
                    c.px(x, y, ICE_BODY)
    return c.surface


def _ice_shatter_frame(spread: float, alpha: int) -> pygame.Surface:
    c = Canvas(ICE_W, ICE_H)
    cx, cy = ICE_W / 2, ICE_H / 2
    rng = random.Random(41)
    for _ in range(6):
        angle = rng.uniform(0, 2 * math.pi)
        length = rng.uniform(4, 7)
        x0 = cx + math.cos(angle) * spread
        y0 = cy + math.sin(angle) * spread * 0.75
        x1 = x0 + math.cos(angle) * length
        y1 = y0 + math.sin(angle) * length * 0.75
        steps = round(length)
        for s in range(steps + 1):
            t = s / steps if steps else 0
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            fade = max(0, alpha - round(t * alpha * 0.5))
            c.px(round(x), round(y), (*ICE_BODY[:3], fade))
    return c.surface


def ice() -> None:
    shard = [_ice_shard_frame(a) for a in (0.0, 0.6, 1.2)]
    shatter = [
        _ice_shatter_frame(1, 255),
        _ice_shatter_frame(4, 190),
        _ice_shatter_frame(7, 110),
    ]
    frames = shard + shatter

    sheet = pygame.Surface((ICE_W * len(frames), ICE_H), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame, (index * ICE_W, 0))

    path = OUT_DIR / "ice.png"
    pygame.image.save(sheet, str(path))
    print(f"saved {path} ({len(frames)} frames)")


# -- Arcane orb (Magia) -------------------------------------------------------
# Magia damages the opponent with a random, sometimes-critical amount
# (see src.combat.elements) -- a glowing orb like the fireball's, but
# ringed by a tilted halo of rune studs so it reads as "arcane" and
# not just a purple fireball. Impact is a precise double magic-circle
# flash (two concentric rings plus six studs), geometric rather than a
# soft blob.

ARCANE_SIZE = 30
ARCANE_CENTER = (ARCANE_SIZE - 1) / 2

ARCANE_CORE = (250, 235, 255, 255)
ARCANE_MID = (200, 130, 240, 255)
ARCANE_DEEP = (120, 60, 170, 255)
ARCANE_RING = (225, 170, 250, 235)


def _arcane_orb_frame(ring_offset: float) -> pygame.Surface:
    c = Canvas(ARCANE_SIZE, ARCANE_SIZE)
    for y in range(ARCANE_SIZE):
        for x in range(ARCANE_SIZE):
            dist = math.hypot(x - ARCANE_CENTER, y - ARCANE_CENTER)
            if dist <= 2.4:
                c.px(x, y, ARCANE_CORE)
            elif dist <= 4.6:
                c.px(x, y, ARCANE_MID)
            elif dist <= 6.2:
                c.px(x, y, ARCANE_DEEP)

    # Rune studs as 2x2 blocks (not single pixels) on a tilted halo,
    # well clear of the orb -- needs to read as an orbiting ring, not
    # a faint speckle around a purple fireball.
    for i in range(8):
        angle = ring_offset + i * (math.pi / 4)
        cx = ARCANE_CENTER + math.cos(angle) * 12.0
        cy = ARCANE_CENTER + math.sin(angle) * 5.4
        for dx in (0, 1):
            for dy in (0, 1):
                c.px(round(cx) + dx, round(cy) + dy, ARCANE_RING)
    return c.surface


def _arcane_flash_frame(radius: float, alpha: int) -> pygame.Surface:
    c = Canvas(ARCANE_SIZE, ARCANE_SIZE)
    ring_color = (*ARCANE_RING[:3], alpha)
    core_color = (*ARCANE_CORE[:3], alpha)
    for y in range(ARCANE_SIZE):
        for x in range(ARCANE_SIZE):
            dist = math.hypot(x - ARCANE_CENTER, y - ARCANE_CENTER)
            if dist <= 2.2:
                c.px(x, y, core_color)
            elif radius - 1.4 <= dist <= radius:
                c.px(x, y, ring_color)
            elif radius * 0.55 - 1.2 <= dist <= radius * 0.55:
                c.px(x, y, ring_color)
    for i in range(6):
        angle = i * (math.pi / 3)
        x = ARCANE_CENTER + math.cos(angle) * radius
        y = ARCANE_CENTER + math.sin(angle) * radius
        c.px(round(x), round(y), core_color)
    return c.surface


def arcane() -> None:
    orb = [_arcane_orb_frame(a) for a in (0.0, 0.8, 1.6)]
    flash = [
        _arcane_flash_frame(7, 255),
        _arcane_flash_frame(9.5, 180),
        _arcane_flash_frame(12, 100),
    ]
    frames = orb + flash

    sheet = pygame.Surface((ARCANE_SIZE * len(frames), ARCANE_SIZE), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame, (index * ARCANE_SIZE, 0))

    path = OUT_DIR / "arcane.png"
    pygame.image.save(sheet, str(path))
    print(f"saved {path} ({len(frames)} frames)")


# -- Void portal (Oscuridad) -------------------------------------------------
# Oscuridad ignores defense entirely (see src.combat.elements) -- a
# dark rift opens flat on the ground under the target with a violet
# rim (pure black would vanish against the background) and a few
# clawed tendrils reach up out of it. Fixed at the target, like the
# rock spikes, but thin and curved instead of solid and angular, and
# it closes back down instead of crumbling.

VOID_W = 44
VOID_H = 40

VOID_RIM = (150, 90, 200, 255)
VOID_GLOW = (90, 50, 130, 180)
VOID_CORE = (10, 6, 16, 255)


def _void_portal(c: Canvas, cx: float, cy: float, rx: float, ry: float) -> None:
    for y in range(c.height):
        for x in range(c.width):
            dx, dy = (x - cx) / rx, (y - cy) / ry
            v = dx * dx + dy * dy
            if v <= 1.0:
                c.px(x, y, VOID_CORE)
            elif v <= 1.3:
                c.px(x, y, VOID_RIM)
            elif v <= 1.7:
                c.px(x, y, VOID_GLOW)


def _void_tendril(c: Canvas, base_x: float, base_y: float, height: float, curve: float) -> None:
    steps = round(height)
    for s in range(steps + 1):
        t = s / steps if steps else 0
        x = base_x + curve * math.sin(t * math.pi)
        y = base_y - height * t
        xs = (-1, 0, 1) if t < 0.85 else (0,)
        for w in xs:
            c.px(round(x + w), round(y), VOID_RIM if t > 0.15 else VOID_GLOW)


def _void_frame(seed: int, tendril_height: float, portal_scale: float = 1.0) -> pygame.Surface:
    c = Canvas(VOID_W, VOID_H)
    cx, cy = VOID_W / 2, VOID_H - 8
    _void_portal(c, cx, cy, 15 * portal_scale, 5 * portal_scale)

    rng = random.Random(seed)
    for i in range(4):
        offset = (i - 1.5) * 6.5 + rng.uniform(-1.5, 1.5)
        curve = rng.uniform(-3, 3)
        _void_tendril(c, cx + offset, cy - 2, tendril_height * rng.uniform(0.7, 1.05), curve)
    return c.surface


def _void_close_frame(rx: float, ry: float, alpha: int) -> pygame.Surface:
    c = Canvas(VOID_W, VOID_H)
    cx, cy = VOID_W / 2, VOID_H - 8
    core = (*VOID_CORE[:3], alpha)
    rim = (*VOID_RIM[:3], alpha)
    for y in range(c.height):
        for x in range(c.width):
            dx, dy = (x - cx) / rx, (y - cy) / ry
            v = dx * dx + dy * dy
            if v <= 1.0:
                c.px(x, y, core)
            elif v <= 1.4:
                c.px(x, y, rim)
    return c.surface


def void() -> None:
    rise = [
        _void_frame(1, tendril_height=6),
        _void_frame(1, tendril_height=13),
        _void_frame(1, tendril_height=20),
    ]
    # Impact (full tendrils + a wider, brighter rim flash), then the
    # rift shrinks back down in two visible steps rather than jumping
    # straight to a barely-there speck.
    impact = [
        _void_frame(1, tendril_height=24, portal_scale=1.25),
        _void_close_frame(10, 3.5, 210),
        _void_close_frame(5, 1.8, 120),
    ]
    frames = rise + impact

    sheet = pygame.Surface((VOID_W * len(frames), VOID_H), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame, (index * VOID_W, 0))

    path = OUT_DIR / "void.png"
    pygame.image.save(sheet, str(path))
    print(f"saved {path} ({len(frames)} frames)")


if __name__ == "__main__":
    fireball()
    lightning()
    water()
    rocks()
    wind()
    ice()
    arcane()
    void()
