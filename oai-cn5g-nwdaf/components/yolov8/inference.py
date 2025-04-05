from pymongo import MongoClient
import os
import torch
from ultralytics import YOLO
import base64
from io import BytesIO
from PIL import Image
import datetime
import time

# Conexión a MongoDB
MONGO_URI = "mongodb://oai-nwdaf-database:27017"
client = MongoClient(MONGO_URI)
db = client.yolov8

# Colecciones
pending_collection = db.pending_images
detections_collection = db.detections
images_collection = db.images

#Crear índices para mejorar el rendimiento de búsqueda
print("Verificando/creando índices en MongoDB...")
pending_collection.create_index("image_name")
images_collection.create_index("image_name")
detections_collection.create_index("image")
print("Índices asegurados.")

# Verificar si CUDA está disponible
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Usando dispositivo: {device}")

# Cargar modelo preentrenado YOLOv8
model_path = "yolov8m.pt"
if not os.path.exists(model_path):
    print("Descargando modelo YOLOv8...")
    os.system(f"wget -O {model_path} https://github.com/ultralytics/assets/releases/download/v8.3.0/{model_path}")

model = YOLO(model_path)
model.to(device)

# Función de procesamiento de una imagen
def process_image(image_doc):
    image_name = image_doc["image_name"]
    image_data_base64 = image_doc["image_data"]
    img_bytes = base64.b64decode(image_data_base64)
    image = Image.open(BytesIO(img_bytes)).convert("RGB")

    # Guardar temporalmente la imagen
    temp_path = f"/tmp/{image_name}"
    image.save(temp_path)

    # Inferencia
    results = model(temp_path)

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

        if detections:
            detections_collection.insert_many(detections)

        # Guardar imagen con bounding boxes
        result_path = f"/tmp/detected_{image_name}"
        result.save(filename=result_path)

        # Codificar imagen resultante
        with open(result_path, "rb") as image_file:
            img_base64 = base64.b64encode(image_file.read()).decode("utf-8")

        image_document = {
            "image_name": image_name,
            "image_data": img_base64,
            "detections": detections,
            "timestamp": datetime.datetime.utcnow()
        }
        images_collection.insert_one(image_document)

        # Limpiar archivos temporales
        os.remove(temp_path)
        os.remove(result_path)

# Bucle watchdog para escuchar nuevas imágenes
def main_loop():
    print("Esperando nuevas imágenes...")
    while True:
        pending_images = list(pending_collection.find())
        if pending_images:
            print(f"Nuevas imágenes encontradas: {len(pending_images)}")
        for image_doc in pending_images:
            try:
                print(f"Procesando imagen: {image_doc['image_name']}")
                process_image(image_doc)
                pending_collection.delete_one({"_id": image_doc["_id"]})
                print(f"Imagen {image_doc['image_name']} procesada con éxito.")
            except Exception as e:
                print(f"Error procesando {image_doc.get('image_name', 'N/A')}: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
