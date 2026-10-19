"""
Battles between nations.

Military power decides most of a battle, but not all of it. A nation's army is multiplied by how ready the nation is
for war: fed, stable, well supplied, healthy. The further a value is from 50, the harder it pulls (a curve, not a
straight line). Weather, the defender's home ground and a little luck then move each side by a few percent, always
less than the army and the readiness do.

    power = military x readiness x (1 + terrain/weather bonus + luck)

Everything tunable lives in the "battle" section of scenario_config.json; DEFAULTS below are used for missing keys.
"""

import copy
import math
import random
from typing import Any, Dict, List, Optional, Tuple

DEFAULTS: Dict[str, Any] = {
    # How strongly each value changes readiness, and how sharply the pull grows away from 50.
    "readiness_weights": {"stability": 0.22, "grain": 0.20, "cores": 0.14, "vitality": 0.10, "standing": 0.06, "silk": 0.04},
    "curve": 1.6,
    "readiness_range": [0.35, 1.9],
    "luck": 0.12,                       # each side's roll is within +/- this (fog widens it): well below readiness (0.35-1.9)
    "cordon_defence": 0.08,
    # What a nation's scouts can tell it. How many modifiers are revealed depends on the wealth (Grain + Cores + Silk) of
    # the nation asking; how exact they are depends on its Silk and Cores (its spies and its instruments).
    "intel": {"wealth_per_line": 28, "max_lines": 9, "accuracy_at": 80, "accuracy_cap": 0.9, "own_bonus": 0.30, "noise_pp": 14,
              "odds_blur_base": 0.08, "odds_blur_scale": 0.30},
    "attack_cost": {"grain": 10},
    "min_military": 10,
    "max_attacks_received_per_turn": 2,
    "stalemate_below": 0.04,            # |margin| = |A-D|/(A+D) under this: nobody wins
    "narrow_below": 0.15,
    "crushing_above": 0.40,
    "plunder": {"base": 0.05, "scale": 0.30, "keep": 0.75, "caps": {"grain": 30, "cores": 25, "silk": 25}},
    "terrain": {
        "volcanic_mountains": {"name": "Volcanic mountains", "defence": 0.10, "note": "Steep passes favour the defenders."},
        "abyssal_chasm": {"name": "The Abyssal Rift", "defence": 0.10, "note": "Attackers must fight in the dark."},
        "northern_steppes": {"name": "Open steppe", "defence": -0.04, "note": "Open ground favours the attackers."},
        "verdant_lowlands": {"name": "Soft lowland fields", "defence": -0.05, "note": "Flat farmland is hard to hold."},
        "solar_plateau": {"name": "Sunlit plateau", "defence": 0.03, "note": "A good view of the approach."},
        "coastal_archipelago": {"name": "Island coast", "defence": 0.08, "note": "Landings under fire are costly."},
    },
    "weather": [
        {"id": "clear", "name": "Clear skies", "weight": 4, "attacker": 0.0, "defender": 0.0, "luck": 1.0,
         "text": "Clear skies: neither side has an advantage."},
        {"id": "rain", "name": "Heavy rain", "weight": 2, "attacker": -0.05, "defender": 0.0, "luck": 1.0,
         "text": "Heavy rain turns the roads to mud and slows attackers."},
        {"id": "fog", "name": "Dense fog", "weight": 2, "attacker": -0.03, "defender": -0.03, "luck": 1.6,
         "text": "Dense fog hides both armies from each other."},
        {"id": "storm", "name": "Thunderstorm", "weight": 1, "attacker": -0.08, "defender": -0.02, "luck": 1.0,
         "text": "A thunderstorm batters marching columns."},
        {"id": "heat", "name": "Scorching heat", "weight": 1, "attacker": -0.04, "defender": -0.04, "luck": 1.0,
         "text": "Scorching heat saps both armies."},
        {"id": "tailwind", "name": "Favourable winds", "weight": 1, "attacker": 0.05, "defender": 0.0, "luck": 1.0,
         "text": "Favourable winds speed the march."},
        {"id": "night", "name": "Moonless night", "weight": 1, "attacker": 0.04, "defender": -0.02, "luck": 1.0,
         "text": "A moonless night favours raiders."},
    ],
}

