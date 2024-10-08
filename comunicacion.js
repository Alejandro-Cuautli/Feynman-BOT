const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const amqp = require('amqplib/callback_api');

const RABBIT_USER = 'guest';
const RABBIT_PASSWORD = 'guest';
const RABBIT_HOST = 'localhost';

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys');

    const startSocket = () => {
        const sock = makeWASocket({
            auth: state,
            printQRInTerminal: true
        });

        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect } = update;
            if (connection === 'close') {
                const statusCode = (lastDisconnect?.error)?.output?.statusCode;
                const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
                console.error('Conexión cerrada:', lastDisconnect?.error);
                if (shouldReconnect) {
                    console.log('Intentando reconectar...');
                    setTimeout(() => startSocket(), 5000);  // Agregar una pausa antes de intentar reconectar
                } else {
                    console.log('Error 401: Necesita volver a escanear el QR.');
                }
            } else if (connection === 'open') {
                console.log('Conectado a WhatsApp');
                receiveFromRabbitMQ(sock);
            }
        });

        // Manejar mensajes entrantes
        sock.ev.on('messages.upsert', async ({ messages }) => {
            try {
                for (const msg of messages) {
                    if (!msg.key.fromMe && msg.key.remoteJid.endsWith('@s.whatsapp.net')) {
                        // Obtener el número y el mensaje del usuario
                        const numberId = msg.key.remoteJid; // 'number@s.whatsapp.net'
                        const number = numberId.split('@')[0];
                        let userMessage = '';

                        // Verificar si el mensaje tiene texto u otro contenido soportado
                        if (msg.message?.conversation) {
                            userMessage = msg.message.conversation;
                        } else if (msg.message?.extendedTextMessage?.text) {
                            userMessage = msg.message.extendedTextMessage.text;
                        } else if (msg.message?.imageMessage?.caption) {
                            userMessage = msg.message.imageMessage.caption;
                        } else {
                            userMessage = '[Tipo de mensaje no soportado]';
                            console.log(`Mensaje no soportado recibido de ${number}.`);
                            // Opcional: puedes decidir si quieres responder al usuario aquí
                        }

                        console.log(`Nuevo mensaje de ${number}: ${userMessage}`);
                        sendToRabbitMQ(number, userMessage);
                    }
                }
            } catch (error) {
                console.error('Error al procesar mensajes entrantes:', error);
            }
        });
    };

    startSocket();
}

function sendToRabbitMQ(number, userMessage) {
    const queueName = `chatbot_queue_Feynman`;
    amqp.connect(`amqp://${RABBIT_USER}:${RABBIT_PASSWORD}@${RABBIT_HOST}`, (error0, connection) => {
        if (error0) {
            console.error('Conexión a RabbitMQ fallida:', error0.message);
            return;
        }
        console.log('Conexión exitosa al servidor RabbitMQ para enviar mensajes.');

        connection.createChannel((error1, channel) => {
            if (error1) {
                console.error('Fallo al crear el canal:', error1.message);
                return;
            }
            console.log('Canal creado exitosamente para enviar mensajes.');

            const message = JSON.stringify({ number, userMessage });
            channel.assertQueue(queueName, { durable: false });
            channel.sendToQueue(queueName, Buffer.from(message));
            console.log(`Mensaje enviado a RabbitMQ: ${message}`);
        });

        // Cerrar la conexión después de un tiempo para asegurar que el mensaje se envió
        setTimeout(() => {
            connection.close();
            console.log('Conexión a RabbitMQ cerrada después de enviar el mensaje.');
        }, 2000);
    });
}

function receiveFromRabbitMQ(sock) {
    const queueName = 'chatbot_queue_regreso';
    amqp.connect(`amqp://${RABBIT_USER}:${RABBIT_PASSWORD}@${RABBIT_HOST}`, (error0, connection) => {
        if (error0) {
            console.error('Conexión a RabbitMQ fallida:', error0.message);
            return;
        }
        console.log('Conexión exitosa al servidor RabbitMQ para recibir mensajes.');

        connection.createChannel((error1, channel) => {
            if (error1) {
                console.error('Fallo al crear el canal:', error1.message);
                return;
            }
            console.log('Canal creado exitosamente para recibir mensajes.');

            channel.assertQueue(queueName, { durable: true });
            channel.prefetch(1); // Procesar un mensaje a la vez para reducir el riesgo de sobrecarga
            channel.consume(queueName, async (msg) => {
                if (msg !== null) {
                    try {
                        const parsedMessage = JSON.parse(msg.content.toString());
                        const { number, response } = parsedMessage;

                        if (response) {
                            console.log(`Respuesta recibida para ${number}: ${response}`);
                            await sock.sendMessage(`${number}@s.whatsapp.net`, { text: response });
                        } else {
                            console.error('Error: El mensaje recibido no contiene una respuesta.');
                        }
                    } catch (e) {
                        console.error('Error al parsear el mensaje:', e.message);
                    }
                    channel.ack(msg);
                }
            });
        });
    });
}

connectToWhatsApp();
