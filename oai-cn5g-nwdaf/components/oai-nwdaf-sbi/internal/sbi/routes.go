package sbi

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"log"
	"net/http"
	"strings"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

// MongoDB Configuration
var mongoURI = "mongodb://192.168.74.156:27017"
var dbName = "yolov8"
var collectionName = "detections"

// ------------------------------------------------------------------------------
// Handler para obtener las detecciones desde MongoDB
func GetDetectionsHandler(w http.ResponseWriter, r *http.Request) {
	client, err := mongo.Connect(context.TODO(), options.Client().ApplyURI(mongoURI))
	if err != nil {
		http.Error(w, "Error conectando a MongoDB", http.StatusInternalServerError)
		log.Println("Error conectando a MongoDB:", err)
		return
	}
	defer client.Disconnect(context.TODO())

	collection := client.Database(dbName).Collection(collectionName)
	cursor, err := collection.Find(context.TODO(), bson.M{})
	if err != nil {
		http.Error(w, "Error consultando MongoDB", http.StatusInternalServerError)
		log.Println("Error consultando MongoDB:", err)
		return
	}
	defer cursor.Close(context.TODO())

	var detections []bson.M
	if err = cursor.All(context.TODO(), &detections); err != nil {
		http.Error(w, "Error leyendo los resultados", http.StatusInternalServerError)
		log.Println("Error leyendo los resultados:", err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(detections)
}

// ------------------------------------------------------------------------------
// Handler para servir imágenes detectadas desde MongoDB
func GetImageHandler(w http.ResponseWriter, r *http.Request) {
	imageName := strings.TrimPrefix(r.URL.Path, "/images/") // Extrae nombre de imagen

	client, err := mongo.Connect(context.TODO(), options.Client().ApplyURI(mongoURI))
	if err != nil {
		http.Error(w, "Error conectando a MongoDB", http.StatusInternalServerError)
		log.Println("Error conectando a MongoDB:", err)
		return
	}
	defer client.Disconnect(context.TODO())

	collection := client.Database(dbName).Collection("images")

	// Buscar imagen que termine en el nombre solicitado
	filter := bson.M{
		"image_name": bson.M{
			"$regex":   imageName + "$",
			"$options": "i",
		},
	}

	var imgDoc bson.M
	err = collection.FindOne(context.TODO(), filter).Decode(&imgDoc)
	if err != nil {
		http.Error(w, "Imagen no encontrada", http.StatusNotFound)
		log.Println("Imagen no encontrada:", err)
		return
	}

	imgBase64, ok := imgDoc["image_data"].(string)
	if !ok {
		http.Error(w, "Imagen malformada en MongoDB", http.StatusInternalServerError)
		log.Println("Campo image_data no es string")
		return
	}

	imgBytes, err := base64.StdEncoding.DecodeString(imgBase64)
	if err != nil {
		http.Error(w, "Error decodificando la imagen", http.StatusInternalServerError)
		log.Println("Error base64:", err)
		return
	}

	w.Header().Set("Content-Type", "image/jpeg")
	w.WriteHeader(http.StatusOK)
	w.Write(imgBytes)
}

// ------------------------------------------------------------------------------
// NewRouter - crea el router para el servidor HTTP
func NewRouter() http.Handler {
	mux := http.NewServeMux()

	// Rutas ya existentes
	mux.HandleFunc(config.Amf.ApiRoute, storeAmfNotificationOnDB)
	mux.HandleFunc(config.Smf.ApiRoute, storeSmfNotificationOnDB)

	// Nuevas rutas para detección e imágenes
	mux.HandleFunc("/detections", GetDetectionsHandler)
	mux.HandleFunc("/images/", GetImageHandler)

	log.Println("Rutas registradas: /detections, /images/{image_name}")
	return mux
}
