#!/usr/bin/env python3
"""
Script générique pour lancer un programme Python et ouvrir une URL dans le navigateur
"""

import subprocess
import webbrowser
import time
import sys
import os

# =============================================================================
# CONFIGURATION - Modifiez ces variables selon vos besoins
# =============================================================================

# Chemin vers le programme Python à exécuter
base_dir = os.path.dirname(os.path.abspath(__file__))
PYTHON_PROGRAM = os.path.normpath(os.path.join(base_dir, "app.py"))

# URL à ouvrir dans le navigateur
URL = "http://localhost:5000"

# Délai avant d'ouvrir le navigateur (en secondes)
# Utile si le programme Python doit démarrer un serveur
DELAY_BEFORE_BROWSER = 2

# Garder le script en vie après le lancement (True/False)
KEEP_ALIVE = True

# =============================================================================
# FONCTIONS
# =============================================================================

def launch_python_program():
    """Lance le programme Python spécifié"""
    print(f"Lancement du programme Python: {PYTHON_PROGRAM}")
    
    # Vérifier que le fichier existe
    if not os.path.exists(PYTHON_PROGRAM):
        print(f"Erreur: Le fichier {PYTHON_PROGRAM} n'existe pas!")
        return None
    
    try:
        # Lancer le programme Python en arrière-plan
        process = subprocess.Popen([sys.executable, PYTHON_PROGRAM])
        print(f"Programme lancé avec PID: {process.pid}")
        return process
    except Exception as e:
        print(f"Erreur lors du lancement du programme: {e}")
        return None

def open_browser():
    """Ouvre l'URL dans le navigateur par défaut"""
    print(f"Ouverture de l'URL dans le navigateur: {URL}")
    try:
        webbrowser.open(URL)
        print("Navigateur ouvert avec succès")
    except Exception as e:
        print(f"Erreur lors de l'ouverture du navigateur: {e}")

def main():
    """Fonction principale"""
    print("=" * 50)
    print("LANCEUR PYTHON + NAVIGATEUR")
    print("=" * 50)
    
    # Lancer le programme Python
    process = launch_python_program()
    
    if process is None:
        print("Impossible de continuer sans le programme Python")
        return
    
    # Attendre un peu avant d'ouvrir le navigateur
    if DELAY_BEFORE_BROWSER > 0:
        print(f"Attente de {DELAY_BEFORE_BROWSER} secondes...")
        time.sleep(DELAY_BEFORE_BROWSER)
    
    # Ouvrir le navigateur
    open_browser()
    
    if KEEP_ALIVE:
        print("\nScript en cours d'exécution...")
        print("Appuyez sur Ctrl+C pour arrêter le programme Python et quitter")
        try:
            # Attendre que le processus se termine ou que l'utilisateur interrompe
            while process.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nArrêt demandé par l'utilisateur")
            print("Fermeture du programme Python...")
            process.terminate()
            # Attendre un peu pour la fermeture propre
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Forçage de la fermeture...")
                process.kill()
        
        print("Programme terminé")
    else:
        print("Script terminé (programme Python continue en arrière-plan)")

if __name__ == "__main__":
    main()