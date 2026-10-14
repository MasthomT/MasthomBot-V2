"""
Alertes à l'écran (follow, sub, subgift, bits, raid) façon « boîte d'alertes » + screamer.

Chaque type d'événement a une ou plusieurs VARIANTES (nom, condition de montant, durée, effet de fond,
média image / gif / vidéo déplaçable, texte stylé déplaçable, animations d'entrée / sortie, son).
Au moment de l'événement, la variante dont la condition correspond est envoyée à l'overlay /overlay/events.
Réglages éditables dans /admin/alerts.
"""
import json
import logging
import os
import random
import re
import time
import uuid

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.alerts")

KINDS = ["follow", "sub", "subgift", "bits", "raid", "hype_start", "hype_end", "hype_record", "goal_start", "goal_end"]
KIND_LABELS = {"follow": "Follow", "sub": "Sub / Resub", "subgift": "Subs offerts", "bits": "Bits", "raid": "Raid",
               "hype_start": "Train de la Hype lancé", "hype_end": "Train de la Hype terminé",
               "hype_record": "Nouveau record de train de la Hype",
               "goal_start": "Objectif lancé", "goal_end": "Objectif atteint"}
KIND_GROUPS = {"follow": "Chaîne", "sub": "Chaîne", "subgift": "Chaîne", "bits": "Chaîne", "raid": "Chaîne",
               "hype_start": "Trains de la Hype", "hype_end": "Trains de la Hype", "hype_record": "Trains de la Hype",
               "goal_start": "Objectifs", "goal_end": "Objectifs"}
KIND_VARS = {
    "follow": ["user"], "sub": ["user", "months"], "subgift": ["user", "count"],
    "bits": ["user", "bits"], "raid": ["user", "viewers"],
    "hype_start": ["user", "level", "total", "goal"], "hype_end": ["user", "level", "total"],
    "hype_record": ["user", "level", "total"],
    "goal_start": ["description", "type", "current", "target"], "goal_end": ["description", "type", "current", "target"],
}
# montant sur lequel porte la condition « à partir de / jusqu'à » (follow : aucun)
AMOUNT_FIELD = {"sub": "months", "subgift": "count", "bits": "bits", "raid": "viewers",
                "hype_end": "level", "hype_record": "level", "goal_start": "target", "goal_end": "target"}
AMOUNT_LABEL = {"sub": "mois cumulés", "subgift": "subs offerts", "bits": "bits", "raid": "viewers",
                "hype_end": "niveau", "hype_record": "niveau", "goal_start": "cible de l'objectif", "goal_end": "cible de l'objectif"}
ALL_VARS = ["user", "months", "count", "bits", "viewers", "level", "total", "goal", "description", "current", "target", "type"]

EFFECTS = {"none": "Aucun", "ghost": "Fantôme qui passe", "bats": "Nuée de chauves-souris",
           "lightning": "Éclair", "confetti": "Confettis / bonbons", "snow": "Neige", "hearts": "Cœurs"}
ANIM_IN = {"none": "Aucune", "fade": "Fondu", "zoom": "Zoom", "bounce": "Rebond", "slide-up": "Glisse du bas",
           "slide-down": "Glisse du haut", "slide-left": "Glisse de la droite", "slide-right": "Glisse de la gauche",
           "shake": "Secousse", "spin": "Rotation", "typewriter": "Machine à écrire (texte)", "wave": "Lettres en vague (texte)"}
ANIM_OUT = {"none": "Aucune", "fade": "Fondu", "zoom-out": "Rétrécit", "slide-up": "Part vers le haut",
            "slide-down": "Part vers le bas", "slide-left": "Part vers la gauche", "slide-right": "Part vers la droite"}
ALIGNS = ("left", "center", "right")
WEIGHTS = ("100", "200", "300", "400", "500", "600", "700", "800", "900")

IMAGE_EXTS = {".gif", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}
SOUND_EXTS = {".mp3", ".wav", ".ogg"}
IMAGES_DIR = "static/commands/images"
SOUNDS_DIR = "static/commands/sounds"

