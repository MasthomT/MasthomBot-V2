"""Automatisations : « quand ce déclencheur arrive (et que les conditions sont remplies), le bot écrit ce message dans le t'chat ».

Chaque automatisation créée dans /admin/automatisations a : un déclencheur (raid lancé, follow, sub, bits, récompense,
début / fin de live…), des conditions (seuil, titre de récompense), un ou plusieurs messages (un est tiré au hasard),
un délai et une attente minimale entre deux envois.

Les événements arrivent d'EventSub (`on_eventsub`) ; chaque déclencheur y est traduit en variables ({user}, {viewers}…).
Pour ajouter un déclencheur : une entrée dans TRIGGERS + sa traduction dans `translate`.
"""
import asyncio
import json
import logging
import random
import time

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.automation")

DOUBLON = "Les alertes (page Alertes) envoient déjà un message dans le t'chat pour cet événement : évite de doubler."

TRIGGERS = {
    "raid_out": {"group": "Raids", "label": "Raid lancé (c'est toi qui raides)", "icon": "fa-rocket",
                 "description": "Au moment où le raid que TU lances part vers une autre chaîne.",
                 "vars": {"channel": "nom de la chaîne raidée", "login": "adresse de la chaîne (twitch.tv/…)", "viewers": "viewers emmenés"},
                 "sample": {"channel": "ChaîneTest", "login": "chainetest", "viewers": 12},
                 "value": ("viewers", "Seulement à partir de (viewers)"), "text": None,
                 "default": "🚀 On part en raid chez {channel} avec {viewers} viewers ! Suivez-nous sur https://twitch.tv/{login} et mettez le feu au chat ! 🔥"},
    "raid_in": {"group": "Raids", "label": "Raid reçu", "icon": "fa-person-walking-arrow-right",
                "description": "Quand une autre chaîne te raide.", "note": DOUBLON,
                "vars": {"user": "chaîne qui raide", "viewers": "viewers emmenés"}, "sample": {"user": "RaiderTest", "viewers": 25},
                "value": ("viewers", "Seulement à partir de (viewers)"), "text": None,
                "default": "🎉 Bienvenue aux {viewers} raiders de {user} ! Installez-vous, ça va être chouette ! 💜"},
    "follow": {"group": "Communauté", "label": "Nouveau follow", "icon": "fa-heart", "description": "Quelqu'un te suit.", "note": DOUBLON,
               "vars": {"user": "pseudo du nouveau follower"}, "sample": {"user": "NouveauTest"}, "value": None, "text": None,
               "default": "💜 Merci pour le follow {user} ! Bienvenue dans la team !"},
    "sub": {"group": "Communauté", "label": "Abonnement / réabonnement", "icon": "fa-star", "description": "Un nouvel abonné ou un réabonnement.", "note": DOUBLON,
            "vars": {"user": "pseudo", "months": "mois cumulés", "tier": "palier (1, 2 ou 3)"},
            "sample": {"user": "AbonneTest", "months": 3, "tier": 1}, "value": ("months", "Seulement à partir de (mois cumulés)"), "text": None,
            "default": "🌟 Merci {user} pour l'abonnement ({months} mois) ! 💜"},
    "subgift": {"group": "Communauté", "label": "Subs offerts", "icon": "fa-gift", "description": "Quelqu'un offre des abonnements.", "note": DOUBLON,
                "vars": {"user": "donateur", "count": "nombre de subs offerts", "tier": "palier"},
                "sample": {"user": "DonateurTest", "count": 5, "tier": 1}, "value": ("count", "Seulement à partir de (subs offerts)"), "text": None,
                "default": "🎁 {user} offre {count} sub(s) à la communauté ! Merci énormément ! 💜"},
    "cheer": {"group": "Communauté", "label": "Bits (cheer)", "icon": "fa-gem", "description": "Quelqu'un envoie des bits.", "note": DOUBLON,
              "vars": {"user": "pseudo", "bits": "nombre de bits", "message": "message accompagnant les bits"},
              "sample": {"user": "BitsTest", "bits": 500, "message": "GG !"}, "value": ("bits", "Seulement à partir de (bits)"), "text": None,
              "default": "💎 Merci {user} pour les {bits} bits ! 💜"},
    "reward": {"group": "Points de chaîne", "label": "Récompense de points de chaîne", "icon": "fa-trophy",
               "description": "Quand un viewer prend une récompense (toutes, ou une seule en donnant son titre exact).",
               "vars": {"user": "pseudo", "reward": "titre de la récompense", "input": "message écrit par le viewer", "cost": "prix en points"},
               "sample": {"user": "ViewerTest", "reward": "Hydrate-toi", "input": "", "cost": 200},
               "value": ("cost", "Seulement à partir de (points)"), "text": ("reward", "Titre exact de la récompense (vide = toutes)"),
               "default": "🎯 {user} a pris « {reward} » !"},
    "ban": {"group": "Modération", "label": "Sanction (ban / timeout)", "icon": "fa-gavel", "description": "Quelqu'un est banni ou mis en timeout.",
            "vars": {"user": "pseudo sanctionné", "kind": "Ban ou Timeout", "mod": "qui a sanctionné", "reason": "raison"},
            "sample": {"user": "TrollTest", "kind": "Timeout", "mod": "ModoTest", "reason": "spam"}, "value": None, "text": None,
            "default": "🔨 {user} : {kind} par {mod}."},
    "mod_added": {"group": "Modération", "label": "Nouveau modérateur", "icon": "fa-user-shield", "description": "Quelqu'un devient modérateur.",
                  "vars": {"user": "pseudo"}, "sample": {"user": "ModoTest"}, "value": None, "text": None,
                  "default": "🛡️ {user} rejoint l'équipe de modération ! Merci !"},
    "mod_removed": {"group": "Modération", "label": "Modérateur retiré", "icon": "fa-user-slash", "description": "Quelqu'un n'est plus modérateur.",
                    "vars": {"user": "pseudo"}, "sample": {"user": "ModoTest"}, "value": None, "text": None,
                    "default": "🛡️ {user} n'est plus modérateur."},
    "hype_start": {"group": "Live", "label": "Train de la Hype : début", "icon": "fa-train", "description": "Un Hype Train démarre.",
                   "vars": {"level": "niveau"}, "sample": {"level": 1}, "value": None, "text": None,
                   "default": "🚂 Le Hype Train démarre ! Allez, on accélère ! 🔥"},
    "hype_end": {"group": "Live", "label": "Train de la Hype : fin", "icon": "fa-flag-checkered", "description": "Un Hype Train se termine.",
                 "vars": {"level": "niveau atteint"}, "sample": {"level": 4}, "value": ("level", "Seulement à partir du niveau"), "text": None,
                 "default": "🏁 Fin du Hype Train : niveau {level} ! GG tout le monde ! 💜"},
    "stream_online": {"group": "Live", "label": "Début de live", "icon": "fa-circle-play", "description": "Le live démarre.",
                      "vars": {}, "sample": {}, "value": None, "text": None, "default": "🔴 C'est parti, le live commence ! Installez-vous ! 💜"},
    "stream_offline": {"group": "Live", "label": "Fin de live", "icon": "fa-circle-stop", "description": "Le live se termine.",
                       "vars": {}, "sample": {}, "value": None, "text": None, "default": "👋 Fin du live, merci d'être passés ! À bientôt ! 💜"},
}

