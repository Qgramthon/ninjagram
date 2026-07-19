const express = require('express');
const http = require('http');
const fs = require('fs');
const path = require('path');
const {
    makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    makeCacheableSignalKeyStore,
    fetchLatestBaileysVersion
} = require('@whiskeysockets/baileys');
const pino = require('pino');
const QRCode = require('qrcode');

// ====== إعدادات ======
const PORT = 3000;
const SESSIONS_DIR = './wa_sessions';
const USERS_FILE = './wa_users.json';

if (!fs.existsSync(SESSIONS_DIR)) fs.mkdirSync(SESSIONS_DIR, { recursive: true });
if (!fs.existsSync(USERS_FILE)) fs.writeFileSync(USERS_FILE, '{}');

// ====== Express Server ======
const app = express();
const server = http.createServer(app);
app.use(express.json());

// ====== تخزين ======
const clients = new Map();
const qrCodes = new Map();
const statusMap = new Map();

// ====== أوامر الواتساب ======
const commands = {
    'بنغ': async (sock, msg) => {
        const start = Date.now();
        await sock.sendMessage(msg.key.remoteJid, { 
            text: '[NinjaWhats] Calculating...' 
        });
        const end = Date.now();
        await sock.sendMessage(msg.key.remoteJid, { 
            text: `[NinjaWhats] Ping: *${end - start}ms*` 
        });
    },
    
    'وقتي': async (sock, msg) => {
        const now = new Date();
        const time = now.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });
        await sock.sendMessage(msg.key.remoteJid, { text: `⏰ ${time}` });
    },
    
    'عريض': async (sock, msg, text) => {
        await sock.sendMessage(msg.key.remoteJid, { text: `*${text}*` });
    },
    
    'مائل': async (sock, msg, text) => {
        await sock.sendMessage(msg.key.remoteJid, { text: `_${text}_` });
    },
    
    'مشطوب': async (sock, msg, text) => {
        await sock.sendMessage(msg.key.remoteJid, { text: `~${text}~` });
    },
    
    'نيم': async (sock, msg, name) => {
        try {
            await sock.updateProfileName(name);
            await sock.sendMessage(msg.key.remoteJid, { text: '✅ Name updated' });
        } catch (e) {
            await sock.sendMessage(msg.key.remoteJid, { text: `❌ Error: ${e.message}` });
        }
    },
    
    'بايو': async (sock, msg, bio) => {
        try {
            await sock.updateProfileStatus(bio);
            await sock.sendMessage(msg.key.remoteJid, { text: '✅ Bio updated' });
        } catch (e) {
            await sock.sendMessage(msg.key.remoteJid, { text: `❌ Error: ${e.message}` });
        }
    },
    
    'انتحال': async (sock, msg, text) => {
        await sock.sendMessage(msg.key.remoteJid, { delete: msg.key });
        await sock.sendMessage(msg.key.remoteJid, { text });
    },
    
    'اوامر': async (sock, msg) => {
        await sock.sendMessage(msg.key.remoteJid, { 
            text: `╭━━━━[ *NinjaWhats* ]━━━━╮

*.بنغ* - Ping
*.وقتي* - Time
*.عريض* + text - Bold
*.مائل* + text - Italic
*.مشطوب* + text - Strike
*.نيم* + name - Change name
*.بايو* + bio - Change bio
*.انتحال* + text - Ghost
*.ايقاف* - Stop

╰━━━━━━━━━━━━━━━━━━╯`
        });
    },
    
    'ايقاف': async (sock, msg) => {
        await sock.sendMessage(msg.key.remoteJid, { text: '[NinjaWhats] Stopping...' });
        const userId = [...clients.entries()].find(([id, c]) => c === sock)?.[0];
        if (userId) {
            await sock.logout();
            clients.delete(userId);
            statusMap.delete(userId);
        }
    }
};

