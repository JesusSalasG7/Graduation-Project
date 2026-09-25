"""
Estados de la Máquina de Estados de Gale para 2048:
  - CoverState: pantalla de inicio con la imagen de portada (Cover.png).
  - PlayState: tablero jugable, entrada de flechas, marcador.
  - GameOverState: pantalla final (victoria o derrota) con reinicio.
"""
from src.states.cover_state import CoverState
from src.states.game_over_state import GameOverState
from src.states.play_state import PlayState

__all__ = ["CoverState", "GameOverState", "PlayState"]