_FONT_RE = re.compile(r"^[A-Za-z0-9 ]{0,40}$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_VARIANTS = 30

DEFAULT_SCREAMER = {
    "enabled": False,            # désactivé tant que le streamer ne l'a pas activé : c'est une surprise !
    "image": "", "sound": "", "volume": 1.0,
    "duration": 1.8,
    "flash": True,               # deux éclairs blancs rapides (jamais de stroboscope)
    "shake": True,
    "chance": 0.0,               # % de chance qu'un événement déclenche un screamer à la place de l'alerte
    "reward_title": "Screamer",  # récompense de points de chaîne qui le déclenche ('' = aucune)
    "cooldown": 60,
}

_ready = False
_last_screamer = 0.0


# ── Variantes : modèle, valeurs par défaut, nettoyage ────────────────────────

def new_variant(kind: str, **over) -> dict:
    """Variante complète avec toutes ses valeurs par défaut, puis surcharges."""
    v = {
        "id": "v_" + uuid.uuid4().hex[:8], "kind": kind, "name": "Nouvelle variante", "enabled": True,
        "min_amount": 1, "max_amount": 0,          # max 0 = pas de limite haute
        "duration": 6.0, "effect": "none",
        "sound": "", "volume": 0.8, "sound_delay": 0,          # délais en secondes après le début de l'alerte
        "chat_enabled": True, "chat_message": DEFAULT_CHAT.get(kind, ""),   # message envoyé dans le t'chat
        "media": {"file": "", "emoji": "", "delay": 0, "x": 50, "y": 34, "w": 26, "opacity": 1.0,
                  "anim_in": "zoom", "anim_out": "fade", "loop": True, "video_sound": False,
                  # rognage (en % de l'image d'origine) et découpe d'une vidéo (secondes ; fin 0 = jusqu'au bout)
                  "crop_t": 0, "crop_r": 0, "crop_b": 0, "crop_l": 0, "trim_start": 0, "trim_end": 0},
        "text": {"template": "{user}", "font": "", "delay": 0, "fit": "shrink", "min_size": 36, "size": 84, "weight": "900", "color": "#ffffff",
                 "highlight": "", "stroke": "#000000", "stroke_w": 4, "glow": "", "align": "center",
                 "x": 50, "y": 72, "w": 92, "uppercase": False, "letter": 0,
                 "anim_in": "fade", "anim_out": "fade"},
        "anim_dur": 0.6,
    }
    for k, val in over.items():
        if isinstance(val, dict) and isinstance(v.get(k), dict):
            v[k].update(val)
        else:
            v[k] = val
    return v


# Valeurs par défaut SIMPLES : une image (à choisir), un son (à choisir) et un texte. Aucun effet ni emoji d'office.
DEFAULT_TEXT = {
    "follow": "{user} vient de follow !",
    "sub": "{user} vient de s'abonner ! ({months} mois)",
    "subgift": "{user} offre {count} sub(s) !",
    "bits": "{user} envoie {bits} bits !",
    "raid": "{user} arrive avec {viewers} viewers !",
    "hype_start": "Un train de la Hype démarre !",
    "hype_end": "Train de la Hype terminé : niveau {level} !",
    "hype_record": "Nouveau record : train de la Hype niveau {level} !",
    "goal_start": "Nouvel objectif : {description} ({target})",
    "goal_end": "Objectif atteint : {description} !",
}
DEFAULT_CHAT = {
    "follow": "💜 Merci pour le follow {user} ! Bienvenue !",
    "sub": "🎉 Merci {user} pour ton abonnement ({months} mois) !",
    "subgift": "🎁 Merci {user} pour les {count} sub(s) offerts !",
    "bits": "💎 Merci {user} pour les {bits} bits !",
    "raid": "🚀 Bienvenue aux {viewers} viewers de {user} ! Merci pour le raid !",
    "hype_start": "🚂 Un train de la Hype démarre ! Tout le monde à bord !",
    "hype_end": "🏁 Le train de la Hype est terminé au niveau {level} ! GG à tous !",
    "hype_record": "🏆 NOUVEAU RECORD : train de la Hype niveau {level} !",
    "goal_start": "🎯 Nouvel objectif : {description} ({target}) !",
    "goal_end": "✅ Objectif atteint : {description} ! Merci !",
}
DEFAULT_NAME = {"follow": "Follow", "sub": "Sub / Resub", "subgift": "Subs offerts", "bits": "Bits", "raid": "Raid",
                "hype_start": "Train de la Hype lancé", "hype_end": "Train de la Hype terminé",
                "hype_record": "Nouveau record de train",
                "goal_start": "Objectif lancé", "goal_end": "Objectif atteint"}


def default_variants() -> list[dict]:
    return [new_variant(k, id="v_" + k, name=DEFAULT_NAME[k], text={"template": DEFAULT_TEXT[k]}) for k in KINDS]


# Premiers réglages par défaut (avec effets et emoji d'office) : ceux qu'on n'a pas touchés sont ramenés au simple.
_OLD_DEFAULTS = {
    "v_follow": ("ghost", "", "👻 {user} rejoint la horde !"),
    "v_sub": ("confetti", "🎃", "{user} s'abonne ! — {months} mois"),
    "v_subgift": ("bats", "🎁", "{user} offre {count} sub(s) !"),
    "v_bits": ("lightning", "💀", "{user} lâche {bits} bits !"),
    "v_raid": ("bats", "🦇", "RAID de {user} — {viewers} viewers !"),
}


def _simplify_untouched(variants: list[dict]) -> list[dict]:
    out = []
    for v in variants:
        old = _OLD_DEFAULTS.get(v["id"])
        untouched = (old and v["effect"] == old[0] and v["media"]["emoji"] == old[1] and v["text"]["template"] == old[2]
                     and not v["media"]["file"] and not v["sound"])
        out.append(new_variant(v["kind"], id=v["id"], name=DEFAULT_NAME[v["kind"]],
                               text={"template": DEFAULT_TEXT[v["kind"]]}, enabled=v["enabled"]) if untouched else v)
    return out


def _num(v, lo, hi, name, cast=float):
    try:
        x = cast(v)
    except (TypeError, ValueError):
        raise ValueError(f"« {name} » doit être un nombre")
    if not lo <= x <= hi:
        raise ValueError(f"« {name} » doit être entre {lo} et {hi}")
    return x


def _color(v, name, allow_empty=True) -> str:
    s = ("" if v is None else str(v)).strip()
    if s == "" and allow_empty:
        return ""
    if not _COLOR_RE.match(s):
        raise ValueError(f"« {name} » doit être une couleur #rrggbb")
    return s


def clean_variant(raw: dict, images: set, sounds: set) -> dict:
    """Variante validée (ValueError avec un message lisible sinon). Les champs absents prennent leur défaut."""
    if not isinstance(raw, dict):
        raise ValueError("variante invalide")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise ValueError("type d'événement inconnu")
    base = new_variant(kind)
    name = str(raw.get("name", base["name"])).strip()[:60] or "Variante"
    vid = str(raw.get("id") or base["id"])
    if not re.match(r"^v_[A-Za-z0-9]{1,16}$", vid):
        vid = base["id"]

    def pick(d, key, allowed, label):
        v = d.get(key, base_section[key])
        if v not in allowed:
            raise ValueError(f"{label} inconnu")
        return v

    m_raw = raw.get("media") or {}
    t_raw = raw.get("text") or {}
    out = {
        "id": vid, "kind": kind, "name": name,
        "enabled": bool(raw.get("enabled", True)),
        "min_amount": _num(raw.get("min_amount", 1), 0, 10_000_000, f"{name} › minimum", int),
        "max_amount": _num(raw.get("max_amount", 0), 0, 10_000_000, f"{name} › maximum", int),
        "duration": _num(raw.get("duration", 6), 2, 30, f"{name} › durée"),
        "anim_dur": _num(raw.get("anim_dur", 0.6), 0.1, 3, f"{name} › durée d'animation"),
        "effect": raw.get("effect", "none"),
        "sound": raw.get("sound") or "",
        "volume": _num(raw.get("volume", 0.8), 0, 1, f"{name} › volume"),
        "sound_delay": _num(raw.get("sound_delay", 0), 0, 30, f"{name} › délai du son"),
        "chat_enabled": bool(raw.get("chat_enabled", True)),
        "chat_message": str(raw.get("chat_message", DEFAULT_CHAT.get(kind, "")))[:450],
    }
    if out["effect"] not in EFFECTS:
        raise ValueError(f"{name} › effet inconnu")
    if out["sound"] and out["sound"] not in sounds:
        raise ValueError(f"{name} › son introuvable")

    base_section = base["media"]
    media = {
        "file": m_raw.get("file") or "",
        "emoji": str(m_raw.get("emoji") or "")[:8],
        "delay": _num(m_raw.get("delay", 0), 0, 30, f"{name} › délai du média"),
        "x": _num(m_raw.get("x", 50), -20, 120, f"{name} › média X"),
        "y": _num(m_raw.get("y", 34), -20, 120, f"{name} › média Y"),
        "w": _num(m_raw.get("w", 26), 2, 120, f"{name} › média largeur"),
        "opacity": _num(m_raw.get("opacity", 1), 0, 1, f"{name} › média opacité"),
        "anim_in": pick(m_raw, "anim_in", [a for a in ANIM_IN if a not in ("typewriter", "wave")], f"{name} › animation d'entrée du média"),
        "anim_out": pick(m_raw, "anim_out", ANIM_OUT, f"{name} › animation de sortie du média"),
        "loop": bool(m_raw.get("loop", True)),
        "video_sound": bool(m_raw.get("video_sound", False)),
        "crop_t": _num(m_raw.get("crop_t", 0), 0, 90, f"{name} › rognage haut"),
        "crop_r": _num(m_raw.get("crop_r", 0), 0, 90, f"{name} › rognage droite"),
        "crop_b": _num(m_raw.get("crop_b", 0), 0, 90, f"{name} › rognage bas"),
        "crop_l": _num(m_raw.get("crop_l", 0), 0, 90, f"{name} › rognage gauche"),
        "trim_start": _num(m_raw.get("trim_start", 0), 0, 3600, f"{name} › début de la vidéo"),
        "trim_end": _num(m_raw.get("trim_end", 0), 0, 3600, f"{name} › fin de la vidéo"),
    }
    if media["crop_l"] + media["crop_r"] > 95 or media["crop_t"] + media["crop_b"] > 95:
        raise ValueError(f"{name} › le rognage ne laisse plus rien à afficher")
    if media["trim_end"] and media["trim_end"] <= media["trim_start"]:
        raise ValueError(f"{name} › la fin de la vidéo doit être après son début")
    if media["file"] and media["file"] not in images:
        raise ValueError(f"{name} › média introuvable")
    out["media"] = media

    base_section = base["text"]
    font = str(t_raw.get("font", "")).strip()
    if not _FONT_RE.match(font):
        raise ValueError(f"{name} › nom de police invalide")
    text = {
        "template": str(t_raw.get("template", "{user}"))[:240],
        "font": font,
        "delay": _num(t_raw.get("delay", 0), 0, 30, f"{name} › délai du texte"),
        # texte trop long : « shrink » = on garde la taille et on ne réduit que le pseudo s'il dépasse le cadre ;
        # « line » = tout sur une ligne en réduisant la taille ; « wrap » = coupe n'importe où ; « none » = rien
        "fit": t_raw.get("fit", "shrink"),
        "min_size": _num(t_raw.get("min_size", 36), 12, 400, f"{name} › taille minimale", int),
        "size": _num(t_raw.get("size", 84), 12, 400, f"{name} › taille du texte", int),
        "weight": pick(t_raw, "weight", WEIGHTS, f"{name} › graisse"),
        "color": _color(t_raw.get("color", "#ffffff"), f"{name} › couleur du texte", allow_empty=False),
        "highlight": _color(t_raw.get("highlight", ""), f"{name} › couleur du pseudo"),
        "stroke": _color(t_raw.get("stroke", "#000000"), f"{name} › contour"),
        "stroke_w": _num(t_raw.get("stroke_w", 4), 0, 30, f"{name} › épaisseur du contour"),
        "glow": _color(t_raw.get("glow", ""), f"{name} › lueur"),
        "align": pick(t_raw, "align", ALIGNS, f"{name} › alignement"),
        "x": _num(t_raw.get("x", 50), -20, 120, f"{name} › texte X"),
        "y": _num(t_raw.get("y", 72), -20, 120, f"{name} › texte Y"),
        "w": _num(t_raw.get("w", 92), 5, 120, f"{name} › texte largeur"),
        "uppercase": bool(t_raw.get("uppercase", False)),
        "letter": _num(t_raw.get("letter", 0), -10, 40, f"{name} › espacement"),
        "anim_in": pick(t_raw, "anim_in", ANIM_IN, f"{name} › animation d'entrée du texte"),
        "anim_out": pick(t_raw, "anim_out", ANIM_OUT, f"{name} › animation de sortie du texte"),
    }
    if text["fit"] not in ("shrink", "line", "wrap", "none"):
        raise ValueError(f"{name} › mode d'ajustement du texte inconnu")
    out["text"] = text
    # un élément qui apparaîtrait après la fin de l'alerte ne serait jamais vu
    last = out["duration"] - 0.5
    for label, d in (("du texte", text["delay"]), ("du média", media["delay"]), ("du son", out["sound_delay"])):
        if d > last:
            raise ValueError(f"{name} › le délai {label} ({d:g} s) dépasse la durée de l'alerte ({out['duration']:g} s)")
    return out


def clean_variants(raw_list, images: set, sounds: set) -> list[dict]:
    if not isinstance(raw_list, list):
        raise ValueError("liste de variantes invalide")
    if len(raw_list) > MAX_VARIANTS:
        raise ValueError(f"{MAX_VARIANTS} variantes maximum")
    out, seen = [], set()
    for raw in raw_list:
        v = clean_variant(raw, images, sounds)
        while v["id"] in seen:
            v["id"] = "v_" + uuid.uuid4().hex[:8]
        seen.add(v["id"])
        out.append(v)
    return out


def _legacy_variants(kinds: dict) -> list[dict]:
    """Ancien format (un jeu de réglages par type) -> variantes : on garde texte, durée, son, image."""
    base = {v["kind"]: v for v in default_variants()}
    style_to_effect = {"ghost": "ghost", "bats": "bats", "lightning": "lightning", "pumpkin": "confetti", "card": "none"}
    out = []
    for k in KINDS:
        old = (kinds or {}).get(k) or {}
        v = json.loads(json.dumps(base[k]))
        if old:
            v["enabled"] = bool(old.get("enabled", True))
            v["effect"] = style_to_effect.get(old.get("style"), v["effect"])
            if old.get("text"):
                v["text"]["template"] = str(old["text"])
            v["duration"] = float(old.get("duration", v["duration"]))
            v["min_amount"] = int(old.get("min_amount", 1))
            v["sound"] = old.get("sound") or ""
            v["volume"] = float(old.get("volume", 0.8))
            if old.get("image"):
                v["media"]["file"] = old["image"]
                v["media"]["emoji"] = ""
            if old.get("color"):
                v["text"]["glow"] = old["color"]
        out.append(v)
    return out


# ── Inspection des vidéos : ce que le navigateur d'OBS sait (ou non) lire ─────

_VIDEO_CODECS = [  # (étiquette MP4, nom, statut)
    (b"avc1", "H.264", "ok"), (b"avc3", "H.264", "ok"), (b"vp09", "VP9", "ok"), (b"av01", "AV1", "ok"),
    (b"hvc1", "HEVC / H.265", "maybe"), (b"hev1", "HEVC / H.265", "maybe"),
    (b"mp4v", "MPEG-4 Part 2", "bad"), (b"apch", "ProRes", "bad"), (b"apcn", "ProRes", "bad"),
    (b"apcs", "ProRes", "bad"), (b"apco", "ProRes", "bad"), (b"ap4h", "ProRes", "bad"),
    (b"mjpa", "Motion JPEG", "bad"), (b"jpeg", "Motion JPEG", "bad"), (b"s263", "H.263", "bad"),
]
_media_cache: dict = {}


def inspect_media(file: str) -> dict:
    """{'kind': 'image'|'video', 'status': 'ok'|'maybe'|'bad'|'unknown', 'codec': str, 'width', 'height', 'message'}"""
    path = os.path.join(IMAGES_DIR, file)
    ext = os.path.splitext(file)[1].lower()
    if ext not in (".mp4", ".webm"):
        return {"kind": "image", "status": "ok", "codec": "", "message": ""}
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {"kind": "video", "status": "unknown", "codec": "", "message": ""}
    hit = _media_cache.get(file)
    if hit and hit[0] == mtime:
        return hit[1]
    info = {"kind": "video", "status": "unknown", "codec": "", "width": None, "height": None, "message": ""}
    if ext == ".webm":
        info.update(status="ok", codec="WebM")
    else:
        try:
            import struct
            size = os.path.getsize(path)
            with open(path, "rb") as fh:
                pos, moov = 0, None
                while pos + 8 <= size:
                    fh.seek(pos)
                    sz, typ = struct.unpack(">I4s", fh.read(8))
                    if sz == 1:
                        sz = struct.unpack(">Q", fh.read(8))[0]
                    if typ == b"moov":
                        fh.seek(pos)
                        moov = fh.read(min(sz, 8 * 1024 * 1024))
                        break
                    pos += sz if sz else size
            if moov:
                for tag, name, status in _VIDEO_CODECS:
                    i = moov.find(tag)
                    if i > 0:
                        info.update(status=status, codec=name)
                        try:
                            w, h = struct.unpack(">HH", moov[i + 4 + 24:i + 4 + 28])
                            if 16 <= w <= 16384 and 16 <= h <= 16384:
                                info.update(width=w, height=h)
                        except Exception:
                            pass
                        break
        except Exception as e:
            logger.warning(f"⚠️ [ALERTES] Inspection de {file} impossible : {e}")
    if info["status"] == "bad":
        info["message"] = (f"Format {info['codec']} : OBS ne sait pas lire cette vidéo (elle restera invisible). "
                           f"Convertis-la en MP4 H.264 ou en WebM.")
    elif info["status"] == "maybe":
        info["message"] = "Format HEVC / H.265 : souvent illisible dans OBS. Une conversion en MP4 H.264 est plus sûre."
    elif info.get("width") and info["width"] > 1920:
        info["message"] = f"Vidéo en {info['width']}×{info['height']} : lourde pour OBS, 1920×1080 suffit."
    _media_cache[file] = (mtime, info)
    return info


# ── Stockage ─────────────────────────────────────────────────────────────────

async def ensure_table():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS alert_config (id INTEGER PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}')")
        await db.execute("INSERT INTO alert_config (id, data) VALUES (1, '{}') ON CONFLICT (id) DO NOTHING")
    _ready = True


def media_files(folder: str, exts: set) -> list[str]:
    if not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in exts)


