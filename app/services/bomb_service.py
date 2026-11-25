"""« La Bombe » : une charge de TNT posée sur un viewer au hasard (qui a parlé récemment).

- Lancée par l'étape « Lancer la bombe » d'une récompense (Récompenses › Actions) ou d'une automatisation.
- La cible coupe un fil dans le t'chat : « !coupe rouge ». 6 fils, effets mélangés à chaque bombe :
  désamorce, explose, turbo (x2), +10 s, cadran brouillé, patate chaude (la bombe passe à un autre viewer).
- Explosion ou temps écoulé : timeout de la cible (simulé en test).
- L'overlay /overlay/bombe vient lire l'état par petites requêtes (pas de connexion permanente : OBS sature).
Une seule bombe à la fois ; les suivantes attendent leur tour.
"""
import asyncio
import logging
import random
import time
import unicodedata

logger = logging.getLogger("masthbot.bomb")

START_SECONDS = 30
BOOM_TIMEOUT = 60          # secondes de timeout pour la cible si ça explose
SHOW_RESULT = 7            # secondes d'affichage du résultat avant de disparaître
COLORS = ["rouge", "bleu", "vert", "jaune", "blanc", "violet"]
EFFECTS = ["defuse", "boom", "turbo", "plus", "scramble", "pass"]

_state: dict = {"active": False, "version": 0}
_queue: list[dict] = []
_task: asyncio.Task | None = None


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()


def _remaining() -> float:
    s = _state
    if not s.get("active"):
        return 0.0
    if s.get("result"):
        return max(0.0, s["rem0"])
    return max(0.0, s["rem0"] - (time.time() - s["t0"]) * s["speed"])


def _set_speed(speed: float):
    _state["rem0"], _state["t0"], _state["speed"] = _remaining(), time.time(), speed


def _bump():
    _state["version"] = _state.get("version", 0) + 1


def _log(text: str, kind: str = ""):
    _state.setdefault("log", []).append({"text": text, "kind": kind})
    del _state["log"][:-6]
    _bump()


async def _say(text: str):
    from app.services import alerts_service
    await alerts_service.send_chat(text)


def _pick_target(exclude: set[str]) -> tuple[str, str] | None:
    """(login, pseudo affiché) d'un viewer qui a parlé ces 2 dernières heures."""
    from app.core.config import settings
    from app.services import reward_overlay_service as R
    now = time.time()
    skip = {e.lower() for e in exclude} | {settings.TWITCH_BOT_USERNAME.lower(), settings.TWITCH_CHANNEL.lstrip("#").lower()} | R.BOTS
    pool = [(k, d) for k, (d, t) in R._chatters.items() if now - t < R.CHATTER_WINDOW and k not in skip]
    return random.choice(pool) if pool else None


def state() -> dict:
    s = _state
    if not s.get("active"):
        return {"active": False, "version": s.get("version", 0)}
    return {"active": True, "version": s["version"], "sender": s["sender"], "target": s["target_name"],
            "remaining": round(_remaining(), 2), "speed": s["speed"], "scrambled": s["scrambled"],
            "wires": [{"color": c, "cut": c in s["cut"]} for c in COLORS], "result": s.get("result", ""),
            "log": s.get("log", []), "test": s.get("test", False)}


async def start(sender: str, test: bool = False) -> str:
    """Pose une bombe (ou la met en attente si une autre est en cours). Renvoie un court compte rendu."""
    if _state.get("active"):
        _queue.append({"sender": sender, "test": test})
        return f"bombe en attente ({len(_queue)} avant elle)"
    return await _begin(sender, test)


async def _begin(sender: str, test: bool) -> str:
    global _task
    target = _pick_target({sender})
    if not target:
        await _say(f"💣 {sender} voulait poser une bombe… mais personne n'a parlé dans le t'chat ces 2 dernières heures. Ouf !")
        return "aucune cible (personne n'a parlé récemment)"
    effects = EFFECTS[:]
    random.shuffle(effects)
    version = _state.get("version", 0) + 1
    _state.clear()
    _state.update({"active": True, "version": version, "sender": sender,
                   "target_login": target[0], "target_name": target[1], "rem0": float(START_SECONDS), "t0": time.time(),
                   "speed": 1.0, "scrambled": False, "cut": [], "map": dict(zip(COLORS, effects)), "result": "",
                   "log": [], "test": test})
    _log(f"{sender} pose une bombe sur {target[1]} !")
    await _say(f"💣 {sender} a posé une bombe sur @{target[1]} ! Tu as {START_SECONDS} secondes pour couper le bon fil : "
               f"!coupe rouge, bleu, vert, jaune, blanc ou violet. Le t'chat peut t'aider… ou te mentir 😈")
    logger.info(f"💣 [BOMBE] {sender} → {target[1]} ({'test' if test else 'live'}) : {_state['map']}")
    _task = asyncio.create_task(_watch())
    return f"bombe posée sur {target[1]}"


