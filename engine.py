"""
Socioeconomic simulation engine for The Summit of Realms.
Driven by scenario_config.json for 100% AI and Facilitator configurability.
Handles:
  - Exact Wall-Clock Timer Synchronization (zero polling-induced speedups)
  - Dynamic Event Targeting Engine (e.g. 'highest 1 by alchemical_grain', 'lowest 3 by public_vitality')
  - Automated Background Event Scheduling (triggers at turn start / mid-turn)
  - Sovereign Domestic Governance Levers (Emergency Grain Relief, Arcane Forges, Gala, Guard)
  - Qualitative Fog of War indicators for rivals and public views
  - Phase state machine: 5-minute Working Session -> Plenary Voting Session
  - Grand Plenary sequential 5-minute discussion and voting for Round 3
  - Targeted and Open motion seconding/endorsements (>= 2 countries to qualify)
  - Delegation 4-digit PIN authentication
  - Direct Facilitator time editing (+1m, +2m, exact input)
"""

import json
import os
import random
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple
from models import Database, DEFAULT_REALMS

SCENARIO_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenario_config.json")

def load_scenario_config() -> Dict[str, Any]:
    if os.path.exists(SCENARIO_CONFIG_FILE):
        try:
            with open(SCENARIO_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def load_events_catalog() -> List[Dict[str, Any]]:
    config = load_scenario_config()
    return config.get("events_catalog", [])

# Secret missions that only make sense when another nation takes part in the summit.
MISSION_REQUIRES = {
    "sylvan_defense": ("aethelgard",),
    "valkhor_contain_military": ("aethelgard",),
    "solaris_contain_valkhor": ("val_khor",),
    "umbra_challenge": ("solaria",),
    "aethelgard_contain_valkhor": ("val_khor",),
}

RESOURCE_FIELDS = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk",
                   "military": "military_power", "standing": "diplomatic_standing", "stability": "civil_stability"}
RESOURCE_LABELS = {"grain": "Grain", "cores": "Cores", "silk": "Silk", "military": "Military",
                   "standing": "Standing", "stability": "Stability"}

QUIZ_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lore_quiz.json")
_quiz_cache: Dict[str, Any] = {"mtime": None, "data": None}

def load_quiz() -> Dict[str, Any]:
    mtime = os.path.getmtime(QUIZ_PATH)
    if _quiz_cache["mtime"] != mtime:
        with open(QUIZ_PATH, "r", encoding="utf-8") as f:
            _quiz_cache.update(mtime=mtime, data=json.load(f))
    return _quiz_cache["data"]


