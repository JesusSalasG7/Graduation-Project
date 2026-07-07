import settings
from src.RescueofCeleste import RescueofCeleste

if __name__ == "__main__":
    Rescue_of_Celeste = RescueofCeleste(
        "Rescue of Celeste",
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.VIRTUAL_WIDTH,
        settings.VIRTUAL_HEIGHT,
    )
    Rescue_of_Celeste.exec()