async def get_config() -> dict:
    await ensure_table()
    async with get_db_connection() as db:
        c = await db.execute("SELECT data FROM alert_config WHERE id = 1")
        row = await c.fetchone()
    try:
        data = json.loads(row["data"]) if row else {}
    except Exception:
        data = {}

    images = set(media_files(IMAGES_DIR, IMAGE_EXTS))
    sounds = set(media_files(SOUNDS_DIR, SOUND_EXTS))
    if isinstance(data.get("variants"), list) and data["variants"]:
        try:
            variants = clean_variants(data["variants"], images | {v.get("media", {}).get("file", "") for v in data["variants"] if isinstance(v, dict)},
                                      sounds | {v.get("sound", "") for v in data["variants"] if isinstance(v, dict)})
        except ValueError as e:
            logger.error(f"❌ [ALERTES] Configuration invalide, valeurs par défaut utilisées : {e}")
            variants = default_variants()
    elif data.get("kinds"):
        variants = _legacy_variants(data["kinds"])          # ancienne configuration : migrée à la volée
    else:
        variants = default_variants()

    sc = dict(DEFAULT_SCREAMER)
    if isinstance(data.get("screamer"), dict):
        sc.update({k: v for k, v in data["screamer"].items() if k in DEFAULT_SCREAMER})
    variants = _simplify_untouched(variants)
    have = {v["kind"] for v in variants}
    for k in KINDS:                      # types ajoutés depuis la dernière sauvegarde (train de la Hype, objectifs…)
        if k not in have:
            variants.append(new_variant(k, id="v_" + k, name=DEFAULT_NAME[k], text={"template": DEFAULT_TEXT[k]}))
    return {"variants": variants, "screamer": sc}


