// static/js/juego.js
const socket = io();
let juegoTerminado = false;
let minasTotales = 0;
let banderasColocadas = 0;
let temporizador = null;
let tiempoRestante = 60;

function iniciarJuego() {
    juegoTerminado = false;
    clearInterval(temporizador);
    document.getElementById('btn-resolver').disabled = false;
    
    const filas = document.getElementById('filas').value;
    const columnas = document.getElementById('columnas').value;
    minasTotales = parseInt(document.getElementById('minas').value);
    banderasColocadas = 0;

    document.getElementById('txt-minas-restantes').innerText = minasTotales;

    const usarTiempo = document.getElementById('modo-tiempo').checked;
    if (usarTiempo) {
        tiempoRestante = 300;
        document.getElementById('txt-tiempo').innerText = tiempoRestante;
        document.getElementById('display-tiempo').style.display = 'block';
        
        temporizador = setInterval(() => {
            if (juegoTerminado) {
                clearInterval(temporizador);
                return;
            }
            tiempoRestante--;
            document.getElementById('txt-tiempo').innerText = tiempoRestante;
            if (tiempoRestante <= 0) {
                clearInterval(temporizador);
                juegoTerminado = true;
                alert('⏰ ¡Se acabó el tiempo! Juego Terminado.');
                resolverJuego();
            }
        }, 1000);
    } else {
        document.getElementById('display-tiempo').style.display = 'none';
    }

    socket.emit('configurar_juego', { filas: filas, columnas: columnas, minas: minasTotales });
}

socket.on('tablero_creado', (data) => {
    const contenedor = document.getElementById('contenedor-tablero');
    contenedor.innerHTML = '';

    const grid = document.createElement('div');
    grid.className = 'tablero-grid';
    grid.style.gridTemplateColumns = `repeat(${data.columnas}, 40px)`;

    for (let f = 0; f < data.filas; f++) {
        for (let c = 0; c < data.columnas; c++) {
            const boton = document.createElement('button');
            boton.className = 'celda';
            boton.id = `celda-${f}-${c}`;
            
            boton.onclick = () => manejarClickCelda(f, c);
            
            boton.oncontextmenu = (e) => {
                e.preventDefault();
                manejarClicDerecho(f, c);
            };
            
            grid.appendChild(boton);
        }
    }
    contenedor.appendChild(grid);
});

function manejarClickCelda(f, c) {
    if (juegoTerminado) return;
    const celda = document.getElementById(`celda-${f}-${c}`);
    if (celda.classList.contains('revelada') || celda.classList.contains('bandera')) return;

    socket.emit('click_celda', { fila: f, columna: c });
}

function manejarClicDerecho(f, c) {
    if (juegoTerminado) return;
    const celda = document.getElementById(`celda-${f}-${c}`);
    if (celda.classList.contains('revelada')) return;

    if (!celda.classList.contains('bandera')) {
        celda.classList.add('bandera');
        celda.innerText = '🚩';
        banderasColocadas++;
    } else {
        celda.classList.remove('bandera');
        celda.innerText = '';
        banderasColocadas--;
    }

    document.getElementById('txt-minas-restantes').innerText = minasTotales - banderasColocadas;
}

socket.on('resultado_click', (data) => {
    data.celdas_a_revelar.forEach(item => {
        const targetCelda = document.getElementById(`celda-${item.fila}-${item.columna}`);
        if (targetCelda) {
            if (targetCelda.classList.contains('bandera')) {
                targetCelda.classList.remove('bandera');
                banderasColocadas--;
                document.getElementById('txt-minas-restantes').innerText = minasTotales - banderasColocadas;
            }
            targetCelda.classList.add('revelada');
            if (item.valor > 0) {
                targetCelda.innerText = item.valor;
                if (item.valor === 1) targetCelda.style.color = 'blue';
                else if (item.valor === 2) targetCelda.style.color = 'green';
                else targetCelda.style.color = 'red';
            }
        }
    });

    if (data.evento === 'GAME_OVER') {
        juegoTerminado = true;
        clearInterval(temporizador);
        alert('💥 ¡BOOM! Has pisado una mina. Juego Terminado.');
        resolverJuego();
    }
});

function resolverJuego() {
    socket.emit('solicitar_resolucion');
}

socket.on('juego_resuelto', (data) => {
    clearInterval(temporizador);
    data.minas.forEach(mina => {
        const celdaMina = document.getElementById('celda-' + mina[0] + '-' + mina[1]);
        if (celdaMina) {
            celdaMina.classList.remove('bandera');
            celdaMina.classList.add('mina');
            celdaMina.innerText = '💣';
        }
    });
    juegoTerminado = true;
});