class SummitEngine:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.active_sessions: Dict[str, Dict[str, float]] = {}
        self.SESSION_TIMEOUT_SECONDS = 45.0
        self._ensure_initial_state()

    def register_realm_session(self, realm_id: str, session_id: str) -> None:
        """Registers or refreshes an active participant session for a realm."""
        if not realm_id or not session_id:
            return
        now = time.time()
        if realm_id not in self.active_sessions:
            self.active_sessions[realm_id] = {}
        self.active_sessions[realm_id][session_id] = now

    def remove_realm_session(self, realm_id: str, session_id: str) -> None:
        """Removes a session (e.g. on logout or leave)."""
        if realm_id in self.active_sessions and session_id in self.active_sessions[realm_id]:
            del self.active_sessions[realm_id][session_id]

    def clear_realm_sessions(self, realm_id: Optional[str] = None) -> None:
        """Clears sessions for a specific realm or all realms."""
        if realm_id:
            self.active_sessions[realm_id] = {}
        else:
            self.active_sessions.clear()

    def prune_expired_sessions(self) -> None:
        """Removes sessions that haven't been seen within SESSION_TIMEOUT_SECONDS."""
        now = time.time()
        for r_id in list(self.active_sessions.keys()):
            self.active_sessions[r_id] = {
                s_id: ts for s_id, ts in self.active_sessions[r_id].items()
                if now - ts <= self.SESSION_TIMEOUT_SECONDS
            }

    def get_connected_player_count(self, realm_id: str) -> int:
        """Returns the number of currently active sessions for a realm."""
        self.prune_expired_sessions()
        return len(self.active_sessions.get(realm_id, {}))

    def is_realm_capacity_full(self, realm_id: str, capacity: Optional[int] = None) -> bool:
        """Returns True if connected players >= capacity."""
        if capacity is None:
            realms = self.db.get_state("realms", [])
            r = next((x for x in realms if x["id"] == realm_id), None)
            capacity = r.get("player_count", 2) if r else 2
        return self.get_connected_player_count(realm_id) >= capacity

    def is_session_registered(self, realm_id: str, session_id: str) -> bool:
        """Checks if this specific session_id is currently registered for realm_id."""
        self.prune_expired_sessions()
        return session_id in self.active_sessions.get(realm_id, {})

    # -------------------------------------------------------------------------
    # Per-game settings (facilitator setup screen); defaults in scenario_config.json
    # -------------------------------------------------------------------------
    SETTING_LIMITS = {
        "working_session_seconds": (60, 3600), "plenary_vote_seconds": (30, 900),
        "debate_session_seconds": (30, 1200), "grand_vote_seconds": (20, 600),
        "intermission_seconds": (0, 600), "minor_events_per_turn": (0, 30), "large_events_per_turn": (0, 10),
        "motions_per_turn": (1, 10),
    }
    FLOAT_SETTING_LIMITS = {"minor_event_max": (1, 50)}

    def settings(self) -> Dict[str, Any]:
        cfg = load_scenario_config()
        s = dict(cfg.get("game_settings_defaults", {}))
        s.update(self.db.get_state("settings", {}) or {})
        s["max_turns"] = cfg.get("simulation_settings", {}).get("max_turns", 3)
        diff = cfg.get("difficulties", {}).get(s.get("difficulty"), {})
        s["grain_consumption"] = diff.get("grain_consumption", 20)
        s["positive_share"] = diff.get("positive_share", 0.5)
        s["famine_storyline"] = bool(cfg.get("scenarios", {}).get(s.get("scenario"), {}).get("famine_storyline", False))
        return s

    def update_settings(self, changes: Dict[str, Any]) -> Tuple[bool, str]:
        cfg = load_scenario_config()
        current = self.db.get_state("settings", {}) or {}
        for key, value in (changes or {}).items():
            if key in self.SETTING_LIMITS:
                lo, hi = self.SETTING_LIMITS[key]
                try:
                    current[key] = int(max(lo, min(hi, int(value))))
                except (TypeError, ValueError):
                    return False, f"{key} must be a number."
            elif key in self.FLOAT_SETTING_LIMITS:
                lo, hi = self.FLOAT_SETTING_LIMITS[key]
                try:
                    current[key] = round(max(lo, min(hi, float(value))), 1)
                except (TypeError, ValueError):
                    return False, f"{key} must be a number."
            elif key == "auto_advance":
                current[key] = bool(value)
            elif key == "scenario" and value in cfg.get("scenarios", {}):
                current[key] = value
            elif key == "difficulty" and value in cfg.get("difficulties", {}):
                current[key] = value
        self.db.set_state("settings", current)
        # A changed working-session length applies straight away if the session has not started yet.
        meta = self.db.get_state("meta", {}) or {}
        if "working_session_seconds" in changes and meta.get("phase") == "working" and not meta.get("is_timer_running") \
                and meta.get("turn_timer_remaining") == meta.get("turn_timer_total"):
            meta["turn_timer_remaining"] = meta["turn_timer_total"] = current["working_session_seconds"]
            self.db.set_state("meta", meta)
        # New event counts apply to the rest of this working session: drop its plan and plan the remainder anew.
        if {"minor_events_per_turn", "large_events_per_turn", "working_session_seconds"} & set(changes or {}):
            meta = self.db.get_state("meta", {}) or {}
            schedule = meta.get("minor_event_schedule") or {}
            key = str(meta.get("current_turn", 1))
            if key in schedule and meta.get("phase") == "working":
                total = meta.get("turn_timer_total", 1200)
                elapsed = total - meta.get("turn_timer_remaining", total)
                s = self.settings()
                left = lambda n, done: sorted(random.uniform(max(elapsed + 5, 0.08 * total), 0.92 * total)
                                              for _ in range(max(0, int(n) - done))) if elapsed < 0.92 * total else []
                old = schedule[key]
                schedule[key] = {"times": left(s["minor_events_per_turn"], old.get("fired", 0)), "fired": 0,
                                 "large_times": left(s["large_events_per_turn"], old.get("large_fired", 0)), "large_fired": 0}
                self.db.set_state("meta", meta)
        return True, "Settings saved."

    def _ensure_initial_state(self):
        if self.db.get_state("meta") is None:
            self.reset_simulation()

    def reset_simulation(self):
        """Reset the simulation back to Turn 1 using parameters from scenario_config.json."""
        config = load_scenario_config()
        settings = self.settings()
        working_secs = settings.get("working_session_seconds", 1200)
        debate_secs = settings.get("debate_session_seconds", 300)

        meta = {
            "current_turn": 1,
            "phase": "working",
            "round_type": "quick",
            "turn_timer_remaining": working_secs,
            "turn_timer_total": working_secs,
            "turn_timer_end": None, # Wall-clock target timestamp
            "is_timer_running": False,
            "discussion_timer_remaining": debate_secs,
            "discussion_timer_total": debate_secs,
            "discussion_timer_end": None,
            "is_discussion_timer_running": False,
            "plenary_docket": [],
            "current_motion_index": 0,
            "vote_timer_end": None,
            "vote_timer_remaining": 0,
            "intermission_end": None,
            "minor_event_schedule": {},
            "final_consumption_done": False,
            "triggered_events": [],
            "latest_catastrophe": None,
            "audio_cue": {
                "seq": 0,
                "type": "none",
                "message": ""
            }
        }
        self.db.set_state("meta", meta)
        
        raw_realms = config.get("realms") or DEFAULT_REALMS
        realms = [dict(r) for r in raw_realms]
        for r in realms:
            r.setdefault("claimed_lore", [])
            r.setdefault("failed_lore", [])
        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)
        
        self.db.set_state("trades", [])
        self.db.set_state("trade_partners", {})     # who traded with whom (Aquila's missions)
        self.db.set_state("military_trades", [])    # military sales (Sylvan's independence mission)
        self.db.set_state("news_archive", [])       # full timeline for the results report
        self.db.set_state("proposals", [])
        self.db.set_state("active_assembly", None)
        self.db.set_state("summit_outcome", None)
        
        init_news_conf = config.get("initial_news") or [
            {
                "type": "system",
                "headline": "THE SUMMIT CONVENES",
                "detail": "Delegates have assembled at the Neutral Spire. Turn 1 Working Session (5 Minutes) is officially underway."
            }
        ]

        initial_news = []
        for n in init_news_conf:
            initial_news.append({
                "id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "time_str": "Turn 1 (T+00:00)",
                "type": n.get("type", "system"),
                "headline": n.get("headline", ""),
                "detail": n.get("detail", "")
            })
        self.db.set_state("news_feed", initial_news)

    def _format_now(self) -> str:
        meta = self.db.get_state("meta")
        if not meta:
            return "Turn 1 (T+00:00)"
        turn = meta.get("current_turn", 1)
        total = meta.get("turn_timer_total", 300)
        rem = meta.get("turn_timer_remaining", 300)
        elapsed = max(0, total - rem)
        mins = elapsed // 60
        secs = elapsed % 60
        return f"Turn {turn} (T+{mins:02d}:{secs:02d})"

    @staticmethod
    def get_qualitative_tier(resource_type: str, value: int) -> str:
        """Translates exact numerical values into qualitative tier assessments: LOW / MEDIUM / HIGH."""
        if resource_type in ("grain", "cores", "silk", "military"):
            if value >= 60:
                return "HIGH"
            elif value >= 30:
                return "MEDIUM"
            else:
                return "LOW"
        else:
            if value >= 70:
                return "HIGH"
            elif value >= 40:
                return "MEDIUM"
            else:
                return "LOW"

    def get_realm_missions(self, realm: Any, all_realms: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Returns public mission and active secret missions scaled to player_count and total active realm count."""
        if isinstance(realm, str):
            realms = all_realms or self.db.get_state("realms", [])
            realm_obj = next((r for r in realms if r["id"] == realm), None)
            realm = realm_obj or {}

        realms = all_realms or self.db.get_state("realms", [])
        active_realms = [r for r in realms if r.get("active", True)]
        N = max(1, len(active_realms))

        raw_pub = realm.get("public_mission") or {}
        pub_title = raw_pub.get("title", "Public Mandate")
        pub_desc = raw_pub.get("description", "Ensure national survival and fulfill sovereign responsibilities.")

        r_id = realm.get("id", "")
        # Dynamically scale public mission description based on N
        if r_id == "val_khor":
            target_cores = max(2, min(N, round(4 * N / 6)))
            pub_title = "Continental Modernisation"
            pub_desc = f"By the end of the summit, at least {target_cores} of {N} nations must reach 60 Cores."
        elif r_id == "solaria":
            support_req = max(2, min(N - 1, 4))
            pub_title = "Preserve the International Order"
            pub_desc = f"During the summit, at least 3 international resolutions must pass, each receiving votes from at least {support_req} different nations."
        elif r_id == "aquila":
            target_partners = max(1, min(2, N - 1))
            pub_title = "Connect the Continent"
            pub_desc = f"Every active nation must successfully trade with at least {target_partners} different nations during the summit."
        elif r_id == "sylvan":
            pub_title = "Feed the Continent"
            pub_desc = "At the end of the summit, no active nation may starve (no state may finish with 0 Grain)."
        elif r_id == "umbra":
            pub_title = "Balance of Power"
            pub_desc = "At the end of the summit, no nation may hold more than 90 Military."
        elif r_id == "aethelgard":
            pub_title = "Continental Security"
            pub_desc = "No active nation may finish with Stability < 50, and no nation may hit Stability 0 during the summit."

        public_mission = {
            "title": pub_title,
            "description": pub_desc
        }

        pool = realm.get("secret_missions_pool") or []
        player_count = max(1, int(realm.get("player_count", 1)))
        active_ids = {r.get("id") for r in active_realms}
        # A secret mission about another nation only makes sense if that nation is playing.
        playable_pool = [sm for sm in pool
                         if all(dep in active_ids for dep in MISSION_REQUIRES.get(sm.get("id", ""), ()))]

        active_secrets = []
        for sm in playable_pool[:player_count]:
            sm_copy = dict(sm)
            sm_id = sm_copy.get("id", "")
            if sm_id == "aquila_trade_network":
                req_target = max(1, min(4, N - 1))
                sm_copy["objective"] = f"Successfully trade with at least {req_target} of the other {N - 1} nations."
            active_secrets.append(sm_copy)

        return {
            "public": public_mission,
            "secrets": active_secrets,
            "secret_missions": active_secrets,
            "player_count": player_count
        }

    def _recalculate_all_realms(self, realms: List[Dict[str, Any]]):
        for r in realms:
            if "ethos" not in r:
                r["ethos"] = r.get("values", "")
            if "values" not in r:
                r["values"] = r.get("ethos", "")
            if "pin" not in r:
                r["pin"] = "1001"
            if "military_power" not in r:
                r["military_power"] = 50
            if "active" not in r:
                r["active"] = True
            if "player_count" not in r:
                r["player_count"] = 2
            p_count = max(1, int(r.get("player_count", 2)))
            r["player_count"] = p_count
            connected = self.get_connected_player_count(r.get("id", ""))
            r["connected_players"] = connected
            r["is_capacity_full"] = (connected >= p_count)

            # Total wealth = Grain + Cores + Silk (per MGV document, Military is separate)
            r["total_wealth"] = (
                r.get("alchemical_grain", 0) +
                r.get("aether_cores", 0) +
                r.get("echo_silk", 0)
            )

            r["grain_tier"] = self.get_qualitative_tier("grain", r.get("alchemical_grain", 0))
            r["cores_tier"] = self.get_qualitative_tier("cores", r.get("aether_cores", 0))
            r["silk_tier"] = self.get_qualitative_tier("silk", r.get("echo_silk", 0))
            r["military_tier"] = self.get_qualitative_tier("military", r.get("military_power", 0))
            r["vitality_tier"] = self.get_qualitative_tier("vitality", r.get("public_vitality", 0))
            r["standing_tier"] = self.get_qualitative_tier("standing", r.get("diplomatic_standing", 0))
            r["stability_tier"] = self.get_qualitative_tier("stability", r.get("civil_stability", 0))

            # Base votes from configuration (per MGV document table: Solaris 3, Umbra 1, others 2)
            base_votes = r.get("base_votes", 2)
            r["base_votes"] = base_votes
            r["bonus_votes"] = 0
            r["assembly_votes"] = base_votes
            r["is_plutocrat"] = False

            # Missions assignment scaled to player count and active nations
            missions = self.get_realm_missions(r, all_realms=realms)
            r["public_mission"] = missions["public"]
            r["active_secret_missions"] = missions["secrets"]

            if r.get("aether_cores", 0) >= 75:
                r["tech_efficiency_unlocked"] = True

            r["is_starving"] = r.get("alchemical_grain", 0) <= 0
            r["complacency_warning"] = (
                r.get("civil_stability", 0) >= 85 and
                r.get("public_vitality", 0) >= 85 and
                r.get("echo_silk", 0) < 10
            )

            # Check if any realm reached Stability 0 during the game
            if r.get("civil_stability", 0) <= 0:
                meta = self.db.get_state("meta", {})
                if meta and not meta.get("any_stability_zero_reached", False):
                    meta["any_stability_zero_reached"] = True
                    self.db.set_state("meta", meta)

        active_realms = [r for r in realms if r.get("active", True)]
        if active_realms:
            max_wealth = max(r["total_wealth"] for r in active_realms)
            wealthiest_realms = [r for r in active_realms if r["total_wealth"] == max_wealth]
            if len(wealthiest_realms) == 1:
                wealthiest = wealthiest_realms[0]
                wealthiest["is_plutocrat"] = True
                wealthiest["bonus_votes"] = 1
                wealthiest["assembly_votes"] = wealthiest["base_votes"] + 1

    # -------------------------------------------------------------------------
    # State Polling with Exact Wall-Clock Timer Math & Auto-Event Check
    # -------------------------------------------------------------------------
    AUTOSAVE_INTERVAL = 300  # seconds

    def autosave(self, label: Optional[str] = None, force: bool = False) -> Optional[int]:
        """Snapshot the whole game every AUTOSAVE_INTERVAL seconds (checked on each state poll)."""
        now = time.time()
        if not force and now - getattr(self, "_last_autosave", 0) < self.AUTOSAVE_INTERVAL:
            return None
        self._last_autosave = now
        meta = self.db.get_state("meta", {}) or {}
        label = label or f"Autosave · Turn {meta.get('current_turn', 1)} · {meta.get('phase', 'working').replace('_', ' ')}"
        return self.db.add_autosave(self.db.dump_all(), label)

    def restore_snapshot(self, snapshot: Dict[str, Any]) -> Tuple[bool, str]:
        if not isinstance(snapshot, dict) or "realms" not in snapshot or "meta" not in snapshot:
            return False, "That is not a Summit of Realms save."
        self.autosave(label="Before restore", force=True)   # so a mistaken restore can be undone
        self.db.restore_all(snapshot)
        meta = snapshot.get("meta", {})
        if meta.get("is_timer_running"):                       # resume the clock from the saved remaining time
            meta["turn_timer_end"] = time.time() + meta.get("turn_timer_remaining", 0)
            self.db.set_state("meta", meta)
        self.add_news("diplomacy", "SUMMIT RESTORED", "The facilitator restored the summit from a saved game.")
        return True, f"Game restored (Turn {meta.get('current_turn', 1)})."

    def get_full_state(self) -> Dict[str, Any]:
        self.autosave()
        self._tick()
        meta = self.db.get_state("meta", {})
        realms = self.db.get_state("realms", [])
        trades = self.db.get_state("trades", [])
        proposals = self.db.get_state("proposals", [])
        active_assembly = self.db.get_state("active_assembly", None)
        news_feed = self.db.get_state("news_feed", [])

        self.prune_expired_sessions()
        for r in realms:
            r_id = r.get("id", "")
            connected = len(self.active_sessions.get(r_id, {}))
            capacity = max(1, int(r.get("player_count", 2)))
            r["connected_players"] = connected
            r["is_capacity_full"] = (connected >= capacity)

        active_realms = [r for r in realms if r.get("active", True)]
        meta["active_realms_count"] = len(active_realms)
        meta["total_realms_count"] = len(realms)

        self._add_display_timer(meta)
        self._recalculate_all_realms(realms)

        cfg = load_scenario_config()
        return {
            "meta": meta,
            "realms": realms,
            "trades": trades,
            "proposals": proposals,
            "active_assembly": active_assembly,
            "news_feed": news_feed,
            "world_lore": cfg.get("world_lore", {}),
            "resolution_types": cfg.get("resolution_types", []),
            "simulation_settings": cfg.get("simulation_settings", {}),
            "catastrophes_catalog": cfg.get("catastrophes_catalog", []),
            "summit_outcome": self.db.get_state("summit_outcome", None),
            "game_settings": self.settings(),
            "reflection_questions": cfg.get("reflection_questions", [])
        }

    # -------------------------------------------------------------------------
    # Clock: timers, automatic phase changes and small events (runs on every state poll)
    # -------------------------------------------------------------------------
    def _tick(self):
        meta = self.db.get_state("meta", {}) or {}
        if not meta:
            return
        s = self.settings()
        auto = bool(s.get("auto_advance", True))
        now = time.time()
        phase = meta.get("phase")

        # Short pause before an automatically started turn (time to read out the breaking news).
        if meta.get("intermission_end") and phase == "working":
            if now >= meta["intermission_end"]:
                meta["intermission_end"] = None
                meta["is_timer_running"] = True
                meta["turn_timer_end"] = now + meta.get("turn_timer_remaining", s["working_session_seconds"])
                self.db.set_state("meta", meta)
                self.trigger_audio_cue("gong", f"Turn {meta.get('current_turn', 1)} begins")
            return

        # Working-session clock
        if meta.get("is_timer_running"):
            end = meta.get("turn_timer_end") or now + meta.get("turn_timer_remaining", 300)
            meta["turn_timer_end"] = end
            rem = max(0, int(round(end - now)))
            meta["turn_timer_remaining"] = rem
            if rem == 0 and phase == "working":
                meta["is_timer_running"] = False
                meta["turn_timer_end"] = None
                self.db.set_state("meta", meta)
                self.trigger_audio_cue("alert", "Time is up! The working session has ended.")
                self.add_news("turn", "TIME IS UP",
                              f"The working session of Turn {meta.get('current_turn', 1)} has ended.")
                if auto:
                    self._advance_after_working()
                return
            self.db.set_state("meta", meta)
            if phase == "working":
                self._check_scheduled_events(meta, s)

        # Grand Plenary debate clock (always opens the vote when it runs out)
        if meta.get("is_discussion_timer_running") and phase == "grand_plenary_discussion":
            end = meta.get("discussion_timer_end") or now + meta.get("discussion_timer_remaining", 300)
            meta["discussion_timer_end"] = end
            rem = max(0, int(round(end - now)))
            meta["discussion_timer_remaining"] = rem
            self.db.set_state("meta", meta)
            if rem == 0:
                self.trigger_audio_cue("alert", "Debate time is up")
                self.start_grand_motion_vote()
            return

        # Voting clocks
        if meta.get("vote_timer_end") and phase in ("plenary_quick", "grand_plenary_voting"):
            rem = max(0, int(round(meta["vote_timer_end"] - now)))
            meta["vote_timer_remaining"] = rem
            self.db.set_state("meta", meta)
            if rem == 0 and auto:
                meta["vote_timer_end"] = None
                self.db.set_state("meta", meta)
                self.trigger_audio_cue("alert", "Voting has closed")
                if phase == "plenary_quick":
                    self.conclude_quick_plenary()
                    self._advance_turn_or_finish()
                else:
                    self.advance_grand_plenary_next()
                    if (self.db.get_state("meta", {}) or {}).get("phase") == "turn_summary":
                        self._advance_turn_or_finish()

    def _qualified_motions(self) -> List[Dict[str, Any]]:
        return [p for p in self.db.get_state("proposals", [])
                if p.get("status") in ("draft", "qualified") and (len(p.get("support_list", [])) >= 2 or p.get("is_qualified"))]

    def _advance_after_working(self):
        """When the working session ends: Assembly vote if there are motions, otherwise end the turn."""
        if self._qualified_motions():
            self.start_plenary_session()
        else:
            self.add_news("assembly", "NO MOTIONS ON THE BALLOT",
                          "No motion found a co-sponsor this turn, so the Assembly does not sit.")
            self._advance_turn_or_finish()

    def _advance_turn_or_finish(self):
        meta = self.db.get_state("meta", {}) or {}
        s = self.settings()
        if meta.get("current_turn", 1) < s["max_turns"]:
            self.process_end_of_turn()
            if s.get("auto_advance", True):
                meta = self.db.get_state("meta", {})
                pause = int(s.get("intermission_seconds", 45))
                if pause > 0:
                    meta["intermission_end"] = time.time() + pause
                else:
                    meta["is_timer_running"] = True
                    meta["turn_timer_end"] = time.time() + meta.get("turn_timer_remaining", 0)
                self.db.set_state("meta", meta)
        else:
            self.conclude_summit()

    def _add_display_timer(self, meta: Dict[str, Any]):
        """One clock for the screens: whatever is counting down in the current phase."""
        phase, now = meta.get("phase"), time.time()
        if meta.get("intermission_end") and phase == "working":
            meta["display_timer"] = {"label": f"Turn {meta.get('current_turn', 1)} starts in", "seconds": max(0, int(meta["intermission_end"] - now))}
        elif phase == "grand_plenary_discussion":
            meta["display_timer"] = {"label": "Debate", "seconds": meta.get("discussion_timer_remaining", 0)}
        elif phase in ("plenary_quick", "grand_plenary_voting") and meta.get("vote_timer_end"):
            meta["display_timer"] = {"label": "Voting closes in", "seconds": max(0, int(meta["vote_timer_end"] - now))}
        else:
            meta["display_timer"] = {"label": "Working session", "seconds": meta.get("turn_timer_remaining", 0)}

    def _check_scheduled_events(self, meta: Dict[str, Any], s: Dict[str, Any]):
        """Random events at random moments of each working session: small news items and, if set, large disasters."""
        key = str(meta.get("current_turn", 1))
        total = meta.get("turn_timer_total", 1200)
        elapsed = total - meta.get("turn_timer_remaining", total)
        schedule = meta.setdefault("minor_event_schedule", {})
        if key not in schedule:
            pick = lambda n: sorted(random.uniform(0.08, 0.92) * total for _ in range(int(n)))
            schedule[key] = {"times": pick(s.get("minor_events_per_turn", 6)), "fired": 0,
                             "large_times": pick(s.get("large_events_per_turn", 0)), "large_fired": 0}
            self.db.set_state("meta", meta)
        entry = schedule[key]
        entry.setdefault("large_times", [])
        entry.setdefault("large_fired", 0)
        # at most one event per poll, so two never land in the same second
        if entry["large_fired"] < len(entry["large_times"]) and elapsed >= entry["large_times"][entry["large_fired"]]:
            entry["large_fired"] += 1
            self.db.set_state("meta", meta)
            self.fire_large_event()
        elif entry["fired"] < len(entry["times"]) and elapsed >= entry["times"][entry["fired"]]:
            entry["fired"] += 1
            self.db.set_state("meta", meta)
            self.fire_minor_event(s)

    def fire_minor_event(self, s: Optional[Dict[str, Any]] = None, tone: Optional[str] = None) -> Tuple[bool, str]:
        """One small news item for one nation. Each effect is a random amount between 0 and the set maximum
        (scaled by the effect's weight in scenario_config.json), never less than 1."""
        s = s or self.settings()
        cfg = load_scenario_config()
        events = cfg.get("minor_events", [])
        realms = self.db.get_state("realms", [])
        active = [r for r in realms if r.get("active", True)]
        if not events or not active:
            return False, "No events or nations."
        tone = tone or ("good" if random.random() < s.get("positive_share", 0.5) else "bad")
        pool = [ev for ev in events if ev.get("tone") == tone] or events
        ev = random.choice(pool)
        realm = random.choice(active)
        cap = float(s.get("minor_event_max", 5))
        fields = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk", "military": "military_power",
                  "vitality": "public_vitality", "standing": "diplomatic_standing", "stability": "civil_stability"}
        labels = {"grain": "Grain", "cores": "Cores", "silk": "Silk", "military": "Military",
                  "vitality": "Vitality", "standing": "Standing", "stability": "Stability"}
        parts = []
        for res, weight in ev.get("effects", {}).items():
            amount = max(1, round(random.uniform(0, cap * abs(weight))))
            amount = amount if weight > 0 else -amount
            field = fields[res]
            value = realm.get(field, 0) + amount
            realm[field] = max(0, min(100, value)) if res in ("vitality", "standing", "stability") else max(0, value)
            parts.append(f"{amount:+d} {labels[res]}")
        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)
        name = realm["name"]
        self.add_news("boon" if ev.get("tone") == "good" else "crisis",
                      ev["headline"].replace("{nation}", name.upper()),
                      ev["detail"].replace("{nation}", name) + f" ({', '.join(parts)})")
        return True, f"{ev['id']} → {name} ({', '.join(parts)})"

    def fire_large_event(self) -> Tuple[bool, str]:
        """A random disaster from the catastrophe catalog, striking a nation whose land suits it."""
        catalog = load_scenario_config().get("catastrophes_catalog", [])
        active = [r for r in self.db.get_state("realms", []) if r.get("active", True)]
        terrains = {r.get("geography", {}).get("terrain") for r in active}
        pool = [c for c in catalog if "all" in c.get("geographic_affinities", [])
                or terrains & set(c.get("geographic_affinities", []))] or catalog
        if not pool or not active:
            return False, "No disasters or nations."
        return self.trigger_catastrophe(random.choice(pool)["id"])

    def _apply_catastrophe(self, cat: Dict[str, Any], target_realm: Dict[str, Any], extra_damage: Dict[str, int], damage_mult: float, is_compound: bool = False, source_cat_name: str = ""):
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == target_realm["id"]), target_realm)

        res_keys = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk", "military": "military_power"}
        metric_keys = {"vitality": "public_vitality", "standing": "diplomatic_standing", "stability": "civil_stability"}

        effects = dict(cat.get("effects", {}))
        for k, v in extra_damage.items():
            effects[k] = effects.get(k, 0) + v

        impact_summary = []
        for k, delta in effects.items():
            final_delta = int(delta * damage_mult)
            if k in res_keys:
                rk = res_keys[k]
                realm[rk] = max(0, realm.get(rk, 0) + final_delta)
                impact_summary.append(f"{final_delta} {rk.replace('_', ' ').title()}")
            elif k in metric_keys:
                mk = metric_keys[k]
                realm[mk] = max(0, min(100, realm.get(mk, 0) + final_delta))
                impact_summary.append(f"{final_delta} {mk.replace('_', ' ').title()}")

        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)

        geo = realm.get("geography", {})
        world_pos = geo.get("world_pos", [0, 0, 0])
        region_name = geo.get("region_name", "National Frontier")

        meta = self.db.get_state("meta", {})
        meta["latest_catastrophe"] = {
            "id": cat["id"],
            "name": cat["name"],
            "realm_id": realm["id"],
            "realm_name": realm["name"],
            "epicenter": world_pos,
            "is_compound": is_compound,
            "timestamp": time.time()
        }
        self.db.set_state("meta", meta)

        headline_prefix = "CASCADING COMPOUND CRISIS: " if is_compound else "PLANETARY CRISIS: "
        headline = f"{headline_prefix}{cat['headline']}"
        detail_intro = f"Secondary shockwave from {source_cat_name}! " if is_compound else ""
        detail = f"{detail_intro}{cat['narrative']} Epicenter: {realm['name']} ({region_name}). Impact: {', '.join(impact_summary)}."

        self.add_news("crisis", headline, detail)
        self.trigger_audio_cue("siren", f"{realm['name']}: {cat['name']}")

    def trigger_catastrophe(self, catastrophe_id: str, target_realm_id: Optional[str] = None) -> Tuple[bool, str]:
        """Directly triggers a catastrophe for testing or facilitator override."""
        config = load_scenario_config()
        catalog = config.get("catastrophes_catalog", [])
        cat = next((c for c in catalog if c["id"] == catastrophe_id), None)
        if not cat:
            return False, f"Catastrophe '{catastrophe_id}' not found in catalog."

        realms = self.db.get_state("realms", [])
        active = [r for r in realms if r.get("active", True)] or realms
        if target_realm_id:
            target = next((r for r in realms if r["id"] == target_realm_id), None)
            if not target:
                return False, f"Realm '{target_realm_id}' not found."
        else:
            affinities = cat.get("geographic_affinities", [])
            eligible = [r for r in active if r.get("geography", {}).get("terrain") in affinities or "all" in affinities]
            target = random.choice(eligible or active) if active else None

        if not target:
            return False, "No realms available to target."

        damage_mult = 1.0
        multipliers = cat.get("resource_multipliers", {})
        if "quarantined_mitigation" in multipliers and target.get("is_quarantined", False):
            damage_mult *= (1.0 - multipliers["quarantined_mitigation"].get("damage_reduction", 0.5))
        if "cores_efficiency_mitigation" in multipliers and target.get("tech_efficiency_unlocked", False):
            damage_mult *= (1.0 - multipliers["cores_efficiency_mitigation"].get("damage_reduction", 0.3))

        self._apply_catastrophe(cat, target, {}, damage_mult)
        return True, f"Triggered catastrophe: {cat['name']} targeting {target['name']}"

    # -------------------------------------------------------------------------
    # Dynamic Event Target Query Engine
    # -------------------------------------------------------------------------
    def _resolve_target_realms(self, realms: List[Dict[str, Any]], target_query: str) -> List[Dict[str, Any]]:
        """
        Parses dynamic, non-hardcoded queries such as:
          - 'highest 1 by alchemical_grain'
          - 'lowest 3 by public_vitality'
          - 'top 2 by aether_cores'
          - 'bottom 2 by civil_stability'
          - 'highest 1 by total_wealth'
          - 'all'
          - 'random 2'
        """
        if not realms:
            return []

        query = str(target_query).strip().lower()
        if query in ("all", "everyone", "continent"):
            return realms

        # Random N
        if query.startswith("random"):
            parts = query.split()
            count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            return random.sample(realms, min(count, len(realms)))

        # Parse: [highest|top|lowest|bottom] [N] by [stat]
        direction = "highest"
        count = 1
        stat_key = "alchemical_grain"

        # Field alias dictionary
        alias_map = {
            "food": "alchemical_grain", "grain": "alchemical_grain", "alchemical_grain": "alchemical_grain",
            "cores": "aether_cores", "core": "aether_cores", "tech": "aether_cores", "energy": "aether_cores", "aether_cores": "aether_cores",
            "silk": "echo_silk", "luxury": "echo_silk", "echo_silk": "echo_silk",
            "vitality": "public_vitality", "population": "public_vitality", "health": "public_vitality", "public_vitality": "public_vitality",
            "standing": "diplomatic_standing", "prestige": "diplomatic_standing", "diplomatic_standing": "diplomatic_standing",
            "stability": "civil_stability", "order": "civil_stability", "civil_stability": "civil_stability",
            "wealth": "total_wealth", "total_wealth": "total_wealth"
        }

        tokens = query.split()
        if tokens:
            if tokens[0] in ("lowest", "bottom", "least", "poorest"):
                direction = "lowest"
            elif tokens[0] in ("highest", "top", "most", "wealthiest"):
                direction = "highest"

            for token in tokens[1:]:
                if token.isdigit():
                    count = int(token)
                    break

            for token in tokens:
                clean_token = token.replace("by", "").strip()
                if clean_token in alias_map:
                    stat_key = alias_map[clean_token]
                    break

        # Sort realms according to parsed query
        is_reverse = (direction == "highest")
        sorted_realms = sorted(realms, key=lambda r: r.get(stat_key, 0), reverse=is_reverse)
        return sorted_realms[:max(1, count)]

    def trigger_catalog_event(self, event_id: str) -> Tuple[bool, str]:
        events = self.get_catalog_events()
        event = next((e for e in events if e["id"] == event_id), None)
        if not event:
            return False, f"Event '{event_id}' not found in catalog."

        meta = self.db.get_state("meta", {})
        triggered = meta.get("triggered_events", [])
        if event_id not in triggered:
            triggered.append(event_id)
            meta["triggered_events"] = triggered
            self.db.set_state("meta", meta)

        realms = self.db.get_state("realms", [])
        target_query = event.get("target") or event.get("target_type") or "all"
        target_realms = self._resolve_target_realms(realms, target_query)

        effects = event.get("effects", {})
        res_keys = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk"}
        metric_keys = {"vitality": "public_vitality", "standing": "diplomatic_standing", "stability": "civil_stability"}

        for r in target_realms:
            for k, delta in effects.items():
                if k in res_keys:
                    rk = res_keys[k]
                    r[rk] = max(0, r.get(rk, 0) + delta)
                elif k in metric_keys:
                    mk = metric_keys[k]
                    r[mk] = max(0, min(100, r.get(mk, 0) + delta))

        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)

        target_names = ", ".join(r["name"] for r in target_realms)
        dispatch_narrative = f"{event['narrative']} (Impacted Delegations: {target_names})"
        self.add_news("crisis", event["headline"], dispatch_narrative)
        self.trigger_audio_cue("alert", event["headline"])
        return True, f"Triggered: {event['headline']}"

    # -------------------------------------------------------------------------
    # Sovereign Domestic Governance Levers (Direct Participant Agency)
    # -------------------------------------------------------------------------
    def execute_sovereign_action(self, realm_id: str, action_type: str) -> Tuple[bool, str]:
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, "Realm not found."

        meta = self.db.get_state("meta", {})
        if meta.get("phase") != "working":
            return False, "Domestic policies can only be enacted during Working Sessions."

        if action_type == "relief":
            # Emergency Grain Rationing: -15 Grain -> +15 Vitality
            if realm.get("alchemical_grain", 0) < 15:
                return False, "Insufficient Alchemical Grain (15 required)."
            realm["alchemical_grain"] -= 15
            realm["public_vitality"] = min(100, realm.get("public_vitality", 0) + 15)
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            self.add_news(
                "economy",
                f"CIVIC RELIEF DISPATCH: {realm['name'].upper()}",
                f"{realm['name']} released 15 Alchemical Grain to feed domestic populations (+15 Vitality)."
            )
            self.trigger_audio_cue("chime", f"{realm['name']}: Grain Rationing Enacted")
            return True, "Emergency grain distributed. Public vitality improved (+15 Vitality)."

        elif action_type == "forge":
            # Stoke Arcane Forges: -10 Grain, -10 Silk -> +15 Cores
            if realm.get("alchemical_grain", 0) < 10 or realm.get("echo_silk", 0) < 10:
                return False, "Requires 10 Grain and 10 Silk to stoke the forges."
            realm["alchemical_grain"] -= 10
            realm["echo_silk"] -= 10
            realm["aether_cores"] = realm.get("aether_cores", 0) + 15
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            self.add_news(
                "economy",
                f"INDUSTRIAL SURGE IN {realm['name'].upper()}",
                f"{realm['name']} mobilized heavy industrial forges (+15 Aether Cores)."
            )
            self.trigger_audio_cue("chime", f"{realm['name']}: Forges Activated")
            return True, "Industrial fabrication active (+15 Aether Cores)."

        elif action_type == "gala":
            # Host Grand Gala: -15 Silk -> +10 Standing, +10 Stability
            if realm.get("echo_silk", 0) < 15:
                return False, "Requires 15 Echo Silk to fund the grand gala."
            realm["echo_silk"] -= 15
            realm["diplomatic_standing"] = min(100, realm.get("diplomatic_standing", 0) + 10)
            realm["civil_stability"] = min(100, realm.get("civil_stability", 0) + 10)
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            self.add_news(
                "diplomacy",
                f"GRAND CULTURAL GALA: {realm['name'].upper()}",
                f"{realm['name']} celebrated international prestige (+10 Standing, +10 Stability)."
            )
            self.trigger_audio_cue("chime", f"{realm['name']}: Grand Gala Hosted")
            return True, "Grand Gala hosted successfully (+10 Standing, +10 Stability)."

        elif action_type == "security":
            # Mobilize Civil Guard: -10 Cores -> +15 Stability
            if realm.get("aether_cores", 0) < 10:
                return False, "Requires 10 Aether Cores to power security networks."
            realm["aether_cores"] -= 10
            realm["civil_stability"] = min(100, realm.get("civil_stability", 0) + 15)
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            self.add_news(
                "order",
                f"SECURITY MOBILIZATION: {realm['name'].upper()}",
                f"{realm['name']} deployed security wardens to stabilize domestic districts (+15 Stability)."
            )
            self.trigger_audio_cue("chime", f"{realm['name']}: Civil Guard Mobilized")
            return True, "Civil order restored (+15 Stability)."

        elif action_type == "muster":
            # Muster Sovereign Regiments: -10 Grain, -10 Cores -> +15 Military Power
            if realm.get("alchemical_grain", 0) < 10 or realm.get("aether_cores", 0) < 10:
                return False, "Requires 10 Grain and 10 Cores to muster sovereign regiments."
            realm["alchemical_grain"] -= 10
            realm["aether_cores"] -= 10
            realm["military_power"] = realm.get("military_power", 0) + 15
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            self.add_news(
                "security",
                f"MILITARY MOBILIZATION: {realm['name'].upper()}",
                f"{realm['name']} levied knightly battalions and fortified territorial garrisons (+15 Military Power)."
            )
            self.trigger_audio_cue("chime", f"{realm['name']}: Regiments Mustered")
            return True, "Sovereign regiments mustered (+15 Military Power)."

        return False, "Unknown domestic action."

    # -------------------------------------------------------------------------
    # Delegation Authentication & Admin Timer Controls
    # -------------------------------------------------------------------------
    def verify_realm_pin(self, realm_id: str, pin: str) -> bool:
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False
        expected = str(realm.get("pin", "1001")).strip()
        return str(pin).strip() == expected

    def admin_set_realm_pin(self, realm_id: str, new_pin: str) -> Tuple[bool, str]:
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, "Realm not found."
        new_pin = str(new_pin).strip()
        if not new_pin.isdigit() or not 3 <= len(new_pin) <= 8:
            return False, "A passcode is 3 to 8 digits."
        if any(r["id"] != realm_id and str(r.get("pin")) == new_pin for r in realms):
            return False, "Another nation already uses that passcode."
        realm["pin"] = str(new_pin).strip()
        self.db.set_state("realms", realms)
        return True, f"PIN updated for {realm['name']}."

    def admin_set_timer(self, seconds: int):
        meta = self.db.get_state("meta", {})
        secs = max(0, int(seconds))
        meta["turn_timer_remaining"] = secs
        meta["turn_timer_total"] = max(meta.get("turn_timer_total", 300), secs)
        if meta.get("is_timer_running", False):
            meta["turn_timer_end"] = time.time() + secs
        else:
            meta["turn_timer_end"] = None
        self.db.set_state("meta", meta)

    def admin_adjust_timer(self, delta_seconds: int):
        meta = self.db.get_state("meta", {})
        cur = meta.get("turn_timer_remaining", 0)
        new_val = max(0, cur + delta_seconds)
        meta["turn_timer_remaining"] = new_val
        if meta.get("is_timer_running", False):
            meta["turn_timer_end"] = time.time() + new_val
        self.db.set_state("meta", meta)

    def admin_control_timer(self, action: str, total_seconds: Optional[int] = None):
        meta = self.db.get_state("meta", {})
        now = time.time()

        if action == "start":
            meta["is_timer_running"] = True
            rem = meta.get("turn_timer_remaining", 300)
            meta["turn_timer_end"] = now + rem
        elif action == "pause":
            if meta.get("is_timer_running", False):
                end_time = meta.get("turn_timer_end", now)
                meta["turn_timer_remaining"] = max(0, int(end_time - now))
            meta["is_timer_running"] = False
            meta["turn_timer_end"] = None
        elif action == "reset":
            secs = total_seconds if total_seconds is not None else meta.get("turn_timer_total", 300)
            meta["turn_timer_total"] = secs
            meta["turn_timer_remaining"] = secs
            meta["is_timer_running"] = False
            meta["turn_timer_end"] = None

        self.db.set_state("meta", meta)

    def admin_control_discussion_timer(self, action: str, total_seconds: Optional[int] = None):
        meta = self.db.get_state("meta", {})
        now = time.time()
        if action == "start":
            meta["is_discussion_timer_running"] = True
            rem = meta.get("discussion_timer_remaining", 300)
            meta["discussion_timer_end"] = now + rem
        elif action == "pause":
            if meta.get("is_discussion_timer_running", False):
                end_time = meta.get("discussion_timer_end", now)
                meta["discussion_timer_remaining"] = max(0, int(end_time - now))
            meta["is_discussion_timer_running"] = False
            meta["discussion_timer_end"] = None
        elif action == "reset":
            secs = total_seconds if total_seconds is not None else 300
            meta["discussion_timer_total"] = secs
            meta["discussion_timer_remaining"] = secs
            meta["is_discussion_timer_running"] = False
            meta["discussion_timer_end"] = None
        self.db.set_state("meta", meta)

    # -------------------------------------------------------------------------
    # Socioeconomic Calculations (End of Turn)
    # -------------------------------------------------------------------------
    def process_end_of_turn(self) -> Dict[str, Any]:
        meta = self.db.get_state("meta", {})
        realms = self.db.get_state("realms", [])
        current_turn = meta.get("current_turn", 1)

        config = load_scenario_config()
        settings = self.settings()
        famine = settings.get("famine_storyline", False)

        active_realms = [r for r in realms if r.get("active", True)]
        self._consume_grain(active_realms, settings)


        # Round 2 rule (famine scenario): Military < 50 at end of Round 2 incurs -10 Stability
        if current_turn == 2 and famine:
            for r in active_realms:
                if r.get("military_power", 0) < 50:
                    r["civil_stability"] = max(0, r["civil_stability"] - 10)
                    self.add_news(
                        "crisis",
                        f"SECURITY DEFICIT: {r['name'].upper()}",
                        f"Military power below 50 during continental security crisis (-10 Civil Stability)!"
                    )

        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)

        new_turn = current_turn + 1
        meta["current_turn"] = new_turn
        meta["phase"] = "working"
        meta["round_type"] = "grand" if new_turn >= 3 else "quick"
        work_secs = settings.get("working_session_seconds", 1200)
        meta["turn_timer_remaining"] = work_secs
        meta["turn_timer_total"] = work_secs
        meta["is_timer_running"] = False
        meta["turn_timer_end"] = None
        meta["plenary_docket"] = []
        meta["current_motion_index"] = 0
        meta["catastrophe_checked_minutes"] = []
        meta["latest_catastrophe"] = None

        if new_turn == 2 and famine:
            self.trigger_audio_cue("alert", "Round 2: Security Crisis")
            self.add_news(
                "crisis",
                "BREAKING NEWS — BORDER INCIDENT",
                "A serious military incident has occurred along the continental borderlands. It is unclear who provoked it. The event has ignited widespread fears that economic stagnation could transform into armed conflict. Citizens demand protection. (Round 2 Rule: Any nation finishing with Military < 50 suffers -10 Stability. All Grain trades lose 5 Grain in transit due to route disruptions.)"
            )
        elif new_turn == 3 and famine:
            # Round 3 immediate effect: all active realms receive -15 Grain
            for r in active_realms:
                r["alchemical_grain"] = max(0, r.get("alchemical_grain", 0) - 15)
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)

            self.trigger_audio_cue("siren", "Round 3: The Great Famine")
            self.add_news(
                "crisis",
                "EMERGENCY BROADCAST — THE GREAT FAMINE",
                "The agricultural crisis is significantly worse than early projections indicated. A second crop failure has devastated the continent. All realms immediately lose 15 Grain! Standard round-end consumption of -20 Grain awaits. The Spire Council has submitted Continental Emergency Food Acts to the Grand Plenary docket."
            )

            # Inject mandatory proposals into Plenary docket
            N = max(1, len(active_realms))
            quota_b = max(20, (N - 1) * 10)
            proposals = self.db.get_state("proposals", [])
            act_a = {
                "id": f"food_act_a_{uuid.uuid4().hex[:6]}",
                "proposer_id": "spire_council",
                "proposer_name": "Neutral Spire Facilitator",
                "title": "Continental Food Act: Emergency Redistribution (A)",
                "description": "Every nation holding more than 50 Grain before final consumption transfers the surplus to nations below 20 Grain.",
                "effect_type": "emergency_food_a",
                "target_seconder_id": None,
                "target_seconder_name": None,
                "support_list": ["facilitator", "spire_council"],
                "supporters": [{"id": "facilitator", "name": "Facilitator Mandate"}],
                "is_qualified": True,
                "status": "draft",
                "created_turn": 3,
                "created_at": time.time(),
                "time_str": "Turn 3 (T+00:00)",
                "votes": {},
                "tallies": {"support_weight": 0, "oppose_weight": 0, "abstain_weight": 0, "total_cast": 0}
            }
            act_b = {
                "id": f"food_act_b_{uuid.uuid4().hex[:6]}",
                "proposer_id": "spire_council",
                "proposer_name": "Neutral Spire Facilitator",
                "title": "Continental Food Act: Industrial Agriculture (B)",
                "description": f"Each active nation contributes 10 Cores. If at least {quota_b} Cores are collected in total, every nation receives +15 Grain.",
                "effect_type": "emergency_food_b",
                "target_seconder_id": None,
                "target_seconder_name": None,
                "support_list": ["facilitator", "spire_council"],
                "supporters": [{"id": "facilitator", "name": "Facilitator Mandate"}],
                "is_qualified": True,
                "status": "draft",
                "created_turn": 3,
                "created_at": time.time(),
                "time_str": "Turn 3 (T+00:00)",
                "votes": {},
                "tallies": {"support_weight": 0, "oppose_weight": 0, "abstain_weight": 0, "total_cast": 0}
            }
            proposals.insert(0, act_b)
            proposals.insert(0, act_a)
            self.db.set_state("proposals", proposals)
        else:
            self.trigger_audio_cue("turn", f"Turn {new_turn} Commenced")

        self.db.set_state("meta", meta)

        self.add_news(
            "turn",
            f"OPERATIONAL TURN {new_turn} BEGINS",
            f"Background socioeconomic cycles processed for Turn {current_turn}. Continental reserves and stability updated."
        )

        return {
            "previous_turn": current_turn,
            "new_turn": new_turn
        }

    def _consume_grain(self, active_realms: List[Dict[str, Any]], settings: Dict[str, Any]):
        """End of a turn: every nation eats; empty silos mean famine."""
        cfg = load_scenario_config().get("simulation_settings", {})
        base = settings.get("grain_consumption", 20)
        efficient = round(base * 0.75)
        starv_vit = cfg.get("starvation_vitality_loss", 25)
        starv_stab = cfg.get("starvation_stability_loss", 20)
        for r in active_realms:
            r["alchemical_grain"] = max(0, r.get("alchemical_grain", 0) - (efficient if r.get("tech_efficiency_unlocked") else base))
            if r["alchemical_grain"] <= 0:
                r["is_starving"] = True
                r["public_vitality"] = max(0, r["public_vitality"] - starv_vit)
                r["civil_stability"] = max(0, r["civil_stability"] - starv_stab)
                self.add_news("crisis", f"FAMINE EMERGENCY IN {r['name'].upper()}",
                              f"Silos ran dry this cycle. Populations are starving (-{starv_vit} Vitality, -{starv_stab} Stability)!")
            else:
                r["is_starving"] = False

    def add_news(self, news_type: str, headline: str, detail: str):
        news = self.db.get_state("news_feed", [])
        item = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "time_str": self._format_now(),
            "type": news_type,
            "headline": headline,
            "detail": detail
        }
        news.insert(0, item)
        self.db.set_state("news_feed", news[:100])
        # Full history for the results report (not sent to phones, so polling stays light).
        archive = self.db.get_state("news_archive", [])
        archive.append(dict(item, turn=(self.db.get_state("meta", {}) or {}).get("current_turn", 1)))
        self.db.set_state("news_archive", archive[-1500:])

    def trigger_audio_cue(self, cue_type: str, message: str = ""):
        meta = self.db.get_state("meta", {})
        cue = meta.get("audio_cue", {"seq": 0, "type": "none", "message": ""})
        cue["seq"] = cue.get("seq", 0) + 1
        cue["type"] = cue_type
        cue["message"] = message
        meta["audio_cue"] = cue
        self.db.set_state("meta", meta)

    # -------------------------------------------------------------------------
    # Peer-to-Peer Trading
    # -------------------------------------------------------------------------
    def create_trade(self, sender_id: str, receiver_id: str,
                     offer_res: str, offer_amt: int,
                     request_res: str, request_amt: int,
                     note: str = "") -> Tuple[bool, str]:
        if sender_id == receiver_id:
            return False, "Cannot trade with your own delegation."

        realms = self.db.get_state("realms", [])
        sender = next((r for r in realms if r["id"] == sender_id), None)
        receiver = next((r for r in realms if r["id"] == receiver_id), None)
        if not sender or not receiver:
            return False, "Invalid sender or receiver delegation."
        if not sender.get("active", True) or not receiver.get("active", True):
            return False, "That nation is not taking part in this summit."
        try:
            offer_amt, request_amt = int(offer_amt), int(request_amt)
        except (TypeError, ValueError):
            return False, "Amounts must be whole numbers."
        if offer_amt < 0 or request_amt < 0 or offer_amt + request_amt == 0 or max(offer_amt, request_amt) > 500:
            return False, "Amounts must be between 0 and 500, and the trade cannot be empty."

        res_key_map = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk", "military": "military_power"}
        sender_res_key = res_key_map.get(offer_res)
        if not sender_res_key or sender.get(sender_res_key, 0) < offer_amt:
            return False, f"Insufficient {offer_res} in national reserves."

        trade_id = str(uuid.uuid4())[:8]
        clean_note = (note or "").strip()[:200]
        new_trade = {
            "id": trade_id,
            "sender_id": sender_id,
            "sender_name": sender["name"],
            "receiver_id": receiver_id,
            "receiver_name": receiver["name"],
            "offer_resource": offer_res,
            "offer_amount": offer_amt,
            "request_resource": request_res,
            "request_amount": request_amt,
            "note": clean_note,
            "status": "pending",
            "created_at": time.time(),
            "time_str": self._format_now()
        }

        trades = self.db.get_state("trades", [])
        trades.insert(0, new_trade)
        self.db.set_state("trades", trades)

        note_txt = f" Dispatch: \"{clean_note}\"" if clean_note else ""
        self.add_news(
            "trade",
            f"TREATY PROPOSED: {sender['name'].upper()} -> {receiver['name'].upper()}",
            f"Diplomatic courier dispatched offering {offer_amt} {offer_res} for {request_amt} {request_res}.{note_txt}"
        )
        return True, "Trade proposal transmitted."

    def respond_trade(self, trade_id: str, action: str, responder_id: str) -> Tuple[bool, str]:
        trades = self.db.get_state("trades", [])
        trade = next((t for t in trades if t["id"] == trade_id), None)
        if not trade:
            return False, "Trade not found."

        if trade["status"] != "pending":
            return False, f"Trade is already {trade['status']}."

        realms = self.db.get_state("realms", [])
        sender = next((r for r in realms if r["id"] == trade["sender_id"]), None)
        receiver = next((r for r in realms if r["id"] == trade["receiver_id"]), None)

        if action == "cancel":
            if responder_id != trade["sender_id"]:
                return False, "Only the initiating realm can rescind an offer."
            trade["status"] = "cancelled"
            self.db.set_state("trades", trades)
            return True, "Trade offer rescinded."

        if action == "decline":
            if responder_id != trade["receiver_id"]:
                return False, "Only the counterparty can decline this offer."
            trade["status"] = "declined"
            self.db.set_state("trades", trades)
            return True, "Trade offer declined."

        if action == "accept":
            if responder_id != trade["receiver_id"]:
                return False, "Only the receiving delegation can ratify this treaty."

            res_key_map = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk", "military": "military_power"}
            sender_res_key = res_key_map.get(trade["offer_resource"])
            receiver_res_key = res_key_map.get(trade["request_resource"])

            if sender.get(sender_res_key, 0) < trade["offer_amount"]:
                trade["status"] = "cancelled"
                self.db.set_state("trades", trades)
                return False, f"Sender lacks sufficient {trade['offer_resource']}. Treaty invalidated."

            if receiver.get(receiver_res_key, 0) < trade["request_amount"]:
                return False, f"You lack sufficient {trade['request_resource']} to honor this exchange."

            meta = self.db.get_state("meta", {})
            current_turn = meta.get("current_turn", 1)
            is_round_2 = (current_turn == 2 or meta.get("active_crisis_round") == 2) and self.settings()["famine_storyline"]

            actual_offer_delivered = trade["offer_amount"]
            transit_offer_loss = 0
            if is_round_2 and trade["offer_resource"] == "grain":
                transit_offer_loss = min(5, trade["offer_amount"])
                actual_offer_delivered = max(0, trade["offer_amount"] - 5)

            actual_request_delivered = trade["request_amount"]
            transit_request_loss = 0
            if is_round_2 and trade["request_resource"] == "grain":
                transit_request_loss = min(5, trade["request_amount"])
                actual_request_delivered = max(0, trade["request_amount"] - 5)

            sender[sender_res_key] -= trade["offer_amount"]
            receiver[sender_res_key] += actual_offer_delivered
            receiver[receiver_res_key] -= trade["request_amount"]
            sender[receiver_res_key] += actual_request_delivered

            # Track bilateral trade partner network
            partners = self.db.get_state("trade_partners", {})
            s_partners = set(partners.get(sender["id"], []))
            r_partners = set(partners.get(receiver["id"], []))
            s_partners.add(receiver["id"])
            r_partners.add(sender["id"])
            partners[sender["id"]] = list(s_partners)
            partners[receiver["id"]] = list(r_partners)
            self.db.set_state("trade_partners", partners)

            # Track military trade transactions (e.g. Sylvan purchasing from Aethelgard)
            if trade["offer_resource"] == "military" or trade["request_resource"] == "military":
                mil_trades = self.db.get_state("military_trades", [])
                if trade["offer_resource"] == "military":
                    mil_trades.append({"buyer": receiver["id"], "seller": sender["id"], "amount": trade["offer_amount"]})
                if trade["request_resource"] == "military":
                    mil_trades.append({"buyer": sender["id"], "seller": receiver["id"], "amount": trade["request_amount"]})
                self.db.set_state("military_trades", mil_trades)

            trade["status"] = "accepted"
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            self.db.set_state("trades", trades)

            labels_map = {"grain": "Alchemical Grain", "cores": "Aether Cores", "silk": "Echo Silk", "military": "Military Regiments"}
            off_label = labels_map.get(trade['offer_resource'], trade['offer_resource'])
            req_label = labels_map.get(trade['request_resource'], trade['request_resource'])

            loss_notice = ""
            if transit_offer_loss > 0 or transit_request_loss > 0:
                loss_notice = " (Round 2 Border Crisis: 5 Grain lost in transit)"

            self.add_news(
                "trade",
                f"BILATERAL TREATY RATIFIED: {sender['name'].upper()} & {receiver['name'].upper()}",
                f"{sender['name']} delivered {actual_offer_delivered} {off_label} to {receiver['name']} in exchange for {actual_request_delivered} {req_label}.{loss_notice}"
            )
            self.trigger_audio_cue("trade", f"Treaty Ratified: {sender['name']} & {receiver['name']}")
            return True, f"Treaty ratified! Resources transferred.{loss_notice}"

        return False, "Invalid action."

    # -------------------------------------------------------------------------
    # Motion Drafting & Endorsements
    # -------------------------------------------------------------------------
    def draft_proposal(self, proposer_id: str, title: str, description: str,
                       effect_type: str = "custom",
                       target_seconder_id: Optional[str] = None,
                       target_realm_id: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        realms = self.db.get_state("realms", [])
        proposer = next((r for r in realms if r["id"] == proposer_id), None)
        if not proposer:
            return False, "Proposer realm not found.", None

        # Players table motions from the templates in scenario_config.json (resolution_types).
        template = next((t for t in load_scenario_config().get("resolution_types", [])
                         if t["id"] == effect_type and t.get("player_selectable", True)), None)
        if not template:
            return False, "Choose one of the motion templates.", None
        title = (title or "").strip()[:100]
        description = (description or "").strip()[:1000]
        if not title or not description:
            return False, "Give the motion a title and terms.", None

        # Each nation may table only a few motions per turn (questions to the game masters included).
        meta = self.db.get_state("meta", {})
        limit = int(self.settings().get("motions_per_turn", 2))
        tabled = sum(1 for p in self.db.get_state("proposals", [])
                     if p.get("proposer_id") == proposer_id and p.get("created_turn") == meta.get("current_turn", 1))
        if tabled >= limit:
            return False, f"Your nation has already tabled {tabled} motions this turn (the limit is {limit}).", None

        target_realm = None
        if template.get("needs_target"):
            target_realm = next((r for r in realms if r["id"] == target_realm_id and r.get("active", True)), None)
            if not target_realm:
                return False, f"Choose the nation for this motion ({template.get('target_label', 'target nation')}).", None

        target_name = None
        if target_seconder_id:
            seconder_realm = next((r for r in realms if r["id"] == target_seconder_id and r.get("active", True)), None)
            if not seconder_realm:
                return False, "The nation you asked to co-sponsor is not taking part.", None
            target_name = seconder_realm["name"]

        prop_id = str(uuid.uuid4())[:8]
        new_prop = {
            "id": prop_id,
            "proposer_id": proposer_id,
            "proposer_name": proposer["name"],
            "title": title,
            "description": description,
            "effect_type": effect_type,
            "target_seconder_id": target_seconder_id or None,
            "target_seconder_name": target_name,
            "target_realm_id": target_realm["id"] if target_realm else None,
            "target_realm_name": target_realm["name"] if target_realm else None,
            "support_list": [proposer_id],
            "supporters": [{"id": proposer_id, "name": proposer["name"]}],
            "is_qualified": False,
            "status": "draft",
            "created_turn": meta.get("current_turn", 1),
            "created_at": time.time(),
            "time_str": self._format_now(),
            "votes": {},
            "tallies": {
                "support_weight": 0,
                "oppose_weight": 0,
                "abstain_weight": 0,
                "total_cast": 0
            }
        }

        proposals = self.db.get_state("proposals", [])
        proposals.insert(0, new_prop)
        self.db.set_state("proposals", proposals)

        # A motion addressed to one nation stays private until it qualifies; open motions are announced.
        if not target_name:
            self.add_news(
                "assembly",
                f"MOTION TABLED BY {proposer['name'].upper()}",
                f"'{title}' is on the floor. It needs a co-sponsoring nation to reach the Assembly vote."
            )
        return True, "Motion filed. Awaiting a co-sponsor.", prop_id

    def support_proposal(self, prop_id: str, supporter_id: str) -> Tuple[bool, str]:
        proposals = self.db.get_state("proposals", [])
        prop = next((p for p in proposals if p["id"] == prop_id), None)
        if not prop:
            return False, "Proposal not found."

        if prop["status"] not in ("draft", "qualified"):
            return False, f"Motion is already {prop['status']}."

        realms = self.db.get_state("realms", [])
        supporter = next((r for r in realms if r["id"] == supporter_id), None)
        if not supporter:
            return False, "Supporter realm not found."

        if prop.get("target_seconder_id") and supporter_id != prop.get("target_seconder_id"):
            return False, f"This motion specifically requests endorsement from {prop.get('target_seconder_name')}."

        support_list = prop.get("support_list", [])
        if supporter_id in support_list:
            return False, "Your delegation has already endorsed this motion."

        support_list.append(supporter_id)
        prop["support_list"] = support_list
        if "supporters" not in prop:
            prop["supporters"] = []
        prop["supporters"].append({"id": supporter_id, "name": supporter["name"]})

        if len(support_list) >= 2:
            prop["is_qualified"] = True
            prop["status"] = "qualified"
            prop["seconder_id"] = supporter_id
            prop["seconder_name"] = supporter["name"]
            self.db.set_state("proposals", proposals)
            # Co-sponsors stay anonymous: only the nation that tabled the motion is named.
            self.add_news(
                "assembly",
                f"MOTION ON THE BALLOT: '{prop['title']}'",
                f"Tabled by {prop.get('proposer_name')}, the motion found a co-sponsor and goes to the Assembly vote."
            )
            self.trigger_audio_cue("chime", f"Motion Qualified: {prop['title']}")
            return True, f"Endorsement recorded! '{prop['title']}' has met the 2-country threshold and qualified for the Plenary Ballot."
        else:
            self.db.set_state("proposals", proposals)
            return True, f"Endorsement recorded ({len(support_list)}/2 required)."

    # -------------------------------------------------------------------------
    # Between-Round Plenary Voting Structure
    # -------------------------------------------------------------------------
    def answer_question(self, prop_id: str, answer: str) -> Tuple[bool, str]:
        """The facilitators answer a question the Assembly passed; everyone sees the answer."""
        answer = (answer or "").strip()[:1000]
        if not answer:
            return False, "Write an answer first."
        proposals = self.db.get_state("proposals", [])
        prop = next((p for p in proposals if p["id"] == prop_id and p.get("effect_type") == "gm_question"), None)
        if not prop:
            return False, "Question not found."
        if prop.get("status") != "passed":
            return False, "Only questions the Assembly has passed are answered."
        prop.update(answer=answer, answered_at=time.time())
        self.db.set_state("proposals", proposals)
        self.add_news("diplomacy", "THE GAME MASTERS ANSWER",
                      f"{prop.get('proposer_name')} asked: \"{prop.get('title')}\" {prop.get('description')} — Answer: {answer}")
        self.trigger_audio_cue("chime", "The game masters answer")
        return True, "Answer published to everyone."

    def start_plenary_session(self) -> Tuple[bool, str]:
        meta = self.db.get_state("meta", {})
        proposals = self.db.get_state("proposals", [])

        # Only motions still awaiting a vote; motions already passed/rejected never return to the ballot.
        qualified = [p for p in proposals if p.get("status") in ("draft", "qualified")
                     and (len(p.get("support_list", [])) >= 2 or p.get("is_qualified"))]
        if not qualified:
            return False, "No resolutions met the threshold of support from at least two countries."

        qualified.sort(key=lambda p: len(p.get("support_list", [])), reverse=True)
        docket_ids = [p["id"] for p in qualified]

        meta["is_timer_running"] = False
        meta["turn_timer_end"] = None
        meta["plenary_docket"] = docket_ids
        meta["current_motion_index"] = 0

        settings = self.settings()
        debate_secs = settings.get("debate_session_seconds", 300)

        current_turn = meta.get("current_turn", 1)
        if current_turn < settings["max_turns"]:
            meta["phase"] = "plenary_quick"
            meta["vote_timer_end"] = time.time() + settings.get("plenary_vote_seconds", 180)
            meta["vote_timer_total"] = settings.get("plenary_vote_seconds", 180)
            self.db.set_state("meta", meta)
            self.add_news(
                "assembly",
                "BETWEEN-ROUNDS PLENARY CONVENED",
                f"{len(qualified)} motions qualified for sovereign vote. Direct roll-call voting open on all qualified resolutions."
            )
            self.trigger_audio_cue("gong", "Plenary Session Convened")
            return True, f"Between-Rounds Plenary Convened with {len(qualified)} qualified motions."
        else:
            meta["phase"] = "grand_plenary_discussion"
            meta["discussion_timer_remaining"] = debate_secs
            meta["discussion_timer_total"] = debate_secs
            meta["discussion_timer_end"] = time.time() + debate_secs
            meta["is_discussion_timer_running"] = True
            self.db.set_state("meta", meta)

            first_prop = qualified[0]
            self.add_news(
                "assembly",
                "GRAND PLENARY CONVENED: 5-MINUTE FLOOR DEBATE",
                f"Highest-ranked resolution '{first_prop['title']}' ({len(first_prop['support_list'])} sponsors) is now open for 5 minutes of discussion before voting."
            )
            self.trigger_audio_cue("gong", "Grand Plenary Debate Commenced")
            return True, f"Grand Plenary initiated. 5 minutes allocated for discussion on '{first_prop['title']}'."

    def start_grand_motion_vote(self) -> Tuple[bool, str]:
        meta = self.db.get_state("meta", {})
        if meta.get("phase") != "grand_plenary_discussion":
            return False, "Not currently in Grand Plenary discussion phase."

        meta["phase"] = "grand_plenary_voting"
        meta["is_discussion_timer_running"] = False
        meta["discussion_timer_end"] = None
        meta["vote_timer_end"] = time.time() + self.settings().get("grand_vote_seconds", 90)
        meta["vote_timer_total"] = self.settings().get("grand_vote_seconds", 90)
        self.db.set_state("meta", meta)

        proposals = self.db.get_state("proposals", [])
        docket = meta.get("plenary_docket", [])
        idx = meta.get("current_motion_index", 0)
        active_prop = next((p for p in proposals if p["id"] == docket[idx]), None)
        title = active_prop["title"] if active_prop else "Active Resolution"

        self.add_news(
            "assembly",
            f"FLOOR DISCUSSION CONCLUDED: VOTE CALLED",
            f"5 minutes of debate on '{title}' elapsed. Sovereign delegates must now cast their weighted ballots."
        )
        self.trigger_audio_cue("gong", f"Vote Called: {title}")
        return True, f"Floor debate closed. Voting active on '{title}'."

    def advance_grand_plenary_next(self) -> Tuple[bool, str]:
        meta = self.db.get_state("meta", {})
        if meta.get("phase") not in ("grand_plenary_voting", "grand_plenary_discussion"):
            return False, "Not currently in Grand Plenary."

        proposals = self.db.get_state("proposals", [])
        docket = meta.get("plenary_docket", [])
        idx = meta.get("current_motion_index", 0)
        active_prop = next((p for p in proposals if p["id"] == docket[idx]), None)

        if active_prop:
            tallies = active_prop.get("tallies", {})
            outcome = "passed" if tallies.get("support_weight", 0) > tallies.get("oppose_weight", 0) else "rejected"
            active_prop["status"] = outcome
            effect_msg = self._apply_proposal_effect(active_prop)
            self.add_news(
                "assembly",
                f"RESOLUTION {outcome.upper()}: '{active_prop['title']}'",
                f"Floor vote finalized: {tallies.get('support_weight', 0)} Support vs {tallies.get('oppose_weight', 0)} Oppose. {effect_msg}"
            )

        if idx + 1 < len(docket):
            next_idx = idx + 1
            debate_secs = self.settings().get("debate_session_seconds", 300)
            meta["vote_timer_end"] = None
            meta["current_motion_index"] = next_idx
            meta["phase"] = "grand_plenary_discussion"
            meta["discussion_timer_remaining"] = debate_secs
            meta["discussion_timer_total"] = debate_secs
            meta["discussion_timer_end"] = time.time() + debate_secs
            meta["is_discussion_timer_running"] = True
            self.db.set_state("meta", meta)
            self.db.set_state("proposals", proposals)

            next_prop = next((p for p in proposals if p["id"] == docket[next_idx]), None)
            title = next_prop["title"] if next_prop else f"Motion {next_idx + 1}"
            self.add_news(
                "assembly",
                f"GRAND PLENARY PROCEEDS: MOTION {next_idx + 1} OF {len(docket)}",
                f"'{title}' entered the floor. 5 minutes allocated for sovereign discussion."
            )
            self.trigger_audio_cue("gong", f"Next Motion: {title}")
            return True, f"Advanced to Motion {next_idx + 1}: '{title}'."
        else:
            meta["phase"] = "turn_summary"
            meta["is_discussion_timer_running"] = False
            meta["discussion_timer_end"] = None
            meta["vote_timer_end"] = None
            self.db.set_state("meta", meta)
            self.db.set_state("proposals", proposals)
            self.add_news(
                "assembly",
                "GRAND PLENARY CONCLUDED",
                "All qualified sovereign resolutions have been debated and voted on. Ready to finalize simulation results."
            )
            self.trigger_audio_cue("gong", "Grand Plenary Concluded")
            return True, "Grand Plenary concluded. Ready for final turn processing."

    def cast_plenary_vote(self, realm_id: str, prop_id: str, choice: str) -> Tuple[bool, str]:
        if choice not in ("support", "oppose", "abstain"):
            return False, "Invalid vote choice."

        proposals = self.db.get_state("proposals", [])
        prop = next((p for p in proposals if p["id"] == prop_id), None)
        if not prop:
            return False, "Proposal not found."

        meta = self.db.get_state("meta", {})
        phase = meta.get("phase", "working")
        if phase not in ("plenary_quick", "grand_plenary_voting"):
            return False, f"Plenary voting is not currently open (current phase: {phase})."

        if phase == "grand_plenary_voting":
            docket = meta.get("plenary_docket", [])
            idx = meta.get("current_motion_index", 0)
            if idx < len(docket) and docket[idx] != prop_id:
                return False, "This resolution is not currently on the plenary voting floor."

        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, "Realm not found."

        votes = prop.get("votes", {})
        if realm_id in votes:
            return False, "Your sovereign vote on this resolution has already been cast."

        weight = realm.get("assembly_votes", 1)
        votes[realm_id] = {
            "realm_name": realm["name"],
            "choice": choice,
            "weight": weight
        }
        prop["votes"] = votes

        sup, opp, abs_val = 0, 0, 0
        for v in votes.values():
            c = v.get("choice")
            w = v.get("weight", 1)
            if c == "support": sup += w
            elif c == "oppose": opp += w
            elif c == "abstain": abs_val += w

        prop["tallies"] = {
            "support_weight": sup,
            "oppose_weight": opp,
            "abstain_weight": abs_val,
            "total_cast": len(votes)
        }
        self.db.set_state("proposals", proposals)
        return True, f"Sovereign ballot ({weight} Votes) recorded: {choice.upper()}."

    def conclude_quick_plenary(self) -> Tuple[bool, str]:
        meta = self.db.get_state("meta", {})
        if meta.get("phase") != "plenary_quick":
            return False, "Not currently in quick plenary phase."

        proposals = self.db.get_state("proposals", [])
        docket = meta.get("plenary_docket", [])

        passed_count = 0
        for prop_id in docket:
            prop = next((p for p in proposals if p["id"] == prop_id), None)
            if prop:
                tallies = prop.get("tallies", {})
                outcome = "passed" if tallies.get("support_weight", 0) > tallies.get("oppose_weight", 0) else "rejected"
                prop["status"] = outcome
                if outcome == "passed":
                    passed_count += 1
                    self._apply_proposal_effect(prop)

        self.db.set_state("proposals", proposals)
        meta["phase"] = "turn_summary"
        meta["vote_timer_end"] = None
        self.db.set_state("meta", meta)

        self.add_news(
            "assembly",
            "BETWEEN-ROUNDS PLENARY CONCLUDED",
            f"All qualified motions settled ({passed_count} ratified, {len(docket) - passed_count} rejected). Ready to process end of turn."
        )
        self.trigger_audio_cue("chime", "Plenary Concluded")
        return True, f"Quick Plenary settled. {passed_count} of {len(docket)} motions passed."

    def _apply_proposal_effect(self, prop: Dict[str, Any]) -> str:
        effect_type = prop.get("effect_type", "custom")
        realms = self.db.get_state("realms", [])
        
        # Only nations at the table take part (an inactive nation keeps its numbers untouched).
        active = [r for r in realms if r.get("active", True)] or realms

        if effect_type == "tax":
            for r in active:
                if r["alchemical_grain"] > 50:
                    r["alchemical_grain"] -= 10
                elif r["alchemical_grain"] < 25:
                    r["alchemical_grain"] += 15
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            return "Emergency Tax enacted: Grain reallocated from surplus reserves to famine zones."

        elif effect_type == "aid":
            proposer = next((r for r in realms if r["id"] == prop.get("proposer_id")), None)
            if proposer:
                proposer["diplomatic_standing"] = min(100, proposer["diplomatic_standing"] + 10)
                self._recalculate_all_realms(realms)
                self.db.set_state("realms", realms)
                return f"Humanitarian Aid ratified: {proposer['name']} gained +10 Diplomatic Standing."

        elif effect_type == "embargo":
            max_wealth = max(r["total_wealth"] for r in active)
            wealthiest = next((r for r in active if r["total_wealth"] == max_wealth), None)
            if wealthiest:
                wealthiest["civil_stability"] = max(0, wealthiest["civil_stability"] - 15)
                self._recalculate_all_realms(realms)
                self.db.set_state("realms", realms)
                return f"Embargo sanctions enforced against {wealthiest['name']} (-15 Stability)."

        elif effect_type == "cordon":
            target_id = prop.get("target_realm_id") or prop.get("target_seconder_id")
            if target_id:
                target_realm = next((r for r in realms if r["id"] == target_id), None)
                if target_realm:
                    target_realm["is_quarantined"] = True
                    target_realm["civil_stability"] = min(100, target_realm["civil_stability"] + 10)
                    self._recalculate_all_realms(realms)
                    self.db.set_state("realms", realms)
                    return f"Environmental Cordon deployed around {target_realm['name']}: Borders fortified against unrest (+10 Stability)."
            for r in active:
                r["is_quarantined"] = True
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            return "Continental Environmental Cordon ratified: All frontiers militarized and quarantined against unrest."

        elif effect_type == "emergency_food_a":
            # Continental Emergency Food Act A: Redistribution
            surplus_total = 0
            active_realms = [r for r in realms if r.get("active", True)]
            for r in active_realms:
                if r.get("alchemical_grain", 0) > 50:
                    excess = r["alchemical_grain"] - 50
                    r["alchemical_grain"] = 50
                    surplus_total += excess
            starving_realms = [r for r in active_realms if r.get("alchemical_grain", 0) < 20]
            if starving_realms and surplus_total > 0:
                share = surplus_total // len(starving_realms)
                rem = surplus_total % len(starving_realms)
                for idx, sr in enumerate(starving_realms):
                    sr["alchemical_grain"] += share + (1 if idx < rem else 0)
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            return f"Continental Emergency Redistribution Act enacted: {surplus_total} surplus Grain transferred to struggling regions."

        elif effect_type == "emergency_food_b":
            # Continental Emergency Food Act B: Industrial Agriculture
            active_realms = [r for r in realms if r.get("active", True)]
            quota = max(20, (len(active_realms) - 1) * 10)
            collected = 0
            for r in active_realms:
                if r.get("aether_cores", 0) >= 10:
                    r["aether_cores"] -= 10
                    collected += 10
                else:
                    collected += r.get("aether_cores", 0)
                    r["aether_cores"] = 0
            if collected >= quota:
                for r in active_realms:
                    r["alchemical_grain"] = r.get("alchemical_grain", 0) + 15
                self._recalculate_all_realms(realms)
                self.db.set_state("realms", realms)
                return f"Emergency Industrial Agriculture Act enacted: {collected} Cores collected (Quota {quota} reached). Every state received +15 Grain!"
            else:
                self._recalculate_all_realms(realms)
                self.db.set_state("realms", realms)
                return f"Emergency Industrial Agriculture Act underfunded: Only {collected}/{quota} Cores collected. Quota not met."

        elif effect_type == "gm_question":
            return "The question goes to the game masters, who will answer it for everyone."

        elif effect_type == "custom":
            proposer = next((r for r in realms if r["id"] == prop.get("proposer_id")), None)
            if proposer:
                proposer["diplomatic_standing"] = min(100, proposer["diplomatic_standing"] + 5)
                proposer["civil_stability"] = min(100, proposer["civil_stability"] + 5)
                self._recalculate_all_realms(realms)
                self.db.set_state("realms", realms)
                return f"Sovereign Resolution enacted: {proposer['name']} elevated standing and stability (+5 Standing, +5 Stability)."

        return "Resolution ratified into sovereign law."

    def second_proposal(self, prop_id: str, seconder_id: str) -> Tuple[bool, str]:
        return self.support_proposal(prop_id, seconder_id)

    def cast_vote(self, realm_id: str, choice: str) -> Tuple[bool, str]:
        meta = self.db.get_state("meta", {})
        phase = meta.get("phase", "working")
        if phase in ("plenary_quick", "grand_plenary_voting"):
            docket = meta.get("plenary_docket", [])
            idx = meta.get("current_motion_index", 0)
            if docket and idx < len(docket):
                return self.cast_plenary_vote(realm_id, docket[idx], choice)
        return False, "No active vote floor."

    def get_catalog_events(self) -> List[Dict[str, Any]]:
        return load_events_catalog()

    def auto_draw_next_event(self) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Draws and triggers the next recommended untriggered crisis event."""
        events = self.get_catalog_events()
        meta = self.db.get_state("meta", {})
        current_turn = meta.get("current_turn", 1)
        triggered = meta.get("triggered_events", [])

        # Priority 1: Events for current turn
        for ev in events:
            if ev.get("id") not in triggered and ev.get("turn_recommended") == current_turn:
                ok, msg = self.trigger_catalog_event(ev["id"])
                return ok, msg, ev

        # Priority 2: Any remaining untriggered event
        for ev in events:
            if ev.get("id") not in triggered:
                ok, msg = self.trigger_catalog_event(ev["id"])
                return ok, msg, ev

        return False, "All catalog events have already been triggered.", None

    def admin_assembly_override(self, action: str) -> Tuple[bool, str]:
        """Provides facilitator command deck control over assembly / plenary sessions."""
        if action == "start":
            return self.start_plenary_session()
        elif action == "call_vote":
            return self.start_grand_motion_vote()
        elif action == "next":
            return self.advance_grand_plenary_next()
        elif action == "conclude_quick":
            return self.conclude_quick_plenary()
        elif action == "reset":
            meta = self.db.get_state("meta", {})
            meta["plenary_docket"] = []
            meta["current_motion_index"] = 0
            meta["phase"] = "working"
            meta["is_discussion_timer_running"] = False
            self.db.set_state("meta", meta)
            return True, "Assembly docket reset to working session."
        return False, f"Unknown assembly action: '{action}'."

    def shuffle_pins(self) -> Dict[str, str]:
        """New random 4-digit passcodes for every nation (all different)."""
        realms = self.db.get_state("realms", [])
        pins = random.sample(range(1000, 10000), len(realms))
        for r, pin in zip(realms, pins):
            r["pin"] = str(pin)
        self.db.set_state("realms", realms)
        self.clear_realm_sessions()          # everyone logs in again with the new codes
        return {r["id"]: r["pin"] for r in realms}

    def start_new_summit(self) -> Tuple[bool, str]:
        """Fresh game with the current settings, keeping the roster, delegation sizes and passcodes."""
        self.autosave(label="Before new summit", force=True)
        keep = {r["id"]: {k: r.get(k) for k in ("active", "player_count", "pin")} for r in self.db.get_state("realms", [])}
        self.reset_simulation()
        realms = self.db.get_state("realms", [])
        for r in realms:
            r.update({k: v for k, v in keep.get(r["id"], {}).items() if v is not None})
        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)
        self.clear_realm_sessions()
        s = self.settings()
        cfg = load_scenario_config()
        self.add_news("turn", "A NEW SUMMIT IS PREPARED",
                      f"Scenario: {cfg.get('scenarios', {}).get(s['scenario'], {}).get('name', s['scenario'])} · "
                      f"difficulty {s['difficulty']} · {len([r for r in realms if r.get('active', True)])} nations.")
        return True, "New summit ready. Start the clock on the command deck when everyone has joined."

    def admin_toggle_realm(self, realm_id: str, active: Optional[bool] = None) -> Tuple[bool, str]:
        """Enables or disables participation of a country."""
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, "Realm not found."

        new_val = not realm.get("active", True) if active is None else bool(active)
        if not new_val and sum(1 for r in realms if r.get("active", True) and r["id"] != realm_id) < 2:
            return False, "At least two nations must take part in the summit."
        realm["active"] = new_val
        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)
        status_str = "joins the summit" if new_val else "is no longer taking part"
        self.add_news("diplomacy", "SUMMIT ROSTER CHANGED", f"{realm['name']} {status_str}.")
        return True, f"{realm['name']} {status_str}."

    def admin_set_player_count(self, realm_id: str, count: int) -> Tuple[bool, str]:
        """Sets delegation member count and auto-scales secret missions accordingly."""
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, "Realm not found."

        new_count = max(1, int(count))
        realm["player_count"] = new_count
        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)
        active_count = len(realm.get("active_secret_missions", []))
        return True, f"{realm['name']} set to {new_count} player(s). {active_count} secret mission(s) assigned."

    def admin_set_active_realm_count(self, count: int) -> Tuple[bool, str]:
        """Explicitly sets the number of participating active countries in the summit."""
        realms = self.db.get_state("realms", [])
        if not realms:
            return False, "No realms registered."

        count = max(2, min(len(realms), int(count)))
        # Canonical MGV country order: Sylvan, Val-Khor, Solaris, Umbra, Aquila, Aethelgard
        canonical_order = ["sylvan", "val_khor", "solaria", "umbra", "aquila", "aethelgard"]
        ordered_ids = [cid for cid in canonical_order if any(r["id"] == cid for r in realms)]
        for r in realms:
            if r["id"] not in ordered_ids:
                ordered_ids.append(r["id"])

        active_target_ids = set(ordered_ids[:count])
        for r in realms:
            r["active"] = (r["id"] in active_target_ids)

        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)

        active_names = [r["name"] for r in realms if r.get("active", True)]
        self.add_news(
            "diplomacy",
            "SUMMIT ROSTER CONFIGURED",
            f"The Facilitator has configured the summit scale to {count} sovereign nations: {', '.join(active_names)}."
        )
        return True, f"Participating countries set to {count} ({', '.join(active_names)})."

    def trigger_round_crisis(self, round_num: int) -> Tuple[bool, str]:
        """Triggers official MGV 2026 round crisis announcements and mechanics."""
        meta = self.db.get_state("meta", {})
        realms = self.db.get_state("realms", [])
        active_realms = [r for r in realms if r.get("active", True)]

        meta["active_crisis_round"] = round_num
        self.db.set_state("meta", meta)

        if round_num == 1:
            self.add_news(
                "crisis",
                "BREAKING NEWS — THE FAILED HARVEST",
                "This year's harvest is the poorest in decades. Analysts do not predict immediate starvation, but warn states against rapid depletion of grain reserves. The Summit commences."
            )
            self.trigger_audio_cue("alert", "Round 1: The Failed Harvest")
            return True, "Round 1 crisis announced."

        elif round_num == 2:
            self.add_news(
                "crisis",
                "BREAKING NEWS — BORDER INCIDENT",
                "A serious military incident has occurred along continental borderlands. It is unclear who provoked it. The event has ignited widespread fears that economic stagnation could transform into armed conflict. Citizens demand protection. (Round 2 Rule: Any nation finishing with Military < 50 suffers -10 Stability. All Grain trades lose 5 Grain in transit.)"
            )
            self.trigger_audio_cue("alert", "Round 2: Border Incident")
            return True, "Round 2 Security Crisis activated."

        elif round_num == 3:
            # Immediate -15 grain
            for r in active_realms:
                r["alchemical_grain"] = max(0, r.get("alchemical_grain", 0) - 15)
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)

            # Inject Emergency Food Acts into proposals if not present
            N = max(1, len(active_realms))
            quota_b = max(20, (N - 1) * 10)
            proposals = self.db.get_state("proposals", [])
            has_food_a = any(p.get("effect_type") == "emergency_food_a" for p in proposals)
            has_food_b = any(p.get("effect_type") == "emergency_food_b" for p in proposals)
            if not has_food_a:
                proposals.append({
                    "id": f"food_act_a_{uuid.uuid4().hex[:6]}",
                    "proposer_id": "spire_council",
                    "proposer_name": "Neutral Spire Facilitator",
                    "title": "Continental Food Act: Emergency Redistribution (A)",
                    "description": "Every nation holding more than 50 Grain before final consumption transfers the surplus to nations below 20 Grain.",
                    "effect_type": "emergency_food_a",
                    "target_seconder_id": None,
                    "target_seconder_name": None,
                    "support_list": ["facilitator", "spire_council"],
                    "supporters": [{"id": "facilitator", "name": "Facilitator Mandate"}],
                    "is_qualified": True,
                    "status": "draft",
                    "created_turn": 3,
                    "created_at": time.time(),
                    "time_str": "Turn 3 (T+00:00)",
                    "votes": {},
                    "tallies": {"support_weight": 0, "oppose_weight": 0, "abstain_weight": 0, "total_cast": 0}
                })
            if not has_food_b:
                proposals.append({
                    "id": f"food_act_b_{uuid.uuid4().hex[:6]}",
                    "proposer_id": "spire_council",
                    "proposer_name": "Neutral Spire Facilitator",
                    "title": "Continental Food Act: Industrial Agriculture (B)",
                    "description": f"Each active nation contributes 10 Cores. If at least {quota_b} Cores are collected in total, every nation receives +15 Grain.",
                    "effect_type": "emergency_food_b",
                    "target_seconder_id": None,
                    "target_seconder_name": None,
                    "support_list": ["facilitator", "spire_council"],
                    "supporters": [{"id": "facilitator", "name": "Facilitator Mandate"}],
                    "is_qualified": True,
                    "status": "draft",
                    "created_turn": 3,
                    "created_at": time.time(),
                    "time_str": "Turn 3 (T+00:00)",
                    "votes": {},
                    "tallies": {"support_weight": 0, "oppose_weight": 0, "abstain_weight": 0, "total_cast": 0}
                })
            self.db.set_state("proposals", proposals)

            self.add_news(
                "crisis",
                "EMERGENCY BROADCAST — THE GREAT FAMINE",
                "The agricultural crisis is significantly worse than early projections indicated. A second crop failure has devastated the continent. Food reserves are plummeting! All nations immediately lose 15 Grain. Standard round-end consumption of -20 Grain awaits."
            )
            self.trigger_audio_cue("siren", "Round 3: The Great Famine (-15 Grain)")
            return True, "Round 3 Great Famine applied (-15 Grain to all states)."

        return False, f"Unknown round: {round_num}"

    def admin_override_realm(self, realm_id: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, "Realm not found."

        numeric_fields = ["alchemical_grain", "aether_cores", "echo_silk", "military_power",
                          "public_vitality", "diplomatic_standing", "civil_stability", "player_count", "base_votes"]
        for field in numeric_fields:
            if field in updates:
                try:
                    realm[field] = int(updates[field])
                except (ValueError, TypeError):
                    pass

        bool_fields = ["is_quarantined", "is_striking", "is_starving", "tech_efficiency_unlocked", "active"]
        for field in bool_fields:
            if field in updates:
                realm[field] = bool(updates[field])

        if "private_agenda" in updates and updates["private_agenda"]:
            realm["private_agenda"] = str(updates["private_agenda"])
        if "ethos" in updates and updates["ethos"]:
            realm["ethos"] = str(updates["ethos"])
            realm["values"] = realm["ethos"]
        if "pin" in updates and updates["pin"]:
            realm["pin"] = str(updates["pin"])

        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)
        return True, f"Updated {realm['name']}."

    def admin_remove_realm(self, realm_id: str) -> Tuple[bool, str]:
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, f"Realm '{realm_id}' not found."

        realms = [r for r in realms if r["id"] != realm_id]

        trades = self.db.get_state("trades", [])
        trades = [t for t in trades if t.get("initiator_id") != realm_id and t.get("target_id") != realm_id]
        self.db.set_state("trades", trades)

        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)

        self.add_news(
            "diplomacy",
            "DELEGATION WITHDRAWN",
            f"The delegation of {realm['name']} has departed the Grand Summit. Continental dynamics and treaty quotas have been adjusted."
        )
        return True, f"Successfully removed {realm['name']} from the summit."

    def verify_admin_passcode(self, passcode: str) -> bool:
        config = load_scenario_config()
        expected = os.environ.get("ADMIN_PASSCODE") or config.get("simulation_settings", {}).get("admin_passcode", "admin2026")
        return str(passcode).strip() == str(expected).strip()

    def conclude_summit(self) -> Tuple[bool, str, Dict[str, Any]]:
        meta = self.db.get_state("meta", {})
        realms = self.db.get_state("realms", [])
        proposals = self.db.get_state("proposals", [])

        # The last turn ends like the others: nations eat before the results are counted.
        if not meta.get("final_consumption_done") and meta.get("current_turn", 1) >= self.settings()["max_turns"] \
                and meta.get("phase") != "summit_concluded":
            self._consume_grain([r for r in realms if r.get("active", True)], self.settings())
            meta["final_consumption_done"] = True
            self.db.set_state("meta", meta)
            self.db.set_state("realms", realms)

        self._recalculate_all_realms(realms)

        active_realms = [r for r in realms if r.get("active", True)]
        if not active_realms:
            active_realms = realms

        starving_count = sum(1 for r in active_realms if r.get("is_starving") or r.get("alchemical_grain", 0) <= 0)
        low_stability_count = sum(1 for r in active_realms if r.get("civil_stability", 0) < 50)
        zero_stability_count = sum(1 for r in active_realms if r.get("civil_stability", 0) <= 0) or meta.get("any_stability_zero_reached", False)
        avg_vitality = sum(r.get("public_vitality", 0) for r in active_realms) / max(1, len(active_realms))
        avg_stability = sum(r.get("civil_stability", 0) for r in active_realms) / max(1, len(active_realms))
        avg_standing = sum(r.get("diplomatic_standing", 0) for r in active_realms) / max(1, len(active_realms))

        # Questions to the game masters are not resolutions: they do not count towards missions.
        passed_proposals = [p for p in proposals if p.get("status") == "passed" and p.get("effect_type") != "gm_question"]
        failed_proposals = [p for p in proposals if p.get("status") == "rejected" and p.get("effect_type") != "gm_question"]
        trade_partners = self.db.get_state("trade_partners", {})
        military_trades = self.db.get_state("military_trades", [])

        # MGV 2026 Continental Outcome:
        # 🟢 STABLE CONTINENT: No nation starving, no nation Stability < 50, average Standing >= 50
        # 🟡 FRAGILE PEACE: at most 1 nation starving, no nation has Stability 0
        # 🔴 CONTINENTAL CRISIS: 2+ nations starving OR at least one nation has Stability 0
        if starving_count == 0 and low_stability_count == 0 and avg_standing >= 50 and not zero_stability_count:
            verdict = "STABLE CONTINENT"
            verdict_desc = "No nation is starving, all states preserved stability (≥50), and average diplomatic standing is elevated. The continent thrives in enduring peace."
            verdict_grade = "legendary"
        elif starving_count <= 1 and not zero_stability_count:
            verdict = "FRAGILE PEACE"
            verdict_desc = "The worst catastrophes were averted (at most one struggling state, no collapses to zero stability). Peace endures, though precarious."
            verdict_grade = "moderate"
        else:
            verdict = "CONTINENTAL CRISIS"
            verdict_desc = "The continent has plunged into crisis and instability due to widespread famine or domestic civil collapse."
            verdict_grade = "critical"

        N = max(1, len(active_realms))
        realm_evaluations = []
        for r in active_realms:
            r_id = r["id"]

            # -------------------------------------------------------------
            # Public Mission Evaluation
            # -------------------------------------------------------------
            pub_mission = r.get("public_mission") or {}
            pub_achieved = False
            pub_explanation = ""

            if r_id == "sylvan":
                # No nation may starve (0 Grain) at the end of the summit
                pub_achieved = all(o.get("alchemical_grain", 0) > 0 for o in active_realms)
                pub_explanation = "No nation ended with 0 Grain." if pub_achieved else f"Nations suffering famine: {starving_count}."

            elif r_id == "val_khor":
                # Dynamically scaled target based on N
                target_req = max(2, min(N, round(4 * N / 6)))
                reached_cores = sum(1 for o in active_realms if o.get("aether_cores", 0) >= 60)
                pub_achieved = (reached_cores >= target_req)
                pub_explanation = f"{reached_cores} of {N} nations reached ≥60 Cores (Target: ≥{target_req})."

            elif r_id == "solaria":
                # Broadly supported international resolutions passed
                support_threshold = max(2, min(N - 1, 4))
                passed_with_broad_support = 0
                for p in passed_proposals:
                    supporter_count = sum(1 for v in p.get("votes", {}).values() if v.get("choice") == "support")
                    if supporter_count >= support_threshold:
                        passed_with_broad_support += 1
                pub_achieved = (passed_with_broad_support >= 3)
                pub_explanation = f"{passed_with_broad_support} resolutions passed with support from ≥{support_threshold} nations (Target: ≥3)."

            elif r_id == "umbra":
                # No nation may hold more than 90 Military
                max_mil = max((o.get("military_power", 0) for o in active_realms), default=0)
                pub_achieved = all(o.get("military_power", 0) <= 90 for o in active_realms)
                pub_explanation = f"Highest military power on continent: {max_mil} (Target: ≤90)."

            elif r_id == "aquila":
                # Every active nation must trade with at least target_partners different nations
                target_partners = max(1, min(2, N - 1))
                all_traded = all(len(trade_partners.get(o["id"], [])) >= target_partners for o in active_realms)
                pub_achieved = all_traded
                min_partners = min((len(trade_partners.get(o["id"], [])) for o in active_realms), default=0)
                pub_explanation = f"All nations have ≥{target_partners} trade partners." if pub_achieved else f"Least connected nation has only {min_partners} trade partners (Target: ≥{target_partners})."

            elif r_id == "aethelgard":
                # No nation may finish with Stability < 50 and none hit 0
                pub_achieved = all(o.get("civil_stability", 0) >= 50 for o in active_realms) and not zero_stability_count
                pub_explanation = "All nations maintained stability ≥50 and none collapsed to 0." if pub_achieved else f"Nations with stability <50: {low_stability_count}; collapsed to 0: {'Yes' if zero_stability_count else 'No'}."

            else:
                pub_achieved = r.get("public_vitality", 0) >= 50
                pub_explanation = f"Vitality: {r.get('public_vitality')}/100."

            # -------------------------------------------------------------
            # Secret Missions Evaluation (scaled to active player count)
            # -------------------------------------------------------------
            active_secrets = r.get("active_secret_missions", [])
            secret_evals = []

            for sm in active_secrets:
                sm_id = sm.get("id")
                achieved = False
                explanation = ""

                # Sylvan
                if sm_id == "sylvan_winter":
                    achieved = r.get("alchemical_grain", 0) >= 70
                    explanation = f"Grain reserves: {r.get('alchemical_grain')} (Target: ≥70)."
                elif sm_id == "sylvan_defense":
                    mil = r.get("military_power", 0)
                    bought_from_aethelgard = any(
                        mt.get("buyer") == "sylvan" and mt.get("seller") == "aethelgard" for mt in military_trades
                    )
                    achieved = (mil >= 40 and not bought_from_aethelgard)
                    explanation = f"Military: {mil} (Target: ≥40). Purchased from Aethelgard: {'Yes (Violated)' if bought_from_aethelgard else 'No (Honored)'}."

                # Val-Khor
                elif sm_id == "valkhor_tech":
                    other_max_cores = max((o.get("aether_cores", 0) for o in active_realms if o["id"] != "val_khor"), default=0)
                    achieved = r.get("aether_cores", 0) >= other_max_cores + 20
                    explanation = f"Val-Khor Cores: {r.get('aether_cores')}, second highest: {other_max_cores} (Lead: {r.get('aether_cores') - other_max_cores}, Target: ≥20)."
                elif sm_id == "valkhor_grain":
                    achieved = r.get("alchemical_grain", 0) >= 30
                    explanation = f"Grain reserves: {r.get('alchemical_grain')} (Target: ≥30)."
                elif sm_id == "valkhor_contain_military":
                    aethel = next((o for o in active_realms if o["id"] == "aethelgard"), None)
                    aethel_mil = aethel.get("military_power", 0) if aethel else 0
                    diff = aethel_mil - r.get("military_power", 0)
                    achieved = (diff <= 10)
                    explanation = f"Aethelgard Military: {aethel_mil}, Val-Khor: {r.get('military_power', 0)} (Difference: {diff}, Target: ≤10 ahead)."

                # Solaris
                elif sm_id == "solaris_veto":
                    solaris_opposed_passed = [p["title"] for p in passed_proposals if p.get("votes", {}).get("solaria", {}).get("choice") == "oppose"]
                    achieved = (len(solaris_opposed_passed) == 0)
                    explanation = "No resolution opposed by Solaris passed." if achieved else f"Resolutions passed over Solaris veto: {', '.join(solaris_opposed_passed)}."
                elif sm_id == "solaris_standing":
                    other_max_standing = max((o.get("diplomatic_standing", 0) for o in active_realms if o["id"] != "solaria"), default=0)
                    achieved = (r.get("diplomatic_standing", 0) > other_max_standing)
                    explanation = f"Solaris Standing: {r.get('diplomatic_standing')}, second highest: {other_max_standing} (Target: strictly highest on continent)."
                elif sm_id == "solaris_contain_valkhor":
                    vk = next((o for o in active_realms if o["id"] == "val_khor"), None)
                    if vk:
                        max_c = max(o.get("aether_cores", 0) for o in active_realms)
                        max_m = max(o.get("military_power", 0) for o in active_realms)
                        both_top = (vk.get("aether_cores", 0) >= max_c and vk.get("military_power", 0) >= max_m)
                        achieved = not both_top
                        explanation = "Val-Khor did not dominate both sectors simultaneously." if achieved else "Val-Khor achieved supremacy in both Cores and Military!"
                    else:
                        achieved = True
                        explanation = "Val-Khor is not active."
                elif sm_id == "solaris_silk":
                    achieved = r.get("echo_silk", 0) >= 50
                    explanation = f"Silk reserves: {r.get('echo_silk')} (Target: ≥50)."

                # Umbra
                elif sm_id == "umbra_challenge":
                    solaris_supported_failed = [p["title"] for p in failed_proposals if p.get("votes", {}).get("solaria", {}).get("choice") == "support"]
                    has_failed = (len(solaris_supported_failed) >= 1)
                    standing_ok = r.get("diplomatic_standing", 0) >= 50
                    achieved = (has_failed and standing_ok)
                    explanation = f"Solaris initiative defeated: {'Yes' if has_failed else 'No'}, Umbra Standing: {r.get('diplomatic_standing')}/100 (Target: ≥50)."
                elif sm_id == "umbra_autonomy":
                    achieved = (r.get("aether_cores", 0) >= 60 and r.get("civil_stability", 0) >= 60)
                    explanation = f"Cores: {r.get('aether_cores')} (≥60), Stability: {r.get('civil_stability')} (≥60)."

                # Aquila
                elif sm_id == "aquila_wealth":
                    other_max_wealth = max((o.get("total_wealth", 0) for o in active_realms if o["id"] != "aquila"), default=0)
                    lead = r.get("total_wealth", 0) - other_max_wealth
                    achieved = (lead >= 25)
                    explanation = f"Aquila Total Wealth: {r.get('total_wealth')}, second wealthiest: {other_max_wealth} (Lead: {lead}, Target: ≥25)."
                elif sm_id == "aquila_trade_network":
                    req_target = max(1, min(4, N - 1))
                    partners_count = len(trade_partners.get("aquila", []))
                    achieved = (partners_count >= req_target)
                    explanation = f"Aquila traded with {partners_count} nations (Target: ≥{req_target} of {N - 1})."

                # Aethelgard
                elif sm_id == "aethelgard_superiority":
                    other_max_mil = max((o.get("military_power", 0) for o in active_realms if o["id"] != "aethelgard"), default=0)
                    lead = r.get("military_power", 0) - other_max_mil
                    achieved = (lead >= 20)
                    explanation = f"Aethelgard Military: {r.get('military_power')}, second strongest: {other_max_mil} (Lead: {lead}, Target: ≥20)."
                elif sm_id == "aethelgard_contain_valkhor":
                    vk = next((o for o in active_realms if o["id"] == "val_khor"), None)
                    vk_mil = vk.get("military_power", 0) if vk else 0
                    achieved = (vk_mil <= 75)
                    explanation = f"Val-Khor Military: {vk_mil} (Target: ≤75)."
                elif sm_id == "aethelgard_reserves":
                    g = r.get("alchemical_grain", 0)
                    c = r.get("aether_cores", 0)
                    achieved = (g >= 35 and c >= 35)
                    explanation = f"Grain: {g} (≥35), Cores: {c} (≥35)."

                else:
                    achieved = (r.get("public_vitality", 0) >= 50)
                    explanation = "Standard sovereign survival."

                secret_evals.append({
                    "id": sm_id,
                    "title": sm.get("title", "Secret Objective"),
                    "objective": sm.get("objective", ""),
                    "achieved": achieved,
                    "explanation": explanation
                })

            total_missions = 1 + len(secret_evals)
            achieved_missions = (1 if pub_achieved else 0) + sum(1 for sm in secret_evals if sm["achieved"])
            all_achieved = (achieved_missions == total_missions)

            # Score: equal weights for each mission (e.g. 100 points each achieved) + baseline resource points
            score = (
                (achieved_missions * 100) +
                int(r.get("alchemical_grain", 0)) +
                int(r.get("aether_cores", 0)) +
                int(r.get("echo_silk", 0)) +
                int(r.get("military_power", 0)) +
                int(r.get("public_vitality", 0)) +
                int(r.get("diplomatic_standing", 0)) +
                int(r.get("civil_stability", 0))
            )

            if all_achieved:
                epilogue = f"The delegation of {r['name']} fulfilled all assigned mandates ({achieved_missions}/{total_missions})! They return home heralded as sovereign champions."
            elif achieved_missions > 0:
                epilogue = f"The delegation of {r['name']} secured {achieved_missions} of {total_missions} mandates. The domestic assembly views the diplomatic mission with mixed satisfaction."
            else:
                epilogue = f"{r['name']} failed to secure any of its strategic objectives (0/{total_missions}). The government faces a severe political crisis."

            first_secret = secret_evals[0] if secret_evals else {"title": "Secret Directive", "explanation": "No secret directives assigned."}
            realm_evaluations.append({
                "realm_id": r_id,
                "name": r["name"],
                "player_count": int(r.get("player_count", 1)),
                "score": score,
                "achieved_missions": achieved_missions,
                "total_missions": total_missions,
                "success_ratio": f"{achieved_missions}/{total_missions}",
                "directive_achieved": all_achieved,
                "directive_title": first_secret["title"],
                "directive_explanation": first_secret["explanation"],
                "public_mission_eval": {
                    "title": pub_mission.get("title", "Public Mandate"),
                    "description": pub_mission.get("description", ""),
                    "achieved": pub_achieved,
                    "explanation": pub_explanation
                },
                "secret_missions_eval": secret_evals,
                "epilogue": epilogue,
                "stats": {
                    "grain": r.get("alchemical_grain", 0),
                    "cores": r.get("aether_cores", 0),
                    "silk": r.get("echo_silk", 0),
                    "military": r.get("military_power", 0),
                    "vitality": r.get("public_vitality", 0),
                    "standing": r.get("diplomatic_standing", 0),
                    "stability": r.get("civil_stability", 0),
                    "votes": r.get("assembly_votes", 1)
                }
            })

        realm_evaluations.sort(key=lambda x: x["score"], reverse=True)

        arch_diplomat = max(active_realms, key=lambda r: r.get("diplomatic_standing", 0))
        industrial_hegemon = max(active_realms, key=lambda r: r.get("aether_cores", 0))
        breadbasket = max(active_realms, key=lambda r: r.get("alchemical_grain", 0))
        wealthiest = max(active_realms, key=lambda r: r.get("total_wealth", 0))
        supreme_general = max(active_realms, key=lambda r: r.get("military_power", 0))

        summit_outcome = {
            "concluded_at": time.time(),
            "concluded_time_str": self._format_now(),
            "continental_verdict": verdict,
            "continental_desc": verdict_desc,
            "continental_grade": verdict_grade,
            "starving_count": starving_count,
            "avg_vitality": round(avg_vitality, 1),
            "avg_stability": round(avg_stability, 1),
            "avg_standing": round(avg_standing, 1),
            "passed_proposals_count": len(passed_proposals),
            "realm_evaluations": realm_evaluations,
            "honors": {
                "arch_diplomat": {"name": arch_diplomat["name"], "standing": arch_diplomat["diplomatic_standing"]},
                "industrial_hegemon": {"name": industrial_hegemon["name"], "cores": industrial_hegemon["aether_cores"]},
                "breadbasket": {"name": breadbasket["name"], "grain": breadbasket["alchemical_grain"]},
                "wealthiest": {"name": wealthiest["name"], "wealth": wealthiest["total_wealth"]},
                "supreme_general": {"name": supreme_general["name"], "military": supreme_general.get("military_power", 0)}
            }
        }

        meta["phase"] = "summit_concluded"
        meta["is_timer_running"] = False
        meta["turn_timer_end"] = None
        meta["is_discussion_timer_running"] = False
        meta["discussion_timer_end"] = None
        self.db.set_state("meta", meta)
        self.db.set_state("summit_outcome", summit_outcome)

        self.add_news(
            "turn",
            f"THE SUMMIT CONCLUDES: {verdict}",
            f"{verdict_desc} Full diplomatic assessments and scorecards are now active on the Grand Projector."
        )
        self.trigger_audio_cue("gong", f"Summit Concluded: {verdict}")
        return True, f"Summit officially concluded: {verdict}", summit_outcome

    def get_quiz_for_realm(self, realm_id: str) -> Optional[Dict[str, Any]]:
        """Shared question bank (same for every nation) with this realm's per-question status.
        Answers/explanations are only included for questions this realm has already answered."""
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return None
        meta = self.db.get_state("meta", {})
        turn = int(meta.get("current_turn", 1) or 1)
        claimed = set(realm.get("claimed_lore", []))
        failed = set(realm.get("failed_lore", []))
        picks = realm.get("quiz_answers", {})
        questions = []
        for q in load_quiz()["questions"]:
            item = {k: q[k] for k in ("id", "turn", "article", "question", "options", "reward_resource", "reward_amount")}
            if q["id"] in claimed:
                item.update(status="correct", correct_index=q["correct_index"], explanation=q["explanation"])
            elif q["id"] in failed:
                item.update(status="failed", correct_index=q["correct_index"], explanation=q["explanation"],
                            your_index=picks.get(q["id"]))
            elif q["turn"] > turn:
                item.update(status="sealed", question="", options=[])
            else:
                item["status"] = "open"
            questions.append(item)
        return {"current_turn": turn, "questions": questions}

    def build_report(self) -> Dict[str, Any]:
        """Everything that happened in this summit, for the facilitator's results download."""
        state = self.get_full_state()
        realms = [r for r in state["realms"] if r.get("active", True)]
        names = {r["id"]: r["name"] for r in state["realms"]}
        trades = self.db.get_state("trades", [])
        proposals = self.db.get_state("proposals", [])
        types = {t["id"]: t for t in load_scenario_config().get("resolution_types", [])}
        archive = self.db.get_state("news_archive", []) or list(reversed(state.get("news_feed", [])))
        nations = [{
            "id": r["id"], "name": r["name"], "delegates": r.get("player_count"), "votes": r.get("assembly_votes"),
            "grain": r.get("alchemical_grain"), "cores": r.get("aether_cores"), "silk": r.get("echo_silk"),
            "military": r.get("military_power"), "vitality": r.get("public_vitality"),
            "standing": r.get("diplomatic_standing"), "stability": r.get("civil_stability"),
            "public_mission": (r.get("public_mission") or {}).get("title"),
            "secret_missions": [m.get("title") for m in r.get("active_secret_missions", [])],
            "quiz_correct": len(r.get("claimed_lore", [])), "quiz_wrong": len(r.get("failed_lore", [])),
            "trade_partners": sorted({names.get(t["receiver_id"] if t["sender_id"] == r["id"] else t["sender_id"], "?")
                                      for t in trades if t.get("status") == "accepted" and r["id"] in (t["sender_id"], t["receiver_id"])}),
        } for r in realms]
        motions = [{
            "title": p.get("title"), "type": types.get(p.get("effect_type"), {}).get("name", p.get("effect_type")),
            "tabled_by": p.get("proposer_name"), "sponsors": [s.get("name") for s in p.get("supporters", [])],
            "status": p.get("status"), "turn": p.get("created_turn"), "terms": p.get("description"),
            "answer": p.get("answer"),
            "votes": [{"nation": v.get("realm_name"), "choice": v.get("choice"), "weight": v.get("weight")} for v in (p.get("votes") or {}).values()],
        } for p in reversed(proposals)]
        trade_log = [{
            "time": t.get("time_str"), "from": t.get("sender_name"), "to": t.get("receiver_name"),
            "gives": f"{t.get('offer_amount')} {t.get('offer_resource')}", "asks": f"{t.get('request_amount')} {t.get('request_resource')}",
            "status": t.get("status"), "note": t.get("note", ""),
        } for t in reversed(trades)]
        return {
            "generated": self._format_now(), "meta": state["meta"], "outcome": state.get("summit_outcome"),
            "nations": nations, "trades": trade_log, "motions": motions,
            "timeline": [{"turn": n.get("turn"), "time": n.get("time_str"), "type": n.get("type"),
                          "headline": n.get("headline"), "detail": n.get("detail")} for n in archive],
        }

    def admin_set_reflection(self, step: Optional[int]) -> Tuple[bool, str]:
        """Debrief: show reflection question `step` on the projector (None = back to the results)."""
        meta = self.db.get_state("meta", {})
        if meta.get("phase") != "summit_concluded":
            return False, "Reflection starts after the summit has concluded."
        total = len(load_scenario_config().get("reflection_questions", []))
        if step is not None:
            step = max(0, min(total - 1, int(step)))
        meta["reflection_step"] = step
        self.db.set_state("meta", meta)
        return True, "Showing the results." if step is None else f"Reflection question {step + 1} of {total}."

    def submit_lore_quiz(self, realm_id: str, question_id: str, selected_option_index: int) -> Tuple[bool, str, Dict[str, Any]]:
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, "Realm delegation not found.", {}

        claimed = realm.setdefault("claimed_lore", [])
        failed = realm.setdefault("failed_lore", [])
        if question_id in claimed:
            return False, "Your delegation has already answered this question correctly.", {}
        if question_id in failed:
            return False, "Locked: your delegation already answered this question incorrectly.", {}

        question = next((q for q in load_quiz()["questions"] if q["id"] == question_id), None)
        if not question:
            return False, "Question not found.", {}
        meta = self.db.get_state("meta", {})
        if question["turn"] > int(meta.get("current_turn", 1) or 1):
            return False, f"This question unlocks in Turn {question['turn']}.", {}
        if not (0 <= selected_option_index < len(question["options"])):
            return False, "Invalid answer.", {}

        config = load_scenario_config()
        res_type = question.get("reward_resource", "grain")
        amt = int(question.get("reward_amount", 5))
        label = f"+{amt} {RESOURCE_LABELS.get(res_type, res_type.title())}"
        realm.setdefault("quiz_answers", {})[question_id] = selected_option_index
        payload = {"question_id": question_id, "correct_index": question["correct_index"],
                   "explanation": question["explanation"], "article": question["article"]}

        if selected_option_index == question["correct_index"]:
            field = RESOURCE_FIELDS.get(res_type, "alchemical_grain")
            realm[field] = realm.get(field, 0) + amt
            claimed.append(question_id)
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            self.add_news(
                "lore",
                f"SCHOLARLY BREAKTHROUGH: {realm['name'].upper()}",
                f"{realm['name']} delegates answered a Spireopedia question correctly ({label})."
            )
            return True, f"Correct! {label} added to your reserves.", dict(payload, status="correct", reward_label=label)

        # A wrong answer costs exactly what a right answer would have earned.
        field = RESOURCE_FIELDS.get(res_type, "alchemical_grain")
        lost = min(amt, realm.get(field, 0))
        realm[field] = realm.get(field, 0) - lost
        failed.append(question_id)
        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)
        self.add_news(
            "lore",
            f"SCHOLARLY BLUNDER: {realm['name'].upper()}",
            f"{realm['name']} delegates gave a wrong answer in the Spireopedia quiz (-{amt} {RESOURCE_LABELS.get(res_type, res_type)})."
        )
        return False, f"Wrong answer. -{amt} {RESOURCE_LABELS.get(res_type, res_type)}; this question is now locked.", dict(
            payload, status="failed", penalty_resource=res_type, penalty_amount=amt)
