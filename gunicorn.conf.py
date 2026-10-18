# Gunicorn reads this file automatically (Render and the Procfile start the app with gunicorn).
import os


def on_starting(server):
    """Runs once when the server starts (not when a worker restarts): begin a fresh game from
    scenario_config.json, keeping a game that was under way on the Saves tab. FRESH_START=0 turns this off."""
    if os.environ.get("FRESH_START", "1") == "0":
        return
    from models import Database
    from engine import SummitEngine
    SummitEngine(Database()).fresh_start()
