"""Page maîtresse « Récompenses de points de chaîne » : vue d'ensemble + modules de configuration précise
(podium First / Deuz / Troiz aujourd'hui ; d'autres récompenses à comportement précis viendront ici)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.security import require_admin
from app.services import podium_service, reward_clone_service as RC

logger = logging.getLogger("masthbot.channel_rewards")
router = APIRouter(tags=["channel_rewards"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="app/templates")

# Récompenses dont le comportement est branché dans le bot en dehors du podium (id Twitch -> libellé)
KNOWN_BY_ID = {
    "093cceb1-3c5e-4e8e-bc16-7f27ff6a2d2b": "Commande !play (TikTok / clip)",
}
# Branchements par titre (voir eventsub_service)
KNOWN_BY_TITLE = {
    "polaroïd": "Polaroïd (bot)",
    "screamer": "Screamer (bot)",
}


@router.get("/admin/rewards", response_class=HTMLResponse)
async def admin_rewards_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/rewards_manager.html")


@router.get("/admin/podium")
async def admin_podium_legacy():
    """Ancienne adresse : le podium vit maintenant dans la page maîtresse."""
    return RedirectResponse(url="/admin/rewards#podium", status_code=307)


@router.get("/admin/api/rewards/overview")
async def admin_rewards_overview():
    _, _, broadcaster = podium_service._creds()
    status, data = await podium_service._helix("GET", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster})
    if status != 200:
        raise HTTPException(status_code=502, detail=data.get("message") or f"Twitch a répondu {status}")
    _, mine_data = await podium_service._helix(
        "GET", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster, "only_manageable_rewards": "true"})
    manageable = {r["id"] for r in mine_data.get("data", [])}
    from app.services import aura_service
    aura_cfg = await aura_service.get_config()
    podium_ids = {c["reward_id"]: f"Podium · {c['title']}" for c in await podium_service.get_config() if c["reward_id"]}
    known_ids = RC.resolve(KNOWN_BY_ID)
    from app.services import reward_overlay_service
    actions = {v["title"].strip().lower(): v for v in await reward_overlay_service.list_visuals()}
    pend = await RC.pending()
    # Original déjà supprimé sur Twitch mais « Finaliser » pas cliqué : on finalise tout seul, sinon la copie
    # (désactivée, nom provisoire) resterait cachée et la récompense semblerait avoir disparu.
    present = {r["id"] for r in data.get("data", [])}
    orphans = [oid for oid, p in pend.items() if oid not in present and p["clone_id"] in present]
    for oid in orphans:
        try:
            await RC.finalize(oid)
        except ValueError as e:
            logger.warning(f"🎁 [REWARDS] Finalisation automatique impossible pour {pend[oid]['title']} : {e}")
    if orphans:
        status, data = await podium_service._helix("GET", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster})
        pend = await RC.pending()
    present = {r["id"] for r in data.get("data", [])}
    clone_ids = {p["clone_id"] for oid, p in pend.items() if oid in present}   # copie cachée seulement si l'original est là

    rewards = []
    for r in data.get("data", []):
        if r["id"] in clone_ids:          # copie en attente : affichée sur la ligne de l'original
            continue
        ms = r.get("max_per_stream_setting") or {}
        mu = r.get("max_per_user_per_stream_setting") or {}
        cd = r.get("global_cooldown_setting") or {}
        img = r.get("image") or r.get("default_image") or {}
        handler = (podium_ids.get(r["id"]) or known_ids.get(r["id"])
                   or KNOWN_BY_TITLE.get((r.get("title") or "").lower())
                   or ("Aura (bot)" if aura_cfg["enabled"] and (r["id"] == aura_cfg["reward_id"] or (not aura_cfg["reward_id"] and (r.get("title") or "").strip().lower() == aura_cfg["reward_title"].strip().lower())) else None))
        rewards.append({
            "id": r["id"],
            "title": r.get("title", ""),
            "cost": int(r.get("cost", 0)),
            "enabled": bool(r.get("is_enabled")),
            "paused": bool(r.get("is_paused")),
            "color": r.get("background_color"),
            "image": img.get("url_2x") or img.get("url_1x"),
            "max_per_stream": ms.get("max_per_stream") if ms.get("is_enabled") else None,
            "max_per_user": mu.get("max_per_user_per_stream") if mu.get("is_enabled") else None,
            "cooldown": cd.get("global_cooldown_seconds") if cd.get("is_enabled") else None,
            "user_input": bool(r.get("is_user_input_required")),
            "manageable": r["id"] in manageable,
            "handler": handler,
            "prompt": r.get("prompt") or "",
            "clone_pending": r["id"] in pend,
            "actions": _summary(actions.get((r.get("title") or "").strip().lower())),
        })
    rewards.sort(key=lambda x: (not x["enabled"], x["title"].lower()))
    return {"rewards": rewards}


def _summary(v: dict | None) -> list[str]:
    """Ce que fait la récompense (page Récompenses › Actions), en court."""
    if not v:
        return []
    out = []
    if v.get("media"):
        out.append("vidéo" if v["media"].lower().endswith((".mp4", ".webm")) else "image")
    if v.get("sound"):
        out.append("son")
    if v.get("messages"):
        out.append("message")
    if v.get("steps"):
        out.append(f"{len(v['steps'])} étape(s)")
    return out + ([] if v.get("enabled", True) else ["désactivé"])


# ── Clonage (pour que le bot puisse gérer une récompense créée sur Twitch) et modification ──

def _run(coro_fn):
    async def inner(*a, **k):
        try:
            return await coro_fn(*a, **k)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return inner


@router.post("/admin/api/rewards/{reward_id}/clone")
async def admin_reward_clone(reward_id: str):
    return await _run(RC.clone)(reward_id)


@router.post("/admin/api/rewards/{reward_id}/clone/finalize")
async def admin_reward_clone_finalize(reward_id: str):
    return await _run(RC.finalize)(reward_id)


@router.post("/admin/api/rewards/{reward_id}/clone/cancel")
async def admin_reward_clone_cancel(reward_id: str):
    return await _run(RC.cancel)(reward_id)


@router.post("/admin/api/rewards")
async def admin_reward_create(payload: dict):
    r = await _run(RC.create)(payload or {})
    return {"status": "ok", "id": r["id"], "title": r.get("title")}


@router.delete("/admin/api/rewards/{reward_id}")
async def admin_reward_delete(reward_id: str):
    await _run(RC.delete)(reward_id)
    return {"status": "ok"}


@router.put("/admin/api/rewards/{reward_id}")
async def admin_reward_edit(reward_id: str, payload: dict):
    r = await _run(RC.edit)(reward_id, payload or {})
    return {"status": "ok", "title": r.get("title")}


@router.get("/admin/api/rewards/dashboard-url")
async def admin_reward_dashboard_url():
    from app.core.config import settings
    login = settings.TWITCH_CHANNEL.replace("#", "").lower()
    return {"url": f"https://dashboard.twitch.tv/u/{login}/viewer-rewards/channel-points/rewards"}
