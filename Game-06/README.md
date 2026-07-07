# Video_game_project
# The Rescue of Celeste
Un emocionante juego de aventura y rescate desarrollado en Python con las bibliotecas Pygame y Gale.

# Historia del juego
En un reino lejano, la princesa Celeste ha sido secuestrada por una malvada criatura que ha sumido al reino en la oscuridad. Desesperado, el Rey encomienda la misión de rescate a su caballero más fiel y valiente. El jugador tomará el rol de este caballero y deberá aventurarse en mazmorras llenas de peligros, resolver acertijos y enfrentarse a temibles enemigos para devolver la paz al reino.

# Mecánicas del juego
# Movimiento del caballero
•	Desplazarse a la izquierda: Presiona la tecla (a) o la tecla Flecha Izquierda.

•	Desplazarse a la derecha: Presiona la tecla (d) o la tecla Flecha Derecha.

•	Saltar: Presiona la tecla Espacio.

•	Atacar: Presiona la tecla (x) para invocar y utilizar tu espada.

# Vida del caballero
•	El caballero comienza con tres vidas.

•	Perderás una vida si:
Una criatura te daña.
Caes en los trampas de las mazmorras.

•	pierdes todas las vidas si:
caes en los abismos de la mazmorras

•	Si pierdes todas tus vidas, será el fin del juego.

# Elementos de las mazmorras
1.	Enemigos:
Criaturas hostiles que intentarán detener tu progreso.

2.  trampas:
trampas para evitar que puddas superar la mazmorras.

3.	Ítems:
Algunos objetos en las mazmorras son necesarios para avanzar en el juego.

# El objetivo
•	Rescatar a la princesa Celeste:
Para lograrlo, deberás atravesar todas las mazmorras y enfrentarte al Final Boss.

•	El Final Boss:
Este enemigo cuenta con siete vidas.
Evita sus ataques mientras encuentras oportunidades para contraatacar y derrotarlo.
Una vez que logres vencerlo, podrás liberar a la princesa y completar el juego.

# Recursos de audio y texturas
•	Origen de los recursos:
Los sonidos y texturas utilizados en el juego fueron obtenidos de la plataforma OpenGameArt.org.
Estos recursos han sido adaptados y personalizados para encajar en la estética y temática del juego.

# Contribuciones al código
•	Mecánicas y lógica:
Algunas de las mecánicas y la lógica del juego se basan en implementaciones realizadas por Alejandro Mijica, cuya experiencia en diseño de videojuegos fue clave para optimizar y enriquecer el desarrollo del proyecto.

# Metodología de desarrollo
•	Este juego fue diseñado utilizando los conocimientos adquiridos en el curso de Programación de Videojuegos.
•	Se emplearon las bibliotecas Pygame y Gale para la programación y diseño visual.

# Comenzando con The Rescue of Celeste
Sigue estos pasos para ejecutar el juego en tu computadora:
Descomprimir el archivo

Descomprime el archivo rescue_of_celeste.zip. Esto creará una carpeta llamada rescue_of_celeste.
Ingresar al directorio

Abre una terminal y navega a la carpeta del juego con el siguiente comando:
cd rescue_of_celeste

Crear un entorno virtual de Python

Crea un entorno virtual para gestionar las dependencias del juego:
python3 -m venv .venv

Activar el entorno virtual

Activa el entorno virtual con el siguiente comando:
source .venv/bin/activate

Instalar las dependencias

Una vez activado el entorno, instala los paquetes necesarios con:
pip install -r requirements.txt

Instalar la biblioteca Pillow

Es necesario instalar Pillow, una biblioteca de Python para manejar imágenes:
pip install pillow

Ejecutar el juego
Finalmente, ejecuta el juego con el siguiente comando:
python main.py

