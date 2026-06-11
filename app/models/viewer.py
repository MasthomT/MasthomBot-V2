from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ViewerBase(BaseModel):
    """Base commune pour les viewers."""
    twitch_id: str = Field(..., description="ID unique Twitch")
    username: str = Field(..., description="Nom d'utilisateur Twitch officiel")
    nickname: Optional[str] = Field(None, description="Surnom choisi par le viewer pour Félix")
    nickname_for_bot: Optional[str] = Field(None, description="Comment le viewer appelle Félix")

    # Statistiques conservées
    watchtime: int = Field(0, description="Watchtime cumulé en secondes")
    messages: int = Field(0, description="Compteur total de messages")
    points: int = Field(0, description="Points d'expérience (EXP)")
    first_count: int = Field(0, description="Nombre de FIRST")
    deuz_count: int = Field(0, description="Nombre de DEUZ")
    troiz_count: int = Field(0, description="Nombre de TROIZ")
    rank: Optional[int] = Field(None, description="Rang dans le classement")
    is_mod: bool = Field(False, description="Statut modérateur")
    is_artist: bool = Field(False, description="Statut artiste")
    vip_expiry: Optional[str] = Field(None, description="Date expiration VIP texte")

    # Logique VIP (temporelle stricte)
    is_vip: bool = Field(False, description="Statut VIP actuel")
    vip_expiry_date: Optional[datetime] = Field(None, description="Date d'expiration stricte du VIP")
    last_seen: Optional[datetime] = Field(None, description="Dernière apparition dans le chat")

    # Contexte IA Félix
    roast_level: int = Field(
        default=5,
        ge=0,
        le=10,
        description="Niveau d'insolence de Félix (1 à 10)"
    )
    birthday: Optional[str] = None
    sleep_pattern: Optional[str] = None
    pronouns: Optional[str] = None
    vibe: Optional[str] = None
    favorite_game: Optional[str] = None
    comfort_game: Optional[str] = None
    signature_emote: Optional[str] = None
    play_style: Optional[str] = None
    useless_talent: Optional[str] = None
    favorite_feature: Optional[str] = None
    favorite_food: Optional[str] = None
    favorite_drink: Optional[str] = None
    free_message: Optional[str] = None
    bot_tone: Optional[str] = Field(None, description="La personnalité de Félix choisie par le viewer")

class ViewerCreate(ViewerBase):
    """Schéma utilisé lors de la toute première détection d'un viewer."""
    pass

class ViewerUpdate(BaseModel):
    """
    Schéma pour les mises à jour partielles.
    Tous les champs sont optionnels car on ne met à jour que ce qui change.
    """
    nickname: Optional[str] = None
    nickname_for_bot: Optional[str] = None
    watchtime: Optional[int] = None
    messages: Optional[int] = None
    points: Optional[int] = None
    is_vip: Optional[bool] = None
    vip_expiry_date: Optional[datetime] = None
    roast_level: Optional[int] = None
    birthday: Optional[str] = None
    sleep_pattern: Optional[str] = None
    pronouns: Optional[str] = None
    vibe: Optional[str] = None
    favorite_game: Optional[str] = None
    comfort_game: Optional[str] = None
    signature_emote: Optional[str] = None
    play_style: Optional[str] = None
    useless_talent: Optional[str] = None
    favorite_feature: Optional[str] = None
    favorite_food: Optional[str] = None
    favorite_drink: Optional[str] = None
    free_message: Optional[str] = None

class ViewerResponse(ViewerBase):
    """
    Schéma de réponse API.
    C'est exactement ce format JSON qui sera renvoyé à ton frontend FEL-X.
    """
    level: Optional[int] = Field(1, description="Niveau calculé via l'EXP")
    
    # Les deux listes dont le frontend a besoin :
    daily_activity: List[Dict[str, Any]] = []
    exp_history: List[Dict[str, Any]] = []
