"""Page maîtresse « Récompenses de points de chaîne » : vue d'ensemble + modules de configuration précise
(podium First / Deuz / Troiz aujourd'hui ; d'autres récompenses à comportement précis viendront ici)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.security import require_admin
from app.services import podium_service

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
    podium_ids = {c["reward_id"]: f"Podium · {c['title']}" for c in await podium_service.get_config() if c["reward_id"]}

    rewards = []
    for r in data.get("data", []):
        ms = r.get("max_per_stream_setting") or {}
        mu = r.get("max_per_user_per_stream_setting") or {}
        cd = r.get("global_cooldown_setting") or {}
        img = r.get("image") or r.get("default_image") or {}
        handler = (podium_ids.get(r["id"]) or KNOWN_BY_ID.get(r["id"])
                   or KNOWN_BY_TITLE.get((r.get("title") or "").lower()))
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
        })
    rewards.sort(key=lambda x: (not x["enabled"], x["title"].lower()))
    return {"rewards": rewards}
