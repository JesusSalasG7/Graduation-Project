"""
One-off generator for the combat sprite animation sheets
(src/combat/character.py). Same authoring convention as
tools/generate_portraits.py: pixel art authored on a fixed grid,
each grid cell rendered as a solid UNIT x UNIT block. There is no
photo/AI/ripped source image involved -- these are hand-placed grid
cells, in the same spirit as an .aseprite pixel-art editor, just
authored in Python instead of by mouse.

GRID here is 48 with UNIT=2 (each grid cell becomes a 2x2 block of
final pixels) so each frame comes out at settings.CHARACTER_SPRITE_SIZE
(96px) and drops straight into Character without any further scaling
-- a much finer authoring grid than the 16x16 used for portraits, so
there's room for a real fighting stance (raised guard, punching arm,
planted stance) instead of a flat color block.

Each character is saved as one horizontal sheet of 5 frames:
    idle_a, idle_b     -- a breathing bob loop
    attack_a, attack_b -- windup, then punch/impact
    hurt               -- reaction pose (guard drops, head snaps back)
src/combat/character.py slices the sheet back into those 5 frames.

Run once with the project's venv (needs pygame, already a dependency):
    python tools/generate_character_sprites.py
Re-run any time a design below changes; it overwrites the PNGs in
assets/graphics/characters/.
"""

from pathlib import Path

import pygame

pygame.init()

UNIT = 2
GRID = 48
SIZE = GRID * UNIT
FRAME_NAMES = ("idle_a", "idle_b", "attack_a", "attack_b", "hurt")

OUT_DIR = Path(__file__).parent.parent / "assets" / "graphics" / "characters"
OUT_DIR.mkdir(parents=True, exist_ok=True)


class Canvas:
    def __init__(self) -> None:
        self.surface = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)

    def px(self, x: int, y: int, color) -> None:
        if color is None or not (0 <= x < GRID and 0 <= y < GRID):
            return
        self.surface.fill(color, pygame.Rect(x * UNIT, y * UNIT, UNIT, UNIT))

    def rect(self, x0: int, y0: int, x1: int, y1: int, color) -> None:
        # Inclusive grid-cell rectangle, e.g. rect(3, 8, 12, 14, ...).
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.px(x, y, color)


def _save_sheet(frames: list, name: str) -> None:
    sheet = pygame.Surface((SIZE * len(frames), SIZE), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame, (index * SIZE, 0))
    path = OUT_DIR / name
    pygame.image.save(sheet, str(path))
    print(f"saved {path} ({len(frames)} frames)")


# -- Karateka (player) -------------------------------------------------------
# Fighting-game-style martial artist in a white gi with a red headband
# and belt, right leg forward, left fist guarding the chin, right fist
# throwing the punch. Facing right (towards the enemy panel).

P = {
    "skin": (232, 186, 140),
    "skin_sh": (196, 148, 108),
    "gi": (243, 243, 238),
    "gi_sh": (206, 206, 198),
    "band": (206, 40, 40),
    "band_dk": (150, 22, 22),
    "hair": (46, 34, 28),
    "cuff": (28, 24, 22),
    "eye": (24, 20, 18),
}


def _karateka_head(c: Canvas, bob: int, hurt: bool) -> None:
    y = 4 + bob
    # Hair cap + a few spiky tufts.
    c.rect(16, y + 1, 31, y + 6, P["hair"])
    for x in (17, 20, 24, 27, 30):
        c.px(x, y, P["hair"])
    # Headband, tied with a trailing tail to the back (left = behind,
    # since the character faces right).
    c.rect(16, y + 6, 31, y + 8, P["band"])
    c.rect(13, y + 6, 15, y + 8, P["band_dk"])
    c.px(13, y + 9, P["band_dk"])
    # Face.
    c.rect(17, y + 9, 30, y + 15, P["skin"])
    c.rect(17, y + 14, 30, y + 15, P["skin_sh"])
    if hurt:
        # Eyes squeezed shut: a single dark line each.
        c.rect(19, y + 11, 21, y + 11, P["eye"])
        c.rect(25, y + 11, 27, y + 11, P["eye"])
        c.rect(21, y + 14, 25, y + 14, P["skin_sh"])
    else:
        c.px(20, y + 11, P["eye"])
        c.px(21, y + 11, P["eye"])
        c.px(26, y + 11, P["eye"])
        c.px(27, y + 11, P["eye"])
    # Neck.
    c.rect(21, y + 16, 26, y + 18, P["skin"])


