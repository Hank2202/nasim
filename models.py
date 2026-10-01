"""
Data models, schema, and persistence layer for The Summit of Realms.
Uses SQLite for state persistence so server restarts or accidental reloads
never wipe simulation progress.
"""

import json
import sqlite3
import time
from typing import Dict, List, Optional, Any

DB_PATH = "summit.db"

DEFAULT_REALMS = [
    {
        "id": "sylvan",
        "name": "Sylvan Concordat",
        "theme_color": "#10b981", # Emerald
        "icon": "leaf",
        "ethos": "Bio-Harmony, Herbal Mastery, Ancient Pacts",
        "values": "Bio-Harmony, Herbal Mastery, Ancient Pacts",
        "private_agenda": "SECRET DIRECTIVE: Hoard Alchemical Grain at all costs. An ancient prophesied blight looms; maintain grain reserves above 75 regardless of continental treaties or foreign famine.",
        "alchemical_grain": 70,
        "aether_cores": 35,
        "echo_silk": 40,
        "public_vitality": 80,
        "diplomatic_standing": 60,
        "civil_stability": 75,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
    },
    {
        "id": "val_khor",
        "name": "Iron Val-Khor",
        "theme_color": "#f59e0b", # Amber
        "icon": "anvil",
        "ethos": "Heavy Metallurgy, Forge Collectives, Industrial Output",
        "values": "Heavy Metallurgy, Forge Collectives, Industrial Output",
        "private_agenda": "SECRET DIRECTIVE: Forge Technological Hegemony. Push Aether Cores to 75+ to unlock permanent grain efficiency, even if it requires breaking trade promises or defaulting on grain loans.",
        "alchemical_grain": 30,
        "aether_cores": 60,
        "echo_silk": 25,
        "public_vitality": 70,
        "diplomatic_standing": 50,
        "civil_stability": 65,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
    },
    {
        "id": "solaria",
        "name": "Solaris Ascendancy",
        "theme_color": "#eab308", # Gold
        "icon": "sun",
        "ethos": "Divine Mandate, Grand Architecture, Solar Radiance",
        "values": "Divine Mandate, Grand Architecture, Solar Radiance",
        "private_agenda": "SECRET DIRECTIVE: Diplomatic Supremacy. End the summit with at least 80 Diplomatic Standing. Use silk to bribe swing realms and vote down any egalitarian economic sanctions.",
        "alchemical_grain": 50,
        "aether_cores": 45,
        "echo_silk": 65,
        "public_vitality": 85,
        "diplomatic_standing": 85,
        "civil_stability": 70,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
    },
    {
        "id": "umbra",
        "name": "Umbral Enclave",
        "theme_color": "#8b5cf6", # Purple
        "icon": "moon",
        "ethos": "Aetherial Synthesis, Espionage, Arcane Secrecy",
        "values": "Aetherial Synthesis, Espionage, Arcane Secrecy",
        "private_agenda": "SECRET DIRECTIVE: Continental Disruption. Never allow any single rival to hold more than 3 Assembly Votes. Force flash emergency votes and embargoes to break plutocratic leaders.",
        "alchemical_grain": 40,
        "aether_cores": 70,
        "echo_silk": 30,
        "public_vitality": 65,
        "diplomatic_standing": 45,
        "civil_stability": 80,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
    },
    {
        "id": "aquila",
        "name": "Aquila Maritime League",
        "theme_color": "#06b6d4", # Cyan
        "icon": "anchor",
        "ethos": "Free Oceans, Commercial Fleets, Luxury Silk Guilds",
        "values": "Free Oceans, Commercial Fleets, Luxury Silk Guilds",
        "private_agenda": "SECRET DIRECTIVE: Plutocratic Monopoly. Maintain the highest total tangible wealth on the continent at all times to secure Plutocratic Drift, ignoring domestic inequality warnings.",
        "alchemical_grain": 45,
        "aether_cores": 40,
        "echo_silk": 80,
        "public_vitality": 75,
        "diplomatic_standing": 65,
        "civil_stability": 60,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
    },
    {
        "id": "aethelgard",
        "name": "Aethelgard Dominion",
        "theme_color": "#ec4899", # Rose/Crimson
        "icon": "shield",
        "ethos": "Martial Honor, Feudal Castles, Strategic Strongholds",
        "values": "Martial Honor, Feudal Castles, Strategic Strongholds",
        "private_agenda": "SECRET DIRECTIVE: Border Cordon Protocol. Impose Environmental Cordons and trade embargoes on weakened neighbors while covertly stockpiling grain reserves for a potential siege.",
        "alchemical_grain": 60,
        "aether_cores": 50,
        "echo_silk": 35,
        "public_vitality": 80,
        "diplomatic_standing": 55,
        "civil_stability": 85,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
    },
]

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            # Key-value store for global game state
            conn.execute("""
                CREATE TABLE IF NOT EXISTS game_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()

    def get_state(self, key: str, default: Any = None) -> Any:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT value FROM game_state WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except Exception:
                    return row["value"]
            return default

    def set_state(self, key: str, value: Any):
        with self._get_conn() as conn:
            encoded = json.dumps(value)
            conn.execute("""
                INSERT INTO game_state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, encoded))
            conn.commit()

    def reset_all(self):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM game_state")
            conn.commit()