# Outcome tiers (from the attacker's point of view)
OUTCOMES = ("attacker_crushing", "attacker_victory", "attacker_narrow", "stalemate",
            "defender_narrow", "defender_victory", "defender_crushing")
RES_FIELDS = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk", "military": "military_power",
              "vitality": "public_vitality", "standing": "diplomatic_standing", "stability": "civil_stability"}
FACTOR_LABELS = {"stability": "Stability", "grain": "Grain", "cores": "Cores", "vitality": "Vitality", "standing": "Standing", "silk": "Silk"}
FACTOR_TEXT = {"stability": "Civil stability", "grain": "Grain stores", "cores": "Aether Cores", "vitality": "Public vitality",
               "standing": "Diplomatic standing", "silk": "Echo Silk"}
FACTOR_FIELDS = {"stability": "civil_stability", "grain": "alchemical_grain", "cores": "aether_cores",
                 "vitality": "public_vitality", "standing": "diplomatic_standing", "silk": "echo_silk"}


def config(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """DEFAULTS with the scenario file's overrides merged on top (one level deep for the tables)."""
    cfg = copy.deepcopy(DEFAULTS)
    for key, value in (raw or {}).items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def roll_weather(cfg: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    table = cfg["weather"]
    return dict(rng.choices(table, weights=[w.get("weight", 1) for w in table], k=1)[0])


def _pull(value: float, curve: float) -> float:
    """-1..+1.5 on the way away from 50, shaped so that being far from 50 matters much more than being near it."""
    d = max(-1.0, min(1.5, (value - 50.0) / 50.0))
    return (abs(d) ** curve) * (1 if d >= 0 else -1)


def readiness(realm: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    """How ready the nation is for war (about 0.35 to 1.9) and the biggest reasons, in percent."""
    factors = []
    total = 0.0
    for key, weight in cfg["readiness_weights"].items():
        value = realm.get(FACTOR_FIELDS[key], 0)
        part = weight * _pull(value, cfg["curve"])
        total += part
        factors.append({"key": key, "label": FACTOR_LABELS[key], "value": value, "pct": round(part * 100)})
    lo, hi = cfg["readiness_range"]
    factors.sort(key=lambda f: -abs(f["pct"]))
    return max(lo, min(hi, 1.0 + total)), factors


def terrain_for(realm: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    tid = (realm.get("geography") or {}).get("terrain", "")
    t = dict(cfg["terrain"].get(tid, {"name": "Unknown ground", "defence": 0.0, "note": ""}))
    t["id"] = tid
    return t


def side_power(realm: Dict[str, Any], side: str, terrain: Dict[str, Any], weather: Dict[str, Any],
               cfg: Dict[str, Any], rng: Optional[random.Random]) -> Dict[str, Any]:
    ready, factors = readiness(realm, cfg)
    if side == "attacker":
        env = weather.get("attacker", 0.0)
    else:
        env = terrain.get("defence", 0.0) + weather.get("defender", 0.0)
        if realm.get("is_quarantined"):
            env += cfg["cordon_defence"]
    mods = realm.get("modifiers") or {}                       # facilitator adjustments, in percent
    env += mods.get("war_power_pct", 0) / 100.0
    if side == "defender":
        env += mods.get("war_defence_pct", 0) / 100.0
    luck_range = cfg["luck"] * weather.get("luck", 1.0)
    luck = rng.uniform(-luck_range, luck_range) if rng else 0.0
    military = realm.get("military_power", 0)
    return {"power": max(0.0, military * ready * (1.0 + env + luck)), "military": military, "readiness": ready,
            "factors": factors, "environment": env, "luck": luck}


def outcome_for(margin: float, cfg: Dict[str, Any]) -> str:
    s = abs(margin)
    if s < cfg["stalemate_below"]:
        return "stalemate"
    tier = "narrow" if s < cfg["narrow_below"] else ("crushing" if s >= cfg["crushing_above"] else "victory")
    return f"{'attacker' if margin > 0 else 'defender'}_{tier}"


def intel(realm: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """How much this nation's scouts can find out: `reach` (how many modifiers) and `accuracy` (0 to 1, how exact)."""
    ic = cfg["intel"]
    wealth = realm.get("alchemical_grain", 0) + realm.get("aether_cores", 0) + realm.get("echo_silk", 0)
    reach = max(1, min(ic["max_lines"], round(wealth / ic["wealth_per_line"])))
    accuracy = max(0.0, min(ic["accuracy_cap"], ((realm.get("echo_silk", 0) + realm.get("aether_cores", 0)) / 2) / ic["accuracy_at"]))
    return {"reach": reach, "accuracy": accuracy}


def accuracy_label(accuracy: float) -> str:
    return "rough guesses" if accuracy < 0.3 else ("fair estimates" if accuracy < 0.6 else "good estimates")


def modifier_lines(realm: Dict[str, Any], side: str, terrain: Dict[str, Any], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The modifiers that move one side's strength, in percent. The random roll and the facilitators' own adjustments are
    never among them: no one can scout those."""
    _ready, factors = readiness(realm, cfg)
    lines = [{"key": f["key"], "label": FACTOR_TEXT[f["key"]], "pct": f["pct"]} for f in factors]
    if side == "defender":
        lines.append({"key": "terrain", "label": f"Home ground ({terrain.get('name', 'terrain')})", "pct": round(terrain.get("defence", 0) * 100)})
        if realm.get("is_quarantined"):
            lines.append({"key": "cordon", "label": "Cordon around the borders", "pct": round(cfg["cordon_defence"] * 100)})
    return [ln for ln in lines if ln["pct"] != 0]


def _word(value: float) -> str:
    size = abs(value)
    if size < 3:
        return "barely matters"
    return ("slightly " if size < 10 else ("" if size < 20 else "strongly ")) + ("helps" if value > 0 else "hurts")


def reveal(own: Dict[str, Any], sides: Dict[str, List[Dict[str, Any]]], viewer_side: str, scout: Dict[str, Any],
           cfg: Dict[str, Any], seed: str) -> Dict[str, Any]:
    """What a viewer learns about the modifiers of both sides. The biggest modifiers are revealed first; how many depends
    on `scout["reach"]`. Each is shown with noise (the same seed always gives the same noise), so the more accurate the
    scouts the closer the figure is to the truth, and the poorest scouts only get a word, which can even be the wrong one."""
    ic = cfg["intel"]
    pool = [(side, ln) for side, lines in sides.items() for ln in lines]
    pool.sort(key=lambda item: (-abs(item[1]["pct"]), random.Random(f"{seed}:order:{item[0]}:{item[1]['key']}").random()))
    shown = []
    for side, ln in pool[:scout["reach"]]:
        mine = side == viewer_side
        acc = min(ic["accuracy_cap"], scout["accuracy"] + (ic["own_bonus"] if mine else 0.0))   # never perfect
        sigma = ic["noise_pp"] * (1.0 - acc)
        noisy = ln["pct"] + random.Random(f"{seed}:noise:{side}:{ln['key']}").gauss(0, sigma)
        if acc >= 0.6:
            text = f"about {round(noisy):+d}%"
        elif acc >= 0.3:
            lo, hi = 5 * round((noisy - sigma) / 5), 5 * round((noisy + sigma) / 5)
            text = f"between {lo:+d}% and {hi:+d}%" if lo != hi else f"around {lo:+d}%"
        else:
            text = _word(noisy)
        shown.append({"whose": "own" if mine else "enemy", "side": side, "label": ln["label"], "text": text,
                      "dir": "pos" if noisy >= 0 else "neg"})
    return {"modifiers": shown, "hidden": max(0, len(pool) - len(shown)), "total": len(pool),
            "quality": accuracy_label(scout["accuracy"])}


def odds_label(ratio: float) -> str:
    for limit, text in ((0.6, "Very unfavourable"), (0.85, "Unfavourable"), (1.2, "Evenly matched"), (1.7, "Favourable")):
        if ratio < limit:
            return text
    return "Very favourable"


def scouting(attacker: Dict[str, Any], defender: Dict[str, Any], weather: Dict[str, Any], cfg: Dict[str, Any],
             seed: str) -> Dict[str, Any]:
    """The attacker's scouting report: the balance without luck, blurred (less so with good scouts), and the modifiers that
    the attacker's wealth and spies reveal. The same seed always gives the same blur, so asking again learns nothing new."""
    terrain = terrain_for(defender, cfg)
    a = side_power(attacker, "attacker", terrain, weather, cfg, None)
    d = side_power(defender, "defender", terrain, weather, cfg, None)
    scout = intel(attacker, cfg)
    ic = cfg["intel"]
    width = ic["odds_blur_base"] + ic["odds_blur_scale"] * (1.0 - scout["accuracy"])
    blur = math.exp(random.Random(seed).uniform(-width, width))
    ratio = (a["power"] / d["power"]) * blur if d["power"] > 0 else 9.9
    sides = {"attacker": modifier_lines(attacker, "attacker", terrain, cfg), "defender": modifier_lines(defender, "defender", terrain, cfg)}
    report = reveal(attacker, sides, "attacker", scout, cfg, seed)
    report.update(label=odds_label(ratio), reach=scout["reach"],
                  terrain={"name": terrain.get("name", ""), "note": terrain.get("note", "")},
                  weather={"id": weather.get("id", ""), "name": weather.get("name", ""), "text": weather.get("text", "")})
    return report


def resolve(attacker: Dict[str, Any], defender: Dict[str, Any], weather: Dict[str, Any], cfg: Dict[str, Any],
            rng: random.Random) -> Dict[str, Any]:
    """Fight the battle. Returns the outcome and every change to carry out, without touching the realms."""
    terrain = terrain_for(defender, cfg)
    a = side_power(attacker, "attacker", terrain, weather, cfg, rng)
    d = side_power(defender, "defender", terrain, weather, cfg, rng)
    total = a["power"] + d["power"]
    margin = (a["power"] - d["power"]) / total if total > 0 else 0.0
    outcome = outcome_for(margin, cfg)
    scale = abs(margin)

    winner = loser = None
    if outcome != "stalemate":
        winner, loser = (attacker, defender) if margin > 0 else (defender, attacker)

    # changes[id][resource] = delta (negative = lost); plunder = what the winner took
    changes: Dict[str, Dict[str, int]] = {attacker["id"]: {}, defender["id"]: {}}
    plunder: Dict[str, int] = {}

    def add(rid: str, res: str, delta: int) -> None:
        if delta:
            changes[rid][res] = changes[rid].get(res, 0) + delta

    if outcome == "stalemate":
        for r in (attacker, defender):
            add(r["id"], "military", -round(r.get("military_power", 0) * 0.05))
        add(defender["id"], "stability", -2)
        add(attacker["id"], "standing", -4)
    else:
        pl = cfg["plunder"]
        frac = pl["base"] + pl["scale"] * scale
        for res in ("grain", "cores", "silk"):
            have = loser.get(RES_FIELDS[res], 0)
            lost = min(have, pl["caps"].get(res, 30), round(have * frac))
            if lost > 0:
                got = round(lost * pl["keep"])
                add(loser["id"], res, -lost)
                add(winner["id"], res, got)
                plunder[res] = got
        add(loser["id"], "military", -round(loser.get("military_power", 0) * (0.08 + 0.32 * scale)))
        add(winner["id"], "military", -round(winner.get("military_power", 0) * (0.04 + 0.10 * (1 - scale))))
        add(loser["id"], "stability", -round(3 + 17 * scale))
        add(winner["id"], "stability", -2)
        add(loser["id"], "vitality", -round(2 + 8 * scale))
        add(attacker["id"], "standing", -6)                      # aggression is never free
        if winner is attacker and outcome == "attacker_crushing":
            add(attacker["id"], "standing", -4)                  # bullying a much weaker nation
        if loser is attacker:
            add(attacker["id"], "standing", -4)                  # and failing is humiliating
        if winner is defender:
            add(defender["id"], "standing", 3)                   # sympathy for the victim

    return {"outcome": outcome, "winner_id": winner["id"] if winner else None, "loser_id": loser["id"] if loser else None,
            "margin": margin, "scale": scale, "share": a["power"] / total if total > 0 else 0.5,
            "terrain": terrain, "weather": weather, "changes": changes, "plunder": plunder,
            "attacker": a, "defender": d,
            "lines": {"attacker": modifier_lines(attacker, "attacker", terrain, cfg),
                      "defender": modifier_lines(defender, "defender", terrain, cfg)}}
