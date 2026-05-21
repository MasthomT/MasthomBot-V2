import asyncio
from app.core.database import get_db_connection

async def audit_complet():
    print("\n" + "="*50)
    print("🚀 AUDIT PROFOND DES FONCTIONNALITÉS 🚀")
    print("="*50 + "\n")

    try:
        async with get_db_connection() as conn:
            
            # --- 1. TROPHÉES & XP ---
            print("🏆 [1/4] SYSTÈME DE TROPHÉES & NIVEAUX")
            try:
                c1 = await conn.execute("SELECT COUNT(*) as c FROM trophy_list")
                nb_trophies = (await c1.fetchone())["c"]
                c2 = await conn.execute("SELECT COUNT(*) as c FROM viewer_trophies")
                nb_debloques = (await c2.fetchone())["c"]
                print(f"  ✅ Trophées configurés : {nb_trophies}")
                print(f"  ✅ Trophées débloqués par les viewers : {nb_debloques}")
            except Exception as e:
                print(f"  ❌ Erreur Trophées : {e}")
            print("")

            # --- 2. SONDAGES ---
            print("📊 [2/4] SYSTÈME DE SONDAGES")
            try:
                c3 = await conn.execute("SELECT COUNT(*) as c FROM polls")
                nb_polls = (await c3.fetchone())["c"]
                c4 = await conn.execute("SELECT * FROM polls WHERE is_active=1 ORDER BY id DESC LIMIT 1")
                actif = await c4.fetchone()
                print(f"  ✅ Historique des sondages : {nb_polls} créés")
                if actif:
                    print(f"  🟢 Un sondage est actuellement ACTIF : '{dict(actif).get('question')}'")
                else:
                    print("  💤 Aucun sondage actif en ce moment.")
            except Exception as e:
                print(f"  ❌ Erreur Sondages : {e}")
            print("")

            # --- 3. VIP & VIEWERS ---
            print("💎 [3/4] SYSTÈME VIP & VIEWERS")
            try:
                c5 = await conn.execute("SELECT COUNT(*) as c FROM viewers")
                nb_viewers = (await c5.fetchone())["c"]
                c6 = await conn.execute("SELECT COUNT(*) as c FROM viewers WHERE is_vip=1")
                nb_vips = (await c6.fetchone())["c"]
                print(f"  ✅ Base de données Viewers : {nb_viewers} personnes enregistrées")
                print(f"  ✅ VIPs actifs reconnus : {nb_vips}")
            except Exception as e:
                print(f"  ❌ Erreur VIPs : {e}")
            print("")

            # --- 4. MODÉRATION ---
            print("🛡️ [4/4] SYSTÈME DE MODÉRATION")
            try:
                c7 = await conn.execute("SELECT * FROM moderation_settings LIMIT 1")
                mod = await c7.fetchone()
                if mod:
                    m_dict = dict(mod)
                    print("  ✅ Réglages de modération trouvés.")
                    print(f"  🔒 Mots interdits activés : {'Oui' if m_dict.get('banned_words_enabled') else 'Non'}")
                    print(f"  🛡️ Protection Majuscules : {'Oui' if m_dict.get('caps_protection_enabled') else 'Non'}")
                else:
                    print("  ⚠️ La table de modération est vide ! (Il faut sauvegarder les réglages sur le panel web)")
            except Exception as e:
                print(f"  ❌ Erreur Modération : {e}")
            print("\n" + "="*50)

    except Exception as e:
        print(f"❌ Impossible de se connecter à la BDD : {e}")

if __name__ == "__main__":
    asyncio.run(audit_complet())
