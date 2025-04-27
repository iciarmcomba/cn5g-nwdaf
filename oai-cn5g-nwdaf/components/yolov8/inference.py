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
INFERENCE_CSV = "/results/inference_times.csv"

# Crear carpeta de resultados si no existe
OUTPUT_DIR = "/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Crear CSV si no existe
if not os.path.exists(INFERENCE_CSV):
    with open(INFERENCE_CSV, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Image", "Inference Time (ms)"])

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
    image_name = image_doc["image_name"]
    image_data_base64 = image_doc["image_data"]
    img_bytes = base64.b64decode(image_data_base64)
    image = Image.open(BytesIO(img_bytes)).convert("RGB")

    temp_path = f"/tmp/{image_name}"
    image.save(temp_path)

    # Medir tiempo de inferencia
    start_time = time.time()
    results = model(temp_path)
    end_time = time.time()
    elapsed_ms = round((end_time - start_time) * 1000, 4)

    # Guardar tiempo en CSV
    with open(INFERENCE_CSV, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([image_name, elapsed_ms])

    print(f"{image_name} inferida en {elapsed_ms} ms")

    # Guardar resultado procesado
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
