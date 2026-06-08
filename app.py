import random
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'buscaminas_secret_key'
# Permitimos conexiones desde cualquier origen para evitar problemas de CORS
socketio = SocketIO(app, cors_allowed_origins="*")

# Diccionario en memoria para guardar el estado del juego de cada cliente conectado
# Estructura: { socket_id: { 'tablero': [...], 'minas': [...], 'filas': X, 'columnas': Y } }
partidas_activas = {}

class BuscaminasLogica:
  @staticmethod
  def generar_tablero(filas, columnas, num_minas):
    # Creamos tablero vacío lleno de ceros
    tablero = [[0 for _ in range(columnas)] for _ in range(filas)]
    minas = []

    # Colocamos las minas aleatoreamente
    minas_colocadas = 0
    while minas_colocadas < num_minas:
      fila = random.randint(0, filas - 1)
      columna = random.randint(0, columnas - 1)
      if (fila, columna) not in minas:
        minas.append((fila, columna))
        tablero[fila][columna] = 'M' # Representramos la mina con una 'M'
        minas_colocadas += 1

    # Calcular los números alrededor de las minas
    for fila, columna in minas:
      for i in range(-1, 2):
        for j in range(-1, 2):
          if 0 <= fila + i < filas and 0 <= columna + j < columnas:
            if tablero[fila + i][columna + j] != 'M':
              tablero[fila + i][columna + j] += 1

    return tablero, minas
  
@app.route('/')
def index():
  # Renderizamos la página web principal
  return render_template('index.html')

# --- EVENTOS WEB SOCKETS (Comunicación Bidireccional) ---

@socketio.on('connect')
def handle_connect(auth=None):
    print(f"Cliente conectado al servidor distribuido. Socket-ID: {request.sid}")

@socketio.on('configurar_juego')
def handle_config(data):
  # El cliente envía el tamaño y cantidad de minas por el socket
  filas = int(data['filas'])
  columnas = int(data['columnas'])
  num_minas = int(data['minas'])

  # El servidor genera el tablero dinámicamente
  tablero, minas = BuscaminasLogica.generar_tablero(filas, columnas, num_minas)

  # Guardamos la partida asociada al ID único de este cliente (Socket)
  # Flask-SocketIO maneja un hilo independiente para cada evento de cliente
  client_id = request.sid
  partidas_activas[client_id] = {
    'tablero': tablero,
    'minas': minas,
    'filas': filas,
    'columnas': columnas,
    'reveladas': set()
  }

  # Le avisamos al cliente que el tablero está listo (sin enviarle las posiciones de las minas)
  emit('tablero_creado', {'filas': filas, 'columnas': columnas})

# --- LÓGICA DE EVENTOS DE JUEGO EN TIEMPO REAL ---

@socketio.on('click_celda')
def handle_click(data):
  client_id = request.sid
  # Si por alguna razón el servidor se reinició y no encuentra la partida, ignoramos.
  if client_id not in partidas_activas:
    return
  
  partida = partidas_activas[client_id]
  f = int(data['fila'])
  c = int(data['columna'])

  tablero = partida['tablero']
  celdas_a_revelar = []

  # REQUISITO 1: Verificar si pisó una mina (Game Over)
  if tablero[f][c] == 'M':
    emit('resultado_click', {'evento': 'GAME_OVER', 'celdas_a_revelar': []})
    return

  # REQUISITO 2: Algoritmo recursivo para expandir casillas vacías ("FLOOD FILL")
  def expandir_vacias(fila, columna):
    # Validar límites de la matriz y si ya fue procesada en este ciclo o antes
    if not (0 <= fila < partida['filas'] and 0 <= columna < partida['columnas']):
      return
    if (fila, columna) in partida['reveladas']:
      return

    partida['reveladas'].add((fila, columna))
    valor = tablero[fila][columna]

    celdas_a_revelar.append({'fila': fila, 'columna': columna, 'valor': valor})

    # Si la celda actual tiene 0 minas alrededor, ejecutamos la recursividad en las 8 direcciones contiguas
    if valor == 0:
      for i in range(-1, 2):
        for j in range(-1, 2):
          if i != 0 or j != 0:
            expandir_vacias(fila + i, columna + j)

  # Iniciamos la expansión desde la celda donde el usuario hizo click
  expandir_vacias(f, c)

  # Devolvemos al cliente la lista de celdas que debe pintar en su pantalla
  emit('resultado_click', {'evento': 'CONTINUAR', 'celdas_a_revelar': celdas_a_revelar})


# REQUISITO 3: Opción "RESOLVER" 
@socketio.on('solicitar_resolucion')
def handle_resolver():
  client_id = request.sid
  if client_id in partidas_activas:
    partida = partidas_activas[client_id]
    # Le enviamos al cliente únicamente las coordenadas de las minas
    emit('juego_resuelto', {'minas': partida['minas']})

if __name__ == '__main__':
  # Ejecutamos el servidor con soporte para WebSockets
  socketio.run(app, debug=True)
