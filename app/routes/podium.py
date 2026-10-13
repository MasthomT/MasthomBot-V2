"""API d'admin du podium First / Deuz / Troiz (page : /admin/rewards#podium, voir app/services/podium_service.py)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.security import require_admin
from app.services import podium_service

logger = logging.getLogger("masthbot.podium_routes")
router = APIRouter(tags=["podium"], dependencies=[Depends(require_admin)])


class RewardCfg(BaseModel):
    position: int
    title: str
    cost: int
    prompt: str = ""
    color: str = "#9146FF"
    user_input: bool = False
    win_message: str = ""


class PodiumPayload(BaseModel):
    rewards: list[RewardCfg]


@router.get("/admin/api/podium")
async def admin_podium_get():
    cfgs = await podium_service.get_config()
    state = await podium_service.get_state()
    return {
        "rewards": [dict(c, created=bool(c["reward_id"])) for c in cfgs],
        "state": state,
    }


@router.put("/admin/api/podium")
async def admin_podium_save(payload: PodiumPayload):
    await podium_service.ensure_tables()
    for r in payload.rewards:
        if r.position not in podium_service.POSITIONS:
            raise HTTPException(status_code=400, detail=f"Position inconnue : {r.position}")
        title = r.title.strip()
        if not title or len(title) > 45:
            raise HTTPException(status_code=400, detail="Le titre doit faire entre 1 et 45 caractères.")
        if r.cost < 1:
            raise HTTPException(status_code=400, detail="Le prix doit être d'au moins 1 point.")
    async with get_db_connection() as db:
        for r in payload.rewards:
            await db.execute(
                """UPDATE podium_rewards
                   SET title = $1, cost = $2, prompt = $3, color = $4, user_input = $5, win_message = $6
                   WHERE position = $7""",
                (r.title.strip(), r.cost, r.prompt, r.color, r.user_input, r.win_message, r.position),
            )
    report = await podium_service.push_config_to_twitch()
    return {"status": "ok", "twitch": report}


@router.post("/admin/api/podium/create")
async def admin_podium_create():
    return {"status": "ok", "report": await podium_service.create_rewards()}


@router.post("/admin/api/podium/stage/{stage}")
async def admin_podium_stage(stage: int):
    if stage not in (0, 1, 2, 3):
        raise HTTPException(status_code=400, detail="Étape invalide (0 = tout éteindre, 1 à 3).")
    await podium_service.manual_set_stage(stage)
    return {"status": "ok"}
