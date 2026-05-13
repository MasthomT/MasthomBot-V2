require('dotenv').config({ path: '/home/thomas/masthom/BOT_V2/.env' });
const express = require('express');
const axios = require('axios');
const cors = require('cors');
const fs = require('fs');
const dotenv = require('dotenv');
const { OBSWebSocket } = require('obs-websocket-js');

// =================================================================
// 1. GESTION DU TOKEN TWITCH (LECTURE DYNAMIQUE DU .ENV)
// =================================================================
let HELIX_TOKEN = "";

function loadToken() {
    try {
        // Lecture directe du fichier physique pour contourner le cache de Node
        const fileContent = fs.readFileSync('/home/thomas/masthom/BOT_V2/.env');
        const envConfig = dotenv.parse(fileContent);
        
        const rawEnv = envConfig.TWITCH_OAUTH_TOKEN || "";
        const cleanToken = rawEnv.replace(/oauth:/i, "").replace(/['"\s]/g, "").trim();
        
        if (cleanToken && cleanToken !== HELIX_TOKEN) {
            console.log(`[Node Auth] 🚀 Succès : Nouveau Token Twitch chargé avec succès !`);
        }
        return cleanToken;
    } catch (err) {
        console.error(`[Node Auth] ❌ ERREUR lecture du fichier .env :`, err.message);
        return "";
    }
}

HELIX_TOKEN = loadToken();
// Vérification toutes les 2 minutes pour appliquer les changements presque en direct
setInterval(() => { HELIX_TOKEN = loadToken(); }, 2 * 60 * 1000);

// =================================================================
// 2. CONFIGURATION
// =================================================================
const CONFIG = {
    PORT: 3005,
    TWITCH_CLIENT_ID: process.env.TWITCH_CLIENT_ID,
    CHANNEL_NAME: (process.env.TWITCH_USERNAME || "masthom_").replace(/['"\s]/g, '').trim(),
    GQL_CLIENT_ID: 'kimne78kx3ncx6brgo4mv6wki5h1ko',
    OBS_ADDRESS: `ws://${process.env.OBS_HOST || '127.0.0.1'}:${process.env.OBS_PORT || '4455'}`,
    OBS_PASSWORD: process.env.OBS_PASSWORD,
    BRB_SCENE_NAME: 'ON BREAK'
};

let clients = [];
let shoutoutQueue = [];
let isProcessing = false;
let currentQueueItemTimer = null;

let currentScene = 'main';
let brbLoopActive = false;
let brbClipsPool = [];
let brbPlayedHistory = new Set();
let brbTimeout = null;
let gameCache = {};

const app = express();
const obs = new OBSWebSocket();

app.use(cors());
app.use(express.json());
app.use('/static/uploads', express.static('/home/thomas/masthom/BOT_V2/app/static/uploads'));
// =================================================================
// 3. CONNEXION OBS
// =================================================================
async function connectOBS() {
    try {
        await obs.connect(CONFIG.OBS_ADDRESS, CONFIG.OBS_PASSWORD);
        console.log(`🎬 [OBS] Connecté ! Surveillance de la scène "${CONFIG.BRB_SCENE_NAME}".`);
    } catch (error) {
        setTimeout(connectOBS, 30000);
    }
}

obs.on('CurrentProgramSceneChanged', data => {
    if (data.sceneName === CONFIG.BRB_SCENE_NAME) {
        if (!brbLoopActive) { 
            currentScene = 'brb'; 
            startBrbLoop(); 
            broadcast({ type: 'change_scene', scene: 'brb' }); 
        }
    } else {
        if (brbLoopActive) { 
            currentScene = 'main'; 
            stopBrbLoop(); 
            broadcast({ type: 'change_scene', scene: 'main' }); 
        }
    }
});

connectOBS();

// =================================================================
// 4. API TWITCH HELPERS
// =================================================================

function extractClipId(url) {
    if (!url) return null;
    let match = url.match(/clips\.twitch\.tv\/([\w-]+)/i);
    if (match) return match[1];
    match = url.match(/clip\/([\w-]+)/i);
    if (match) return match[1];
    if (!url.includes('/')) return url.trim();
    return null;
}

async function getUserInfo(identifier) {
    if (!identifier) return null;
    try {
        const cleanId = identifier.replace(/['"\s]/g, '').trim();
        const paramType = /^\d+$/.test(cleanId) ? 'id' : 'login';
        const resp = await axios.get(`https://api.twitch.tv/helix/users?${paramType}=${cleanId}`, {
            headers: { 'Client-ID': CONFIG.TWITCH_CLIENT_ID, 'Authorization': `Bearer ${HELIX_TOKEN}` }
        });
        return resp.data.data?.[0] || null;
    } catch (e) { 
        console.error(`❌ [API Twitch] getUserInfo a échoué pour ${identifier}. Token expiré ? (${e.message})`);
        return null; 
    }
}

async function getGameName(gameId) {
    if (!gameId) return "Just Chatting";
    if (gameCache[gameId]) return gameCache[gameId];
    try {
        const resp = await axios.get(`https://api.twitch.tv/helix/games?id=${gameId}`, {
            headers: { 'Client-ID': CONFIG.TWITCH_CLIENT_ID, 'Authorization': `Bearer ${HELIX_TOKEN}` }
        });
        const name = resp.data.data?.[0]?.name || "Just Chatting";
        gameCache[gameId] = name;
        return name;
    } catch (e) { return "Just Chatting"; }
}

async function getDirectMp4Url(slug) {
    try {
        const resp = await axios.post('https://gql.twitch.tv/gql', {
            operationName: "VideoAccessToken_Clip", variables: { slug: slug },
            extensions: { persistedQuery: { version: 1, sha256Hash: "36b89d2507fce29e5ca551df756d27c1cfe079e2609642b4390aa4c35796eb11" } }
        }, { headers: { 'Client-ID': CONFIG.GQL_CLIENT_ID } });
        const clipData = resp.data?.data?.clip;
        
        let selected = clipData.videoQualities.find(q => q.quality === '720p') 
                    || clipData.videoQualities.find(q => q.quality === '480p') 
                    || clipData.videoQualities[0];
                    
        return `${selected.sourceURL}?sig=${clipData.playbackAccessToken.signature}&token=${encodeURIComponent(clipData.playbackAccessToken.value)}`;
    } catch (e) { 
        console.error("❌ [GQL] Impossible d'extraire le MP4:", e.message);
        return null; 
    }
}

// =================================================================
// 5. SCANNER DE CLIPS
// =================================================================

async function findSmartClip(userId, mode, extraData) {
    try {
        const targetId = userId || (await getUserInfo(CONFIG.CHANNEL_NAME))?.id;
        if (!targetId) return null;
        const headers = { 'Client-ID': CONFIG.TWITCH_CLIENT_ID, 'Authorization': `Bearer ${HELIX_TOKEN}` };

        if (extraData?.slug) {
            const clipId = extractClipId(extraData.slug);
            if (clipId) {
                const resp = await axios.get(`https://api.twitch.tv/helix/clips?id=${clipId}`, { headers });
                if (resp.data.data?.[0]) return resp.data.data[0];
            }
        }

        if (mode === 'so') {
            const resp = await axios.get(`https://api.twitch.tv/helix/clips?broadcaster_id=${targetId}&first=100`, { headers });
            let clips = resp.data.data || [];
            if (clips.length > 0) return clips[Math.floor(Math.random() * clips.length)];
            return null;
        }

        if (extraData?.query) {
            const searchTerms = extraData.query.toLowerCase().trim().split(/\s+/);
            let cursor = "";
            let matchedClips = [];
            
            for (let i = 0; i < 5; i++) {
                let url = `https://api.twitch.tv/helix/clips?broadcaster_id=${targetId}&first=100`;
                if (cursor) url += `&after=${cursor}`;
                const resp = await axios.get(url, { headers });
                const clips = resp.data.data || [];
                if (clips.length === 0) break;

                const matches = clips.filter(c => searchTerms.every(term => c.title.toLowerCase().includes(term)));
                if (matches.length > 0) {
                    matchedClips.push(...matches);
                    break;
                }
                cursor = resp.data.pagination?.cursor;
                if (!cursor) break;
            }

            if (matchedClips.length > 0) {
                matchedClips.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                return matchedClips[0];
            }
            return null;
        }

        const timeWindows = [1, 3, 7, 30, 365]; 
        for (let days of timeWindows) {
            const d = new Date();
            d.setDate(d.getDate() - days);
            const url = `https://api.twitch.tv/helix/clips?broadcaster_id=${targetId}&first=100&started_at=${d.toISOString()}`;
            const resp = await axios.get(url, { headers });
            let clips = resp.data.data || [];
            if (clips.length > 0) {
                clips.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                return clips[0];
            }
        }
        return null;

    } catch(e) { 
        console.error("❌ [API Twitch] Recherche de clip échouée:", e.message);
        return null; 
    }
}

// =================================================================
// 6. TRAITEMENT SO/REPLAY & BOUCLE BRB
// =================================================================

async function processQueue() {
    if (isProcessing || shoutoutQueue.length === 0) return;
    isProcessing = true;
    const item = shoutoutQueue.shift();

    try {
        const targetUser = await getUserInfo(item.target);
        const finalClip = await findSmartClip(targetUser?.id, item.mode, item.extraData);
        
        if (finalClip) {
            console.log(`🎬 [CLIP TROUVÉ] : ${finalClip.title}`);
            const mp4Url = await getDirectMp4Url(finalClip.id);
            
            if (mp4Url) {
                console.log(`✅ [LIEN MP4 PRÊT] Lancement sur l'Overlay OBS...`);
                const gameName = await getGameName(finalClip.game_id);
                const dateStr = new Date(finalClip.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });

                // 🧚‍♂️ 1. ON LANCE LE SON INSTANTANÉMENT
                broadcast({ type: 'play_sound', file: '/static/uploads/hey_listen.mp3' });

                // ⏱️ 2. ON ATTEND 1.5 SECONDES (le temps que Navi finisse de parler)
                setTimeout(() => {
                    // 🎬 3. ON AFFICHE LE CLIP SUR OBS
                    broadcast({ 
                        type: 'play_clip', 
                        url: mp4Url,
                        meta: {
                            name: targetUser ? targetUser.display_name : finalClip.broadcaster_name,
                            avatar: targetUser ? targetUser.profile_image_url : '',
                            title: finalClip.title,
                            game: gameName,
                            date: dateStr
                        }
                    });
                }, 1500); // <-- C'est ici qu'on crée le décalage parfait !

                // 4. On ajuste le temps d'attente total en rajoutant nos 1.5 secondes
                const waitTime = finalClip.duration || 30;
                if (currentQueueItemTimer) clearTimeout(currentQueueItemTimer);
                currentQueueItemTimer = setTimeout(() => {
                    isProcessing = false;
                    processQueue();
                }, (waitTime * 1000) + 15000 + 1500); 
                return;

            } else {
                console.error(`❌ Impossible de récupérer la vidéo MP4 pour ce clip.`);
            }
        } else {
            console.error(`❌ Aucun clip valide trouvé pour : ${item.target}`);
        }
    } catch (err) { console.error("❌ Queue Error:", err.message); }
    
    isProcessing = false;
    processQueue();
}

async function startBrbLoop() {
    if (brbLoopActive) return;
    brbLoopActive = true;
    
    const user = await getUserInfo(CONFIG.CHANNEL_NAME);
    
    if (!user) {
        console.error("❌ [BRB] Connexion Twitch instable. Token expiré ? Annulation du BRB.");
        brbLoopActive = false;
        return;
    }

    try {
        const resp = await axios.get(`https://api.twitch.tv/helix/clips?broadcaster_id=${user.id}&first=100`, {
            headers: { 'Client-ID': CONFIG.TWITCH_CLIENT_ID, 'Authorization': `Bearer ${HELIX_TOKEN}` }
        });
        brbClipsPool = resp.data.data || [];
        if (brbClipsPool.length > 0) playNextBrbClip();
        else brbLoopActive = false;
    } catch(e) {
        console.error("❌ [BRB] Échec récupération des clips :", e.message);
        brbLoopActive = false;
    }
}

async function playNextBrbClip() {
    if (!brbLoopActive || currentScene !== 'brb') return;
    if (brbTimeout) clearTimeout(brbTimeout);

    let available = brbClipsPool.filter(c => !brbPlayedHistory.has(c.id));
    if (available.length === 0) { brbPlayedHistory.clear(); available = brbClipsPool; }
    
    const clip = available[Math.floor(Math.random() * available.length)];
    brbPlayedHistory.add(clip.id); 
    const mp4Url = await getDirectMp4Url(clip.id);
    
    if (mp4Url) {
        broadcast({ type: 'brb_clip', url: mp4Url, title: clip.title, creator: clip.creator_name });
        brbTimeout = setTimeout(playNextBrbClip, (clip.duration * 1000) + 15000);
    } else { 
        brbTimeout = setTimeout(playNextBrbClip, 1000); 
    }
}

function stopBrbLoop() { 
    brbLoopActive = false; 
    if (brbTimeout) clearTimeout(brbTimeout); 
}

// =================================================================
// 7. ROUTES API ET ÉVÉNEMENTS
// =================================================================

app.post('/api/brb/next', (req, res) => {
    if (brbLoopActive) playNextBrbClip();
    res.sendStatus(200);
});

app.post('/api/queue/next', (req, res) => {
    if (currentQueueItemTimer) clearTimeout(currentQueueItemTimer);
    isProcessing = false;
    processQueue();
    res.sendStatus(200);
});

app.post('/api/replay', async (req, res) => {
    try {
        const targetUser = await getUserInfo(CONFIG.CHANNEL_NAME);
        const finalClip = await findSmartClip(targetUser?.id, 'replay', req.body);

        if (finalClip) {
            shoutoutQueue.push({ target: CONFIG.CHANNEL_NAME, mode: 'replay', extraData: { slug: finalClip.id } });
            if (!isProcessing) processQueue();
            res.json({ status: "success", title: finalClip.title, creator: finalClip.creator_name });
        } else {
            res.json({ status: "not_found" });
        }
    } catch (error) { res.status(500).json({ status: "error" }); }
});

app.post('/api/shoutout', (req, res) => {
    shoutoutQueue.push({ target: req.body.target, mode: 'so', extraData: { slug: req.body.slug } });
    if (!isProcessing) processQueue();
    res.json({ status: "success" });
});

app.post('/api/trigger', (req, res) => {
    broadcast(req.body);
    res.json({ status: "success" });
});

app.get('/events', (req, res) => {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    const id = Date.now();
    clients.push({ id, res });
    
    // 🫀 AJOUT DU HEARTBEAT : Envoie un ping toutes les 15 secondes
    const heartbeat = setInterval(() => {
        res.write(`event: ping\ndata: {"time": "${new Date().toISOString()}"}\n\n`);
    }, 15000);

    req.on('close', () => {
        clearInterval(heartbeat); // 🛑 Arrêt propre du heartbeat à la déconnexion
        clients = clients.filter(c => c.id !== id);
    });
});

function broadcast(data) { clients.forEach(c => c.res.write(`data: ${JSON.stringify(data)}\n\n`)); }

// =================================================================
// 8. PAGES HTML
// =================================================================

app.get('/shoutout', (req, res) => {
    res.send(`
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { margin:0; overflow:hidden; background:transparent; display:flex; align-items:center; justify-content:center; height:100vh; font-family: 'Inter', sans-serif; }
        
        #wrapper { opacity:0; transition:0.5s cubic-bezier(0.4, 0, 0.2, 1); width:1280px; display:flex; flex-direction:column; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); transform: translateY(50px); }
        #wrapper.visible { opacity:1; transform: translateY(0); }
        
        .video-box { position:relative; width:100%; aspect-ratio: 16/9; background:black; border: 6px solid #9146FF; border-bottom: none; border-radius: 24px 24px 0 0; overflow: hidden; }
        video { position:absolute; top:0; left:0; width:100%; height:100%; object-fit:contain; z-index:1; }
        
        .progress-bg { position:absolute; bottom:0; left:0; width:100%; height:8px; background:rgba(15,23,42,0.9); z-index:10; }
        #progress { height:100%; background:#bf94ff; width:0%; box-shadow: 0 0 15px #9146FF; transition: width 0.1s linear; }
        
        .card { background:rgba(15,23,42,0.95); backdrop-filter:blur(10px); border: 6px solid #9146FF; border-top: none; border-radius: 0 0 24px 24px; padding:20px 30px; display:flex; align-items:center; gap:25px; position:relative; overflow:hidden; }
    </style>
</head>
<body>
    <div id="wrapper">
        <div class="video-box">
            <video id="v" playsinline preload="auto"></video>
            <div class="progress-bg"><div id="progress"></div></div>
        </div>
        <div class="card">
            <img id="avatar" src="" class="w-24 h-24 rounded-full border-4 border-[#9146FF] object-cover bg-slate-800 shadow-xl relative z-10">
            <div class="flex-1 overflow-hidden text-white relative z-10">
                <h2 id="name" class="text-4xl font-black mb-1 truncate"></h2>
                <div class="flex items-center gap-4 text-[#bf94ff] font-bold text-xl mb-1">
                    <span><i class="fas fa-gamepad mr-2 text-slate-400"></i><span id="game"></span></span>
                    <span class="text-slate-600">|</span>
                    <span class="text-slate-300 text-base"><i class="fas fa-calendar-alt mr-2"></i><span id="date"></span></span>
                </div>
                <p id="title" class="italic text-slate-400 truncate text-base"></p>
            </div>
            <i class="fab fa-twitch text-[#9146FF] text-7xl opacity-20 absolute right-8"></i>
        </div>
    </div>
    <script>
        const v = document.getElementById('v');
        const wrapper = document.getElementById('wrapper');
        const p = document.getElementById('progress');
        
        let source;
        let watchdogTimer;

        const finishClip = () => {
            if (!v.isEnding) {
                v.isEnding = true;
                wrapper.classList.remove('visible');
                setTimeout(() => { p.style.width = '0%'; }, 500);
                fetch('/api/queue/next', { method: 'POST' }).catch(e => {});
            }
        };

        v.addEventListener('timeupdate', () => {
            if(v.duration) {
                p.style.width = (v.currentTime / v.duration * 100) + '%';
                if (v.duration - v.currentTime <= 0.5) finishClip();
            }
        });
        
        v.addEventListener('ended', finishClip);

        // ⚡ AJOUT DE LA CONNEXION ROBUSTE (AUTO-RECONNECT)
        function connect() {
            if (source) source.close();
            source = new EventSource('/events');

            source.addEventListener('ping', (e) => {
                clearTimeout(watchdogTimer);
                watchdogTimer = setTimeout(() => { connect(); }, 35000);
            });

            source.onmessage = (e) => {
                const d = JSON.parse(e.data);
                if(d.type === 'play_sound') {
                    const audio = new Audio(d.file);
                    audio.volume = 0.5; // Tu pourras modifier le volume ici (0.8 = 80%)
                    audio.play().catch(err => console.error("Erreur Audio:", err));
                }

                if(d.type === 'play_clip') {
                    document.getElementById('avatar').src = d.meta.avatar;
                    document.getElementById('name').textContent = d.meta.name;
                    document.getElementById('game').textContent = d.meta.game;
                    document.getElementById('date').textContent = d.meta.date;
                    document.getElementById('title').textContent = d.meta.title;
                    
                    p.style.width = '0%';
                    v.isEnding = false;
                    v.src = d.url;
                    
                    wrapper.classList.add('visible');
                    v.play().catch(err => console.error(err));
                }
            };

            source.onerror = () => {
                clearTimeout(watchdogTimer);
                setTimeout(connect, 5000);
            };
        }
        
        connect();
    </script>
</body>
</html>
    `);
});

app.get('/brb', (req, res) => {
    res.send(`
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { margin:0; overflow:hidden; background:transparent; display:flex; align-items:center; justify-content:center; height:100vh; font-family: 'Inter', sans-serif; }
        
        #container { opacity:0; transition:1s; width:95vw; height:90vh; position:relative; border-radius:40px; overflow:hidden; border:10px solid #9146FF; background:black; box-shadow: 0 0 50px rgba(145,70,255,0.3); }
        video { position:absolute; top:0; left:0; width:100%; height:100%; object-fit:cover; z-index:1; }
        
        .bottom-bar { position:absolute; bottom:0; left:0; width:100%; height:64px; background:rgba(15,23,42,0.9); backdrop-filter:blur(8px); border-top:2px solid rgba(145,70,255,0.4); z-index:20; display:flex; align-items:center; justify-content:space-between; padding:0 32px; }
        #progress { position:absolute; top:-4px; left:0; height:4px; background:#bf94ff; width:0%; box-shadow: 0 0 15px #9146FF; transition: width 0.1s linear; z-index:21; }
    </style>
</head>
<body>
    <div id="container">
        <video id="v" playsinline preload="auto"></video>
        
        <div class="bottom-bar">
            <div id="progress"></div>
            <div id="title" class="text-white font-bold text-2xl truncate flex-1 pr-8 drop-shadow-lg"></div>
            <div class="text-[#bf94ff] font-black text-lg uppercase tracking-widest flex-shrink-0 drop-shadow-lg">
                <i class="fas fa-video mr-3 opacity-50"></i>Clips : <span id="author"></span>
            </div>
        </div>
    </div>
    <script>
        const v = document.getElementById('v');
        const c = document.getElementById('container');
        const t = document.getElementById('title');
        const a = document.getElementById('author');
        const p = document.getElementById('progress');

        let source;
        let watchdogTimer;

        const triggerNextClip = () => {
            if (!v.isEnding) {
                v.isEnding = true;
                fetch('/api/brb/next', { method: 'POST' }).catch(e => {});
            }
        };

        v.addEventListener('timeupdate', () => {
            if(v.duration) {
                p.style.width = (v.currentTime / v.duration * 100) + '%';
                if (v.duration - v.currentTime <= 0.5) triggerNextClip();
            }
        });
        
        v.addEventListener('ended', triggerNextClip);

        // ⚡ AJOUT DE LA CONNEXION ROBUSTE (AUTO-RECONNECT)
        function connect() {
            if (source) source.close();
            source = new EventSource('/events');

            source.addEventListener('ping', (e) => {
                clearTimeout(watchdogTimer);
                watchdogTimer = setTimeout(() => { connect(); }, 35000);
            });

            source.onmessage = (e) => {
                const d = JSON.parse(e.data);
                
                if(d.type === 'change_scene' || d.type === 'init'){
                    if(d.scene === 'brb') {
                        c.style.opacity = 1;
                        if (v.src) v.play().catch(e=>console.log(e));
                    } else { 
                        c.style.opacity = 0; 
                        v.pause(); 
                    }
                }
                
                if(d.type === 'brb_clip'){
                    p.style.width = '0%';
                    v.isEnding = false;
                    v.src = d.url;
                    t.textContent = d.title;
                    a.textContent = d.creator || "Inconnu";
                    v.play().catch(err => console.error(err));
                }
            };

            source.onerror = () => {
                clearTimeout(watchdogTimer);
                setTimeout(connect, 5000);
            };
        }
        
        connect();
    </script>
</body>
</html>
    `);
});

app.listen(CONFIG.PORT, '0.0.0.0', () => { console.log(`🚀 RÉGIE CONNECTÉE SUR PORT ${CONFIG.PORT}`); });
