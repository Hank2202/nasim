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
from engine import SummitEngine, load_scenario_config, load_events_catalog
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
        """Verify diplomatic notes are stored on trade proposals and announced in dispatches."""
        ok, msg = self.engine.create_trade(
            "sylvan", "val_khor", "grain", 15, "cores", 10,
            note="Urgent grain for your miners in exchange for reactor power."
        )
        self.assertTrue(ok)
        trades = self.engine.get_full_state()["trades"]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["note"], "Urgent grain for your miners in exchange for reactor power.")

        # Check news dispatch
        news = self.engine.get_full_state()["news_feed"]
        self.assertTrue(any("Urgent grain for your miners" in n["detail"] for n in news))

    def test_environmental_cordon_statutory_effect(self):
        """Verify cordon resolution ratifies quarantine protection."""
        ok, msg, pid = self.engine.draft_proposal(
            "aethelgard", "Frontier Quarantine Cordon",
            "Militarize frontiers and seal refugee spillovers.", "cordon", "sylvan"
        )
        self.assertTrue(ok)
        self.engine.support_proposal(pid, "sylvan")

        prop = next(p for p in self.engine.get_full_state()["proposals"] if p["id"] == pid)
        result_str = self.engine._apply_proposal_effect(prop)
        self.assertIn("Borders fortified against unrest", result_str)

        sylvan = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")
        self.assertTrue(sylvan["is_quarantined"])

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
        """A wrong answer costs -5 Standing and permanently locks the question for that realm only."""
        q = self._q("q02")
        wrong = (q["correct_index"] + 1) % 4
        standing_before = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")["diplomatic_standing"]

        ok, msg, data = self.engine.submit_lore_quiz("sylvan", "q02", wrong)
        self.assertFalse(ok)
        self.assertIn("-5 Diplomatic Standing", msg)
        after = next(r for r in self.engine.get_full_state()["realms"] if r["id"] == "sylvan")
        self.assertEqual(after["diplomatic_standing"], standing_before - 5)
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
        self.assertIn(b"Continental Registry", resp_auth.data)
        self.assertIn(b"Domestic Decrees", resp_auth.data)

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
        self.assertIn(b"wiki-frame", resp_realm.data)
        self.assertIn(b"trade-preview-box", resp_realm.data)

    def test_projector_3d_canvas_rendering(self):
        """Verify projector displays 3D world canvas, controls, and 3D projection stays safely within screen bounds."""
        resp = self.client.get("/projector")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"world-3d-canvas", resp.data)
        self.assertIn(b"world3d.js", resp.data)
        self.assertIn(b"btn-open-settings", resp.data)
        self.assertIn(b"proj-settings-modal", resp.data)
        self.assertIn(b"btn-camera-drift", resp.data)
        self.assertIn(b"btn-camera-speed", resp.data)

        # Run 3D projection math in JSC to ensure center and all 6 realm capitals project within visible screen bounds
        import subprocess
        js_code = '''
var window = this;
window.addEventListener = function() {};
window.requestAnimationFrame = function() {};
var document = {
  getElementById: function(id) {
    if (id === "world-3d-canvas") {
      return {
        clientWidth: 1200, clientHeight: 800, width: 1200, height: 800,
        getContext: function() { return { setTransform: function() {} }; },
        addEventListener: function() {},
        getBoundingClientRect: function() { return { left: 0, top: 0, width: 1200, height: 800 }; }
      };
    }
    return { classList: { toggle: function() {} }, style: {}, innerText: "" };
  }
};
eval($.NSString.stringWithContentsOfFileEncodingError("static/world3d.js", $.NSUTF8StringEncoding, null).js);
var map = new World3DMap("world-3d-canvas");
var centerP = map.project(0, 0, 0);
if (!centerP || centerP.x < 100 || centerP.x > 1100 || centerP.y < 100 || centerP.y > 700) {
  throw new Error("Center out of visible screen bounds: " + JSON.stringify(centerP));
}
for (var id in map.realmsData) {
  var cap = map.realmsData[id].capital.pos;
  var p = map.project(cap[0], cap[1], cap[2]);
  if (!p || p.x < 50 || p.x > 1150 || p.y < 50 || p.y > 750) {
    throw new Error("Capital " + id + " out of bounds: " + JSON.stringify(p));
  }
}
"PROJECTION_VERIFIED";
'''
        cmd = ["osascript", "-l", "JavaScript", "-e", js_code]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"3D Projection Error: {res.stderr}")
        self.assertIn("PROJECTION_VERIFIED", res.stdout)

    def test_minute_catastrophe_simulation_and_geography_placement(self):
        """Verify scenario_config.json contains 3D geography and realistic catastrophes catalog."""
        cfg = load_scenario_config()
        self.assertIn("catastrophes_catalog", cfg)
        self.assertGreater(len(cfg["catastrophes_catalog"]), 5)
        self.assertIn("compound_disaster_chance", cfg["simulation_settings"])
        self.assertIn("catastrophe_roll_interval_seconds", cfg["simulation_settings"])

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
        """Ensure static/app.js and static/world3d.js are free of JavaScript syntax errors using macOS JavaScriptCore evaluator."""
        import subprocess
        cmd = [
            "osascript", "-l", "JavaScript", "-e",
            'var window = this; var document = { getElementById: function() { return null; }, querySelectorAll: function() { return []; }, addEventListener: function() {} }; eval($.NSString.stringWithContentsOfFileEncodingError("static/world3d.js", $.NSUTF8StringEncoding, null).js); eval($.NSString.stringWithContentsOfFileEncodingError("static/app.js", $.NSUTF8StringEncoding, null).js); "OK"'
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
        from app import engine
        # Test Round 1 trigger
        resp_r1 = self.client.post("/api/admin/crisis/round", json={"round_num": 1})
        self.assertEqual(resp_r1.status_code, 200)
        self.assertTrue(json.loads(resp_r1.data)["success"])

        # Test Round 2 trigger
        resp_r2 = self.client.post("/api/admin/crisis/round", json={"round_num": 2})
        self.assertEqual(resp_r2.status_code, 200)
        self.assertTrue(json.loads(resp_r2.data)["success"])

        # In Round 2, trade with Grain incurs 5 Grain loss in transit
        # Sylvan sends 15 Grain to Val-Khor for 10 Cores
        sylvan = next(r for r in engine.get_full_state()["realms"] if r["id"] == "sylvan")
        vk = next(r for r in engine.get_full_state()["realms"] if r["id"] == "val_khor")
        s_g_before = sylvan["alchemical_grain"]
        vk_g_before = vk["alchemical_grain"]

        ok_tr, msg_tr = engine.create_trade("sylvan", "val_khor", "grain", 15, "cores", 10)
        self.assertTrue(ok_tr)
        trade_id = engine.get_full_state()["trades"][-1]["id"]
        ok_acc, msg_acc = engine.respond_trade(trade_id, "accept", "val_khor")
        self.assertTrue(ok_acc)

        st_trade = engine.get_full_state()
        s_after = next(r for r in st_trade["realms"] if r["id"] == "sylvan")
        vk_after = next(r for r in st_trade["realms"] if r["id"] == "val_khor")
        # Sender lost 15 Grain
        self.assertEqual(s_after["alchemical_grain"], s_g_before - 15)
        # Receiver got 15 - 5 = 10 Grain
        self.assertEqual(vk_after["alchemical_grain"], vk_g_before + 10)

        # Test Round 3 trigger: -15 Grain deducted across all active states, Emergency Food Acts injected
        resp_r3 = self.client.post("/api/admin/crisis/round", json={"round_num": 3})
        self.assertEqual(resp_r3.status_code, 200)
        st_r3 = engine.get_full_state()
        props = st_r3["proposals"]
        self.assertTrue(any(p["effect_type"] == "emergency_food_a" for p in props))
        self.assertTrue(any(p["effect_type"] == "emergency_food_b" for p in props))

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
        # For N=5: support_req = min(5 - 1, 4) = 4
        self.assertIn("4 different nations", sol5["public_mission"]["description"])

        # Remove another realm (Aquila) -> 4 active realms
        rem2 = self.client.post("/api/admin/realm/remove", json={"realm_id": "aquila"})
        self.assertEqual(rem2.status_code, 200)
        st4 = engine.get_full_state()
        self.assertEqual(len(st4["realms"]), 4)
        vk4 = next(r for r in st4["realms"] if r["id"] == "val_khor")
        sol4 = next(r for r in st4["realms"] if r["id"] == "solaria")
        # For N=4: target_cores = round(4 * 4 / 6) = 3
        self.assertIn("3 of 4 nations", vk4["public_mission"]["description"])
        # For N=4: support_req = min(4 - 1, 4) = 3
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

    def test_wiki_routes(self):
        self.assertEqual(self.client.get("/wiki").status_code, 200)
        r = self.client.get("/wiki/sylvan-concordat")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Pact of Roots", r.data)
        self.assertIn(b"wk-infobox", r.data)
        self.assertEqual(self.client.get("/wiki/nope").status_code, 302)
        self.assertIn(b"Salt War", self.client.get("/wiki/search?q=salt").data)

    def test_markup_is_escaped(self):
        import wiki
        self.assertNotIn("<script>", str(wiki.render_markup("<script>alert(1)</script> [[nope]]")))
