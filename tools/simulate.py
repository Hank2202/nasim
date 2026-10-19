"""
Play complete summits with computer-controlled delegations, through the real game engine,
to check that the game is playable and winnable.

    venv/bin/python tools/simulate.py                 # default sweep, ~5 minutes
    venv/bin/python tools/simulate.py --games 200     # more games per scenario
    venv/bin/python tools/simulate.py --rosters       # every 5-nation roster (one nation left out)
    venv/bin/python tools/simulate.py --nations       # how each nation fares (to rate easy and hard nations)
    venv/bin/python tools/simulate.py --war           # what attacks do to the continent

Kinds of delegations:
  cooperative  - share grain so nobody starves, trade widely, table and back broad motions,
                 study the Spireopedia (take quiz questions they can answer) and pursue their own secret missions
  selfish      - only look after their own reserves, trade at random, vote at random
  devoted      - like cooperative, but in the last turn (after the Assembly, before the final meal) nations that would
                 starve are rescued by the others, even at the cost of their own secret missions
  warlike      - like devoted, but opportunistic: attacks whenever the scouts report favourable odds

The quiz: one question at a time, the nation chooses whether to take the next one. `skill` is the chance of knowing
a standard question; hard ones are known with skill x 0.65.

The numbers are an estimate of what is *possible* with sensible play, not a prediction of a real group.
"""

import argparse
import collections
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("SUMMIT_DB_PATH", os.path.join(tempfile.mkdtemp(), "sim.db"))

import models  # noqa: E402
models.DB_PATH = os.environ["SUMMIT_DB_PATH"]
from engine import SummitEngine, load_quiz, load_scenario_config  # noqa: E402

_connect = models.Database._get_conn


def _fast_conn(self):
    # the simulation throws its database away, so skip the disk syncs that make SQLite slow
    conn = _connect(self)
    conn.execute("PRAGMA synchronous=OFF")
    return conn


models.Database._get_conn = _fast_conn

ARMAGEDDON = dict(scenario="armageddon", **load_scenario_config()["scenarios"]["armageddon"]["suggested"])
FIELDS = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk", "military": "military_power"}
HARD_FACTOR = 0.65
QUIZ_PER_TURN = 6               # a nation has time for about this many 15-second questions between negotiations