_ready = False
_last_fire: dict[int, float] = {}
_recent_sub: dict[str, float] = {}


async def _ensure():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS automation_rules (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL DEFAULT '', enabled BOOLEAN NOT NULL DEFAULT TRUE,
            trigger TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}', created_at TIMESTAMP NOT NULL DEFAULT NOW())""")
        await db.execute("""CREATE TABLE IF NOT EXISTS automation_log (
            id SERIAL PRIMARY KEY, ts TIMESTAMP NOT NULL DEFAULT NOW(), key TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '')""")
        await db.execute("CREATE TABLE IF NOT EXISTS automations (key TEXT PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}')")
        c = await db.execute("SELECT 1 FROM automations WHERE key = '_seeded'")
        if not await c.fetchone():
            # Reprise de la première version (un seul événement « raid lancé ») : elle devient la première automatisation
            c = await db.execute("SELECT data FROM automations WHERE key = 'raid_out'")
            row = await c.fetchone()
            try:
                old = json.loads(row["data"]) if row else {}
            except Exception:
                old = {}
            base = _defaults("raid_out")
            base.update({k: v for k, v in old.items() if k in base})
            enabled = bool(old.get("enabled", True))
            await db.execute("INSERT INTO automation_rules (name, enabled, trigger, data) VALUES ($1, $2, 'raid_out', $3)",
                             ("Message quand je lance un raid", enabled, json.dumps(base, ensure_ascii=False)))
            await db.execute("INSERT INTO automations (key, data) VALUES ('_seeded', '{}')")
    _ready = True


