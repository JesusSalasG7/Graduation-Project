"""
main.py

Punto de entrada de 2048 (Pygame + framework Gale).

Ejecutar desde este directorio con:
    python main.py
(o, si se usa el entorno virtual sugerido en requirements.txt:
    ./.venv/bin/python main.py)
"""
from __future__ import annotations

from gale.game import Game
from gale.state import StateMachine
from gale.input_handler import (
    InputHandler,
    KEY_UP,
    KEY_DOWN,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_r,
    KEY_RETURN,
    KEY_KP_ENTER,
    KEY_ESCAPE,
)

from states import PortadaState, PlayState, GameOverState


class Juego2048(Game):
    """Juego contenedor: delega toda la lógica en la StateMachine de Gale."""

    def init(self) -> None:
        # Flechas de dirección -> acciones de movimiento del tablero.
        InputHandler.set_keyboard_action(KEY_UP, "mover_arriba")
        InputHandler.set_keyboard_action(KEY_DOWN, "mover_abajo")
        InputHandler.set_keyboard_action(KEY_LEFT, "mover_izquierda")
        InputHandler.set_keyboard_action(KEY_RIGHT, "mover_derecha")
        InputHandler.set_keyboard_action(KEY_r, "reiniciar")
        InputHandler.set_keyboard_action(KEY_ESCAPE, "quit")

        # ENTER (principal o del teclado numérico) confirma en la portada.
        InputHandler.set_keyboard_action(KEY_RETURN, "confirmar")
        InputHandler.set_keyboard_action(KEY_KP_ENTER, "confirmar")

        self.state_machine = StateMachine(
            {"portada": PortadaState, "jugar": PlayState, "gameover": GameOverState}
        )
        self.state_machine.change("portada")

    def on_input(self, input_id: str, input_data) -> None:
        if input_id == "quit" and getattr(input_data, "pressed", False):
            self.quit()
            return
        self.state_machine.on_input(input_id, input_data)

    def update(self, dt: float) -> None:
        self.state_machine.update(dt)

    def render(self, surface) -> None:
        self.state_machine.render(surface)


if __name__ == "__main__":
    Juego2048().exec()
