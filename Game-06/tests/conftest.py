"""
Runs before any test module is imported. Forces SDL's dummy video/audio
drivers so importing `settings` (which initializes pygame's display and
mixer) works headlessly in CI/terminals without a screen or sound card.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