def _defaults(trigger: str) -> dict:
    t = TRIGGERS[trigger]
    # mode : « all » = tous les messages à la suite (espacés de `gap` secondes), « random » = un seul tiré au hasard
    return {"messages": [t["default"]], "mode": "all", "gap": 1.5, "delay": 1.0, "cooldown": 30, "min_value": 0, "text_filter": ""}


def _row_to_rule(r) -> dict:
    try:
        data = json.loads(r["data"])
    except Exception:
        data = {}
    rule = _defaults(r["trigger"]) if r["trigger"] in TRIGGERS else {"messages": [], "mode": "all", "gap": 1.5, "delay": 1.0, "cooldown": 30, "min_value": 0, "text_filter": ""}
    rule.update({k: v for k, v in data.items() if k in rule})
    rule.update({"id": r["id"], "name": r["name"], "enabled": bool(r["enabled"]), "trigger": r["trigger"]})
    return rule


async def list_rules() -> list[dict]:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT id, name, enabled, trigger, data FROM automation_rules ORDER BY id")
        return [_row_to_rule(r) for r in await c.fetchall()]


def catalog() -> list[dict]:
    return [{"key": k, "group": t["group"], "label": t["label"], "icon": t["icon"], "description": t["description"],
             "note": t.get("note", ""), "vars": t["vars"], "default": t["default"],
             "value": {"key": t["value"][0], "label": t["value"][1]} if t["value"] else None,
             "text": {"key": t["text"][0], "label": t["text"][1]} if t["text"] else None} for k, t in TRIGGERS.items()]


def clean_rule(raw: dict) -> dict:
    trigger = raw.get("trigger")
    if trigger not in TRIGGERS:
        raise ValueError("Déclencheur inconnu.")
    name = str(raw.get("name") or "").strip()[:80] or TRIGGERS[trigger]["label"]
    msgs = [str(m).strip()[:450] for m in (raw.get("messages") or []) if str(m).strip()]
    if not msgs:
        raise ValueError("Écris au moins un message (ou désactive l'automatisation).")
    if len(msgs) > 10:
        raise ValueError("10 messages au maximum.")
    mode = raw.get("mode", "all")
    if mode not in ("all", "random"):
        raise ValueError("Mode d'envoi inconnu.")
    try:
        gap = float(raw.get("gap", 1.5))
        delay = float(raw.get("delay", 1))
        cooldown = int(raw.get("cooldown", 30))
        min_value = int(raw.get("min_value", 0) or 0)
    except (TypeError, ValueError):
        raise ValueError("Délai, attente et seuil doivent être des nombres.")
    if not 0 <= gap <= 30 or not 0 <= delay <= 120 or not 0 <= cooldown <= 86400 or not 0 <= min_value <= 10_000_000:
        raise ValueError("Valeur hors limites (délai ≤ 120 s, attente ≤ 24 h).")
    return {"name": name, "enabled": bool(raw.get("enabled", True)), "trigger": trigger,
            "data": {"messages": msgs, "mode": mode, "gap": gap, "delay": delay, "cooldown": cooldown, "min_value": min_value,
                     "text_filter": str(raw.get("text_filter") or "").strip()[:100]}}


async def create_rule(trigger: str, name: str = "") -> dict:
    await _ensure()
    if trigger not in TRIGGERS:
        raise ValueError("Déclencheur inconnu.")
    name = (name or "").strip()[:80] or TRIGGERS[trigger]["label"]
    async with get_db_connection() as db:
        c = await db.execute("INSERT INTO automation_rules (name, enabled, trigger, data) VALUES ($1, TRUE, $2, $3) RETURNING id",
                             (name, trigger, json.dumps(_defaults(trigger), ensure_ascii=False)))
        row = await c.fetchone()
    return (await get_rule(row["id"]))


