from pymongo import MongoClient
import os
import torch
from ultralytics import YOLO
import base64
from PIL import Image
from io import BytesIO
import glob

# Conectar a MongoDB
MONGO_URI = "mongodb://oai-nwdaf-database:27017"
client = MongoClient(MONGO_URI)
db = client.yolov8
#dataset_info = db.coco8.find_one({"dataset": "coco8"})
dataset_info = db.brain.find_one({"dataset": "brain"})

if dataset_info:
    images_path = dataset_info["images_path"]
    labels_path = dataset_info["labels_path"]
else:
    raise ValueError("No se encontró el dataset en MongoDB")

# Verificar si CUDA está disponible
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Usando dispositivo: {device}")

# Descargar el modelo YOLOv8 si no está disponible
model_path = "yolov8n.pt"
if not os.path.exists(model_path):
    print("Descargando modelo YOLOv8...")
    os.system(f"wget -O {model_path} https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt")

# Cargar el modelo
model = YOLO(model_path)
model.to(device)

# Configurar el dataset para YOLOv8
#data_yaml = "/coco8/coco8.yaml"
data_yaml = "/brain/data.yaml"

# Entrenar el modelo con el dataset de MongoDB
print("Iniciando entrenamiento...")
model.train(data=data_yaml, epochs=10, imgsz=640, device=device)
print("Entrenamiento finalizado.")

# Inferencia en nuevas imágenes
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
        classes = result.names
        confidences = result.boxes.conf

        detections = []
        for i in range(len(boxes)):
            detection = {
                "image": os.path.basename(img_path),
                "class_id": classes[int(result.boxes.cls[i])],
                "class_name": classes[int(result.boxes.cls[i])],
                "confidence": confidences[i].item(),
                "bbox": {
                    "x_center": boxes[i][0].item(),
                    "y_center": boxes[i][1].item(),
                    "width": boxes[i][2].item(),
                    "height": boxes[i][3].item()
                }
            }
            detections.append(detection)

        db.detections.insert_many(detections)

        # Guardar imagen con bounding boxes
        result_path = "/tmp/detected.jpg"
        result.save(filename=result_path)

        # Codificar imagen resultante
        with open(result_path, "rb") as image_file:
            img_base64 = base64.b64encode(image_file.read()).decode("utf-8")

        image_document = {
            "image_name": os.path.basename(img_path),
            "image_data": img_base64,
            "detections": detections
        }
        db.images.insert_one(image_document)

print("Inferencia y almacenamiento en MongoDB completado.")