async def save_config(variants: list, screamer: dict):
    await ensure_table()
    async with get_db_connection() as db:
        await db.execute("UPDATE alert_config SET data = $1 WHERE id = 1",
                         (json.dumps({"variants": variants, "screamer": screamer}, ensure_ascii=False),))


# ── Mémoire des records (train de la Hype) ───────────────────────────────────

async def get_state(key: str, default: str = "") -> str:
    await ensure_table()
    async with get_db_connection() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS alert_state (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')")
        c = await db.execute("SELECT value FROM alert_state WHERE key = $1", (key,))
        row = await c.fetchone()
    return row["value"] if row else default


async def set_state(key: str, value: str):
    await ensure_table()
    async with get_db_connection() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS alert_state (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')")
        await db.execute("INSERT INTO alert_state (key, value) VALUES ($1, $2) "
                         "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, str(value)))


GOAL_TYPES = {
    "follow": "followers", "subscription": "points d'abonnement", "subscription_count": "abonnés",
    "new_subscription": "nouveaux points d'abonnement", "new_subscription_count": "nouveaux abonnés",
    "new_bit": "bits", "new_cheerer": "donateurs de bits",
}


async def handle_hype_train(phase: str, event: dict, log_event=None) -> None:
    """begin -> « train lancé » ; end -> « nouveau record » si le niveau dépasse le meilleur connu."""
    level = int(event.get("level") or 1)
    total = int(event.get("total") or 0)
    tops = event.get("top_contributions") or []
    top_user = (tops[0].get("user_name") if tops and isinstance(tops[0], dict) else "") or \
               ((event.get("last_contribution") or {}).get("user_name") or "")
    # record déjà connu : celui de Twitch (v2) et notre propre mémoire, on garde le plus haut
    known = int(await get_state("hype_record_level", "0") or 0)
    twitch_record = int(event.get("all_time_high_level") or 0)
    if twitch_record > known:
        known = twitch_record
        await set_state("hype_record_level", str(known))
    if phase == "begin":
        await fire_alert("hype_start", top_user, level=level, total=total, goal=int(event.get("goal") or 0))
    elif phase == "end":
        if log_event:
            await log_event("hype_train", top_user or "communauté", {"level": level, "total": total})
        await fire_alert("hype_end", top_user, level=level, total=total)
        if level > known:
            await set_state("hype_record_level", str(level))
            await fire_alert("hype_record", top_user, level=level, total=total)


async def handle_goal(phase: str, event: dict) -> None:
    """begin -> « objectif lancé » ; end -> « objectif atteint » seulement s'il est réellement atteint."""
    gtype = event.get("type") or ""
    vals = dict(description=event.get("description") or "", type=GOAL_TYPES.get(gtype, gtype),
                current=int(event.get("current_amount") or 0), target=int(event.get("target_amount") or 0))
    if phase == "begin":
        await fire_alert("goal_start", "", **vals)
    elif phase == "end" and event.get("is_achieved"):
        await fire_alert("goal_end", "", **vals)


# ── Envoi à l'écran ──────────────────────────────────────────────────────────

async def _emit(payload: dict):
    from app.routes.overlays import trigger_overlay_event
    await trigger_overlay_event(payload)


def pick_variant(variants: list[dict], kind: str, amount: int | None) -> dict | None:
    """La variante activée dont la condition de montant correspond ; à défaut de précision, la plus exigeante."""
    ok = []
    for v in variants:
        if v["kind"] != kind or not v["enabled"]:
            continue
        if amount is not None:
            if amount < v["min_amount"] or (v["max_amount"] and amount > v["max_amount"]):
                continue
        ok.append(v)
    if not ok:
        return None
    top = max(v["min_amount"] for v in ok)
    return random.choice([v for v in ok if v["min_amount"] == top])


def render_chat(variant: dict, vars_: dict, prefix: str = "") -> str:
    """Message du t'chat : variables remplacées ; jamais une commande (/ban, !commande…)."""
    text = variant.get("chat_message") or ""
    for k in ALL_VARS:
        text = text.replace("{" + k + "}", str(vars_.get(k, "")))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if text[0] in "/.!":
        text = "• " + text
    return (prefix + text)[:480]


async def send_chat(text: str) -> bool:
    if not text:
        return False
    try:
        from app.core.config import settings
        from app.services.twitch_service import twitch_bot
        channel = twitch_bot.get_channel(settings.TWITCH_CHANNEL.replace("#", "").lower())
        if not channel:
            logger.warning("⚠️ [ALERTES] Message du t'chat non envoyé : bot non connecté au chat.")
            return False
        await channel.send(text)
        return True
    except Exception as e:
        logger.error(f"❌ [ALERTES] Message du t'chat : {e}")
        return False


async def fire_alert(kind: str, user: str, force: bool = False, variant: dict | None = None, **values) -> bool:
    """Envoie l'animation d'un événement. values : months, count, bits, viewers, level, total, goal, description…
    force=True (test) ignore l'activation et le hasard du screamer ; `variant` impose la variante à jouer."""
    if kind not in KINDS:
        return False
    cfg = await get_config()
    amount_key = AMOUNT_FIELD.get(kind)
    amount = int(values.get(amount_key, 1)) if amount_key else None

    chosen = variant
    if chosen is None:
        chosen = pick_variant(cfg["variants"], kind, amount)
        if chosen is None and force:
            chosen = next((v for v in cfg["variants"] if v["kind"] == kind), None)
    if chosen is None:
        return False

    sc = cfg["screamer"]
    if not force and sc["enabled"] and float(sc["chance"]) > 0 and random.random() * 100 < float(sc["chance"]):
        if await fire_screamer(source="hasard", user=user, config=cfg):
            return True

    vars_ = {"user": user, "months": values.get("months", 1), "count": values.get("count", 1),
             "bits": values.get("bits", 0), "viewers": values.get("viewers", 0),
             "level": values.get("level", 1), "total": values.get("total", 0), "goal": values.get("goal", 0),
             "description": values.get("description", ""), "current": values.get("current", 0),
             "target": values.get("target", 0), "type": values.get("type", "")}
    await _emit({"type": "stream_alert", "variant": chosen, "vars": vars_})
    # Message dans le t'chat (pas pour un simple test d'affichage depuis l'admin)
    if not force and chosen.get("chat_enabled", True):
        await send_chat(render_chat(chosen, vars_))
    return True


async def fire_screamer(source: str = "commande", user: str | None = None, force: bool = False, config: dict | None = None) -> bool:
    """Déclenche le screamer. force=True ignore l'activation et le délai minimum (test depuis l'admin)."""
    global _last_screamer
    cfg = config or await get_config()
    sc = cfg["screamer"]
    if not sc["enabled"] and not force:
        return False
    now = time.time()
    if not force and now - _last_screamer < float(sc["cooldown"]):
        return False
    _last_screamer = now
    logger.info(f"😱 [SCREAMER] déclenché ({source}{' par ' + user if user else ''})")
    await _emit({
        "type": "screamer", "image": sc["image"], "sound": sc["sound"], "volume": float(sc["volume"]),
        "duration": float(sc["duration"]), "flash": bool(sc["flash"]), "shake": bool(sc["shake"]),
    })
    return True
