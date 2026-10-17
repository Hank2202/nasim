"""
Play complete summits with computer-controlled delegations, through the real game engine,
to check that the game is playable and winnable.

    venv/bin/python tools/simulate.py                 # default sweep, ~5 minutes
    venv/bin/python tools/simulate.py --games 200     # more games per scenario

Two kinds of delegations:
  cooperative  - share grain so nobody starves, trade widely, table and back broad motions,
                 study the Spireopedia (answer the quiz well) and pursue their own secret missions
  selfish      - only look after their own reserves, trade at random, vote at random

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


class Game:
    def __init__(self, engine, policy, quiz_skill, rng):
        self.e, self.policy, self.skill, self.rng = engine, policy, quiz_skill, rng

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
        for q in load_quiz()["questions"]:
            if q["turn"] > turn:
                continue
            for rid in self.realms():
                correct = self.rng.random() < self.skill
                answer = q["correct_index"] if correct else (q["correct_index"] + 1) % 4
                # cooperative delegations skip questions they would guess (only answer when they studied)
                if self.policy == "cooperative" and not correct and self.rng.random() < 0.7:
                    continue
                self.e.submit_lore_quiz(rid, q["id"], answer)

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
        famine_hit = 15 if (turn <= 2 and self.e.settings()["scenario"] == "famine") else 0
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
        plan = {1: [("solaria", "aid")], 2: [("solaria", "custom"), ("solaria", "embargo")], 3: []}[turn]
        # the grain tax creates food when more nations are short (<25, +15) than rich (>50, −10)
        if 15 * sum(r["alchemical_grain"] < 25 for r in R.values()) > 10 * sum(r["alchemical_grain"] > 50 for r in R.values()):
            plan.append(("aquila", "tax"))
        for proposer, kind in plan:
            if proposer in R:
                ok, _, pid = self.e.draft_proposal(proposer, f"{kind} motion", "x", kind)
                if ok:
                    self.e.support_proposal(pid, "aquila" if proposer != "aquila" else "sylvan")

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
            self.assembly(turn)
            if turn < 3:
                self.e.process_end_of_turn()
        ok, _, outcome = self.e.conclude_summit()
        return outcome


def run(engine, policy, skill, games, settings, seed=1):
    rng = random.Random(seed)
    verdicts = collections.Counter()
    mission_hits = collections.Counter()
    mission_totals = collections.Counter()
    best = 0
    avg_ratio = starving = unstable = 0.0
    for g in range(games):
        random.seed(rng.random())
        engine.db.set_state("settings", settings)
        engine.reset_simulation()
        out = Game(engine, policy, skill, rng).play()
        verdicts[out["continental_verdict"]] += 1
        starving += out["starving_count"] / games
        unstable += sum(1 for r in engine.db.get_state("realms") if r.get("active", True)
                        and r["civil_stability"] < 50) / games
        achieved = total = 0
        for ev in out["realm_evaluations"]:
            items = [("public:" + ev["realm_id"], ev["public_mission_eval"]["achieved"])] + \
                    [("secret:" + s["id"], s["achieved"]) for s in ev["secret_missions_eval"]]
            for key, ok in items:
                mission_totals[key] += 1
                mission_hits[key] += int(ok)
            achieved += ev["achieved_missions"]
            total += ev["total_missions"]
        best = max(best, achieved)
        avg_ratio += achieved / total / games
    return verdicts, mission_hits, mission_totals, best, total, avg_ratio, starving, unstable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    args = ap.parse_args()
    engine = SummitEngine(models.Database(models.DB_PATH))

    scenarios = [
        ("cooperative, good quiz (80%)", "cooperative", 0.8, {"difficulty": "standard"}),
        ("cooperative, weak quiz (40%)", "cooperative", 0.4, {"difficulty": "standard"}),
        ("cooperative, no quiz", "cooperative", 0.0, {"difficulty": "standard"}),
        ("selfish, random quiz (25%)", "selfish", 0.25, {"difficulty": "standard"}),
        ("cooperative, good quiz, gentle", "cooperative", 0.8, {"difficulty": "gentle"}),
        ("cooperative, good quiz, harsh", "cooperative", 0.8, {"difficulty": "harsh"}),
        ("Armageddon, cooperative, good quiz", "cooperative", 0.8, dict(ARMAGEDDON, difficulty="standard")),
        ("Armageddon, cooperative, weak quiz", "cooperative", 0.4, dict(ARMAGEDDON, difficulty="standard")),
    ]
    d = engine.settings()
    print(f"{args.games} games per row · 6 nations · famine storyline · {d['minor_events_per_turn']} small events "
          f"per turn (up to {d['minor_event_max']:g})\n")
    print(f"{'Scenario':34} {'Stable':>7} {'Fragile':>8} {'Crisis':>7} {'Missions met':>13} {'Best game':>10} {'Starving':>9} {'Stab<50':>8}")
    detail = None
    for label, policy, skill, settings in scenarios:
        if sys.stdout.isatty():
            print(label, end="\r", flush=True)
        v, hits, totals, best, total, ratio, starving, unstable = run(engine, policy, skill, args.games, settings)
        n = sum(v.values())
        print(f"{label:34} {v['STABLE CONTINENT'] / n:7.0%} {v['FRAGILE PEACE'] / n:8.0%} {v['CONTINENTAL CRISIS'] / n:7.0%}"
              f" {ratio:13.0%} {best:>7}/{total} {starving:9.1f} {unstable:8.1f}")
        if detail is None:
            detail = (label, hits, totals)
    label, hits, totals = detail
    print(f"\nHow often each mission was met ({label}):")
    for key in sorted(totals):
        print(f"  {key:34} {hits[key] / totals[key]:5.0%}")


if __name__ == "__main__":
    main()
