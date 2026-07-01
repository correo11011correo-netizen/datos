#!/bin/bash

# Configuración
PORT=8000
PID_FILE="server.pid"
LOG_FILE="server.log"
VENV_BIN="./venv/bin/uvicorn"
APP_MODULE="app.api.main:app"

# Función para liberar el puerto
clear_port() {
    echo "Liberando puerto $PORT..."
    fuser -k $PORT/tcp 2>/dev/null || lsof -t -i:$PORT | xargs kill -9 2>/dev/null
}

start() {
    echo "Iniciando servidor en modo Hot Reload..."
    clear_port
    
    # Iniciar uvicorn en segundo plano usando nohup para persistencia
    nohup $VENV_BIN $APP_MODULE --host 0.0.0.0 --port $PORT --reload > $LOG_FILE 2>&1 &
    
    PID=$!
    echo $PID > $PID_FILE
    echo "Servidor iniciado con PID: $PID"
    echo "Logs disponibles en: $LOG_FILE"
    echo "Esperando a que el servidor responda..."
    
    # Esperar hasta que el servidor responda o timeout (10s)
    for i in {1..10}; do
        if curl -s "http://localhost:$PORT/api/status" > /dev/null; then
            echo "✅ Servidor online y respondiendo."
            return 0
        fi
        sleep 1
    done
    echo "⚠️ El servidor inició pero no responde en el puerto $PORT. Revisa $LOG_FILE"
}

stop() {
    echo "Deteniendo servidor..."
    if [ -f $PID_FILE ]; then
        PID=$(cat $PID_FILE)
        kill $PID 2>/dev/null
        rm $PID_FILE
        echo "Proceso $PID detenido."
    else
        echo "No se encontró archivo PID. Forzando cierre del puerto $PORT..."
        clear_port
    fi
}

status() {
    if [ -f $PID_FILE ] && ps -p $(cat $PID_FILE) > /dev/null; then
        echo "🟢 Servidor EJECUTÁNDOSE (PID: $(cat $PID_FILE))"
        curl -s "http://localhost:$PORT/api/status" | sed 's/^/  /'
    else
        echo "🔴 Servidor DETENIDO"
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    status) status ;;
    *) echo "Uso: $0 {start|stop|restart|status}" ;;
esac
