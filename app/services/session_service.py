import sys
import time
import logging

# On utilise le système de logs de l'application
logger = logging.getLogger("masthbot.session")

# =================================================================
# SINGLETON : MÉMOIRE VIVE UNIQUE DANS L'INTERPRÉTEUR
# =================================================================
# Attacher les données à 'sys' garantit que Flask (interface web) 
# et le Bot Twitch (arrière-plan) partagent exactement le même dictionnaire.
if not hasattr(sys, '_masthom_session_data'):
    sys._masthom_session_data = {
        "start_time": time.time(),
        "chatters": [],      
        "followers": [],     
        "subs": [],          
        "subgifters": [],    
        "bits": [],          
        "raids": [],         
        "moderators": [],    
        "vips": [],          
        "lurkers": []
    }

def get_live_session_data():
    """Récupère la mémoire unique partagée."""
    return sys._masthom_session_data

def reset_session_data():
    """Vide la mémoire de la session (Idéal en début de stream via le dashboard)."""
    data = sys._masthom_session_data
    data["start_time"] = time.time()
    for key in data:
        if isinstance(data[key], list):
            data[key] = []
    logger.info("🧹 [Session] Mémoire vive réinitialisée pour le nouveau live.")
    return True

def update_live_session_data(event_type, user_name, details=None, is_mod=False, is_vip=False):
    """Inscrit une action dans la RAM, classe STRICTEMENT les rôles et cumule les dons."""
    data = sys._masthom_session_data
    if not user_name: 
        return False
    
    user_clean = str(user_name).strip()
    user_lower = user_clean.lower()

    # =================================================================
    # 1. SÉPARATION STRICTE DES RÔLES (MODO / VIP / SIMPLE VIEWER)
    # =================================================================
    is_already_mod = user_lower in [u.lower() if isinstance(u, str) else u.get('username','').lower() for u in data['moderators']]
    is_already_vip = user_lower in [u.lower() if isinstance(u, str) else u.get('username','').lower() for u in data['vips']]

    # Ajout aux Modérateurs (Priorité 1)
    if is_mod and not is_already_mod:
        data['moderators'].append(user_clean)
        logger.info(f"🛡️ [RAM] +1 MODO : {user_clean}")
        is_already_mod = True
    
    # Ajout aux VIPs (Priorité 2, seulement si pas Modo)
    elif is_vip and not is_already_mod and not is_already_vip:
        data['vips'].append(user_clean)
        logger.info(f"💎 [RAM] +1 VIP : {user_clean}")
        is_already_vip = True

    # NETTOYAGE : Si c'est un Modo/VIP, on s'assure qu'il n'est PAS dans les simples viewers
    if is_already_mod or is_already_vip:
        data['chatters'] = [c for c in data['chatters'] if (c.lower() if isinstance(c, str) else c.get('username', '').lower()) != user_lower]
        data['lurkers'] = [c for c in data['lurkers'] if (c.lower() if isinstance(c, str) else c.get('username', '').lower()) != user_lower]

    # =================================================================
    # 2. MAPPING DES ÉVÉNEMENTS
    # =================================================================
    mapping = {
        "chat_message": "chatters", "message": "chatters", "chat": "chatters",
        "follow": "followers", "follower": "followers", "follows": "followers",
        "sub": "subs", "resub": "subs", "subscriber": "subs", "subscription": "subs",
        "subgift": "subgifters", "gift": "subgifters", "giftsub": "subgifters",
        "bits": "bits", "cheer": "bits", "cheering": "bits",
        "raid": "raids", "raider": "raids", "hosting": "raids",
        "lurker": "lurkers", "lurk": "lurkers"
    }
    
    key = mapping.get(str(event_type).lower())
    if not key: 
        logger.warning(f"⚠️ [RAM] Type d'événement ignoré car inconnu : {event_type}")
        return False

    # BLOCAGE : Les Modos et VIPs ont droit de donner des Bits/Subs, mais on ne les 
    # rajoute JAMAIS dans la catégorie "chatters" ou "lurkers" (réservée aux viewers)
    if (key == "chatters" or key == "lurkers") and (is_already_mod or is_already_vip):
        return True

    # 3. Récupération des noms existants pour l'anti-doublon
    existing = [str(u).lower() if isinstance(u, str) else str(u.get('username', u.get('name', ''))).lower() for u in data[key]]

    # NOUVELLE ENTRÉE (La personne n'a pas encore fait cette action)
    if user_lower not in existing:
        if details:
            if key == "subgifters": 
                entry = {"name": user_clean, "count": details.get('count', 1)}
            elif key == "bits": 
                entry = {"username": user_clean, "amount": details.get('bits', 0)}
            elif key == "raids": 
                entry = {"username": user_clean, "viewer_count": details.get('viewers', 0)}
            elif key == "subs":
                entry = {"username": user_clean, "details": details}
            else: 
                entry = {"username": user_clean, "details": details}
            data[key].append(entry)
        else:
            data[key].append(user_clean)
        
        logger.info(f"📈 [RAM] +1 {key.upper()} : {user_clean}")
        return True

    # CUMUL (La personne a déjà fait l'action, on additionne)
    else:
        if key == "subgifters" and details:
            for index, u in enumerate(data[key]):
                if isinstance(u, dict) and u.get('name', '').lower() == user_lower:
                    data[key][index]['count'] += details.get('count', 1)
                    logger.info(f"🎁 [RAM] {user_clean} offre encore des subs ! (Total: {data[key][index]['count']})")
                    return True
                    
        elif key == "bits" and details:
            for index, u in enumerate(data[key]):
                if isinstance(u, dict) and u.get('username', '').lower() == user_lower:
                    data[key][index]['amount'] += details.get('bits', 0)
                    logger.info(f"💎 [RAM] {user_clean} a donné plus de bits ! (Total: {data[key][index]['amount']})")
                    return True

    return False
