"""
One-off generator for the combat portraits (src/ui/hud.draw_portrait).

Every sprite is authored on a 16x16 "pixel-art" grid where each grid
cell is rendered as a solid UNIT x UNIT block, then saved at
16*UNIT = 64px so it drops in at the exact size the combat HUD's
portrait rects already use (settings.py). There is no photo/AI source
image involved -- these are hand-placed grid cells, in the same spirit
as an .ase/.aseprite pixel-art editor, just authored in Python instead
of by mouse.

Run once with the project's venv (needs pygame, already a dependency):
    python tools/generate_portraits.py
Re-run any time a design below changes; it overwrites the PNGs in
assets/graphics/portraits/.
"""

from pathlib import Path

import pygame

pygame.init()

UNIT = 4
GRID = 16
SIZE = GRID * UNIT

OUT_DIR = Path(__file__).parent.parent / "assets" / "graphics" / "portraits"
OUT_DIR.mkdir(parents=True, exist_ok=True)


class Canvas:
    def __init__(self) -> None:
        self.surface = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)

    def px(self, x: int, y: int, color) -> None:
        if color is None:
            return
        self.surface.fill(color, pygame.Rect(x * UNIT, y * UNIT, UNIT, UNIT))

    def rect(self, x0: int, y0: int, x1: int, y1: int, color) -> None:
        # Inclusive grid-cell rectangle, e.g. rect(3, 8, 12, 14, ...).
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.px(x, y, color)

    def row(self, y: int, pattern: str, palette: dict, mirror: bool = True) -> None:
        """
        pattern covers columns 0..len(pattern)-1. If mirror is True
        (the default), it is also mirrored onto the remaining columns
        of the 16-wide grid (pattern of length 8 -> columns 8..15 get
        the reverse), which is how every symmetric front-facing sprite
        below is authored: draw the left half, get the right half free.
        """
        for x, ch in enumerate(pattern):
            self.px(x, y, palette.get(ch))
        if mirror:
            width = len(pattern)
            for x, ch in enumerate(pattern):
                self.px(GRID - 1 - x, y, palette.get(ch))

    def save(self, name: str) -> None:
        path = OUT_DIR / name
        pygame.image.save(self.surface, str(path))
        print(f"saved {path}")


def alquimista() -> None:
    c = Canvas()
    P = {
        "h": (46, 54, 92),
        "H": (68, 92, 168),
        "f": (24, 22, 32),
        "e": (150, 230, 255),
        "r": (60, 92, 190),
        "d": (40, 60, 140),
        "b": (214, 182, 84),
        "s": (224, 182, 150),
    }
    c.row(2, ".......h", P)
    c.row(3, "......hH", P)
    c.row(4, ".....hHH", P)
    c.row(5, "....hHHH", P)
    c.row(6, "...hHfef", P)
    c.row(7, "..hHHfff", P)
    c.rect(1, 8, 14, 8, None)
    c.row(8, "dHHHHHHH", P)
    c.rect(3, 9, 12, 13, P["r"])
    c.rect(7, 9, 8, 13, P["H"])
    c.rect(1, 9, 2, 12, P["d"])
    c.rect(3, 11, 12, 11, P["b"])
    c.rect(2, 14, 13, 15, P["d"])
    c.px(1, 12, P["s"])
    # Right hand holds a vial of Esencia Roja -- deliberately breaks
    # the mirror symmetry, drawn after row()/rect() so it overrides
    # whatever the mirrored robe put there.
    c.px(14, 12, P["s"])
    c.rect(13, 9, 14, 10, (204, 224, 232))
    c.px(13, 9, (232, 70, 70))
    c.save("alquimista.png")


def homunculo_de_hierro() -> None:
    c = Canvas()
    P = {
        "p": (150, 152, 160),
        "d": (104, 106, 116),
        "o": (58, 58, 66),
        "r": (220, 60, 50),
    }
    c.row(3, "....pppp", P)
    c.row(4, "...ppppd", P)
    c.row(5, "...pordp", P)
    c.row(6, "...poddp", P)
    c.row(7, "....pppp", P)
    c.rect(1, 8, 14, 8, P["o"])
    c.rect(2, 9, 13, 14, P["p"])
    c.rect(2, 9, 3, 14, P["d"])
    c.rect(1, 9, 1, 12, P["d"])
    c.rect(6, 10, 9, 13, P["d"])
    c.px(6, 11, P["o"])
    c.px(9, 11, P["o"])
    c.rect(2, 15, 13, 15, P["o"])
    c.save("homunculo_hierro.png")


def espectro_alquimico() -> None:
    c = Canvas()
    P = {
        "g": (150, 96, 200),
        "G": (188, 140, 224),
        "d": (94, 58, 140),
        "e": (216, 244, 255),
    }
    c.row(3, "......gg", P)
    c.row(4, ".....gGG", P)
    c.row(5, "....gGeG", P)
    c.row(6, "....gGGG", P)
    c.rect(3, 7, 12, 12, P["g"])
    c.rect(5, 7, 10, 12, P["G"])
    c.row(13, "..gGdGg.", P, mirror=False)
    c.row(14, ".gGd.dGg", P, mirror=False)
    c.row(15, "gGd...dG", P, mirror=False)
    c.save("espectro_alquimico.png")


def guardian_de_cristal() -> None:
    c = Canvas()
    P = {
        "c": (72, 156, 208),
        "C": (140, 210, 236),
        "d": (38, 92, 132),
        "w": (236, 250, 255),
    }
    c.row(2, ".......c", P)
    c.row(3, "......cC", P)
    c.row(4, ".....cCw", P)
    c.row(5, "......cC", P)
    c.row(6, ".......c", P)
    c.rect(2, 7, 13, 8, P["c"])
    c.rect(2, 9, 13, 14, P["c"])
    c.rect(6, 9, 9, 14, P["C"])
    c.rect(2, 9, 3, 14, P["d"])
    c.rect(12, 9, 13, 14, P["d"])
    c.px(7, 10, P["w"])
    c.px(7, 12, P["w"])
    c.rect(3, 15, 12, 15, P["d"])
    c.save("guardian_cristal.png")


def dragon_de_mercurio() -> None:
    c = Canvas()
    P = {
        "b": (196, 90, 62),
        "B": (226, 128, 90),
        "d": (140, 56, 40),
        "e": (250, 220, 60),
    }
    # Horns (deliberately gapped -- two separate points, not a block)
    c.row(2, "......b.", P)
    # Head: each row's rightmost column touches the mirror seam so the
    # head reads as one solid block instead of splitting into two.
    c.row(3, ".....BBB", P)
    c.row(4, ".....BeB", P)
    c.row(5, ".....dBB", P)
    c.row(6, ".....BBB", P)
    # Wings flare out past the body on rows 7-9
    c.rect(0, 8, 2, 10, P["d"])
    c.rect(1, 8, 2, 9, P["b"])
    c.rect(13, 8, 15, 10, P["d"])
    c.rect(13, 8, 14, 9, P["b"])
    # Body
    c.rect(4, 7, 11, 13, P["b"])
    c.rect(5, 8, 10, 12, P["B"])
    # Tail, curling off to one side (asymmetric on purpose)
    c.row(14, ".d......", P, mirror=False)
    c.row(14, "......d.", P, mirror=False)
    c.row(15, "dd......", P, mirror=False)
    c.rect(4, 14, 11, 15, P["d"])
    c.save("dragon_mercurio.png")


if __name__ == "__main__":
    alquimista()
    homunculo_de_hierro()
    espectro_alquimico()
    guardian_de_cristal()
    dragon_de_mercurio()
