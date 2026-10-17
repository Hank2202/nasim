"""
Data models, schema, and persistence layer for The Summit of Realms.
Uses SQLite for state persistence so server restarts or accidental reloads
never wipe simulation progress.
"""

import json
import os
import sqlite3
import time
from typing import Dict, List, Optional, Any

DB_PATH = os.environ.get("SUMMIT_DB_PATH", "summit.db")

DEFAULT_REALMS = [
    {
        "id": "sylvan",
        "name": "Sylvan Concordat",
        "theme_color": "#10b981", # Emerald
        "icon": "leaf",
        "emoji": "🌿",
        "ethos": "Bio-Harmony, Herbal Mastery, Ancient Pacts",
        "values": "Bio-Harmony, Herbal Mastery, Ancient Pacts",
        "active": True,
        "player_count": 2,
        "base_votes": 2,
        "alchemical_grain": 100,
        "aether_cores": 25,
        "echo_silk": 30,
        "military_power": 25,
        "public_vitality": 85,
        "diplomatic_standing": 65,
        "civil_stability": 80,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
        "public_mission": {
            "title": "Feed the Continent",
            "description": "At the end of the summit, no active nation may starve (no state may finish with 0 Grain)."
        },
        "secret_missions_pool": [
            {
                "id": "sylvan_winter",
                "title": "Prepare for the Long Winter",
                "narrative": "Our scientists believe the failed harvest is not an isolated event. Climate patterns indicate that another, even more severe harvest failure may follow. The government has ordered you to protect Sylvan’s strategic food reserves at all costs.",
                "objective": "Sylvan must finish the summit with at least 70 Grain."
            },
            {
                "id": "sylvan_defense",
                "title": "Independent Security",
                "narrative": "Intelligence reports suggest that growing food shortages could eventually lead to military pressure on Sylvan. The government refuses to become dependent on Aethelgard for its security.",
                "objective": "Finish with at least 40 Military and do not purchase Military from Aethelgard."
            }
        ]
    },
    {
        "id": "val_khor",
        "name": "Iron Val-Khor",
        "theme_color": "#f59e0b", # Amber
        "icon": "anvil",
        "emoji": "⚒️",
        "ethos": "Heavy Metallurgy, Forge Collectives, Industrial Output",
        "values": "Heavy Metallurgy, Forge Collectives, Industrial Output",
        "active": True,
        "player_count": 3,
        "base_votes": 2,
        "alchemical_grain": 30,
        "aether_cores": 80,
        "echo_silk": 25,
        "military_power": 65,
        "public_vitality": 70,
        "diplomatic_standing": 50,
        "civil_stability": 70,
        "tech_efficiency_unlocked": True,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
        "public_mission": {
            "title": "Continental Modernisation",
            "description": "By the end of the summit, at least 4 nations must reach 60 Cores."
        },
        "secret_missions_pool": [
            {
                "id": "valkhor_tech",
                "title": "Technological Hegemony",
                "narrative": "Val-Khor's prosperity depends on its technological advantage. The government fears that sharing too much industrial knowledge could allow another power to challenge our position. Help modernise the continent – but make sure Val-Khor remains indispensable.",
                "objective": "Finish with at least 20 more Cores than any other country."
            },
            {
                "id": "valkhor_grain",
                "title": "Workers' Bread",
                "narrative": "Confidential government forecasts show that Val-Khor's food reserves are dangerously low. A prolonged crisis could trigger unrest among workers and threaten industrial production.",
                "objective": "Finish with at least 30 Grain."
            },
            {
                "id": "valkhor_contain_military",
                "title": "Strategic Parity",
                "narrative": "Military intelligence is increasingly concerned about Aethelgard's growing armed forces. A major military imbalance would leave Val-Khor vulnerable to political pressure.",
                "objective": "Aethelgard must not finish more than 10 Military ahead of Val-Khor."
            }
        ]
    },
    {
        "id": "solaria",
        "name": "Solaris Ascendancy",
        "theme_color": "#eab308", # Gold
        "icon": "sun",
        "emoji": "☀️",
        "ethos": "Divine Mandate, Grand Architecture, Solar Radiance",
        "values": "Divine Mandate, Grand Architecture, Solar Radiance",
        "active": True,
        "player_count": 4,
        "base_votes": 3,
        "alchemical_grain": 50,
        "aether_cores": 40,
        "echo_silk": 75,
        "military_power": 45,
        "public_vitality": 85,
        "diplomatic_standing": 90,
        "civil_stability": 80,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
        "public_mission": {
            "title": "Preserve the International Order",
            "description": "During the summit, at least 3 international resolutions must pass, each supported by votes from at least 4 different nations."
        },
        "secret_missions_pool": [
            {
                "id": "solaris_veto",
                "title": "Control the Assembly",
                "narrative": "For decades, Solaris has been the architect of the continental order. The government believes that any major decision openly opposed by Solaris would signal the beginning of its political decline.",
                "objective": "No resolution that Solaris votes against may pass."
            },
            {
                "id": "solaris_standing",
                "title": "Diplomatic Leadership",
                "narrative": "Solaris's influence depends not only on wealth or military power, but on its reputation. The government expects Solaris to remain the country others look to for leadership.",
                "objective": "Finish with the highest Standing on the continent."
            },
            {
                "id": "solaris_contain_valkhor",
                "title": "Check Industrial Rivals",
                "narrative": "Intelligence services warn that Val-Khor's combination of industrial and military power could eventually challenge the continental order. It must not dominate both sectors simultaneously.",
                "objective": "Val-Khor must not finish with both the highest Cores and the highest Military."
            },
            {
                "id": "solaris_silk",
                "title": "Domestic Prosperity",
                "narrative": "Solaris's citizens have grown accustomed to prosperity. A dramatic decline in luxury goods would undermine public confidence in the government.",
                "objective": "Finish with at least 50 Silk."
            }
        ]
    },
    {
        "id": "umbra",
        "name": "Umbral Enclave",
        "theme_color": "#8b5cf6", # Purple
        "icon": "moon",
        "emoji": "🌙",
        "ethos": "Aetherial Synthesis, Espionage, Arcane Secrecy",
        "values": "Aetherial Synthesis, Espionage, Arcane Secrecy",
        "active": True,
        "player_count": 1,
        "base_votes": 1,
        "alchemical_grain": 40,
        "aether_cores": 70,
        "echo_silk": 30,
        "military_power": 55,
        "public_vitality": 65,
        "diplomatic_standing": 40,
        "civil_stability": 70,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
        "public_mission": {
            "title": "Balance of Power",
            "description": "At the end of the summit, no nation may hold more than 90 Military."
        },
        "secret_missions_pool": [
            {
                "id": "umbra_challenge",
                "title": "Break the Hegemon",
                "narrative": "Umbra has watched Solaris shape the continental order for decades while smaller nations were expected to follow. Your government believes that a stable continent requires proof that Solaris can be challenged. However, Umbra cannot afford to become internationally isolated in the process.",
                "objective": "At least one resolution supported by Solaris must fail, while Umbra must finish with at least 50 Standing."
            },
            {
                "id": "umbra_autonomy",
                "title": "Sovereign Independence",
                "narrative": "Ensure Umbra preserves independent defense and economic integrity without bowing to larger empires.",
                "objective": "Finish with at least 60 Cores and at least 60 Stability."
            }
        ]
    },
    {
        "id": "aquila",
        "name": "Aquila Maritime League",
        "theme_color": "#06b6d4", # Cyan
        "icon": "anchor",
        "emoji": "⚓",
        "ethos": "Free Oceans, Commercial Fleets, Luxury Silk Guilds",
        "values": "Free Oceans, Commercial Fleets, Luxury Silk Guilds",
        "active": True,
        "player_count": 2,
        "base_votes": 2,
        "alchemical_grain": 50,
        "aether_cores": 40,
        "echo_silk": 80,
        "military_power": 35,
        "public_vitality": 80,
        "diplomatic_standing": 70,
        "civil_stability": 70,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
        "public_mission": {
            "title": "Connect the Continent",
            "description": "Every active nation must successfully trade with at least 2 different nations."
        },
        "secret_missions_pool": [
            {
                "id": "aquila_wealth",
                "title": "Commercial Supremacy",
                "narrative": "Aquila's influence has always come from commerce rather than armies. The government sees the current instability as an opportunity to establish Aquila as the economic centre of the continent.",
                "objective": "Finish as the wealthiest country (Grain + Cores + Silk), at least 25 points ahead of the second wealthiest."
            },
            {
                "id": "aquila_trade_network",
                "title": "Indispensable Partner",
                "narrative": "Aquila's long-term security depends on making itself useful to as many nations as possible. A country connected to everyone is difficult to isolate.",
                "objective": "Successfully trade with at least four of the other five countries."
            }
        ]
    },
    {
        "id": "aethelgard",
        "name": "Aethelgard Dominion",
        "theme_color": "#ec4899", # Rose/Crimson
        "icon": "shield",
        "emoji": "🛡️",
        "ethos": "Martial Honor, Feudal Castles, Strategic Strongholds",
        "values": "Martial Honor, Feudal Castles, Strategic Strongholds",
        "active": True,
        "player_count": 3,
        "base_votes": 2,
        "alchemical_grain": 60,
        "aether_cores": 50,
        "echo_silk": 25,
        "military_power": 80,
        "public_vitality": 80,
        "diplomatic_standing": 55,
        "civil_stability": 85,
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
        "public_mission": {
            "title": "Continental Security",
            "description": "No active nation may finish with Stability < 50, and no nation may hit Stability 0 during the summit."
        },
        "secret_missions_pool": [
            {
                "id": "aethelgard_superiority",
                "title": "Peace Through Strength",
                "narrative": "Aethelgard's military doctrine is simple: war is least likely when no rival believes it can defeat us. With tensions rising, the government considers overwhelming military superiority the best guarantee of peace.",
                "objective": "Finish with the highest Military, at least 20 ahead of the second strongest country."
            },
            {
                "id": "aethelgard_contain_valkhor",
                "title": "Contain Rearmament",
                "narrative": "Intelligence reports indicate that Val-Khor is rapidly expanding its military-industrial capacity. If left unchecked, it could become the first genuine strategic threat to Aethelgard in decades.",
                "objective": "Val-Khor must finish with no more than 75 Military."
            },
            {
                "id": "aethelgard_reserves",
                "title": "Strategic Reserves",
                "narrative": "Military strength means little if Aethelgard cannot sustain itself through a prolonged crisis. The government has ordered the creation of strategic reserves.",
                "objective": "Finish with at least 35 Grain and 35 Cores."
            }
        ]
    },
]

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            # Key-value store for global game state
            conn.execute("""
                CREATE TABLE IF NOT EXISTS game_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            # Rolling autosaves (snapshots of game_state), newest kept
            conn.execute("""
                CREATE TABLE IF NOT EXISTS autosaves (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created REAL NOT NULL,
                    label TEXT NOT NULL,
                    data TEXT NOT NULL
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

    # ------------------------------------------------------------------ saves
    def dump_all(self) -> Dict[str, Any]:
        """The whole game state as one JSON-able dict (a save file)."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT key, value FROM game_state").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    def restore_all(self, snapshot: Dict[str, Any]):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM game_state")
            conn.executemany("INSERT INTO game_state (key, value) VALUES (?, ?)",
                             [(k, json.dumps(v)) for k, v in snapshot.items()])
            conn.commit()

    def add_autosave(self, snapshot: Dict[str, Any], label: str, keep: int = 12) -> int:
        with self._get_conn() as conn:
            cur = conn.execute("INSERT INTO autosaves (created, label, data) VALUES (?, ?, ?)",
                               (time.time(), label, json.dumps(snapshot)))
            conn.execute("DELETE FROM autosaves WHERE id NOT IN (SELECT id FROM autosaves ORDER BY id DESC LIMIT ?)", (keep,))
            conn.commit()
            return cur.lastrowid

    def list_autosaves(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT id, created, label FROM autosaves ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def get_autosave(self, save_id: int) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT data FROM autosaves WHERE id = ?", (save_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def reset_all(self):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM game_state")
            conn.commit()
