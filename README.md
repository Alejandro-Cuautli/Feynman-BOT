# Instrucciones para Configurar y Ejecutar Feynman-BOT

A continuación se encuentran los pasos necesarios para configurar y ejecutar Feynman-BOT. Este bot utiliza Docker para correr RabbitMQ, Node.js para algunas funcionalidades, y Python para la parte principal del bot.

## Prerrequisitos

1. **Docker**: Asegúrate de tener Docker instalado para poder correr RabbitMQ.
2. **Node.js**: Necesitas tener instalado Node.js y npm (Node Package Manager).
3. **Python**: Asegúrate de tener instalado Python (versión 3.6 o superior).
4. **Git**: Asegúrate de haber clonado este repositorio.

## Configuración del Entorno

1. **Archivo .env**: Crea un archivo `.env` en la raíz del proyecto para almacenar variables de entorno sensibles. Asegúrate de que contenga la siguiente información:

   ```
    GROQ_API_KEY= ""
    LANGCHAIN_API_KEY= ""
    LANGCHAIN_ENDPOINT=""
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_PROJECT=  "Feynman-Rag"
    PINECONE_ENVIRONMENT=""
    OPENAI_API_KEY=""

   ``

2. **Dependencias de Node.js**: Instala las dependencias necesarias ejecutando el siguiente comando en la carpeta del proyecto:

   ```
   npm install  @whiskeysockets/baileys
   npm install qrcode-terminal
   npm install amqplib
   ```

## Instrucciones para Docker

1. **Correr RabbitMQ**: Ejecuta el siguiente comando para iniciar un contenedor de Docker con RabbitMQ:

   ```
   docker run -d --hostname feynman --name FeynmanRabit -p 5672:5672 -p 15672:15672 rabbitmq:3-management
   ```

## Ejecución del Bot

1. **Ejecutar el bot en Python**: Corre el bot principal escrito en Python ejecutando:

   ```
   python bot-feynman.py
   ```

2. **Ejecutar el archivo de comunicación en Node.js**: En otra terminal, ejecuta el siguiente comando para iniciar el script de comunicación en Node.js:

   ```
   node comunicacion.js
   ```

## Resumen de Comandos

1. **Clonar el repositorio**:
   ```
   git clone https://github.com/Alejandro-Cuautli/Feynman-BOT.git
   ```

2. **Ir a la carpeta del proyecto**:
   ```
   cd Feynman-BOT
   ```

3. **Crear el archivo .env** y agregar tus credenciales de RabbitMQ.

4. **Instalar dependencias de Node.js**:
   ```
   npm install
   ```

5. **Correr el contenedor de Docker para RabbitMQ**:
   ```
   docker run -d --hostname feynman --name FeynmanRabit -p 5672:5672 -p 15672:15672 rabbitmq:3-management
   ```

6. **Ejecutar el bot principal en Python**:
   ```
   python bot-feynman.py
   ```

7. **Ejecutar el script de Node.js**:
   ```
   node comunicacion.js
   ```

Con estos pasos, Feynman-BOT debería estar configurado y funcionando correctamente.

