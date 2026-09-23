"""Prueba rapida y manual de la configuracion de Gemini (AI_PROVIDER=gemini
+ GEMINI_API_KEY), sin arrancar la sesion guiada completa.

No hardcodea ni imprime la API key -- solo lee las variables de entorno ya
exportadas en la terminal donde se corre este script.

Uso:
    export AI_PROVIDER=gemini
    export GEMINI_API_KEY="tu-api-key"
    .venv/bin/python graphic_interface/test_gemini_connection.py
"""

import ai_backend

print(f"Proveedor activo: {ai_backend.active_provider()}")

if not ai_backend.provider_available():
    print(f"NO disponible: {ai_backend.provider_unavailable_reason()}")
    raise SystemExit(1)

print("Variables detectadas, probando llamada real a Gemini...")
result = ai_backend.run_isolated_prompt(
    prompt="Responde unicamente con la palabra: OK",
    system_prompt="Eres un asistente que responde de forma extremadamente breve.",
    model="",  # no aplica al backend gemini
    timeout=30,
)

if result.ok:
    print(f"Conexión OK. Respuesta del modelo: {result.text!r}")
else:
    print(f"Falló: {result.error}")
    raise SystemExit(1)
