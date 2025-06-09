#!/bin/bash

CONTAINER="gnbsim-vpp"
OUTPUT_FILE="/home/netcom/oai-cn5g-fed/inferenced-results/resource_usage.csv"
MONITOR_STOP_FILE="/home/netcom/oai-cn5g-fed/inferenced-results/.monitor_stop"
INTERVAL=1

echo "Esperando a que el contenedor $CONTAINER esté disponible..."

# Esperar hasta que el contenedor exista
while ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; do
    sleep 1
done

# Esperar hasta que el contenedor esté en estado 'running'
while [ "$(docker inspect -f '{{.State.Running}}' $CONTAINER 2>/dev/null)" != "true" ]; do
    sleep 1
done

# Eliminar archivo de parada si existe para evitar salida temprana
rm -f "$MONITOR_STOP_FILE"

echo "Contenedor $CONTAINER en ejecución. Comenzando monitorización..."

# Encabezado del CSV
echo "Timestamp,CPU %,MemUsage,MemLimit,Mem %,NetIO,BlockIO,PIDs" > "$OUTPUT_FILE"

# Bucle de monitorización
while [ "$(docker inspect -f '{{.State.Running}}' $CONTAINER)" == "true" ]; do
    if [ -f "$MONITOR_STOP_FILE" ]; then
        echo "Archivo de parada detectado. Finalizando monitoreo..."
        break
    fi

    docker stats --no-stream --format \
    "{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}" \
    "$CONTAINER" | while IFS=',' read -r cpu mem memperc netio blockio pids; do
        ts=$(date +%Y-%m-%dT%H:%M:%S)
        usage=$(echo "$mem" | awk -F'/' '{print $1}' | xargs)
        limit=$(echo "$mem" | awk -F'/' '{print $2}' | xargs)
        echo "$ts,$cpu,$usage,$limit,$memperc,$netio,$blockio,$pids" >> "$OUTPUT_FILE"
    done

    sleep $INTERVAL
done

echo "Monitorización finalizada. Resultados guardados en $OUTPUT_FILE"
