import random
import os
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'buscaminas_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Diccionarios y estructuras en memoria para el control del clúster distributed
partidas_activas = {}
clientes_conectados = set()  # Registro en memoria de sockets activos en tiempo real

class BuscaminasLogica:
  @staticmethod
  def generar_tablero(filas, columnas, num_minas):
    # Creamos tablero vacío lleno de ceros
    tablero = [[0 for _ in range(columnas)] for _ in range(filas)]
    minas = []

    # Colocamos las minas aleatoriamente
    minas_colocadas = 0
    while minas_colocadas < num_minas:
      fila = random.randint(0, filas - 1)
      columna = random.randint(0, columnas - 1)
      if (fila, columna) not in minas:
        minas.append((fila, columna))
        tablero[fila][columna] = 'M' # Representamos la mina con una 'M'
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

# --- EVENTOS WEB SOCKETS (Monitoreo del Clúster y Conexiones) ---

@socketio.on('connect')
def handle_connect(auth=None):
    sid = request.sid
    clientes_conectados.add(sid)
    print(f"\n[+ CONEXIÓN] Cliente conectado al servidor distribuido. Socket-ID: {sid}")
    print(f"[ESTADO CLÚSTER] Total clientes concurrentes activos: {len(clientes_conectados)}")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    # Remoción del socket del registro de telemetría activa
    if sid in clientes_conectados:
        clientes_conectados.remove(sid)
    
    # Limpieza preventiva de memoria RAM sobre el servidor
    if sid in partidas_activas:
        del partidas_activas[sid]
        
    print(f"\n[- DESCONEXIÓN] Cliente desconectado del servidor. Socket-ID: {sid}")
    print(f"[ESTADO CLÚSTER] Total clientes concurrentes activos: {len(clientes_conectados)}")

@socketio.on('configurar_juego')
def handle_config(data):
  filas = int(data['filas'])
  columnas = int(data['columnas'])
  num_minas = int(data['minas'])

  # El servidor genera el tablero dinámicamente
  tablero, minas = BuscaminasLogica.generar_tablero(filas, columnas, num_minas)

  # Guardamos la partida asociada al ID único de este cliente (Socket)
  client_id = request.sid
  partidas_activas[client_id] = {
    'tablero': tablero,
    'minas': minas,
    'filas': filas,
    'columnas': columnas,
    'reveladas': set()
  }

  # Le avisamos al cliente que el tablero está listo
  emit('tablero_creado', {'filas': filas, 'columnas': columnas})

# --- LÓGICA DE EVENTOS DE JUEGO EN TIEMPO REAL ---

@socketio.on('click_celda')
def handle_click(data):
  client_id = request.sid
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
    if not (0 <= fila < partida['filas'] and 0 <= columna < partida['columnas']):
      return
    if (fila, columna) in partida['reveladas']:
      return

    partida['reveladas'].add((fila, columna))
    valor = tablero[fila][columna]

    celdas_a_revelar.append({'fila': fila, 'columna': columna, 'valor': valor})

    if valor == 0:
      for i in range(-1, 2):
        for j in range(-1, 2):
          if i != 0 or j != 0:
            expandir_vacias(fila + i, columna + j)

  # Iniciamos la expansión desde la celda donde el usuario hizo click
  expandir_vacias(f, c)

  # --- LÓGICA DE DETECCIÓN DE VICTORIA ---
  total_casillas = partida['filas'] * partida['columnas']
  total_minas = len(partida['minas'])
  
  # Si las casillas ocultas son exactamente iguales a la cantidad de minas, el usuario ganó
  if total_casillas - len(partida['reveladas']) == total_minas:
    emit('resultado_click', {'evento': 'VICTORIA', 'celdas_a_revelar': celdas_a_revelar})
  else:
    emit('resultado_click', {'evento': 'CONTINUAR', 'celdas_a_revelar': celdas_a_revelar})

# REQUISITO 3: Opción "RESOLVER" 
@socketio.on('solicitar_resolucion')
def handle_resolver():
  client_id = request.sid
  if client_id in partidas_activas:
    partida = partidas_activas[client_id]
    emit('juego_resuelto', {'minas': partida['minas']})

if __name__ == '__main__':
    # Captura el puerto dinámico asignado por el entorno de Railway en producción
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)