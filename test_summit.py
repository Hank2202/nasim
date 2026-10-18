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
import time
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
        self.assertIn("Borders fortified against unrest", result_str)

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

    def test_lore_quiz_correct_answer_awards_resource(self):
        """A correct answer credits the question's resource and records the claim."""
        q = self._q("q01")
        field = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk"}[q["reward_resource"]]
        before = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")[field]

        ok, msg, data = self.engine.submit_lore_quiz("sylvan", "q01", q["correct_index"])
        self.assertTrue(ok)
        self.assertEqual(data["explanation"], q["explanation"])

        after = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")
        self.assertEqual(after[field], before + q["reward_amount"])
        self.assertIn("q01", after["claimed_lore"])

        ok_dup, msg_dup, _ = self.engine.submit_lore_quiz("sylvan", "q01", q["correct_index"])
        self.assertFalse(ok_dup)
        self.assertIn("already answered", msg_dup)

    def test_lore_quiz_incorrect_answer_applies_penalty_and_lockout(self):
        """A wrong answer costs the reward's resource and amount, and locks the question for that realm only."""
        q = self._q("q02")
        wrong = (q["correct_index"] + 1) % 4
        field = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk"}[q["reward_resource"]]
        before = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")[field]

        ok, msg, data = self.engine.submit_lore_quiz("sylvan", "q02", wrong)
        self.assertFalse(ok)
        self.assertIn(f"-{q['reward_amount']}", msg)
        after = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")
        self.assertEqual(after[field], before - q["reward_amount"])   # same resource, same amount as the reward
        self.assertIn("q02", after["failed_lore"])

        ok_lock, msg_lock, _ = self.engine.submit_lore_quiz("sylvan", "q02", q["correct_index"])
        self.assertFalse(ok_lock)
        self.assertIn("Locked", msg_lock)

        # Same question is still open for every other nation (shared bank, per-realm attempts)
        ok_other, _, _ = self.engine.submit_lore_quiz("val_khor", "q02", q["correct_index"])
        self.assertTrue(ok_other)

    def test_quiz_turn_gating_and_no_answer_leak(self):
        quiz = self.engine.get_quiz_for_realm("aquila")
        self.assertEqual(quiz["current_turn"], 1)
        for item in quiz["questions"]:
            self.assertNotIn("correct_index", item)
            self.assertNotIn("explanation", item)
            if item["turn"] > 1:
                self.assertEqual(item["status"], "sealed")
                self.assertEqual(item["question"], "")
        later = next(i for i in quiz["questions"] if i["turn"] == 2)
        ok, msg, _ = self.engine.submit_lore_quiz("aquila", later["id"], 0)
        self.assertFalse(ok)
        self.assertIn("unlocks in Turn 2", msg)

    def test_quiz_bank_is_well_formed(self):
        import wiki
        from engine import load_quiz
        slugs = set(wiki.load_wiki()["by_slug"])
        qs = load_quiz()["questions"]
        self.assertGreaterEqual(len(qs), 30)
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
        self.assertIn(b"The nations at the summit", resp_auth.data)
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
        self.assertIn(b"modal-confirm-reset", resp_admin.data)
        self.assertIn(b"FACILITATOR ROOM SOUNDS", resp_admin.data)

        resp_realm = self.client.get("/realm/sylvan?auth=1")
        self.assertEqual(resp_realm.status_code, 200)
        self.assertIn(b"mobile-concluded-callout", resp_realm.data)
        self.assertIn(b"trade-note", resp_realm.data)
        self.assertIn(b"nav-motions-badge", resp_realm.data)
        self.assertIn(b"quiz-container", resp_realm.data)
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
        q = load_quiz()["questions"][0]
        listing = self.client.get("/api/quiz/sylvan").json
        self.assertTrue(listing["success"])
        self.assertNotIn("correct_index", listing["questions"][0])
        resp = self.client.post("/api/lore/quiz", json={
            "realm_id": "sylvan",
            "question_id": q["id"],
            "answer_index": q["correct_index"]
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertIn("reward_label", data["data"])

    def test_js_syntax_integrity(self):
        """Ensure the scripts in static/js/ are free of JavaScript syntax errors using macOS JavaScriptCore evaluator."""
        import subprocess
        cmd = [
            "osascript", "-l", "JavaScript", "-e",
            'var window = this; var document = { getElementById: function() { return null; }, querySelectorAll: function() { return []; }, addEventListener: function() {} }; eval($.NSString.stringWithContentsOfFileEncodingError("static/js/common.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/js/map.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/js/realm.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/js/projector.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/js/admin.js", $.NSUTF8StringEncoding, null).js); "OK"'
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
            self.assertIn(b"Facilitator Master Passcode", resp.data)

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
            self.assertIn(b"Master workspace", authed_resp.data)

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
        self.assertIn("capacity reached", data3["message"].lower())

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
        self.assertEqual(self.client.get("/admin?auth=1").data.count(b"Master workspace"), 0)

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
        engine.reset_simulation()

    def test_autosave_and_restore_round_trip(self):
        from app import engine
        engine._last_autosave = 0
        engine.get_full_state()                       # first poll triggers an autosave
        saves = self.client.get("/api/admin/saves").json["saves"]
        self.assertTrue(saves)
        engine.get_full_state()                       # no second autosave within 5 minutes
        self.assertEqual(len(self.client.get("/api/admin/saves").json["saves"]), len(saves))

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
        ok, _ = self.engine.update_settings({"working_session_seconds": 5, "minor_event_max": 99,
                                             "difficulty": "harsh", "scenario": "nope", "auto_advance": False})
        self.assertTrue(ok)
        s = self.engine.settings()
        self.assertEqual(s["working_session_seconds"], 60)
        self.assertEqual(s["minor_event_max"], 50)
        self.assertEqual(s["difficulty"], "harsh")
        self.assertEqual(s["grain_consumption"], 25)
        self.assertEqual(s["scenario"], "famine")
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

    def test_motion_limit_per_turn(self):
        app.config["TESTING"] = True
        for i in range(2):
            self.assertTrue(self.engine.draft_proposal("sylvan", f"M{i}", "x", "aid")[0])
        ok, msg, _ = self.engine.draft_proposal("sylvan", "M3", "x", "gm_question")
        self.assertFalse(ok)
        self.assertIn("limit is 2", msg)
        self.assertTrue(self.engine.draft_proposal("aquila", "Other nation", "x", "aid")[0])
        self.engine.update_settings({"motions_per_turn": 3})
        self.assertTrue(self.engine.draft_proposal("sylvan", "M3", "x", "aid")[0])
        self.engine.db.set_state("settings", {})
        self.engine.process_end_of_turn()                                  # a new turn, a new allowance
        self.assertTrue(self.engine.draft_proposal("sylvan", "Turn 2", "x", "aid")[0])


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
        self.assertIn("/?login=sylvan", resp.headers["Location"])
        self.assertIn("has_auth_sylvan=;", resp.headers.get("Set-Cookie", ""))  # lobby asks for the passcode again

    def test_browsers_do_not_keep_stale_copies(self):
        self.assertEqual(app.test_client().get("/static/js/realm.js").headers["Cache-Control"], "no-cache")
        self.assertEqual(app.test_client().get("/").headers["Cache-Control"], "no-cache")
        self.assertEqual(app.test_client().get("/api/state").headers["Cache-Control"], "no-store")
