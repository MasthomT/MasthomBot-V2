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
    CHANNEL_NAME: (process.env.TWITCH_USERNAME || "masthou").replace(/['"\s]/g, '').trim(),
    GQL_CLIENT_ID: process.env.TWITCH_CLIENT_ID,
    //GQL_CLIENT_ID: 'kimne78kx3ncx6brgo4mv6wki5h1ko',
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
let brbFirstClip = false;
let brbTimeout = null;
let gameCache = {};

const app = express();
const obs = new OBSWebSocket();

app.use(cors());
app.use(express.json());
app.use('/static/commands', express.static('/home/thomas/masthom/BOT_V2/static/commands'));
app.use('/static/uploads', express.static('/home/thomas/masthom/BOT_V2/app/static/uploads'));

// 📡 SharedWorker : UNE seule connexion SSE partagée entre TOUTES les sources OBS de
// cette origine (au lieu d'une connexion permanente par overlay — BRB, alertes,
// shoutout, horloge, mur d'emotes), pour respecter le quota de ~6 connexions/origine
// qu'OBS alloue à toutes ses browser sources. Reprend la logique ping/watchdog qui
// vivait avant dans chaque page, mais centralisée ici pour tout le monde.
const WORKER_JS = `
let source = null;
let watchdogTimer = null;
let dernierInit = null; // dernier statut de scène connu (type 'init'/'change_scene'),
                         // rejoué aux pages qui se connectent après coup (ex: BRB)
const ports = [];

function reconnecter() {
    clearTimeout(watchdogTimer);
    if (source) { try { source.close(); } catch (err) {} source = null; }
    setTimeout(connecter, 3000);
}

function connecter() {
    if (source) return;
    source = new EventSource('/events');

    source.addEventListener('ping', () => {
        clearTimeout(watchdogTimer);
        watchdogTimer = setTimeout(reconnecter, 35000);
    });

    source.onmessage = (e) => {
        try {
            const d = JSON.parse(e.data);
            if (d.type === 'init' || d.type === 'change_scene') dernierInit = e.data;
        } catch (err) {}
        for (const p of ports) {
            try { p.postMessage(e.data); } catch (err) {}
        }
    };

    source.onerror = reconnecter;
}

self.onconnect = (e) => {
    const port = e.ports[0];
    ports.push(port);
    port.start();
    if (dernierInit) port.postMessage(dernierInit);
    connecter();
};
`;

app.get('/worker.js', (req, res) => {
    res.set('Content-Type', 'application/javascript');
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate');
    res.send(WORKER_JS);
});

// =================================================================
// 3. CONNEXION OBS
// =================================================================
let sourceMap = new Map();
let obsReconnectTimeout = null; // 🛡️ Le filet de sécurité pour éviter le crash
let obsConnected = false; // exposé via /api/health pour le dashboard de santé du bot
let obsProgramScene = ''; // scène OBS en cours (écran de titre automatique : le navigateur OBS ne la donne pas toujours)

async function refreshSourceMap() {
    try {
        console.log("🔄 [OBS] Mise à jour du mapping des sources...");
        const data = await obs.call('GetSceneList');
        for (const scene of data.scenes) {
            const items = await obs.call('GetSceneItemList', { sceneName: scene.sceneName });
            for (const item of items.sceneItems) {
                // On crée une clé unique "NomScène|NomSource" pour retrouver l'ID
                sourceMap.set(`${scene.sceneName}|${item.sourceName}`, item.sceneItemId);
            }
        }
        console.log("✅ [OBS] Mapping terminé.");
    } catch (e) {
        console.error("❌ [OBS] Erreur lors du mapping :", e);
    }
}

// 🛡️ La lib obs-websocket-js émet 'ConnectionClosed' à la fois sur une tentative de
// connexion ratée ET sur une vraie coupure : on centralise donc la planification de
// reconnexion ici pour n'avoir qu'un seul timer et un seul log par coupure (au lieu
// de deux messages dupliqués pour le même événement).
// OBS fermé = une tentative toutes les 10 s, mais on ne l'écrit dans les logs qu'à la
// 1re coupure puis toutes les 10 min (avant : ~3 300 lignes/jour quand OBS était éteint).
let obsFailCount = 0;
function scheduleObsReconnect(reason) {
    if (obsReconnectTimeout) return; // déjà programmé, on ignore les doublons
    obsFailCount++;
    if (obsFailCount === 1) {
        console.log(`🔌 [OBS] ${reason}. Nouvelle tentative toutes les 10s (log toutes les 10 min).`);
    } else if (obsFailCount % 60 === 0) {
        console.log(`🔌 [OBS] Toujours injoignable (${obsFailCount} tentatives).`);
    }
    obsReconnectTimeout = setTimeout(() => {
        obsReconnectTimeout = null;
        connectOBS();
    }, 10000);
}

async function connectOBS() {
    try {
        await obs.connect(CONFIG.OBS_ADDRESS, CONFIG.OBS_PASSWORD);
        obsConnected = true;
        obsFailCount = 0;
        console.log(`🎬 [OBS] Connecté ! Surveillance de la scène "${CONFIG.BRB_SCENE_NAME}".`);

        // ⚡ On vérifie sur quelle scène on est au moment même de la connexion
        await refreshSourceMap();
        const data = await obs.call('GetCurrentProgramScene');
        obsProgramScene = data.currentProgramSceneName || '';
        if (data.currentProgramSceneName === CONFIG.BRB_SCENE_NAME) {
            if (!brbLoopActive) {
                currentScene = 'brb';
                startBrbLoop();
                broadcast({ type: 'change_scene', scene: 'brb' });
            }
        }
    } catch (error) {
        obsConnected = false;
        scheduleObsReconnect('Échec de connexion');
    }
}

// 🔄 Auto-reconnexion si OBS est fermé puis relancé
obs.on('ConnectionClosed', () => {
    obsConnected = false;
    scheduleObsReconnect('Connexion perdue');
});

// 🎬 Écoute en direct des changements de scène OBS. Avant, la scène n'était vérifiée
// qu'UNE FOIS, au moment de la connexion — si on basculait sur "ON BREAK" pendant que
// Node était déjà connecté (le cas normal en plein stream), le BRB ne se déclenchait
// jamais. Constaté le 07/07/2026 : le BRB n'apparaissait plus du tout.
// Traitement d'un changement de scène (événement OBS OU relevé régulier ci-dessous)
function onProgramScene(sceneName) {
    obsProgramScene = sceneName || '';
    const isBrbScene = sceneName === CONFIG.BRB_SCENE_NAME;
    if (isBrbScene) {
        if (!brbLoopActive) {
            currentScene = 'brb';
            startBrbLoop();
            broadcast({ type: 'change_scene', scene: 'brb' });
            console.log('🎬 [OBS] Scène "ON BREAK" détectée en direct : lancement du BRB.');
        }
    } else {
        if (brbLoopActive) {
            currentScene = 'main';
            stopBrbLoop();
            broadcast({ type: 'change_scene', scene: 'main' });
            console.log('🛑 [OBS] Sortie de la scène "ON BREAK" détectée en direct : arrêt du BRB.');
        }
    }
}
obs.on('CurrentProgramSceneChanged', (data) => onProgramScene(data.sceneName));

// Filet de sécurité : la connexion à OBS peut rester « ouverte » sans plus recevoir d'événements (constaté le 03/11/2026 :
// la scène connue du serveur restait figée, donc l'écran de titre automatique n'affichait plus rien). On relève donc
// la scène toutes les 2 s ; si OBS ne répond plus, on coupe pour déclencher la reconnexion automatique.
let obsPollBusy = false;
setInterval(async () => {
    if (!obsConnected || obsPollBusy) return;
    obsPollBusy = true;
    try {
        const d = await Promise.race([
            obs.call('GetCurrentProgramScene'),
            new Promise((_, rej) => setTimeout(() => rej(new Error('délai dépassé')), 4000)),
        ]);
        if ((d.currentProgramSceneName || '') !== obsProgramScene) onProgramScene(d.currentProgramSceneName);
    } catch (e) {
        console.log(`🔌 [OBS] Relevé de scène impossible (${e.message}) : reconnexion forcée.`);
        obsConnected = false;
        try { await obs.disconnect(); } catch (e2) { /* déjà coupé */ }
        scheduleObsReconnect('Connexion inactive');
    } finally {
        obsPollBusy = false;
    }
}, 2000);

app.get('/api/obs-scene', (req, res) => {
    res.json({ scene: obsProgramScene, connected: obsConnected });
});

app.get('/api/health', (req, res) => {
    res.json({
        obs_connected: obsConnected,
        current_scene: currentScene,
        brb_loop_active: brbLoopActive,
        uptime_seconds: process.uptime(),
    });
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
        const resp = await axios.post('https://gql.twitch.tv/gql', [{
            operationName: 'ClipsBroadcasterPage_Clip',
            variables: { slug },
            query: `query ClipsBroadcasterPage_Clip($slug: ID!) { clip(slug: $slug) { playbackAccessToken(params: {platform: "web", playerBackend: "mediaplayer", playerType: "site"}) { signature value } videoQualities { frameRate quality sourceURL } } }`
        }], { headers: { 'Client-ID': 'kimne78kx3ncx6brgo4mv6wki5h1ko' } });

        const clipData = resp.data[0]?.data?.clip;
        if (clipData?.videoQualities?.length > 0) {
            let selected = clipData.videoQualities.find(q => q.quality === '720')
                        || clipData.videoQualities.find(q => q.quality === '480')
                        || clipData.videoQualities[0];
            return `${selected.sourceURL}?sig=${clipData.playbackAccessToken.signature}&token=${encodeURIComponent(clipData.playbackAccessToken.value)}`;
        }
    } catch(e) {
        console.error("❌ [GQL] Erreur:", e.message);
    }
    return null;
}

// =================================================================
// 5. SCANNER DE CLIPS
// =================================================================

async function findSmartClip(userId, mode, extraData) {
    try {
        // Pour le mode 'so', on n'utilise JAMAIS de fallback sur la propre chaîne :
        // si l'utilisateur cible est introuvable, on abandonne plutôt que d'afficher
        // ses propres clips par erreur.
        let targetId;
        if (userId) {
            targetId = userId;
        } else if (mode !== 'so') {
            targetId = (await getUserInfo(CONFIG.CHANNEL_NAME))?.id;
        }
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
    console.log(`[DEBUG] processQueue appelée - isProcessing=${isProcessing} queue=${shoutoutQueue.length}`);
    if (isProcessing || shoutoutQueue.length === 0) return;
    isProcessing = true;
    const item = shoutoutQueue.shift();
    console.log(`[DEBUG] Traitement de : ${JSON.stringify(item)}`);

    // TikTok : même file que les clips, donc jamais les deux en même temps à l'écran. La page signale
    // la fin via /api/queue/next ; le minuteur n'est qu'un filet si elle ne répond jamais.
    if (item.mode === 'tiktok') {
        broadcast({ type: 'play_tiktok', mode: 'tiktok', url: item.extraData.url, source: item.extraData.source || 'tiktok' });
        if (currentQueueItemTimer) clearTimeout(currentQueueItemTimer);
        const safetyMs = ((item.extraData.duration || 600) + 20) * 1000;
        currentQueueItemTimer = setTimeout(() => {
            isProcessing = false;
            processQueue();
        }, safetyMs);
        return;
    }

    try {
        const targetUser = await getUserInfo(item.target);
        if (!targetUser && item.mode === 'so') {
            console.error(`❌ [SO] Utilisateur "${item.target}" introuvable sur Twitch — SO annulé.`);
            isProcessing = false;
            processQueue();
            return;
        }
        const finalClip = await findSmartClip(targetUser?.id, item.mode, item.extraData);

        if (finalClip) {
            console.log(`🎬 [CLIP TROUVÉ] : ${finalClip.title}`);
            const mp4Url = await getDirectMp4Url(finalClip.id);
            
            if (mp4Url) {
                console.log(`✅ [LIEN MP4 PRÊT] Lancement sur l'Overlay OBS...`);
                const gameName = await getGameName(finalClip.game_id);
                const dateStr = new Date(finalClip.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });

                // 🧚‍♂️ 1. ON LANCE LE SON INSTANTANÉMENT
                broadcast({ type: 'play_sound', mode: item.mode, file: '/static/uploads/hey_listen.mp3' });

                // ⏱️ 2. ON ATTEND 1.5 SECONDES (le temps que Navi finisse de parler)
                setTimeout(() => {
                    // 🎬 3. ON AFFICHE LE CLIP SUR OBS
                    broadcast({ 
                        type: 'play_clip', 
                        mode: item.mode,
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
    brbFirstClip = true; // Marqueur : le prochain clip est le premier
    
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
        console.log(`[BRB] Clips chargés : ${brbClipsPool.length}`);
        
        if (brbClipsPool.length > 0) {
            console.log("🚀 [BRB] Lancement immédiat du premier clip !");
            playNextBrbClip(); 
        } else {
            brbLoopActive = false;
        }

    } catch(e) {
        console.error("❌ [BRB] Échec récupération des clips :", e.message);
        brbLoopActive = false;
    }
}
async function playNextBrbClip() {
    // 🛡️ SÉCURITÉ : On ne fait rien si le BRB est désactivé, 
    // si on est sur la mauvaise scène, ou si la liste est vide
    if (!brbLoopActive || currentScene !== 'brb' || brbClipsPool.length === 0) {
        console.log("[BRB] Boucle en attente : clips non chargés ou scène changée.");
        return; 
    }
    
    if (brbTimeout) clearTimeout(brbTimeout);

    let available = brbClipsPool.filter(c => !brbPlayedHistory.has(c.id));
    if (available.length === 0) { 
        brbPlayedHistory.clear(); 
        available = brbClipsPool; 
    }
    
    const clip = available[Math.floor(Math.random() * available.length)];
    
    // 🛡️ SÉCURITÉ : Si le clip est introuvable, on réessaie dans 5 secondes
    if (!clip || !clip.id) {
        console.warn("[BRB] Aucun clip disponible, tentative dans 5s...");
        brbTimeout = setTimeout(playNextBrbClip, 5000);
        return;
    }

    brbPlayedHistory.add(clip.id); 
    const mp4Url = await getDirectMp4Url(clip.id);
    
    if (mp4Url) {
        // Au premier clip seulement : on affiche l'overlay, puis on envoie la vidéo
        if (brbFirstClip) {
            broadcast({ type: 'change_scene', scene: 'brb' });
            brbFirstClip = false;
        }
        broadcast({ type: 'brb_clip', url: mp4Url, title: clip.title, creator: clip.creator_name });
        // Filet de sécurité uniquement : si le client ne répond plus (OBS crashé, etc.)
        // On attend durée + 45s avant de forcer le suivant
        brbTimeout = setTimeout(playNextBrbClip, (clip.duration * 1000) + 45000);
    } else { 
        // Si le lien MP4 échoue, on passe au suivant
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
            res.json({ status: "success", title: finalClip.title, creator: finalClip.creator_name, clip_id: finalClip.id, url: finalClip.url || `https://clips.twitch.tv/${finalClip.id}` });
        } else {
            res.json({ status: "not_found" });
        }
    } catch (error) { res.status(500).json({ status: "error" }); }
});

// Style (thème) des widgets : relais vers le bot Python, pour que les pages Node le lisent sans CORS.
app.get('/api/theme-style', async (req, res) => {
    try {
        const r = await axios.get('http://127.0.0.1:8000/api/labels/style', { timeout: 4000 });
        res.set('Cache-Control', 'no-store').json(r.data);
    } catch (e) {
        res.status(502).json({ error: 'style indisponible' });
    }
});

app.post('/api/tiktok', (req, res) => {
    const url = req.body && req.body.url;
    if (!url) return res.status(400).json({ status: "error", message: "url manquante" });
    shoutoutQueue.push({ mode: 'tiktok', extraData: { url: url, duration: Number(req.body.duration) || 0, source: String(req.body.source || 'tiktok') } });
    if (!isProcessing) processQueue();
    res.json({ status: "success" });
});

app.post('/api/shoutout', (req, res) => {
    shoutoutQueue.push({ target: req.body.target, mode: 'so', extraData: { slug: req.body.slug } });
    if (!isProcessing) processQueue();
    res.json({ status: "success" });
});

// ⚙️ Exécute une action OBS d'une commande du site (/admin/commands). Le mapping des sources est relu
// automatiquement quand une source est introuvable : une source ajoutée dans OBS après le démarrage marche tout de suite.
async function findSceneItemId(scene, source) {
    const key = `${scene}|${source}`;
    if (!sourceMap.has(key)) await refreshSourceMap();
    const id = sourceMap.get(key);
    if (!id) { const e = new Error(`Source introuvable : « ${source} » dans la scène « ${scene} »`); e.notFound = true; throw e; }
    return id;
}

async function runObsAction(action, p) {
    switch (action) {
        case 'scene_switch':
            await obs.call('SetCurrentProgramScene', { sceneName: p.scene });
            return;
        case 'source_show':
        case 'source_hide':
        case 'source_toggle': {
            const sceneItemId = await findSceneItemId(p.scene, p.source);
            let enabled = action === 'source_show';
            if (action === 'source_toggle') {
                const cur = await obs.call('GetSceneItemEnabled', { sceneName: p.scene, sceneItemId });
                enabled = !cur.sceneItemEnabled;
            }
            await obs.call('SetSceneItemEnabled', { sceneName: p.scene, sceneItemId, sceneItemEnabled: enabled });
            return enabled ? 'affichée' : 'masquée';
        }
        case 'filter_enable':
        case 'filter_disable':
        case 'filter_toggle': {
            let enabled = action === 'filter_enable';
            if (action === 'filter_toggle') {
                const cur = await obs.call('GetSourceFilter', { sourceName: p.source, filterName: p.filter });
                enabled = !cur.filterEnabled;
            }
            await obs.call('SetSourceFilterEnabled', { sourceName: p.source, filterName: p.filter, filterEnabled: enabled });
            return enabled ? 'activé' : 'désactivé';
        }
        case 'media_play':
            await obs.call('TriggerMediaInputAction', { inputName: p.source, mediaAction: 'OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY' }); return;
        case 'media_stop':
            await obs.call('TriggerMediaInputAction', { inputName: p.source, mediaAction: 'OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP' }); return;
        case 'media_restart':
            await obs.call('TriggerMediaInputAction', { inputName: p.source, mediaAction: 'OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART' }); return;
        case 'mute_source':
            await obs.call('SetInputMute', { inputName: p.source, inputMuted: true }); return;
        case 'unmute_source':
            await obs.call('SetInputMute', { inputName: p.source, inputMuted: false }); return;
        case 'toggle_mute':
            await obs.call('ToggleInputMute', { inputName: p.source }); return;
        case 'stream_start': await obs.call('StartStream'); return;
        case 'stream_stop': await obs.call('StopStream'); return;
        case 'record_start': await obs.call('StartRecord'); return;
        case 'record_stop': await obs.call('StopRecord'); return;
        case 'record_pause': await obs.call('PauseRecord'); return;
        case 'record_resume': await obs.call('ResumeRecord'); return;
        case 'text_update': {
            const cur = await obs.call('GetInputSettings', { inputName: p.source });
            await obs.call('SetInputSettings', { inputName: p.source, inputSettings: { ...cur.inputSettings, text: p.text || '' } });
            return;
        }
        default:
            throw new Error(`Action OBS inconnue : ${action}`);
    }
}

app.post('/api/trigger', async (req, res) => {
    const data = req.body;
    
    // Si c'est une commande OBS venant de Python
    if (data.type === 'obs_command') {
        const d = data.details || {};
        const { action, scene, source, filter, text } = d;
        try {
            if (!obsConnected) throw new Error('OBS non connecté');
            const r = await runObsAction(action, { scene, source, filter, text });
            console.log(`✅ [OBS] Action ${action} exécutée${source ? ' sur ' + source : ''}${r ? ' (' + r + ')' : ''}`);
            res.json({ status: "success" });
        } catch (err) {
            const msg = (err && err.message) || String(err);
            console.error(`❌ [OBS] Action ${action} (${scene || ''}|${source || ''}) : ${msg}`);
            res.status(err && err.notFound ? 404 : 500).json({ status: "error", message: msg });
        }
    }
    // Si c'est une commande pour l'overlay (image, son, brb)
    else {
        if (data.type === 'change_scene') {
            if (data.scene === 'brb') { stopBrbLoop(); startBrbLoop(); } 
            else if (data.scene === 'main') { stopBrbLoop(); broadcast(data); }
        } else {
            broadcast(data);
        }
        res.json({ status: "success" });
    }
});

app.post('/alerts', (req, res) => {
    const { type, details } = req.body;
    console.log(`[NODE] 📦 Colis reçu : ${type}`);
    
    // On retransmet simplement le colis à tous les clients connectés (l'overlay)
    broadcast({ type: type, details: details });
    
    res.status(200).json({ status: "success" });
});

app.get('/events', (req, res) => {
    // 🛡️ Headers blindés pour les Server-Sent Events
    res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform', // no-transform empêche la compression (gzip) de casser le flux
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no' // Désactive les tampons des proxies ou box internet
    });
    res.flushHeaders(); // Force l'envoi immédiat pour valider la connexion

    const id = Date.now();
    clients.push({ id, res });

    // On dit TOUT DE SUITE à la page web sur quelle scène on est
    res.write(`data: ${JSON.stringify({ type: 'init', scene: currentScene })}\n\n`);

    // 🫀 AJOUT DU HEARTBEAT : Envoie un ping toutes les 15 secondes
    const heartbeat = setInterval(() => {
        res.write(`event: ping\ndata: {"time": "${new Date().toISOString()}"}\n\n`);
    }, 15000);

    req.on('close', () => {
        clearInterval(heartbeat);
        clients = clients.filter(c => c.id !== id);
    });
});

function broadcast(data) { 
    console.log(`[BROADCAST] Envoi à ${clients.length} client(s) : ${data.type}`);
    clients.forEach(c => c.res.write(`data: ${JSON.stringify(data)}\n\n`)); 
}

app.post('/api/brb/toggle', (req, res) => {
    if (req.body.scene === 'brb') {
        if (!brbLoopActive) {
            currentScene = 'brb';
            startBrbLoop();
            broadcast({ type: 'change_scene', scene: 'brb' });
            console.log("🎬 [NODE] Ordre reçu de Python : Lancement du BRB !");
        }
    } else {
        if (brbLoopActive) {
            currentScene = 'main';
            stopBrbLoop();
            broadcast({ type: 'change_scene', scene: 'main' });
            console.log("🛑 [NODE] Ordre reçu de Python : Arrêt du BRB !");
        }
    }
    res.sendStatus(200);
});

app.get('/alerts', (req, res) => {
    res.send(`
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Overlay Alertes</title>
    <style>
        body { margin:0; overflow:hidden; width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; background: transparent; }
        #media-container { opacity: 0; transition: opacity 0.5s ease-in-out; max-width: 100%; max-height: 100%; }
    </style>
</head>
<body>
    <div id="media-container"></div>
    <script>
        const mediaContainer = document.getElementById('media-container');
        let imgTimeout;

        function handleEvent(d) {
            if (d.type === 'sound') {
                const audio = new Audio('/static/commands/sounds/' + d.details.filename);
                audio.volume = 1.0;
                audio.play().catch(err => console.error("Erreur Audio:", err));
            }

            if (d.type === 'image') {
                const filename = d.details.filename;
                const isVideo = filename.match(/\\.(mp4|webm)$/i);

                if (isVideo) {
                    mediaContainer.innerHTML = \`<video src="/static/commands/images/\${filename}" autoplay muted style="width:100%; height:100%; object-fit:contain;"></video>\`;
                } else {
                    mediaContainer.innerHTML = \`<img src="/static/commands/images/\${filename}" style="width:100%; height:100%; object-fit:contain;" />\`;
                }

                mediaContainer.style.opacity = 1;

                if (imgTimeout) clearTimeout(imgTimeout);
                imgTimeout = setTimeout(() => {
                    mediaContainer.style.opacity = 0;
                    setTimeout(() => { mediaContainer.innerHTML = ''; }, 500);
                }, 8000);
            }
        }

        // 📡 UNE seule connexion SSE partagée entre TOUTES les sources OBS de cette
        // origine (via SharedWorker), au lieu d'une connexion par overlay.
        if (typeof SharedWorker !== 'undefined') {
            try {
                const worker = new SharedWorker('/worker.js');
                worker.port.onmessage = (e) => handleEvent(JSON.parse(e.data));
                worker.port.start();
            } catch (e) { console.error('SharedWorker indisponible :', e); }
        }
    </script>
</body>
</html>
    `);
});

app.get('/shoutout', (req, res) => {
    // OVERLAY UNIQUE « lecteur » : clips (replay / shoutout) ET TikToks, dans une seule source navigateur OBS.
    // Tailles en vw/vh : la mise en page suit la résolution du canvas (prévue pour 1920x1080).
    //   - clip   : centré, 50 % de la largeur de l'écran
    //   - TikTok : à droite, centré verticalement (80 % de la hauteur, format vertical 9:16)
    // (pas de backticks ni de dollar-accolade dans ce HTML : il vit dans un gabarit JS)
    res.send(`
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * { box-sizing: border-box; }
        html, body { margin:0; width:100%; height:100%; overflow:hidden; background:transparent; font-family:'Inter','Segoe UI',Arial,sans-serif; }

        /* ───────── CLIP / SHOUTOUT : centré, moitié de la largeur de l'écran ───────── */
        #wrapper { position:fixed; top:50%; left:50%; width:50vw; display:flex; flex-direction:column;
                   opacity:0; transform:translate(-50%, calc(-50% + 40px)); transition:0.5s cubic-bezier(0.4,0,0.2,1);
                   box-shadow:0 25px 50px -12px rgba(0,0,0,0.7); }
        #wrapper.visible { opacity:1; transform:translate(-50%, -50%); }

        .video-box { position:relative; width:100%; aspect-ratio:16/9; background:#000; border:0.3vw solid #9146FF; border-bottom:none; border-radius:1.2vw 1.2vw 0 0; overflow:hidden; }
        #v { position:absolute; top:0; left:0; width:100%; height:100%; object-fit:contain; z-index:1; }
        .progress-bg { position:absolute; bottom:0; left:0; width:100%; height:0.45vw; background:rgba(15,23,42,0.9); z-index:10; }
        #progress { height:100%; width:0%; background:#bf94ff; box-shadow:0 0 15px #9146FF; transition:width 0.1s linear; }

        .card { position:relative; display:flex; align-items:center; gap:1.4vw; padding:1.1vw 1.6vw; overflow:hidden;
                background:rgba(15,23,42,0.95); border:0.3vw solid #9146FF; border-top:none; border-radius:0 0 1.2vw 1.2vw; }
        #avatar { width:4.2vw; height:4.2vw; flex:none; border-radius:50%; border:0.22vw solid #9146FF; object-fit:cover; background:#1e293b; position:relative; z-index:2; }
        .info { flex:1; min-width:0; color:#fff; position:relative; z-index:2; }
        #name { margin:0 0 0.2vw; font-size:2vw; font-weight:900; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .meta { display:flex; align-items:center; gap:1vw; color:#bf94ff; font-weight:700; font-size:1.1vw; margin-bottom:0.2vw; }
        .meta i { margin-right:0.4vw; color:#94a3b8; }
        .meta .sep { color:#475569; }
        .meta .date { color:#cbd5e1; font-size:0.95vw; }
        #title { margin:0; font-style:italic; color:#94a3b8; font-size:0.95vw; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .twitch-logo { position:absolute; right:1.6vw; font-size:4.4vw; color:#9146FF; opacity:0.2; z-index:1; }

        /* ───────── VIDÉO (TikTok / YouTube / Instagram) : le cadre épouse le format de la vidéo ─────────
           Vertical / carré : collé à droite (marge 20 px), 80 % de la hauteur.
           Paysage : centré, jusqu'à 50 % de la largeur (comme un clip).
           La taille exacte est calculée par la page dès que le format de la vidéo est connu (fitTikTok). */
        #tiktok { --c:#fe2c55; position:fixed; top:50%; right:20px; height:80vh; width:45vh; display:flex; flex-direction:column;
                  background:#000; border:3px solid var(--c); border-radius:24px; overflow:hidden;
                  box-shadow:0 25px 50px rgba(0,0,0,0.8), 0 0 30px var(--c);
                  opacity:0; pointer-events:none; }
        #tiktok.port { transform:translateY(-50%) scale(0.85); transform-origin:right center;
                       transition:transform 0.5s cubic-bezier(0.34,1.56,0.64,1), opacity 0.5s ease; }
        #tiktok.port.visible { opacity:1; transform:translateY(-50%) scale(1); }
        #tiktok.land { right:auto; left:50%; transform:translate(-50%,-50%) scale(0.85); transform-origin:center center;
                       transition:transform 0.5s cubic-bezier(0.34,1.56,0.64,1), opacity 0.5s ease; }
        #tiktok.land.visible { opacity:1; transform:translate(-50%,-50%) scale(1); }
        .tt-badge { flex:none; height:3.6vh; display:flex; align-items:center; justify-content:center; gap:8px;
                    background:var(--c); color:#fff; font-weight:900; font-size:1.7vh; text-transform:uppercase; letter-spacing:0.08em; }
        #tt { flex:1; min-height:0; width:100%; object-fit:contain; background:#000; display:block; }
    </style>
    <script>(function(){var s=document.createElement('script');s.src=location.protocol+'//'+location.hostname+':8000/static/theme.js?t='+Date.now();document.head.appendChild(s);})();</script>
</head>
<body>
    <div id="wrapper">
        <div class="video-box">
            <video id="v" playsinline preload="auto"></video>
            <div class="progress-bg"><div id="progress"></div></div>
        </div>
        <div class="card">
            <img id="avatar" src="">
            <div class="info">
                <h2 id="name"></h2>
                <div class="meta">
                    <span><i class="fas fa-gamepad"></i><span id="game"></span></span>
                    <span class="sep">|</span>
                    <span class="date"><i class="fas fa-calendar-alt"></i><span id="date"></span></span>
                </div>
                <p id="title"></p>
            </div>
            <i class="fab fa-twitch twitch-logo"></i>
        </div>
    </div>

    <div id="tiktok">
        <div class="tt-badge" id="tt-badge">&#127925; TikTok</div>
        <video id="tt" playsinline preload="auto"></video>
    </div>

    <script>
        const v = document.getElementById('v');
        const wrapper = document.getElementById('wrapper');
        const p = document.getElementById('progress');
        const tt = document.getElementById('tt');
        const ttBox = document.getElementById('tiktok');

        function nextInQueue() { fetch('/api/queue/next', { method: 'POST' }).catch(function () {}); }

        // ───── CLIP ─────
        const finishClip = () => {
            if (!v.isEnding) {
                v.isEnding = true;
                wrapper.classList.remove('visible');
                setTimeout(() => { p.style.width = '0%'; }, 500);
                nextInQueue();
            }
        };

        v.addEventListener('timeupdate', () => {
            if (v.duration) {
                p.style.width = (v.currentTime / v.duration * 100) + '%';
                if (v.duration - v.currentTime <= 0.5) finishClip();
            }
        });

        v.addEventListener('ended', finishClip);

        // Clip cassé/introuvable : on ne montre jamais l'embed, on passe directement au suivant.
        v.addEventListener('error', () => {
            if (!v.isEnding) {
                v.isEnding = true;
                wrapper.classList.remove('visible');
                p.style.width = '0%';
                nextInQueue();
            }
        });

        v.addEventListener('loadeddata', () => {
            wrapper.classList.add('visible');
        });

        // ───── TIKTOK ─────
        let ttEnding = false, ttRetry = null, ttCleanup = null;
        function ttStopRetry() { if (ttRetry) { clearInterval(ttRetry); ttRetry = null; } }

        function ttFinish() {
            if (ttEnding) return;
            ttEnding = true;
            ttStopRetry();
            ttBox.classList.remove('visible');
            ttCleanup = setTimeout(function () {
                tt.pause();
                tt.removeAttribute('src');
                tt.load();
                ttCleanup = null;
            }, 600);
            nextInQueue();
        }

        function ttPlay() {
            // Démarrage directement AVEC le son (OBS autorise l'autoplay) : démuter en cours de lecture
            // déclencherait la politique anti-autoplay de Chromium. Repli en muet si refus.
            tt.muted = false;
            const tenter = function () {
                const pr = tt.play();
                if (pr && pr.catch) pr.catch(function () {
                    tt.muted = true;
                    const p2 = tt.play();
                    if (p2 && p2.catch) p2.catch(function () {});
                });
            };
            tenter();
            ttStopRetry();
            ttRetry = setInterval(function () {
                if (tt.ended || !tt.paused) { ttStopRetry(); return; }
                tenter();
            }, 400);
        }

        // Habillage selon la plateforme (couleur du cadre + bandeau)
        const TT_SOURCES = {
            tiktok:    { c: '#fe2c55', label: '&#127925; TikTok' },
            youtube:   { c: '#ff0000', label: '&#9654; YouTube' },
            instagram: { c: '#e1306c', label: '&#128247; Instagram' }
        };
        function ttSkin(source) {
            const k = TT_SOURCES[source] || TT_SOURCES.tiktok;
            ttBox.style.setProperty('--c', k.c);
            document.getElementById('tt-badge').innerHTML = k.label;
        }

        // Le cadre prend la forme de la vidéo : vertical/carré = à droite, paysage = centré.
        function fitTikTok() {
            const w = tt.videoWidth, h = tt.videoHeight;
            if (!w || !h) return;
            const a = w / h, VW = window.innerWidth, VH = window.innerHeight;
            const badge = 0.036 * VH, bord = 6;
            const land = a >= 1.1;
            let vw, vh;
            if (land) {
                vw = Math.min(0.5 * VW, (0.8 * VH - badge - bord) * a);
                vh = vw / a;
            } else {
                vh = 0.8 * VH - badge - bord;
                vw = vh * a;
                if (vw > 0.45 * VW) { vw = 0.45 * VW; vh = vw / a; }
            }
            ttBox.style.width = Math.round(vw + bord) + 'px';
            ttBox.style.height = Math.round(vh + badge + bord) + 'px';
            // Changement de disposition SANS animation (la boîte est encore invisible), puis l'entrée en scène.
            ttBox.style.transition = 'none';
            ttBox.classList.toggle('land', land);
            ttBox.classList.toggle('port', !land);
            void ttBox.offsetWidth;
            ttBox.style.transition = '';
        }
        ttBox.classList.add('port');

        function showTikTok(url, source) {
            if (ttCleanup) { clearTimeout(ttCleanup); ttCleanup = null; }
            ttEnding = false;
            ttSkin(source);
            // La vidéo est servie sur un PORT SÉPARÉ (8001) : OBS lui alloue son propre pool de connexions
            // (sinon les overlays saturent le quota et la vidéo ne charge jamais).
            let src = url;
            if (url.charAt(0) === '/') src = location.protocol + '//' + location.hostname + ':8001' + url;
            tt.src = src;
            tt.load();
            ttPlay();
        }

        tt.addEventListener('loadedmetadata', fitTikTok);
        tt.addEventListener('loadeddata', function () { fitTikTok(); ttBox.classList.add('visible'); });
        tt.addEventListener('playing', ttStopRetry);
        tt.addEventListener('ended', ttFinish);
        tt.addEventListener('error', function () { if (tt.getAttribute('src')) ttFinish(); });
        // Si OBS réaffiche la source (changement de scène), on relance la lecture
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden && ttBox.classList.contains('visible') && tt.paused && tt.getAttribute('src')) ttPlay();
        });

        // ───── Événements ─────
        // ?only=so | replay | tiktok : cette page ne gère que ce type de lecture (un widget = une chose dans
        // la scène OBS). Sans paramètre, elle gère tout, comme avant.
        const ONLY = new URLSearchParams(location.search).get('only') || '';
        if (ONLY) {
            const st = document.createElement('style');
            st.textContent = (ONLY === 'tiktok') ? '#wrapper{display:none !important}' : '#tiktok{display:none !important}';
            document.head.appendChild(st);
        }

        function handleEvent(d) {
            if (ONLY && (d.type === 'play_sound' || d.type === 'play_clip' || d.type === 'play_tiktok') && d.mode !== ONLY) return;
            if (d.type === 'play_sound') {
                // On cherche si la balise existe déjà, sinon on la crée DANS la page HTML
                let audioEl = document.getElementById('so-audio');
                if (!audioEl) {
                    audioEl = document.createElement('audio');
                    audioEl.id = 'so-audio';
                    document.body.appendChild(audioEl);
                }
                audioEl.src = d.file;
                audioEl.volume = 0.5;
                audioEl.play().catch(err => console.error("Erreur Audio:", err));
            }

            if (d.type === 'play_clip') {
                const avatar = document.getElementById('avatar');
                avatar.src = d.meta.avatar || '';
                avatar.style.display = d.meta.avatar ? 'block' : 'none';
                document.getElementById('name').textContent = d.meta.name;
                document.getElementById('game').textContent = d.meta.game;
                document.getElementById('date').textContent = d.meta.date;
                document.getElementById('title').textContent = d.meta.title;

                p.style.width = '0%';
                v.isEnding = false;
                v.src = d.url;

                // L'embed n'apparaît qu'une fois le clip réellement chargé (voir listener 'error' plus haut pour le cas où ça échoue).
                v.play().catch(err => console.error(err));
            }

            if (d.type === 'play_tiktok' && d.url) showTikTok(d.url, d.source);
        }

        // 📡 UNE seule connexion SSE partagée entre TOUTES les sources OBS de cette
        // origine (via SharedWorker), au lieu d'une connexion par overlay.
        if (typeof SharedWorker !== 'undefined') {
            try {
                const worker = new SharedWorker('/worker.js');
                worker.port.onmessage = (e) => handleEvent(JSON.parse(e.data));
                worker.port.start();
            } catch (e) { console.error('SharedWorker indisponible :', e); }
        }
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
    <script>(function(){var s=document.createElement('script');s.src=location.protocol+'//'+location.hostname+':8000/static/theme.js?t='+Date.now();document.head.appendChild(s);})();</script>
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

        // Le client ne décide JAMAIS de passer au clip suivant.
        // Il se contente de jouer ce que le serveur lui envoie.
        // Le serveur reçoit un signal quand la vidéo est finie pour enchaîner proprement.
        const notifyEnd = () => {
            if (!v.isEnding) {
                v.isEnding = true;
                fetch('/api/brb/next', { method: 'POST' }).catch(e => {});
            }
        };

        v.addEventListener('timeupdate', () => {
            if (v.duration) {
                p.style.width = (v.currentTime / v.duration * 100) + '%';
            }
        });

        v.addEventListener('ended', notifyEnd);

        // Clip cassé/introuvable : on cache la vidéo et on demande directement le clip suivant.
        v.addEventListener('error', () => {
            t.textContent = '';
            a.textContent = '';
            notifyEnd();
        });

        function handleEvent(d) {
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
        }

        // 📡 UNE seule connexion SSE partagée entre TOUTES les sources OBS de cette
        // origine (via SharedWorker), au lieu d'une connexion par overlay.
        if (typeof SharedWorker !== 'undefined') {
            try {
                const worker = new SharedWorker('/worker.js');
                worker.port.onmessage = (e) => handleEvent(JSON.parse(e.data));
                worker.port.start();
            } catch (e) { console.error('SharedWorker indisponible :', e); }
        }
    </script>
</body>
</html>
    `);
});

app.listen(CONFIG.PORT, '0.0.0.0', () => { console.log(`🚀 RÉGIE CONNECTÉE SUR PORT ${CONFIG.PORT}`); });
