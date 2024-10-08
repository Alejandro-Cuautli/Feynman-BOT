# Dockerfile Unificado

# Etapa 1: Configuración de RabbitMQ
FROM rabbitmq:3-management as rabbitmq

# Etapa 2: Configuración para Node.js y Python
FROM node:16 as app

# Instalar Python en la imagen Node.js
RUN apt-get update && apt-get install -y python3 python3-pip

# Crear directorio de trabajo
WORKDIR /usr/src/app

# Copiar el archivo package.json e instalar dependencias para Node.js
COPY package*.json ./
RUN npm install

# Copiar el archivo requirements.txt e instalar dependencias para Python
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copiar todo el código de la aplicación al contenedor
COPY . .

# Comando para iniciar RabbitMQ en segundo plano y luego ejecutar los scripts de Python y JavaScript
CMD rabbitmq-server -detached && \
    sleep 10 && \ 
    python3 Bot-feynman.py && \
    node comunicacion.js