async def get_rule(rule_id: int) -> dict | None:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT id, name, enabled, trigger, data FROM automation_rules WHERE id = $1", (rule_id,))
        r = await c.fetchone()
    return _row_to_rule(r) if r else None


async def save_rule(rule_id: int, raw: dict) -> dict:
    clean = clean_rule(raw)
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("UPDATE automation_rules SET name = $1, enabled = $2, trigger = $3, data = $4 WHERE id = $5",
                         (clean["name"], clean["enabled"], clean["trigger"], json.dumps(clean["data"], ensure_ascii=False), rule_id))
    return await get_rule(rule_id)


async def delete_rule(rule_id: int):
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("DELETE FROM automation_rules WHERE id = $1", (rule_id,))


async def duplicate_rule(rule_id: int) -> dict | None:
    r = await get_rule(rule_id)
    if not r:
        return None
    async with get_db_connection() as db:
        c = await db.execute("INSERT INTO automation_rules (name, enabled, trigger, data) VALUES ($1, FALSE, $2, $3) RETURNING id",
                             ((r["name"] + " (copie)")[:80], r["trigger"], json.dumps(
                                 {k: r[k] for k in ("messages", "mode", "gap", "delay", "cooldown", "min_value", "text_filter")}, ensure_ascii=False)))
        row = await c.fetchone()
    return await get_rule(row["id"])


# ── Envoi ────────────────────────────────────────────────────────────────────

def render(template: str, values: dict) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", str(v))
    return out


async def get_log(limit: int = 15) -> list[dict]:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT ts, key, detail FROM automation_log ORDER BY id DESC LIMIT $1", (limit,))
        rows = [dict(r) for r in await c.fetchall()]
    for r in rows:
        r["ts"] = r["ts"].strftime("%d/%m %H:%M") if r.get("ts") else ""
    return rows


async def _log(label: str, detail: str):
    try:
        async with get_db_connection() as db:
            await db.execute("INSERT INTO automation_log (key, detail) VALUES ($1, $2)", (label[:80], detail[:400]))
            await db.execute("DELETE FROM automation_log WHERE id NOT IN (SELECT id FROM automation_log ORDER BY id DESC LIMIT 80)")
    except Exception as e:
        logger.error(f"❌ [AUTOMATISATION] Journal : {e}")


def _matches(rule: dict, values: dict) -> bool:
    t = TRIGGERS[rule["trigger"]]
    if t["value"] and int(values.get(t["value"][0], 0) or 0) < int(rule["min_value"] or 0):
        return False
    if t["text"] and rule["text_filter"]:
        if str(values.get(t["text"][0], "")).strip().lower() != rule["text_filter"].strip().lower():
            return False
    return True


async def _send(rule: dict, values: dict, test: bool = False) -> bool:
    """Envoie les messages de la règle : tous à la suite (mode « all ») ou un seul au hasard (mode « random »)."""
    from app.services import alerts_service
    messages = list(rule["messages"]) if rule.get("mode", "all") == "all" else [random.choice(rule["messages"])]
    ok_all = True
    for i, template in enumerate(messages):
        if i:
            await asyncio.sleep(float(rule.get("gap", 1.5)))      # petit écart : Twitch limite le rythme des messages
        text = render(template, values)
        sent = await alerts_service.send_chat(text)
        ok_all = ok_all and sent
        await _log(rule["name"], ("test · " if test else "") + ("" if sent else "NON ENVOYÉ (bot non connecté au chat) · ") + text)
        logger.info(f"⚡ [AUTOMATISATION] « {rule['name']} » → {'envoyé' if sent else 'échec'} : {text}")
    return ok_all


async def dispatch(trigger: str, values: dict):
    """Déclenche toutes les automatisations actives de ce déclencheur dont les conditions sont remplies."""
    if trigger not in TRIGGERS:
        return
    for rule in await list_rules():
        if rule["trigger"] != trigger or not rule["enabled"] or not _matches(rule, values):
            continue
        if time.time() - _last_fire.get(rule["id"], 0) < rule["cooldown"]:
            continue
        _last_fire[rule["id"]] = time.time()
        try:
            if rule["delay"] > 0:
                await asyncio.sleep(rule["delay"])
            await _send(rule, values)
        except Exception as e:
            logger.error(f"❌ [AUTOMATISATION] « {rule['name']} » : {e}")


