"""
Comprehensive Automated Test Suite for The Summit of Realms.
Validates:
  - Wall-clock timer synchronization (immune to rapid multi-client polling)
  - Dynamic, non-hardcoded event targeting queries ('highest 1 by alchemical_grain', 'lowest 3 by public_vitality', etc.)
  - Sovereign Domestic Governance Levers (Relief, Forges, Gala, Civil Guard)
  - Unified Single Source of Truth ('scenario_config.json' without redundant 'events.json')
  - Participant Mobile Console 6 Tabs: Realm, World, Trade, Motions, Wiki, Quiz
  - Trade Proposal & Atomic Execution Lifecycle
  - Sovereign Motion Qualification (2-country endorsement rule)
  - Delegation 4-digit PIN authentication & session security
  - Projector zero-scroll layout & qualitative intel
  - Direct Facilitator timer editing APIs
  - Plenary state machine & voting
"""

import unittest
import os
import json
import tempfile
import time

# Everything the tests do goes to a throwaway database, never to the summit.db of a real game (set before app is imported).
os.environ["SUMMIT_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "summit_under_test.db")

from models import Database
from engine import SummitEngine, load_scenario_config, load_events_catalog, load_quiz
from app import app

TEST_DB = "test_summit.db"

class TestSummitEngine(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        self.db = Database(TEST_DB)
        self.engine = SummitEngine(self.db)

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_single_source_of_truth_no_events_json(self):
        """Verify events.json is removed and scenario_config.json is the sole source."""
        self.assertFalse(os.path.exists("events.json"), "events.json must not exist to prevent redundancy!")
        catalog = load_events_catalog()
        self.assertGreater(len(catalog), 0)
        self.assertTrue(any(e["id"] == "blight_outbreak" for e in catalog))

    def test_world_lore_in_full_state(self):
        """Verify world lore and backstory are included in get_full_state()."""
        state = self.engine.get_full_state()
        self.assertIn("world_lore", state)
        self.assertIn("title", state["world_lore"])
        self.assertIn("resources", state["world_lore"])

    def test_timer_wallclock_stability_under_rapid_polling(self):
        """Verify that multiple concurrent polls do NOT drain the timer at 3x-20x speed."""
        self.engine.admin_control_timer("start", 300)
        
        # Simulate 20 rapid polls in ~0.05 seconds
        for _ in range(20):
            st = self.engine.get_full_state()
            time.sleep(0.002)

        final_st = self.engine.get_full_state()
        rem = final_st["meta"]["turn_timer_remaining"]
        # In a real ~0.05s interval, time remaining must still be 299 or 300, NEVER <= 280!
        self.assertGreaterEqual(rem, 299, f"Timer drained too fast! Expected >= 299, got {rem}")

    def test_dynamic_event_targeting_queries(self):
        realms = self.engine.get_full_state()["realms"]

        # 1. Highest 1 by grain -> Sylvan has 70 grain
        top_grain = self.engine._resolve_target_realms(realms, "highest 1 by alchemical_grain")
        self.assertEqual(len(top_grain), 1)
        self.assertEqual(top_grain[0]["id"], "sylvan")

        # 2. Lowest 3 by vitality
        low_vit = self.engine._resolve_target_realms(realms, "lowest 3 by public_vitality")
        self.assertEqual(len(low_vit), 3)

        # 3. Top 2 by aether_cores -> Umbra (70) and Val-Khor (60)
        top_cores = self.engine._resolve_target_realms(realms, "top 2 by aether_cores")
        self.assertEqual(len(top_cores), 2)
        top_ids = [r["id"] for r in top_cores]
        self.assertIn("umbra", top_ids)
        self.assertIn("val_khor", top_ids)

        # 4. 'all'
        all_realms = self.engine._resolve_target_realms(realms, "all")
        self.assertEqual(len(all_realms), 6)

    def test_sovereign_domestic_levers(self):
        # 1. Sylvan enacts Emergency Grain Relief: -15 Grain -> +15 Vitality
        sylvan_before = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")
        g_before = sylvan_before["alchemical_grain"]
        v_before = sylvan_before["public_vitality"]

        ok, msg = self.engine.execute_sovereign_action("sylvan", "relief")
        self.assertTrue(ok)

        sylvan_after = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")
        self.assertEqual(sylvan_after["alchemical_grain"], g_before - 15)
        self.assertEqual(sylvan_after["public_vitality"], min(100, v_before + 15))

        # 2. Val-Khor enacts Stoke Forges: -10 Grain, -10 Silk -> +15 Cores
        vk_before = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "val_khor")
        cores_before = vk_before["aether_cores"]

        ok_f, _ = self.engine.execute_sovereign_action("val_khor", "forge")
        self.assertTrue(ok_f)

        vk_after = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "val_khor")
        self.assertEqual(vk_after["aether_cores"], cores_before + 15)

        # 3. Solaria enacts Gala: -15 Silk -> +10 Standing, +10 Stability
        ok_g, _ = self.engine.execute_sovereign_action("solaria", "gala")
        self.assertTrue(ok_g)

        # 4. Umbra enacts Civil Guard: -10 Cores -> +15 Stability
        ok_s, _ = self.engine.execute_sovereign_action("umbra", "security")
        self.assertTrue(ok_s)

    def test_trade_lifecycle(self):
        # Sylvan creates trade with Solaria: offers 10 grain for 10 silk
        ok, msg = self.engine.create_trade("sylvan", "solaria", "grain", 10, "silk", 10)
        self.assertTrue(ok)

        trades = self.engine.get_full_state()["trades"]
        self.assertEqual(len(trades), 1)
        trade_id = trades[0]["id"]
        self.assertEqual(trades[0]["status"], "pending")

        # Solaria accepts
        ok_acc, msg_acc = self.engine.respond_trade(trade_id, "accept", "solaria")
        self.assertTrue(ok_acc)

        # Verify trade marked accepted
        trades_after = self.engine.get_full_state()["trades"]
        self.assertEqual(trades_after[0]["status"], "accepted")

    def test_delegation_pin_authentication(self):
        self.assertTrue(self.engine.verify_realm_pin("sylvan", "1001"))
        self.assertFalse(self.engine.verify_realm_pin("sylvan", "9999"))

        ok, msg = self.engine.admin_set_realm_pin("sylvan", "5432")
        self.assertTrue(ok)
        self.assertTrue(self.engine.verify_realm_pin("sylvan", "5432"))

    def test_direct_timer_editing(self):
        self.engine.admin_set_timer(420)
        state = self.engine.get_full_state()
        self.assertEqual(state["meta"]["turn_timer_remaining"], 420)

        self.engine.admin_adjust_timer(-60)
        state = self.engine.get_full_state()
        self.assertEqual(state["meta"]["turn_timer_remaining"], 360)

    def test_targeted_proposal_and_two_country_qualification(self):
        ok, msg, pid = self.engine.draft_proposal(
            "sylvan", "Iron-Wood Pact", "Exchange timber for smelting cores", "custom", "val_khor"
        )
        self.assertTrue(ok)

        ok_fail, _ = self.engine.support_proposal(pid, "umbra")
        self.assertFalse(ok_fail)

        ok_vk, msg_vk = self.engine.support_proposal(pid, "val_khor")
        self.assertTrue(ok_vk)

        prop_after = next(p for p in self.engine.get_full_state()["proposals"] if p["id"] == pid)
        self.assertTrue(prop_after["is_qualified"])

    def test_trade_with_diplomatic_note(self):
        """A note travels with the offer to the partner only; public news never shows offers, notes or amounts."""
        ok, msg = self.engine.create_trade(
            "sylvan", "val_khor", "grain", 15, "cores", 10,
            note="Urgent grain for your miners in exchange for reactor power."
        )
        self.assertTrue(ok)
        trades = self.engine.get_full_state()["trades"]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["note"], "Urgent grain for your miners in exchange for reactor power.")
        news = json.dumps(self.engine.get_full_state()["news_feed"])
        self.assertNotIn("Urgent grain", news)
        self.engine.respond_trade(trades[0]["id"], "accept", "val_khor")
        latest = self.engine.get_full_state()["news_feed"][0]
        self.assertIn("SYLVAN CONCORDAT & IRON VAL-KHOR", latest["headline"])
        self.assertNotIn("15", latest["detail"])
        self.assertNotIn("Grain", latest["detail"])

    def test_environmental_cordon_statutory_effect(self):
        """Verify cordon resolution ratifies quarantine protection."""
        ok, msg, pid = self.engine.draft_proposal(
            "aethelgard", "Frontier Quarantine Cordon",
            "Militarize frontiers and seal refugee spillovers.", "cordon", None, "sylvan"
        )
        self.assertTrue(ok)
        self.engine.support_proposal(pid, "sylvan")

        prop = next(p for p in self.engine.get_full_state()["proposals"] if p["id"] == pid)
        result_str = self.engine._apply_proposal_effect(prop)
        self.assertIn("Sylvan Concordat +10 Stability", result_str)
        self.assertIn("Sylvan Concordat is cordoned", result_str)

        sylvan = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")
        self.assertTrue(sylvan["is_quarantined"])

    def test_motion_templates_validation(self):
        """Players draft from templates: food acts are facilitator-only, cordon needs a target, title/terms required."""
        ok, msg, _ = self.engine.draft_proposal("sylvan", "Food", "Terms", "emergency_food_a")
        self.assertFalse(ok)
        ok, msg, _ = self.engine.draft_proposal("sylvan", "Watch", "Terms", "cordon")
        self.assertFalse(ok)
        self.assertIn("Choose the nation", msg)
        ok, msg, _ = self.engine.draft_proposal("sylvan", "  ", "Terms", "aid")
        self.assertFalse(ok)
        ok, msg, pid = self.engine.draft_proposal("sylvan", "Watch", "Terms", "cordon", None, "umbra")
        self.assertTrue(ok)
        prop = next(p for p in self.engine.get_full_state()["proposals"] if p["id"] == pid)
        self.assertEqual(prop["target_realm_name"], "Umbral Enclave")

    def test_inactive_nations_are_left_out(self):
        """With fewer nations: no trades with absent nations, nation-specific secret missions are skipped."""
        self.engine.admin_set_active_realm_count(4)  # sylvan, val_khor, solaria, umbra
        ok, msg = self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5)
        self.assertFalse(ok)
        realms = {r["id"]: r for r in self.engine.get_full_state()["realms"]}
        sylvan_ids = [m["id"] for m in realms["sylvan"]["active_secret_missions"]]
        self.assertNotIn("sylvan_defense", sylvan_ids)  # depends on Aethelgard, which is not playing
        ok, msg = self.engine.admin_toggle_realm("umbra", False)
        self.assertTrue(ok)
        self.engine.admin_toggle_realm("solaria", False)
        ok, msg = self.engine.admin_toggle_realm("val_khor", False)
        self.assertFalse(ok)  # at least two nations must remain

    def test_motion_effects_skip_nations_not_playing(self):
        """The grain tax and the embargo only touch nations at the table."""
        self.engine.admin_toggle_realm("sylvan", False)          # richest in grain
        before = {r["id"]: r for r in self.engine.get_full_state()["realms"]}
        self.engine._apply_proposal_effect({"effect_type": "tax"})
        after = {r["id"]: r for r in self.engine.get_full_state()["realms"]}
        self.assertEqual(after["sylvan"]["alchemical_grain"], before["sylvan"]["alchemical_grain"])
        self.assertEqual(after["aethelgard"]["alchemical_grain"], before["aethelgard"]["alchemical_grain"] - 10)

        self.engine.admin_toggle_realm("aquila", False)          # wealthiest overall
        self.engine._apply_proposal_effect({"effect_type": "embargo"})
        after2 = {r["id"]: r for r in self.engine.get_full_state()["realms"]}
        self.assertEqual(after2["aquila"]["civil_stability"], after["aquila"]["civil_stability"])
        self.assertEqual(after2["solaria"]["civil_stability"], after["solaria"]["civil_stability"] - 15)

    def test_new_game_forgets_previous_trades(self):
        ok, _ = self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5)
        trade = self.engine.db.get_state("trades")[0]
        self.engine.respond_trade(trade["id"], "accept", "aquila")
        self.assertTrue(self.engine.db.get_state("trade_partners"))
        self.engine.reset_simulation()
        self.assertEqual(self.engine.db.get_state("trade_partners"), {})
        self.assertEqual(self.engine.db.get_state("news_archive"), [])

    def test_trade_amounts_must_be_sane(self):
        ok, _ = self.engine.create_trade("sylvan", "aquila", "grain", -50, "silk", 5)
        self.assertFalse(ok)
        ok, _ = self.engine.create_trade("sylvan", "aquila", "grain", 0, "silk", 0)
        self.assertFalse(ok)

    def test_cordon_target_is_not_replaced_by_the_cosponsor_request(self):
        ok, _, pid = self.engine.draft_proposal("sylvan", "Watch", "Terms", "cordon", "aquila", "umbra")
        self.assertTrue(ok)
        prop = next(p for p in self.engine.db.get_state("proposals") if p["id"] == pid)
        self.assertEqual(prop["target_realm_id"], "umbra")
        self.assertEqual(prop["target_seconder_id"], "aquila")

    def test_decided_motions_never_return_to_ballot(self):
        ok, _, pid = self.engine.draft_proposal("sylvan", "Relief", "Terms", "aid")
        self.engine.support_proposal(pid, "aquila")
        ok, _ = self.engine.start_plenary_session()
        self.assertTrue(ok)
        self.engine.conclude_quick_plenary()
        meta = self.engine.db.get_state("meta", {})
        meta["phase"] = "working"
        self.engine.db.set_state("meta", meta)
        ok, msg = self.engine.start_plenary_session()
        self.assertFalse(ok)

    def test_conclude_summit_verdict_and_secret_directive_evaluation(self):
        """Verify conclude_summit computes verdict, honours, and secret directive evaluations."""
        # Set up state: Pass 2 proposals to qualify for Golden Age or Fragile Truce
        ok1, _, p1 = self.engine.draft_proposal("sylvan", "Pact 1", "Aid", "aid")
        self.engine.support_proposal(p1, "solaria")
        self.engine._apply_proposal_effect(next(p for p in self.engine.get_full_state()["proposals"] if p["id"] == p1))
        p1_obj = next(p for p in self.engine.get_full_state()["proposals"] if p["id"] == p1)
        p1_obj["status"] = "passed"
        self.engine.db.set_state("proposals", [p1_obj])

        ok2, _, p2 = self.engine.draft_proposal("solaria", "Pact 2", "Aid", "aid")
        self.engine.support_proposal(p2, "val_khor")
        p2_obj = next(p for p in self.engine.get_full_state()["proposals"] if p["id"] == p2)
        p2_obj["status"] = "passed"
        props = self.engine.get_full_state()["proposals"]
        props.append(p2_obj)
        self.engine.db.set_state("proposals", props)

        # Execute summit conclusion
        ok, msg, outcome = self.engine.conclude_summit()
        self.assertTrue(ok)
        self.assertIn("continental_verdict", outcome)
        self.assertIn("realm_evaluations", outcome)
        self.assertIn("honors", outcome)
        self.assertEqual(len(outcome["realm_evaluations"]), 6)

        # Check that state phase transitioned to summit_concluded
        state = self.engine.get_full_state()
        self.assertEqual(state["meta"]["phase"], "summit_concluded")
        self.assertIsNotNone(state["summit_outcome"])

        # Check that secret directives have been scored with narrative epilogues
        for r_eval in outcome["realm_evaluations"]:
            self.assertIn("score", r_eval)
            self.assertIn("directive_achieved", r_eval)
            self.assertIn("epilogue", r_eval)
            self.assertGreater(len(r_eval["epilogue"]), 10)

    def test_single_config_file_contains_all_workshop_data(self):
        """Verify scenario_config.json contains all simulation, faction, lore, and resolution settings."""
        cfg = load_scenario_config()
        self.assertIn("simulation_settings", cfg)
        self.assertIn("realms", cfg)
        self.assertIn("resolution_types", cfg)
        self.assertIn("events_catalog", cfg)
        self.assertGreater(len(cfg["resolution_types"]), 3)

    def _q(self, qid):
        from engine import load_quiz
        return next(q for q in load_quiz()["questions"] if q["id"] == qid)

    def _take(self, realm_id, qid=None):
        """The nation takes its next question; returns the bank entry with this draw's stake added as `stake`."""
        ok, msg, active = self.engine.quiz_start(realm_id)
        self.assertTrue(ok, msg)
        if qid:
            self.assertEqual(active["question_id"], qid)
        return dict(self._q(active["question_id"]), stake=active["stake_amount"])

    def _field(self, q):
        return {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk"}[q["reward_resource"]]

    def _stock(self, realm_id, field):
        return next(r for r in self.engine.get_full_state()["realms"] if r["id"] == realm_id)[field]

    def test_lore_quiz_correct_answer_awards_resource(self):
        """A correct answer credits the question's resource and records the claim."""
        q = self._take("sylvan")
        field = self._field(q)
        before = self._stock("sylvan", field)

        ok, msg, data = self.engine.submit_lore_quiz("sylvan", q["id"], q["correct_index"])
        self.assertTrue(ok)
        self.assertEqual(data["explanation"], q["explanation"])
        self.assertEqual(self._stock("sylvan", field), before + q["stake"])
        realm = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")
        self.assertIn(q["id"], realm["claimed_lore"])
        self.assertIsNone(realm["quiz_active"])

        ok_dup, msg_dup, _ = self.engine.submit_lore_quiz("sylvan", q["id"], q["correct_index"])
        self.assertFalse(ok_dup)
        self.assertIn("already answered", msg_dup)

    def test_lore_quiz_incorrect_answer_applies_penalty_and_lockout(self):
        """A wrong answer costs the reward's resource and amount, and locks the question for that realm only."""
        q = self._take("sylvan")
        wrong = (q["correct_index"] + 1) % 4
        field = self._field(q)
        before = self._stock("sylvan", field)

        ok, msg, data = self.engine.submit_lore_quiz("sylvan", q["id"], wrong)
        self.assertFalse(ok)
        self.assertIn(f"-{q['stake']}", msg)
        self.assertEqual(self._stock("sylvan", field), before - q["stake"])   # same resource, same amount
        realm = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")
        self.assertIn(q["id"], realm["failed_lore"])

        ok_lock, msg_lock, _ = self.engine.submit_lore_quiz("sylvan", q["id"], q["correct_index"])
        self.assertFalse(ok_lock)
        self.assertIn("Locked", msg_lock)

        # The question stays open for every other nation (shared bank, one lock per nation)
        realms = self.engine.db.get_state("realms")
        next(r for r in realms if r["id"] == "val_khor")["quiz_next"] = {"question_id": q["id"], "stake": 4}
        self.engine.db.set_state("realms", realms)
        other = self._take("val_khor", q["id"])
        ok_other, _, _ = self.engine.submit_lore_quiz("val_khor", other["id"], other["correct_index"])
        self.assertTrue(ok_other)

    def test_quiz_turn_gating_and_no_answer_leak(self):
        status = self.engine.get_quiz_status("aquila")
        self.assertEqual(status["current_turn"], 1)
        self.assertIsNone(status["active"])
        self.assertNotIn("question", json.dumps(status["next"]))          # nothing about the question until it is taken
        self.assertEqual(status["history"], [])
        # Only Turn 1 questions come up; Turn 2's stay sealed
        seen = []
        for _ in range(status["stats"]["left"]):
            q = self._take("aquila")
            seen.append(q)
            self.assertEqual(q["turn"], 1)
            self.engine.submit_lore_quiz("aquila", q["id"], q["correct_index"])
        self.assertEqual(len({q["id"] for q in seen}), len(seen))
        ok, msg, _ = self.engine.quiz_start("aquila")
        self.assertFalse(ok)
        self.assertIn("More unlock next turn", msg)
        self.assertEqual(self.engine.get_quiz_status("aquila")["unlocks_turn"], 2)
        # The open question shows its text and shuffled options, never the answer
        meta = self.engine.db.get_state("meta")
        meta["current_turn"] = 2
        self.engine.db.set_state("meta", meta)
        ok, msg, active = self.engine.quiz_start("aquila")
        self.assertTrue(ok)
        self.assertNotIn("correct_index", active)
        self.assertNotIn("explanation", active)
        self.assertEqual(sorted(o["i"] for o in active["options"]), [0, 1, 2, 3])

    def test_quiz_bank_is_well_formed(self):
        import wiki
        from engine import load_quiz
        slugs = set(wiki.load_wiki()["by_slug"])
        qs = load_quiz()["questions"]
        self.assertGreaterEqual(len(qs), 60)
        self.assertGreaterEqual(sum(1 for q in qs if q.get("tier") == "hard"), 30)
        self.assertEqual(len({q["id"] for q in qs}), len(qs))
        for q in qs:
            self.assertIn(q["article"], slugs)
            self.assertEqual(len(q["options"]), 4)
            self.assertEqual(len(set(q["options"])), 4)
            self.assertIn(q["correct_index"], range(4))
            self.assertIn(q["turn"], (1, 2, 3))

class TestFlaskEndpoints(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        from app import engine
        engine.reset_simulation()

    def test_routes_status_code_and_no_builtin_values_bug(self):
        # 1. Lobby
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"<built-in method values", resp.data)

        # 2. Realm view requires auth or param ?auth=1
        resp_no_auth = self.client.get("/realm/sylvan")
        self.assertEqual(resp_no_auth.status_code, 302)

        resp_auth = self.client.get("/realm/sylvan?auth=1")
        self.assertEqual(resp_auth.status_code, 200)
        self.assertNotIn(b"<built-in method values", resp.data)
        
        # Verify 5 Mobile Tabs exist in realm.html
        self.assertIn(b'id="view-overview"', resp_auth.data)
        self.assertIn(b'id="view-news"', resp_auth.data)
        self.assertIn(b'id="view-trades"', resp_auth.data)
        self.assertIn(b'id="view-declarations"', resp_auth.data)
        self.assertIn(b'id="view-wiki"', resp_auth.data)
        self.assertIn(b'id="view-quiz"', resp_auth.data)
        
        # Encyclopedia (reading) and Quiz (answering) live in separate tabs
        self.assertIn(b"Spireopedia Quiz", resp_auth.data)
        self.assertIn(b"The nations", resp_auth.data)
        self.assertIn(b"Royal decrees", resp_auth.data)

        # 3. Facilitator Command Deck
        resp = self.client.get("/admin")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"<built-in method values", resp.data)
        self.assertIn(b"Facilitator Command Deck", resp.data)

        # 4. Projector Overview Screen (defaults to high-visibility light theme, zero scroll)
        resp = self.client.get("/projector")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"<built-in method values", resp.data)
        self.assertIn(b"theme-light", resp.data)
        self.assertIn(b"Join QR", resp.data)

    def test_trade_and_proposal_endpoints(self):
        # Trade endpoint
        resp_trade = self.client.post("/api/trade/create", json={
            "sender_id": "sylvan",
            "receiver_id": "solaria",
            "offer_resource": "grain",
            "offer_amount": 10,
            "request_resource": "silk",
            "request_amount": 10
        })
        self.assertEqual(resp_trade.status_code, 200)
        self.assertTrue(json.loads(resp_trade.data)["success"])

        # Proposal endpoint
        resp_prop = self.client.post("/api/proposal/create", json={
            "proposer_id": "sylvan",
            "title": "Clean Energy Treaty",
            "effect_type": "aid",
            "description": "Joint development of geothermal reservoirs."
        })
        self.assertEqual(resp_prop.status_code, 200)
        self.assertTrue(json.loads(resp_prop.data)["success"])

    def test_domestic_action_api(self):
        resp = self.client.post("/api/realm/action", json={"realm_id": "sylvan", "action": "relief"})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])

    def test_pin_auth_api(self):
        resp = self.client.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])

        resp_bad = self.client.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "0000"})
        self.assertEqual(resp_bad.status_code, 401)

    def test_admin_summit_conclude_api(self):
        resp = self.client.post("/api/admin/summit/conclude")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertIn("outcome", data)
        self.assertIn("continental_verdict", data["outcome"])

    def test_projector_and_admin_concluded_ui(self):
        resp_proj = self.client.get("/projector")
        self.assertEqual(resp_proj.status_code, 200)
        self.assertIn(b"proj-concluded-stage", resp_proj.data)
        self.assertIn(b"proj-verdict-title", resp_proj.data)

        resp_admin = self.client.get("/admin")
        self.assertEqual(resp_admin.status_code, 200)
        self.assertIn(b"now-panel", resp_admin.data)
        self.assertIn(b"Sounds in the room", resp_admin.data)

        resp_realm = self.client.get("/realm/sylvan?auth=1")
        self.assertEqual(resp_realm.status_code, 200)
        self.assertIn(b"mobile-concluded-callout", resp_realm.data)
        self.assertIn(b"trade-note", resp_realm.data)
        self.assertIn(b"nav-motions-badge", resp_realm.data)
        self.assertIn(b"quiz-stage", resp_realm.data)
        self.assertIn(b"wiki-body", resp_realm.data)
        self.assertIn(b"trade-partner-chips", resp_realm.data)

    def test_projector_map_rendering(self):
        """Projector shows the parchment map of the Continent and the council of nations."""
        resp = self.client.get("/projector")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'id="realm-map"', resp.data)
        self.assertIn(b"js/map.js", resp.data)
        self.assertIn(b"projector-realms-list", resp.data)
        self.assertIn(b"btn-open-settings", resp.data)
        self.assertIn(b"proj-settings-modal", resp.data)
        self.assertNotIn(b"world3d.js", resp.data)

    def test_minute_catastrophe_simulation_and_geography_placement(self):
        """Verify scenario_config.json contains 3D geography and realistic catastrophes catalog."""
        cfg = load_scenario_config()
        self.assertIn("catastrophes_catalog", cfg)
        self.assertGreater(len(cfg["catastrophes_catalog"]), 5)
        self.assertIn("minor_events", cfg)

        # Verify all realms have 3D world_pos coordinates and hazard affinities
        for r in cfg["realms"]:
            self.assertIn("geography", r)
            self.assertIn("world_pos", r["geography"])
            self.assertEqual(len(r["geography"]["world_pos"]), 3)
            self.assertIn("hazard_affinities", r["geography"])

    def test_catastrophe_triggering_and_realistic_damage(self):
        """Verify trigger_catastrophe inflicts placement-based damage and logs epicenter."""
        from app import engine
        realms_before = engine.get_full_state()["realms"]
        val_khor_before = next(r for r in realms_before if r["id"] == "val_khor")
        cores_before = val_khor_before["aether_cores"]

        # Trigger tectonic earthquake targeting mountain realm Val-Khor
        ok, msg = engine.trigger_catastrophe("tectonic_earthquake", "val_khor")
        self.assertTrue(ok)
        self.assertIn("Val-Khor", msg)

        state = engine.get_full_state()
        val_khor_after = next(r for r in state["realms"] if r["id"] == "val_khor")
        self.assertLess(val_khor_after["aether_cores"], cores_before)

        # Check epicenter and news dispatch
        meta = state["meta"]
        self.assertIsNotNone(meta.get("latest_catastrophe"))
        self.assertEqual(meta["latest_catastrophe"]["realm_id"], "val_khor")
        self.assertEqual(len(meta["latest_catastrophe"]["epicenter"]), 3)

    def test_catastrophe_quarantine_mitigation(self):
        """Verify quarantined realms mitigate epidemic catastrophe damage."""
        from app import engine
        realms = engine.db.get_state("realms", [])
        sylvan = next(r for r in realms if r["id"] == "sylvan")
        sylvan["is_quarantined"] = True
        sylvan["public_vitality"] = 80
        engine.db.set_state("realms", realms)

        # Trigger virulent_pestilence with quarantine active
        ok, _ = engine.trigger_catastrophe("virulent_pestilence", "sylvan")
        self.assertTrue(ok)

        state = engine.get_full_state()
        sylvan_after = next(r for r in state["realms"] if r["id"] == "sylvan")
        # With 70% mitigation, vitality drop should be small (<= 6 points instead of 20)
        self.assertGreaterEqual(sylvan_after["public_vitality"], 70)

    def test_api_lore_quiz(self):
        from engine import load_quiz
        from app import engine
        engine.reset_simulation()
        listing = self.client.get("/api/quiz/sylvan").json
        self.assertTrue(listing["success"])
        self.assertIsNone(listing["active"])
        started = self.client.post("/api/quiz/start", json={"realm_id": "sylvan"}).json
        self.assertTrue(started["success"])
        qid = started["question"]["question_id"]
        self.assertNotIn("correct_index", started["question"])
        bank = {x["id"]: x for x in load_quiz()["questions"]}
        resp = self.client.post("/api/lore/quiz", json={"realm_id": "sylvan", "question_id": qid, "answer_index": bank[qid]["correct_index"]})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertIn("reward_label", data["data"])
        again = self.client.post("/api/lore/quiz", json={"realm_id": "sylvan", "question_id": qid, "answer_index": 0})
        self.assertEqual(again.status_code, 400)

    def test_js_syntax_integrity(self):
        """Ensure the scripts in static/js/ are free of JavaScript syntax errors using macOS JavaScriptCore evaluator."""
        import subprocess
        cmd = [
            "osascript", "-l", "JavaScript", "-e",
            'var window = this; var document = { getElementById: function() { return null; }, querySelectorAll: function() { return []; }, addEventListener: function() {} }; eval($.NSString.stringWithContentsOfFileEncodingError("static/js/common.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/js/battle.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/js/map.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/js/realm.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/js/projector.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/js/admin.js", $.NSUTF8StringEncoding, null).js); "OK"'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"JS Syntax Error detected: {result.stderr}")
        self.assertIn("OK", result.stdout)

    def test_military_power_resource_and_goals(self):
        """Verify military power is tracked, tradeable, governable, and tied to Aethelgard goals."""
        from app import engine
        state = engine.get_full_state()
        for r in state["realms"]:
            self.assertIn("military_power", r)
            self.assertGreater(r["military_power"], 0)
            self.assertIn("military_tier", r)

        # Test muster domestic action
        aethelgard = next(r for r in state["realms"] if r["id"] == "aethelgard")
        init_mil = aethelgard["military_power"]
        ok, msg = engine.execute_sovereign_action("aethelgard", "muster")
        self.assertTrue(ok)
        state_after = engine.get_full_state()
        aethel_after = next(r for r in state_after["realms"] if r["id"] == "aethelgard")
        self.assertEqual(aethel_after["military_power"], init_mil + 15)

        # Conclude summit evaluates military goal
        ok_conclude, _, outcome = engine.conclude_summit()
        self.assertTrue(ok_conclude)
        self.assertIn("supreme_general", outcome["honors"])
        aethel_eval = next(e for e in outcome["realm_evaluations"] if e["realm_id"] == "aethelgard")
        self.assertTrue(aethel_eval["directive_achieved"])
        self.assertIn("military", aethel_eval["stats"])

    def test_game_overview_page_endpoint(self):
        """Verify the /overview page renders successfully and aliases redirect properly."""
        client = app.test_client()
        resp = client.get("/overview")
        self.assertEqual(resp.status_code, 200)
        content = resp.get_data(as_text=True)
        self.assertIn("The Summit of Realms", content)
        self.assertIn("Sylvan Concordat", content)
        self.assertIn("Iron Val-Khor", content)
        self.assertIn("Solaris Ascendancy", content)
        self.assertIn("Umbral Enclave", content)
        self.assertIn("Aquila Maritime League", content)
        self.assertIn("Aethelgard Dominion", content)
        self.assertIn("Dynamic Voting Weights", content)
        self.assertIn("Emergency Grain Rationing", content)

        # Test aliases /rules and /guide redirect to /overview
        for alias in ["/rules", "/guide"]:
            r = client.get(alias)
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers.get("Location"), "/overview")

    def test_admin_toggle_realm_api(self):
        from app import engine
        # Toggle umbra to inactive
        resp = self.client.post("/api/admin/realm/toggle", json={"realm_id": "umbra", "active": False})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertFalse(data["active"])

        # Check full state
        st = engine.get_full_state()
        umbra = next(r for r in st["realms"] if r["id"] == "umbra")
        self.assertEqual(umbra["active"], 0)

        # Check lobby only includes active realms
        resp_lobby = self.client.get("/")
        self.assertEqual(resp_lobby.status_code, 200)
        self.assertNotIn(b'href="/realm/umbra"', resp_lobby.data)

        # Re-activate umbra
        resp_act = self.client.post("/api/admin/realm/toggle", json={"realm_id": "umbra", "active": True})
        self.assertEqual(resp_act.status_code, 200)
        st_after = engine.get_full_state()
        umbra_after = next(r for r in st_after["realms"] if r["id"] == "umbra")
        self.assertEqual(umbra_after["active"], 1)

    def test_admin_set_player_count_and_auto_scaled_missions(self):
        from app import engine
        # Set val_khor player count to 2
        resp = self.client.post("/api/admin/realm/player_count", json={"realm_id": "val_khor", "player_count": 2})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["player_count"], 2)

        # Check auto-scaled missions count
        missions = engine.get_realm_missions("val_khor")
        self.assertEqual(len(missions["secret_missions"]), 2)
        self.assertIn("Technological Hegemony", missions["secret_missions"][0]["title"])
        self.assertIn("Workers' Bread", missions["secret_missions"][1]["title"])

        # Change player count to 3
        resp3 = self.client.post("/api/admin/realm/player_count", json={"realm_id": "val_khor", "player_count": 3})
        self.assertEqual(resp3.status_code, 200)
        missions3 = engine.get_realm_missions("val_khor")
        self.assertEqual(len(missions3["secret_missions"]), 3)
        self.assertIn("Strategic Parity", missions3["secret_missions"][2]["title"])

    def test_round_crisis_triggers_and_grain_loss(self):
        """The Round buttons only announce in the famine storyline (its effects come with the turns),
        and apply each effect once in the open scenario."""
        from app import engine
        post = lambda n: self.client.post("/api/admin/crisis/round", json={"round_num": n})
        grain = lambda rid: next(r for r in engine.get_full_state()["realms"] if r["id"] == rid)["alchemical_grain"]
        try:
            self.assertTrue(json.loads(post(1).data)["success"])
            # Famine storyline, Turn 1: Round 2 is only announced, no transit loss yet; Round 3 is refused
            self.assertIn("automatically", json.loads(post(2).data)["message"])
            vk = grain("val_khor")
            engine.create_trade("sylvan", "val_khor", "grain", 15, "cores", 10)
            engine.respond_trade(engine.get_full_state()["trades"][0]["id"], "accept", "val_khor")
            self.assertEqual(grain("val_khor"), vk + 15)
            self.assertEqual(post(3).status_code, 400)

            # Open scenario: the buttons apply the rules
            engine.update_settings({"scenario": "open"})
            self.assertIn("switched on", json.loads(post(2).data)["message"])
            vk = grain("val_khor")
            engine.create_trade("sylvan", "val_khor", "grain", 15, "cores", 10)
            engine.respond_trade(engine.get_full_state()["trades"][0]["id"], "accept", "val_khor")
            self.assertEqual(grain("val_khor"), vk + 10)              # 5 Grain lost in transit

            before = grain("aethelgard")
            self.assertEqual(post(3).status_code, 200)
            self.assertEqual(grain("aethelgard"), before - 15)
            props = engine.get_full_state()["proposals"]
            self.assertTrue(any(p["effect_type"] == "emergency_food_a" for p in props))
            self.assertTrue(any(p["effect_type"] == "emergency_food_b" for p in props))
            self.assertIn("nothing was deducted", json.loads(post(3).data)["message"])
            self.assertEqual(grain("aethelgard"), before - 15)          # never twice
        finally:
            engine.db.set_state("settings", {})

    def test_famine_is_applied_once_even_if_the_button_is_pressed(self):
        from app import engine
        engine.reset_simulation()
        engine.process_end_of_turn()
        engine.process_end_of_turn()                                   # Turn 3 begins: famine applied automatically
        before = next(r for r in engine.get_full_state()["realms"] if r["id"] == "aethelgard")["alchemical_grain"]
        res = json.loads(self.client.post("/api/admin/crisis/round", json={"round_num": 3}).data)
        self.assertTrue(res["success"])
        after = next(r for r in engine.get_full_state()["realms"] if r["id"] == "aethelgard")["alchemical_grain"]
        self.assertEqual(after, before)
        self.assertEqual(sum(p["effect_type"] == "emergency_food_a" for p in engine.get_full_state()["proposals"]), 1)

    def test_continental_emergency_food_acts_resolution(self):
        from app import engine
        # Enact emergency_food_a
        prop_a = {
            "id": "act_a",
            "title": "Act A",
            "proposer_id": "sylvan",
            "effect_type": "emergency_food_a",
            "description": "Donations"
        }
        res_a = engine._apply_proposal_effect(prop_a)
        self.assertIn("Redistribution Act", res_a)

        # Enact emergency_food_b
        prop_b = {
            "id": "act_b",
            "title": "Act B",
            "proposer_id": "val_khor",
            "effect_type": "emergency_food_b",
            "description": "Reduced consumption"
        }
        res_b = engine._apply_proposal_effect(prop_b)
        self.assertIn("Industrial Agriculture Act", res_b)
        self.assertIn("+15 Grain", res_b)

    def test_3_tier_continental_outcome_and_pure_wealth(self):
        from app import engine
        engine.reset_simulation()
        # Verify wealth calculation: Grain + Cores + Silk only (excluding military)
        sylvan = next(r for r in engine.get_full_state()["realms"] if r["id"] == "sylvan")
        expected_wealth = sylvan["alchemical_grain"] + sylvan["aether_cores"] + sylvan["echo_silk"]
        self.assertEqual(sylvan["total_wealth"], expected_wealth)

        # Conclude summit
        ok, msg, outcome = engine.conclude_summit()
        self.assertTrue(ok)
        self.assertIn("continental_verdict", outcome)
        self.assertIn("continental_desc", outcome)
        self.assertIn("continental_grade", outcome)
        self.assertIn("realm_evaluations", outcome)
        self.assertIn("honors", outcome)

        # Check realm evaluations include public and secret mission results
        for r_eval in outcome["realm_evaluations"]:
            self.assertIn("public_mission_eval", r_eval)
            self.assertIn("secret_missions_eval", r_eval)
            self.assertIsInstance(r_eval["secret_missions_eval"], list)
            self.assertEqual(len(r_eval["secret_missions_eval"]), r_eval["player_count"])

    def test_admin_passcode_authentication_and_route_protection(self):
        # 1. Unauthenticated /admin request when TESTING is False renders admin_login.html
        app.config["TESTING"] = False
        try:
            resp = self.client.get("/admin")
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b"Facilitator passcode", resp.data)

            # 2. Rejection of invalid passcode
            bad_auth = self.client.post("/api/auth/admin", json={"passcode": "wrong_passcode"})
            self.assertEqual(bad_auth.status_code, 401)
            self.assertFalse(bad_auth.json["success"])

            # 3. Successful authentication sets cookie
            good_auth = self.client.post("/api/auth/admin", json={"passcode": "admin2026"})
            self.assertEqual(good_auth.status_code, 200)
            self.assertTrue(good_auth.json["success"])
            self.assertIn("auth_admin", good_auth.headers.get("Set-Cookie", ""))

            # 4. Authenticated request opens Command Deck
            # login response already set the signed auth_admin cookie on the client
            authed_resp = self.client.get("/admin")
            self.assertEqual(authed_resp.status_code, 200)
            self.assertIn(b'id="now-panel"', authed_resp.data)

            # 5. Logout clears cookie
            logout_resp = self.client.post("/api/auth/admin/logout")
            self.assertEqual(logout_resp.status_code, 200)
        finally:
            app.config["TESTING"] = True

    def test_admin_remove_realm_and_dynamic_mission_scaling(self):
        from app import engine
        engine.reset_simulation()

        # Initial state: 6 realms
        st6 = engine.get_full_state()
        self.assertEqual(len(st6["realms"]), 6)
        vk6 = next(r for r in st6["realms"] if r["id"] == "val_khor")
        sol6 = next(r for r in st6["realms"] if r["id"] == "solaria")
        self.assertIn("4 of 6 nations", vk6["public_mission"]["description"])
        self.assertIn("4 different nations", sol6["public_mission"]["description"])

        # Remove 1 realm (Umbra) -> 5 active realms
        rem1 = self.client.post("/api/admin/realm/remove", json={"realm_id": "umbra"})
        self.assertEqual(rem1.status_code, 200)
        st5 = engine.get_full_state()
        self.assertEqual(len(st5["realms"]), 5)
        vk5 = next(r for r in st5["realms"] if r["id"] == "val_khor")
        sol5 = next(r for r in st5["realms"] if r["id"] == "solaria")
        # For N=5: target_cores = round(4 * 5 / 6) = 3
        self.assertIn("3 of 5 nations", vk5["public_mission"]["description"])
        # For N=5: resolutions need votes from round(4 * 5 / 6) = 3 nations (4 of 6 scaled, like Val-Khor's target)
        self.assertIn("3 different nations", sol5["public_mission"]["description"])

        # Remove another realm (Aquila) -> 4 active realms
        rem2 = self.client.post("/api/admin/realm/remove", json={"realm_id": "aquila"})
        self.assertEqual(rem2.status_code, 200)
        st4 = engine.get_full_state()
        self.assertEqual(len(st4["realms"]), 4)
        vk4 = next(r for r in st4["realms"] if r["id"] == "val_khor")
        sol4 = next(r for r in st4["realms"] if r["id"] == "solaria")
        # For N=4: target_cores = round(4 * 4 / 6) = 3
        self.assertIn("3 of 4 nations", vk4["public_mission"]["description"])
        # For N=4: round(4 * 4 / 6) = 3
        self.assertIn("3 different nations", sol4["public_mission"]["description"])

        # Conclude summit with 4 realms and check evaluations
        ok, msg, outcome = engine.conclude_summit()
        self.assertTrue(ok)
        self.assertEqual(len(outcome["realm_evaluations"]), 4)
        for r_eval in outcome["realm_evaluations"]:
            # Epilogues and evaluations must be purely in English
            self.assertNotIn("stát", r_eval["epilogue"].lower())
            self.assertNotIn("splnila", r_eval["epilogue"].lower())

    def test_admin_set_active_realm_count(self):
        """Facilitator can explicitly set the active country count in the admin console."""
        from app import engine
        engine.reset_simulation()

        # Set to 4 active nations
        resp = self.client.post("/api/admin/realms/set_count", json={"count": 4})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])

        state = engine.get_full_state()
        active_realms = [r for r in state["realms"] if r.get("active", True)]
        inactive_realms = [r for r in state["realms"] if not r.get("active", True)]
        self.assertEqual(len(active_realms), 4)
        self.assertEqual(len(inactive_realms), 2)
        self.assertEqual([r["id"] for r in active_realms], ["sylvan", "val_khor", "solaria", "umbra"])

        # Check dynamic mission rescaling for N=4
        vk = next(r for r in active_realms if r["id"] == "val_khor")
        self.assertIn("3 of 4 nations", vk["public_mission"]["description"])

        # Set to 3 active nations
        resp3 = self.client.post("/api/admin/realms/set_count", json={"count": 3})
        self.assertEqual(resp3.status_code, 200)
        state3 = engine.get_full_state()
        active3 = [r for r in state3["realms"] if r.get("active", True)]
        self.assertEqual(len(active3), 3)
        self.assertEqual([r["id"] for r in active3], ["sylvan", "val_khor", "solaria"])

        # Set back to 6 active nations
        resp6 = self.client.post("/api/admin/realms/set_count", json={"count": 6})
        self.assertEqual(resp6.status_code, 200)
        state6 = engine.get_full_state()
        active6 = [r for r in state6["realms"] if r.get("active", True)]
        self.assertEqual(len(active6), 6)

    def test_capacity_enforcement_and_sessions(self):
        """Verify connected seat counts, capacity locking (403), re-entry for existing sessions, and logout."""
        from app import engine
        engine.reset_simulation()
        engine.clear_realm_sessions()

        # Set sylvan capacity to 2 delegates
        engine.admin_set_player_count("sylvan", 2)

        # Delegate 1 joins
        client1 = app.test_client()
        client1.set_cookie("summit_session_id", "sess-sylvan-1")
        r1 = client1.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
        self.assertEqual(r1.status_code, 200)

        st = engine.get_full_state()
        sylvan = next(r for r in st["realms"] if r["id"] == "sylvan")
        self.assertEqual(sylvan["connected_players"], 1)
        self.assertFalse(sylvan["is_capacity_full"])

        # Delegate 2 joins
        client2 = app.test_client()
        client2.set_cookie("summit_session_id", "sess-sylvan-2")
        r2 = client2.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
        self.assertEqual(r2.status_code, 200)

        st = engine.get_full_state()
        sylvan = next(r for r in st["realms"] if r["id"] == "sylvan")
        self.assertEqual(sylvan["connected_players"], 2)
        self.assertTrue(sylvan["is_capacity_full"])

        # Delegate 3 attempts to join -> 403 Forbidden with is_full: True
        client3 = app.test_client()
        client3.set_cookie("summit_session_id", "sess-sylvan-3")
        r3 = client3.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
        self.assertEqual(r3.status_code, 403)
        data3 = json.loads(r3.data)
        self.assertFalse(data3["success"])
        self.assertTrue(data3.get("is_full"))
        self.assertIn("seats of sylvan concordat are taken", data3["message"].lower())

        # Existing Delegate 1 re-authenticates -> allowed without 403
        r1_reentry = client1.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
        self.assertEqual(r1_reentry.status_code, 200)

        # Delegate 1 logs out -> frees seat
        r1_logout = client1.post("/api/auth/realm/logout", json={"realm_id": "sylvan"})
        self.assertEqual(r1_logout.status_code, 200)

        st = engine.get_full_state()
        sylvan = next(r for r in st["realms"] if r["id"] == "sylvan")
        self.assertEqual(sylvan["connected_players"], 1)
        self.assertFalse(sylvan["is_capacity_full"])

        # Now Delegate 3 can join successfully
        r3_retry = client3.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
        self.assertEqual(r3_retry.status_code, 200)

        # Facilitator clears sessions for sylvan
        clr_resp = self.client.post("/api/admin/realm/clear_sessions", json={"realm_id": "sylvan"})
        self.assertEqual(clr_resp.status_code, 200)
        st = engine.get_full_state()
        sylvan = next(r for r in st["realms"] if r["id"] == "sylvan")
        self.assertEqual(sylvan["connected_players"], 0)
        self.assertFalse(sylvan["is_capacity_full"])

    def test_lobby_shows_capacity_and_seats(self):
        """Lobby shows connected seat ratio and capacity badge."""
        from app import engine
        engine.reset_simulation()
        engine.clear_realm_sessions()

        # Initial lobby
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("seats", html)

