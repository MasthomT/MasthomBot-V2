# simule_viewers.py
import time
import os

# DOIT ÊTRE IDENTIQUE AU SERVICE
PATH = "/home/masthom/BOT_V2/labels/viewers.txt"

print(f"📡 Simulation forcée sur : {PATH}")

try:
    while True:
        # On s'assure que le dossier existe
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        
        with open(PATH, "w", encoding="utf-8") as f:
            f.write("123") # On met 123 pour bien voir le test
            
        print("✅ Écrit : 123")
        time.sleep(5)
except KeyboardInterrupt:
    print("Arrêt.")