def _karateka_torso_legs(c: Canvas) -> None:
    # Gi top, shaded darker on the left (away from the light).
    c.rect(13, 19, 34, 33, P["gi_sh"])
    c.rect(16, 19, 34, 30, P["gi"])
    # Collar V.
    c.px(20, 19, P["skin_sh"])
    c.px(19, 20, P["skin_sh"])
    c.px(27, 19, P["skin_sh"])
    c.px(28, 20, P["skin_sh"])
    # Belt.
    c.rect(13, 29, 34, 31, P["band"])
    c.rect(13, 31, 34, 32, P["band_dk"])
    c.rect(21, 29, 26, 33, P["band_dk"])
    # Wide forward stance: back leg (left), front leg planted right.
    c.rect(14, 34, 21, 43, P["gi_sh"])
    c.rect(15, 34, 20, 42, P["gi"])
    c.rect(27, 34, 37, 44, P["gi_sh"])
    c.rect(28, 34, 36, 43, P["gi"])
    # Ankle cuffs + bare feet.
    c.rect(14, 42, 21, 43, P["cuff"])
    c.rect(27, 43, 37, 44, P["cuff"])
    c.rect(13, 44, 22, 46, P["skin"])
    c.rect(26, 45, 38, 47, P["skin"])


def _karateka_arms(c: Canvas, mode: str) -> None:
    # Back (left) arm: fixed high guard near the chin in every frame.
    c.rect(8, 17, 13, 22, P["skin"])
    c.rect(6, 10, 13, 17, P["skin_sh"])
    c.rect(6, 10, 12, 16, P["skin"])

    # Front (right) punching arm: guard -> cocked at the hip -> thrust.
    if mode in ("idle", "hurt"):
        c.rect(33, 18, 38, 23, P["skin"])
        c.rect(37, 16, 45, 23, P["skin_sh"])
        c.rect(37, 16, 44, 22, P["skin"])
        if mode == "hurt":
            # Guard drops to waist height, staggered back.
            c.rect(33, 18, 38, 23, None)
            c.rect(37, 16, 44, 22, None)
            c.rect(32, 27, 37, 32, P["skin"])
            c.rect(36, 30, 43, 36, P["skin_sh"])
            c.rect(36, 30, 42, 35, P["skin"])
    elif mode == "windup":
        c.rect(30, 25, 36, 30, P["skin"])
        c.rect(29, 29, 37, 36, P["skin_sh"])
        c.rect(29, 29, 36, 35, P["skin"])
    elif mode == "strike":
        c.rect(34, 18, 39, 23, P["skin"])
        c.rect(38, 17, 47, 23, P["skin_sh"])
        c.rect(38, 17, 46, 22, P["skin"])
        # Impact spark past the fist.
        c.px(47, 18, P["band"])
        c.px(47, 21, P["band"])
        c.px(46, 15, P["band"])


def _karateka_frame(bob: int, arm_mode: str, hurt: bool = False) -> pygame.Surface:
    c = Canvas()
    _karateka_torso_legs(c)
    _karateka_arms(c, arm_mode)
    _karateka_head(c, bob, hurt)
    return c.surface


def karateka() -> None:
    frames = [
        _karateka_frame(0, "idle"),
        _karateka_frame(-1, "idle"),
        _karateka_frame(0, "windup"),
        _karateka_frame(0, "strike"),
        _karateka_frame(1, "hurt", hurt=True),
    ]
    _save_sheet(frames, "player.png")


# -- Brawler (enemy) ----------------------------------------------------
# Bulkier, dark-palette street brawler with wrapped fists, facing left
# (towards the player panel) -- a distinct silhouette and colorway
# from the player so the two combatants read clearly apart.