class TestRulesAreKept(unittest.TestCase):
    """Regressions from the code review: rejected motions, lost sounds, the last turn, restored saves."""

    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        self.engine = SummitEngine(Database(TEST_DB))

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def _realm(self, rid):
        return next(r for r in self.engine.db.get_state("realms") if r["id"] == rid)

    def _vote_through_grand_plenary(self, choice):
        e = self.engine
        while e.db.get_state("meta")["phase"] in ("grand_plenary_discussion", "grand_plenary_voting"):
            e.start_grand_motion_vote()
            meta = e.db.get_state("meta")
            pid = meta["plenary_docket"][meta["current_motion_index"]]
            for r in e.db.get_state("realms"):
                e.cast_plenary_vote(r["id"], pid, choice)
            e.advance_grand_plenary_next()

    def test_a_rejected_motion_changes_nothing_in_the_grand_plenary(self):
        e = self.engine
        e.process_end_of_turn()
        e.process_end_of_turn()
        ok, _, pid = e.draft_proposal("sylvan", "Sanction", "x", "embargo", params={"target": "aethelgard", "resource": "stability", "amount": 30})
        self.assertTrue(ok)
        e.support_proposal(pid, "umbra")
        before = {r["id"]: (r["civil_stability"], r["aether_cores"], r["alchemical_grain"]) for r in e.db.get_state("realms")}
        e.start_plenary_session()
        self._vote_through_grand_plenary("oppose")
        prop = next(p for p in e.db.get_state("proposals") if p["id"] == pid)
        self.assertEqual(prop["status"], "rejected")
        self.assertIsNone(prop.get("result_text"))
        after = {r["id"]: (r["civil_stability"], r["aether_cores"], r["alchemical_grain"]) for r in e.db.get_state("realms")}
        self.assertEqual(before, after)                      # neither the sanction nor the rejected Food Acts took effect

    def test_a_passed_motion_still_works_in_the_grand_plenary(self):
        e = self.engine
        e.process_end_of_turn()
        e.process_end_of_turn()
        ok, _, pid = e.draft_proposal("sylvan", "Sanction", "x", "embargo", params={"target": "aethelgard", "resource": "stability", "amount": 30})
        e.support_proposal(pid, "umbra")
        stability = self._realm("aethelgard")["civil_stability"]
        cores = self._realm("sylvan")["aether_cores"]
        e.start_plenary_session()
        self._vote_through_grand_plenary("support")
        self.assertEqual(self._realm("aethelgard")["civil_stability"], stability - 30)
        self.assertEqual(self._realm("sylvan")["aether_cores"], cores - 10)    # Food Act B passed as well

    def test_new_turns_can_be_heard_and_their_news_carry_the_new_turn(self):
        e = self.engine
        seq = e.db.get_state("meta")["audio_cue"]["seq"]
        e.process_end_of_turn()
        cue = e.db.get_state("meta")["audio_cue"]
        self.assertGreater(cue["seq"], seq)
        self.assertEqual(cue["type"], "alert")
        incident = next(n for n in e.db.get_state("news_feed") if "BORDER INCIDENT" in n["headline"])
        self.assertTrue(incident["time_str"].startswith("Turn 2"), incident["time_str"])
        e.process_end_of_turn()
        meta = e.db.get_state("meta")
        self.assertEqual(meta["audio_cue"]["type"], "siren")
        self.assertTrue(meta["famine_applied"])

    def test_every_sound_the_engine_asks_for_can_be_played(self):
        common = open("static/js/common.js", encoding="utf-8").read()
        for kind in ("gong", "turn", "chime", "trade", "alert", "siren", "battle"):
            self.assertIn(f"{kind}:", common, kind)
        self.assertIn("playSiren()", common)

    def test_only_motions_on_the_ballot_can_be_voted_on(self):
        e = self.engine
        ok, _, on_ballot = e.draft_proposal("sylvan", "A", "x", "aid")
        e.support_proposal(on_ballot, "umbra")
        ok, _, not_on_ballot = e.draft_proposal("sylvan", "B", "x", "aid")
        e.start_plenary_session()
        self.assertTrue(e.cast_plenary_vote("umbra", on_ballot, "support")[0])
        self.assertFalse(e.cast_plenary_vote("umbra", not_on_ballot, "support")[0])
        self.assertEqual(next(p for p in e.db.get_state("proposals") if p["id"] == not_on_ballot)["votes"], {})

    def test_catalogue_events_leave_absent_nations_alone(self):
        e = self.engine
        e.admin_toggle_realm("sylvan", False)
        before = {k: v for k, v in self._realm("sylvan").items() if k in ("alchemical_grain", "aether_cores", "echo_silk", "public_vitality", "diplomatic_standing", "civil_stability")}
        for event in e.get_catalog_events():
            e.trigger_catalog_event(event["id"])
            self.assertNotIn("Sylvan", e.db.get_state("news_feed")[0]["detail"].split("Impacted Delegations:")[-1], event["id"])
        self.assertEqual(before, {k: self._realm("sylvan")[k] for k in before})

    def test_a_save_restored_during_a_vote_keeps_the_time_it_had_left(self):
        e = self.engine
        ok, _, pid = e.draft_proposal("sylvan", "A", "x", "aid")
        e.support_proposal(pid, "umbra")
        e.start_plenary_session()
        snapshot = e.db.dump_all()
        snapshot["meta"]["vote_timer_end"] = time.time() - 600     # saved ten minutes ago
        snapshot["meta"]["vote_timer_remaining"] = 120
        self.assertTrue(e.restore_snapshot(snapshot)[0])
        e.get_full_state()
        meta = e.db.get_state("meta")
        self.assertEqual(meta["phase"], "plenary_quick")           # no jump past the vote
        self.assertIsNone(meta["vote_timer_end"])                  # the clock waits for the facilitator...
        self.assertEqual(meta["vote_timer_remaining"], 120)
        e.admin_clock("resume")                                    # ...and goes on with the time it had
        self.assertAlmostEqual(e.db.get_state("meta")["vote_timer_end"] - time.time(), 120, delta=3)

    def test_a_save_restored_during_a_debate_keeps_the_time_it_had_left(self):
        e = self.engine
        e.process_end_of_turn()
        e.process_end_of_turn()
        e.start_plenary_session()
        snapshot = e.db.dump_all()
        snapshot["meta"]["discussion_timer_end"] = time.time() - 600
        snapshot["meta"]["discussion_timer_remaining"] = 90
        e.restore_snapshot(snapshot)
        e.get_full_state()
        meta = e.db.get_state("meta")
        self.assertEqual(meta["phase"], "grand_plenary_discussion")
        self.assertFalse(meta["is_discussion_timer_running"])
        self.assertEqual(meta["discussion_timer_remaining"], 90)
        e.admin_clock("resume")
        self.assertAlmostEqual(e.db.get_state("meta")["discussion_timer_end"] - time.time(), 90, delta=3)

    def test_a_quiz_question_open_in_a_restored_save_is_not_charged(self):
        e = self.engine
        ok, _, question = e.quiz_start("sylvan")
        snapshot = e.db.dump_all()
        stake = next(r for r in snapshot["realms"] if r["id"] == "sylvan")["quiz_active"]["stake"]
        for r in snapshot["realms"]:
            if r.get("quiz_active"):
                r["quiz_active"]["deadline"] = time.time() - 600
        e.restore_snapshot(snapshot)
        e.get_full_state()
        sylvan = self._realm("sylvan")
        self.assertEqual(sylvan.get("failed_lore", []), [])
        self.assertEqual(sylvan["quiz_next"], {"question_id": question["question_id"], "stake": stake})

    def test_removing_a_nation_removes_its_trades(self):
        e = self.engine
        e.create_trade("umbra", "sylvan", "cores", 5, "grain", 5)
        e.create_trade("aquila", "sylvan", "silk", 5, "grain", 5)
        e.admin_remove_realm("umbra")
        self.assertEqual([t["sender_id"] for t in e.db.get_state("trades")], ["aquila"])


