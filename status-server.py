from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import pika
import asyncio
import json
import time

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

def get_rabbit_connection():
    """Cria uma nova conexão com o RabbitMQ."""
    return pika.BlockingConnection(pika.ConnectionParameters(
        host="localhost",
        credentials=pika.PlainCredentials("user", "password")
    ))

def get_rabbit_channel(connection):
    """Cria um novo canal no RabbitMQ a partir da conexão fornecida."""
    return connection.channel()

async def wait_for_queue(queue_name, timeout=30):
    """
    Aguarda até que a fila esteja disponível no RabbitMQ, verificando periodicamente.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            connection = get_rabbit_connection()
            channel = get_rabbit_channel(connection)
            channel.queue_declare(queue=queue_name, passive=True)
            channel.close()
            connection.close()
            return True
        except pika.exceptions.ChannelClosedByBroker:
            connection.close()
        except pika.exceptions.AMQPConnectionError:
            await asyncio.sleep(1)
            continue
        await asyncio.sleep(1)
    return False

async def event_generator(queue_name):
    # Cria uma conexão e um canal com o RabbitMQ
    connection = get_rabbit_connection()
    channel = get_rabbit_channel(connection)

    # Consome mensagens da fila especificada
    for method_frame, properties, body in channel.consume(queue_name, inactivity_timeout=100):
        if body:
            data = json.loads(body.decode())
            message = f"{data['type']} - {data['message']}"
            yield f"data: {message}\n\n"
            if data['type'] == "RESULT":
                channel.queue_delete(queue=queue_name)
                break
        await asyncio.sleep(1)

    # Fecha o canal e a conexão
    channel.close()
    connection.close()

@app.get("/status/{file_id}")
async def sse_endpoint(file_id: str):
    # Define o nome da fila de status
    queue_name = f"status.{file_id}"
    # Aguarda até que a fila esteja disponível
    queue_exists = await wait_for_queue(queue_name)
    if not queue_exists:
        raise HTTPException(status_code=404, detail=f"Fila {queue_name} não encontrada dentro do tempo limite.")

    # Retorna uma resposta de streaming com os eventos da fila
    return StreamingResponse(event_generator(queue_name), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # Executa a aplicação FastAPI usando Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
