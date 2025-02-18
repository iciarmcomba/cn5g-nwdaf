from pymongo import MongoClient
import os
import torch
from ultralytics import YOLO

# Conectar a MongoDB
MONGO_URI = "mongodb://oai-nwdaf-database:27017"
client = MongoClient(MONGO_URI)
db = client.yolov8
dataset_info = db.coco8.find_one({"dataset": "coco8"})

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
#data_yaml = os.path.join(images_path, "coco8.yaml")
data_yaml = "/coco8/coco8.yaml"

# Entrenar el modelo con el dataset de MongoDB
print("Iniciando entrenamiento...")
model.train(data=data_yaml, epochs=10, imgsz=640, device=device)

print("Entrenamiento finalizado.")