async def _watch():
    """Surveille le compte à rebours ; à la fin du jeu, laisse le résultat affiché puis passe à la bombe suivante."""
    try:
        while _state.get("active") and not _state.get("result"):
            if _remaining() <= 0:
                await _explode("Le temps est écoulé !")
                break
            await asyncio.sleep(0.2)
        await asyncio.sleep(SHOW_RESULT)
    except asyncio.CancelledError:
        return
    except Exception as e:
        logger.error(f"❌ [BOMBE] {e}")
    _state.update({"active": False})
    _bump()
    if _queue:
        nxt = _queue.pop(0)
        await asyncio.sleep(2)
        await _begin(nxt["sender"], nxt["test"])


async def _explode(why: str):
    s = _state
    _set_speed(0)
    s["result"] = "boom"
    who, login = s["target_name"], s["target_login"]
    _log(f"{why} BOUM ! {who} prend {BOOM_TIMEOUT} s de timeout.", "boom")
    await _say(f"💥 BOUM ! {why} @{who} prend {BOOM_TIMEOUT} secondes de timeout. Repose en paix 🪦")
    if s.get("test"):
        logger.info(f"💣 [BOMBE] test : timeout de {who} simulé")
        return
    try:
        from app.services.automation_service import _timeout
        await _timeout(login, BOOM_TIMEOUT, "La Bombe 💣")
    except Exception as e:
        logger.warning(f"⚠️ [BOMBE] Timeout de {who} impossible : {e}")


async def on_chat(login: str, display: str, content: str) -> bool:
    """« !coupe <couleur> » écrit par la cible. Renvoie True si le message a été pris en compte."""
    s = _state
    if not s.get("active") or s.get("result") or login.lower() != s["target_login"]:
        return False
    parts = content.split()
    color = _norm(parts[1]) if len(parts) > 1 else ""
    if color not in COLORS:
        return False
    if color in s["cut"]:
        await _say(f"✂️ @{display}, le fil {color} est déjà coupé !")
        return True
    s["cut"].append(color)
    effect, who = s["map"][color], s["target_name"]
    if effect == "defuse":
        left = round(_remaining())
        _set_speed(0)
        s["result"] = "defused"
        _log(f"{who} coupe le {color} : bombe désamorcée avec {left} s restantes !", "ok")
        await _say(f"✅ @{who} coupe le fil {color}… la bombe est DÉSAMORCÉE avec {left} secondes restantes ! Bravo 🎉")
    elif effect == "boom":
        await _explode(f"{who} a coupé le fil {color}…")
    elif effect == "turbo":
        _set_speed(2.0)
        _log(f"{who} coupe le {color} : le tic-tac s'emballe !", "warn")
        await _say(f"⏩ Fil {color} : le compte à rebours s'emballe, il va deux fois plus vite !")
    elif effect == "plus":
        _state["rem0"] = _remaining() + 10
        _state["t0"] = time.time()
        _log(f"{who} coupe le {color} : +10 secondes, ouf.")
        await _say(f"➕ Fil {color} : +10 secondes de sursis !")
    elif effect == "scramble":
        s["scrambled"] = True
        _log(f"{who} coupe le {color} : le cadran devient fou !", "warn")
        await _say(f"🌀 Fil {color} : le cadran est brouillé, plus moyen de lire le temps !")
    elif effect == "pass":
        nxt = _pick_target({s["sender"], s["target_login"]})
        if nxt:
            s["target_login"], s["target_name"] = nxt
            _log(f"{who} coupe le {color} : la bombe saute dans les mains de {nxt[1]} !", "warn")
            await _say(f"🔁 Fil {color} : patate chaude ! La bombe saute dans les mains de @{nxt[1]}, à toi de couper !")
        else:
            _state["rem0"] = _remaining() + 10
            _state["t0"] = time.time()
            _log(f"{who} coupe le {color} : personne pour la récupérer… +10 s.")
            await _say(f"🔁 Fil {color} : la bombe voulait changer de mains, mais personne n'est là. +10 secondes !")
    _bump()
    return True
