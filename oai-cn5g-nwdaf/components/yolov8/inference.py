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
data_yaml = "/coco8/coco8.yaml"

# Entrenar el modelo con el dataset de MongoDB
print("Iniciando entrenamiento...")
model.train(data=data_yaml, epochs=10, imgsz=640, device=device)
print("Entrenamiento finalizado.")

# Inferencia en nuevas imágenes
# Filtrar solo las imágenes con extensiones válidas
valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
images_to_infer = [f for f in os.listdir(images_path) if os.path.splitext(f)[1].lower() in valid_extensions]
#images_to_infer = [f for f in os.listdir(images_path) if os.path.splitext(f)[1].lower() in valid_extensions]
images_to_infer = []

for ext in valid_extensions:
    images_to_infer.extend(glob.glob(os.path.join(images_path, '**', f'*{ext}'), recursive=True))

print(f"Imágenes encontradas para inferencia: {images_to_infer}")  # DEPURACIÓN

# Para cada imagen en la carpeta de imágenes, realizar la inferencia y almacenar los resultados
for img_name in images_to_infer:
    img_path = os.path.join(images_path, img_name)

    # Realizar la inferencia
    results = model(img_path)  # Resultados de la inferencia

    # Iterar sobre los resultados para cada imagen
    for result in results:
        # Obtener las predicciones de las cajas delimitadoras
        boxes = result.boxes.xywh  # Obtener las cajas como coordenadas [x_center, y_center, width, height]
        classes = result.names  # Clases detectadas
        confidences = result.boxes.conf  # Confianza de la predicción

        # Preparar la información para insertar en MongoDB
        detections = []
        for i in range(len(boxes)):
            detection = {
                "image": img_name,
                "class_id": classes[int(result.boxes.cls[i])],  # ID de la clase
                "class_name": classes[int(result.boxes.cls[i])],  # Nombre de la clase
                "confidence": confidences[i].item(),  # Confianza de la detección
                "bbox": {
                    "x_center": boxes[i][0].item(),
                    "y_center": boxes[i][1].item(),
                    "width": boxes[i][2].item(),
                    "height": boxes[i][3].item()
                }
            }
            detections.append(detection)

        # Insertar los resultados en MongoDB
        db.detections.insert_many(detections)  # Guardamos todos los resultados de una vez

        # Opcional: Guardar la imagen como base64 en MongoDB
        image = Image.open(img_path)
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # Insertar la imagen codificada en base64 junto con las detecciones
        image_document = {
            "image_name": img_name,
            "image_data": img_base64,
            "detections": detections
        }
        db.images.insert_one(image_document)  # Guardamos la imagen y sus detecciones

print("Inferencia y almacenamiento en MongoDB completado.")
