#!/bin/bash

SBI_URL="http://192.168.70.158:8080"
INPUT_DIR="/images"
OUTPUT_DIR="/results"
MAX_RETRIES=10
SLEEP_BETWEEN_RETRIES=1
PROCESSING_CSV="$OUTPUT_DIR/processing_times.csv"

echo "Iniciando envío de imágenes desde $INPUT_DIR a $SBI_URL/upload"
mkdir -p "$OUTPUT_DIR"

# Crear CSV con encabezado si no existe
if [ ! -f "$PROCESSING_CSV" ]; then
    echo "Image,StartTime,EndTime,ProcessingTime(s)" > "$PROCESSING_CSV"
fi

for img in "$INPUT_DIR"/*.{jpg,jpeg,png}; do
    [ -e "$img" ] || continue
    filename=$(basename "$img")
    echo "Enviando: $filename"

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
	    echo "$filename,$start_time,$end_time,$duration" >> "$PROCESSING_CSV"
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

echo "done" > /results/.monitor_stop

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
