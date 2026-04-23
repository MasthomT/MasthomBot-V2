import json
import os
import sys
from flask import Blueprint, request, jsonify

# --- CONFIG DES CHEMINS ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# IMPORTS DES SERVICES
from app.services.xp_service import add_xp
from app.services.session_service import update_live_session_data 

chat_bp = Blueprint('chat', __name__)

@chat_bp.route("/api/chat-message", methods=['POST'])
def handle_chat_message():
    """
    Réceptionne les données Twitch et les injecte en RAM et SQL.
    Note : Passage en 'def' synchrone pour éviter l'erreur de retour Flask.
    """
    try:
        # Récupération sécurisée du JSON
        raw_data = request.get_data(as_text=True)
        if not raw_data:
            return jsonify({"status": "error", "message": "Empty body"}), 400
            
        data = json.loads(raw_data)
    except Exception as e:
        print(f"⚠️ [Chat Route] Erreur parsing JSON : {e}")
        return jsonify({"status": "error", "message": str(e)}), 400
    
    # --- CORRECTION MASSIVE : DÉTECTION DU VRAI TYPE D'ÉVÉNEMENT ---
    # On rattrape "event", "type", ou "event_type" pour ne plus rien rater
    event_type_raw = data.get('event_type') or data.get('type') or data.get('event') or 'chat_message'
    event_type = str(event_type_raw).strip().lower()
    
    # Extraction sécurisée du pseudo
    user = data.get('user') or data.get('userName') or data.get('username') or 'inconnu'
    user_id = str(data.get('userId', '0'))
    
    # Rôles Twitch
    is_mod = bool(data.get('isMod', False))
    is_vip = bool(data.get('isVip', False))
    
    # --- NORMALISATION (On force dans les bonnes cases) ---
    details = None
    if "bit" in event_type or "cheer" in event_type:
        event_type = "bits"
        details = {"bits": data.get("bits", data.get("amount", 0))}
    elif "raid" in event_type or "host" in event_type:
        event_type = "raid"
        details = {"viewers": data.get("viewers", data.get("viewerCount", 0))}
    elif "gift" in event_type:
        event_type = "subgift"
        details = {"count": data.get("count", data.get("gifts", 1))}
    elif "sub" in event_type:
        event_type = "sub"
        details = {"months": data.get("months", data.get("tier", 1))}
    elif "follow" in event_type:
        event_type = "follow"

    # 1. Injection RAM (Studio & Générique)
    # On s'assure que le service reçoit bien les rôles pour le tri
    try:
        update_live_session_data(
            event_type=event_type, 
            user_name=user, 
            details=details, 
            is_mod=is_mod, 
            is_vip=is_vip
        )
    except Exception as e:
        print(f"⚠️ [Chat Route] Erreur Session Service : {e}")

    # 2. Injection SQL (XP)
    if user_id != "0":
        try:
            add_xp(user_id, user, action_type=event_type)
        except Exception as e:
            print(f"⚠️ [Chat Route] Erreur XP Service : {e}")
    
    # On renvoie TOUJOURS une réponse valide à Flask
    return jsonify({"status": "ok", "processed_event": event_type})
