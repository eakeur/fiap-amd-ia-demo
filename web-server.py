from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
from PIL import Image
import io
from minio import Minio
from minio.error import S3Error
from datetime import timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Carrega variáveis de ambiente de um arquivo .env
load_dotenv()

# Inicializa a aplicação FastAPI
app = FastAPI()

# Configura o middleware CORS para permitir todas as origens
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa o cliente MongoDB e seleciona o banco de dados e a coleção
mongo_client = MongoClient("mongodb://user:password@localhost:27017/")
db = mongo_client["fiap-ia"]
predictions_collection = db["predictions"]

# Inicializa o cliente Minio para armazenamento de objetos
minio_client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False
)

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """
    Endpoint para receber a imagem enviada.
    """
    # Gera um ID único para o arquivo
    file_id = str(uuid.uuid4())
    file_name = f"{file_id}.png"

    # Lê o conteúdo do arquivo e converte para escala de cinza
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("L")
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    try:
        # Faz upload da imagem para o Minio
        minio_client.put_object(
            "raw-images",
            file_name,
            data=image_bytes,
            length=image_bytes.getbuffer().nbytes,
            content_type="image/png"
        )
    except S3Error as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    # Insere um documento no MongoDB com o status da imagem
    predictions_collection.insert_one({
        "file_id": file_id,
        "file_name": file_name,
        "prediction" : {
            "model_version": "",
            "class": "",
            "confidence": 0.0
        },
        "status": "image-uploaded"
    })

    return JSONResponse({"message": "Imagem recebida e processamento iniciado", "file_id" : file_id, "file_name": file_name})

@app.get("/get-presigned")
async def get_presigned():
    """
    Gera uma URL pré-assinada para upload no MinIO.
    """
    # Gera um ID único para o arquivo
    file_id = str(uuid.uuid4())
    file_name = f"{file_id}.png"

    try:
        # Gera a URL pré-assinada
        presigned_url = minio_client.presigned_put_object(
            "raw-images",
            file_name,
            expires=timedelta(minutes=10),
        )
    except S3Error as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    
    try:
        # Insere um documento no MongoDB com o status de espera de upload
        predictions_collection.insert_one({
            "file_id": file_id,
            "file_name": file_name,
            "status": "waiting-upload"
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse({"url": presigned_url, "file_id": file_id})

if __name__ == "__main__":
    import uvicorn
    # Executa a aplicação FastAPI usando Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)