class Game:
    def __init__(self, engine, policy, quiz_skill, rng):
        self.e, self.policy, self.skill, self.rng = engine, policy, quiz_skill, rng
        self.bank = {q["id"]: q for q in load_quiz()["questions"]}

    # ------------------------------------------------------------------ helpers
    def realms(self):
        return {r["id"]: r for r in self.e.db.get_state("realms", []) if r.get("active", True)}

    def trade(self, a, b, give, give_amt, get, get_amt):
        if give_amt <= 0 and get_amt <= 0:
            return
        ok, _ = self.e.create_trade(a, b, give, give_amt, get, get_amt)
        if ok:
            trade = self.e.db.get_state("trades")[0]
            self.e.respond_trade(trade["id"], "accept", b)

    def decree(self, rid, action):
        self.e.execute_sovereign_action(rid, action)

    # ------------------------------------------------------------------ phases
    def quiz(self, turn):
        for rid in self.realms():
            for _ in range(QUIZ_PER_TURN):
                status = self.e.get_quiz_status(rid)
                nxt = status["next"]
                if not nxt:
                    break
                p = self.skill * (HARD_FACTOR if nxt["tier"] == "hard" else 1.0)
                # a cooperative delegation only takes a question it expects to answer (the stake is lost otherwise);
                # an unprepared one waits and studies, so it does not take the question this turn
                if self.policy != "selfish" and p < 0.5:
                    break
                ok, _, q = self.e.quiz_start(rid)
                if not ok:
                    break
                correct = self.rng.random() < p
                bank = self.bank[q["question_id"]]
                answer = bank["correct_index"] if correct else (bank["correct_index"] + 1) % 4
                self.e.submit_lore_quiz(rid, q["question_id"], answer)

    def decrees(self, turn):
        R = self.realms()
        for rid, r in R.items():
            if self.policy == "selfish":
                self.decree(rid, self.rng.choice(["relief", "forge", "gala", "security", "muster"]))
                continue
            if rid == "aethelgard" and r["aether_cores"] >= 45 and r["alchemical_grain"] >= 45:
                self.decree(rid, "muster")                       # military lead, keeping reserves ≥35
            if rid == "sylvan" and r["military_power"] < 40 and r["alchemical_grain"] > 90:
                self.decree(rid, "muster")                       # independent defence
            if rid == "solaria" and r["echo_silk"] >= 65:
                self.decree(rid, "gala")                         # highest standing, keep silk ≥50
            if rid == "umbra" and r["diplomatic_standing"] < 55 and r["echo_silk"] >= 15:
                self.decree(rid, "gala")                         # standing ≥50 for "Break the Hegemon"
            if rid == "umbra" and turn == 1 and r["aether_cores"] >= 70:
                self.decree(rid, "security")                     # stability; trims cores so Val-Khor keeps its lead
            if r["civil_stability"] < 55 and r["aether_cores"] >= 20:
                self.decree(rid, "security")

    def trades(self, turn):
        R = self.realms()
        ids = list(R)
        if self.policy == "selfish":
            for _ in range(4):
                a, b = self.rng.sample(ids, 2)
                give, get = self.rng.sample(list(FIELDS), 2)
                self.trade(a, b, give, self.rng.choice([5, 10]), get, self.rng.choice([5, 10]))
            return
        turns_left = 4 - turn
        eat = self.e.settings()["grain_consumption"]
        famine_hit = 15 if (turn <= 2 and self.e.settings()["famine_storyline"]) else 0
        reserve = {"sylvan": 75, "val_khor": 35, "aethelgard": 40}
        # grain flows from nations with a surplus to nations that would otherwise starve
        need = {}
        for rid, r in R.items():
            needed = eat * turns_left + famine_hit + 5
            need[rid] = r["alchemical_grain"] - max(needed, reserve.get(rid, 0) + eat * turns_left // 2)
        donors = sorted([i for i in ids if need[i] > 0], key=lambda i: -need[i])
        takers = sorted([i for i in ids if need[i] < 0], key=lambda i: need[i])
        for t in takers:
            for d in donors:
                if need[d] <= 0 or need[t] >= 0:
                    continue
                amt = min(need[d], -need[t], 30)
                amt -= amt % 5
                if amt < 5:
                    continue
                payment = max(FIELDS, key=lambda f: R[t][FIELDS[f]] if f != "grain" else -1)
                pay_amt = min(amt // 2, max(0, R[t][FIELDS[payment]] - 20))
                self.trade(d, t, "grain", amt, payment, pay_amt - pay_amt % 5)
                need[d] -= amt
                need[t] += amt
        # small goodwill trades so everyone has partners (Aquila's missions)
        if turn == 1:
            for other in ids:
                if other != "aquila" and "aquila" in R:
                    self.trade("aquila", other, "silk", 5, "cores" if other in ("val_khor", "umbra") else "grain", 5)
            for a, b in [("val_khor", "solaria"), ("umbra", "sylvan"), ("aethelgard", "solaria"), ("sylvan", "val_khor")]:
                if a in R and b in R:
                    self.trade(a, b, "cores" if R[a]["aether_cores"] > 40 else "silk", 5, "silk", 5)
            if "aquila" not in R:
                # without the trading nation, a ring of small swaps gives everyone two partners
                for i, a in enumerate(ids):
                    self.trade(a, ids[(i + 1) % len(ids)], "silk", 5, "cores", 5)

    def motions(self, turn):
        R = self.realms()
        ids = list(R)
        if self.policy == "selfish":
            for _ in range(2):
                a, b = self.rng.sample(ids, 2)
                ok, _, pid = self.e.draft_proposal(a, "Motion", "x", self.rng.choice(["tax", "aid", "custom", "embargo"]))
                if ok and self.rng.random() < 0.6:
                    self.e.support_proposal(pid, b)
            return
        first = lambda *pref: next((x for x in pref if x in R), ids[0])
        leader = first("solaria", "aquila", "sylvan", "aethelgard", "val_khor", "umbra")
        plan = {1: [(leader, "aid")], 2: [(leader, "custom")] + ([("solaria", "embargo")] if "solaria" in R else []), 3: []}[turn]
        # a redistribution helps when some nations run low while others hold a lot
        if any(r["alchemical_grain"] < 25 for r in R.values()) and any(r["alchemical_grain"] > 50 for r in R.values()):
            plan.append((first("aquila", "sylvan", "umbra", "val_khor"), "tax"))
        for proposer, kind in plan:
            ok, _, pid = self.e.draft_proposal(proposer, f"{kind} motion", "x", kind)
            if ok:
                self.e.support_proposal(pid, next(x for x in ("aquila", "sylvan", "umbra", "val_khor", "aethelgard", "solaria")
                                                  if x in R and x != proposer))

    def vote(self, prop):
        R = self.realms()
        for rid in R:
            if self.policy == "selfish":
                choice = self.rng.choice(["support", "oppose", "abstain"])
            elif prop.get("effect_type") == "embargo":
                # a Solaris-backed motion the others defeat: Umbra's mission, harmless to Solaris' veto mission
                choice = "support" if rid == "solaria" else "oppose"
            elif prop.get("effect_type") == "emergency_food_a":
                choice = "oppose" if rid in ("sylvan", "aethelgard") else "support"
            else:
                choice = "support"
            self.e.cast_plenary_vote(rid, prop["id"], choice)

    def rescue(self):
        """Last minute: nobody should starve. The richest nations hand over just enough Grain (paid in small change)."""
        if self.policy not in ("devoted", "warlike"):
            return
        eat = self.e.settings()["grain_consumption"]
        for _ in range(8):                                                   # a few rounds of haggling
            R = self.realms()
            cost = {rid: round(eat * 0.75) if r.get("tech_efficiency_unlocked") else eat for rid, r in R.items()}
            short = [rid for rid, r in R.items() if r["alchemical_grain"] - cost[rid] <= 0]
            if not short:
                return
            donors = sorted((rid for rid, r in R.items() if r["alchemical_grain"] - cost[rid] >= 8), key=lambda i: -R[i]["alchemical_grain"])
            if not donors:
                return
            t, d = short[0], donors[0]
            give = min(R[d]["alchemical_grain"] - cost[d] - 1, cost[t] - R[t]["alchemical_grain"] + 1)
            if give < 1:
                return
            payment = "silk" if R[t]["echo_silk"] >= R[t]["aether_cores"] else "cores"
            self.trade(d, t, "grain", give, payment, min(give // 2, max(0, R[t][FIELDS[payment]] - 15)))

    def wars(self, turn):
        """Opportunists attack when the scouts say the odds are good (and always from a position of supplies)."""
        if self.policy != "warlike":
            return
        for rid in list(self.realms()):
            if self.rng.random() < 0.5:
                continue
            status = self.e.get_war_status(rid)
            best = None
            for t in status["targets"]:
                if not t["can_attack"]:
                    continue
                ok, _, info = self.e.battle_preview(rid, t["id"])
                rank = {"Very favourable": 2, "Favourable": 1}.get(info["label"], 0)
                if rank and (best is None or rank > best[0]):
                    best = (rank, t["id"])
            if best:
                self.e.declare_attack(rid, best[1], "siege")
        self.e.resolve_sieges(force=True)          # the armies arrive (the simulation has no wall clock)

    def assembly(self, turn):
        ok, _ = self.e.start_plenary_session()
        if not ok:
            return
        meta = self.e.db.get_state("meta")
        if meta["phase"] == "plenary_quick":
            for pid in meta["plenary_docket"]:
                self.vote(next(p for p in self.e.db.get_state("proposals") if p["id"] == pid))
            self.e.conclude_quick_plenary()
        else:
            while self.e.db.get_state("meta")["phase"] in ("grand_plenary_discussion", "grand_plenary_voting"):
                self.e.start_grand_motion_vote()
                meta = self.e.db.get_state("meta")
                pid = meta["plenary_docket"][meta["current_motion_index"]]
                self.vote(next(p for p in self.e.db.get_state("proposals") if p["id"] == pid))
                self.e.advance_grand_plenary_next()

    def play(self):
        s = self.e.settings()
        for turn in (1, 2, 3):
            for _ in range(s["minor_events_per_turn"]):
                self.e.fire_minor_event(s)
            for _ in range(s.get("large_events_per_turn", 0)):
                self.e.fire_large_event()
            self.quiz(turn)
            self.decrees(turn)
            self.trades(turn)
            self.motions(turn)
            self.wars(turn)
            self.assembly(turn)
            if turn < 3:
                self.e.process_end_of_turn()
            else:
                self.rescue()
        ok, _, outcome = self.e.conclude_summit()
        return outcome


class Results:
    """What a batch of games came to."""

    def __init__(self):
        self.games = 0
        self.verdicts = collections.Counter()
        self.mission_hits, self.mission_totals = collections.Counter(), collections.Counter()
        self.nation_hits, self.nation_totals = collections.Counter(), collections.Counter()
        self.best = self.total = 0
        self.ratio = self.starving = self.unstable = self.battles = self.standing = self.stability = 0.0

    def add(self, engine, outcome):
        self.games += 1
        self.verdicts[outcome["continental_verdict"]] += 1
        self.starving += outcome["starving_count"]
        self.standing += outcome["avg_standing"]
        self.stability += outcome["avg_stability"]
        self.battles += len(engine.db.get_state("battles", []))
        self.unstable += sum(1 for r in engine.db.get_state("realms") if r.get("active", True) and r["civil_stability"] < 50)
        achieved = total = 0
        for ev in outcome["realm_evaluations"]:
            items = [("public:" + ev["realm_id"], ev["public_mission_eval"]["achieved"])] + \
                    [("secret:" + s["id"], s["achieved"]) for s in ev["secret_missions_eval"]]
            for key, ok in items:
                self.mission_totals[key] += 1
                self.mission_hits[key] += int(ok)
            self.nation_hits[ev["realm_id"]] += ev["achieved_missions"]
            self.nation_totals[ev["realm_id"]] += ev["total_missions"]
            achieved += ev["achieved_missions"]
            total += ev["total_missions"]
        self.best = max(self.best, achieved)
        self.total = total
        self.ratio += achieved / total

    def avg(self, name):
        return getattr(self, name) / max(1, self.games)

    def share(self, verdict):
        return self.verdicts[verdict] / max(1, self.games)


def run(engine, policy, skill, games, settings, seed=1, drop=None):
    rng = random.Random(seed)
    res = Results()
    for _ in range(games):
        random.seed(rng.random())
        engine.db.set_state("settings", settings)
        engine.reset_simulation()
        if drop:
            engine.admin_toggle_realm(drop, False)
        res.add(engine, Game(engine, policy, skill, rng).play())
    return res


def row(label, r):
    return (f"{label:36} {r.share('STABLE CONTINENT'):7.0%} {r.share('FRAGILE PEACE'):8.0%} {r.share('CONTINENTAL CRISIS'):7.0%}"
            f" {r.avg('ratio'):13.0%} {r.best:>7}/{r.total} {r.avg('starving'):9.1f} {r.avg('unstable'):8.1f} {r.avg('battles'):8.1f}")


HEADER = (f"{'Scenario':36} {'Stable':>7} {'Fragile':>8} {'Crisis':>7} {'Missions met':>13} {'Best game':>10} "
          f"{'Starving':>9} {'Stab<50':>8} {'Battles':>8}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--rosters", action="store_true", help="play every 5-nation roster instead of the default sweep")
    ap.add_argument("--nations", action="store_true", help="how each nation fares, to rate easy and hard nations")
    ap.add_argument("--war", action="store_true", help="what attacks do to the continent")
    args = ap.parse_args()
    engine = SummitEngine(models.Database(models.DB_PATH))
    if args.rosters:
        return roster_sweep(engine, args.games)
    if args.nations:
        return nation_sweep(engine, args.games)
    if args.war:
        return war_sweep(engine, args.games)

    no_war = {"attacks_enabled": False}
    scenarios = [
        ("cooperative, good quiz (80%)", "cooperative", 0.8, dict(no_war, difficulty="standard")),
        ("cooperative, weak quiz (45%)", "cooperative", 0.45, dict(no_war, difficulty="standard")),
        ("cooperative, no quiz", "cooperative", 0.0, dict(no_war, difficulty="standard")),
        ("selfish, random quiz (25%)", "selfish", 0.25, dict(no_war, difficulty="standard")),
        ("cooperative, good quiz, gentle", "cooperative", 0.8, dict(no_war, difficulty="gentle")),
        ("cooperative, good quiz, harsh", "cooperative", 0.8, dict(no_war, difficulty="harsh")),
        ("Armageddon, cooperative, good quiz", "cooperative", 0.8, dict(ARMAGEDDON, attacks_enabled=False, difficulty="standard")),
        ("Armageddon, cooperative, weak quiz", "cooperative", 0.45, dict(ARMAGEDDON, attacks_enabled=False, difficulty="standard")),
    ]
    d = engine.settings()
    print(f"{args.games} games per row · 6 nations · famine storyline · {d['minor_events_per_turn']} small events "
          f"per turn (up to {d['minor_event_max']:g}) · no attacks\n")
    print(HEADER)
    detail = None
    for label, policy, skill, settings in scenarios:
        if sys.stdout.isatty():
            print(label, end="\r", flush=True)
        r = run(engine, policy, skill, args.games, settings)
        print(row(label, r))
        if detail is None:
            detail = (label, r)
    label, r = detail
    print(f"\nHow often each mission was met ({label}):")
    for key in sorted(r.mission_totals):
        print(f"  {key:34} {r.mission_hits[key] / r.mission_totals[key]:5.0%}")


def war_sweep(engine, games):
    print(f"{games} games per row · 6 nations · famine storyline · standard difficulty\n")
    print(HEADER)
    rows = [
        ("peaceful, good quiz (80%)", "devoted", 0.8, {"attacks_enabled": False}),
        ("peaceful, weak quiz (45%)", "devoted", 0.45, {"attacks_enabled": False}),
        ("warlike, good quiz (80%)", "warlike", 0.8, {"attacks_enabled": True}),
        ("warlike, weak quiz (45%)", "warlike", 0.45, {"attacks_enabled": True}),
        ("warlike, harsh difficulty", "warlike", 0.8, {"attacks_enabled": True, "difficulty": "harsh"}),
        ("warlike, Armageddon", "warlike", 0.8, dict(ARMAGEDDON, attacks_enabled=True)),
        ("warlike from Turn 1", "warlike", 0.8, {"attacks_enabled": True, "attacks_from_turn": 1}),
        ("warlike, 3 marches per turn", "warlike", 0.8, {"attacks_enabled": True, "attacks_per_turn": 3}),
    ]
    for label, policy, skill, settings in rows:
        if sys.stdout.isatty():
            print(label, end="\r", flush=True)
        print(row(label, run(engine, policy, skill, games, dict({"difficulty": "standard"}, **settings))))


def nation_sweep(engine, games):
    """Average share of its missions each nation meets, with cooperative and with warlike delegations."""
    names = {r["id"]: r["name"] for r in load_scenario_config()["realms"]}
    stars = {r["id"]: r["difficulty"] for r in load_scenario_config()["realms"]}
    print(f"{games} games per row · famine storyline · standard difficulty\n")
    print(f"{'Nation':26} {'Rated':>6}  " + "".join(f"{label:>22}" for label in ("devoted, quiz 80%", "devoted, quiz 45%", "warlike, quiz 80%")))
    results = [run(engine, p, s, games, dict(difficulty="standard", attacks_enabled=(p == "warlike")))
               for p, s in (("devoted", 0.8), ("devoted", 0.45), ("warlike", 0.8))]
    for rid in names:
        cells = "".join(f"{r.nation_hits[rid] / max(1, r.nation_totals[rid]):>22.0%}" for r in results)
        print(f"{names[rid]:26} {stars[rid]:>6}  {cells}")


def roster_sweep(engine, games):
    print(f"{games} games per row · famine storyline · standard difficulty · cooperative delegations · no attacks\n")
    print(f"{'Left out':12} {'Quiz':>5} {'Stable':>7} {'Fragile':>8} {'Crisis':>7} {'Missions met':>13} {'Starving':>9}  Missions met least often")
    for drop in (None, "sylvan", "val_khor", "solaria", "umbra", "aquila", "aethelgard"):
        for skill in (0.8, 0.45):
            if sys.stdout.isatty():
                print(drop or "nobody", end="\r", flush=True)
            r = run(engine, "cooperative", skill, games, {"difficulty": "standard", "attacks_enabled": False}, drop=drop)
            hardest = sorted(r.mission_totals, key=lambda k: r.mission_hits[k] / r.mission_totals[k])[:3]
            hard = ", ".join(f"{k.replace('public:', 'public ').replace('secret:', '')} {r.mission_hits[k] / r.mission_totals[k]:.0%}" for k in hardest)
            print(f"{drop or 'nobody':12} {skill:5.0%} {r.share('STABLE CONTINENT'):7.0%} {r.share('FRAGILE PEACE'):8.0%} "
                  f"{r.share('CONTINENTAL CRISIS'):7.0%} {r.avg('ratio'):13.0%} {r.avg('starving'):9.1f}  {hard}")


if __name__ == "__main__":
    main()