async def test_rule(raw: dict) -> dict:
    """Envoie vraiment le premier message dans le t'chat avec des valeurs d'exemple (règle telle qu'elle est éditée)."""
    clean = clean_rule(raw)
    rule = dict(clean["data"], name=clean["name"], trigger=clean["trigger"])
    values = TRIGGERS[clean["trigger"]]["sample"]
    sent = await _send(rule, values, test=True)
    n = len(rule["messages"]) if rule.get("mode") == "all" else 1
    return {"ok": sent, "message": (f"{n} message(s) envoyé(s) dans le t'chat avec des valeurs d'exemple.") if sent else "Le bot n'est pas connecté au chat."}


# ── Traduction des événements EventSub ───────────────────────────────────────

def translate(sub_type: str, event: dict, broadcaster_id: str) -> tuple[str, dict] | None:
    g = event.get
    if sub_type == "channel.raid":
        if str(g("from_broadcaster_user_id")) == str(broadcaster_id):
            login = g("to_broadcaster_user_login") or g("to_broadcaster_user_name", "")
            return "raid_out", {"channel": g("to_broadcaster_user_name") or login, "login": login, "viewers": int(g("viewers", 0) or 0)}
        return "raid_in", {"user": g("from_broadcaster_user_name", "Inconnu"), "viewers": int(g("viewers", 0) or 0)}
    if sub_type == "channel.follow":
        return "follow", {"user": g("user_name", "Inconnu")}
    if sub_type in ("channel.subscribe", "channel.subscription.message"):
        if g("is_gift"):
            return None
        user = g("user_name", "Inconnu")
        now = time.time()                                  # Twitch envoie parfois « subscribe » PUIS « subscription.message »
        if now - _recent_sub.get(str(g("user_id")), 0) < 60:
            return None
        _recent_sub[str(g("user_id"))] = now
        months = g("cumulative_months") or 1
        return "sub", {"user": user, "months": int(months), "tier": str(g("tier", "1000"))[:1]}
    if sub_type == "channel.subscription.gift":
        if g("is_anonymous"):
            return None
        return "subgift", {"user": g("user_name", "Anonyme"), "count": int(g("total", 1) or 1), "tier": str(g("tier", "1000"))[:1]}
    if sub_type == "channel.cheer":
        return "cheer", {"user": "Anonyme" if g("is_anonymous") else g("user_name", "Anonyme"), "bits": int(g("bits", 0) or 0),
                         "message": g("message", "")}
    if sub_type == "channel.channel_points_custom_reward_redemption.add":
        rw = g("reward") or {}
        return "reward", {"user": g("user_name", "Inconnu"), "reward": rw.get("title", ""), "input": g("user_input", "") or "",
                          "cost": int(rw.get("cost", 0) or 0)}
    if sub_type == "channel.ban":
        return "ban", {"user": g("user_name", "Inconnu"), "kind": "Ban" if g("is_permanent") else "Timeout",
                       "mod": g("moderator_user_name", "Modo"), "reason": g("reason") or "aucune raison"}
    if sub_type == "channel.moderator.add":
        return "mod_added", {"user": g("user_name") or g("user_login", "Inconnu")}
    if sub_type == "channel.moderator.remove":
        return "mod_removed", {"user": g("user_name") or g("user_login", "Inconnu")}
    if sub_type == "channel.hype_train.begin":
        return "hype_start", {"level": int(g("level", 1) or 1)}
    if sub_type == "channel.hype_train.end":
        return "hype_end", {"level": int(g("level", 1) or 1)}
    if sub_type == "stream.online":
        return "stream_online", {}
    if sub_type == "stream.offline":
        return "stream_offline", {}
    return None


async def on_eventsub(sub_type: str, event: dict, broadcaster_id: str):
    """Appelé pour chaque notification EventSub (en tâche de fond : ne ralentit jamais le traitement normal)."""
    try:
        tr = translate(sub_type, event or {}, broadcaster_id)
        if tr:
            await dispatch(tr[0], tr[1])
    except Exception as e:
        logger.error(f"❌ [AUTOMATISATION] {sub_type} : {e}")