class TestApiIsKept(unittest.TestCase):
    """Regressions through the real API with logins enforced."""

    def setUp(self):
        from app import engine, _failed_logins
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()
        engine.clear_realm_sessions(None)
        _failed_logins.clear()
        app.config["TESTING"] = False
        self.phone = app.test_client()
        pin = next(r for r in engine.db.get_state("realms") if r["id"] == "umbra")["pin"]
        self.assertTrue(self.phone.post("/api/auth/realm", json={"realm_id": "umbra", "pin": pin}).json["success"])

    def tearDown(self):
        app.config["TESTING"] = True

    def _grain(self, rid):
        return next(r for r in self.engine.db.get_state("realms") if r["id"] == rid)["alchemical_grain"]

    def test_a_phone_cannot_act_in_another_nations_name(self):
        attempts = [
            ("/api/trade/create", {"realm_id": "umbra", "sender_id": "sylvan", "receiver_id": "umbra", "offer_resource": "grain",
                                   "offer_amount": 50, "request_resource": "silk", "request_amount": 0}),
            ("/api/proposal/create", {"realm_id": "umbra", "proposer_id": "sylvan", "title": "x", "description": "y", "effect_type": "aid"}),
            ("/api/proposal/abc/support", {"realm_id": "umbra", "supporter_id": "sylvan"}),
        ]
        for path, body in attempts:
            self.assertEqual(self.phone.post(path, json=body).status_code, 401, path)
        self.assertEqual(self.engine.db.get_state("trades"), [])
        self.assertEqual(self.engine.db.get_state("proposals"), [])

    def test_a_phone_can_still_act_for_itself(self):
        res = self.phone.post("/api/trade/create", json={"sender_id": "umbra", "receiver_id": "sylvan", "offer_resource": "cores",
                                                         "offer_amount": 5, "request_resource": "grain", "request_amount": 5})
        self.assertEqual(res.status_code, 200)

    def test_a_request_with_a_strange_body_is_refused_not_a_crash(self):
        self.assertEqual(self.phone.post("/api/realm/action", json=["umbra"]).status_code, 401)
        self.assertEqual(self.phone.post("/api/realm/action", json={"realm_id": ["umbra"], "action": "gala"}).status_code, 401)

    def test_a_blank_trade_amount_gets_a_message(self):
        res = self.phone.post("/api/trade/create", json={"sender_id": "umbra", "receiver_id": "sylvan", "offer_resource": "grain",
                                                         "offer_amount": None, "request_resource": "silk", "request_amount": 5})
        self.assertEqual(res.status_code, 400)
        self.assertIn("whole numbers", res.json["message"])

    def test_trade_offers_stay_between_the_two_nations(self):
        self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5, "our secret")
        self.engine.create_trade("sylvan", "umbra", "grain", 5, "silk", 5, "for you")
        visible = self.phone.get("/api/state").json["trades"]
        self.assertEqual([t["note"] for t in visible], ["for you"])
        self.assertEqual(app.test_client().get("/api/state").json["trades"], [])

    def test_everyone_can_see_that_two_nations_traded_but_not_what(self):
        self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5, "our secret")
        trade = self.engine.db.get_state("trades")[0]
        self.engine.respond_trade(trade["id"], "accept", "aquila")
        seen = app.test_client().get("/api/state").json["trades"][0]          # the projector draws the route from this
        self.assertEqual((seen["sender_id"], seen["receiver_id"], seen["status"]), ("sylvan", "aquila", "accepted"))
        for private in ("note", "offer_amount", "request_amount", "offer_resource", "request_resource"):
            self.assertNotIn(private, seen)

    def test_the_crisis_catalogue_is_for_the_facilitators(self):
        self.assertEqual(self.phone.get("/api/events").status_code, 401)

    def test_nobody_sees_another_nations_next_quiz_question(self):
        self.engine.get_quiz_status("sylvan")
        realms = {r["id"]: r for r in self.phone.get("/api/state").json["realms"]}
        self.assertNotIn("quiz_next", realms["sylvan"])

    def test_the_last_turn_cannot_be_advanced_past(self):
        app.config["TESTING"] = True
        client = app.test_client()
        self.assertTrue(client.post("/api/admin/turn/next", json={}).json["success"])
        self.assertTrue(client.post("/api/admin/turn/next", json={}).json["success"])
        res = client.post("/api/admin/turn/next", json={})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.engine.db.get_state("meta")["current_turn"], 3)
        self.engine.conclude_summit()
        self.assertEqual(client.post("/api/admin/turn/next", json={}).status_code, 400)      # a finished game stays finished
        self.assertEqual(self.engine.db.get_state("meta")["phase"], "summit_concluded")


class TestDifficultySettings(unittest.TestCase):
    """Difficulty has two settings: the game's complexity and the scenario."""

    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        self.engine = SummitEngine(Database(TEST_DB))
        self.cfg = load_scenario_config()

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_the_old_third_setting_is_gone(self):
        self.assertNotIn("difficulties", self.cfg)
        self.assertNotIn("difficulty", self.cfg["game_settings_defaults"])
        self.assertNotIn("difficulty", self.engine.settings())

    def test_the_full_game_is_the_default_and_the_famine_numbers_are_unchanged(self):
        s = self.engine.settings()
        self.assertEqual((s["complexity"], s["scenario"]), ("full", "famine"))
        self.assertEqual((s["grain_consumption"], s["positive_share"], s["minor_events_per_turn"], s["large_events_per_turn"]), (20, 0.5, 6, 0))
        self.assertTrue(s["rules"]["quiz"] and s["rules"]["war"] and s["rules"]["free_motions"] and s["rules"]["grand_plenary"])
        self.assertFalse(s["rules"]["one_secret_mission"] or s["rules"]["hide_vitality"] or s["rules"]["live_hints"])
        self.assertEqual(s["rules"]["starting_bonus"], {})

    def test_the_full_game_starts_from_the_facilitator_notes(self):
        expected = {"sylvan": (100, 25, 30), "val_khor": (30, 80, 25), "solaria": (50, 40, 75), "umbra": (40, 70, 30),
                    "aquila": (50, 40, 80), "aethelgard": (60, 50, 25)}
        for r in self.engine.db.get_state("realms"):
            self.assertEqual((r["alchemical_grain"], r["aether_cores"], r["echo_silk"]), expected[r["id"]], r["id"])

    def test_scenarios_are_ranked_and_bring_their_own_numbers(self):
        levels = {k: v["level"] for k, v in self.cfg["scenarios"].items()}
        self.assertEqual(levels, {"open": 1, "famine": 2, "armageddon": 3})
        for key, sc in self.cfg["scenarios"].items():
            self.engine.db.set_state("settings", {})
            self.engine.update_settings({"scenario": key})
            s = self.engine.settings()
            self.assertEqual(s["grain_consumption"], sc["suggested"]["grain_consumption"], key)
            self.assertEqual(s["good_news_percent"], sc["suggested"]["good_news_percent"], key)

    def test_typed_numbers_beat_the_scenario_until_the_scenario_changes(self):
        e = self.engine
        e.update_settings({"grain_consumption": 25, "good_news_percent": 35})
        self.assertEqual(e.settings()["grain_consumption"], 25)
        e.update_settings({"scenario": "open"})                       # nothing typed along: the new scenario's own numbers
        self.assertEqual(e.settings()["grain_consumption"], 15)
        e.update_settings({"scenario": "famine", "grain_consumption": 30})
        self.assertEqual(e.settings()["grain_consumption"], 30)
        realms = e.db.get_state("realms")
        before = next(r for r in realms if r["id"] == "sylvan")["alchemical_grain"]
        e.process_end_of_turn()
        self.assertEqual(next(r for r in e.db.get_state("realms") if r["id"] == "sylvan")["alchemical_grain"], before - 30)

    def test_the_new_summit_news_names_both_settings(self):
        self.engine.update_settings({"complexity": "simplified", "scenario": "armageddon"})
        self.engine.start_new_summit()
        headline = next(n for n in self.engine.db.get_state("news_feed") if n["headline"] == "A NEW SUMMIT IS PREPARED")
        self.assertIn("Simplified", headline["detail"])
        self.assertIn("Armageddon", headline["detail"])


class TestSimplifiedGame(unittest.TestCase):
    """The reduced-complexity game: ready-made motions, no quiz, no war, one secret mission."""

    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        self.engine = SummitEngine(Database(TEST_DB))
        self.engine.db.set_state("settings", {"complexity": "simplified"})
        self.engine.reset_simulation()
        self.cfg = load_scenario_config()
        self.bonus = self.cfg["complexities"]["simplified"]["starting_bonus"]

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def _realm(self, rid):
        return next(r for r in self.engine.db.get_state("realms") if r["id"] == rid)

    def _table_and_pass(self, proposer, motion, amount=None, co_sponsor=None):
        e = self.engine
        params = {"amount": amount} if amount is not None else None
        ok, msg, pid = e.draft_proposal(proposer, "", "", motion, params=params)
        self.assertTrue(ok, msg)
        co_sponsor = co_sponsor or next(r["id"] for r in e.db.get_state("realms") if r["id"] != proposer)
        self.assertTrue(e.support_proposal(pid, co_sponsor)[0])
        self.assertTrue(e.start_plenary_session()[0])
        for r in e.db.get_state("realms"):
            e.cast_plenary_vote(r["id"], pid, "support")
        self.assertTrue(e.conclude_quick_plenary()[0])
        # back to a working session for the next motion
        meta = e.db.get_state("meta")
        meta["phase"] = "working"
        e.db.set_state("meta", meta)
        return next(p for p in e.db.get_state("proposals") if p["id"] == pid)

    # ---- resources instead of the quiz
    def test_nations_start_with_what_the_quiz_would_have_paid(self):
        for raw in self.cfg["realms"]:
            r = self._realm(raw["id"])
            for res, field in (("grain", "alchemical_grain"), ("cores", "aether_cores"), ("silk", "echo_silk")):
                self.assertEqual(r[field], raw[field] + self.bonus[res], (raw["id"], res))
            self.assertEqual(r["military_power"], raw["military_power"])

    def test_the_bonus_keeps_the_gaps_between_nations(self):
        grain = {r["id"]: r["alchemical_grain"] for r in self.engine.db.get_state("realms")}
        self.assertEqual(grain["sylvan"] - grain["val_khor"], 70)            # the breadbasket is still the breadbasket

    def test_all_twelve_missions_can_be_met_on_the_food_there_is(self):
        """Grain left after the meals, the famine and Food Act B must cover what the secret missions ask for."""
        realms = self.engine.db.get_state("realms")
        total = sum(r["alchemical_grain"] for r in realms)
        eat = self.engine.settings()["grain_consumption"]
        meals = sum(3 * (round(eat * 0.75) if r.get("tech_efficiency_unlocked") else eat) for r in realms)
        left = total - 10 - meals - 15 * len(realms) + 15 * len(realms)        # 10: Sylvan musters once for its mission
        required = 30 + 35 + 4                                                 # Val-Khor, Aethelgard, and something for the other four
        self.assertGreaterEqual(left, required + 20, "too little room for bad news and human mistakes")

    def test_changing_complexity_before_play_swaps_the_bonus_without_a_new_game(self):
        e = self.engine
        game = e.db.get_state("meta")["game_id"]
        self.assertEqual(e.update_settings({"complexity": "full"}), (True, "Settings saved."))
        self.assertEqual(e.db.get_state("meta")["game_id"], game)
        self.assertEqual(self._realm("sylvan")["alchemical_grain"], 100)
        self.assertFalse(e.rules()["live_hints"])
        e.update_settings({"complexity": "simplified"})
        self.assertEqual(self._realm("sylvan")["alchemical_grain"], 100 + self.bonus["grain"])
        self.assertTrue(e.rules()["live_hints"])

    def test_a_running_game_keeps_its_complexity_until_a_new_summit(self):
        e = self.engine
        e.db.set_state("settings", {})
        e.reset_simulation()
        e.admin_control_timer("start")
        ok, msg = e.update_settings({"complexity": "simplified"})
        self.assertTrue(ok)
        self.assertIn("next new summit", msg)
        self.assertEqual(e.rules()["id"], "full")
        self.assertEqual(self._realm("sylvan")["alchemical_grain"], 100)
        self.assertEqual(e.settings()["complexity"], "simplified")           # chosen for the next game
        e.start_new_summit()
        self.assertEqual(e.rules()["id"], "simplified")
        self.assertEqual(self._realm("sylvan")["alchemical_grain"], 100 + self.bonus["grain"])

    def test_a_save_from_before_complexity_existed_plays_the_full_game(self):
        meta = self.engine.db.get_state("meta")
        del meta["complexity"]
        self.engine.db.set_state("meta", meta)
        self.assertEqual(self.engine.rules()["id"], "full")

    # ---- the quiz
    def test_there_is_no_quiz(self):
        e = self.engine
        self.assertFalse(e.quiz_start("sylvan")[0])
        self.assertFalse(e.submit_lore_quiz("sylvan", "q01", 0)[0])
        self.assertFalse(e.get_quiz_status("sylvan")["enabled"])
        self.assertIsNone(self._realm("sylvan")["quiz_active"])

    # ---- war
    def test_there_is_no_war(self):
        e = self.engine
        e.process_end_of_turn()
        self.assertFalse(e.settings()["attacks_enabled"])
        ok, msg, _ = e.declare_attack("aethelgard", "sylvan", "siege")
        self.assertFalse(ok)
        self.assertIn("switched off", msg)

    def test_the_war_setting_is_kept_for_the_next_full_game(self):
        e = self.engine
        e.update_settings({"attacks_enabled": True})
        self.assertFalse(e.settings()["attacks_enabled"])
        self.assertTrue(e.settings(as_chosen=True)["attacks_enabled"])

    # ---- motions
    def test_only_ready_made_motions_can_be_tabled(self):
        e = self.engine
        for full_game_motion in ("tax", "pact", "open", "gm_question", "aid", "cordon"):
            self.assertFalse(e.draft_proposal("sylvan", "Mine", "Mine", full_game_motion)[0], full_game_motion)
        self.assertEqual(e.db.get_state("proposals"), [])

    def test_a_player_cannot_change_the_wording_or_address_a_motion(self):
        e = self.engine
        ok, _, pid = e.draft_proposal("sylvan", "My own title", "My own terms", "relief_mission", target_seconder_id="umbra", target_realm_id="umbra")
        self.assertTrue(ok)
        prop = next(p for p in e.db.get_state("proposals") if p["id"] == pid)
        self.assertEqual(prop["title"], "Relief Mission led by Sylvan Concordat")
        self.assertNotIn("My own", prop["description"])
        self.assertIsNone(prop["target_seconder_id"])
        self.assertIsNone(prop["target_realm_id"])

    def test_the_amount_is_the_one_thing_that_can_be_chosen(self):
        e = self.engine
        spec = next(m for m in self.cfg["simple_motions"] if m["id"] == "share_grain")["amount"]
        ok, _, pid = e.draft_proposal("sylvan", "", "", "share_grain", params={"amount": spec["max"], "resource": "silk", "above": 1, "lines": []})
        self.assertTrue(ok)
        prop = next(p for p in e.db.get_state("proposals") if p["id"] == pid)
        self.assertEqual(prop["effects"][0]["give"], spec["max"])
        self.assertEqual((prop["effects"][0]["resource"], prop["effects"][0]["above"]), ("grain", 50))   # the rest cannot be changed
        self.assertIn(str(spec["max"]), prop["title"])
        self.assertIn(str(spec["max"]), prop["effect_text"][0])
        for bad in (spec["max"] + 1, spec["min"] - 1, "lots", None):
            self.assertFalse(e.draft_proposal("sylvan", "", "", "share_grain", params={"amount": bad})[0], bad)

    def test_a_motion_with_no_amount_has_nothing_to_choose(self):
        e = self.engine
        prop_id = e.draft_proposal("sylvan", "", "", "relief_mission", params={"amount": 999})[2]
        prop = next(p for p in e.db.get_state("proposals") if p["id"] == prop_id)
        self.assertEqual(prop["effects"][0]["amount"], 10)

    def test_every_motion_is_automatic_and_says_what_it_does(self):
        e = self.engine
        self.assertTrue(self.cfg["simple_motions"])
        for m in self.cfg["simple_motions"]:
            ok, msg, sentences = e.preview_proposal("umbra", m["id"], {"amount": (m.get("amount") or {}).get("default")})
            self.assertTrue(ok, msg)
            self.assertEqual(len(sentences), 1)
            self.assertNotIn("{", sentences[0], m["id"])
            self.assertTrue(m["lines"], m["id"])
            self.assertFalse(m.get("needs_target"), m["id"])

    def test_share_the_grain_moves_only_what_exists(self):
        e = self.engine
        realms = e.db.get_state("realms")
        for r in realms:
            r["alchemical_grain"] = {"sylvan": 100, "aethelgard": 60, "umbra": 10, "val_khor": 20}.get(r["id"], 30)
        e.db.set_state("realms", realms)
        total = sum(r["alchemical_grain"] for r in realms)
        self._table_and_pass("umbra", "share_grain", 10)
        self.assertEqual(sum(r["alchemical_grain"] for r in e.db.get_state("realms")), total)
        self.assertEqual(self._realm("sylvan")["alchemical_grain"], 90)
        self.assertEqual(self._realm("aethelgard")["alchemical_grain"], 50)
        self.assertEqual(self._realm("umbra")["alchemical_grain"], 20)
        self.assertEqual(self._realm("val_khor")["alchemical_grain"], 30)
        self.assertEqual(self._realm("aquila")["alchemical_grain"], 30)      # between the limits: neither gives nor receives

    def test_the_modernisation_fund_helps_the_nations_behind(self):
        before = {r["id"]: r["aether_cores"] for r in self.engine.db.get_state("realms")}
        total = sum(before.values())
        self._table_and_pass("val_khor", "modernisation_fund", 10)
        after = {r["id"]: r["aether_cores"] for r in self.engine.db.get_state("realms")}
        self.assertEqual(sum(after.values()), total)
        self.assertEqual(after["val_khor"], before["val_khor"] - 10)
        self.assertEqual(after["umbra"], before["umbra"] - 10)
        self.assertGreater(after["sylvan"], before["sylvan"])

    def test_a_plea_for_aid_brings_grain_from_every_other_nation(self):
        before = {r["id"]: r["alchemical_grain"] for r in self.engine.db.get_state("realms")}
        prop = self._table_and_pass("umbra", "plea_for_aid", 5)
        after = {r["id"]: r["alchemical_grain"] for r in self.engine.db.get_state("realms")}
        self.assertEqual(after["umbra"], before["umbra"] + 25)
        self.assertEqual(after["sylvan"], before["sylvan"] - 5)
        self.assertIn("Umbral Enclave", prop["effect_text"][0])
        self.assertIn("Umbral Enclave +25 Grain", prop["result_text"])

    def test_the_richest_nation_can_be_sanctioned(self):
        richest = max(self.engine.db.get_state("realms"), key=lambda r: r["total_wealth"])
        before = richest["civil_stability"]
        self._table_and_pass("umbra", "sanction_richest", 15)
        self.assertEqual(self._realm(richest["id"])["civil_stability"], before - 15)

    def test_the_motions_that_reward_the_nation_itself(self):
        standing, stability = self._realm("umbra")["diplomatic_standing"], self._realm("umbra")["civil_stability"]
        self._table_and_pass("umbra", "relief_mission")
        self.assertEqual(self._realm("umbra")["diplomatic_standing"], standing + 10)
        self._table_and_pass("umbra", "guard_borders")
        self.assertEqual(self._realm("umbra")["civil_stability"], stability + 10)
        self.assertTrue(self._realm("umbra")["is_quarantined"])

    def test_no_motion_waits_for_the_game_masters(self):
        prop = self._table_and_pass("umbra", "relief_mission")
        self.assertFalse(prop.get("awaiting_gm"))
        for m in self.cfg["simple_motions"]:
            self.assertNotIn(m.get("builder"), ("open",), m["id"])

    def test_the_screens_only_offer_ready_made_motions(self):
        types = {t["id"]: t for t in self.engine.get_full_state()["resolution_types"]}
        selectable = {k for k, t in types.items() if t.get("player_selectable", True)}
        self.assertEqual(selectable, {m["id"] for m in self.cfg["simple_motions"]})
        self.assertIn("emergency_food_a", types)                            # the Food Acts keep their name and icon on the ballot

    # ---- the Assembly
    def test_turn_three_is_one_vote_like_the_others(self):
        e = self.engine
        e.process_end_of_turn()
        e.process_end_of_turn()
        self.assertTrue(e.start_plenary_session()[0])
        meta = e.db.get_state("meta")
        self.assertEqual(meta["phase"], "plenary_quick")
        acts = [p["id"] for p in e.db.get_state("proposals") if p["effect_type"].startswith("emergency_food")]
        self.assertEqual(len(acts), 2)
        self.assertEqual(sorted(meta["plenary_docket"]), sorted(acts))
        for pid in acts:
            self.assertTrue(e.cast_plenary_vote("umbra", pid, "support")[0])

    def test_when_the_last_vote_closes_the_summit_ends_by_itself(self):
        e = self.engine
        e.process_end_of_turn()
        e.process_end_of_turn()
        e.start_plenary_session()
        meta = e.db.get_state("meta")
        for pid in meta["plenary_docket"]:
            for r in e.db.get_state("realms"):
                e.cast_plenary_vote(r["id"], pid, "support")
        meta = e.db.get_state("meta")
        meta["vote_timer_end"] = time.time() - 1
        e.db.set_state("meta", meta)
        e.get_full_state()
        self.assertEqual(e.db.get_state("meta")["phase"], "summit_concluded")
        self.assertIsNotNone(e.db.get_state("summit_outcome"))
        self.assertEqual(next(p for p in e.db.get_state("proposals") if p["effect_type"] == "emergency_food_b")["status"], "passed")

    def test_the_full_game_still_has_its_grand_plenary(self):
        e = self.engine
        e.db.set_state("settings", {})
        e.reset_simulation()
        e.process_end_of_turn()
        e.process_end_of_turn()
        e.start_plenary_session()
        self.assertEqual(e.db.get_state("meta")["phase"], "grand_plenary_discussion")

    # ---- missions
    def test_each_nation_has_one_secret_mission_about_itself(self):
        for r in self.engine.db.get_state("realms"):
            secrets = r["active_secret_missions"]
            self.assertEqual(len(secrets), 1, r["id"])
            self.assertEqual(secrets[0]["id"], r["simple_secret"])

    def test_each_nation_keeps_a_secret_mission_with_fewer_nations(self):
        for absent in ("sylvan", "val_khor", "solaria", "umbra", "aquila", "aethelgard"):
            self.engine.db.set_state("settings", {"complexity": "simplified"})
            self.engine.reset_simulation()
            self.engine.admin_toggle_realm(absent, False)
            for r in self.engine.db.get_state("realms"):
                if r.get("active", True):
                    self.assertEqual(len(r["active_secret_missions"]), 1, (absent, r["id"]))

    def test_sylvan_plays_the_stand_in_without_aethelgard(self):
        self.engine.admin_toggle_realm("aethelgard", False)
        self.assertEqual(self._realm("sylvan")["active_secret_missions"][0]["id"], "sylvan_defense_home")

    def test_the_delegation_size_does_not_add_missions(self):
        self.engine.admin_set_player_count("solaria", 4)
        self.assertEqual(len(self._realm("solaria")["active_secret_missions"]), 1)

    def test_a_perfect_game_meets_every_mission(self):
        """Not luck: a group that plays well can meet all twelve missions and keep the continent stable."""
        e = self.engine
        e.update_settings({"minor_events_per_turn": 0})

        def trade(a, b, give, n, get, m):
            self.assertTrue(e.create_trade(a, b, give, n, get, m)[0], (a, b))
            self.assertTrue(e.respond_trade(e.db.get_state("trades")[0]["id"], "accept", b)[0], (a, b))

        def assembly(*motions):
            for proposer, motion, co in motions:
                ok, msg, pid = e.draft_proposal(proposer, "", "", motion)
                self.assertTrue(ok, msg)
                e.support_proposal(pid, co)
            self.assertTrue(e.start_plenary_session()[0])
            for pid in e.db.get_state("meta")["plenary_docket"]:
                for r in e.db.get_state("realms"):
                    e.cast_plenary_vote(r["id"], pid, "support")
            e.conclude_quick_plenary()

        # Turn 1: Sylvan arms itself. Solaris and Aquila modernise (Food Act B will take 10 Cores from everyone, so
        # they need 70 by then). Sylvan's surplus goes to the nations whose missions need Grain, before the border
        # incident makes Grain trades lose 5 in transit. Aquila also deals with the nations it has not met yet.
        self.assertTrue(e.execute_sovereign_action("sylvan", "muster")[0])
        self.assertTrue(e.execute_sovereign_action("solaria", "forge")[0])
        trade("aquila", "val_khor", "silk", 15, "cores", 20)
        trade("solaria", "umbra", "silk", 5, "cores", 5)
        trade("sylvan", "val_khor", "grain", 25, "silk", 5)
        trade("sylvan", "aethelgard", "grain", 15, "silk", 5)
        trade("sylvan", "solaria", "grain", 5, "silk", 5)
        trade("aquila", "umbra", "silk", 5, "cores", 0)
        trade("aquila", "aethelgard", "silk", 5, "cores", 0)
        trade("aquila", "solaria", "silk", 5, "silk", 5)
        assembly(("solaria", "relief_mission", "aquila"))
        e.process_end_of_turn()
        # Turn 2: the border incident costs the nations below 50 Military some Stability, which they can afford.
        assembly(("umbra", "relief_mission", "solaria"))
        e.process_end_of_turn()
        # Turn 3: the famine strikes, the Assembly passes both Food Acts, and everyone gets through the last meal.
        assembly()
        ok, _, outcome = e.conclude_summit()
        self.assertTrue(ok)
        failed = [(ev["realm_id"], ev["public_mission_eval"]["explanation"]) for ev in outcome["realm_evaluations"] if not ev["public_mission_eval"]["achieved"]]
        failed += [(ev["realm_id"], s["explanation"]) for ev in outcome["realm_evaluations"] for s in ev["secret_missions_eval"] if not s["achieved"]]
        self.assertEqual(failed, [])
        self.assertEqual(outcome["continental_verdict"], "STABLE CONTINENT")

    # ---- what the phones are told
    def test_phones_see_how_their_missions_stand(self):
        state = self.engine.get_full_state()
        umbra = next(r for r in state["realms"] if r["id"] == "umbra")
        status = umbra["mission_status"]
        self.assertTrue(status["public"]["met"])
        self.assertTrue(status["secrets"][0]["met"])                         # 80 Cores and 70 Stability at the start
        self.assertIn("80", status["secrets"][0]["note"])

    def test_hints_never_quote_another_nations_numbers(self):
        realms = self.engine.db.get_state("realms")
        next(r for r in realms if r["id"] == "aethelgard")["military_power"] = 95
        self.engine.db.set_state("realms", realms)
        state = self.engine.get_full_state()
        umbra = next(r for r in state["realms"] if r["id"] == "umbra")
        self.assertFalse(umbra["mission_status"]["public"]["met"])
        self.assertNotIn("95", umbra["mission_status"]["public"]["note"])

    def test_the_full_game_has_no_hints(self):
        self.engine.db.set_state("settings", {})
        self.engine.reset_simulation()
        self.assertNotIn("mission_status", self.engine.get_full_state()["realms"][0])

    def test_the_hints_agree_with_the_final_results(self):
        ok, _, outcome = self.engine.conclude_summit()
        state = self.engine.get_full_state()
        hints = {r["id"]: r["mission_status"] for r in state["realms"]}
        for ev in outcome["realm_evaluations"]:
            self.assertEqual(hints[ev["realm_id"]]["public"]["met"], ev["public_mission_eval"]["achieved"], ev["realm_id"])
            self.assertEqual([s["met"] for s in hints[ev["realm_id"]]["secrets"]], [s["achieved"] for s in ev["secret_missions_eval"]], ev["realm_id"])

    # ---- fewer things to watch
    def test_grain_rationing_is_not_available(self):
        e = self.engine
        grain = self._realm("sylvan")["alchemical_grain"]
        self.assertFalse(e.execute_sovereign_action("sylvan", "relief")[0])
        self.assertEqual(self._realm("sylvan")["alchemical_grain"], grain)
        self.assertTrue(e.execute_sovereign_action("sylvan", "gala")[0])

    def test_the_news_never_mentions_vitality(self):
        e = self.engine
        realms = e.db.get_state("realms")
        for r in realms:
            r["alchemical_grain"] = 0
        e.db.set_state("realms", realms)
        e.process_end_of_turn()                                               # everyone starves
        for _ in range(80):
            e.fire_minor_event()
        for cat in load_scenario_config()["catastrophes_catalog"]:
            e.trigger_catastrophe(cat["id"])
        for n in e.db.get_state("news_archive"):
            self.assertNotIn("Vitality", n["detail"], n["headline"])

    def test_the_full_game_news_still_reports_vitality(self):
        e = self.engine
        e.db.set_state("settings", {})
        e.reset_simulation()
        realms = e.db.get_state("realms")
        for r in realms:
            r["alchemical_grain"] = 0
        e.db.set_state("realms", realms)
        e.process_end_of_turn()
        self.assertTrue(any("-25 Vitality" in n["detail"] for n in e.db.get_state("news_archive")))

    def test_the_reflection_question_fits_a_shared_secret_mission(self):
        texts = [q["text"] for q in self.engine.get_full_state()["reflection_questions"]]
        self.assertFalse(any("personal secret mission" in t for t in texts))
        self.assertTrue(any("your secret mission" in t for t in texts))


