from pymongo import MongoClient
import os
import torch
from ultralytics import YOLO
import base64
from PIL import Image
import glob

# Conectar a MongoDB
MONGO_URI = "mongodb://oai-nwdaf-database:27017"
client = MongoClient(MONGO_URI)
db = client.yolov8

# Obtener info del dataset montado
dataset_info = db.coco8.find_one({"dataset": "coco8"})
if not dataset_info:
    raise ValueError("No se encontró el dataset en MongoDB")

images_path = dataset_info["images_path"]

# Usar GPU si está disponible
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Usando dispositivo: {device}")

# Descargar modelo preentrenado si no está
model_path = "yolov8n.pt"
if not os.path.exists(model_path):
    print("Descargando modelo YOLOv8...")
    os.system(f"wget -O {model_path} https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt")

# Cargar modelo preentrenado
model = YOLO(model_path)
model.to(device)

# Buscar imágenes a inferir
valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
images_to_infer = []
for ext in valid_extensions:
    images_to_infer.extend(glob.glob(os.path.join(images_path, '**', f'*{ext}'), recursive=True))

print(f"Imágenes encontradas para inferencia: {images_to_infer}")

# Inferencia y almacenamiento
for img_path in images_to_infer:
    results = model(img_path)

    for result in results:
        boxes = result.boxes.xywh
        class_ids = result.boxes.cls
        confidences = result.boxes.conf
        names = result.names

        detections = []
        for i in range(len(boxes)):
            detections.append({
                "image": os.path.basename(img_path),
                "class_id": int(class_ids[i]),
                "class_name": names[int(class_ids[i])],
                "confidence": float(confidences[i]),
                "bbox": {
                    "x_center": float(boxes[i][0]),
                    "y_center": float(boxes[i][1]),
                    "width": float(boxes[i][2]),
                    "height": float(boxes[i][3]),
                }
            })

        if detections:
            db.detections.insert_many(detections)

            # Guardar imagen con predicción
            result_path = "/tmp/detected.jpg"
            result.save(filename=result_path)

            # Codificar imagen a base64
            with open(result_path, "rb") as image_file:
                img_base64 = base64.b64encode(image_file.read()).decode("utf-8")

            db.images.insert_one({
                "image_name": os.path.basename(img_path),
                "image_data": img_base64,
                "detections": detections
            })

print("Inferencia completada y resultados almacenados en MongoDB.")
