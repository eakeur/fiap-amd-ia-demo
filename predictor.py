import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image
import io
import json
import pika
from minio import Minio
from pymongo import MongoClient
import time
from dotenv import load_dotenv
import os

# Carrega variáveis de ambiente de um arquivo .env
load_dotenv()

# Inicializa o cliente Minio para armazenamento de objetos
minio_client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False
)

# Inicializa o cliente MongoDB e seleciona o banco de dados e a coleção
mongo_client = MongoClient("mongodb://user:password@localhost:27017/")
db = mongo_client["fiap-ia"]
predictions_collection = db["predictions"]

# Inicializa a conexão RabbitMQ e declara a fila
rabbit_connection = pika.BlockingConnection(pika.ConnectionParameters(
    host="localhost",
    credentials=pika.PlainCredentials("user", "password")
))
channel = rabbit_connection.channel()
channel.queue_declare(queue="new.image.upload", durable=True)

# Define uma classe de Rede Neural Convolucional (CNN)
class CNN(nn.Module):
    def __init__(self):
        super(CNN, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(64 * 7 * 7, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = torch.relu(self.conv1(x))
        x = self.pool(x)
        x = torch.relu(self.conv2(x))
        x = self.pool(x)
        x = x.view(-1, 64 * 7 * 7)
        x = torch.relu(self.fc1(x))
        x = self.fc2(x)
        return x

# Define o dispositivo como GPU se disponível, caso contrário, CPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Carrega o modelo pré-treinado
model = CNN().to(device)
model.load_state_dict(torch.load("best_model.pth", map_location=device))
model.eval()

# Define o pipeline de transformação de imagem
transform_pipeline = transforms.Compose([
    transforms.Grayscale(num_output_channels=1),
    transforms.Resize((28, 28)),
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,))
])

# Define a função de callback para processar mensagens do RabbitMQ
def process_message(ch, method, properties, body):
    message = json.loads(body)
    file_key = message["Key"]
    file_name = file_key.split("/")[-1]
    file_id = file_name.split(".")[0]

    # Declara uma fila de status para o arquivo específico
    status_queue = f"status.{file_id}"
    channel.queue_declare(queue=status_queue, durable=True)

    # Envia mensagem de status inicial
    message_body = {
        "type": "STATUS",
        "message": "Iniciando o processo de classificação."
    }
    channel.basic_publish(exchange="", routing_key=status_queue, body=json.dumps(message_body))
    time.sleep(5)

    try:
        # Recupera a imagem do Minio
        response = minio_client.get_object("raw-images", file_name)
        image_data = response.read()
        image = Image.open(io.BytesIO(image_data)).convert("L")
    except Exception as e:
        print(str(e))
        return

    # Envia mensagem de status após carregar a imagem
    message_body = {
        "type": "STATUS",
        "message": "Imagem carregada com sucesso."
    }
    channel.basic_publish(exchange="", routing_key=status_queue, body=json.dumps(message_body))
    time.sleep(5)

    # Transforma a imagem em tensor
    image_tensor = transform_pipeline(image).unsqueeze(0).to(device)
    
    # Envia mensagem de status após normalizar a imagem
    message_body = {
        "type": "STATUS",
        "message": "Imagem normalizada com sucesso."
    }
    channel.basic_publish(exchange="", routing_key=status_queue, body=json.dumps(message_body))
    time.sleep(5)

    # Realiza a inferência com o modelo
    with torch.no_grad():
        outputs = model(image_tensor)
        probabilities = torch.softmax(outputs, dim=1)
        confidence, predicted = torch.max(probabilities, 1)
        digit = predicted.item()
        confidence_score = confidence.item() * 100
    print(f'imagem classificada - {digit} - com confiança de {confidence_score:.2f}%')

    # Envia mensagem de status após a classificação
    message_body = {
        "type": "STATUS",
        "message": "Classificação finalizada, processando resultado."
    }
    channel.basic_publish(exchange="", routing_key=status_queue, body=json.dumps(message_body))
    time.sleep(5)

    # Atualiza o MongoDB com o resultado da classificação
    data_updated = {
        "prediction": {
            "model_version": "1.0",
            "class": digit,
            "confidence": confidence_score
        },
        "status": "image-classified"
    }
    predictions_collection.update_one(
        {"file_id": file_id},
        {"$set": data_updated}
    )

    # Envia mensagem de resultado final
    message_body = {
        "type": "RESULT",
        "message": f"O modelo tem {confidence_score:.2f}% de confiança que o número desenhado foi o {digit}."
    }
    channel.basic_publish(exchange="", routing_key=status_queue, body=json.dumps(message_body))
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Inicia o consumo de mensagens do RabbitMQ
channel.basic_consume(queue="new.image.upload", on_message_callback=process_message)
print("Aguardando mensagens na fila 'new.image.upload'...")
channel.start_consuming()