class TestNationRatings(unittest.TestCase):
    """How hard a nation is to play depends on the kind of game. The lobby is public, so no note may give away a secret mission."""

    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        self.engine = SummitEngine(Database(TEST_DB))

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_notes_do_not_give_away_secret_missions(self):
        giveaways = {"aquila": ("wealthiest", "25 points"), "aethelgard": ("20 ahead", "reserves"), "val_khor": ("20 more", "hegemony"),
                     "solaria": ("veto", "highest standing"), "sylvan": ("70 grain", "long winter"), "umbra": ("hegemon", "60 cores")}
        for r in load_scenario_config()["realms"]:
            for note in (r["difficulty_note"], r["simple_difficulty_note"]):
                self.assertNotIn("secret", note.lower(), r["id"])
                for word in giveaways[r["id"]]:
                    self.assertNotIn(word, note.lower(), r["id"])

    def test_the_rating_follows_the_kind_of_game(self):
        e = self.engine
        realm = lambda rid: next(r for r in e.get_full_state()["realms"] if r["id"] == rid)
        self.assertEqual(realm("sylvan")["play_difficulty"], 3)
        self.assertIn("tempting target", realm("sylvan")["play_difficulty_note"])
        e.update_settings({"complexity": "simplified"})
        self.assertEqual(realm("sylvan")["play_difficulty"], 2)
        self.assertNotIn("tempting target", realm("sylvan")["play_difficulty_note"])    # nobody attacks in this game
        self.assertEqual(realm("val_khor")["play_difficulty"], 3)
        self.assertEqual(realm("aquila")["play_difficulty"], 1)

    def test_every_nation_is_rated_for_the_simplified_game(self):
        levels = set()
        for r in load_scenario_config()["realms"]:
            self.assertIn(r["simple_difficulty"], (1, 2, 3), r["id"])
            self.assertGreater(len(r["simple_difficulty_note"]), 30, r["id"])
            self.assertNotIn("attack", r["simple_difficulty_note"].lower(), r["id"])
            levels.add(r["simple_difficulty"])
        self.assertEqual(levels, {1, 2, 3})

    def test_an_old_save_without_ratings_still_shows_one(self):
        realms = self.engine.db.get_state("realms")
        for r in realms:
            r.pop("simple_difficulty", None)
            r.pop("simple_difficulty_note", None)
        self.engine.db.set_state("realms", realms)
        self.engine.update_settings({"complexity": "simplified"})
        self.assertEqual(next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")["play_difficulty"], 3)


class TestSimplifiedScreens(unittest.TestCase):
    """What the pages contain in each kind of game."""

    def setUp(self):
        from app import engine
        self.engine = engine
        app.config["TESTING"] = True
        self.client = app.test_client()
        engine.db.set_state("settings", {"complexity": "simplified"})
        engine.reset_simulation()

    def tearDown(self):
        self.engine.db.set_state("settings", {})
        self.engine.reset_simulation()

    def _full(self):
        self.engine.db.set_state("settings", {})
        self.engine.reset_simulation()

    def test_the_phone_has_no_quiz_war_room_or_motion_editor(self):
        html = self.client.get("/realm/sylvan?auth=1").get_data(as_text=True)
        self.assertNotIn('data-view="view-quiz"', html)
        self.assertNotIn('id="view-quiz"', html)
        self.assertNotIn('id="war-section"', html)
        self.assertNotIn('id="proposal-form"', html)
        self.assertNotIn('id="proposal-title"', html)
        self.assertNotIn('id="vitality-bar"', html)
        self.assertNotIn("Grain Rationing", html)
        self.assertIn('id="food-forecast"', html)
        self.assertIn('id="public-hint"', html)
        self.assertIn('id="motion-templates"', html)
        self.assertIn('data-view="view-wiki"', html)

    def test_the_full_phone_is_unchanged(self):
        self._full()
        html = self.client.get("/realm/sylvan?auth=1").get_data(as_text=True)
        for present in ('data-view="view-quiz"', 'id="view-quiz"', 'id="war-section"', 'id="proposal-form"', 'id="proposal-title"',
                        'id="vitality-bar"', "Grain Rationing", 'id="motion-params"'):
            self.assertIn(present, html)
        for absent in ('id="food-forecast"', 'id="public-hint"'):
            self.assertNotIn(absent, html)

    def test_the_setup_page_offers_both_settings_and_nothing_else(self):
        html = self.client.get("/admin/setup").get_data(as_text=True)
        for present in ('name="complexity" value="simplified"', 'name="complexity" value="full"', 'name="scenario" value="open"',
                        'name="scenario" value="famine"', 'name="scenario" value="armageddon"', 'id="grain_per_turn"', 'id="good_news"',
                        "Game complexity", "+20 Grain"):
            self.assertIn(present, html)
        self.assertNotIn('name="difficulty"', html)

    def test_the_setup_page_shows_the_choice_for_the_next_game(self):
        self.engine.db.set_state("settings", {"complexity": "full"})
        self.engine.reset_simulation()
        self.engine.admin_control_timer("start")
        self.engine.update_settings({"complexity": "simplified"})
        html = self.client.get("/admin/setup").get_data(as_text=True)
        self.assertIn('value="simplified" checked', html)
        self.assertIn("Full game", html)                                     # the running game is named in the warning

    def test_the_guide_describes_the_game_being_played(self):
        html = self.client.get("/overview").get_data(as_text=True)
        self.assertIn("Game complexity: Simplified", html)
        self.assertIn("Share the Grain", html)
        self.assertIn("Grain: <strong>120 (HIGH)</strong>", html)            # Sylvan, with the starting bonus
        self.assertNotIn("Vitality:", html)
        self.assertNotIn("Lore Quiz", html)
        self.assertNotIn("Grand Plenary debates", html)
        self.assertNotIn("Emergency Grain Rationing", html)
        self.assertNotIn("{amount}", html)
        self.assertNotIn("{me}", html)
        self._full()
        html = self.client.get("/overview").get_data(as_text=True)
        self.assertIn("Game complexity: Full game", html)
        self.assertIn("Grain: <strong>100 (HIGH)</strong>", html)
        self.assertIn("Lore Quiz", html)
        self.assertIn("Resource Pact", html)
        self.assertIn("Emergency Grain Rationing", html)

    def test_the_facilitator_deck_drops_what_the_game_does_not_have(self):
        html = self.client.get("/admin").get_data(as_text=True)
        self.assertIn("Simplified", html)
        self.assertNotIn('id="gm-inbox-card"', html)
        self.assertNotIn('id="admin-war-log"', html)
        self._full()
        html = self.client.get("/admin").get_data(as_text=True)
        self.assertIn('id="gm-inbox-card"', html)
        self.assertIn('id="admin-war-log"', html)

    def test_the_report_names_the_game_and_skips_the_quiz_column(self):
        self.engine.conclude_summit()
        html = self.client.get("/admin/report").get_data(as_text=True)
        self.assertIn("Simplified", html)
        self.assertNotIn("Quiz ✓/✗", html)
        self.assertNotIn("<th>Vitality</th>", html)
        self._full()
        html = self.client.get("/admin/report").get_data(as_text=True)
        self.assertIn("Quiz ✓/✗", html)
        self.assertIn("<th>Vitality</th>", html)

    def test_the_quiz_api_says_there_is_none(self):
        self.assertFalse(self.client.get("/api/quiz/sylvan").json["success"])
        self.assertEqual(self.client.post("/api/quiz/start", json={"realm_id": "sylvan"}).status_code, 400)

    def test_a_motion_goes_all_the_way_through_the_api(self):
        res = self.client.post("/api/proposal/create", json={"proposer_id": "umbra", "effect_type": "plea_for_aid", "params": {"amount": 10}}).json
        self.assertTrue(res["success"], res)
        self.assertTrue(self.client.post(f"/api/proposal/{res['proposal_id']}/support", json={"supporter_id": "sylvan"}).json["success"])
        self.assertTrue(self.client.post("/api/admin/plenary/start", json={}).json["success"])
        for r in self.engine.db.get_state("realms"):
            self.client.post("/api/plenary/vote", json={"realm_id": r["id"], "proposal_id": res["proposal_id"], "choice": "support"})
        grain = next(r for r in self.engine.db.get_state("realms") if r["id"] == "umbra")["alchemical_grain"]
        self.assertTrue(self.client.post("/api/admin/plenary/conclude_quick", json={}).json["success"])
        self.assertEqual(next(r for r in self.engine.db.get_state("realms") if r["id"] == "umbra")["alchemical_grain"], grain + 50)

    def test_mission_hints_stay_on_the_nations_own_phone(self):
        from app import _failed_logins
        _failed_logins.clear()
        app.config["TESTING"] = False
        try:
            phone = app.test_client()
            pin = next(r for r in self.engine.db.get_state("realms") if r["id"] == "umbra")["pin"]
            phone.post("/api/auth/realm", json={"realm_id": "umbra", "pin": pin})
            realms = {r["id"]: r for r in phone.get("/api/state").json["realms"]}
            self.assertIn("mission_status", realms["umbra"])
            self.assertNotIn("mission_status", realms["sylvan"])
            self.assertNotIn("mission_status", app.test_client().get("/api/state").json["realms"][0])
        finally:
            app.config["TESTING"] = True


if __name__ == "__main__":
    unittest.main()


class TestHostedAuthHardening(unittest.TestCase):
    """Enforced auth (TESTING off): admin APIs, signed cookies, state filtering."""

    def setUp(self):
        from app import engine
        engine.reset_simulation()
        engine.clear_realm_sessions(None)
        app.config["TESTING"] = False
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = True

    def test_admin_api_requires_admin_cookie(self):
        self.assertEqual(self.client.post("/api/admin/reset").status_code, 401)
        self.assertEqual(self.client.post("/api/admin/timer/set", json={"seconds": 5}).status_code, 401)

    def test_forged_cookie_rejected(self):
        self.client.set_cookie("auth_admin", "authenticated")
        self.assertEqual(self.client.post("/api/admin/reset").status_code, 401)
        self.assertEqual(self.client.get("/admin?auth=1").data.count(b'id="now-panel"'), 0)

    def test_realm_write_requires_own_cookie(self):
        r = self.client.post("/api/realm/action", json={"realm_id": "sylvan", "action": "relief"})
        self.assertEqual(r.status_code, 401)
        self.client.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
        other = self.client.post("/api/realm/action", json={"realm_id": "val_khor", "action": "relief"})
        self.assertEqual(other.status_code, 401)

    def test_state_hides_pins_secrets_and_answers(self):
        data = self.client.get("/api/state").json
        for r in data["realms"]:
            self.assertNotIn("pin", r)
            self.assertNotIn("secret_missions_pool", r)
            self.assertNotIn("alchemical_grain", r)
        self.assertNotIn("lore_encyclopedia", data)
        self.assertEqual(self.client.get("/api/quiz/sylvan").status_code, 401)
        self.assertNotIn(b'"pin"', self.client.get("/").data)

    def test_owner_sees_own_stocks_only(self):
        self.client.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
        realms = {r["id"]: r for r in self.client.get("/api/state").json["realms"]}
        self.assertIn("alchemical_grain", realms["sylvan"])
        self.assertNotIn("alchemical_grain", realms["val_khor"])


class TestSpireopedia(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_articles_valid_and_links_resolve(self):
        import wiki
        self.assertEqual(wiki.validate(), [])

    def test_every_realm_has_an_article(self):
        import wiki
        slugs = set(wiki.load_wiki()["by_slug"])
        for name in ("sylvan-concordat", "iron-val-khor", "solaris-ascendancy",
                     "umbral-enclave", "aquila-maritime-league", "aethelgard-dominion"):
            self.assertIn(name, slugs)

    def test_wiki_is_in_game_api_only(self):
        # No standalone encyclopedia site: only the JSON API used by the phone Wiki tab.
        self.assertEqual(self.client.get("/wiki").status_code, 404)
        index = self.client.get("/api/wiki").json
        self.assertEqual(len(index["articles"]), 22)
        art = self.client.get("/api/wiki/sylvan-concordat").json["article"]
        self.assertIn("Pact of Roots", art["sections"][0]["html"])
        self.assertTrue(any(k == "Capital" for k, _ in art["infobox"]))
        self.assertIn('data-wiki="', art["lead"])
        self.assertEqual(self.client.get("/api/wiki/nope").status_code, 404)
        hits = self.client.get("/api/wiki/search?q=salt").json["results"]
        self.assertIn("salt-war", [h["slug"] for h in hits])

    def test_wiki_requires_game_login(self):
        app.config["TESTING"] = False
        try:
            client = app.test_client()
            self.assertEqual(client.get("/api/wiki").status_code, 401)
            client.post("/api/auth/realm", json={"realm_id": "aquila", "pin": "1005"})
            self.assertEqual(client.get("/api/wiki").status_code, 200)
        finally:
            app.config["TESTING"] = True

    def test_markup_is_escaped(self):
        import wiki
        self.assertNotIn("<script>", str(wiki.render_markup("<script>alert(1)</script> [[nope]]")))


class TestSaves(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.db.set_state("resume_dismissed", None)
        engine.reset_simulation()
        with engine.db._get_conn() as conn:           # every test starts without saves
            conn.execute("DELETE FROM autosaves")
            conn.commit()

    def tearDown(self):
        self.engine.db.set_state("settings", {})
        self.engine.reset_simulation()

    def _saves(self):
        return self.engine.db.list_autosaves()

    def _poll_after_the_interval(self):
        self.engine._last_autosave = 0                # as if five minutes had passed
        return self.engine.get_full_state()

    def _start_a_game(self):
        self.engine.admin_clock("resume")

    # --- the five-minute autosave ------------------------------------------------------------------
    def test_a_game_being_played_is_saved_every_interval(self):
        self._start_a_game()
        self._poll_after_the_interval()
        self.assertEqual([s["kind"] for s in self._saves()], ["auto"])
        self.assertTrue(self._saves()[0]["label"].startswith("Autosave · Turn 1"))
        self.engine.get_full_state()                  # no second save within five minutes
        self.assertEqual(len(self._saves()), 1)
        time.sleep(1.1)                               # the clock moved on: that is worth a new save
        self._poll_after_the_interval()
        self.assertEqual(len(self._saves()), 2)

    def test_a_game_nobody_has_started_is_not_saved(self):
        for _ in range(3):
            self._poll_after_the_interval()
        self.assertEqual(self._saves(), [])

    def test_a_save_is_not_repeated_when_nothing_has_changed(self):
        self._start_a_game()
        self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5)
        self.engine.admin_clock("pause")
        self._poll_after_the_interval()
        self.assertEqual(len(self._saves()), 1)
        for _ in range(3):                            # a projector polling a paused game for hours
            self._poll_after_the_interval()
        self.assertEqual(len(self._saves()), 1)
        self.engine.admin_override_realm("sylvan", {"alchemical_grain": 1})
        self._poll_after_the_interval()
        self.assertEqual(len(self._saves()), 2)

    def test_a_finished_game_stops_filling_the_list(self):
        self._start_a_game()
        self.engine.conclude_summit()
        count = len(self._saves())
        self.assertEqual(self._saves()[0]["label"], "Summit concluded")
        self._poll_after_the_interval()               # the first check after the end has nothing new to keep...
        settled = len(self._saves())
        self.assertLessEqual(settled, count + 1)
        for _ in range(3):
            self._poll_after_the_interval()
        self.assertEqual(len(self._saves()), settled)  # ...and neither does any later one

    def test_every_turn_leaves_a_checkpoint(self):
        self._start_a_game()
        self.engine.process_end_of_turn()
        self.assertEqual(self._saves()[0]["label"], "Start of Turn 2")
        self.assertEqual(self._saves()[0]["kind"], "kept")
        self.assertEqual(self._saves()[0]["turn"], 2)

    def test_automatic_saves_cannot_push_out_a_deliberate_one(self):
        self._start_a_game()
        keep = self.engine.autosave(label="Manual save", force=True)
        for i in range(Database.KEEP_AUTOMATIC + 5):
            self.engine.db.add_autosave({"meta": {}, "realms": []}, f"Autosave {i}")
        saves = self._saves()
        self.assertIn(keep, [s["id"] for s in saves])
        self.assertEqual(sum(s["kind"] == "auto" for s in saves), Database.KEEP_AUTOMATIC)
        self.assertEqual(sum(s["kind"] != "auto" for s in saves), 1)

    def test_a_failing_autosave_does_not_stop_the_game_and_is_reported(self):
        self._start_a_game()
        self.engine._last_autosave = 0
        real = self.engine.db.add_autosave
        def broken(*args, **kwargs):
            raise OSError("disk full")
        self.engine.db.add_autosave = broken
        try:
            self.assertIn("realms", self.engine.get_full_state())        # the poll still works
            self.assertIn("disk full", self.engine.save_status()["error"])
        finally:
            self.engine.db.add_autosave = real
        self._poll_after_the_interval()
        self.assertIsNone(self.engine.save_status()["error"])

    def test_a_database_from_before_the_new_columns_keeps_its_saves(self):
        import sqlite3, tempfile
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE autosaves (id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL, label TEXT NOT NULL, data TEXT NOT NULL)")
        conn.execute("INSERT INTO autosaves (created, label, data) VALUES (1, 'Autosave · Turn 2 · working', '{}')")
        conn.execute("INSERT INTO autosaves (created, label, data) VALUES (2, 'Manual save', '{}')")
        conn.commit()
        conn.close()
        kinds = {s["label"]: s["kind"] for s in Database(path).list_autosaves()}
        self.assertEqual(kinds, {"Autosave · Turn 2 · working": "auto", "Manual save": "kept"})

    # --- a server restart --------------------------------------------------------------------------
    def test_a_restart_offers_the_interrupted_game_back(self):
        e = self.engine
        self._start_a_game()
        e.create_trade("sylvan", "aquila", "grain", 5, "silk", 5)
        e.admin_override_realm("sylvan", {"alchemical_grain": 77})
        game = e.db.get_state("meta")["game_id"]
        time.sleep(1.1)
        e.get_full_state()
        left = e.db.get_state("meta")["turn_timer_remaining"]
        e.fresh_start()

        offer = e.interrupted_game()
        self.assertEqual(offer["game_id"], game)
        self.assertEqual(offer["kind"], "restart")
        self.assertIn("Turn 1", offer["description"])
        self.assertEqual(self.client.get("/api/state").json["interrupted_game"]["id"], offer["id"])

        res = self.client.post("/api/admin/save/restore", json={"id": offer["id"]})
        self.assertTrue(res.json["success"])
        self.assertIn("paused", res.json["message"])
        meta = e.db.get_state("meta")
        self.assertEqual(meta["game_id"], game)
        self.assertFalse(meta["is_timer_running"])                     # the clock waits until everyone is back
        self.assertLessEqual(abs(meta["turn_timer_remaining"] - left), 1)
        self.assertEqual(next(r for r in e.db.get_state("realms") if r["id"] == "sylvan")["alchemical_grain"], 77)
        self.assertEqual(len(e.db.get_state("trades")), 1)
        self.assertIsNone(e.interrupted_game())                        # back in that game: nothing left to offer

    def test_an_idle_screen_cannot_wipe_the_interrupted_game(self):
        e = self.engine
        self._start_a_game()
        e.autosave(label="Manual save", force=True)
        e.fresh_start()
        for _ in range(Database.KEEP_AUTOMATIC + 5):                   # the projector stays open all night
            self._poll_after_the_interval()
        labels = [s["label"] for s in self._saves()]
        self.assertIn("Manual save", labels)
        self.assertTrue(any(label.startswith("Before server restart") for label in labels))
        self.assertIsNotNone(e.interrupted_game())

    def test_the_offer_ends_when_a_new_game_starts_or_is_declined(self):
        e = self.engine
        self._start_a_game()
        e.fresh_start()
        self.assertIsNotNone(e.interrupted_game())
        self._start_a_game()
        self.assertIsNone(e.interrupted_game())

        self.engine.reset_simulation()
        self._start_a_game()
        e.fresh_start()
        self.assertTrue(self.client.post("/api/admin/resume/dismiss").json["success"])
        self.assertIsNone(e.interrupted_game())
        self.assertTrue(any(s["kind"] == "restart" for s in self._saves()))   # it stays on the Saves tab
        e.fresh_start()                                                # and is not offered again after one more restart
        self.assertIsNone(e.interrupted_game())

    def test_an_old_interruption_is_not_offered_forever(self):
        e = self.engine
        self._start_a_game()
        e.fresh_start()
        with e.db._get_conn() as conn:
            conn.execute("UPDATE autosaves SET created = created - ?", (e.RESUME_OFFER_HOURS * 3600 + 60,))
            conn.commit()
        self.assertIsNone(e.interrupted_game())

    def test_a_finished_game_is_kept_but_not_offered(self):
        e = self.engine
        self._start_a_game()
        e.conclude_summit()
        e.fresh_start()
        self.assertTrue(self._saves()[0]["label"].startswith("Before server restart"))
        self.assertIsNone(e.interrupted_game())

    def test_a_prepared_game_survives_a_restart(self):
        e = self.engine
        ok, _ = e.admin_set_realm_pin("sylvan", "4242")
        self.assertTrue(ok)
        e.update_settings({"scenario": "armageddon"})
        self.assertFalse(e.game_in_progress())
        e.fresh_start()
        offer = e.interrupted_game()
        self.assertEqual(offer["kind"], "setup")
        self.assertNotEqual(next(r for r in e.db.get_state("realms") if r["id"] == "sylvan")["pin"], "4242")
        self.client.post("/api/admin/save/restore", json={"id": offer["id"]})
        self.assertEqual(next(r for r in e.db.get_state("realms") if r["id"] == "sylvan")["pin"], "4242")
        self.assertEqual(e.settings()["scenario"], "armageddon")

    def test_nothing_is_kept_for_a_restart_when_nothing_was_prepared(self):
        self.engine.update_settings(load_scenario_config()["game_settings_defaults"])   # saved, but nothing changed
        self.engine.fresh_start()
        self.assertEqual(self._saves(), [])
        self.assertIsNone(self.engine.interrupted_game())

    def test_a_phone_is_back_in_when_its_game_is_restored(self):
        e = self.engine
        app.config["TESTING"] = False
        try:
            phone = app.test_client()
            self.assertEqual(phone.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"}).status_code, 200)
            self.assertEqual(phone.get("/api/state").json["my_realms"], ["sylvan"])
            self._start_a_game()
            e.fresh_start()
            self.assertEqual(phone.get("/api/state").json["my_realms"], [])
            self.assertEqual(phone.get("/?login=sylvan").status_code, 200)         # asks for the passcode meanwhile
            e.restore_snapshot(e.db.get_autosave(e.interrupted_game()["id"]))
            self.assertEqual(phone.get("/api/state").json["my_realms"], ["sylvan"])
            resp = phone.get("/?login=sylvan")                                     # the waiting phone goes straight back
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/realm/sylvan", resp.headers["Location"])
        finally:
            app.config["TESTING"] = True

    def test_only_the_facilitator_hears_about_saves(self):
        app.config["TESTING"] = False
        try:
            data = app.test_client().get("/api/state").json
            for secret in ("save_status", "interrupted_game", "pins_are_default"):
                self.assertNotIn(secret, data)
            self.assertEqual(app.test_client().post("/api/admin/resume/dismiss").status_code, 401)
            self.assertEqual(app.test_client().get("/admin/cards").status_code, 302)
        finally:
            app.config["TESTING"] = True
        self.assertIn("save_status", self.client.get("/api/state").json)

    # --- other ways to lose a game --------------------------------------------------------------------
    def test_a_reset_keeps_a_copy_of_the_game_it_replaces(self):
        self._start_a_game()
        self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5)
        self.assertTrue(self.client.post("/api/admin/reset").json["success"])
        self.assertEqual(self._saves()[0]["label"], "Before reset")
        self.assertEqual(len(self.engine.db.get_autosave(self._saves()[0]["id"])["trades"]), 1)

    def test_starting_over_with_nothing_played_leaves_no_clutter(self):
        self.client.post("/api/admin/reset")
        self.engine.start_new_summit()
        self.assertEqual(self._saves(), [])

    def test_restoring_garbage_is_refused_without_touching_the_game(self):
        self._start_a_game()
        game = self.engine.db.get_state("meta")["game_id"]
        for body in ({"id": "nonsense"}, {"id": 999999}, {"snapshot": {"realms": "x", "meta": {}}}, {"snapshot": None}):
            self.assertEqual(self.client.post("/api/admin/save/restore", json=body).status_code, 400, body)
        self.assertEqual(self.engine.db.get_state("meta")["game_id"], game)

    def test_a_restored_save_counts_as_the_running_game_for_later_saves(self):
        self._start_a_game()
        saved = self.engine.autosave(label="Manual save", force=True)
        self.client.post("/api/admin/save/restore", json={"id": saved})
        self.assertEqual(self.engine.save_status()["game_id"], self.engine.db.get_state("meta")["game_id"])
        self.assertTrue(self.engine.save_status()["last_at"])

    def test_autosave_and_restore_round_trip(self):
        from app import engine
        self._start_a_game()
        self._poll_after_the_interval()
        self.assertTrue(self.client.get("/api/admin/saves").json["saves"])
        self.assertTrue(self.client.get("/api/admin/save/export").json["in_progress"])

        exported = self.client.get("/api/admin/save/export").json["snapshot"]
        grain = next(r for r in exported["realms"] if r["id"] == "sylvan")["alchemical_grain"]
        engine.admin_override_realm("sylvan", {"alchemical_grain": 1})
        r = self.client.post("/api/admin/save/restore", json={"snapshot": exported})
        self.assertTrue(r.json["success"])
        sylvan = next(x for x in engine.get_full_state()["realms"] if x["id"] == "sylvan")
        self.assertEqual(sylvan["alchemical_grain"], grain)

    def test_restore_rejects_garbage_and_needs_admin(self):
        self.assertEqual(self.client.post("/api/admin/save/restore", json={"snapshot": {"x": 1}}).status_code, 400)
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            self.assertEqual(c.get("/api/admin/saves").status_code, 401)
            self.assertEqual(c.get("/api/admin/save/export").status_code, 401)
            self.assertEqual(c.post("/api/admin/save/restore", json={"id": 1}).status_code, 401)
        finally:
            app.config["TESTING"] = True


class TestJoiningAndScreens(unittest.TestCase):
    """What the first screens need from the server."""

    def setUp(self):
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()
        app.config["TESTING"] = False
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = True
        self.engine.reset_simulation()

    def test_the_join_page_offers_the_way_back_to_a_logged_in_phone(self):
        self.assertNotIn(b"Back to Sylvan Concordat", self.client.get("/").data)
        self.client.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
        self.assertIn(b"Back to Sylvan Concordat", self.client.get("/").data)
        self.assertEqual(self.client.get("/?login=sylvan").status_code, 302)
        self.assertEqual(self.client.get("/?login=umbra").status_code, 200)    # another nation's card still asks for its passcode

    def test_the_join_page_does_not_give_anything_away(self):
        html = self.client.get("/").get_data(as_text=True)
        for secret in ("1001", '"pin"', "secret_missions", "active_secret"):
            self.assertNotIn(secret, html)

    def test_nations_not_playing_are_ready_to_appear_without_a_reload(self):
        self.engine.admin_toggle_realm("umbra", False)
        html = self.client.get("/").get_data(as_text=True)
        self.assertRegex(html, r'style="[^"]*display: none;[^"]*" id="card-umbra"')

    def test_login_messages_say_what_to_do(self):
        wrong = self.client.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "9999"}).json
        self.assertIn("facilitator", wrong["message"])
        for i in range(2):
            app.test_client().post("/api/auth/realm", json={"realm_id": "umbra", "pin": "1004"})
        full = self.client.post("/api/auth/realm", json={"realm_id": "umbra", "pin": "1004"}).json
        self.assertTrue(full["is_full"])
        self.assertIn("facilitator", full["message"])

    def test_passcode_cards_show_every_nation_playing(self):
        app.config["TESTING"] = True
        self.engine.admin_toggle_realm("umbra", False)
        html = self.client.get("/admin/cards").get_data(as_text=True)
        self.assertIn("Sylvan Concordat", html)
        self.assertIn("1001", html)
        self.assertEqual(html.count('class="pass-card"'), 5)
        self.assertNotIn("Umbral Enclave", html)

    def test_the_deck_knows_when_passcodes_are_still_the_defaults(self):
        self.assertTrue(self.engine.pins_are_default())
        self.engine.shuffle_pins()
        # (a shuffle could by chance give a nation its old code back; that is rare enough, and harmless, to retry)
        for _ in range(5):
            if not self.engine.pins_are_default():
                break
            self.engine.shuffle_pins()
        self.assertFalse(self.engine.pins_are_default())

    def test_setting_the_clock_before_the_start_does_not_start_the_game(self):
        self.engine.admin_clock("set", 150)
        self.engine.admin_clock("adjust", 60)
        meta = self.engine.db.get_state("meta")
        self.assertEqual((meta["turn_timer_remaining"], meta["turn_timer_total"]), (210, 210))
        self.assertFalse(self.engine.game_in_progress())

    def test_a_decree_is_news_on_the_phones_not_a_sound(self):
        self.engine.execute_sovereign_action("sylvan", "gala")
        self.assertEqual(self.engine.db.get_state("meta")["audio_cue"]["type"], "decree")


