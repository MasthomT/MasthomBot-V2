"""Liste des scènes / sources / filtres OBS pour les menus de l'admin (lecture seule).

server.js est le seul client OBS permanent ; ici on ouvre une connexion obs-websocket (v5) brève : pour les menus
(cache d'une minute) et pour les étapes OBS des automatisations (`run_step`). server.js ne sait pas viser une source
rangée dans un GROUPE (ex. « RECOMPENSES POINTS DE CHAINE »), d'où ces actions faites ici.
"""
import base64
import hashlib
import json
import time

import aiohttp

from app.core.config import settings

MEDIA_KINDS = {"ffmpeg_source", "vlc_source"}
_cache: dict = {"t": 0.0, "data": None}


def _auth(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(hashlib.sha256((password + salt).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()


class _Obs:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def call(self, request_type: str, data: dict | None = None) -> dict:
        self.n += 1
        rid = str(self.n)
        await self.ws.send_str(json.dumps({"op": 6, "d": {"requestType": request_type, "requestId": rid, "requestData": data or {}}}))
        while True:
            msg = json.loads((await self.ws.receive(timeout=5)).data)
            if msg.get("op") == 7 and msg["d"].get("requestId") == rid:
                st = msg["d"].get("requestStatus", {})
                if not st.get("result"):
                    raise RuntimeError(st.get("comment") or request_type)
                return msg["d"].get("responseData") or {}


async def _session(fn):
    url = f"ws://{settings.OBS_HOST}:{settings.OBS_PORT}"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
        async with s.ws_connect(url) as ws:
            hello = json.loads((await ws.receive(timeout=5)).data)["d"]
            ident = {"rpcVersion": 1, "eventSubscriptions": 0}
            if hello.get("authentication"):
                a = hello["authentication"]
                ident["authentication"] = _auth(settings.OBS_PASSWORD, a["salt"], a["challenge"])
            await ws.send_str(json.dumps({"op": 1, "d": ident}))
            ok = json.loads((await ws.receive(timeout=5)).data)
            if ok.get("op") != 2:
                raise RuntimeError("Authentification OBS refusée")
            return await fn(_Obs(ws))


async def catalog(force: bool = False) -> dict:
    """{connected, scenes: [nom], items: {scène: [source]}, media: [source], inputs: [source]}"""
    if not force and _cache["data"] and time.time() - _cache["t"] < 60:
        return _cache["data"]

    async def read(obs: _Obs):
        scenes = [s["sceneName"] for s in reversed((await obs.call("GetSceneList"))["scenes"])]
        items, groups = {}, []
        for sc in scenes:
            lst = (await obs.call("GetSceneItemList", {"sceneName": sc}))["sceneItems"]
            items[sc] = [it["sourceName"] for it in lst]
            groups += [it["sourceName"] for it in lst if it.get("isGroup") and it["sourceName"] not in groups]
        for g in groups:              # sources rangées dans un groupe : le groupe sert de « scène »
            items[g + " (groupe)"] = [it["sourceName"] for it in (await obs.call("GetGroupSceneItemList", {"sceneName": g}))["sceneItems"]]
        inputs = (await obs.call("GetInputList"))["inputs"]
        return {"connected": True, "scenes": scenes, "items": items,
                "media": sorted(i["inputName"] for i in inputs if i.get("inputKind") in MEDIA_KINDS),
                "inputs": sorted(i["inputName"] for i in inputs)}

    try:
        data = await _session(read)
    except Exception as e:
        return _cache["data"] or {"connected": False, "error": str(e), "scenes": [], "items": {}, "media": [], "inputs": []}
    _cache.update(t=time.time(), data=data)
    return data


async def filters(source: str) -> list[str]:
    try:
        return await _session(lambda obs: _filters(obs, source))
    except Exception:
        return []


async def _filters(obs: _Obs, source: str) -> list[str]:
    return [f["filterName"] for f in (await obs.call("GetSourceFilterList", {"sourceName": source}))["filters"]]


# ── Étapes OBS des automatisations ───────────────────────────────────────────

def container(name: str) -> str:
    """« X (groupe) » (libellé des menus) -> « X » (nom OBS)."""
    return name[:-len(" (groupe)")] if name.endswith(" (groupe)") else name


async def run_step(step: dict) -> str:
    """Exécute une étape OBS. Renvoie un court compte rendu ; lève une exception si OBS refuse."""
    kind = step.get("type")

    async def go(obs: _Obs):
        if kind == "scene":
            await obs.call("SetCurrentProgramScene", {"sceneName": step["scene"]})
            return f"scène → {step['scene']}"
        if kind in ("show", "hide"):
            sc = container(step["scene"])
            iid = (await obs.call("GetSceneItemId", {"sceneName": sc, "sourceName": step["source"]}))["sceneItemId"]
            await obs.call("SetSceneItemEnabled", {"sceneName": sc, "sceneItemId": iid, "sceneItemEnabled": kind == "show"})
            if kind == "show" and step.get("source") in (_cache["data"] or {}).get("media", []):
                try:   # vidéo / son : on la relance depuis le début
                    await obs.call("TriggerMediaInputAction", {"inputName": step["source"], "mediaAction": "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"})
                except Exception:
                    pass
            return f"{step['source']} {'affichée' if kind == 'show' else 'masquée'}"
        if kind in ("filter_on", "filter_off"):
            await obs.call("SetSourceFilterEnabled", {"sourceName": step["source"], "filterName": step["filter"], "filterEnabled": kind == "filter_on"})
            return f"filtre {step['filter']} {'activé' if kind == 'filter_on' else 'désactivé'}"
        if kind in ("mute", "unmute"):
            await obs.call("SetInputMute", {"inputName": step["source"], "inputMuted": kind == "mute"})
            return f"{step['source']} {'coupée' if kind == 'mute' else 'rétablie'}"
        raise RuntimeError(f"étape inconnue : {kind}")

    if not (_cache["data"] or {}).get("media"):
        await catalog()
    return await _session(go)
