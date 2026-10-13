#!/usr/bin/env node
/**
 * Liste TOUTES les sources Navigateur (browser_source) d'OBS : nom, lien, taille, scènes où elles sont utilisées.
 * Lecture seule : le script ne modifie rien dans OBS.
 *
 * Usage (depuis la racine du projet) :
 *   node scripts/obs_web_sources.js                 # tableau lisible
 *   node scripts/obs_web_sources.js --csv > sources.csv
 *   node scripts/obs_web_sources.js --json > sources.json
 *   node scripts/obs_web_sources.js --md > sources.md
 *
 * Connexion : mêmes variables que server.js (.env) — OBS_HOST (127.0.0.1), OBS_PORT (4455),
 * OBS_PASSWORD (ou OBS_WEBSOCKET_PASSWORD). Dans OBS : Outils > Paramètres du serveur WebSocket.
 * On peut aussi les passer en ligne de commande : --host 192.168.1.50 --port 4455 --password xxx
 */
const path = require('path');
const { OBSWebSocket } = require(path.join(__dirname, '..', 'node_modules', 'obs-websocket-js'));
require(path.join(__dirname, '..', 'node_modules', 'dotenv')).config({ path: path.join(__dirname, '..', '.env'), quiet: true });

const argv = process.argv.slice(2);
const flag = (name) => argv.includes('--' + name);
const opt = (name, fallback) => {
    const i = argv.indexOf('--' + name);
    return i !== -1 && argv[i + 1] ? argv[i + 1] : fallback;
};

const host = opt('host', process.env.OBS_HOST || '127.0.0.1');
const port = opt('port', process.env.OBS_PORT || '4455');
const password = opt('password', process.env.OBS_PASSWORD || process.env.OBS_WEBSOCKET_PASSWORD || undefined);

const log = (...a) => console.error(...a); // stdout reste propre pour --csv / --json

async function main() {
    const obs = new OBSWebSocket();
    try {
        const timeout = new Promise((_, rej) => setTimeout(() => rej(new Error('délai dépassé (10 s) — OBS éteint ou adresse injoignable')), 10000));
        await Promise.race([obs.connect(`ws://${host}:${port}`, password), timeout]);
    } catch (e) {
        log(`❌ Connexion à OBS impossible (ws://${host}:${port}) : ${e.message}`);
        log('   Vérifie qu\'OBS est ouvert, que le serveur WebSocket est activé et que le mot de passe est bon.');
        process.exit(1);
    }

    // 1) Toutes les sources navigateur (une entrée par source, même si elle est dans plusieurs scènes)
    const { inputs } = await obs.call('GetInputList', { inputKind: 'browser_source' });
    const byName = new Map();
    for (const input of inputs) {
        let s = {};
        try { s = (await obs.call('GetInputSettings', { inputName: input.inputName })).inputSettings; } catch (_) {}
        byName.set(input.inputName, {
            name: input.inputName,
            url: s.is_local_file ? (s.local_file || '') : (s.url || ''),
            localFile: !!s.is_local_file,
            width: s.width ?? null,
            height: s.height ?? null,
            fps: s.fps ?? null,
            customCss: s.css ? true : false,
            shutdownWhenHidden: !!s.shutdown,
            restartWhenActive: !!s.restart_when_active,
            scenes: [],
        });
    }

    // 2) Dans quelles scènes (et groupes) chaque source apparaît, et si elle y est visible
    const { scenes } = await obs.call('GetSceneList');
    const visit = async (sceneName, label, listFn) => {
        let items = [];
        try { items = await listFn(); } catch (_) { return; }
        for (const it of items) {
            const src = byName.get(it.sourceName);
            if (src) src.scenes.push({ scene: label, enabled: !!it.sceneItemEnabled });
            if (it.isGroup) {
                await visit(sceneName, `${label} › ${it.sourceName}`,
                    async () => (await obs.call('GetGroupSceneItemList', { sceneName: it.sourceName })).sceneItems);
            }
        }
    };
    for (const sc of scenes) {
        await visit(sc.sceneName, sc.sceneName,
            async () => (await obs.call('GetSceneItemList', { sceneName: sc.sceneName })).sceneItems);
    }
    await obs.disconnect();

    const rows = [...byName.values()].sort((a, b) => a.name.localeCompare(b.name, 'fr'));
    output(rows, scenes.length);
}

function sceneText(src) {
    if (!src.scenes.length) return '(dans aucune scène)';
    return src.scenes.map(s => s.scene + (s.enabled ? '' : ' (masquée)')).join(' | ');
}

function output(rows, sceneCount) {
    if (flag('json')) {
        console.log(JSON.stringify(rows, null, 2));
        return;
    }
    if (flag('csv')) {
        const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
        console.log(['Nom', 'Lien', 'Largeur', 'Hauteur', 'FPS', 'Scènes'].map(esc).join(';'));
        for (const r of rows) console.log([r.name, r.url, r.width, r.height, r.fps, sceneText(r)].map(esc).join(';'));
        return;
    }
    if (flag('md')) {
        console.log('| Nom | Lien | Taille | Scènes |\n|---|---|---|---|');
        for (const r of rows) console.log(`| ${r.name} | ${r.url} | ${r.width}×${r.height} | ${sceneText(r)} |`);
        return;
    }
    console.log(`\n${rows.length} source(s) navigateur dans ${sceneCount} scène(s)\n${'─'.repeat(60)}`);
    rows.forEach((r, i) => {
        console.log(`${String(i + 1).padStart(2)}. ${r.name}`);
        console.log(`    Lien   : ${r.url || '(vide)'}${r.localFile ? '  [fichier local]' : ''}`);
        console.log(`    Taille : ${r.width}×${r.height} @ ${r.fps ?? '?'} fps${r.customCss ? ' · CSS personnalisé' : ''}`
            + `${r.shutdownWhenHidden ? ' · coupée si masquée' : ''}`);
        console.log(`    Scènes : ${sceneText(r)}`);
    });
    console.log('');
}

main().catch((e) => { log('❌ Erreur :', e.message); process.exit(1); });