E = {
    "skin": (168, 150, 140),
    "skin_sh": (128, 112, 104),
    "vest": (52, 48, 60),
    "vest_sh": (36, 33, 42),
    "wrap": (96, 46, 130),
    "wrap_dk": (66, 30, 92),
    "hair": (26, 22, 26),
    "cuff": (22, 19, 24),
    "eye": (230, 90, 60),
}


def _brawler_head(c: Canvas, bob: int, hurt: bool) -> None:
    y = 3 + bob
    c.rect(16, y + 1, 31, y + 7, E["hair"])
    for x in (15, 19, 28, 32):
        c.px(x, y, E["hair"])
    c.rect(17, y + 8, 30, y + 16, E["skin"])
    c.rect(17, y + 15, 30, y + 16, E["skin_sh"])
    if hurt:
        c.rect(19, y + 11, 21, y + 11, E["eye"])
        c.rect(25, y + 11, 27, y + 11, E["eye"])
        c.rect(21, y + 14, 25, y + 14, E["skin_sh"])
    else:
        c.rect(19, y + 10, 21, y + 11, E["eye"])
        c.rect(25, y + 10, 27, y + 11, E["eye"])
    c.rect(21, y + 17, 26, y + 19, E["skin"])


def _brawler_torso_legs(c: Canvas) -> None:
    c.rect(13, 20, 34, 34, E["vest_sh"])
    c.rect(13, 20, 31, 31, E["vest"])
    c.rect(13, 32, 34, 33, E["wrap_dk"])
    # Wide stance, front (left) leg planted forward.
    c.rect(10, 35, 20, 45, E["vest_sh"])
    c.rect(11, 35, 19, 44, E["vest"])
    c.rect(26, 35, 33, 44, E["vest_sh"])
    c.rect(27, 35, 32, 43, E["vest"])
    c.rect(10, 44, 20, 45, E["cuff"])
    c.rect(26, 43, 33, 44, E["cuff"])
    c.rect(9, 45, 21, 47, E["skin"])
    c.rect(25, 44, 34, 47, E["skin"])


def _brawler_arms(c: Canvas, mode: str) -> None:
    # Back (right) arm: fixed high guard, overlapping the torso's
    # right edge (x=34) by a column so it reads as one connected limb
    # instead of floating beside the head.
    c.rect(34, 17, 39, 22, E["skin"])
    c.rect(34, 10, 41, 17, E["wrap"])

    # Front (left) punching arm: guard -> cocked at the hip -> thrust.
    if mode in ("idle", "hurt"):
        c.rect(10, 18, 15, 23, E["skin"])
        c.rect(3, 16, 11, 23, E["wrap"])
        if mode == "hurt":
            c.rect(10, 18, 15, 23, None)
            c.rect(3, 16, 11, 23, None)
            c.rect(11, 27, 16, 32, E["skin"])
            c.rect(5, 30, 12, 36, E["wrap"])
    elif mode == "windup":
        c.rect(12, 25, 18, 30, E["skin"])
        c.rect(11, 29, 19, 36, E["wrap"])
    elif mode == "strike":
        c.rect(9, 18, 14, 23, E["skin"])
        c.rect(1, 17, 9, 23, E["wrap"])
        c.px(0, 18, E["eye"])
        c.px(0, 21, E["eye"])
        c.px(1, 15, E["eye"])


def _brawler_frame(bob: int, arm_mode: str, hurt: bool = False) -> pygame.Surface:
    c = Canvas()
    _brawler_torso_legs(c)
    _brawler_arms(c, arm_mode)
    _brawler_head(c, bob, hurt)
    return c.surface


def brawler() -> None:
    frames = [
        _brawler_frame(0, "idle"),
        _brawler_frame(-1, "idle"),
        _brawler_frame(0, "windup"),
        _brawler_frame(0, "strike"),
        _brawler_frame(1, "hurt", hurt=True),
    ]
    _save_sheet(frames, "enemy.png")


if __name__ == "__main__":
    karateka()
    brawler()