// ====== بدء جلسة واتساب ======
async function startWhatsApp(userId) {
    const sessionDir = path.join(SESSIONS_DIR, userId);
    if (!fs.existsSync(sessionDir)) fs.mkdirSync(sessionDir, { recursive: true });
    
    const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
    
    const sock = makeWASocket({
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, pino({ level: 'silent' })),
        },
        logger: pino({ level: 'silent' }),
        printQRInTerminal: false,
    });
    
    clients.set(userId, sock);
    statusMap.set(userId, 'connecting');
    
    sock.ev.on('creds.update', saveCreds);
    
    sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            qrCodes.set(userId, qr);
            statusMap.set(userId, 'qr_ready');
            console.log(`[WhatsApp] QR ready for ${userId}`);
        }
        
        if (connection === 'open') {
            statusMap.set(userId, 'connected');
            qrCodes.delete(userId);
            
            const users = JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'));
            users[userId] = {
                id: userId,
                name: sock.user?.name || 'Unknown',
                number: sock.user?.id?.split(':')[0] || 'Unknown',
                connectedAt: new Date().toISOString()
            };
            fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
            
            console.log(`[WhatsApp] ${userId} connected`);
        }
        
        if (connection === 'close') {
            const shouldReconnect = 
                lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
            
            if (shouldReconnect) {
                console.log(`[WhatsApp] Reconnecting ${userId}...`);
                setTimeout(() => startWhatsApp(userId), 3000);
            } else {
                clients.delete(userId);
                statusMap.delete(userId);
                qrCodes.delete(userId);
                
                const users = JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'));
                delete users[userId];
                fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
                
                console.log(`[WhatsApp] ${userId} logged out`);
            }
        }
    });
    
    // معالجة الرسائل
    sock.ev.on('messages.upsert', async ({ messages }) => {
        const msg = messages[0];
        if (!msg.message || !msg.key.fromMe) return;
        
        let text = '';
        if (msg.message.conversation) text = msg.message.conversation;
        if (msg.message.extendedTextMessage?.text) text = msg.message.extendedTextMessage.text;
        if (msg.message.imageMessage?.caption) text = msg.message.imageMessage.caption;
        
        if (!text.startsWith('.')) return;
        
        const args = text.slice(1).trim().split(' ');
        const cmd = args.shift().toLowerCase();
        
        if (commands[cmd]) {
            try {
                await commands[cmd](sock, msg, args.join(' '));
            } catch (error) {
                console.error(`[WhatsApp] Command error:`, error);
            }
        }
    });
    
    return sock;
}

// ====== API Routes ======

// بدء جلسة جديدة
app.post('/start', async (req, res) => {
    const { userId } = req.body;
    if (!userId) return res.status(400).json({ error: 'Missing userId' });
    
    try {
        await startWhatsApp(userId);
        res.json({ success: true, userId });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// الحصول على QR Code
app.get('/qr/:userId', async (req, res) => {
    const { userId } = req.params;
    const qr = qrCodes.get(userId);
    
    if (qr) {
        try {
            const qrImage = await QRCode.toDataURL(qr);
            res.json({ qr: qrImage, status: 'qr_ready' });
        } catch (error) {
            res.json({ status: 'generating' });
        }
    } else {
        const status = statusMap.get(userId);
        if (status === 'connected') {
            res.json({ status: 'connected' });
        } else {
            res.json({ status: 'waiting' });
        }
    }
});

// التحقق من الحالة
app.get('/status/:userId', (req, res) => {
    const { userId } = req.params;
    const status = statusMap.get(userId) || 'unknown';
    const users = JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'));
    
    res.json({ 
        status,
        user: users[userId] || null
    });
});

// إيقاف الجلسة
app.post('/stop', async (req, res) => {
    const { userId } = req.body;
    const client = clients.get(userId);
    
    if (client) {
        try {
            await client.logout();
            clients.delete(userId);
            statusMap.delete(userId);
            qrCodes.delete(userId);
            
            const users = JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'));
            delete users[userId];
            fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
            
            res.json({ success: true });
        } catch (error) {
            res.status(500).json({ error: error.message });
        }
    } else {
        res.json({ success: true, message: 'Already stopped' });
    }
});

// Health check
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        clients: clients.size,
        platform: 'whatsapp'
    });
});

// ====== تشغيل السيرفر ======
server.listen(PORT, () => {
    console.log(`[WhatsApp Server] Running on port ${PORT}`);
});

// ====== تحميل الجلسات القديمة ======
async function loadOldSessions() {
    if (!fs.existsSync(SESSIONS_DIR)) return;
    
    const dirs = fs.readdirSync(SESSIONS_DIR);
    for (const dir of dirs) {
        const sessionPath = path.join(SESSIONS_DIR, dir);
        if (fs.statSync(sessionPath).isDirectory()) {
            console.log(`[WhatsApp] Loading old session: ${dir}`);
            await startWhatsApp(dir);
        }
    }
}

loadOldSessions();
