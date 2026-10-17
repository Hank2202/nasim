"""
End-to-end click-through tests: the real server (with logins enforced) driven by a headless browser.

Run:   venv/bin/pip install -r requirements-dev.txt && venv/bin/python -m playwright install chromium
       venv/bin/python -m pytest -q test_e2e.py
Skipped automatically when Playwright is not installed (e.g. on the Render server).
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
expect = playwright_api.expect

ROOT = os.path.dirname(os.path.abspath(__file__))
ADMIN_PASSCODE = "e2e-pass"
PHONE = {"viewport": {"width": 390, "height": 844}, "has_touch": True}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    """Start a fresh game server on a free port with its own temporary database."""
    port = free_port()
    db = os.path.join(tempfile.mkdtemp(), "e2e.db")
    env = dict(os.environ, PORT=str(port), SUMMIT_DB_PATH=db, ADMIN_PASSCODE=ADMIN_PASSCODE,
               SECRET_KEY="e2e-secret", ALLOW_AUTH_PARAM="0")
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "app.py")], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/healthz", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield base
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def watch_errors(page):
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors


def admin_page(browser, base):
    page = browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
    page.goto(base + "/admin")
    page.fill("#admin-passcode", ADMIN_PASSCODE)
    page.click("#unlock-btn")
    expect(page.locator(".page-title")).to_have_text("Facilitator Command Deck")
    return page


def join(browser, base, realm_name, pin):
    """A phone joins a delegation from the lobby."""
    ctx = browser.new_context(**PHONE)
    page = ctx.new_page()
    errors = watch_errors(page)
    page.goto(base + "/")
    page.locator(".lobby-realm-card", has_text=realm_name).click()
    page.fill("#login-realm-pin", pin)
    page.locator("#pin-login-form button[type=submit]").click()
    expect(page.locator(".ribbon-name strong")).to_have_text(realm_name)
    return page, errors


def tab(page, name):
    page.locator(".bottom-nav-item", has_text=name).click()


def test_wrong_passcodes_are_refused(server, browser):
    page = browser.new_page()
    page.goto(server + "/admin")
    page.fill("#admin-passcode", "nope")
    page.click("#unlock-btn")
    expect(page.locator("#login-error")).to_be_visible()

    page.goto(server + "/")
    page.locator(".lobby-realm-card", has_text="Sylvan Concordat").click()
    page.fill("#login-realm-pin", "9999")
    page.locator("#pin-login-form button[type=submit]").click()
    expect(page.locator("#login-error-msg")).to_be_visible()
    page.close()


def test_full_round(server, browser):
    admin = admin_page(browser, server)
    sylvan, sylvan_errors = join(browser, server, "Sylvan Concordat", "1001")
    valkhor, valkhor_errors = join(browser, server, "Iron Val-Khor", "1002")

    # --- Trade: Sylvan offers 10 Grain for 10 Cores, Val-Khor accepts ----------------
    expect(sylvan.locator("#grain-val")).to_have_text("100")
    tab(sylvan, "Trade")
    sylvan.locator(".partner-chip", has_text="Iron Val-Khor").click()
    expect(sylvan.locator("#trade-preview-text")).to_contain_text("You give 10 Grain to Iron Val-Khor")
    sylvan.locator("#trade-form button[type=submit]").click()

    tab(valkhor, "Trade")
    offer = valkhor.locator("#incoming-trades-list .offer-card", has_text="Sylvan Concordat")
    expect(offer).to_be_visible(timeout=5000)
    offer.locator("button", has_text="Accept").click()
    tab(sylvan, "Realm")
    expect(sylvan.locator("#grain-val")).to_have_text("90", timeout=5000)
    expect(sylvan.locator("#cores-val")).to_have_text("35")

    # --- Motion from a template, co-sponsored, voted, passed ------------------------
    tab(sylvan, "Motions")
    sylvan.locator(".motion-template", has_text="Sovereign Relief Mission").click()
    expect(sylvan.locator("#proposal-title")).to_have_value("Spire Relief Mission")
    sylvan.locator("#proposal-form button[type=submit]").click()

    tab(valkhor, "Motions")
    card = valkhor.locator("#pending-motions-list .motion-card", has_text="Spire Relief Mission")
    expect(card).to_be_visible(timeout=5000)
    card.locator("button", has_text="Co-sponsor").click()
    expect(card.locator(".status-pill", has_text="On the ballot")).to_be_visible(timeout=5000)

    admin.locator("button", has_text="Convene Between-Rounds Plenary").click()
    for phone in (sylvan, valkhor):
        vote = phone.locator("#plenary-voting-actions-container button", has_text="SUPPORT")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
    admin.locator("button", has_text="Settle Plenary").click()
    tab(sylvan, "Motions")
    decided = sylvan.locator("#decided-motions-list .motion-card", has_text="Spire Relief Mission")
    expect(decided.locator(".status-pill", has_text="Passed")).to_be_visible(timeout=5000)

    assert sylvan_errors == [] and valkhor_errors == []
    admin.close()


def test_addressed_motion_and_game_master_question_stay_private(server, browser):
    admin = admin_page(browser, server)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    valkhor, _ = join(browser, server, "Iron Val-Khor", "1002")
    aquila, _ = join(browser, server, "Aquila Maritime League", "1005")

    # A motion offered only to Val-Khor: Val-Khor sees it, Aquila does not
    tab(sylvan, "Motions")
    sylvan.locator(".motion-template", has_text="General Sovereign Concordat").click()
    sylvan.fill("#proposal-title", "Quiet Grain Pact")
    sylvan.select_option("#proposal-target-realm", "val_khor")
    sylvan.locator("#proposal-submit").click()
    tab(valkhor, "Motions")
    expect(valkhor.locator("#pending-motions-list .motion-card", has_text="Quiet Grain Pact")).to_be_visible(timeout=5000)
    tab(aquila, "Motions")
    aquila.wait_for_timeout(1500)
    expect(aquila.locator("text=Quiet Grain Pact")).to_have_count(0)

    # A question to the game masters: no co-sponsor field, answered privately
    sylvan.locator(".motion-template", has_text="Question to the Game Masters").click()
    expect(sylvan.locator("#proposal-cosponsor-group")).to_be_hidden()
    sylvan.fill("#proposal-title", "Can grain be traded in Turn 3?")
    sylvan.fill("#proposal-desc", "Asking for a friend.")
    sylvan.locator("#proposal-submit", has_text="Send to the game masters").click()
    expect(sylvan.locator("#gm-questions-list")).to_contain_text("Waiting for an answer", timeout=5000)

    admin.locator(".admin-tab-btn", has_text="Resolutions").click()
    question = admin.locator("#gm-inbox .inset", has_text="Can grain be traded in Turn 3?")
    expect(question).to_be_visible(timeout=5000)
    question.locator("textarea").fill("Yes, until the working session ends.")
    question.locator("button", has_text="only").click()

    expect(sylvan.locator("#gm-questions-list")).to_contain_text("Yes, until the working session ends.", timeout=5000)
    expect(aquila.locator("text=Can grain be traded in Turn 3?")).to_have_count(0)
    assert errors == []
    admin.close()


def test_quiz_and_wiki(server, browser):
    phone, errors = join(browser, server, "Solaris Ascendancy", "1003")
    teammate, _ = join(browser, server, "Solaris Ascendancy", "1003")

    # Wiki: full-screen reading mode, internal links, close returns to the game
    tab(phone, "Wiki")
    expect(phone.locator(".nation-ribbon")).to_be_hidden()
    phone.locator("#wiki-body [data-wiki='salt-war']").first.click()
    expect(phone.locator(".wk-title")).to_have_text("Salt War")
    phone.locator(".wk-close").click()
    expect(phone.locator(".nation-ribbon")).to_be_visible()

    # Quiz: answer one question; the teammate's phone sees it answered too
    tab(phone, "Quiz")
    first = phone.locator("#quiz-container .quiz-card").first
    first.locator(".quiz-option").first.click()
    first.locator("button", has_text="Lock in").click()
    expect(phone.locator("#quiz-stat-open")).to_have_text("9", timeout=5000)

    tab(teammate, "Quiz")
    expect(teammate.locator("#quiz-stat-open")).to_have_text("9", timeout=5000)
    assert errors == []


def test_roster_change_reaches_phones_and_projector(server, browser):
    admin = admin_page(browser, server)
    phone, _ = join(browser, server, "Umbral Enclave", "1004")
    projector = browser.new_page(viewport={"width": 1280, "height": 720})
    projector_errors = watch_errors(projector)
    projector.goto(server + "/projector")
    expect(projector.locator(".spot-chip")).to_have_count(6, timeout=5000)

    admin.locator(".roster-chip", has_text="Aquila Maritime League").click()
    expect(projector.locator(".spot-chip")).to_have_count(5, timeout=5000)
    tab(phone, "Trade")
    expect(phone.locator(".partner-chip", has_text="Aquila")).to_have_count(0, timeout=5000)
    expect(phone.locator(".partner-chip")).to_have_count(4)

    admin.locator(".roster-chip", has_text="Aquila Maritime League").click()   # put it back
    expect(projector.locator(".spot-chip")).to_have_count(6, timeout=5000)
    assert projector_errors == []
    admin.close()


def test_saves_report_and_reflection(server, browser):
    admin = admin_page(browser, server)
    admin.locator(".admin-tab-btn", has_text="Saves").click()
    admin.locator("button", has_text="Save now").click()
    expect(admin.locator("#server-saves .inset").first).to_contain_text("Manual save", timeout=5000)
    expect(admin.locator("#browser-saves .inset").first).to_contain_text("Manual save", timeout=5000)

    # End the summit and run the debrief on the projector
    projector = browser.new_page(viewport={"width": 1280, "height": 720})
    errors = watch_errors(projector)
    projector.goto(server + "/projector")
    admin.evaluate("fetch('/api/admin/summit/conclude', {method: 'POST'})")
    expect(projector.locator("#proj-concluded-stage")).to_be_visible(timeout=5000)
    admin.locator(".admin-tab-btn", has_text="Pacing").click()
    admin.locator("button", has_text="Start reflection").click()
    expect(projector.locator("#reflection-question")).to_contain_text("How are you feeling", timeout=5000)
    admin.locator("button", has_text="Next question").click()
    expect(projector.locator("#reflection-kicker")).to_contain_text("question 2 of 12", timeout=5000)

    report = admin.context.new_page()
    report.goto(server + "/admin/report")
    expect(report.locator("h1")).to_contain_text("Results")
    expect(report.locator("text=Spire Relief Mission").first).to_be_visible()
    assert errors == []
    admin.close()


def test_map_quality_modes(server, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    errors = watch_errors(page)
    page.goto(server + "/projector")
    page.wait_for_function("window.projApp && window.projApp.map")
    sizes = page.evaluate("""() => ['low', 'balanced', 'high'].map(q => {
        projApp.map.setQuality(q);
        return [q, projApp.map.texture.width, projApp.map.quality];
    })""")
    assert sizes == [["low", 1200, "low"], ["balanced", 1800, "balanced"], ["high", 2700, "high"]]
    # the choice is remembered for the next visit
    page.reload()
    page.wait_for_function("window.projApp && window.projApp.map")
    assert page.evaluate("projApp.map.qualityMode") == "high"
    page.evaluate("projApp.map.setQuality('auto')")
    assert errors == []


def test_setup_screen_starts_a_new_summit(server, browser):
    admin = admin_page(browser, server)
    admin.goto(server + "/admin/setup")
    admin.locator("input[name=difficulty][value=gentle]").check()
    admin.fill("#working_min", "12")
    admin.locator("input[name=scenario][value=armageddon]").check()     # fills in its suggested event numbers
    expect(admin.locator("#large_per_turn")).to_have_value("3")
    admin.fill("#event_max", "7.5")
    admin.on("dialog", lambda d: d.accept())
    admin.locator("button", has_text="Start a new summit").click()
    expect(admin.locator(".page-title")).to_have_text("Facilitator Command Deck", timeout=5000)
    settings = admin.evaluate("fetch('/api/state').then(r => r.json()).then(s => s.game_settings)")
    assert settings["difficulty"] == "gentle" and settings["working_session_seconds"] == 720
    assert settings["scenario"] == "armageddon" and settings["large_events_per_turn"] == 3
    assert settings["minor_event_max"] == 7.5 and settings["minor_events_per_turn"] == 10
    admin.close()
