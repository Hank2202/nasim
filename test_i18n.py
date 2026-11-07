"""
Languages: the translator (i18n.py), the Czech catalogues in translations/cs, and how the game uses them.

The game is written in English and translated on its way to a screen, so these tests check three things:
the translator finds the right sentence and nothing else, the Czech catalogues cover the game, and the files that
go to every browser hold no secrets (secret missions, quiz answers).
"""

import json
import os
import re
import tempfile
import unittest

os.environ.setdefault("SUMMIT_DB_PATH", os.path.join(tempfile.mkdtemp(), "summit_under_test.db"))

import i18n
import wiki
from app import app, engine

ROOT = os.path.dirname(os.path.abspath(__file__))
CS = os.path.join(ROOT, "translations", "cs")
NATIONS = {"Sylvan Concordat", "Iron Val-Khor", "Solaris Ascendancy", "Umbral Enclave", "Aquila Maritime League", "Aethelgard Dominion"}


def load(name):
    with open(os.path.join(CS, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


class TestTranslator(unittest.TestCase):
    """The rules of i18n.Catalogue, on a small made-up catalogue."""

    def setUp(self):
        self.book = i18n.Catalogue({
            "Grain": "Obilí", "{n} Grain": "{n} obilí", "{n} votes": "{n} {n:hlas|hlasy|hlasů}",
            "Join {name}": "Připojit se k {name}", "Verdict: {a}.": "Verdikt: {a}.", "STABLE CONTINENT": "STABILNÍ KONTINENT",
            "The results are in. Talk it over.": "Výsledky jsou tu. Proberte je.", "You have {amount}": "Máte {amount}",
            "{x} ({y})": "{x} ({y})", "Full game": "Plná hra", "The Great Famine (MGV 2026)": "Velký hladomor (MGV 2026)",
        })
        self.t = self.book.translate

    def test_exact_text_and_symbols_around_it(self):
        self.assertEqual(self.t("Grain"), "Obilí")
        self.assertEqual(self.t("🌾 Grain"), "🌾 Obilí")
        self.assertEqual(self.t("  Grain: "), "  Obilí: ")
        self.assertEqual(self.t("Silk"), "Silk")                     # not in the catalogue: left as it is

    def test_numbers_and_czech_plurals(self):
        self.assertEqual(self.t("1 votes"), "1 hlas")
        self.assertEqual(self.t("3 votes"), "3 hlasy")
        self.assertEqual(self.t("7 votes"), "7 hlasů")
        self.assertEqual(self.t("+12 Grain"), "+12 obilí")
        self.assertEqual(self.t("many votes"), "many votes")       # {n} only stands for a number

    def test_names_and_amounts(self):
        self.assertEqual(self.t("Join Iron Val-Khor"), "Připojit se k Iron Val-Khor")
        self.assertEqual(self.t("Join · The Summit"), "Join · The Summit")      # not a name
        self.assertEqual(self.t("You have 40 Grain"), "Máte 40 obilí")
        self.assertEqual(self.t("You have answered"), "You have answered")

    def test_free_text_does_not_run_into_the_next_sentence(self):
        self.assertEqual(self.t("Verdict: STABLE CONTINENT. The results are in. Talk it over."),
                         "Verdikt: STABILNÍ KONTINENT. Výsledky jsou tu. Proberte je.")

    def test_the_sentences_of_a_long_text_are_known_on_their_own(self):
        self.assertEqual(self.t("Talk it over."), "Proberte je.")

    def test_a_text_is_split_before_a_pattern_without_words_is_tried(self):
        self.assertEqual(self.t("Full game · The Great Famine (MGV 2026)"), "Plná hra · Velký hladomor (MGV 2026)")

    def test_codes_in_game_data_are_left_alone(self):
        book = i18n.Catalogue({"working": "pracovní část", "Grain": "Obilí"})
        data = {"phase": "working", "realm_id": "Grain", "label": "Grain", "votes": {"sylvan": {"choice": "working"}},
                "mission_status": {"note": "Grain"}, "proposal_ids": ["Grain"]}
        out = i18n._walk(data, book)
        self.assertEqual(out["phase"], "working")
        self.assertEqual(out["realm_id"], "Grain")
        self.assertEqual(out["votes"]["sylvan"]["choice"], "working")
        self.assertEqual(out["proposal_ids"], ["Grain"])
        self.assertEqual(out["label"], "Obilí")
        self.assertEqual(out["mission_status"]["note"], "Obilí")    # a block with a code's name is still read for its texts

    def test_html_text_and_attributes_but_not_scripts(self):
        page = '<p title="Grain">Grain</p><script>const x = "Grain";</script><b>3 votes</b>'
        out = i18n.translate_page(page.replace("Grain", "Grain"), "cs")
        self.assertIn('title="Obilí"', out)
        self.assertIn(">Obilí<", out)
        self.assertIn('const x = "Grain";', out)


class TestCzechCatalogues(unittest.TestCase):
    """The Czech catalogues cover the game, and what goes to browsers holds no secrets."""

    @classmethod
    def setUpClass(cls):
        cls.book = i18n.catalogue("cs")
        with open(os.path.join(ROOT, "scenario_config.json"), encoding="utf-8") as f:
            cls.cfg = json.load(f)
        with open(os.path.join(ROOT, "lore_quiz.json"), encoding="utf-8") as f:
            cls.quiz = json.load(f)["questions"]

    def assertTranslated(self, text):
        self.assertNotEqual(self.book.translate(text), text, f"no Czech for: {text}")

    def test_placeholders_match_their_english(self):
        placeholder, plural = re.compile(r"\{(\w+)\}"), re.compile(r"\{(\w+):[^{}]*\}")
        for name in i18n.CATALOGUE_FILES:
            for key, value in load(name).items():
                names = placeholder.findall(key)
                self.assertEqual(len(names), len(set(names)), f"{name}: a placeholder twice in {key}")
                used = set(placeholder.findall(value)) | set(plural.findall(value))
                self.assertLessEqual(used, set(names), f"{name}: {value} uses a placeholder its English does not have")

    def test_every_nation_mission_and_scenario_has_czech(self):
        for realm in self.cfg["realms"]:
            for key in ("ethos", "backstory", "region_name", "difficulty_note"):
                if realm.get(key):
                    self.assertTranslated(realm[key])
            missions = [realm.get("public_mission") or {}] + list(realm.get("secret_missions", []))
            for m in missions:
                for key in ("title", "description", "objective"):
                    if m.get(key) and "{" not in m[key]:
                        self.assertTranslated(m[key])
        for scenario in self.cfg["scenarios"].values():
            self.assertTranslated(scenario["name"])
            self.assertTranslated(scenario["description"])
        for complexity in self.cfg["complexities"].values():
            self.assertTranslated(complexity["name"])
            for point in complexity.get("points", []):
                self.assertTranslated(point)

    def test_every_quiz_question_has_czech(self):
        for q in self.quiz:
            self.assertTranslated(q["question"])
            self.assertTranslated(q["explanation"])
            for option in q["options"]:
                if not (option in NATIONS or re.fullmatch(r"[\d ]+(AC)?", option) or re.fullmatch(r"[A-Z][a-z]+( [A-Z][a-z]+)+", option)
                        or option in {"Rootholm", "Helion", "Brinegate", "Lanternfall"}):
                    self.assertTranslated(option)

    def test_the_czech_encyclopedia_matches_the_english_one(self):
        english, czech = wiki.load_wiki("en"), wiki.load_wiki("cs")
        self.assertNotEqual(wiki.articles_path("cs"), wiki.articles_path("en"))
        self.assertEqual([a["slug"] for a in english["articles"]], [a["slug"] for a in czech["articles"]])
        for a, b in zip(english["articles"], czech["articles"]):
            self.assertEqual(a["see_also"], b["see_also"])
            self.assertEqual(len(a["sections"]), len(b["sections"]), a["slug"])
        self.assertEqual(wiki.validate("cs"), [])
        self.assertTrue(wiki.search("obili", "cs"), "searching without accents finds obilí")

    def test_files_sent_to_every_browser_hold_no_secrets(self):
        sent = json.dumps({**load("public"), **load("deck")}, ensure_ascii=False)
        secrets = []
        for realm in self.cfg["realms"]:
            for m in realm.get("secret_missions", []):
                secrets += [m.get("description", ""), m.get("objective", "")]
        for q in self.quiz:
            secrets += [q["question"], q["explanation"], q["options"][q["correct_index"]]]
        for text in secrets:
            if len(text) > 25:
                self.assertNotIn(text, sent)
                self.assertNotIn(self.book.translate(text), sent)


class TestLanguagesInTheGame(unittest.TestCase):
    """The game's language, a device's own choice, and what each screen gets."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        engine.update_settings({"language": "en"})

    def tearDown(self):
        engine.update_settings({"language": "en"})

    def test_english_screens_do_not_load_the_translator(self):
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn('<html lang="en">', page)
        self.assertNotIn("i18n.js", page)
        self.assertIn("Tap your nation", page)

    def test_the_game_language_and_a_device_of_its_own(self):
        self.client.post("/api/admin/settings", json={"language": "cs"})
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn('<html lang="cs">', page)
        self.assertIn("i18n.js", page)
        self.assertIn("Klepněte na svůj stát", page)
        self.assertEqual(self.client.get("/api/state").get_json()["language"], "cs")
        # One phone switches to English; the game stays Czech for everyone else
        resp = self.client.get("/lang/en", headers={"Referer": "http://localhost/realm/sylvan?x=1"})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/realm/sylvan?x=1"))
        self.assertIn("Tap your nation", self.client.get("/").get_data(as_text=True))
        other = app.test_client()
        self.assertIn("Klepněte na svůj stát", other.get("/").get_data(as_text=True))

    def test_the_language_switch_only_leads_back_into_the_game(self):
        for target in ("https://evil.example/x", "//evil.example/x", "/\\evil.example"):
            location = self.client.get("/lang/cs", query_string={"next": target}).headers["Location"]
            self.assertNotIn("evil.example", location.split("://", 1)[-1].split("/", 1)[0] if "://" in location else location[:2])
            self.assertFalse(location.startswith(("//", "/\\")), location)

    def test_game_data_is_translated_but_its_codes_are_not(self):
        self.client.post("/api/admin/settings", json={"language": "cs"})
        state = self.client.get("/api/state").get_json()
        self.assertEqual(state["meta"]["phase"], "working")
        self.assertIn("sylvan", [r["id"] for r in state["realms"]])
        self.assertTrue(any("NEÚRODA" in n.get("headline", "") for n in state["news_feed"]))
        quiz = self.client.get("/api/quiz/sylvan").get_json()
        self.assertEqual(self.client.get("/api/wiki/sylvan-concordat").get_json()["article"]["sections"][0]["heading"], "Dějiny")
        self.assertIsInstance(quiz, dict)

    def test_the_facilitators_texts_are_for_the_facilitator(self):
        app.config["TESTING"] = False
        try:
            body = self.client.get("/i18n/cs/deck.js").get_data(as_text=True)
            self.assertEqual(body, "window.i18n && window.i18n.add({});")
            self.assertIn("Zrušit", self.client.get("/i18n/cs/public.js").get_data(as_text=True))
        finally:
            app.config["TESTING"] = True

    def test_the_language_outlasts_a_restart_and_a_restored_game(self):
        engine.update_settings({"language": "cs"})
        snapshot = engine.db.dump_all() if hasattr(engine.db, "dump_all") else None
        self.assertFalse(engine._setup_differs_from_config())         # a chosen language alone is nothing to save
        engine.fresh_start()
        self.assertEqual(engine.game_language(), "cs")
        if snapshot is not None:
            engine.update_settings({"language": "en"})
            engine.restore_snapshot(snapshot)
            self.assertEqual(engine.game_language(), "en")              # the room's language, not the save's

    def test_the_results_report_in_czech(self):
        self.client.post("/api/admin/settings", json={"language": "cs"})
        self.client.post("/api/admin/summit/conclude", json={})
        page = self.client.get("/admin/report").get_data(as_text=True)
        self.assertIn('<html lang="cs">', page)
        self.assertIn("Konečné pořadí", page)


if __name__ == "__main__":
    unittest.main()
