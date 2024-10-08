const { default: makeWASocket, useMultiFileAuthState } = require('@whiskeysockets/baileys');

const TEST_NUMBER = '5212228345539';

async function sendTestMessage() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys');

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: true
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection } = update;
        if (connection === 'open') {
            console.log('Conectado a WhatsApp');
            sock.sendMessage(`${TEST_NUMBER}@s.whatsapp.net`, { text: 'Hola mundo' }).then(() => {
                console.log('Mensaje enviado a través de WhatsApp');
                sock.end();
            }).catch((err) => {
                console.error('Error al enviar el mensaje:', err);
            });
        }
    });
}

sendTestMessage();