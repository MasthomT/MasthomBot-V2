from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ViewerBase(BaseModel):
    twitch_id: str
    username: str

class ViewerCreate(ViewerBase):
    # On ajoute TOUS les champs nécessaires à la création initiale
    nickname: Optional[str] = None
    watchtime: int = 0
    message_count: int = 0        # <--- Ajouté
    is_vip: bool = False          # <--- Ajouté
    vip_expiry_date: Optional[datetime] = None  # <--- Ajouté
    roast_level: int = 5          # <--- Ajouté

class ViewerUpdate(BaseModel):
    nickname: Optional[str] = None
    roast_level: Optional[int] = None
    watchtime: Optional[int] = None
    is_vip: Optional[bool] = None
    vip_expiry_date: Optional[datetime] = None

class ViewerInDB(ViewerBase):
    id: int
    nickname: Optional[str] = None
    roast_level: int = 5
    messages_count: int = 0 # Attention à la cohérence du nom (message_count vs messages_count)
    watchtime: int = 0
    last_seen: datetime

    class Config:
        from_attributes = True
