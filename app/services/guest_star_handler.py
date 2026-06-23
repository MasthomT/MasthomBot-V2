"""
guest_star_handler.py — Handler pour les événements EventSub Guest Star

⚠️ CE FICHIER N'EST PAS AUTONOME : je n'ai pas le contenu de ton
eventsub_service.py existant, donc je ne peux pas l'intégrer directement
sans risquer de casser tes handlers actuels (follows, subs, raids...).

CE QU'IL FAUT FAIRE CÔTÉ INTÉGRATION :

1. Dans eventsub_service.py, repère la fonction qui s'abonne aux topics
   EventSub (probablement un truc du genre `subscribe_to_events()` ou
   `create_eventsub_subscription()`). Ajoute ces deux abonnements à la liste
   existante :

     await create_eventsub_subscription(
         "channel.guest_star_guest.update",
         version="beta",  # ⚠️ Guest Star EventSub est encore en version beta chez Twitch
         condition={
             "broadcaster_user_id": BROADCASTER_ID,
             "moderator_user_id": BROADCASTER_ID
         }
     )

2. Repère la fonction qui route les events entrants vers leurs handlers
   (probablement un gros if/elif sur `event_type` ou un dict de dispatch).
   Ajoute une branche :

     elif event_type == "channel.guest_star_guest.update":
         await handle_guest_star_guest_update(event_data)

3. Colle la fonction handle_guest_star_guest_update ci-dessous dans
   eventsub_service.py (ou importe-la depuis ce fichier).

4. Vérifie que ton app Twitch a bien le scope `channel:read:guest_star`
   sur le token utilisé pour la souscription EventSub (peut être différent
   du token du bot chat selon ton architecture).

RÉFÉRENCE TWITCH : la charge utile (payload) de channel.guest_star_guest.update
contient un champ "slots" qui liste les invités actuellement en session, avec
leur "guest_user_id"/"guest_user_login"/"guest_user_name" et leur "state"
("invited", "ready", "live", "removed", etc.). On ne veut enregistrer un
partenaire QUE quand son state passe à "live" — sinon on capturerait aussi
les gens juste invités/en attente qui n'ont jamais vraiment co-streamé.
"""

import logging
from app.services import partners_service

logger = logging.getLogger("masthbot.eventsub.guest_star")

# Mémoire courte pour éviter de spammer plusieurs fois le même invité
# pendant qu'il reste "live" sur plusieurs updates successives du même event.
_already_registered_this_session: set[str] = set()


async def handle_guest_star_guest_update(event_data: dict):
    """
    À appeler depuis le dispatcher EventSub existant quand un event
    'channel.guest_star_guest.update' arrive.

    event_data correspond au champ "event" du payload EventSub Twitch.
    Structure attendue (cf. doc Twitch) :
    {
        "broadcaster_user_id": "...",
        "session_id": "...",
        "moderator_user_id": "...",
        "slots": [
            {
                "guest_user_id": "12345",
                "guest_user_login": "exemplelogin",
                "guest_user_display_name": "ExempleLogin",
                "state": "live",
                ...
            },
            ...
        ]
    }
    """
    slots = event_data.get("slots", [])
    session_id = event_data.get("session_id", "unknown")

    for slot in slots:
        state = slot.get("state", "")
        login = slot.get("guest_user_login", "")

        if not login:
            continue

        dedup_key = f"{session_id}:{login}"

        if state == "live" and dedup_key not in _already_registered_this_session:
            _already_registered_this_session.add(dedup_key)
            logger.info(f"🎙️ [GUEST STAR] {login} est maintenant live en Guest Star — enregistrement comme partenaire.")
            try:
                await partners_service.register_guest_star_collab(login)
            except Exception as e:
                logger.error(f"❌ [GUEST STAR] Échec d'enregistrement du partenaire {login}: {e}")

        elif state in ("removed", "disconnected") and dedup_key in _already_registered_this_session:
            # On retire juste du cache de déduplication ; le partenaire reste
            # en base avec son historique, on ne supprime jamais sur un simple
            # départ de session.
            _already_registered_this_session.discard(dedup_key)


def clear_session_cache():
    """
    À appeler quand une session Guest Star se termine entièrement
    (event 'channel.guest_star_session.end' si tu choisis de t'y abonner aussi),
    pour repartir propre sur la prochaine session.
    """
    _already_registered_this_session.clear()
