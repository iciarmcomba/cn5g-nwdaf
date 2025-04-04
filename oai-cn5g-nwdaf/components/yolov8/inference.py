import time

def main_loop():
    while True:
        pending_images = list(pending_collection.find())
        if not pending_images:
            print("⏳ Esperando imágenes...")
            time.sleep(5)
            continue

        print(f"🔍 {len(pending_images)} imágenes encontradas")

        for image_doc in pending_images:
            try:
                image_name = image_doc["image_name"]
                image_data_base64 = image_doc["image_data"]
                img_bytes = base64.b64decode(image_data_base64)
                image = Image.open(BytesIO(img_bytes)).convert("RGB")

                temp_path = f"/tmp/{image_name}"
                image.save(temp_path)

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

                pending_collection.delete_one({"_id": image_doc["_id"]})
                print(f"✅ Procesada y eliminada: {image_name}")

            except Exception as e:
                print(f"❌ Error procesando {image_doc.get('image_name')}: {e}")
                continue

if __name__ == "__main__":
    main_loop()
