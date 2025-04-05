#!/bin/bash

SBI_URL="http://192.168.70.158:8080"
INPUT_DIR="/images"
OUTPUT_DIR="/results"
MAX_RETRIES=10
SLEEP_BETWEEN_RETRIES=1

CONTAINERS="gnbsim-vpp oai-nwdaf-sbi oai-nwdaf-yolov8 oai-nwdaf-database"
RESOURCE_LOG="/results/resource_usage.log"

echo "Iniciando envío de imágenes desde $INPUT_DIR a $SBI_URL/upload"
mkdir -p "$OUTPUT_DIR"

#Pimera línea del log de recursos
echo -e "Timestamp\tImage\tContainer\tCPU%\tMemUsage" > "$RESOURCE_LOG"

total_time=0
count=0

for img in "$INPUT_DIR"/*.{jpg,jpeg,png}; do
    [ -e "$img" ] || continue
    filename=$(basename "$img")
    echo "Enviando: $filename"

    # Medición de recursos antes del envío
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    for c in $CONTAINERS; do
        docker stats --no-stream --format "$timestamp\t$filename\t{{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" $c >> "$RESOURCE_LOG"
    done

    base64data=$(base64 "$img")
    json=$(jq -n --arg name "$filename" --arg data "$base64data" \
        '{image_name: $name, image_data: $data}')

    start_time=$(date +%s%3N)

    response=$(curl -s -X POST "$SBI_URL/upload" \
        -H "Content-Type: application/json" \
        -d "$json")

    echo "Respuesta del servidor: $response"

    if [[ "$response" != *"éxito"* ]]; then
        echo "Fallo al subir $filename"
        continue
    fi

    echo "Esperando resultados para $filename..."
    attempt=0
    while [ $attempt -lt $MAX_RETRIES ]; do
        sleep $SLEEP_BETWEEN_RETRIES
        curl -s -f "$SBI_URL/images/$filename" --output "$OUTPUT_DIR/inferenced_$filename" && {
	    end_time=$(date +%s%3N)
	    duration=$((end_time - start_time))
            echo "Imagen inferida recibida: $filename. Duración del procesamiento: ${duration} ms"
	    total_time=$((total_time + duration))
	    count=$((count + 1))
            break
        }
        attempt=$((attempt+1))
    done

    if [ $attempt -eq $MAX_RETRIES ]; then
        echo " No se pudo recuperar imagen inferida para $filename después de $MAX_RETRIES intentos"
    fi
done

if [ $count -gt 0 ]; then
    average=$((total_time / count))
    echo "Tiempo promedio de inferencia para $count imágenes: ${average} ms"
else
    echo "No se pudo calcular el promedio, ninguna imagen fue inferida correctamente."
fi

echo "Envío finalizado. Entrando en modo escucha pasiva (pull)..."

# Escucha pasiva cada 30s para ver si hay resultados nuevos
while true; do
    for filename in "$INPUT_DIR"/*.{jpg,jpeg,png}; do
        [ -e "$filename" ] || continue
        base=$(basename "$filename")
        result_file="$OUTPUT_DIR/inferenced_$base"

        if [ ! -f "$result_file" ]; then
            echo "🕵️ Reintentando recuperar resultado para $base..."
            curl -s -f "$SBI_URL/images/$base" --output "$result_file" && \
                echo "Imagen inferida recibida en escucha: $base"
        fi
    done
    sleep 30
done
