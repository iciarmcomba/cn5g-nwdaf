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
    echo "Image,UploadDuration(ms),DownloadDuration(ms),TotalProcessingTime(ms)" > "$PROCESSING_CSV"
fi

for img in "$INPUT_DIR"/*.{jpg,jpeg,png}; do
    [ -e "$img" ] || continue
    filename=$(basename "$img")
    echo "Enviando: $filename"

    base64data=$(base64 "$img")
    json=$(jq -n --arg name "$filename" --arg data "$base64data" \
        '{image_name: $name, image_data: $data}')

    upload_start=$(date +%s.%N)

    response=$(curl -s -X POST "$SBI_URL/upload" \
        -H "Content-Type: application/json" \
        -d "$json")

    upload_end=$(date +%s.%N)

    upload_duration=$(awk "BEGIN {print ($upload_end - $upload_start) * 1000}")
    upload_duration_ms=$(printf "%.4f" "$upload_duration")

    echo "Upload duration: ${upload_duration_ms} ms"

    if [[ "$response" != *"éxito"* ]]; then
        echo "Fallo al subir $filename"
        continue
    fi

    echo "Esperando resultados para $filename..."
    attempt=0
    while [ $attempt -lt $MAX_RETRIES ]; do
        sleep $SLEEP_BETWEEN_RETRIES

        download_start=$(date +%s.%N)

        curl -s -f "$SBI_URL/images/$filename" --output "$OUTPUT_DIR/inferenced_$filename" && {
            download_end=$(date +%s.%N)
            download_duration=$(awk "BEGIN {print ($download_end - $download_start) * 1000}")
            download_duration_ms=$(printf "%.4f" "$download_duration")

            total_duration=$(awk "BEGIN {print ($download_end - $upload_start) * 1000}")
            total_duration_ms=$(printf "%.4f" "$total_duration")

            echo "Download duration: ${download_duration_ms} ms"
            echo "Total processing duration: ${total_duration_ms} ms"

            echo "$filename,$upload_duration_ms,$download_duration_ms,$total_duration_ms" >> "$PROCESSING_CSV"
            break
        }

        attempt=$((attempt+1))
    done

    if [ $attempt -eq $MAX_RETRIES ]; then
        echo "No se pudo recuperar imagen inferida para $filename después de $MAX_RETRIES intentos"
    fi
done

echo "Envío finalizado."
