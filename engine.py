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

class SummitEngine:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self._ensure_initial_state()

    def _ensure_initial_state(self):
        if self.db.get_state("meta") is None:
            self.reset_simulation()

    def reset_simulation(self):
        """Reset the simulation back to Turn 1 using parameters from scenario_config.json."""
        config = load_scenario_config()
        meta_defaults = config.get("meta_defaults", {})
        working_secs = meta_defaults.get("working_session_seconds", 300)
        debate_secs = meta_defaults.get("debate_session_seconds", 300)

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
            "auto_inject_crisis": True,
            "triggered_events": [],
            "catastrophe_checked_minutes": [],
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
        """Translates exact numerical values into qualitative tier assessments."""
        if resource_type == "grain":
            return "Abundant" if value >= 60 else ("Sufficient" if value >= 25 else "Depleted")
        elif resource_type == "cores":
            return "Surplus" if value >= 60 else ("Operational" if value >= 25 else "Scarce")
        elif resource_type == "silk":
            return "Lavish" if value >= 60 else ("Modest" if value >= 25 else "Negligible")
        elif resource_type == "military":
            return "Formidable" if value >= 60 else ("Armed" if value >= 25 else "Vulnerable")
        else:
            if value >= 80: return "Flourishing"
            elif value >= 50: return "Stable"
            elif value >= 30: return "Strained"
            else: return "Critical"

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

            r["total_wealth"] = (
                r.get("alchemical_grain", 0) +
                r.get("aether_cores", 0) +
                r.get("echo_silk", 0) +
                r.get("military_power", 0)
            )

            r["grain_tier"] = self.get_qualitative_tier("grain", r.get("alchemical_grain", 0))
            r["cores_tier"] = self.get_qualitative_tier("cores", r.get("aether_cores", 0))
            r["silk_tier"] = self.get_qualitative_tier("silk", r.get("echo_silk", 0))
            r["military_tier"] = self.get_qualitative_tier("military", r.get("military_power", 0))
            r["vitality_tier"] = self.get_qualitative_tier("vitality", r.get("public_vitality", 0))
            r["standing_tier"] = self.get_qualitative_tier("standing", r.get("diplomatic_standing", 0))
            r["stability_tier"] = self.get_qualitative_tier("stability", r.get("civil_stability", 0))

            standing = r.get("diplomatic_standing", 50)
            if standing >= 80: base_votes = 3
            elif standing >= 45: base_votes = 2
            else: base_votes = 1

            r["base_votes"] = base_votes
            r["bonus_votes"] = 0
            r["assembly_votes"] = base_votes
            r["is_plutocrat"] = False

            if r.get("aether_cores", 0) >= 75:
                r["tech_efficiency_unlocked"] = True

            r["is_starving"] = r.get("alchemical_grain", 0) <= 0
            r["complacency_warning"] = (
                r.get("civil_stability", 0) >= 85 and
                r.get("public_vitality", 0) >= 85 and
                r.get("echo_silk", 0) < 10
            )

        if realms:
            max_wealth = max(r["total_wealth"] for r in realms)
            wealthiest_realms = [r for r in realms if r["total_wealth"] == max_wealth]
            if len(wealthiest_realms) == 1:
                wealthiest = wealthiest_realms[0]
                wealthiest["is_plutocrat"] = True
                wealthiest["bonus_votes"] = 1
                wealthiest["assembly_votes"] = wealthiest["base_votes"] + 1

    # -------------------------------------------------------------------------
    # State Polling with Exact Wall-Clock Timer Math & Auto-Event Check
    # -------------------------------------------------------------------------
    def get_full_state(self) -> Dict[str, Any]:
        meta = self.db.get_state("meta", {})
        realms = self.db.get_state("realms", [])
        trades = self.db.get_state("trades", [])
        proposals = self.db.get_state("proposals", [])
        active_assembly = self.db.get_state("active_assembly", None)
        news_feed = self.db.get_state("news_feed", [])

        now = time.time()

        # Wall-clock synchronization for turn timer
        if meta.get("is_timer_running", False):
            end_time = meta.get("turn_timer_end")
            if not end_time:
                end_time = now + meta.get("turn_timer_remaining", 300)
                meta["turn_timer_end"] = end_time

            rem = max(0, int(end_time - now))
            meta["turn_timer_remaining"] = rem

            if rem == 0 and meta.get("phase") == "working":
                self.trigger_audio_cue("gong", "Working Session Concluded")
                meta["is_timer_running"] = False
                meta["turn_timer_end"] = None

            self.db.set_state("meta", meta)

            # Automated background event trigger check
            if meta.get("phase") == "working":
                self._check_automated_event_triggers(meta)

        # Wall-clock synchronization for Grand Plenary debate timer
        if meta.get("is_discussion_timer_running", False) and meta.get("phase") == "grand_plenary_discussion":
            end_time = meta.get("discussion_timer_end")
            if not end_time:
                end_time = now + meta.get("discussion_timer_remaining", 300)
                meta["discussion_timer_end"] = end_time

            rem = max(0, int(end_time - now))
            meta["discussion_timer_remaining"] = rem

            if rem == 0:
                meta["discussion_timer_end"] = None
                self.start_grand_motion_vote()
            else:
                self.db.set_state("meta", meta)

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
            "lore_encyclopedia": cfg.get("lore_encyclopedia", []),
            "resolution_types": cfg.get("resolution_types", []),
            "simulation_settings": cfg.get("simulation_settings", {}),
            "catastrophes_catalog": cfg.get("catastrophes_catalog", []),
            "summit_outcome": self.db.get_state("summit_outcome", None)
        }

    # -------------------------------------------------------------------------
    # Automated Event & Catastrophe Trigger Scheduler
    # -------------------------------------------------------------------------
    def _check_automated_event_triggers(self, meta: Dict[str, Any]):
        # 1. Minute-by-Minute Realistic Catastrophe Simulation
        self._check_minute_catastrophes(meta)

        # 2. Recommended Turn Dilemmas
        events = self.get_catalog_events()
        current_turn = meta.get("current_turn", 1)
        triggered = meta.get("triggered_events", [])
        rem_secs = meta.get("turn_timer_remaining", 300)
        total_secs = meta.get("turn_timer_total", 300)

        for ev in events:
            ev_id = ev.get("id")
            if ev_id in triggered:
                continue

            # Must match turn recommendation
            if ev.get("turn_recommended") != current_turn:
                continue

            should_trigger = False
            trigger_on = ev.get("trigger_on", "turn_mid")

            if trigger_on == "turn_start" and rem_secs >= total_secs - 5:
                should_trigger = True
            elif ev.get("trigger_at_seconds_remaining") is not None:
                if rem_secs <= ev["trigger_at_seconds_remaining"]:
                    should_trigger = True
            elif trigger_on == "turn_mid" and rem_secs <= (total_secs // 2):
                should_trigger = True

            if should_trigger:
                self.trigger_catalog_event(ev_id)
                break

    def _check_minute_catastrophes(self, meta: Dict[str, Any]):
        if not meta.get("auto_inject_crisis", True) or meta.get("phase") != "working":
            return

        total_secs = meta.get("turn_timer_total", 300)
        rem_secs = meta.get("turn_timer_remaining", 300)
        elapsed_secs = total_secs - rem_secs

        # Check at each 60-second boundary (1m, 2m, 3m, 4m)
        current_minute = int(elapsed_secs // 60)
        if current_minute <= 0:
            return

        checked_minutes = meta.setdefault("catastrophe_checked_minutes", [])
        if current_minute in checked_minutes:
            return

        checked_minutes.append(current_minute)
        self.db.set_state("meta", meta)

        config = load_scenario_config()
        catalog = config.get("catastrophes_catalog", [])
        if not catalog:
            return

        sim_settings = config.get("simulation_settings", {})
        compound_chance = float(sim_settings.get("compound_disaster_chance", 0.28))
        max_simul = int(sim_settings.get("max_simultaneous_catastrophes", 2))
        realms = self.db.get_state("realms", [])
        if not realms:
            return

        triggered_count = 0
        candidate_disasters = list(catalog)
        random.shuffle(candidate_disasters)

        for cat in candidate_disasters:
            if triggered_count >= max_simul:
                break

            base_prob = float(cat.get("base_probability", 0.20))
            affinities = cat.get("geographic_affinities", [])
            multipliers = cat.get("resource_multipliers", {})

            # Filter candidate realms that match geography
            eligible_realms = [
                r for r in realms
                if r.get("geography", {}).get("terrain") in affinities
                or "all" in affinities
                or cat.get("id") in r.get("geography", {}).get("hazard_affinities", [])
            ]
            if not eligible_realms:
                eligible_realms = realms

            best_realm = None
            highest_risk_prob = base_prob
            applied_damage_extra = {}
            damage_multiplier = 1.0

            for r in eligible_realms:
                realm_prob = base_prob
                r_damage_extra = {}
                r_damage_mult = 1.0

                if "cores_high_risk" in multipliers:
                    rule = multipliers["cores_high_risk"]
                    if r.get("aether_cores", 0) >= rule.get("threshold", 60):
                        realm_prob += rule.get("prob_boost", 0.10)
                        r_damage_extra.update(rule.get("extra_damage", {}))

                if "grain_high_risk" in multipliers:
                    rule = multipliers["grain_high_risk"]
                    if r.get("alchemical_grain", 0) >= rule.get("threshold", 60):
                        realm_prob += rule.get("prob_boost", 0.15)
                        r_damage_extra.update(rule.get("extra_damage", {}))

                if "grain_low_risk" in multipliers:
                    rule = multipliers["grain_low_risk"]
                    if r.get("alchemical_grain", 0) <= rule.get("threshold", 35):
                        realm_prob += rule.get("prob_boost", 0.12)
                        r_damage_extra.update(rule.get("extra_damage", {}))

                if "silk_high_risk" in multipliers:
                    rule = multipliers["silk_high_risk"]
                    if r.get("echo_silk", 0) >= rule.get("threshold", 50):
                        realm_prob += rule.get("prob_boost", 0.10)
                        r_damage_extra.update(rule.get("extra_damage", {}))

                if "vitality_low_risk" in multipliers:
                    rule = multipliers["vitality_low_risk"]
                    if r.get("public_vitality", 0) <= rule.get("threshold", 45):
                        realm_prob += rule.get("prob_boost", 0.12)
                        r_damage_extra.update(rule.get("extra_damage", {}))

                if "stability_low_risk" in multipliers:
                    rule = multipliers["stability_low_risk"]
                    if r.get("civil_stability", 0) <= rule.get("threshold", 45):
                        realm_prob += rule.get("prob_boost", 0.10)
                        r_damage_extra.update(rule.get("extra_damage", {}))

                if "quarantined_mitigation" in multipliers and r.get("is_quarantined", False):
                    rule = multipliers["quarantined_mitigation"]
                    realm_prob = max(0.02, realm_prob + rule.get("prob_boost", -0.10))
                    r_damage_mult *= (1.0 - rule.get("damage_reduction", 0.5))

                if "cores_efficiency_mitigation" in multipliers and r.get("tech_efficiency_unlocked", False):
                    rule = multipliers["cores_efficiency_mitigation"]
                    r_damage_mult *= (1.0 - rule.get("damage_reduction", 0.3))

                if realm_prob > highest_risk_prob or best_realm is None:
                    highest_risk_prob = realm_prob
                    best_realm = r
                    applied_damage_extra = r_damage_extra
                    damage_multiplier = r_damage_mult

            # Roll random chance
            roll = random.random()
            if roll < highest_risk_prob and best_realm is not None:
                self._apply_catastrophe(cat, best_realm, applied_damage_extra, damage_multiplier)
                triggered_count += 1

                # Check for compound disaster
                compound_roll = random.random()
                if compound_roll < compound_chance and triggered_count < max_simul:
                    compound_triggers = cat.get("compound_triggers", [])
                    if compound_triggers:
                        secondary_id = random.choice(compound_triggers)
                        sec_cat = next((c for c in catalog if c["id"] == secondary_id), None)
                        if sec_cat:
                            sec_affinities = sec_cat.get("geographic_affinities", [])
                            sec_realms = [
                                r for r in realms
                                if r.get("geography", {}).get("terrain") in sec_affinities
                                or "all" in sec_affinities
                            ]
                            sec_target = random.choice(sec_realms) if sec_realms else best_realm
                            self._apply_catastrophe(sec_cat, sec_target, {}, 1.0, is_compound=True, source_cat_name=cat["name"])
                            triggered_count += 1

    def _apply_catastrophe(self, cat: Dict[str, Any], target_realm: Dict[str, Any], extra_damage: Dict[str, int], damage_mult: float, is_compound: bool = False, source_cat_name: str = ""):
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == target_realm["id"]), target_realm)

        res_keys = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk"}
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
        if target_realm_id:
            target = next((r for r in realms if r["id"] == target_realm_id), None)
            if not target:
                return False, f"Realm '{target_realm_id}' not found."
        else:
            affinities = cat.get("geographic_affinities", [])
            eligible = [r for r in realms if r.get("geography", {}).get("terrain") in affinities or "all" in affinities]
            target = random.choice(eligible) if eligible else (realms[0] if realms else None)

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
        meta_defaults = config.get("meta_defaults", {})
        base_consumption = meta_defaults.get("baseline_grain_consumption", 20)
        eff_consumption = meta_defaults.get("tech_efficiency_consumption", 15)
        starv_vit = meta_defaults.get("starvation_vitality_loss", 25)
        starv_stab = meta_defaults.get("starvation_stability_loss", 20)

        for r in realms:
            r_name = r["name"]
            grain_needed = eff_consumption if r.get("tech_efficiency_unlocked") else base_consumption
            r["alchemical_grain"] -= grain_needed

            if r["alchemical_grain"] <= 0:
                r["alchemical_grain"] = 0
                r["is_starving"] = True
                r["public_vitality"] = max(0, r["public_vitality"] - starv_vit)
                r["civil_stability"] = max(0, r["civil_stability"] - starv_stab)
                self.add_news(
                    "crisis",
                    f"FAMINE EMERGENCY IN {r_name.upper()}",
                    f"Silos ran dry this cycle. Populations are starving (-{starv_vit} Vitality, -{starv_stab} Stability)!"
                )
            else:
                r["is_starving"] = False

            if r["civil_stability"] >= 85 and r["public_vitality"] >= 85:
                if r["echo_silk"] >= 10:
                    r["echo_silk"] -= 10
                    self.add_news(
                        "economy",
                        f"LUXURY FESTIVAL IN {r_name.upper()}",
                        f"10 Echo Silk expended to host grand civic celebrations, satisfying citizen appetites."
                    )
                else:
                    grain_drop = int(r["alchemical_grain"] * 0.10)
                    cores_drop = int(r["aether_cores"] * 0.10)
                    silk_drop = int(r["echo_silk"] * 0.10)
                    r["alchemical_grain"] = max(0, r["alchemical_grain"] - grain_drop)
                    r["aether_cores"] = max(0, r["aether_cores"] - cores_drop)
                    r["echo_silk"] = max(0, r["echo_silk"] - silk_drop)
                    self.add_news(
                        "complacency",
                        f"COMPLACENCY SLUMP IN {r_name.upper()}",
                        f"Excessive tranquility without luxury Silk festivals caused a 10% slump in all resource yields (-{grain_drop} grain, -{cores_drop} cores, -{silk_drop} silk)."
                    )

        self._recalculate_all_realms(realms)
        plutocrat = next((r for r in realms if r.get("is_plutocrat")), None)
        if plutocrat:
            plutocrat["civil_stability"] = max(0, plutocrat["civil_stability"] - 5)
            self.add_news(
                "crisis",
                f"PLUTOCRATIC RESTLESSNESS IN {plutocrat['name'].upper()}",
                f"Holding supreme wealth granted +1 Assembly Vote, but severe inequality stoked domestic unrest (-5 Civil Stability)."
            )

        self._recalculate_all_realms(realms)
        self.db.set_state("realms", realms)

        new_turn = current_turn + 1
        meta["current_turn"] = new_turn
        meta["phase"] = "working"
        meta["round_type"] = "grand" if new_turn >= 3 else "quick"
        meta["turn_timer_remaining"] = meta_defaults.get("working_session_seconds", 300)
        meta["turn_timer_total"] = meta_defaults.get("working_session_seconds", 300)
        meta["is_timer_running"] = False
        meta["turn_timer_end"] = None
        meta["plenary_docket"] = []
        meta["current_motion_index"] = 0
        meta["catastrophe_checked_minutes"] = []
        meta["latest_catastrophe"] = None
        self.trigger_audio_cue("turn", f"Turn {new_turn} Working Session Commenced")
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

            sender[sender_res_key] -= trade["offer_amount"]
            receiver[sender_res_key] += trade["offer_amount"]
            receiver[receiver_res_key] -= trade["request_amount"]
            sender[receiver_res_key] += trade["request_amount"]

            trade["status"] = "accepted"
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            self.db.set_state("trades", trades)

            labels_map = {"grain": "Alchemical Grain", "cores": "Aether Cores", "silk": "Echo Silk", "military": "Military Regiments"}
            off_label = labels_map.get(trade['offer_resource'], trade['offer_resource'])
            req_label = labels_map.get(trade['request_resource'], trade['request_resource'])

            self.add_news(
                "trade",
                f"BILATERAL TREATY RATIFIED: {sender['name'].upper()} & {receiver['name'].upper()}",
                f"{sender['name']} delivered {trade['offer_amount']} {off_label} to {receiver['name']} in exchange for {trade['request_amount']} {req_label}."
            )
            self.trigger_audio_cue("trade", f"Treaty Ratified: {sender['name']} & {receiver['name']}")
            return True, "Treaty ratified! Resources atomically transferred."

        return False, "Invalid action."

    # -------------------------------------------------------------------------
    # Motion Drafting & Endorsements
    # -------------------------------------------------------------------------
    def draft_proposal(self, proposer_id: str, title: str, description: str,
                       effect_type: str = "custom",
                       target_seconder_id: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        realms = self.db.get_state("realms", [])
        proposer = next((r for r in realms if r["id"] == proposer_id), None)
        if not proposer:
            return False, "Proposer realm not found.", None

        target_name = None
        if target_seconder_id:
            target_realm = next((r for r in realms if r["id"] == target_seconder_id), None)
            if target_realm:
                target_name = target_realm["name"]

        meta = self.db.get_state("meta", {})
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

        endorsement_msg = f"Direct envoy sent to {target_name}." if target_name else "Open for continental co-sponsorship."
        self.add_news(
            "assembly",
            f"RESOLUTION DRAFTED BY {proposer['name'].upper()}",
            f"'{title}' introduced on the floor. Requires support from at least two sovereign countries to enter the Plenary Ballot. {endorsement_msg}"
        )
        return True, "Motion filed. Awaiting sovereign co-sponsorship.", prop_id

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
            self.add_news(
                "assembly",
                f"MOTION QUALIFIED: '{prop['title']}'",
                f"Seconded by {supporter['name']}. Supported by {len(support_list)} sovereign nations. Placed on the Between-Rounds Plenary Ballot!"
            )
            self.trigger_audio_cue("chime", f"Motion Qualified: {prop['title']}")
            return True, f"Endorsement recorded! '{prop['title']}' has met the 2-country threshold and qualified for the Plenary Ballot."
        else:
            self.db.set_state("proposals", proposals)
            return True, f"Endorsement recorded ({len(support_list)}/2 required)."

    # -------------------------------------------------------------------------
    # Between-Round Plenary Voting Structure
    # -------------------------------------------------------------------------
    def start_plenary_session(self) -> Tuple[bool, str]:
        meta = self.db.get_state("meta", {})
        proposals = self.db.get_state("proposals", [])

        qualified = [p for p in proposals if len(p.get("support_list", [])) >= 2 or p.get("is_qualified")]
        if not qualified:
            return False, "No resolutions met the threshold of support from at least two countries."

        qualified.sort(key=lambda p: len(p.get("support_list", [])), reverse=True)
        docket_ids = [p["id"] for p in qualified]

        meta["is_timer_running"] = False
        meta["turn_timer_end"] = None
        meta["plenary_docket"] = docket_ids
        meta["current_motion_index"] = 0

        config = load_scenario_config()
        meta_defaults = config.get("meta_defaults", {})
        debate_secs = meta_defaults.get("debate_session_seconds", 300)

        current_turn = meta.get("current_turn", 1)
        if current_turn < 3:
            meta["phase"] = "plenary_quick"
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
            config = load_scenario_config()
            debate_secs = config.get("meta_defaults", {}).get("debate_session_seconds", 300)
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
        
        if effect_type == "tax":
            for r in realms:
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
            max_wealth = max(r["total_wealth"] for r in realms)
            wealthiest = next((r for r in realms if r["total_wealth"] == max_wealth), None)
            if wealthiest:
                wealthiest["civil_stability"] = max(0, wealthiest["civil_stability"] - 15)
                self._recalculate_all_realms(realms)
                self.db.set_state("realms", realms)
                return f"Embargo sanctions enforced against {wealthiest['name']} (-15 Stability)."

        elif effect_type == "cordon":
            target_id = prop.get("target_seconder_id")
            if target_id:
                target_realm = next((r for r in realms if r["id"] == target_id), None)
                if target_realm:
                    target_realm["is_quarantined"] = True
                    target_realm["civil_stability"] = min(100, target_realm["civil_stability"] + 10)
                    self._recalculate_all_realms(realms)
                    self.db.set_state("realms", realms)
                    return f"Environmental Cordon deployed around {target_realm['name']}: Borders fortified against unrest (+10 Stability)."
            for r in realms:
                r["is_quarantined"] = True
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)
            return "Continental Environmental Cordon ratified: All frontiers militarized and quarantined against unrest."

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

    def admin_override_realm(self, realm_id: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, "Realm not found."

        numeric_fields = ["alchemical_grain", "aether_cores", "echo_silk",
                          "public_vitality", "diplomatic_standing", "civil_stability"]
        for field in numeric_fields:
            if field in updates:
                try:
                    realm[field] = int(updates[field])
                except (ValueError, TypeError):
                    pass

        bool_fields = ["is_quarantined", "is_striking", "is_starving", "tech_efficiency_unlocked"]
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

    def conclude_summit(self) -> Tuple[bool, str, Dict[str, Any]]:
        meta = self.db.get_state("meta", {})
        realms = self.db.get_state("realms", [])
        proposals = self.db.get_state("proposals", [])

        self._recalculate_all_realms(realms)

        starving_count = sum(1 for r in realms if r.get("is_starving") or r.get("alchemical_grain", 0) <= 0)
        avg_vitality = sum(r.get("public_vitality", 0) for r in realms) / max(1, len(realms))
        avg_stability = sum(r.get("civil_stability", 0) for r in realms) / max(1, len(realms))
        passed_proposals = [p for p in proposals if p.get("status") == "passed"]

        if starving_count == 0 and len(passed_proposals) >= 2 and avg_stability >= 55:
            verdict = "GOLDEN AGE OF ACCORDS"
            verdict_desc = "The Spire succeeded beyond all expectations! Sovereign powers shared reserves, prevented existential famines, and ratified an enduring multilateral charter."
            verdict_grade = "legendary"
        elif starving_count <= 1 and avg_vitality >= 45:
            verdict = "FRAGILE ARMED TRUCE"
            verdict_desc = "Disaster was narrowly averted. While localized scarcity and resource debt test the frontier, continental civilization holds together under vigilant armed neutrality."
            verdict_grade = "moderate"
        else:
            verdict = "CONTINENTAL COLLAPSE & CHAOS"
            verdict_desc = "Multilateral diplomacy shattered under the pressure of national self-interest. Multiple realms fell into famine, and civil rebellions have engulfed the continent."
            verdict_grade = "critical"

        realm_evaluations = []
        for r in realms:
            r_id = r["id"]
            achieved = False
            explanation = ""

            if r_id == "sylvan":
                achieved = r.get("alchemical_grain", 0) >= 75
                explanation = f"Final grain reserve: {r.get('alchemical_grain')} (Target: >= 75)."
            elif r_id == "val_khor":
                achieved = r.get("aether_cores", 0) >= 75 or r.get("tech_efficiency_unlocked", False)
                explanation = f"Final cores reserve: {r.get('aether_cores')} (Target: >= 75 Cores / Tech Efficiency)."
            elif r_id == "solaria":
                achieved = r.get("diplomatic_standing", 0) >= 80
                explanation = f"Final diplomatic standing: {r.get('diplomatic_standing')}/100 (Target: >= 80)."
            elif r_id == "umbra":
                max_rival_votes = max((other.get("assembly_votes", 1) for other in realms if other["id"] != "umbra"), default=1)
                achieved = max_rival_votes < 3
                explanation = f"Highest rival assembly vote: {max_rival_votes} (Target: prevent any rival reaching 3+ votes)."
            elif r_id == "aquila":
                achieved = bool(r.get("is_plutocrat", False))
                explanation = f"Plutocrat Status: {'Retained' if achieved else 'Lost'} (Total Wealth: {r.get('total_wealth')})."
            elif r_id == "aethelgard":
                achieved = r.get("military_power", 0) >= 80 and r.get("civil_stability", 0) >= 70
                explanation = f"Final military power: {r.get('military_power')} (Target: >= 80), Stability: {r.get('civil_stability')}/100."
            else:
                achieved = r.get("public_vitality", 0) >= 60 and not r.get("is_starving", False)
                explanation = f"General sovereign survival achieved: Vitality {r.get('public_vitality')}/100."

            score = (
                int(r.get("alchemical_grain", 0)) +
                int(r.get("aether_cores", 0)) +
                int(r.get("echo_silk", 0)) +
                int(r.get("military_power", 0)) +
                int(r.get("public_vitality", 0)) +
                int(r.get("diplomatic_standing", 0)) +
                int(r.get("civil_stability", 0)) +
                (100 if achieved else 0)
            )

            if achieved:
                epilogue = f"The delegates of {r['name']} are hailed across their homeland for successfully securing national domestic imperatives amidst continental crisis."
            else:
                epilogue = f"While {r['name']} survived the Summit of Realms, failure to fulfill its classified sovereign mandate has triggered intense political discord back home."

            realm_evaluations.append({
                "realm_id": r_id,
                "name": r["name"],
                "score": score,
                "directive_achieved": achieved,
                "directive_title": r.get("private_agenda", "").split(":")[0] if ":" in r.get("private_agenda", "") else "Secret Directive",
                "directive_explanation": explanation,
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

        arch_diplomat = max(realms, key=lambda r: r.get("diplomatic_standing", 0))
        industrial_hegemon = max(realms, key=lambda r: r.get("aether_cores", 0))
        breadbasket = max(realms, key=lambda r: r.get("alchemical_grain", 0))
        wealthiest = max(realms, key=lambda r: r.get("total_wealth", 0))
        supreme_general = max(realms, key=lambda r: r.get("military_power", 0))

        summit_outcome = {
            "concluded_at": time.time(),
            "concluded_time_str": self._format_now(),
            "continental_verdict": verdict,
            "continental_desc": verdict_desc,
            "continental_grade": verdict_grade,
            "starving_count": starving_count,
            "avg_vitality": round(avg_vitality, 1),
            "avg_stability": round(avg_stability, 1),
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
            f"{verdict_desc} The final debrief and sovereign report cards are now active on the plenary projector."
        )
        self.trigger_audio_cue("gong", f"Summit Concluded: {verdict}")
        return True, f"Summit officially concluded: {verdict}", summit_outcome

    def submit_lore_quiz(self, realm_id: str, topic_id: str, selected_option_index: int) -> Tuple[bool, str, Dict[str, Any]]:
        realms = self.db.get_state("realms", [])
        realm = next((r for r in realms if r["id"] == realm_id), None)
        if not realm:
            return False, "Realm delegation not found.", {}

        claimed = realm.setdefault("claimed_lore", [])
        if topic_id in claimed:
            return False, "Knowledge bounty has already been verified and claimed for this dossier.", {}

        failed = realm.setdefault("failed_lore", [])
        if topic_id in failed:
            return False, "Access locked: An earlier intelligence assessment on this dossier failed.", {}

        config = load_scenario_config()
        encyclopedia = config.get("lore_encyclopedia", [])
        topic = next((t for t in encyclopedia if t["id"] == topic_id), None)
        if not topic or "quiz" not in topic:
            return False, "Dossier or intelligence inquiry not found.", {}

        quiz = topic["quiz"]
        correct_idx = quiz.get("correct_index", 0)

        if selected_option_index == correct_idx:
            # Grant bounty
            res_type = quiz.get("reward_resource", "grain")
            amt = quiz.get("reward_amount", 15)

            if res_type == "grain":
                realm["alchemical_grain"] = realm.get("alchemical_grain", 0) + amt
            elif res_type == "cores":
                realm["aether_cores"] = realm.get("aether_cores", 0) + amt
            elif res_type == "silk":
                realm["echo_silk"] = realm.get("echo_silk", 0) + amt
            elif res_type == "standing":
                realm["diplomatic_standing"] = min(100, realm.get("diplomatic_standing", 0) + amt)
            elif res_type == "stability":
                realm["civil_stability"] = min(100, realm.get("civil_stability", 0) + amt)

            claimed.append(topic_id)
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)

            self.add_news(
                "lore",
                f"SCHOLARLY BREAKTHROUGH: {realm['name'].upper()}",
                f"Delegation scholars verified intelligence on '{topic['title']}' ({quiz.get('reward_label')})."
            )
            self.trigger_audio_cue("chime", f"{realm['name']}: Intel Verified")
            return True, f"Intelligence verified! {quiz.get('reward_label')} added to national reserves.", {
                "status": "correct",
                "reward_label": quiz.get("reward_label"),
                "explanation": quiz.get("explanation"),
                "topic_id": topic_id
            }
        else:
            # High-stakes penalty on failure
            sim_settings = config.get("simulation_settings", {})
            penalty_metric = sim_settings.get("quiz_fail_penalty_metric", "diplomatic_standing")
            penalty_amt = sim_settings.get("quiz_fail_penalty_amount", 5)

            realm[penalty_metric] = max(0, realm.get(penalty_metric, 0) - penalty_amt)
            failed.append(topic_id)
            self._recalculate_all_realms(realms)
            self.db.set_state("realms", realms)

            self.add_news(
                "lore",
                f"INTELLIGENCE BLUNDER: {realm['name'].upper()}",
                f"Delegates submitted a flawed assessment on '{topic['title']}' (-{penalty_amt} Diplomatic Standing penalty)."
            )
            self.trigger_audio_cue("alert", f"{realm['name']}: Intelligence Blunder")
            return False, f"Flawed intelligence report! -{penalty_amt} Diplomatic Standing penalty assessed, and access to this dossier is now locked.", {
                "status": "failed",
                "penalty_metric": penalty_metric,
                "penalty_amount": penalty_amt,
                "topic_id": topic_id
            }
