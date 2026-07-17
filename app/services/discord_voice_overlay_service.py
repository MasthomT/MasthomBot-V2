"""
app/services/discord_voice_overlay_service.py — Overlay OBS "salon vocal Discord" fait
maison, en remplacement de Discord StreamKit Overlay (dont le websocket
streamkit.discord.com se déconnectait en boucle en continu pendant tout le stream —
des centaines de fois par session, cf. audit du 2026-07-16 sur les logs OBS).

Suit automatiquement le salon vocal où se trouve STREAMER_DISCORD_ID : le bot rejoint ce
salon (micro coupé, il n'envoie jamais de son) dès que le streamer y entre, et le quitte
quand il en part.

Détection de la prise de parole : discord.py ne traite QUE l'ENVOI de l'opcode SPEAKING (5)
sur le websocket vocal — il ignore silencieusement sa RÉCEPTION pour les autres membres du
salon (vérifié dans le code source de discord.py 2.7.1 : `DiscordVoiceWebSocket.received_message`
n'a aucun `elif op == self.SPEAKING` côté réception, contrairement à HEARTBEAT_ACK, HELLO, etc.).
On branche donc un hook sur `VoiceConnectionState` — le point d'extension prévu par la lib via
`VoiceClient.create_connection_state()` — pour intercepter nous-mêmes ces paquets bruts.
"""
import logging
from typing import Optional

import discord
from discord.voice_state import VoiceConnectionState
from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger("masthbot.discord_voice_overlay")


class SpeakingVoiceClient(discord.VoiceClient):
    """VoiceClient qui redirige les messages bruts du websocket vocal vers notre hook,
    seul moyen d'observer les paquets SPEAKING des autres membres (cf. docstring du module)."""

    def create_connection_state(self) -> VoiceConnectionState:
        return VoiceConnectionState(self, hook=_on_voice_ws_message)


async def _on_voice_ws_message(ws, msg: dict) -> None:
    if msg.get("op") != 5:  # SPEAKING
        return
    data = msg["d"]
    await discord_voice_overlay_service.handle_speaking(int(data["user_id"]), bool(data["speaking"]))


class DiscordVoiceOverlayService:
    def __init__(self) -> None:
        self.voice_client: Optional[SpeakingVoiceClient] = None
        self.channel: Optional[discord.VoiceChannel] = None
        self.members: dict[int, dict] = {}
        self.ws_clients: set[WebSocket] = set()

    # ---------------------------------------------------------------
    # Connexion / déconnexion du salon suivi
    # ---------------------------------------------------------------
    async def handle_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        streamer_id = settings.STREAMER_DISCORD_ID
        if not streamer_id:
            return

        if str(member.id) == str(streamer_id):
            if after.channel and after.channel != before.channel:
                await self._join_channel(after.channel)
                return
            if after.channel is None and before.channel is not None:
                await self._leave()
                return

        # Membre autre que le streamer (ou changement de mute/deaf du streamer sans
        # changement de salon) : on ne réagit que si ça concerne le salon suivi.
        if self.channel is None:
            return
        if before.channel != self.channel and after.channel != self.channel:
            return

        self._sync_members()
        await self._broadcast()

    async def _join_channel(self, channel: discord.VoiceChannel) -> None:
        if self.channel and self.channel.id == channel.id and self.voice_client and self.voice_client.is_connected():
            return
        await self._leave()
        try:
            self.voice_client = await channel.connect(
                cls=SpeakingVoiceClient, self_mute=True, self_deaf=False, reconnect=True
            )
            self.channel = channel
            self._sync_members()
            logger.info(f"🎙️ [VOICE OVERLAY] Rejoint le salon « {channel.name} ».")
            await self._broadcast()
        except Exception as e:
            logger.error(f"❌ [VOICE OVERLAY] Impossible de rejoindre « {channel.name} » : {e}")
            self.voice_client = None
            self.channel = None

    async def _leave(self) -> None:
        if self.voice_client:
            try:
                await self.voice_client.disconnect(force=True)
            except Exception:
                pass
        self.voice_client = None
        self.channel = None
        self.members = {}
        await self._broadcast()

    # ---------------------------------------------------------------
    # État des membres du salon suivi
    # ---------------------------------------------------------------
    def _sync_members(self) -> None:
        if not self.channel:
            self.members = {}
            return
        fresh: dict[int, dict] = {}
        for m in self.channel.members:
            if m.bot:
                continue
            existing = self.members.get(m.id, {})
            voice = m.voice
            fresh[m.id] = {
                "id": str(m.id),
                "name": m.display_name,
                "avatar": m.display_avatar.replace(size=128).url,
                "speaking": existing.get("speaking", False),
                "muted": bool(voice and (voice.self_mute or voice.mute)),
                "deafened": bool(voice and (voice.self_deaf or voice.deaf)),
            }
        self.members = fresh

    async def handle_speaking(self, user_id: int, speaking: bool) -> None:
        entry = self.members.get(user_id)
        if entry is None or entry["speaking"] == speaking:
            return
        entry["speaking"] = speaking
        await self._broadcast()

    # ---------------------------------------------------------------
    # Diffusion WebSocket vers l'overlay OBS
    # ---------------------------------------------------------------
    def _state_payload(self) -> dict:
        return {
            "connected": self.channel is not None,
            "channel_name": self.channel.name if self.channel else None,
            "members": list(self.members.values()),
        }

    async def register(self, ws: WebSocket) -> None:
        self.ws_clients.add(ws)
        await ws.send_json(self._state_payload())

    def unregister(self, ws: WebSocket) -> None:
        self.ws_clients.discard(ws)

    async def _broadcast(self) -> None:
        if not self.ws_clients:
            return
        payload = self._state_payload()
        dead = []
        for client in self.ws_clients:
            try:
                await client.send_json(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            self.ws_clients.discard(client)


discord_voice_overlay_service = DiscordVoiceOverlayService()
