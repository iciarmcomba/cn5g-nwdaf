import os
import torch
import base64
from io import BytesIO
from PIL import Image
import datetime
import time
import csv
from pymongo import MongoClient
from ultralytics import YOLO

# Conexión MongoDB
MONGO_URI = "mongodb://oai-nwdaf-database:27017"
client = MongoClient(MONGO_URI)
db = client.yolov8
pending_collection = db.pending_images
images_collection = db.images

# Ficheros CSV para guardar métricas
INFERENCE_CSV = "/results/inference_times.csv"
TOTAL_CSV = "/results/total_processing_times.csv"

# Crear carpeta de resultados si no existe
OUTPUT_DIR = "/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Crear CSVs si no existen
if not os.path.exists(INFERENCE_CSV):
    with open(INFERENCE_CSV, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Image", "Inference Time (ms)"])

if not os.path.exists(TOTAL_CSV):
    with open(TOTAL_CSV, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Image", "Total Processing Time (ms)"])

# Verificar CUDA
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Usando dispositivo: {device}")

# Cargar modelo YOLOv8
model_path = "yolov8l.pt"
if not os.path.exists(model_path):
    print("Descargando modelo YOLOv8...")
    os.system(f"wget -O {model_path} https://github.com/ultralytics/assets/releases/download/v8.3.0/{model_path}")
model = YOLO(model_path)
model.to(device)

# --- Procesar Imagen ---
def process_image(image_doc):
    processing_start = time.time()  # ⏱️ Empezar medición total

    image_name = image_doc["image_name"]
    image_data_base64 = image_doc["image_data"]
    img_bytes = base64.b64decode(image_data_base64)
    image = Image.open(BytesIO(img_bytes)).convert("RGB")

    temp_path = f"/tmp/{image_name}"
    image.save(temp_path)

    # Medir tiempo de inferencia
    inference_start = time.time()
    results = model(temp_path)
    inference_end = time.time()
    inference_elapsed_ms = round((inference_end - inference_start) * 1000, 2)

    # Guardar tiempo de inferencia
    with open(INFERENCE_CSV, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([image_name, inference_elapsed_ms])

    print(f"{image_name} inferida en {inference_elapsed_ms} ms")

    # Guardar resultados
    for result in results:
        boxes = result.boxes.xywh
        classes = result.names
        confidences = result.boxes.conf

        detections = []
        for i in range(len(boxes)):
            detection = {
                "image": image_name,
                "class_id": int(result.boxes.cls[i]),
                "class_name": classes[int(result.boxes.cls[i])],
                "confidence": float(confidences[i]),
                "bbox": {
                    "x_center": float(boxes[i][0]),
                    "y_center": float(boxes[i][1]),
                    "width": float(boxes[i][2]),
                    "height": float(boxes[i][3])
                },
                "timestamp": datetime.datetime.utcnow()
            }
            detections.append(detection)

        result_path = f"/tmp/detected_{image_name}"
        result.save(filename=result_path)

        with open(result_path, "rb") as image_file:
            img_base64 = base64.b64encode(image_file.read()).decode("utf-8")

        image_document = {
            "image_name": image_name,
            "image_data": img_base64,
            "detections": detections,
            "timestamp": datetime.datetime.utcnow()
        }
        images_collection.insert_one(image_document)

    processing_end = time.time()
    total_elapsed_ms = round((processing_end - processing_start) * 1000, 2)

    # Guardar tiempo total
    with open(TOTAL_CSV, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([image_name, total_elapsed_ms])

    print(f"{image_name} procesada completamente en {total_elapsed_ms} ms")

    os.remove(temp_path)
    os.remove(result_path)

# --- Bucle Principal ---
def main_loop():
    print("Esperando nuevas imágenes...")
    while True:
        pending_images = list(pending_collection.find())
        if pending_images:
            print(f"Nuevas imágenes encontradas: {len(pending_images)}")
        for image_doc in pending_images:
            try:
                print(f"Procesando {image_doc['image_name']}")
                process_image(image_doc)
                pending_collection.delete_one({"_id": image_doc["_id"]})
            except Exception as e:
                print(f"Error procesando {image_doc.get('image_name', 'N/A')}: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
