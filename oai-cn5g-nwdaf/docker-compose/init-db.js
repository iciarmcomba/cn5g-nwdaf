// Conectamos directamente a la base de datos yolov8
db = db.getSiblingDB('yolov8');

// Insertamos el conjunto de datos
//db.coco8.insertMany([
//  { "dataset": "coco8", "images_path": "/coco8/images", "labels_path": "/coco8/labels" }
//]);

db["brain-tumor"].insertOne({
  dataset: "brain-tumor",
  images_path: "/brain-tumor/train/images",
  labels_path: "/brain-tumor/train/labels"
});
