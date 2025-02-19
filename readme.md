# Lab | Exemplo - Desenhe um Número

## Requisitos
Para executar este laboratório, é aconselhável ter o Python na versão **3.12 ou superior** instalado no sistema.

## Configuração do Ambiente
Para garantir um ambiente isolado e organizado, utilizaremos o **virtualenv** para criar um ambiente virtual.

### Criando um Ambiente Virtual
Caso ainda não tenha o **virtualenv** instalado, execute o seguinte comando para instalá-lo:

```sh
pip install virtualenv
```

Agora, crie e ative o ambiente virtual:

**Linux/macOS:**
```sh
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```sh
python -m venv venv
venv\Scripts\activate
```

### Instalando Dependências
As dependências do projeto estão listadas no arquivo `requirements.txt`. Para instalá-las, execute o seguinte comando:

```sh
pip install -r requirements.txt
```

## Executando com Docker
O projeto conta com um **docker-compose** para facilitar a inicialização dos containers necessários.

Certifique-se de ter o **Docker** e o **Docker Compose** instalados. Para iniciar os containers, execute:

```sh
docker-compose up -d
```

Caso queira verificar os logs dos containers, utilize:

```sh
docker-compose logs -f
```

Para parar os containers, execute:

```sh
docker-compose down
```

Agora, seu ambiente está pronto para iniciar o laboratório!

## Configuração Inicial do Ambiente

Antes de prosseguir, é necessário configurar o RabbitMQ para criar uma **exchange** e uma **fila**, permitindo o recebimento dos eventos do tipo **NovaImagemArmazenada**.

### Acessando o RabbitMQ
1. Abra o painel de administração do RabbitMQ no navegador:
   [http://localhost:15672/](http://localhost:15672/)
2. Insira as credenciais de acesso:
   - **Usuário**: `user`
   - **Senha**: `password`
3. Após o login, prossiga com a criação da **exchange** e da **fila** conforme necessário.

![image](https://github.com/user-attachments/assets/a3679f95-30dc-4995-adf2-a8680218e2bb)

### Configurando a fila

1. Navegue para a aba `Queues and Streams`.
2. Crie uma nova fila com os dados:
  - **Name**: `new.image.upload`
  - **Durability**: `Durable`
3. Clique em `Add queue`

![image](https://github.com/user-attachments/assets/0c1f7ac1-76de-4661-a40b-ffebb0572a20)

Se tudo ocorreu da maneira correta você deverá ver a nova fila:

![image](https://github.com/user-attachments/assets/325fdd04-19ce-4878-9c4e-d5b76b228577)


### Configurando a exchange

1. Navegue para a aba `Exchanges`.
2. Crie uma nova fila com os dados:
  - **Name**: `public.images`
  - **Type**: `direct`
  - **Durability**: `Durable`
3. Clique em `Add exchange`

![image](https://github.com/user-attachments/assets/6ec9b966-ba68-4ba1-8ead-cdb9fc790b80)

Se tudo ocorreu da maneira correta você deverá ver a nova exchange:

![image](https://github.com/user-attachments/assets/fb8b2e8e-72ea-4bbc-acb8-73a56c2edcf9)

### Criando a bind para a fila

1. Clique no nome da nova exchange criada `public.images`.
2. No formulário, insira os seguintes campos:
  - **To queue**: `new.image.upload`
  - **Routing key**: `client.put.new.image`
3. Clique em `Bind`

![image](https://github.com/user-attachments/assets/a6dd7902-751b-422b-a658-04af183867de)

Se tudo ocorreu da maneira correta você deverá ver a nova bind:

![image](https://github.com/user-attachments/assets/f5086fd6-c379-47c5-8647-c25b74c111c0)


### Acessando o MinIO

1. Abra o painel de administração do MinIO no navegador:  
   [http://localhost:9001](http://localhost:9001)  
2. Insira suas credenciais:
   - **Usuário**: `user`
   - **Senha**: `password`


![image](https://github.com/user-attachments/assets/cd567a31-d2de-4ee3-b3c1-0b6841f8e855)

### Criando um Bucket

1. No painel do MinIO, clique em **Buckets** no menu lateral.
2. Clique em **Create Bucket**.  
3. Escolha um nome para o bucket:  
   - **Bucket Name**: `raw-images`
4. Clique em **Create Bucket** para confirmar.

![image](https://github.com/user-attachments/assets/6b39eade-36c8-418c-aa5b-19996979918b)

O novo bucket deverá ser listado:

![image](https://github.com/user-attachments/assets/d2d5cab5-11c6-496d-8632-bd5adb0ac331)

### Criando um Evento para Notificações

1. No painel do MinIO, clique em **Events** no menu lateral.
2. Clique em **Add Event Destination**.  
3. Escolha a fila AMQP
4. Configure o formulário com as informações:
  - **Identifier**: `event-new-image`
  - **URL**: `amqp://user:password@rabbitmq-lab:5672`
  - **Exchange**: `public.images`
  - **Exchange Type**: `direct`
  - **Routing Key**: `client.put.new.image`
  - **Durable**: `ON`
  - **Mandatory**: `ON`
  - **Delivery Mode**: `2`
  - **Queue Directory**: `/`
5. Clique em **Save Event Destination**

![image](https://github.com/user-attachments/assets/a6669dc4-c26f-4497-adff-0b0c2ddb3d9f)

O MinIO precisará ser reiniciado, clique em **Restart** e aguarde. Após o término você deverá ver o evento listado:

![image](https://github.com/user-attachments/assets/e1697f8c-701f-43ad-bfa1-e39e262b67d1)

### Configurando o _trigger_ do evento

1. No painel do MinIO, clique em **Buckets** no menu lateral.
2. Clique no bucket `raw-images`.  
3. No menu lateral do bucket selecione **Events**:  
4. Clique em **Subscribe to Event**.

![image](https://github.com/user-attachments/assets/f08a887b-e4e9-4d30-b1be-4749eef1b433)

5. Configure o formulário com as informações:
  - **ARN**: `arn:minio:sqs::event-new-image:amqp`
  - **Sufix**: `*.png`
  - **Select Event**: `PUT - Object Uploaded`
7. Clique em **Save**.

![image](https://github.com/user-attachments/assets/2a5770d1-4e92-496f-9ab6-94de121ec985)

Com essa configuração, qualquer arquivo com a extenção png inserido no bucket deverá emitir o evento.

![image](https://github.com/user-attachments/assets/cd88af96-3359-4589-89d5-bf37db777ec9)