class TestDebriefAndReport(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        from app import engine
        self.engine = engine
        engine.reset_simulation()

    def test_reflection_only_after_conclusion(self):
        r = self.client.post("/api/admin/reflection", json={"step": 0})
        self.assertEqual(r.status_code, 400)
        self.engine.conclude_summit()
        self.assertTrue(self.client.post("/api/admin/reflection", json={"step": 3}).json["success"])
        state = self.engine.get_full_state()
        self.assertEqual(state["meta"]["reflection_step"], 3)
        self.assertEqual(len(state["reflection_questions"]), 12)
        self.client.post("/api/admin/reflection", json={"step": 99})
        self.assertEqual(self.engine.get_full_state()["meta"]["reflection_step"], 11)  # clamped
        self.client.post("/api/admin/reflection", json={"step": None})
        self.assertIsNone(self.engine.get_full_state()["meta"]["reflection_step"])

    def test_results_report(self):
        self.engine.create_trade("sylvan", "aquila", "grain", 10, "silk", 5)
        trade = self.engine.db.get_state("trades")[0]
        self.engine.respond_trade(trade["id"], "accept", "aquila")
        self.engine.conclude_summit()
        html = self.client.get("/admin/report").data.decode()
        self.assertIn("Final standings", html)
        self.assertIn("Sylvan Concordat", html)
        data = self.client.get("/admin/report?format=json").json
        self.assertTrue(data["outcome"])
        sylvan = next(n for n in data["nations"] if n["id"] == "sylvan")
        self.assertIn("Aquila Maritime League", sylvan["trade_partners"])
        self.assertTrue(any("CONCLUDES" in n["headline"] for n in data["timeline"]))

    def test_report_needs_admin(self):
        app.config["TESTING"] = False
        try:
            self.assertEqual(app.test_client().get("/admin/report").status_code, 302)
        finally:
            app.config["TESTING"] = True


class TestClockAndEvents(unittest.TestCase):
    """Settings, automatic phase changes when time runs out, and small random events."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()

    def tearDown(self):
        self.engine.db.set_state("settings", {})

    def _expire(self, key):
        meta = self.engine.db.get_state("meta")
        meta[key] = time.time() - 1
        self.engine.db.set_state("meta", meta)

    def _start_timer(self, seconds=60):
        self.engine.admin_set_timer(seconds)
        self.engine.admin_control_timer("start")

    def test_settings_are_validated_and_clamped(self):
        ok, _ = self.engine.update_settings({"working_session_seconds": 5, "minor_event_max": 99, "grain_consumption": 25,
                                             "good_news_percent": 500, "scenario": "nope", "complexity": "nope", "auto_advance": False})
        self.assertTrue(ok)
        s = self.engine.settings()
        self.assertEqual(s["working_session_seconds"], 60)
        self.assertEqual(s["minor_event_max"], 50)
        self.assertEqual(s["grain_consumption"], 25)
        self.assertEqual(s["good_news_percent"], 100)
        self.assertEqual(s["positive_share"], 1)
        self.assertEqual(s["scenario"], "famine")
        self.assertEqual(s["complexity"], "full")
        self.assertFalse(s["auto_advance"])

    def test_time_up_without_motions_ends_the_turn_and_pauses(self):
        self._start_timer()
        self._expire("turn_timer_end")
        state = self.engine.get_full_state()
        self.assertEqual(state["meta"]["current_turn"], 2)
        self.assertEqual(state["meta"]["phase"], "working")
        self.assertIsNotNone(state["meta"]["intermission_end"])     # short pause before Turn 2
        self.assertEqual(state["meta"]["audio_cue"]["type"] in ("alert", "gong", "turn"), True)
        self._expire("intermission_end")
        self.assertTrue(self.engine.get_full_state()["meta"]["is_timer_running"])

    def test_time_up_with_motion_opens_vote_then_ends_turn(self):
        ok, _, pid = self.engine.draft_proposal("sylvan", "Relief", "Terms", "aid")
        self.engine.support_proposal(pid, "aquila")
        self._start_timer()
        self._expire("turn_timer_end")
        self.assertEqual(self.engine.get_full_state()["meta"]["phase"], "plenary_quick")
        self.engine.cast_plenary_vote("sylvan", pid, "support")
        self._expire("vote_timer_end")
        state = self.engine.get_full_state()
        self.assertEqual(state["meta"]["current_turn"], 2)
        self.assertEqual(next(p for p in state["proposals"] if p["id"] == pid)["status"], "passed")

    def test_manual_mode_only_sounds_the_alert(self):
        self.engine.update_settings({"auto_advance": False})
        self._start_timer()
        self._expire("turn_timer_end")
        state = self.engine.get_full_state()
        self.assertEqual(state["meta"]["current_turn"], 1)
        self.assertEqual(state["meta"]["audio_cue"]["type"], "alert")

    def test_last_turn_ends_with_consumption_and_results(self):
        meta = self.engine.db.get_state("meta")
        meta["current_turn"] = 3
        meta["phase"] = "turn_summary"
        self.engine.db.set_state("meta", meta)
        grain = {r["id"]: r["alchemical_grain"] for r in self.engine.db.get_state("realms")}
        self.engine._advance_turn_or_finish()
        state = self.engine.get_full_state()
        self.assertEqual(state["meta"]["phase"], "summit_concluded")
        self.assertEqual(next(r for r in state["realms"] if r["id"] == "sylvan")["alchemical_grain"], grain["sylvan"] - 20)

    def test_small_events_respect_the_size_limit(self):
        self.engine.update_settings({"minor_event_max": 3})
        before = {r["id"]: r for r in json.loads(json.dumps(self.engine.db.get_state("realms")))}
        for tone in ("good", "bad") * 10:
            self.engine.fire_minor_event(tone=tone)
        cfg = load_scenario_config()
        self.assertTrue(any(e["tone"] == "good" for e in cfg["minor_events"]))
        news = self.engine.db.get_state("news_feed")[:20]
        self.assertTrue(all(n["type"] in ("boon", "crisis") for n in news))
        for n in news:
            amounts = [int(x.split()[0]) for x in n["detail"].rsplit("(", 1)[1].rstrip(")").split(", ")]
            self.assertTrue(all(1 <= abs(a) <= 3 for a in amounts))

    def test_events_are_scheduled_within_the_session(self):
        self.engine.update_settings({"minor_events_per_turn": 2})
        self._start_timer(600)
        meta = self.engine.db.get_state("meta")
        meta["turn_timer_end"] = time.time() + 10      # 590 s of 600 have passed
        self.engine.db.set_state("meta", meta)
        self.engine.get_full_state()
        schedule = self.engine.db.get_state("meta")["minor_event_schedule"]["1"]
        self.assertEqual(len(schedule["times"]), 2)
        self.assertEqual(schedule["fired"], 1)          # at most one event per poll

    def test_event_size_accepts_decimals_and_varies(self):
        self.engine.update_settings({"minor_event_max": 7.5})
        self.assertEqual(self.engine.settings()["minor_event_max"], 7.5)
        cfg = load_scenario_config()
        self.assertGreaterEqual(len(cfg["minor_events"]), 40)
        for tone in ("good", "bad") * 30:
            self.engine.fire_minor_event(tone=tone)
        amounts = []
        for n in self.engine.db.get_state("news_feed")[:60]:
            amounts += [abs(int(x.split()[0])) for x in n["detail"].rsplit("(", 1)[1].rstrip(")").split(", ")]
        self.assertTrue(all(1 <= a <= 8 for a in amounts))
        self.assertGreater(len(set(amounts)), 3)        # a random amount, not always the maximum

    def test_armageddon_brings_large_disasters(self):
        self.engine.update_settings({"scenario": "armageddon", "large_events_per_turn": 2})
        s = self.engine.settings()
        self.assertTrue(s["famine_storyline"])
        self.engine.admin_toggle_realm("umbra", False)
        self._start_timer(600)
        for _ in range(4):                               # the whole session passes, one event per poll
            meta = self.engine.db.get_state("meta")
            meta["turn_timer_end"] = time.time() + 1
            meta["turn_timer_remaining"] = 1
            self.engine.db.set_state("meta", meta)
            self.engine._check_scheduled_events(self.engine.db.get_state("meta"), s)
        entry = self.engine.db.get_state("meta")["minor_event_schedule"]["1"]
        self.assertEqual(entry["large_fired"], 2)
        disasters = [n for n in self.engine.db.get_state("news_feed") if n["headline"].startswith("PLANETARY CRISIS")]
        self.assertEqual(len(disasters), 2)
        self.assertFalse(any("Umbral Enclave" in n["detail"] for n in disasters))   # not playing

    def test_open_scenario_has_no_famine_storyline(self):
        self.engine.update_settings({"scenario": "open"})
        self.engine.process_end_of_turn()
        self.engine.process_end_of_turn()
        self.assertFalse(any(p["effect_type"].startswith("emergency_food") for p in self.engine.db.get_state("proposals")))
        self.assertFalse(any("BORDER INCIDENT" in n["headline"] for n in self.engine.db.get_state("news_feed")))

    def test_changed_event_count_applies_to_the_rest_of_the_session(self):
        self._start_timer(600)
        self.engine.get_full_state()                       # plans this session's events
        fired = self.engine.db.get_state("meta")["minor_event_schedule"]["1"]["fired"]
        self.engine.update_settings({"minor_events_per_turn": 12, "large_events_per_turn": 1})
        entry = self.engine.db.get_state("meta")["minor_event_schedule"]["1"]
        self.assertEqual(len(entry["times"]) + fired, 12)  # events already shown count towards the new total
        self.assertEqual(len(entry["large_times"]), 1)


class TestMotionPrivacy(unittest.TestCase):
    """Co-sponsors are anonymous; addressed motions stay private; questions to the game masters are voted on."""

    def setUp(self):
        from app import engine
        self.engine = engine
        engine.reset_simulation()
        app.config["TESTING"] = False

    def tearDown(self):
        app.config["TESTING"] = True

    def _phone(self, realm_id, pin):
        c = app.test_client()
        self.assertEqual(c.post("/api/auth/realm", json={"realm_id": realm_id, "pin": pin}).status_code, 200)
        return c

    def _motions(self, client):
        return {p["title"]: p for p in client.get("/api/state").json["proposals"]}

    def test_addressed_motion_and_anonymous_cosponsor(self):
        sylvan, valkhor, solaris = self._phone("sylvan", "1001"), self._phone("val_khor", "1002"), self._phone("solaria", "1003")
        sylvan.post("/api/proposal/create", json={"proposer_id": "sylvan", "title": "Secret Pact", "description": "x",
                                                  "effect_type": "aid", "target_seconder_id": "val_khor"})
        self.assertIn("Secret Pact", self._motions(valkhor))           # the addressed nation sees it
        self.assertNotIn("Secret Pact", self._motions(solaris))        # nobody else does
        self.assertNotIn("Secret Pact", json.dumps(app.test_client().get("/api/state").json))  # nor the projector

        pid = self._motions(valkhor)["Secret Pact"]["id"]
        valkhor.post(f"/api/proposal/{pid}/support", json={"supporter_id": "val_khor"})
        seen_by_solaris = self._motions(solaris)["Secret Pact"]      # on the ballot now: visible...
        self.assertEqual(seen_by_solaris["support_count"], 2)
        self.assertNotIn("val_khor", json.dumps(seen_by_solaris))      # ...but the co-sponsor stays anonymous
        self.assertNotIn("Iron Val-Khor", json.dumps(seen_by_solaris))
        self.assertNotIn("Val-Khor", json.dumps(self.engine.db.get_state("news_feed")[:3]))

    def test_question_to_game_masters_goes_through_a_vote(self):
        sylvan, solaris = self._phone("sylvan", "1001"), self._phone("solaria", "1003")
        r = sylvan.post("/api/proposal/create", json={"proposer_id": "sylvan", "title": "Rules?", "description": "Can we trade military?",
                                                      "effect_type": "gm_question"}).json
        self.assertTrue(r["success"])
        pid = r["proposal_id"]
        self.assertEqual(self._motions(solaris)["Rules?"]["status"], "draft")   # a public motion like any other
        app.config["TESTING"] = True
        self.assertFalse(self.engine.answer_question(pid, "Not yet.")[0])        # only passed questions are answered
        app.config["TESTING"] = False
        self.assertEqual(solaris.post(f"/api/proposal/{pid}/support", json={"supporter_id": "solaria"}).status_code, 200)
        app.config["TESTING"] = True
        self.assertTrue(self.engine.start_plenary_session()[0])
        for rid in ("sylvan", "solaria", "aquila"):
            self.engine.cast_plenary_vote(rid, pid, "support")
        self.engine.conclude_quick_plenary()
        ok, _ = self.engine.answer_question(pid, "Yes, Military can be traded.")
        self.assertTrue(ok)
        app.config["TESTING"] = False
        self.assertEqual(self._motions(solaris)["Rules?"]["answer"], "Yes, Military can be traded.")
        self.assertIn("THE GAME MASTERS ANSWER", self.engine.db.get_state("news_feed")[0]["headline"])
        # questions do not count as resolutions for missions
        app.config["TESTING"] = True
        out = self.engine.conclude_summit()[2]
        self.assertEqual(out["passed_proposals_count"], 0)

    def test_there_is_no_limit_on_motions_per_turn(self):
        app.config["TESTING"] = True
        for i in range(8):
            self.assertTrue(self.engine.draft_proposal("sylvan", f"M{i}", "x", "aid")[0])


class TestFewerNations(unittest.TestCase):
    """With five nations every delegate still has a secret mission, nothing refers to an absent nation,
    and the six-nation targets scale down."""

    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()

    def _realms(self):
        return {r["id"]: r for r in self.engine.get_full_state()["realms"]}

    def test_every_roster_of_five_keeps_one_mission_per_delegate(self):
        names = {"sylvan": "Sylvan", "val_khor": "Val-Khor", "solaria": "Solaris", "umbra": "Umbra",
                 "aquila": "Aquila", "aethelgard": "Aethelgard"}
        for left_out in names:
            self.engine.reset_simulation()
            self.engine.admin_toggle_realm(left_out, False)
            for rid, r in self._realms().items():
                if not r["active"]:
                    continue
                secrets = r["active_secret_missions"]
                self.assertEqual(len(secrets), r["player_count"], f"{rid} without {left_out}")
                text = json.dumps([r["public_mission"], secrets])
                self.assertNotIn(names[left_out], text, f"{rid}'s missions mention {left_out}")

    def test_stand_in_mission_is_evaluated(self):
        self.engine.admin_toggle_realm("aethelgard", False)
        sylvan = self._realms()["sylvan"]
        self.assertIn("sylvan_defense_home", [m["id"] for m in sylvan["active_secret_missions"]])
        realms = self.engine.db.get_state("realms")
        next(r for r in realms if r["id"] == "sylvan")["military_power"] = 45
        self.engine.db.set_state("realms", realms)
        # Buying Military from anyone breaks the stand-in "Independent Defense"
        self.engine.create_trade("val_khor", "sylvan", "military", 5, "grain", 5)
        self.engine.respond_trade(self.engine.db.get_state("trades")[0]["id"], "accept", "sylvan")
        out = self.engine.conclude_summit()[2]
        ev = next(e for e in out["realm_evaluations"] if e["realm_id"] == "sylvan")
        home = next(m for m in ev["secret_missions_eval"] if m["id"] == "sylvan_defense_home")
        self.assertFalse(home["achieved"])
        self.assertIn("Violated", home["explanation"])

    def test_targets_scale_with_five_nations(self):
        self.engine.admin_toggle_realm("umbra", False)
        r = self._realms()
        self.assertIn("3 of 5 nations must reach 60 Cores", r["val_khor"]["public_mission"]["description"])
        self.assertIn("votes from at least 3 different nations", r["solaria"]["public_mission"]["description"])
        network = next(m for m in r["aquila"]["active_secret_missions"] if m["id"] == "aquila_trade_network")
        self.assertIn("at least 3 of the other 4", network["objective"])

    def test_six_nation_targets_are_unchanged(self):
        r = self._realms()
        self.assertIn("4 of 6 nations", r["val_khor"]["public_mission"]["description"])
        self.assertIn("at least 4 different nations", r["solaria"]["public_mission"]["description"])
        network = next(m for m in r["aquila"]["active_secret_missions"] if m["id"] == "aquila_trade_network")
        self.assertIn("at least 4 of the other 5", network["objective"])

    def test_ranking_uses_the_share_of_missions_met(self):
        out = self.engine.conclude_summit()[2]
        for e in out["realm_evaluations"]:
            self.assertEqual(e["score"], round(100 * e["achieved_missions"] / e["total_missions"]))
        scores = [e["score"] for e in out["realm_evaluations"]]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestRuleGotchas(unittest.TestCase):
    """Rules that used to misbehave in corner cases."""

    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()

    def _set(self, rid, **fields):
        realms = self.engine.db.get_state("realms")
        next(r for r in realms if r["id"] == rid).update(fields)
        self.engine.db.set_state("realms", realms)

    def test_stability_zero_is_remembered_after_recovery(self):
        self._set("umbra", alchemical_grain=5, civil_stability=15)    # starves at the end of the turn: 15 - 20 -> 0
        self.engine.process_end_of_turn()
        self._set("umbra", civil_stability=80)                          # recovers later...
        out = self.engine.conclude_summit()[2]
        self.assertEqual(out["continental_verdict"], "CONTINENTAL CRISIS")   # ...but hitting 0 still counts
        aeth = next(e for e in out["realm_evaluations"] if e["realm_id"] == "aethelgard")
        self.assertFalse(aeth["public_mission_eval"]["achieved"])

    def test_food_act_a_keeps_grain_when_nobody_is_below_20(self):
        before = sum(r["alchemical_grain"] for r in self.engine.db.get_state("realms"))
        msg = self.engine._apply_proposal_effect({"effect_type": "emergency_food_a"})
        self.assertIn("nothing is transferred", msg)
        self.assertEqual(sum(r["alchemical_grain"] for r in self.engine.db.get_state("realms")), before)
        self._set("val_khor", alchemical_grain=10)                     # now there is someone to help
        self.engine._apply_proposal_effect({"effect_type": "emergency_food_a"})
        realms = {r["id"]: r for r in self.engine.db.get_state("realms")}
        self.assertEqual(realms["sylvan"]["alchemical_grain"], 50)
        self.assertGreater(realms["val_khor"]["alchemical_grain"], 10)

    def test_nothing_changes_after_the_summit_ends(self):
        ok, _ = self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5)
        pending = self.engine.db.get_state("trades")[0]["id"]
        self.engine.conclude_summit()
        meta = self.engine.db.get_state("meta")
        meta["phase"] = "summit_concluded"
        self.engine.db.set_state("meta", meta)
        self.assertFalse(self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5)[0])
        self.assertFalse(self.engine.respond_trade(pending, "accept", "aquila")[0])
        q = load_quiz()["questions"][0]
        self.assertFalse(self.engine.submit_lore_quiz("sylvan", q["id"], q["correct_index"])[0])
        self.assertFalse(self.engine.draft_proposal("sylvan", "Late", "x", "aid")[0])

    def test_motions_only_during_the_working_session(self):
        ok, _, pid = self.engine.draft_proposal("sylvan", "Early", "x", "aid")
        self.engine.draft_proposal("aquila", "On time", "x", "custom")
        self.engine.support_proposal(pid, "aquila")
        self.engine.start_plenary_session()
        ok, msg, _ = self.engine.draft_proposal("umbra", "During the vote", "x", "aid")
        self.assertFalse(ok)
        self.assertIn("working session", msg)
        other = next(p["id"] for p in self.engine.db.get_state("proposals") if p["title"] == "On time")
        self.assertFalse(self.engine.support_proposal(other, "umbra")[0])

    def test_trade_validation(self):
        self.assertFalse(self.engine.create_trade("sylvan", "aquila", "grain", 5, "gold", 5)[0])
        ok, _ = self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5)
        tid = self.engine.db.get_state("trades")[0]["id"]
        self.engine.admin_toggle_realm("sylvan", False)
        ok, msg = self.engine.respond_trade(tid, "accept", "aquila")
        self.assertFalse(ok)
        self.assertIn("no longer taking part", msg)

    def test_news_follows_the_settings(self):
        self.engine.update_settings({"working_session_seconds": 720, "debate_session_seconds": 120})
        self.engine.reset_simulation()
        self.assertTrue(any("12-minute" in n["detail"] for n in self.engine.db.get_state("news_feed")))
        self.engine.process_end_of_turn()
        self.engine.process_end_of_turn()
        self.engine.start_plenary_session()
        news = json.dumps(self.engine.db.get_state("news_feed")[:3])
        self.assertIn("2 minutes", news)
        self.assertNotIn("5 minutes", news)


class TestFreshStart(unittest.TestCase):
    """Every server start begins a new game from the config; logins belong to one game; nothing stale is cached."""

    def setUp(self):
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()
        app.config["TESTING"] = False

    def tearDown(self):
        app.config["TESTING"] = True
        self.engine.db.set_state("settings", {})

    def _phone(self):
        c = app.test_client()
        self.assertEqual(c.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"}).status_code, 200)
        return c

    def test_restart_starts_a_new_game_and_keeps_the_old_one_as_a_save(self):
        self.engine.update_settings({"scenario": "armageddon", "working_session_seconds": 600})
        self.engine.create_trade("sylvan", "aquila", "grain", 5, "silk", 5)        # the game is under way
        old_id = self.engine.db.get_state("meta")["game_id"]
        self.engine.fresh_start()
        self.assertNotEqual(self.engine.db.get_state("meta")["game_id"], old_id)
        self.assertEqual(self.engine.db.get_state("trades"), [])
        self.assertEqual(self.engine.settings()["scenario"], load_scenario_config()["game_settings_defaults"]["scenario"])
        self.assertTrue(self.engine.db.list_autosaves()[0]["label"].startswith("Before server restart"))
        self.assertFalse(self.engine.game_in_progress())

    def test_gunicorn_starts_fresh_once_at_server_start(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gconf", os.path.join(os.path.dirname(__file__), "gunicorn.conf.py"))
        gconf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gconf)
        old_id = self.engine.db.get_state("meta")["game_id"]
        gconf.on_starting(None)
        self.assertNotEqual(self.engine.db.get_state("meta")["game_id"], old_id)

    def test_a_new_game_logs_phones_out(self):
        phone = self._phone()
        mine = next(r for r in phone.get("/api/state").json["realms"] if r["id"] == "sylvan")
        self.assertIn("active_secret_missions", mine)                 # logged in: sees its own secrets
        self.engine.fresh_start()
        mine = next(r for r in phone.get("/api/state").json["realms"] if r["id"] == "sylvan")
        self.assertNotIn("active_secret_missions", mine)              # the old login no longer counts
        resp = phone.get("/realm/sylvan")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/?login=sylvan&again=1", resp.headers["Location"])   # the join page says why it asks again

    def test_browsers_do_not_keep_stale_copies(self):
        self.assertEqual(app.test_client().get("/static/js/realm.js").headers["Cache-Control"], "no-cache")
        self.assertEqual(app.test_client().get("/").headers["Cache-Control"], "no-cache")
        self.assertEqual(app.test_client().get("/api/state").headers["Cache-Control"], "no-store")


class TestMotionBuilder(unittest.TestCase):
    """Motions carry structured effects that the game applies itself, exactly as the players read them."""

    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()

    def _stock(self, field):
        return {r["id"]: r[field] for r in self.engine.db.get_state("realms")}

    def _pass(self, pid):
        prop = next(p for p in self.engine.db.get_state("proposals") if p["id"] == pid)
        return self.engine._apply_proposal_effect(prop)

    def _pact(self, lines, proposer="sylvan"):
        ok, msg, pid = self.engine.draft_proposal(proposer, "Pact", "terms", "pact", None, None, {"lines": lines})
        self.assertTrue(ok, msg)
        return pid

    def test_a_transfer_takes_at_most_what_the_payer_has_and_the_receiver_gets_only_that(self):
        before = self._stock("alchemical_grain")
        pid = self._pact([{"kind": "transfer", "resource": "grain", "amount": 500, "payers": ["sylvan"], "receivers": ["umbra"]}])
        self._pass(pid)
        after = self._stock("alchemical_grain")
        self.assertEqual(after["sylvan"], 0)
        self.assertEqual(after["umbra"], before["umbra"] + before["sylvan"])
        self.assertEqual(sum(after.values()), sum(before.values()))

    def test_an_open_motion_has_no_effect_until_the_game_masters_carry_it_out(self):
        ok, msg, pid = self.engine.draft_proposal("sylvan", "Anything", "Let everyone dance", "open")
        self.assertTrue(ok, msg)
        before = self._stock("alchemical_grain")
        proposals = self.engine.db.get_state("proposals")
        prop = next(p for p in proposals if p["id"] == pid)
        prop["status"] = "passed"
        self.assertIn("carry", self.engine._apply_proposal_effect(prop).lower())   # the caller saves the proposals
        self.engine.db.set_state("proposals", proposals)
        self.assertEqual(self._stock("alchemical_grain"), before)
        self.assertTrue(next(p for p in self.engine.db.get_state("proposals") if p["id"] == pid)["awaiting_gm"])
        self.assertTrue(self.engine.complete_open_motion(pid, "Dancing arranged")[0])
        prop = next(p for p in self.engine.db.get_state("proposals") if p["id"] == pid)
        self.assertFalse(prop["awaiting_gm"])
        self.assertEqual(prop["result_text"], "Dancing arranged")

    def test_every_player_template_writes_its_effect_in_words(self):
        for t in load_scenario_config()["resolution_types"]:
            if not t.get("player_selectable"):
                continue
            params = {"lines": [{"kind": "transfer", "resource": "grain", "amount": 5, "payers": ["sylvan"], "receivers": ["umbra"]}]} if t["id"] == "pact" else {}
            ok, msg, text = self.engine.preview_proposal("sylvan", t["id"], params, "umbra" if t.get("needs_target") else None)
            self.assertTrue(ok, f"{t['id']}: {msg}")
            self.assertTrue(text and all(isinstance(x, str) and x for x in text))

    def test_pact_transfer_moves_resources_and_creates_none(self):
        pid = self._pact([{"kind": "transfer", "resource": "grain", "amount": 10, "payers": ["sylvan"], "receivers": ["val_khor", "umbra"]}])
        before = self._stock("alchemical_grain")
        self._pass(pid)
        after = self._stock("alchemical_grain")
        self.assertEqual(after["sylvan"], before["sylvan"] - 10)
        self.assertEqual(after["val_khor"], before["val_khor"] + 5)
        self.assertEqual(after["umbra"], before["umbra"] + 5)
        self.assertEqual(sum(after.values()), sum(before.values()))

    def test_pact_remainder_goes_to_the_first_receivers_and_payers_without_stock_pay_less(self):
        realms = self.engine.db.get_state("realms")
        next(r for r in realms if r["id"] == "umbra")["echo_silk"] = 4          # can only give 4 of the 10
        self.engine.db.set_state("realms", realms)
        pid = self._pact([{"kind": "transfer", "resource": "silk", "amount": 10, "payers": ["umbra", "aquila"],
                           "receivers": ["sylvan", "val_khor", "solaria"]}], proposer="aquila")
        before = self._stock("echo_silk")
        self._pass(pid)
        after = self._stock("echo_silk")
        self.assertEqual(before["umbra"] - after["umbra"], 4)
        self.assertEqual(before["aquila"] - after["aquila"], 10)
        gains = [after[i] - before[i] for i in ("sylvan", "val_khor", "solaria")]
        self.assertEqual(sum(gains), 14)
        self.assertEqual(gains, [5, 5, 4])
        self.assertEqual(sum(after.values()), sum(before.values()))

    def test_levy_and_dynamic_targets(self):
        ok, msg, pid = self.engine.draft_proposal("umbra", "Sanction", "terms", "embargo", None, None,
                                                  {"target": "@richest", "resource": "silk", "amount": 12})
        self.assertTrue(ok, msg)
        richest = max(self.engine.db.get_state("realms"), key=lambda r: r["alchemical_grain"] + r["aether_cores"] + r["echo_silk"])
        before = self._stock("echo_silk")
        self._pass(pid)
        after = self._stock("echo_silk")
        self.assertEqual(before[richest["id"]] - after[richest["id"]], 12)
        self.assertEqual(sum(before.values()) - sum(after.values()), 12)

    def test_redistribute_only_hands_out_what_is_collected(self):
        realms = self.engine.db.get_state("realms")
        for r in realms:
            r["alchemical_grain"] = {"sylvan": 100, "val_khor": 10, "umbra": 20}.get(r["id"], 40)
        self.engine.db.set_state("realms", realms)
        ok, msg, pid = self.engine.draft_proposal("aquila", "Share", "terms", "tax", None, None,
                                                  {"resource": "grain", "above": 50, "give": 10, "below": 25, "receive": 15})
        self.assertTrue(ok, msg)
        before = self._stock("alchemical_grain")
        self._pass(pid)
        after = self._stock("alchemical_grain")
        self.assertEqual(before["sylvan"] - after["sylvan"], 10)          # the only nation above 50 gives its 10
        self.assertEqual((after["val_khor"] - before["val_khor"]) + (after["umbra"] - before["umbra"]), 10)
        self.assertEqual(sum(after.values()), sum(before.values()))       # nothing created

    def test_cordon_is_automatic_and_defends_in_battle(self):
        ok, msg, pid = self.engine.draft_proposal("aethelgard", "Watch", "terms", "cordon", None, "umbra")
        self.assertTrue(ok, msg)
        before = self._stock("civil_stability")
        self._pass(pid)
        umbra = next(r for r in self.engine.db.get_state("realms") if r["id"] == "umbra")
        self.assertTrue(umbra["is_quarantined"])
        self.assertEqual(umbra["civil_stability"], before["umbra"] + 10)

    def test_players_cannot_make_value_out_of_nothing_or_break_the_limits(self):
        bad = [
            ([{"kind": "boost", "resource": "grain", "amount": 10, "targets": ["sylvan"]}], "unknown kind"),
            ([{"kind": "transfer", "resource": "grain", "amount": 1000, "payers": ["sylvan"], "receivers": ["umbra"]}], "between"),
            ([{"kind": "transfer", "resource": "grain", "amount": 5, "payers": ["sylvan"], "receivers": ["sylvan"]}], "different"),
            ([{"kind": "transfer", "resource": "grain", "amount": 5, "payers": [], "receivers": ["umbra"]}], "at least one"),
            ([{"kind": "transfer", "resource": "vitality", "amount": 5, "payers": ["sylvan"], "receivers": ["umbra"]}], "resource"),
            ([{"kind": "transfer", "resource": "grain", "amount": 5, "payers": ["nobody"], "receivers": ["umbra"]}], "not a nation"),
            ([{"kind": "levy", "resource": "grain", "amount": 5, "targets": ["sylvan"]}] * 4, "1 to 3"),
        ]
        for lines, fragment in bad:
            ok, msg, _ = self.engine.draft_proposal("sylvan", "Bad", "terms", "pact", None, None, {"lines": lines})
            self.assertFalse(ok)
            self.assertIn(fragment, msg.lower() if fragment.islower() else msg)

    def test_inactive_nations_are_skipped_when_a_motion_passes(self):
        pid = self._pact([{"kind": "transfer", "resource": "grain", "amount": 10, "payers": ["sylvan"], "receivers": ["aquila", "umbra"]}])
        self.engine.admin_toggle_realm("aquila", False)
        before = self._stock("alchemical_grain")
        self._pass(pid)
        after = self._stock("alchemical_grain")
        self.assertEqual(after["aquila"], before["aquila"])
        self.assertEqual(after["umbra"], before["umbra"] + 10)

    def test_passed_motion_reports_what_it_did_and_the_news_says_so(self):
        pid = self._pact([{"kind": "transfer", "resource": "grain", "amount": 10, "payers": ["sylvan"], "receivers": ["umbra"]}])
        self.engine.support_proposal(pid, "umbra")
        self.engine.start_plenary_session()
        for rid in ("sylvan", "umbra", "solaria"):
            self.engine.cast_plenary_vote(rid, pid, "support")
        self.engine.conclude_quick_plenary()
        prop = next(p for p in self.engine.db.get_state("proposals") if p["id"] == pid)
        self.assertEqual(prop["status"], "passed")
        self.assertIn("Sylvan Concordat -10 Grain", prop["result_text"])
        news = json.dumps(self.engine.db.get_state("news_feed")[:4])
        self.assertIn("MOTION PASSED", news)
        self.assertIn("Umbral Enclave +10 Grain", news)

    def test_preview_and_create_endpoints(self):
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            c.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
            body = {"proposer_id": "sylvan", "effect_type": "pact", "params": {"lines": [
                {"kind": "levy", "resource": "silk", "amount": 5, "targets": ["umbra"]}]}}
            prev = c.post("/api/proposal/preview", json=body).json
            self.assertTrue(prev["success"])
            self.assertIn("Umbral Enclave loses 5 Silk", prev["effect_text"][0])
            made = c.post("/api/proposal/create", json=dict(body, title="Fine", description="terms")).json
            self.assertTrue(made["success"])
            mine = next(p for p in c.get("/api/state").json["proposals"] if p["id"] == made["proposal_id"])
            self.assertEqual(mine["effect_text"], prev["effect_text"])
            nobody = app.test_client().post("/api/proposal/preview", json=body)
            self.assertEqual(nobody.status_code, 401)
        finally:
            app.config["TESTING"] = True


class TestQuizRun(unittest.TestCase):
    """One question at a time, against the clock; the news carries a digest, never one line per answer."""

    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()
        self.bank = {q["id"]: q for q in load_quiz()["questions"]}

    def _expire(self, realm_id, seconds=30):
        realms = self.engine.db.get_state("realms")
        next(r for r in realms if r["id"] == realm_id)["quiz_active"]["deadline"] -= seconds
        self.engine.db.set_state("realms", realms)

    def test_one_question_at_a_time_and_it_comes_back_after_a_refresh(self):
        ok, _, first = self.engine.quiz_start("sylvan")
        self.assertTrue(ok)
        again_ok, msg, again = self.engine.quiz_start("sylvan")             # a refresh or a teammate's phone
        self.assertTrue(again_ok)
        self.assertEqual(again["question_id"], first["question_id"])
        self.assertEqual(again["options"], first["options"])               # same shuffle, same clock
        self.assertLessEqual(again["seconds_left"], first["seconds_left"])
        self.assertEqual(self.engine.get_quiz_status("sylvan")["active"]["question_id"], first["question_id"])

    def test_the_order_is_random_and_a_nation_never_gets_the_same_question_twice(self):
        firsts = set()
        for _ in range(12):
            self.engine.reset_simulation()
            ok, _, q = self.engine.quiz_start("sylvan")
            firsts.add(q["question_id"])
        self.assertGreater(len(firsts), 5)                                   # not a fixed list
        seen = []
        for _ in range(20):
            ok, _, q = self.engine.quiz_start("sylvan")
            self.assertTrue(ok)
            seen.append(q["question_id"])
            self.engine.submit_lore_quiz("sylvan", q["question_id"], self.bank[q["question_id"]]["correct_index"])
        self.assertEqual(len(set(seen)), 20)
        self.assertTrue(all(self.bank[i]["turn"] == 1 for i in seen))        # still only the unlocked turn

    def test_a_refresh_shows_the_same_next_question_and_stake_until_it_is_taken(self):
        first = self.engine.get_quiz_status("sylvan")["next"]
        for _ in range(5):
            self.assertEqual(self.engine.get_quiz_status("sylvan")["next"], first)
        ok, _, q = self.engine.quiz_start("sylvan")
        self.assertEqual(q["stake_amount"], first["stake_amount"])           # the stake that was shown is the stake that counts

    def test_stakes_are_random_with_an_average_of_five_and_a_win_equals_a_loss(self):
        stakes = []
        for _ in range(300):
            self.engine.reset_simulation()
            stakes.append(self.engine.get_quiz_status("sylvan")["next"]["stake_amount"])
        self.assertEqual(min(stakes), 1)
        self.assertEqual(max(stakes), 9)
        self.assertGreater(len(set(stakes)), 6)
        self.assertAlmostEqual(sum(stakes) / len(stakes), 5.0, delta=0.4)
        for correct in (True, False):                                        # whichever way it goes, exactly the stake moves
            self.engine.reset_simulation()
            ok, _, q = self.engine.quiz_start("sylvan")
            bank = self.bank[q["question_id"]]
            field = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk"}[bank["reward_resource"]]
            before = next(r for r in self.engine.db.get_state("realms") if r["id"] == "sylvan")[field]
            answer = bank["correct_index"] if correct else (bank["correct_index"] + 1) % 4
            self.engine.submit_lore_quiz("sylvan", q["question_id"], answer)
            after = next(r for r in self.engine.db.get_state("realms") if r["id"] == "sylvan")[field]
            self.assertEqual(after - before, q["stake_amount"] if correct else -q["stake_amount"])

    def test_running_out_of_time_counts_as_wrong_and_costs_the_stake(self):
        ok, _, q = self.engine.quiz_start("val_khor")
        bank = self.bank[q["question_id"]]
        field = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk"}[bank["reward_resource"]]
        before = next(r for r in self.engine.db.get_state("realms") if r["id"] == "val_khor")[field]
        stake = q["stake_amount"]
        self._expire("val_khor")
        status = self.engine.get_quiz_status("val_khor")                    # the next poll settles it
        self.assertIsNone(status["active"])
        self.assertEqual(status["history"][0]["status"], "timeout")
        after = next(r for r in self.engine.db.get_state("realms") if r["id"] == "val_khor")[field]
        self.assertEqual(after, before - stake)
        ok, msg, _ = self.engine.submit_lore_quiz("val_khor", q["question_id"], bank["correct_index"])
        self.assertFalse(ok)                                                # too late, and locked

    def test_a_late_answer_is_a_wrong_answer(self):
        ok, _, q = self.engine.quiz_start("aquila")
        self._expire("aquila")
        ok, msg, payload = self.engine.submit_lore_quiz("aquila", q["question_id"], self.bank[q["question_id"]]["correct_index"])
        self.assertFalse(ok)
        self.assertEqual(payload["status"], "timeout")

    def test_the_time_limit_is_a_setting(self):
        self.engine.update_settings({"quiz_seconds": 40})
        ok, _, q = self.engine.quiz_start("sylvan")
        self.assertEqual(q["seconds_total"], 40)
        self.engine.update_settings({"quiz_seconds": 1})
        self.assertEqual(self.engine.settings()["quiz_seconds"], 5)          # clamped to the lowest allowed

    def test_other_nations_cannot_see_an_open_question(self):
        app.config["TESTING"] = False
        try:
            sylvan = app.test_client()
            sylvan.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
            umbra = app.test_client()
            umbra.post("/api/auth/realm", json={"realm_id": "umbra", "pin": "1004"})
            self.assertTrue(sylvan.post("/api/quiz/start", json={"realm_id": "sylvan"}).json["success"])
            mine = next(r for r in sylvan.get("/api/state").json["realms"] if r["id"] == "sylvan")
            theirs = next(r for r in umbra.get("/api/state").json["realms"] if r["id"] == "sylvan")
            self.assertIsNotNone(mine["quiz_active"])
            self.assertNotIn("quiz_active", theirs)
            self.assertEqual(umbra.post("/api/quiz/start", json={"realm_id": "sylvan"}).status_code, 401)   # not their delegation
        finally:
            app.config["TESTING"] = True

    def test_news_gets_a_digest_every_five_minutes_not_a_line_per_answer(self):
        for rid in ("sylvan", "umbra", "aquila"):
            ok, _, q = self.engine.quiz_start(rid)
            self.engine.submit_lore_quiz(rid, q["question_id"], self.bank[q["question_id"]]["correct_index"])
        ok, _, q = self.engine.quiz_start("sylvan")
        self.engine.submit_lore_quiz("sylvan", q["question_id"], (self.bank[q["question_id"]]["correct_index"] + 1) % 4)
        text = json.dumps(self.engine.db.get_state("news_feed"))
        self.assertNotIn("SCHOLARLY", text)
        self.assertNotIn("SPIREOPEDIA QUIZ", text)                           # nothing yet: the window is still open
        meta = self.engine.db.get_state("meta")
        meta["quiz_digest"]["since"] -= 301
        self.engine.db.set_state("meta", meta)
        self.engine.get_full_state()
        latest = self.engine.db.get_state("news_feed")[0]
        self.assertEqual(latest["type"], "lore")
        self.assertIn("3 of 6 nations answered 4 questions", latest["detail"])
        self.assertIn("3 correct, 1 wrong", latest["detail"])
        self.assertNotIn("Sylvan", latest["detail"])                         # no names, no resources
        self.engine.get_full_state()
        self.assertEqual(sum(1 for n in self.engine.db.get_state("news_feed") if "SPIREOPEDIA" in n["headline"]), 1)

    def test_digest_is_flushed_at_the_end_of_a_turn_and_the_summit(self):
        ok, _, q = self.engine.quiz_start("sylvan")
        self.engine.submit_lore_quiz("sylvan", q["question_id"], self.bank[q["question_id"]]["correct_index"])
        self.engine.process_end_of_turn()
        self.assertTrue(any("SPIREOPEDIA" in n["headline"] for n in self.engine.db.get_state("news_feed")))

    def test_an_open_question_is_closed_without_penalty_when_the_summit_ends(self):
        ok, _, q = self.engine.quiz_start("sylvan")
        before = next(r for r in self.engine.db.get_state("realms") if r["id"] == "sylvan")["failed_lore"][:]
        self.engine.conclude_summit()
        realm = next(r for r in self.engine.db.get_state("realms") if r["id"] == "sylvan")
        self.assertIsNone(realm["quiz_active"])
        self.assertEqual(realm["failed_lore"], before)

    def test_the_open_question_gives_no_article_hint(self):
        ok, _, q = self.engine.quiz_start("sylvan")
        self.assertNotIn("article", q)                                       # the open question gives no pointer to the article


class TestClockConsole(unittest.TestCase):
    """The clock console works in every phase of the game."""

    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()

    def _meta(self, **changes):
        meta = self.engine.db.get_state("meta")
        meta.update(changes)
        self.engine.db.set_state("meta", meta)

    def _clock(self):
        return self.engine.get_full_state()["meta"]["display_timer"]

    def test_working_session(self):
        self.assertEqual(self._clock()["kind"], "working")
        self.assertTrue(self.engine.admin_clock("set", 90)[0])
        self.assertEqual(self._clock()["seconds"], 90)
        self.engine.admin_clock("resume")
        self.assertTrue(self._clock()["running"])
        self.engine.admin_clock("adjust", 30)
        self.assertGreaterEqual(self._clock()["seconds"], 118)
        self.engine.admin_clock("pause")
        self.assertFalse(self._clock()["running"])
        self.engine.admin_clock("reset")
        self.assertEqual(self._clock()["seconds"], self.engine.settings()["working_session_seconds"])

    def test_pause_before_the_next_turn(self):
        self._meta(intermission_end=time.time() + 40)
        self.assertEqual(self._clock()["kind"], "intermission")
        self.engine.admin_clock("adjust", 20)
        self.assertGreaterEqual(self._clock()["seconds"], 58)
        self.engine.admin_clock("set", 5)
        self.assertLessEqual(self._clock()["seconds"], 5)
        self.engine.admin_clock("resume")                                   # skip the pause: the working clock starts now
        state = self.engine.get_full_state()["meta"]
        self.assertIsNone(state["intermission_end"])
        self.assertTrue(state["is_timer_running"])

    def test_debate(self):
        self._meta(phase="grand_plenary_discussion", discussion_timer_remaining=300, discussion_timer_total=300,
                   is_discussion_timer_running=True, discussion_timer_end=time.time() + 300, plenary_docket=[], current_motion_index=0)
        self.assertEqual(self._clock()["kind"], "debate")
        self.engine.admin_clock("set", 45)
        self.assertEqual(self._clock()["seconds"], 45)
        self.engine.admin_clock("pause")
        self.assertFalse(self._clock()["running"])
        self.engine.admin_clock("adjust", 15)
        self.assertEqual(self._clock()["seconds"], 60)

    def test_voting_can_be_paused_extended_and_resumed(self):
        self._meta(phase="plenary_quick", vote_timer_end=time.time() + 100, vote_timer_total=100, plenary_docket=[])
        self.assertEqual(self._clock()["kind"], "vote")
        self.engine.admin_clock("pause")
        clock = self._clock()
        self.assertFalse(clock["running"])
        paused_at = clock["seconds"]
        self.assertGreater(paused_at, 90)
        time.sleep(0.05)
        self.assertEqual(self._clock()["seconds"], paused_at)               # a paused clock does not run
        self.engine.admin_clock("adjust", 30)
        self.assertEqual(self._clock()["seconds"], paused_at + 30)
        self.engine.admin_clock("resume")
        self.assertTrue(self._clock()["running"])

    def test_between_turns_and_after_the_summit_there_is_a_free_countdown(self):
        for phase in ("turn_summary", "summit_concluded"):
            self._meta(phase=phase, free_timer_remaining=0, free_timer_running=False, free_timer_end=None)
            self.assertEqual(self._clock()["kind"], "free")
            self.assertFalse(self.engine.admin_clock("resume")[0])           # nothing to run yet
            self.engine.admin_clock("set", 120)
            self.engine.admin_clock("resume")
            self.assertTrue(self._clock()["running"])
            self.assertLessEqual(self._clock()["seconds"], 120)
            self.engine.admin_clock("pause")
            self.assertIn(self._clock()["seconds"] // 10, (11, 12))

    def test_free_countdown_sounds_the_alert_when_it_ends(self):
        self._meta(phase="turn_summary", free_timer_running=True, free_timer_end=time.time() - 1, free_timer_remaining=30)
        seq = self.engine.get_full_state()["meta"]["audio_cue"]["seq"]
        state = self.engine.get_full_state()["meta"]
        self.assertFalse(state["free_timer_running"])
        self.assertEqual(state["audio_cue"]["type"], "alert")
        self.assertGreaterEqual(state["audio_cue"]["seq"], seq)

    def test_input_is_validated_and_the_endpoint_needs_the_facilitator(self):
        self.assertFalse(self.engine.admin_clock("explode")[0])
        self.assertFalse(self.engine.admin_clock("set", "soon")[0])
        self.assertFalse(self.engine.admin_clock("set", 10 ** 7)[0])
        client = app.test_client()
        self.assertEqual(client.post("/api/admin/clock", json={"action": "set", "value": 60}).json["clock"]["seconds"], 60)
        app.config["TESTING"] = False
        try:
            self.assertEqual(app.test_client().post("/api/admin/clock", json={"action": "set", "value": 60}).status_code, 401)
        finally:
            app.config["TESTING"] = True


class TestBulkResources(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.reset_simulation()

    def _realm(self, rid):
        return next(r for r in self.engine.db.get_state("realms") if r["id"] == rid)

    def test_add_take_and_set_for_several_nations_and_resources(self):
        ok, msg, report = self.engine.admin_bulk_adjust(["sylvan", "umbra"], [
            {"resource": "grain", "mode": "add", "amount": 25}, {"resource": "cores", "mode": "take", "amount": 10},
            {"resource": "military", "mode": "set", "amount": 33}])
        self.assertTrue(ok, msg)
        self.assertEqual(self._realm("sylvan")["alchemical_grain"], 125)
        self.assertEqual(self._realm("sylvan")["aether_cores"], 15)
        self.assertEqual(self._realm("umbra")["military_power"], 33)
        self.assertEqual(self._realm("val_khor")["alchemical_grain"], 30)           # untouched
        self.assertEqual(len(report), 2)

    def test_values_stay_in_range(self):
        self.engine.admin_bulk_adjust(["sylvan"], [{"resource": "stability", "mode": "add", "amount": 500},
                                                   {"resource": "grain", "mode": "take", "amount": 900}])
        sylvan = self._realm("sylvan")
        self.assertEqual(sylvan["civil_stability"], 100)
        self.assertEqual(sylvan["alchemical_grain"], 0)

    def test_it_is_quiet_unless_told_to_announce(self):
        before = len(self.engine.db.get_state("news_feed"))
        self.engine.admin_bulk_adjust(["sylvan"], [{"resource": "silk", "mode": "add", "amount": 5}])
        self.assertEqual(len(self.engine.db.get_state("news_feed")), before)
        self.assertTrue(any(n["type"] == "admin" and "Silk 30 → 35" in n["detail"] for n in self.engine.db.get_state("news_archive")))
        self.engine.admin_bulk_adjust(["sylvan"], [{"resource": "silk", "mode": "add", "amount": 5}], announce=True, reason="Convoys arrive")
        latest = self.engine.db.get_state("news_feed")[0]
        self.assertEqual(latest["headline"], "DECREE FROM THE SPIRE")
        self.assertIn("Convoys arrive", latest["detail"])

    def test_bad_requests_are_refused(self):
        self.assertFalse(self.engine.admin_bulk_adjust([], [{"resource": "grain", "mode": "add", "amount": 1}])[0])
        self.assertFalse(self.engine.admin_bulk_adjust(["sylvan"], [])[0])
        self.assertFalse(self.engine.admin_bulk_adjust(["sylvan"], [{"resource": "gold", "mode": "add", "amount": 1}])[0])
        self.assertFalse(self.engine.admin_bulk_adjust(["sylvan"], [{"resource": "grain", "mode": "add", "amount": "lots"}])[0])
        self.assertFalse(self.engine.admin_bulk_adjust(["nobody"], [{"resource": "grain", "mode": "add", "amount": 1}])[0])

    def test_typed_overrides_are_clamped(self):
        self.engine.admin_override_realm("sylvan", {"civil_stability": 500, "alchemical_grain": -9})
        sylvan = self._realm("sylvan")
        self.assertEqual(sylvan["civil_stability"], 100)
        self.assertEqual(sylvan["alchemical_grain"], 0)

    def test_the_endpoint_needs_the_facilitator(self):
        app.config["TESTING"] = False
        try:
            body = {"realm_ids": ["sylvan"], "changes": [{"resource": "grain", "mode": "add", "amount": 5}]}
            self.assertEqual(app.test_client().post("/api/admin/resources/bulk", json=body).status_code, 401)
        finally:
            app.config["TESTING"] = True
        self.assertTrue(app.test_client().post("/api/admin/resources/bulk", json=body).json["success"])


class TestDifficulty(unittest.TestCase):
    def test_every_nation_is_rated_and_explained(self):
        for r in load_scenario_config()["realms"]:
            self.assertIn(r["difficulty"], (1, 2, 3), r["id"])
            self.assertNotIn("secret", r["difficulty_note"].lower(), r["id"])           # the lobby is public
            self.assertGreater(len(r["difficulty_note"]), 30, r["id"])
        levels = {r["id"]: r["difficulty"] for r in load_scenario_config()["realms"]}
        self.assertLess(levels["solaria"], levels["val_khor"])
        self.assertEqual({1, 2, 3}, set(levels.values()))

    def test_the_lobby_setup_and_guide_say_which_is_which(self):
        app.config["TESTING"] = True
        client = app.test_client()
        for path in ("/", "/overview", "/admin/setup"):
            html = client.get(path).get_data(as_text=True)
            self.assertIn("diff-badge", html, path)
            self.assertIn("★", html, path)
        lobby = client.get("/").get_data(as_text=True)
        self.assertIn("Easy", lobby)
        self.assertIn("Hard", lobby)


class TestBattleRules(unittest.TestCase):
    """The shape of a fight: the army counts most, readiness counts a lot, luck only a little."""

    def setUp(self):
        import battle
        self.battle = battle
        self.cfg = battle.config(load_scenario_config().get("battle"))

    def _nation(self, rid="a", military=50, **values):
        base = {"id": rid, "name": rid.upper(), "military_power": military, "civil_stability": 50, "alchemical_grain": 50,
                "aether_cores": 50, "public_vitality": 50, "diplomatic_standing": 50, "echo_silk": 50,
                "geography": {"terrain": "solar_plateau"}}
        base.update(values)
        return base

    def _outcomes(self, attacker, defender, n=800, weather_id=None):
        """Share of battles the attacker wins, the defender wins, and nobody wins."""
        import random
        rng = random.Random(7)
        wins = losses = 0
        for _ in range(n):
            weather = dict(next(w for w in self.cfg["weather"] if w["id"] == weather_id)) if weather_id else self.battle.roll_weather(self.cfg, rng)
            res = self.battle.resolve(attacker, defender, weather, self.cfg, rng)
            wins += res["winner_id"] == attacker["id"]
            losses += res["winner_id"] == defender["id"]
        return wins / n, losses / n, 1 - (wins + losses) / n

    def _win_rate(self, attacker, defender, n=800, weather_id=None):
        return self._outcomes(attacker, defender, n, weather_id)[0]

    def test_readiness_is_neutral_at_fifty_and_drags_or_lifts_away_from_it(self):
        ready, _ = self.battle.readiness(self._nation(), self.cfg)
        self.assertAlmostEqual(ready, 1.0, places=2)
        strong, _ = self.battle.readiness(self._nation(civil_stability=90, alchemical_grain=90, aether_cores=90, public_vitality=90), self.cfg)
        weak, _ = self.battle.readiness(self._nation(civil_stability=10, alchemical_grain=10, aether_cores=10, public_vitality=10), self.cfg)
        self.assertGreater(strong, 1.3)
        self.assertLess(weak, 0.7)
        lo, hi = self.cfg["readiness_range"]
        self.assertTrue(lo <= weak and strong <= hi)

    def test_the_further_from_fifty_the_more_drastic(self):
        pull = lambda v: self.battle.readiness(self._nation(civil_stability=v), self.cfg)[0] - 1.0
        self.assertGreater(pull(90), 2 * pull(70))                 # twice as far, more than twice the effect
        self.assertGreater(pull(55), 0)
        self.assertLess(pull(55), pull(70) / 2)                    # near 50 hardly matters
        self.assertAlmostEqual(pull(30), -pull(70), places=2)      # symmetric above and below 50

    def test_every_resource_in_the_formula_changes_the_strength(self):
        base = self.battle.readiness(self._nation(), self.cfg)[0]
        for field in ("civil_stability", "alchemical_grain", "aether_cores", "public_vitality", "diplomatic_standing", "echo_silk"):
            better = self.battle.readiness(self._nation(**{field: 90}), self.cfg)[0]
            worse = self.battle.readiness(self._nation(**{field: 10}), self.cfg)[0]
            self.assertGreater(better, base, field)
            self.assertLess(worse, base, field)

    def test_stability_and_grain_matter_more_than_silk(self):
        gain = lambda f: self.battle.readiness(self._nation(**{f: 90}), self.cfg)[0] - 1
        self.assertGreater(gain("civil_stability"), gain("echo_silk") * 3)
        self.assertGreater(gain("alchemical_grain"), gain("echo_silk") * 3)

    def test_the_army_counts_most(self):
        double = self._win_rate(self._nation("a", 80), self._nation("d", 40))
        self.assertGreater(double, 0.97)
        edge = self._win_rate(self._nation("a", 65), self._nation("d", 50))
        self.assertGreater(edge, 0.85)
        won, lost, drawn = self._outcomes(self._nation("a", 50), self._nation("d", 50))
        self.assertTrue(0.05 < won < 0.35, won)                       # attacking an equal is a poor bet...
        self.assertTrue(0.25 < lost < 0.5, lost)                      # ...the defender has the ground
        self.assertTrue(0.3 < drawn < 0.65, drawn)                    # and many fights end in a stalemate

    def test_readiness_can_beat_a_bigger_army(self):
        fed_and_calm = self._nation("a", 50, civil_stability=95, alchemical_grain=100, aether_cores=90, public_vitality=90)
        starving = self._nation("d", 62, civil_stability=15, alchemical_grain=5, aether_cores=20, public_vitality=30)
        self.assertGreater(self._win_rate(fed_and_calm, starving), 0.85)

    def test_luck_decides_close_fights_but_never_beats_a_clear_lead(self):
        # the whole spread of luck, ground and weather is a few percent: much less than a 30 percent army lead
        lo, hi = self.cfg["readiness_range"]
        self.assertLess(self.cfg["luck"], (hi - lo) / 10)
        for t in self.cfg["terrain"].values():
            self.assertLess(abs(t["defence"]), 0.15)
        for w in self.cfg["weather"]:
            self.assertLess(max(abs(w["attacker"]), abs(w["defender"])), 0.1)
        self.assertGreater(self._win_rate(self._nation("a", 65), self._nation("d", 50)), 0.8)
        close = self._win_rate(self._nation("a", 56), self._nation("d", 50))
        self.assertTrue(0.3 < close < 0.75, close)

    def test_ground_and_weather_move_the_result_a_little(self):
        rng_mountains = self._nation("d", 50, geography={"terrain": "volcanic_mountains"})
        rng_fields = self._nation("d", 50, geography={"terrain": "verdant_lowlands"})
        attacker = self._nation("a", 50)
        self.assertLess(self._win_rate(attacker, rng_mountains, weather_id="clear"), self._win_rate(attacker, rng_fields, weather_id="clear"))
        self.assertGreater(self._win_rate(attacker, rng_fields, weather_id="tailwind"), self._win_rate(attacker, rng_fields, weather_id="storm"))

    def test_a_cordon_helps_the_defender(self):
        plain = self._nation("d", 50)
        fortified = self._nation("d", 50, is_quarantined=True)
        attacker = self._nation("a", 50)
        self.assertLess(self._win_rate(attacker, fortified, weather_id="clear"), self._win_rate(attacker, plain, weather_id="clear"))

    def test_spoils_are_taken_from_the_loser_and_some_are_lost_in_the_fighting(self):
        import random
        rng = random.Random(3)
        weather = dict(self.cfg["weather"][0])
        for margin_army in (55, 70, 95):
            a, d = self._nation("a", margin_army), self._nation("d", 40)
            res = self.battle.resolve(a, d, weather, self.cfg, rng)
            self.assertEqual(res["winner_id"], "a")
            for resource, got in res["plunder"].items():
                lost = -res["changes"]["d"][resource]
                self.assertLessEqual(got, lost)                               # never more than the loser lost
                self.assertGreater(lost, 0)
            self.assertLess(res["changes"]["d"]["stability"], res["changes"]["a"]["stability"])   # the loser suffers more
            self.assertLess(res["changes"]["a"]["standing"], 0)                                   # aggression costs Standing

    def test_a_bigger_win_takes_more(self):
        import random
        weather = dict(self.cfg["weather"][0])
        small = self.battle.resolve(self._nation("a", 55), self._nation("d", 50), weather, self.cfg, random.Random(1))
        crushing = self.battle.resolve(self._nation("a", 160), self._nation("d", 50), weather, self.cfg, random.Random(1))
        self.assertEqual(crushing["outcome"], "attacker_crushing")
        self.assertGreater(sum(crushing["plunder"].values()), sum(small["plunder"].values()))
        self.assertLess(crushing["changes"]["d"]["stability"], small["changes"]["d"].get("stability", 0))

    def test_a_failed_attack_costs_the_attacker_dearly_and_pays_the_defender(self):
        import random
        res = self.battle.resolve(self._nation("a", 30), self._nation("d", 80), dict(self.cfg["weather"][0]), self.cfg, random.Random(5))
        self.assertEqual(res["winner_id"], "d")
        self.assertLessEqual(res["changes"]["a"]["standing"], -10)
        self.assertEqual(res["changes"]["d"]["standing"], 3)
        self.assertTrue(res["plunder"])

    def test_a_dead_heat_has_no_winner_and_no_spoils(self):
        import random
        res = self.battle.resolve(self._nation("a", 50), self._nation("d", 50), {"id": "x", "name": "x", "attacker": 0, "defender": 0, "luck": 0.0},
                                  dict(self.cfg, luck=0.0), random.Random(1))
        self.assertEqual(res["outcome"], "stalemate")
        self.assertIsNone(res["winner_id"])
        self.assertEqual(res["plunder"], {})

    def _report(self, attacker, defender, seed="s", weather=None):
        return self.battle.scouting(attacker, defender, weather or {"id": "clear", "name": "Clear skies", "text": "x", "attacker": 0.0, "defender": 0.0, "luck": 1.0},
                                    self.cfg, seed)

    def test_the_more_wealth_the_more_modifiers_are_revealed(self):
        poor = self._nation("a", alchemical_grain=10, aether_cores=10, echo_silk=10, civil_stability=90)
        rich = self._nation("a", alchemical_grain=90, aether_cores=90, echo_silk=90, civil_stability=90)
        enemy = self._nation("d", civil_stability=10, alchemical_grain=90, aether_cores=10, echo_silk=10, public_vitality=90)
        few, many = self._report(poor, enemy), self._report(rich, enemy)
        self.assertEqual(len(few["modifiers"]), 1)
        self.assertGreater(len(many["modifiers"]), len(few["modifiers"]))
        self.assertEqual(many["hidden"] + len(many["modifiers"]), many["total"])

    def test_the_biggest_modifiers_come_first(self):
        att = self._nation("a", alchemical_grain=60, aether_cores=60, echo_silk=60, civil_stability=95)
        dfn = self._nation("d", civil_stability=5)
        report = self._report(att, dfn)
        sizes = [abs(self.battle.modifier_lines(att, "attacker", {}, self.cfg)[0]["pct"])]
        self.assertTrue(report["modifiers"])
        self.assertIn("stability", report["modifiers"][0]["label"].lower())

    def test_better_spies_give_figures_closer_to_the_truth(self):
        import statistics
        dfn = self._nation("d", civil_stability=90)
        truth = next(l for l in self.battle.modifier_lines(dfn, "defender", self.battle.terrain_for(dfn, self.cfg), self.cfg) if l["key"] == "stability")["pct"]
        def error(silk_cores):
            att = self._nation("a", echo_silk=silk_cores, aether_cores=silk_cores, alchemical_grain=90)
            errs = []
            for i in range(200):
                rep = self.battle.reveal(att, {"defender": [{"key": "stability", "label": "x", "pct": truth}], "attacker": []}, "attacker",
                                         self.battle.intel(att, self.cfg), self.cfg, f"seed{i}")
                self.assertEqual(len(rep["modifiers"]), 1)
                errs.append(rep)
            return errs
        # with poor scouts the report is only a word; with great scouts it is a figure close to the truth
        self.assertTrue(all(not any(ch.isdigit() for ch in r["modifiers"][0]["text"]) for r in error(10)))
        good = [int(r["modifiers"][0]["text"].split()[1].rstrip("%")) for r in error(100)]
        self.assertLess(max(abs(g - truth) for g in good), 6)
        self.assertTrue(any(g != truth for g in good))                  # but never perfectly accurate

    def test_a_report_never_contains_luck_or_the_facilitators_adjustments(self):
        att = self._nation("a", modifiers={"war_power_pct": 40}, alchemical_grain=90, aether_cores=90, echo_silk=90)
        dfn = self._nation("d", modifiers={"war_defence_pct": 40})
        text = json.dumps(self._report(att, dfn)).lower()
        for secret in ("luck", "war_power", "war_defence", "defence\": 0.", "attacker\": 0", "own_power", "readiness"):
            self.assertNotIn(secret, text)

    def test_the_own_side_is_scouted_more_accurately_than_the_enemy(self):
        att = self._nation("a", echo_silk=45, aether_cores=45, alchemical_grain=90)
        rep = self.battle.reveal(att, {"attacker": [{"key": "grain", "label": "g", "pct": 10}], "defender": [{"key": "grain", "label": "g", "pct": 10}]},
                                 "attacker", self.battle.intel(att, self.cfg), self.cfg, "z")
        by = {m["whose"]: m["text"] for m in rep["modifiers"]}
        self.assertEqual(len(by), 2)
        self.assertNotEqual(by["own"].split()[0], by["enemy"].split()[0])    # a figure for your own side, a range for theirs

    def test_scouts_give_a_stable_blurred_estimate(self):
        a, d = self._nation("a", 70), self._nation("d", 50)
        weather = dict(self.cfg["weather"][0])
        first = self.battle.scouting(a, d, weather, self.cfg, "seed-1")
        self.assertEqual(first, self.battle.scouting(a, d, weather, self.cfg, "seed-1"))     # asking again changes nothing
        self.assertNotIn("alchemical_grain", json.dumps(first))                             # and says nothing about the target's stock


class TestBattlesInTheGame(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()
        meta = engine.db.get_state("meta")
        meta["current_turn"] = 2                       # attacks unlock in Turn 2
        engine.db.set_state("meta", meta)

    def _realm(self, rid):
        return next(r for r in self.engine.db.get_state("realms") if r["id"] == rid)

    def _set(self, rid, **values):
        realms = self.engine.db.get_state("realms")
        next(r for r in realms if r["id"] == rid).update(values)
        self.engine.db.set_state("realms", realms)

    def test_attacks_wait_for_the_chosen_turn(self):
        meta = self.engine.db.get_state("meta")
        meta["current_turn"] = 1
        self.engine.db.set_state("meta", meta)
        ok, msg, _ = self.engine.declare_attack("aethelgard", "sylvan")
        self.assertFalse(ok)
        self.assertIn("from Turn 2", msg)
        self.engine.update_settings({"attacks_from_turn": 1})
        self.assertTrue(self.engine.declare_attack("aethelgard", "sylvan")[0])

    def test_attacks_can_be_switched_off(self):
        self.engine.update_settings({"attacks_enabled": False})
        ok, msg, _ = self.engine.declare_attack("aethelgard", "sylvan")
        self.assertFalse(ok)
        self.assertIn("switched off", msg)
        self.assertFalse(self.engine.get_war_status("aethelgard")["enabled"])

    def test_the_rules_of_the_field(self):
        self.assertFalse(self.engine.declare_attack("sylvan", "sylvan")[0])
        self.engine.admin_toggle_realm("umbra", False)
        self.assertFalse(self.engine.declare_attack("sylvan", "umbra")[0])
        self._set("sylvan", military_power=5)
        self.assertIn("at least", self.engine.declare_attack("sylvan", "aquila")[1])
        self._set("sylvan", military_power=40, alchemical_grain=4)
        self.assertIn("Grain", self.engine.declare_attack("sylvan", "aquila")[1])
        meta = self.engine.db.get_state("meta")
        meta["phase"] = "plenary_quick"
        self.engine.db.set_state("meta", meta)
        self.assertIn("working session", self.engine.declare_attack("aethelgard", "aquila")[1])

    def test_one_march_per_turn_and_nobody_is_dog_piled(self):
        self.assertTrue(self.engine.declare_attack("aethelgard", "sylvan")[0])
        self.assertIn("already marched", self.engine.declare_attack("aethelgard", "umbra")[1])
        self.assertTrue(self.engine.declare_attack("val_khor", "sylvan")[0])
        ok, msg, _ = self.engine.declare_attack("solaria", "sylvan")
        self.assertFalse(ok)
        self.assertIn("already been attacked", msg)
        self.engine.update_settings({"attacks_per_turn": 2})
        self.assertTrue(self.engine.declare_attack("aethelgard", "umbra")[0])
        self.engine.process_end_of_turn()                                # a new turn, new allowances
        self._set("aethelgard", alchemical_grain=100, military_power=60)
        ok, msg, _ = self.engine.declare_attack("aethelgard", "sylvan")
        self.assertTrue(ok, msg)

    def test_the_march_costs_supplies_and_the_outcome_is_recorded_and_announced(self):
        grain = self._realm("aethelgard")["alchemical_grain"]
        standing = self._realm("aethelgard")["diplomatic_standing"]
        ok, msg, battle = self.engine.declare_attack("aethelgard", "sylvan")
        self.assertTrue(ok)
        self.assertLess(self._realm("aethelgard")["diplomatic_standing"], standing)
        self.assertEqual(self.engine.db.get_state("battles")[0]["id"], battle["id"])
        self.assertEqual(self.engine.db.get_state("news_feed")[0]["type"], "war")
        self.assertEqual(self.engine.get_full_state()["meta"]["audio_cue"]["type"], "battle")
        won = battle["winner_id"] == "aethelgard"
        gained = battle["plunder"].get("grain", 0) if won else -battle["plunder"].get("grain", 0)
        self.assertEqual(self._realm("aethelgard")["alchemical_grain"], max(0, grain - 20 + gained))      # a surprise attack costs double supplies

    def test_spoils_are_never_more_than_the_loser_lost(self):
        total = lambda: sum(r["alchemical_grain"] + r["aether_cores"] + r["echo_silk"] for r in self.engine.db.get_state("realms"))
        before = total()
        ok, msg, battle = self.engine.declare_attack("aethelgard", "sylvan")
        self.assertTrue(ok)
        self.assertLess(total(), before)                                   # war destroys: supplies and the spoils lost in the fighting

    def test_weather_is_rolled_for_every_turn(self):
        weathers = set()
        for _ in range(25):
            self.engine.process_end_of_turn()
            meta = self.engine.db.get_state("meta")
            self.assertIn("name", meta["weather"])
            weathers.add(meta["weather"]["id"])
            meta["current_turn"] = 1
            self.engine.db.set_state("meta", meta)
        self.assertGreater(len(weathers), 2)

    def test_players_see_the_outcome_but_only_their_own_numbers(self):
        ok, msg, battle = self.engine.declare_attack("aethelgard", "sylvan")
        app.config["TESTING"] = False
        try:
            attacker, defender, bystander = app.test_client(), app.test_client(), app.test_client()
            attacker.post("/api/auth/realm", json={"realm_id": "aethelgard", "pin": "1006"})
            defender.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
            bystander.post("/api/auth/realm", json={"realm_id": "umbra", "pin": "1004"})
            seen_by = lambda c: c.get("/api/state").json["battles"][0]
            self.assertEqual(seen_by(attacker)["private"]["side"], "attacker")
            self.assertEqual(seen_by(defender)["private"]["side"], "defender")
            self.assertNotIn("private", seen_by(bystander))
            self.assertNotIn("private", app.test_client().get("/api/state").json["battles"][0])      # the projector
            for key in ("outcome", "share", "plunder", "weather", "terrain", "headline"):
                self.assertIn(key, seen_by(bystander))
            mine = seen_by(attacker)["private"]["mine"]
            text = json.dumps(mine)
            for secret in ("luck", "power", "environment", "readiness", "factors"):
                self.assertNotIn(secret, text)                                  # no luck, no exact strength
            self.assertIn("modifiers", mine)
            self.assertIn("changes", mine)
        finally:
            app.config["TESTING"] = True
        admin = app.test_client().get("/api/state").json["battles"][0]
        self.assertIn("attacker", admin["private"])
        self.assertIn("defender", admin["private"])

    def test_war_endpoints(self):
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            c.post("/api/auth/realm", json={"realm_id": "aethelgard", "pin": "1006"})
            status = c.get("/api/war/aethelgard").json
            self.assertTrue(status["enabled"])
            self.assertEqual(len(status["targets"]), 5)
            self.assertEqual(app.test_client().get("/api/war/aethelgard").status_code, 401)
            preview = c.post("/api/war/preview", json={"realm_id": "aethelgard", "target_id": "umbra"}).json
            self.assertTrue(preview["success"])
            self.assertIn(preview["preview"]["label"], ("Very unfavourable", "Unfavourable", "Evenly matched", "Favourable", "Very favourable"))
            self.assertNotIn("alchemical_grain", json.dumps(preview))
            attack = c.post("/api/war/attack", json={"realm_id": "aethelgard", "target_id": "umbra", "mode": "surprise"}).json
            self.assertTrue(attack["success"])
            self.assertEqual(attack["battle"]["private"]["side"], "attacker")
            self.assertEqual(set(preview["preview"]["modes"]), {"siege", "surprise"})
            self.assertEqual(c.post("/api/war/attack", json={"realm_id": "aethelgard", "target_id": "sylvan"}).status_code, 400)
            other = app.test_client()
            other.post("/api/auth/realm", json={"realm_id": "sylvan", "pin": "1001"})
            self.assertEqual(other.post("/api/war/attack", json={"realm_id": "aethelgard", "target_id": "umbra"}).status_code, 401)
        finally:
            app.config["TESTING"] = True

    def test_starving_nations_fight_worse(self):
        import battle
        cfg = battle.config(load_scenario_config().get("battle"))
        fed = self._realm("aethelgard")
        hungry = dict(fed, alchemical_grain=0, civil_stability=20)
        self.assertLess(battle.readiness(hungry, cfg)[0], battle.readiness(fed, cfg)[0] - 0.2)

    def test_the_report_lists_the_battles(self):
        self.engine.declare_attack("aethelgard", "sylvan")
        report = self.engine.build_report()
        self.assertEqual(len(report["battles"]), 1)
        self.assertEqual(report["battles"][0]["attacker"], "Aethelgard Dominion")


class TestModifiers(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()

    def _realm(self, rid):
        return next(r for r in self.engine.db.get_state("realms") if r["id"] == rid)

    def test_the_sheet_explains_the_automatic_modifiers(self):
        sheet = self.engine.modifier_sheet(self._realm("sylvan"))
        self.assertEqual(sheet["votes"]["total"], self._realm("sylvan")["assembly_votes"])
        self.assertEqual(sheet["grain_use"], 20)
        self.assertEqual(sheet["manual"], {"votes": 0, "grain_use_pct": 0, "war_power_pct": 0, "war_defence_pct": 0})
        self.assertTrue(any("defence" in line for line in sheet["automatic"]))      # the home terrain

    def test_manual_votes_and_grain_use_take_effect(self):
        before = self._realm("umbra")["assembly_votes"]
        self.assertTrue(self.engine.admin_set_modifiers("umbra", {"votes": 2, "grain_use_pct": -50})[0])
        self.assertEqual(self._realm("umbra")["assembly_votes"], before + 2)
        grain = self._realm("umbra")["alchemical_grain"]
        realms = self.engine.db.get_state("realms")
        self.engine._consume_grain([r for r in realms if r["id"] == "umbra"], self.engine.settings())
        self.assertEqual(next(r for r in realms if r["id"] == "umbra")["alchemical_grain"], grain - 10)
        self.assertEqual(self.engine.modifier_sheet(self._realm("umbra"))["grain_use"], 10)

    def test_values_outside_the_limits_are_refused(self):
        self.assertFalse(self.engine.admin_set_modifiers("umbra", {"votes": 99})[0])
        self.assertFalse(self.engine.admin_set_modifiers("umbra", {"nonsense": 1})[0])
        self.assertFalse(self.engine.admin_set_modifiers("umbra", {"votes": "x"})[0])
        self.assertFalse(self.engine.admin_set_modifiers("nobody", {"votes": 1})[0])

    def test_war_modifiers_change_the_power_of_the_army(self):
        import battle
        cfg = battle.config(None)
        realm = dict(self._realm("aethelgard"))
        terrain = battle.terrain_for(realm, cfg)
        base = battle.side_power(realm, "defender", terrain, {}, cfg, None)["power"]
        realm["modifiers"] = {"war_power_pct": 20, "war_defence_pct": 10}
        boosted = battle.side_power(realm, "defender", terrain, {}, cfg, None)["power"]
        self.assertGreater(boosted, base)
        attack_only = battle.side_power(realm, "attacker", terrain, {}, cfg, None)["power"]
        self.assertLess(attack_only, boosted)                        # the defence bonus only counts when attacked

    def test_the_efficiency_flag_can_be_switched_off_even_with_many_cores(self):
        realms = self.engine.db.get_state("realms")
        next(r for r in realms if r["id"] == "umbra")["aether_cores"] = 90
        self.engine._recalculate_all_realms(realms)
        self.engine.db.set_state("realms", realms)
        self.assertTrue(self._realm("umbra")["tech_efficiency_unlocked"])
        self.engine.admin_set_modifiers("umbra", None, {"tech_efficiency_unlocked": False})
        self.assertFalse(self._realm("umbra")["tech_efficiency_unlocked"])
        self.engine.admin_set_modifiers("umbra", None, {"tech_efficiency_unlocked": True})
        self.assertTrue(self._realm("umbra")["tech_efficiency_unlocked"])

    def test_endpoints_and_privacy(self):
        client = app.test_client()
        data = client.get("/api/admin/modifiers").get_json()
        self.assertTrue(data["success"])
        r = client.post("/api/admin/modifiers", json={"realm_id": "umbra", "manual": {"war_power_pct": 15}})
        self.assertEqual(r.status_code, 200)
        app.config["TESTING"] = False
        try:
            state = client.get("/api/state").get_json()
        finally:
            app.config["TESTING"] = True
        self.assertTrue(all("modifiers" not in realm for realm in state["realms"]))


class TestActionJournal(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()
        self.client = app.test_client()

    def _realm(self, rid):
        return next(r for r in self.engine.db.get_state("realms") if r["id"] == rid)

    def _entries(self):
        return self.client.get("/api/admin/journal").get_json()["entries"]

    def test_a_manual_change_is_recorded_and_can_be_reversed(self):
        before = self._realm("sylvan")["alchemical_grain"]
        self.client.post("/api/admin/resources/bulk", json={"realm_ids": ["sylvan"], "changes": [{"resource": "grain", "mode": "add", "amount": 25}]})
        entries = self._entries()
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]["undoable"])
        self.assertIn(f"Grain {before} → {before + 25}", entries[0]["lines"][0])
        r = self.client.post("/api/admin/journal/undo", json={"id": entries[0]["id"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._realm("sylvan")["alchemical_grain"], before)
        self.assertTrue(self._entries()[0]["reverted"])
        self.assertEqual(self.client.post("/api/admin/journal/undo", json={"id": entries[0]["id"]}).status_code, 400)

    def test_undo_keeps_later_changes_to_the_same_nation(self):
        base = self._realm("sylvan")["alchemical_grain"]
        self.client.post("/api/admin/resources/bulk", json={"realm_ids": ["sylvan"], "changes": [{"resource": "grain", "mode": "add", "amount": 25}]})
        first = self._entries()[0]["id"]
        self.client.post("/api/admin/resources/bulk", json={"realm_ids": ["sylvan"], "changes": [{"resource": "grain", "mode": "add", "amount": 10}]})
        self.client.post("/api/admin/journal/undo", json={"id": first})
        self.assertEqual(self._realm("sylvan")["alchemical_grain"], base + 10)

    def test_requests_that_change_nothing_are_not_recorded(self):
        self.client.post("/api/admin/news/broadcast", json={"headline": "x", "detail": "y"})
        self.assertEqual(self._entries(), [])

    def test_a_player_action_is_recorded_under_the_nation_and_flags_are_restored(self):
        self.client.post("/api/admin/modifiers", json={"realm_id": "umbra", "manual": {"votes": 2}, "flags": {"is_quarantined": True}})
        entry = self._entries()[0]
        self.assertEqual(entry["actor"], "Facilitator")
        self.client.post("/api/admin/journal/undo", json={"id": entry["id"]})
        self.assertFalse(self._realm("umbra").get("is_quarantined"))
        self.assertEqual(self.engine.modifier_sheet(self._realm("umbra"))["manual"]["votes"], 0)

    def test_the_end_of_a_turn_is_recorded_but_not_reversible_and_a_reset_clears_the_journal(self):
        self.client.post("/api/admin/turn/next", json={})
        entries = self._entries()
        if entries:
            self.assertFalse(entries[0]["undoable"])
            self.assertEqual(self.client.post("/api/admin/journal/undo", json={"id": entries[0]["id"]}).status_code, 400)
        self.client.post("/api/admin/resources/bulk", json={"realm_ids": ["sylvan"], "changes": [{"resource": "grain", "mode": "add", "amount": 1}]})
        self.engine.reset_simulation()
        self.assertEqual(self._entries(), [])


class TestSiegeAndSurprise(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        from app import engine
        self.engine = engine
        engine.db.set_state("settings", {})
        engine.reset_simulation()
        meta = engine.db.get_state("meta")
        meta["current_turn"] = 2
        meta["turn_timer_remaining"] = 600
        meta["turn_timer_total"] = 600
        engine.db.set_state("meta", meta)

    def _realm(self, rid):
        return next(r for r in self.engine.db.get_state("realms") if r["id"] == rid)

    def _clock(self, remaining):
        meta = self.engine.db.get_state("meta")
        meta["turn_timer_remaining"] = remaining
        meta["is_timer_running"] = False
        self.engine.db.set_state("meta", meta)

    def test_a_siege_is_announced_and_arrives_after_two_minutes_of_working_time(self):
        grain = self._realm("aethelgard")["alchemical_grain"]
        ok, msg, siege = self.engine.declare_attack("aethelgard", "sylvan", "siege")
        self.assertTrue(ok, msg)
        self.assertEqual(self._realm("aethelgard")["alchemical_grain"], grain - 10)        # supplies are paid at once
        self.assertEqual(self.engine.db.get_state("battles"), [])                          # nothing is fought yet
        news = self.engine.db.get_state("news_feed")[0]
        self.assertEqual(news["type"], "war")
        self.assertIn("SIEGE", news["headline"])
        public = self.engine.get_full_state()["sieges"]
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0]["eta"], 120)
        self.assertNotIn("paid", public[0])
        self._clock(500)
        self.assertEqual(self.engine.resolve_sieges(), [])                                 # 100 s have passed
        self.assertEqual(self.engine.get_full_state()["sieges"][0]["eta"], 20)
        self._clock(479)
        fought = self.engine.resolve_sieges()
        self.assertEqual(len(fought), 1)
        self.assertEqual(fought[0]["mode"], "siege")
        self.assertEqual(self.engine.get_full_state()["sieges"], [])
        self.assertEqual(len(self.engine.db.get_state("battles")), 1)

    def test_a_siege_on_the_road_counts_as_a_march_and_as_an_attack_received(self):
        self.engine.declare_attack("aethelgard", "sylvan", "siege")
        ok, msg, _ = self.engine.declare_attack("aethelgard", "umbra", "siege")
        self.assertFalse(ok)
        self.assertIn("already marched", msg)
        self.engine.declare_attack("val_khor", "sylvan", "siege")
        ok, msg, _ = self.engine.declare_attack("solaria", "sylvan", "siege")
        self.assertIn("already been attacked", msg)

    def test_the_clock_decides_when_the_army_arrives_so_a_pause_pauses_the_march(self):
        self.engine.declare_attack("aethelgard", "sylvan", "siege")
        self.engine.db.set_state("meta", dict(self.engine.db.get_state("meta"), is_timer_running=False))
        self.assertEqual(self.engine.resolve_sieges(), [])
        self.assertEqual(self.engine.get_full_state()["sieges"][0]["eta"], 120)

    def test_a_siege_that_is_still_on_the_road_when_the_turn_ends_arrives_first(self):
        self.engine.declare_attack("aethelgard", "sylvan", "siege")
        self.engine.process_end_of_turn()
        self.assertEqual(self.engine.get_full_state()["sieges"], [])
        self.assertEqual(len(self.engine.db.get_state("battles")), 1)

    def test_a_siege_is_lifted_if_a_nation_leaves(self):
        self.engine.declare_attack("aethelgard", "sylvan", "siege")
        self.engine.admin_override_realm("sylvan", {"active": False})
        self.assertEqual(self.engine.resolve_sieges(force=True), [])
        self.assertEqual(self.engine.db.get_state("battles"), [])
        self.assertIn("SIEGE LIFTED", self.engine.db.get_state("news_feed")[0]["headline"])

    def test_the_facilitator_can_bring_in_or_call_back_an_army(self):
        grain = self._realm("aethelgard")["alchemical_grain"]
        siege = self.engine.declare_attack("aethelgard", "sylvan", "siege")[2]
        self.assertTrue(self.engine.admin_siege(siege["id"], "cancel")[0])
        self.assertEqual(self._realm("aethelgard")["alchemical_grain"], grain)             # supplies returned
        self.assertEqual(self.engine.get_full_state()["sieges"], [])
        siege = self.engine.declare_attack("aethelgard", "sylvan", "siege")[2]
        self.assertTrue(self.engine.admin_siege(siege["id"], "arrive")[0])
        self.assertEqual(len(self.engine.db.get_state("battles")), 1)
        self.assertFalse(self.engine.admin_siege(siege["id"], "arrive")[0])

    def test_a_surprise_attack_is_immediate_but_costs_the_attacker_dearly(self):
        before = self._realm("aethelgard")
        ok, msg, battle = self.engine.declare_attack("aethelgard", "sylvan", "surprise")
        self.assertTrue(ok, msg)
        self.assertEqual(battle["mode"], "surprise")
        after = self._realm("aethelgard")
        changes = battle["private"]["attacker"]["changes"]
        self.assertLessEqual(changes["standing"], -15 - 6)                 # the extra price on top of the usual loss
        self.assertLessEqual(changes["stability"], -8)
        self.assertEqual(before["alchemical_grain"] - after["alchemical_grain"] + changes.get("grain", 0), 20)   # double supplies
        self.assertEqual(self.engine.get_full_state()["sieges"], [])

    def test_a_surprise_costs_more_than_a_siege_in_standing_for_the_same_result(self):
        import random
        losses = {}
        for mode in ("siege", "surprise"):
            self.setUp()
            random.seed(5)
            _, _, b = self.engine.declare_attack("aethelgard", "sylvan", mode) if mode == "surprise" else (None, None, None)
            if mode == "siege":
                s = self.engine.declare_attack("aethelgard", "sylvan", "siege")[2]
                random.seed(5)
                b = self.engine.admin_siege(s["id"], "arrive") and self.engine.db.get_state("battles")[0]
            losses[mode] = b["private"]["attacker"]["changes"].get("standing", 0)
        self.assertLess(losses["surprise"], losses["siege"])

    def test_the_preview_describes_both_ways_and_the_api_defaults_to_a_siege(self):
        ok, _, info = self.engine.battle_preview("aethelgard", "sylvan")
        self.assertTrue(info["modes"]["siege"]["can_attack"] and info["modes"]["surprise"]["can_attack"])
        self.assertEqual(info["modes"]["siege"]["seconds"], 120)
        self.assertEqual(info["modes"]["surprise"]["cost"], {"grain": 20})
        client = app.test_client()
        r = client.post("/api/war/attack", json={"realm_id": "aethelgard", "target_id": "sylvan"}).json
        self.assertTrue(r["success"])
        self.assertIn("siege", r)
        self.assertNotIn("battle", r)

    def test_a_poor_nation_can_afford_a_siege_but_not_a_surprise_attack(self):
        realms = self.engine.db.get_state("realms")
        next(r for r in realms if r["id"] == "aethelgard")["alchemical_grain"] = 15
        self.engine.db.set_state("realms", realms)
        _, _, info = self.engine.battle_preview("aethelgard", "sylvan")
        self.assertTrue(info["modes"]["siege"]["can_attack"])
        self.assertFalse(info["modes"]["surprise"]["can_attack"])
        self.assertIn("20 Grain", info["modes"]["surprise"]["reason"])

    def test_the_timer_loop_resolves_arriving_armies(self):
        self.engine.declare_attack("aethelgard", "sylvan", "siege")
        meta = self.engine.db.get_state("meta")
        meta.update(is_timer_running=True, turn_timer_end=time.time() + 400, turn_timer_remaining=400)
        self.engine.db.set_state("meta", meta)
        self.engine._tick()
        self.assertEqual(len(self.engine.db.get_state("battles")), 1)
