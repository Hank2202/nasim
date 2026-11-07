"""
End-to-end click-through tests: the real server (with logins enforced) driven by a headless browser.

Run:   venv/bin/pip install -r requirements-dev.txt && venv/bin/python -m playwright install chromium
       venv/bin/python -m pytest -q test_e2e.py
Skipped automatically when Playwright is not installed (e.g. on the Render server).
"""

import os
import re
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
    expect(page.locator("#admin-passcode")).to_have_count(0)      # the login page has gone
    if "/admin/setup" in page.url:            # before a game starts, login lands on the setup screen
        page.goto(base + "/admin")
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


def motion_builder(page):
    """The Motions tab shows the floor first; proposing a motion is one button further."""
    tab(page, "Motions")
    page.locator("#motion-new-btn").click()


def confirm(page):
    """Answer yes in the confirmation dialog (phones and facilitator alike)."""
    page.locator(".confirm-yes").wait_for()
    page.wait_for_timeout(400)                       # answers are ignored for a moment after the dialog opens
    page.locator(".confirm-yes").click()


def decline(page):
    page.locator(".confirm-no").wait_for()
    page.wait_for_timeout(400)
    page.locator(".confirm-no").click()


def reset_game(admin):
    """Start every test from a fresh Turn 1 (phones that were logged in before are logged out by the new game)."""
    admin.evaluate("fetch('/api/admin/reset', {method: 'POST'})")
    admin.wait_for_timeout(300)


def api(page, path, body=None):
    """POST to the game API from a logged-in page and return the JSON."""
    return page.evaluate("""([path, body]) => fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body || {})}).then(r => r.json())""", [path, body])


def state(page):
    return page.evaluate("fetch('/api/state').then(r => r.json())")


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


def test_login_before_the_game_opens_the_setup_screen(server, browser):
    page = browser.new_context().new_page()
    page.goto(server + "/admin")
    page.fill("#admin-passcode", ADMIN_PASSCODE)
    page.click("#unlock-btn")
    expect(page.locator(".page-title")).to_have_text("Summit setup", timeout=5000)
    page.goto(server + "/admin")
    expect(page.locator("#pregame-card")).to_contain_text("Before you start")
    expect(page.locator("#pregame-card a", has_text="Open setup")).to_be_visible()
    page.close()


def test_lobby_says_which_nations_are_easy_and_which_are_hard(server, browser):
    page = browser.new_page()
    page.goto(server + "/")
    expect(page.locator("#card-solaria .diff-badge")).to_contain_text("Easy")
    expect(page.locator("#card-val_khor .diff-badge")).to_contain_text("Hard")
    # the reason is part of the second step, next to the passcode
    page.locator("#card-val_khor").click()
    expect(page.locator("#modal-realm-detail .diff-note")).to_be_visible()
    expect(page.locator("#modal-realm-detail .diff-note")).to_contain_text("30 Grain")
    page.close()


def test_full_round(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    sylvan, sylvan_errors = join(browser, server, "Sylvan Concordat", "1001")
    valkhor, valkhor_errors = join(browser, server, "Iron Val-Khor", "1002")

    # --- Trade: Sylvan offers 10 Grain for 10 Cores, Val-Khor accepts (each step asks first) -----
    expect(sylvan.locator("#grain-val")).to_have_text("100")
    tab(sylvan, "Trade")
    sylvan.locator(".partner-chip", has_text="Iron Val-Khor").click()
    expect(sylvan.locator("#trade-preview-text")).to_contain_text("You give 10 Grain to Iron Val-Khor")
    sylvan.locator("#trade-form button[type=submit]").click()
    expect(sylvan.locator(".confirm-card")).to_contain_text("You give: 10 Grain")
    confirm(sylvan)

    tab(valkhor, "Trade")
    offer = valkhor.locator("#incoming-trades-list .offer-card", has_text="Sylvan Concordat")
    expect(offer).to_be_visible(timeout=5000)
    offer.locator("button", has_text="Accept").click()
    expect(valkhor.locator(".confirm-card")).to_contain_text("You receive: 10 Grain")
    confirm(valkhor)
    tab(sylvan, "Realm")
    expect(sylvan.locator("#grain-val")).to_have_text("90", timeout=5000)
    expect(sylvan.locator("#cores-val")).to_have_text("35")

    # --- Motion from a template, co-sponsored, voted, passed; its effect is applied by the game ----
    motion_builder(sylvan)
    sylvan.locator(".motion-template", has_text="Sovereign Relief Mission").click()
    expect(sylvan.locator("#proposal-title")).to_have_value("Spire Relief Mission")
    expect(sylvan.locator("#motion-preview")).to_contain_text("Sylvan Concordat gains 10 Standing")
    sylvan.locator("#proposal-form button[type=submit]").click()
    confirm(sylvan)

    tab(valkhor, "Motions")
    card = valkhor.locator("#pending-motions-list .motion-card", has_text="Spire Relief Mission")
    expect(card).to_be_visible(timeout=5000)
    card.locator("button", has_text="Co-sponsor").click()
    confirm(valkhor)
    expect(card.locator(".status-pill", has_text="On the ballot")).to_be_visible(timeout=5000)

    admin.locator("button", has_text="Convene the Assembly").click()
    confirm(admin)
    for phone in (sylvan, valkhor):
        vote = phone.locator("#plenary-voting-actions-container .vote-for")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
        confirm(phone)
    admin.locator("button", has_text="Settle the vote").click()
    confirm(admin)
    tab(sylvan, "Motions")
    decided = sylvan.locator("#decided-motions-list .motion-card", has_text="Spire Relief Mission")
    expect(decided.locator(".status-pill", has_text="Passed")).to_be_visible(timeout=5000)
    expect(decided).to_contain_text("Carried out: Sylvan Concordat +10 Standing")
    assert sylvan_errors == [] and valkhor_errors == []
    admin.close()


def test_every_action_can_be_cancelled(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    sylvan.locator(".decree", has_text="Grain Rationing").click()
    expect(sylvan.locator(".confirm-card")).to_contain_text("−15 Grain")
    decline(sylvan)
    sylvan.wait_for_timeout(500)
    expect(sylvan.locator("#grain-val")).to_have_text("100")
    sylvan.locator(".decree", has_text="Grain Rationing").click()
    sylvan.keyboard.press("Escape")                                      # Escape also cancels
    expect(sylvan.locator(".confirm-overlay")).to_have_count(0)
    sylvan.locator(".decree", has_text="Grain Rationing").click()
    confirm(sylvan)
    expect(sylvan.locator("#grain-val")).to_have_text("85", timeout=5000)

    # the facilitator is asked too
    api(admin, "/api/admin/clock", {"action": "resume"})
    admin.locator("#btn-end-turn-header").click()
    expect(admin.locator(".confirm-card")).to_contain_text("End this turn?")
    decline(admin)
    assert state(admin)["meta"]["current_turn"] == 1
    assert errors == []
    admin.close()


def test_motion_builder_applies_the_pact_automatically(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    umbra, _ = join(browser, server, "Umbral Enclave", "1004")

    motion_builder(sylvan)
    sylvan.locator(".motion-template", has=sylvan.locator(".motion-template-name", has_text="Resource Pact")).click()
    line = sylvan.locator(".pact-line").first
    line.locator(".pick-chips").nth(0).locator(".pick-chip", has_text="Sylvan Concordat").click()
    line.locator(".pick-chips").nth(1).locator(".pick-chip", has_text="Umbral Enclave").click()
    expect(sylvan.locator("#motion-preview")).to_contain_text("Sylvan Concordat gives 10 Grain", timeout=5000)
    expect(sylvan.locator("#motion-preview")).to_contain_text("shared equally by Umbral Enclave")
    line.locator("input[type=number]").fill("12")
    expect(sylvan.locator("#motion-preview")).to_contain_text("gives 12 Grain", timeout=5000)
    sylvan.fill("#proposal-title", "Grain for the Rift")
    sylvan.locator("#proposal-submit").click()
    expect(sylvan.locator(".confirm-card")).to_contain_text("If passed: Sylvan Concordat gives 12 Grain")
    confirm(sylvan)

    tab(umbra, "Motions")
    card = umbra.locator("#pending-motions-list .motion-card", has_text="Grain for the Rift")
    expect(card).to_be_visible(timeout=5000)
    expect(card).to_contain_text("gives 12 Grain")
    card.locator("button", has_text="Co-sponsor").click()
    confirm(umbra)

    admin.locator("button", has_text="Convene the Assembly").click()
    confirm(admin)
    for phone in (sylvan, umbra):
        vote = phone.locator("#plenary-voting-actions-container .vote-for")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
        confirm(phone)
    admin.locator("button", has_text="Settle the vote").click()
    confirm(admin)

    tab(sylvan, "Realm")
    expect(sylvan.locator("#grain-val")).to_have_text("88", timeout=5000)
    tab(umbra, "Realm")
    expect(umbra.locator("#grain-val")).to_have_text("52", timeout=5000)
    # and the facilitator sees what the motion does and what it did, without doing anything by hand
    admin.locator("[data-tab=tab-resolutions]").click()
    expect(admin.locator("#admin-resolutions-list")).to_contain_text("Carried out: Sylvan Concordat -12 Grain; Umbral Enclave +12 Grain")
    assert errors == []
    admin.close()


def test_quiz_one_timed_question_at_a_time(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    phone, errors = join(browser, server, "Solaris Ascendancy", "1003")
    teammate, _ = join(browser, server, "Solaris Ascendancy", "1003")

    # Wiki: full-screen reading mode, internal links, close returns to the game
    tab(phone, "Wiki")
    expect(phone.locator(".nation-ribbon")).to_be_hidden()
    phone.locator("#wiki-body [data-wiki='salt-war']").first.click()
    expect(phone.locator(".wk-title")).to_have_text("Salt War")
    phone.locator(".wk-close").click()
    expect(phone.locator(".nation-ribbon")).to_be_visible()

    # Quiz: nothing but the stake until the nation chooses to start
    tab(phone, "Quiz")
    stage = phone.locator("#quiz-stage")
    expect(stage).to_contain_text("Your next question", timeout=5000)
    expect(stage.locator(".quiz-option")).to_have_count(0)
    expect(stage).to_contain_text("15 seconds on the clock")
    stage.locator("button", has_text="Start the clock").click()                  # the player chooses when it starts, no extra dialog
    expect(phone.locator(".confirm-card")).to_have_count(0)
    expect(stage.locator(".quiz-live .quiz-option")).to_have_count(4, timeout=5000)
    expect(stage.locator("#quiz-clock")).not_to_have_text("0")
    assert 1 <= int(stage.locator("#quiz-clock").inner_text()) <= 15

    # a teammate's phone shows the same open question and the same clock
    tab(teammate, "Quiz")
    expect(teammate.locator(".quiz-live .quiz-q")).to_have_text(stage.locator(".quiz-q").inner_text(), timeout=5000)

    stage.locator(".quiz-option").first.click()                              # tapping answers at once
    expect(stage.locator(".status-pill")).to_be_visible(timeout=5000)
    expect(stage).to_contain_text("Read the article")
    expect(stage.locator("button", has_text="Next question")).to_be_visible()
    expect(phone.locator("#quiz-history-card")).to_be_hidden()               # the result is shown above, not repeated below
    stage.locator("button", has_text="Next question").click()
    expect(stage).to_contain_text("Your next question")                          # the next one waits until the player starts it
    expect(stage.locator(".quiz-option")).to_have_count(0)
    expect(stage.locator("button", has_text="Start the clock")).to_be_visible()

    # the news says nothing about individual answers
    news = [n["headline"] for n in state(admin)["news_feed"]]
    assert not any("SCHOLARLY" in h for h in news)
    assert errors == []
    admin.close()


def test_quiz_clock_runs_out(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    api(admin, "/api/admin/settings", {"quiz_seconds": 5})
    phone, errors = join(browser, server, "Umbral Enclave", "1004")
    tab(phone, "Quiz")
    stage = phone.locator("#quiz-stage")
    stage.locator("button", has_text="Start the clock").click()
    expect(stage.locator(".quiz-live")).to_be_visible(timeout=5000)
    expect(stage).to_contain_text("Out of time", timeout=15000)              # settled by the server a moment after the deadline
    expect(phone.locator("#quiz-stat-wrong")).to_have_text("1")
    api(admin, "/api/admin/settings", {"quiz_seconds": 15})
    assert errors == []
    admin.close()


def test_attack_with_animation_on_the_projector(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    projector = browser.new_page(viewport={"width": 1280, "height": 720})
    projector_errors = watch_errors(projector)
    projector.goto(server + "/projector")
    expect(projector.locator(".spot-chip")).to_have_count(6, timeout=5000)
    aethelgard, errors = join(browser, server, "Aethelgard Dominion", "1006")
    sylvan, sylvan_errors = join(browser, server, "Sylvan Concordat", "1001")

    # Attacks unlock in Turn 2
    expect(aethelgard.locator("#war-status")).to_contain_text("allowed from Turn 2", timeout=5000)
    api(admin, "/api/admin/turn/next")
    expect(aethelgard.locator("#war-status")).to_contain_text("1 more time", timeout=8000)
    expect(aethelgard.locator("#war-weather")).to_contain_text("this turn")
    assert aethelgard.locator("#war-siege-btn").is_disabled() and aethelgard.locator("#war-surprise-btn").is_disabled()
    aethelgard.locator(".war-chip", has_text="Sylvan Concordat").click()
    expect(aethelgard.locator(".scout-odds").first).to_be_visible(timeout=5000)
    expect(aethelgard.locator("#war-scout")).to_contain_text("Their Military:")
    expect(aethelgard.locator("#war-scout")).to_contain_text("What your scouts could find out")
    assert "luck" not in aethelgard.locator("#war-scout").inner_text().lower()
    expect(aethelgard.locator("#war-scout")).to_contain_text("Siege")
    expect(aethelgard.locator("#war-scout")).to_contain_text("Surprise attack")
    assert not aethelgard.locator("#war-surprise-btn").is_disabled()
    aethelgard.locator("#war-surprise-btn").click()
    expect(aethelgard.locator(".confirm-card")).to_contain_text("by surprise")
    confirm(aethelgard)

    # the attacker's phone, the defender's phone and the projector all show the battle
    expect(aethelgard.locator(".bs-modal .bs")).to_be_visible(timeout=5000)
    expect(aethelgard.locator(".bs-modal .bs.bs-done")).to_be_visible(timeout=14000)
    expect(aethelgard.locator(".bs-modal-extra")).to_contain_text("How it went for you (attacking)")
    expect(sylvan.locator(".bs-modal-extra")).to_contain_text("How it went for you (defending)", timeout=6000)
    expect(projector.locator(".atlas-side.battling #battle-stage .bs")).to_be_visible(timeout=6000)
    expect(projector.locator("#spotlight")).to_be_hidden()
    expect(projector.locator("#battle-stage")).to_contain_text("Aethelgard Dominion")
    expect(projector.locator("#battle-stage .bs-done")).to_be_visible(timeout=14000)
    expect(projector.locator("#battle-stage .bs-spoils")).to_be_visible()

    # one march per turn; the facilitator sees both sides' numbers
    aethelgard.locator(".bs-modal #bs-close").click()
    expect(aethelgard.locator("#war-status")).to_contain_text("0 more times", timeout=8000)
    admin.locator(".admin-tab-btn", has_text="Events").click()
    expect(admin.locator("#admin-war-log")).to_contain_text("Aethelgard Dominion")
    expect(admin.locator("#admin-war-log")).to_contain_text("readiness")
    expect(admin.locator("#admin-war-log")).to_contain_text("luck")                 # only the facilitator sees the luck
    assert errors == [] and sylvan_errors == [] and projector_errors == []
    admin.close()


def test_a_siege_is_announced_and_arrives_later(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    projector = browser.new_page(viewport={"width": 1280, "height": 720})
    projector_errors = watch_errors(projector)
    projector.goto(server + "/projector")
    aethelgard, errors = join(browser, server, "Aethelgard Dominion", "1006")
    sylvan, sylvan_errors = join(browser, server, "Sylvan Concordat", "1001")
    api(admin, "/api/admin/turn/next")
    expect(aethelgard.locator("#war-status")).to_contain_text("1 more time", timeout=8000)
    aethelgard.locator(".war-chip", has_text="Sylvan Concordat").click()
    expect(aethelgard.locator("#war-siege-btn")).to_be_enabled(timeout=5000)
    aethelgard.locator("#war-siege-btn").click()
    expect(aethelgard.locator(".confirm-card")).to_contain_text("is warned at once")
    confirm(aethelgard)

    # everyone is told: the target's phone raises the alarm, the projector shows the countdown
    expect(sylvan.locator("#war-sieges .siege-row.danger")).to_contain_text("Aethelgard Dominion marches on", timeout=8000)
    expect(sylvan.locator("#war-sieges .siege-eta")).to_contain_text(":")
    expect(aethelgard.locator("#war-sieges")).to_contain_text("Your army")
    expect(projector.locator("#siege-banner")).to_contain_text("Aethelgard Dominion", timeout=8000)
    assert state(admin)["battles"] == []                                      # nothing is fought yet

    # the facilitator can bring the army in at once
    admin.locator(".admin-tab-btn", has_text="Events").click()
    admin.locator("#admin-sieges button", has_text="Arrive now").click()
    confirm(admin)
    expect(projector.locator(".atlas-side.battling #battle-stage .bs")).to_be_visible(timeout=8000)
    expect(sylvan.locator("#war-sieges .siege-row")).to_have_count(0, timeout=8000)
    assert errors == [] and sylvan_errors == [] and projector_errors == []
    admin.close()


def test_clock_console_works_in_every_phase(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    admin.locator("[data-tab=tab-pacing]").click()
    expect(admin.locator("#clock-label")).to_have_text("Working session")
    admin.fill("#clock-min", "2")
    admin.fill("#clock-sec", "30")
    admin.locator("button", has_text="Set this time").click()
    expect(admin.locator(".confirm-card")).to_contain_text("02:30")
    confirm(admin)
    expect(admin.locator("#clock-big")).to_have_text("02:30", timeout=5000)
    admin.locator(".clock-console button", has_text="−1 min").click()
    expect(admin.locator("#clock-big")).to_have_text("01:30", timeout=5000)
    admin.locator("#clock-resume").click()
    expect(admin.locator("#clock-state")).to_have_text("running", timeout=5000)
    admin.locator("#clock-pause").click()
    expect(admin.locator("#clock-state")).to_have_text("stopped", timeout=5000)

    # the same console after the summit: a free countdown for the debrief
    api(admin, "/api/admin/summit/conclude")
    expect(admin.locator("#clock-label")).to_have_text("Timer", timeout=5000)
    admin.fill("#clock-min", "0")
    admin.fill("#clock-sec", "45")
    admin.locator("button", has_text="Set this time").click()
    confirm(admin)
    expect(admin.locator("#clock-big")).to_have_text("00:45", timeout=5000)
    admin.locator("#clock-resume").click()
    expect(admin.locator("#clock-state")).to_have_text("running", timeout=5000)
    projector = browser.new_page(viewport={"width": 1280, "height": 720})
    projector.goto(server + "/projector")
    admin.close()
    projector.close()


def test_bulk_and_typed_resource_changes(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    umbra, errors = join(browser, server, "Umbral Enclave", "1004")
    admin.locator("[data-tab=tab-resources]").click()
    card = admin.locator("#bulk-card")
    card.locator(".bulk-row input[type=number]").fill("25")
    card.locator(".bulk-nation", has_text="Umbral Enclave").click()
    card.locator(".bulk-nation", has_text="Aquila Maritime League").click()
    expect(card.locator("#bulk-preview")).to_contain_text("Umbral Enclave: Grain 40 → 65")
    expect(card.locator("#bulk-preview")).to_contain_text("Aquila Maritime League: Grain 50 → 75")
    card.locator("button", has_text="Apply these changes").click()
    expect(admin.locator(".confirm-card")).to_contain_text("Change 2 nations?")
    confirm(admin)
    expect(umbra.locator("#grain-val")).to_have_text("65", timeout=6000)

    # a typed value in the telemetry table: type, Enter, confirm
    cell = admin.locator("input.inline-num-input[data-realm=umbra][data-field=echo_silk]")
    cell.fill("77")
    cell.press("Enter")
    expect(admin.locator(".confirm-card")).to_contain_text("From 30 to 77")
    confirm(admin)
    expect(umbra.locator("#silk-val")).to_have_text("77", timeout=6000)
    # saying no puts the old value back
    cell = admin.locator("input.inline-num-input[data-realm=umbra][data-field=echo_silk]")
    cell.fill("5")
    cell.press("Enter")
    decline(admin)
    expect(cell).to_have_value("77")
    assert errors == []
    admin.close()


def test_a_mistaken_change_can_be_reversed_from_the_action_log(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    umbra, errors = join(browser, server, "Umbral Enclave", "1004")
    admin.locator("[data-tab=tab-resources]").click()
    card = admin.locator("#bulk-card")
    card.locator(".bulk-row input[type=number]").fill("25")
    card.locator(".bulk-nation", has_text="Umbral Enclave").click()
    card.locator("button", has_text="Apply these changes").click()
    confirm(admin)
    expect(umbra.locator("#grain-val")).to_have_text("65", timeout=6000)

    entry = admin.locator("#journal-list .journal-entry").first
    expect(entry).to_contain_text("Umbral Enclave: Grain 40 → 65", timeout=8000)
    entry.locator("button", has_text="Reverse this change").click()
    expect(admin.locator(".confirm-card")).to_contain_text("Reverse")
    confirm(admin)
    expect(umbra.locator("#grain-val")).to_have_text("40", timeout=6000)
    expect(admin.locator("#journal-list .journal-entry").first).to_contain_text("Reversed", timeout=6000)
    assert errors == []
    admin.close()


def test_the_facilitator_sees_and_edits_the_modifiers_of_each_nation(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    admin.locator("[data-tab=tab-resources]").click()
    admin.locator("#tab-resources details summary", has_text="modifiers").click()
    card = admin.locator("#modifiers-list .mod-card", has_text="Umbral Enclave")
    expect(card).to_be_visible(timeout=6000)
    expect(card).to_contain_text("votes")
    before = int(admin.evaluate("fetch('/api/state').then(r => r.json()).then(s => s.realms.find(r => r.id === 'umbra').assembly_votes)"))
    card.locator("#mod-umbra-votes").fill("2")
    card.locator("button", has_text="Save modifiers").click()
    expect(admin.locator(".confirm-card")).to_contain_text("Umbral Enclave")
    confirm(admin)
    expect(admin.locator("#modifiers-list .mod-card", has_text="Umbral Enclave")).to_contain_text(f"{before + 2} votes", timeout=6000)
    # the players never see the war adjustments
    assert "modifiers" not in sylvan.evaluate("fetch('/api/state').then(r => r.text())")
    assert errors == []
    admin.close()


def test_open_motion_is_carried_out_by_the_game_masters(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    umbra, _ = join(browser, server, "Umbral Enclave", "1004")
    motion_builder(sylvan)
    sylvan.locator(".motion-template", has=sylvan.locator(".motion-template-name", has_text="Open Motion")).click()
    expect(sylvan.locator("#motion-preview")).to_contain_text("carry", timeout=5000)
    sylvan.fill("#proposal-title", "A feast for all")
    sylvan.fill("#proposal-desc", "Every nation shares a feast; the game masters decide what it costs.")
    sylvan.locator("#proposal-submit").click()
    confirm(sylvan)

    tab(umbra, "Motions")
    card = umbra.locator("#pending-motions-list .motion-card", has_text="A feast for all")
    expect(card).to_be_visible(timeout=5000)
    card.locator("button", has_text="Co-sponsor").click()
    confirm(umbra)

    admin.locator("button", has_text="Convene the Assembly").click()
    confirm(admin)
    for phone in (sylvan, umbra):
        vote = phone.locator("#plenary-voting-actions-container .vote-for")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
        confirm(phone)
    admin.locator("button", has_text="Settle the vote").click()
    confirm(admin)

    admin.locator("[data-tab=tab-resolutions]").click()
    item = admin.locator("#gm-inbox .inset", has_text="A feast for all")
    expect(item).to_contain_text("carry it out", timeout=6000)
    item.locator("textarea").fill("Everyone gets 5 Grain from the royal stores")
    item.locator("button", has_text="Mark as carried out").click()
    confirm(admin)
    expect(admin.locator("#gm-inbox .inset", has_text="A feast for all")).to_contain_text("Carried out", timeout=6000)
    tab(sylvan, "Motions")
    expect(sylvan.locator("#decided-motions-list")).to_contain_text("Everyone gets 5 Grain from the royal stores", timeout=8000)
    assert errors == []
    admin.close()


def test_roster_change_reaches_phones_and_projector(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    phone, _ = join(browser, server, "Umbral Enclave", "1004")
    projector = browser.new_page(viewport={"width": 1280, "height": 720})
    projector_errors = watch_errors(projector)
    projector.goto(server + "/projector")
    expect(projector.locator(".spot-chip")).to_have_count(6, timeout=5000)

    admin.locator("[data-tab=tab-access]").click()
    admin.locator(".roster-chip", has_text="Aquila Maritime League").click()
    confirm(admin)
    expect(projector.locator(".spot-chip")).to_have_count(5, timeout=5000)
    tab(phone, "Trade")
    expect(phone.locator(".partner-chip", has_text="Aquila")).to_have_count(0, timeout=5000)
    expect(phone.locator(".partner-chip")).to_have_count(4)

    admin.locator(".roster-chip", has_text="Aquila Maritime League").click()   # put it back
    confirm(admin)
    expect(projector.locator(".spot-chip")).to_have_count(6, timeout=5000)
    assert projector_errors == []
    admin.close()


def test_addressed_motion_and_game_master_question(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    valkhor, _ = join(browser, server, "Iron Val-Khor", "1002")
    aquila, _ = join(browser, server, "Aquila Maritime League", "1005")

    # A motion offered only to Val-Khor: Val-Khor sees it, Aquila does not
    motion_builder(sylvan)
    sylvan.locator(".motion-template", has_text="General Sovereign Concordat").click()
    sylvan.fill("#proposal-title", "Quiet Grain Pact")
    sylvan.select_option("#proposal-target-realm", "val_khor")
    sylvan.locator("#proposal-submit").click()
    confirm(sylvan)
    tab(valkhor, "Motions")
    expect(valkhor.locator("#pending-motions-list .motion-card", has_text="Quiet Grain Pact")).to_be_visible(timeout=5000)
    tab(aquila, "Motions")
    aquila.wait_for_timeout(1500)
    expect(aquila.locator("text=Quiet Grain Pact")).to_have_count(0)

    # A question to the game masters is a motion: co-sponsored, voted, then answered for everyone
    aquila.locator("#motion-new-btn").click()
    aquila.locator(".motion-template", has_text="Question to the Game Masters").click()
    expect(aquila.locator(".edit-hint")).to_be_visible()                 # templates are clearly editable
    aquila.fill("#proposal-title", "Can grain be traded in Turn 3?")
    aquila.fill("#proposal-desc", "Asking for a friend.")
    aquila.locator("#proposal-submit").click()
    confirm(aquila)
    card = valkhor.locator("#pending-motions-list .motion-card", has_text="Can grain be traded in Turn 3?")
    expect(card).to_be_visible(timeout=5000)
    card.locator("button", has_text="Co-sponsor").click()
    confirm(valkhor)
    expect(card.locator(".status-pill", has_text="On the ballot")).to_be_visible(timeout=5000)

    admin.locator("[data-tab=tab-resolutions]").click()
    question = admin.locator("#gm-inbox .inset", has_text="Can grain be traded in Turn 3?")
    expect(question).to_contain_text("waiting for the Assembly vote", timeout=5000)
    admin.locator("[data-tab=tab-pacing]").click()
    admin.locator("button", has_text="Convene the Assembly").click()
    confirm(admin)
    for phone in (aquila, valkhor):
        vote = phone.locator("#plenary-voting-actions-container .vote-for")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
        confirm(phone)
    admin.locator("button", has_text="Settle the vote").click()
    confirm(admin)

    admin.locator("[data-tab=tab-resolutions]").click()
    expect(question.locator("textarea")).to_be_visible(timeout=5000)
    question.locator("textarea").fill("Yes, until the working session ends.")
    question.locator("button", has_text="Publish answer").click()
    confirm(admin)

    tab(sylvan, "Motions")
    decided = sylvan.locator("#decided-motions-list .motion-card", has_text="Can grain be traded in Turn 3?")
    expect(decided).to_contain_text("Yes, until the working session ends.", timeout=5000)
    assert errors == []
    admin.close()


def test_saves_report_and_reflection(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    api(admin, "/api/proposal/create", {"proposer_id": "sylvan", "title": "Spire Relief Mission", "description": "terms", "effect_type": "aid"})
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
    admin.locator("[data-tab=tab-pacing]").click()
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
    api(admin, "/api/admin/clock", {"action": "resume"})         # a game is under way: only then is there something to start over from
    admin.goto(server + "/admin/setup")
    admin.locator("#setup-more summary").click()
    admin.fill("#working_min", "12")
    admin.fill("#quiz_seconds", "12")
    admin.locator("#attacks_from_turn").fill("3")
    admin.locator("input[name=scenario][value=armageddon]").check()     # fills in its suggested event numbers
    expect(admin.locator("#large_per_turn")).to_have_value("3")
    expect(admin.locator("#grain_per_turn")).to_have_value("20")
    admin.fill("#grain_per_turn", "25")
    admin.fill("#event_max", "7.5")
    admin.locator("button", has_text="Start a new summit").click()
    confirm(admin)
    expect(admin.locator(".page-title")).to_have_text("Facilitator Command Deck", timeout=5000)
    settings = state(admin)["game_settings"]
    assert settings["grain_consumption"] == 25 and settings["working_session_seconds"] == 720
    assert settings["scenario"] == "armageddon" and settings["large_events_per_turn"] == 3
    assert settings["minor_event_max"] == 7.5 and settings["minor_events_per_turn"] == 10
    assert settings["quiz_seconds"] == 12 and settings["attacks_from_turn"] == 3
    admin.close()


def full_game(admin):
    """Back to the full game, for whichever test runs next."""
    api(admin, "/api/admin/settings", {"complexity": "full", "scenario": "famine", "working_session_seconds": 1200, "grain_consumption": 20,
                                       "good_news_percent": 50, "minor_events_per_turn": 6, "minor_event_max": 5, "large_events_per_turn": 0})
    reset_game(admin)


def simplified_game(admin):
    api(admin, "/api/admin/settings", {"complexity": "simplified", "scenario": "famine", "grain_consumption": 20, "good_news_percent": 50,
                                       "minor_events_per_turn": 0, "minor_event_max": 5, "large_events_per_turn": 0})
    reset_game(admin)


def test_setup_screen_offers_two_difficulty_settings(server, browser):
    admin = admin_page(browser, server)
    errors = watch_errors(admin)
    full_game(admin)
    admin.goto(server + "/admin/setup")
    expect(admin.locator("input[name=difficulty]")).to_have_count(0)     # the old third setting is gone
    expect(admin.locator("input[name=complexity]")).to_have_count(2)
    expect(admin.locator("input[name=scenario]")).to_have_count(3)
    expect(admin.locator("input[name=complexity][value=full]")).to_be_checked()
    expect(admin.locator("#setup-more-summary")).to_contain_text("20 min sessions")     # closed, but it says what is in it
    admin.locator("#setup-more summary").click()

    # Fields of mechanics the simplified game does not have disappear when it is chosen
    expect(admin.locator("#quiz_seconds")).to_be_visible()
    expect(admin.locator("#attacks_enabled")).to_be_visible()
    expect(admin.locator("#debate_min")).to_be_visible()
    admin.locator("input[name=complexity][value=simplified]").check()
    expect(admin.locator("#quiz_seconds")).to_be_hidden()
    expect(admin.locator("#attacks_enabled")).to_be_hidden()
    expect(admin.locator("#debate_min")).to_be_hidden()
    expect(admin.locator(".complexity-choice", has_text="Simplified")).to_contain_text("+20 Grain")

    # Each scenario fills in its own numbers
    admin.locator("input[name=scenario][value=open]").check()
    expect(admin.locator("#grain_per_turn")).to_have_value("15")
    expect(admin.locator("#good_news")).to_have_value("65")
    admin.locator("input[name=scenario][value=famine]").check()
    expect(admin.locator("#grain_per_turn")).to_have_value("20")

    # A phone already logged in follows the change while no game has started: same login, the other kind of game
    sylvan, phone_errors = join(browser, server, "Sylvan Concordat", "1001")
    expect(sylvan.locator(".bottom-nav-item", has_text="Quiz")).to_have_count(1)
    expect(sylvan.locator("#grain-val")).to_have_text("100")
    admin.locator("button", has_text="Save settings").click()
    expect(admin.locator(".realm-secrets").first).to_have_text("1", timeout=5000)
    expect(sylvan.locator(".bottom-nav-item", has_text="Quiz")).to_have_count(0, timeout=8000)
    expect(sylvan.locator("#grain-val")).to_have_text("120", timeout=5000)

    # The page remembers the choice, and the fields stay hidden after a reload
    admin.reload()
    admin.locator("#setup-more summary").click()
    expect(admin.locator("input[name=complexity][value=simplified]")).to_be_checked()
    expect(admin.locator("#quiz_seconds")).to_be_hidden()
    assert errors == [] and phone_errors == []
    full_game(admin)
    admin.close()


def test_a_running_game_keeps_its_complexity(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    api(admin, "/api/admin/clock", {"action": "resume"})
    admin.goto(server + "/admin/setup")
    expect(admin.locator(".callout.warn")).to_contain_text("only changes with a new summit")
    admin.locator("input[name=complexity][value=simplified]").check()
    admin.locator("button", has_text="Save settings").click()
    expect(admin.locator(".toast", has_text="next new summit")).to_be_visible(timeout=5000)
    assert state(admin)["game_settings"]["rules"]["id"] == "full"
    admin.locator("button", has_text="Start a new summit").click()
    confirm(admin)
    expect(admin.locator(".page-title")).to_have_text("Facilitator Command Deck", timeout=5000)
    assert state(admin)["game_settings"]["rules"]["id"] == "simplified"
    expect(admin.locator("#admin-mode-pill")).to_contain_text("Simplified")
    full_game(admin)
    admin.close()


def test_simplified_game_from_start_to_finish(server, browser):
    admin = admin_page(browser, server)
    admin_errors = watch_errors(admin)
    simplified_game(admin)
    admin.reload()
    expect(admin.locator("#admin-mode-pill")).to_contain_text("Simplified")
    sylvan, sylvan_errors = join(browser, server, "Sylvan Concordat", "1001")
    umbra, umbra_errors = join(browser, server, "Umbral Enclave", "1004")

    # --- Fewer things on the phone ------------------------------------------------------------------
    expect(sylvan.locator(".bottom-nav-item")).to_have_count(5)
    expect(sylvan.locator(".bottom-nav-item", has_text="Quiz")).to_have_count(0)
    expect(sylvan.locator("#war-section")).to_have_count(0)
    expect(sylvan.locator("#vitality-bar")).to_have_count(0)
    expect(sylvan.locator(".decree")).to_have_count(4)
    expect(sylvan.locator(".decree", has_text="Grain Rationing")).to_have_count(0)

    # --- Resources make up for the quiz, and the phone says where things stand ---------------------
    expect(sylvan.locator("#grain-val")).to_have_text("120")
    expect(sylvan.locator("#cores-val")).to_have_text("35")
    expect(sylvan.locator("#silk-val")).to_have_text("40")
    expect(sylvan.locator("#food-forecast")).to_contain_text("enough Grain for the 3 meals left")
    sylvan.locator(".ribbon-help").click()
    expect(sylvan.locator(".sheet-card .verdict-rules")).to_contain_text("every nation has at least 50 Stability")
    expect(sylvan.locator(".sheet-card .verdict-rules")).to_contain_text("average Standing of all nations is at least 50")
    sylvan.keyboard.press("Escape")
    sylvan.locator(".vital[data-explain=stability]").click()
    expect(sylvan.locator(".sheet-card")).to_contain_text("every nation needs at least 50 at the end")
    sylvan.keyboard.press("Escape")
    expect(umbra.locator("#food-forecast")).to_contain_text("enough Grain")
    expect(sylvan.locator("#public-hint .mission-hint")).to_contain_text("On track")
    sylvan.locator("#toggle-agenda-btn").click()
    expect(sylvan.locator("#secret-missions-list .secret-item")).to_have_count(1)
    expect(sylvan.locator("#secret-missions-list")).to_contain_text("40 Military")
    expect(sylvan.locator("#secret-hint-sylvan_defense .mission-hint")).to_contain_text("Not yet")

    # A mission hint follows the game: mustering reaches 40 Military
    sylvan.locator(".decree", has_text="Muster Regiments").click()
    confirm(sylvan)
    expect(sylvan.locator("#secret-hint-sylvan_defense .mission-hint")).to_contain_text("On track", timeout=5000)
    expect(sylvan.locator("#grain-val")).to_have_text("110", timeout=5000)

    # --- A ready-made motion: nothing to write, only the amount can change --------------------------
    motion_builder(sylvan)
    expect(sylvan.locator(".simple-motion")).to_have_count(6)
    expect(sylvan.locator("#proposal-form")).to_have_count(0)
    expect(sylvan.locator("#view-declarations input[type=text], #view-declarations textarea, #view-declarations select")).to_have_count(0)
    fixed = sylvan.locator('.simple-motion[data-motion="relief_mission"]')
    expect(fixed.locator("input")).to_have_count(0)                      # no amount to choose on this one
    share = sylvan.locator('.simple-motion[data-motion="share_grain"]')
    expect(share.locator(".simple-effect")).to_contain_text("gives 10.")
    share.locator("button", has_text="+5").click()
    expect(share.locator("input")).to_have_value("15")
    expect(share.locator(".simple-effect")).to_contain_text("gives 15.")
    share.locator("button", has_text="−5").click()
    share.locator("button", has_text="−5").click()
    share.locator("button", has_text="−5").click()                       # the smallest amount is 5
    expect(share.locator("input")).to_have_value("5")
    share.locator("input").fill("500")
    share.locator("input").press("Enter")
    expect(share.locator("input")).to_have_value("30")                   # and the largest 30

    plea = umbra.locator('.simple-motion[data-motion="plea_for_aid"]')
    motion_builder(umbra)
    expect(plea.locator(".simple-effect")).to_contain_text("to Umbral Enclave")
    plea.locator("button", has_text="+5").click()
    plea.locator("button", has_text="Table this motion").click()
    expect(umbra.locator(".confirm-card")).to_contain_text("Every other nation gives 10 Grain to Umbral Enclave")
    confirm(umbra)

    sylvan.locator(".link-back").click()                                 # back to the floor
    card = sylvan.locator("#pending-motions-list .motion-card", has_text="Plea for Aid")
    expect(card).to_be_visible(timeout=5000)
    expect(card).to_contain_text("Every other nation gives 10 Grain to Umbral Enclave")
    expect(card.locator("details")).to_have_count(0)                     # no terms to read: "If passed" says it all
    card.locator("button", has_text="Co-sponsor").click()
    confirm(sylvan)
    expect(card.locator(".status-pill", has_text="On the ballot")).to_be_visible(timeout=5000)

    # --- The vote, and the game carries it out by itself ---------------------------------------------
    admin.locator("button", has_text="Convene the Assembly").click()
    confirm(admin)
    for phone in (sylvan, umbra):
        expect(phone.locator("#plenary-callout-title")).to_have_text("The Assembly votes", timeout=5000)
        vote = phone.locator("#plenary-voting-actions-container .vote-for")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
        confirm(phone)
    admin.locator("button", has_text="Settle the vote").click()
    confirm(admin)
    decided = sylvan.locator("#decided-motions-list .motion-card", has_text="Plea for Aid")
    expect(decided.locator(".status-pill", has_text="Passed")).to_be_visible(timeout=5000)
    expect(decided).to_contain_text("Umbral Enclave +50 Grain")
    tab(umbra, "Realm")
    expect(umbra.locator("#grain-val")).to_have_text("110", timeout=5000)

    # --- The facilitator has nothing to carry out, and no quiz or war to mind ------------------------
    admin.locator("[data-tab=tab-resolutions]").click()
    expect(admin.locator("#gm-inbox-card")).to_have_count(0)
    expect(admin.locator("#admin-motion-templates")).to_contain_text("Share the Grain")
    admin.locator("[data-tab=tab-resources]").click()
    expect(admin.locator("#admin-realms-tbody")).not_to_contain_text("QUIZ")

    # --- Turn 3 is the same single vote, with the Food Acts on the ballot ----------------------------
    admin.locator("[data-tab=tab-pacing]").click()
    admin.locator("button", has_text="Go to Turn 2").click()
    confirm(admin)
    expect(admin.locator("#admin-turn-display")).to_have_text("Turn 2 of 3", timeout=5000)
    expect(umbra.locator("#food-forecast")).to_contain_text("2 meals left", timeout=5000)
    admin.locator("#btn-end-turn-header").click()
    confirm(admin)
    expect(admin.locator("#admin-turn-display")).to_have_text("Turn 3 of 3", timeout=5000)
    expect(admin.locator("#btn-end-turn-header")).to_have_text("End the summit", timeout=5000)
    admin.locator("[data-tab=tab-pacing]").click()
    admin.locator("button", has_text="Convene the Assembly").click()
    confirm(admin)
    expect(admin.locator("#admin-phase-display")).to_have_text("The final vote", timeout=5000)
    for phone in (sylvan, umbra):
        votes = phone.locator("#plenary-voting-actions-container .vote-for")
        expect(votes).to_have_count(2, timeout=5000)
        expect(phone.locator("#plenary-voting-actions-container")).to_contain_text("Food Act")
        votes.first.click()
        confirm(phone)
        expect(votes).to_have_count(1, timeout=5000)
        votes.first.click()
        confirm(phone)
    admin.locator("button", has_text="Settle the vote").click()
    confirm(admin)
    admin.locator("button", has_text="End the summit and show the results").click()
    confirm(admin)

    # --- Results: one secret mission each, on the phone and in the report -------------------------
    expect(sylvan.locator("#mobile-concluded-callout")).to_contain_text("Secret mission 1", timeout=5000)
    expect(sylvan.locator("#mobile-concluded-callout")).not_to_contain_text("Secret mission 2")
    expect(sylvan.locator("#food-forecast")).to_be_hidden()
    report = admin.context.new_page()
    report.goto(server + "/admin/report")
    expect(report.locator(".sub").first).to_contain_text("Simplified")
    expect(report.locator("body")).not_to_contain_text("Quiz ✓/✗")
    report.close()

    assert admin_errors == [] and sylvan_errors == [] and umbra_errors == []
    full_game(admin)
    admin.close()


def test_simplified_projector_and_guide(server, browser):
    admin = admin_page(browser, server)
    simplified_game(admin)
    projector = browser.new_page()
    errors = watch_errors(projector)
    projector.goto(server + "/projector")
    expect(projector.locator("#spotlight")).to_contain_text("Standing", timeout=5000)
    expect(projector.locator("#spotlight")).not_to_contain_text("Vitality")
    expect(projector.locator("#proj-timeline")).to_contain_text("Assembly vote")
    expect(projector.locator("#proj-timeline")).not_to_contain_text("Grand Plenary")
    assert errors == []
    projector.close()

    guide = browser.new_page()
    guide.goto(server + "/overview")
    expect(guide.locator("#guide-difficulty")).to_contain_text("Game complexity: Simplified")
    expect(guide.locator("#guide-difficulty")).to_contain_text("The Great Famine")
    guide.locator("[data-tab=tab-pacing]").click()
    expect(guide.locator("#tab-pacing .verdict-rules")).to_contain_text("at most one nation is out of Grain")
    guide.locator("[data-tab=tab-assembly]").click()
    expect(guide.locator("#tab-assembly")).to_contain_text("Share the Grain")
    expect(guide.locator("#tab-assembly")).not_to_contain_text("Lore Quiz")
    guide.close()
    full_game(admin)
    admin.close()


def test_the_full_game_keeps_all_its_motions(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    expect(sylvan.locator(".bottom-nav-item")).to_have_count(6)
    expect(sylvan.locator("#food-forecast")).to_have_count(0)
    expect(sylvan.locator("#vitality-bar")).to_be_visible()
    tab(sylvan, "Motions")
    expect(sylvan.locator(".motion-template")).to_have_count(8)
    expect(sylvan.locator(".simple-motion")).to_have_count(0)

    # Amounts above 30 can really be tabled: the only limit is what a nation has
    sylvan.locator("#motion-new-btn").click()
    sylvan.locator(".motion-template", has_text="Sanction or Embargo").click()
    amount = sylvan.locator("#motion-params input[type=number]")
    amount.fill("75")
    expect(sylvan.locator("#motion-preview")).to_contain_text("loses 75", timeout=5000)
    sylvan.locator("#proposal-form button[type=submit]").click()
    expect(sylvan.locator(".confirm-card")).to_contain_text("75")
    confirm(sylvan)
    motion = sylvan.locator("#pending-motions-list .motion-card").first
    expect(motion).to_contain_text("75", timeout=5000)
    assert errors == []
    admin.close()


def test_screens_can_be_used_while_they_refresh(server, browser):
    """Every screen polls once a second; that must not close what a player has open or swallow a tap."""
    admin = admin_page(browser, server)
    full_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    api(sylvan, "/api/proposal/create", {"proposer_id": "sylvan", "title": "Keep me open", "description": "Terms to read slowly", "effect_type": "aid"})
    tab(sylvan, "Motions")
    terms = sylvan.locator("#pending-motions-list .motion-card", has_text="Keep me open").locator("details")
    expect(terms).to_be_visible(timeout=5000)
    terms.locator("summary").click()
    expect(terms.locator("p")).to_be_visible()
    sylvan.wait_for_timeout(2500)                                        # two or three polls later
    expect(terms.locator("p")).to_be_visible()
    # The same element survives a refresh, so a tap that spans a poll still lands on it.
    sylvan.evaluate("document.querySelector('#pending-motions-list .motion-card').dataset.marker = 'same'")
    sylvan.wait_for_timeout(2500)
    assert sylvan.evaluate("document.querySelector('#pending-motions-list .motion-card').dataset.marker") == "same"
    # The facilitator's seat dropdown stays open too.
    admin.locator("[data-tab=tab-access]").click()
    admin.evaluate("document.querySelector('#admin-pins-tbody select').dataset.marker = 'same'")
    admin.wait_for_timeout(2500)
    assert admin.evaluate("document.querySelector('#admin-pins-tbody select').dataset.marker") == "same"
    assert errors == []
    full_game(admin)
    admin.close()


def test_the_last_turn_button_ends_the_summit(server, browser):
    admin = admin_page(browser, server)
    errors = watch_errors(admin)
    full_game(admin)
    api(admin, "/api/admin/turn/next")
    api(admin, "/api/admin/turn/next")
    expect(admin.locator("#btn-end-turn-header")).to_have_text("End the summit", timeout=5000)
    admin.locator("#btn-end-turn-header").click()
    expect(admin.locator(".confirm-card")).to_contain_text("End the summit?")
    decline(admin)
    assert state(admin)["meta"]["current_turn"] == 3
    assert errors == []
    full_game(admin)
    admin.close()


def test_player_written_text_cannot_run_as_code_on_the_results_screens(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    trap = '<img src=x onerror="window.__hacked=1">'
    solaris, solaris_errors = join(browser, server, "Solaris Ascendancy", "1003")
    res = api(solaris, "/api/proposal/create", {"proposer_id": "solaria", "title": trap, "description": trap, "effect_type": "aid"})
    assert res["success"]
    api(admin, "/api/proposal/%s/support" % res["proposal_id"], {"supporter_id": "umbra"})
    api(admin, "/api/admin/plenary/start")
    api(solaris, "/api/plenary/vote", {"realm_id": "solaria", "proposal_id": res["proposal_id"], "choice": "oppose"})
    api(admin, "/api/plenary/vote", {"realm_id": "umbra", "proposal_id": res["proposal_id"], "choice": "support"})
    # Solaris opposes, Aquila's weight carries the motion: the title lands in Solaris' mission explanation as well
    api(admin, "/api/plenary/vote", {"realm_id": "aquila", "proposal_id": res["proposal_id"], "choice": "support"})
    api(admin, "/api/plenary/vote", {"realm_id": "sylvan", "proposal_id": res["proposal_id"], "choice": "support"})
    api(admin, "/api/admin/plenary/conclude_quick")
    api(admin, "/api/admin/turn/next")
    api(admin, "/api/admin/turn/next")
    api(admin, "/api/admin/summit/conclude")
    projector = browser.new_page()
    projector.goto(server + "/projector")
    expect(projector.locator("#proj-debrief-accords")).to_contain_text("<img", timeout=5000)      # shown as text
    expect(solaris.locator("#mobile-concluded-callout")).to_contain_text("<img", timeout=5000)
    assert projector.evaluate("window.__hacked") is None
    assert solaris.evaluate("window.__hacked") is None
    projector.close()
    full_game(admin)
    admin.close()


# ---------------------------------------------------------------------------------------------------
# The first screens: a new player and a new facilitator should never have to wonder what to do
# ---------------------------------------------------------------------------------------------------
def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 0, page.url


def test_join_page_fits_a_small_phone_and_explains_itself(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    page = browser.new_context(viewport={"width": 360, "height": 640}, has_touch=True).new_page()
    errors = watch_errors(page)
    page.goto(server + "/")
    # every nation is on the first screen, without scrolling
    cards = page.locator(".lobby-realm-card")
    expect(cards).to_have_count(6)
    for i in range(6):
        assert cards.nth(i).bounding_box()["y"] + cards.nth(i).bounding_box()["height"] <= 640
    no_sideways_scroll(page)
    expect(page.locator("#card-umbra .lobby-seats")).to_have_text("0 of 1 seat")

    # second step: the chosen nation, its passcode and what to do when it does not work
    page.locator("#card-sylvan").click()
    expect(page.locator("#modal-realm-name")).to_have_text("Sylvan Concordat")
    expect(page.locator("#login-submit")).to_have_text("Join Sylvan Concordat")
    assert page.evaluate("document.activeElement.id") == "login-realm-pin"
    box = page.locator("#login-submit").bounding_box()
    assert box["y"] + box["height"] <= 640 - 200, "the button must stay above the phone's keyboard"
    page.fill("#login-realm-pin", "0000")
    page.locator("#login-submit").click()
    expect(page.locator("#login-error-msg")).to_contain_text("Check it with your facilitator")
    page.locator(".join-back").click()
    expect(page.locator("#login-pin-modal")).to_be_hidden()

    # once in, the first page leads straight back
    page.locator("#card-sylvan").click()
    page.fill("#login-realm-pin", "1001")
    page.locator("#login-submit").click()
    expect(page.locator(".ribbon-name strong")).to_have_text("Sylvan Concordat")
    page.goto(server + "/")
    expect(page.locator(".join-continue-btn")).to_contain_text("Back to Sylvan Concordat")
    page.locator(".join-continue-btn").click()
    expect(page.locator(".ribbon-name strong")).to_have_text("Sylvan Concordat")
    # a card's link for this nation also goes straight in
    page.goto(server + "/?login=sylvan")
    expect(page.locator(".ribbon-name strong")).to_have_text("Sylvan Concordat")
    assert errors == []
    admin.close()


def test_a_full_delegation_says_what_to_do_instead_of_a_browser_alert(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    join(browser, server, "Umbral Enclave", "1004")         # Umbra has one seat
    page = browser.new_context(**PHONE).new_page()
    page.goto(server + "/")
    expect(page.locator("#badge-seats-umbra")).to_have_text("Full", timeout=6000)
    page.locator("#card-umbra").click()                      # no alert() in the way: Playwright would fail on an unexpected dialog handler
    expect(page.locator("#login-note")).to_contain_text("ask your facilitator to add a seat")
    page.fill("#login-realm-pin", "1004")
    page.locator("#login-submit").click()
    expect(page.locator("#login-error-msg")).to_contain_text("Ask your facilitator")
    admin.close()


def test_the_phone_says_whether_the_game_is_running(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    title = sylvan.locator("#phase-title")
    expect(title).to_have_text("The summit is about to begin")
    expect(sylvan.locator("#timer-display")).to_have_class(re.compile("stopped"))
    api(admin, "/api/admin/clock", {"action": "resume"})
    expect(title).to_have_text("Working session", timeout=5000)
    expect(sylvan.locator("#timer-display")).not_to_have_class(re.compile("stopped"))
    api(admin, "/api/admin/clock", {"action": "pause"})
    expect(title).to_have_text("The clock is paused", timeout=5000)
    expect(sylvan.locator("#timer-display")).to_have_class(re.compile("stopped"))
    api(admin, "/api/admin/clock", {"action": "resume"})
    expect(title).to_have_text("Working session", timeout=5000)
    assert errors == []
    admin.close()


def test_the_phone_explains_itself(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")

    # a first-time card that goes away for good
    expect(sylvan.locator("#welcome-card")).to_be_visible()
    sylvan.locator("#welcome-card button", has_text="Got it").click()
    expect(sylvan.locator("#welcome-card")).to_be_hidden()
    sylvan.reload()
    expect(sylvan.locator(".ribbon-name strong")).to_be_visible()
    expect(sylvan.locator("#welcome-card")).to_be_hidden()

    # tapping a number says what it is for
    sylvan.locator(".coin[data-explain=grain]").click()
    expect(sylvan.locator(".sheet-card")).to_contain_text("eat 20 Grain")
    sylvan.locator(".sheet-close").click()
    expect(sylvan.locator(".sheet-card")).to_have_count(0)
    sylvan.locator(".vital[data-explain=stability]").click()
    expect(sylvan.locator(".sheet-card")).to_contain_text("How calm your people are")
    sylvan.keyboard.press("Escape")
    expect(sylvan.locator(".sheet-card")).to_have_count(0)

    # the ? button: how the game goes, the Guide, sounds, and the way out
    sylvan.locator(".ribbon-help").click()
    sheet = sylvan.locator(".sheet-card")
    expect(sheet).to_contain_text("How a turn goes")
    expect(sheet).to_contain_text("The Assembly votes")
    expect(sheet).not_to_contain_text("How the continent is judged")      # the full game keeps the thresholds to itself
    expect(sheet.locator("a", has_text="full game guide")).to_have_attribute("href", "/overview")
    sheet.locator("#help-sound").click()
    expect(sheet.locator("#help-sound")).to_have_text("Turn sounds on")
    assert sylvan.evaluate("synth.muted") is True
    sheet.locator("#help-sound").click()
    sheet.locator("#help-leave").click()
    expect(sylvan.locator(".confirm-card")).to_contain_text("Leave your delegation?")
    decline(sylvan)
    expect(sylvan.locator(".ribbon-name strong")).to_be_visible()

    # a number that changes is marked where it stands
    api(admin, "/api/admin/resources/bulk", {"realm_ids": ["sylvan"], "changes": [{"resource": "grain", "mode": "take", "amount": 12}]})
    expect(sylvan.locator(".coin[data-explain=grain] .delta.down")).to_have_text("−12", timeout=5000)

    # a decree that cannot be paid for says so before the tap
    api(admin, "/api/admin/resources/bulk", {"realm_ids": ["sylvan"], "changes": [{"resource": "silk", "mode": "set", "amount": 5}]})
    gala = sylvan.locator(".decree", has_text="Grand Gala")
    expect(gala).to_have_class(re.compile("cannot"), timeout=5000)
    expect(gala.locator(".decree-why")).to_have_text("Not enough Silk")
    assert errors == []
    admin.close()


def test_what_needs_an_answer_comes_first_on_the_phone(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    valkhor, _ = join(browser, server, "Iron Val-Khor", "1002")

    # Trade: nothing but the form until someone makes an offer, then the offer is on top
    tab(sylvan, "Trade")
    expect(sylvan.locator("#incoming-card")).to_be_hidden()
    expect(sylvan.locator("#outgoing-card")).to_be_hidden()
    expect(sylvan.locator("#trade-have")).to_have_text("You have 100 Grain")
    sylvan.fill("#trade-offer-amt", "500")
    sylvan.locator(".partner-chip", has_text="Iron Val-Khor").click()
    expect(sylvan.locator("#trade-preview-text")).to_contain_text("You only have 100 Grain")
    sylvan.fill("#trade-offer-amt", "10")

    api(valkhor, "/api/trade/create", {"sender_id": "val_khor", "receiver_id": "sylvan", "offer_resource": "cores", "offer_amount": 5,
                                       "request_resource": "grain", "request_amount": 5})
    expect(sylvan.locator("#incoming-card")).to_be_visible(timeout=5000)
    assert sylvan.locator("#incoming-card").bounding_box()["y"] < sylvan.locator("#trade-form").bounding_box()["y"]
    expect(sylvan.locator(".toast", has_text="New offer from Iron Val-Khor")).to_be_visible()
    # the sender hears what became of it, and it stays on record
    sylvan.locator("#incoming-trades-list button", has_text="Decline").click()
    confirm(sylvan)
    expect(valkhor.locator(".toast", has_text="Sylvan Concordat declined your offer")).to_be_visible(timeout=5000)
    tab(valkhor, "Trade")
    expect(valkhor.locator("#trade-history")).to_contain_text("Sylvan Concordat declined")
    expect(valkhor.locator("#trade-history")).to_contain_text("you give 5 Cores, you get 5 Grain")

    # Motions: the floor first; a motion of another nation is one tap from a co-sponsor
    api(valkhor, "/api/proposal/create", {"proposer_id": "val_khor", "title": "Floor first", "description": "Terms", "effect_type": "aid"})
    tab(sylvan, "Motions")
    motion = sylvan.locator("#pending-motions-list .motion-card", has_text="Floor first")
    expect(motion).to_be_visible(timeout=5000)
    expect(sylvan.locator(".motion-template").first).to_be_hidden()
    assert motion.bounding_box()["y"] < 844, "a motion must be on the first screen of the tab"
    expect(sylvan.locator("#nav-motions-badge")).to_have_text("1")
    # proposing has its own screen, and tabling leads back to the floor
    sylvan.locator("#motion-new-btn").click()
    expect(sylvan.locator("#motion-floor")).to_be_hidden()
    expect(sylvan.locator(".motion-template")).to_have_count(8)
    sylvan.locator(".motion-template", has_text="Sovereign Relief Mission").click()
    expect(sylvan.locator("#motion-gallery-head")).to_be_hidden()
    sylvan.locator("#proposal-submit").click()
    confirm(sylvan)
    expect(sylvan.locator("#motion-floor")).to_be_visible()
    expect(sylvan.locator("#pending-motions-list")).to_contain_text("Your motion. Ask another nation to co-sponsor it.", timeout=5000)

    # World: news first, nations one tap away, and a badge for what is new
    tab(sylvan, "World")
    expect(sylvan.locator("#mobile-news-feed")).to_be_visible()
    expect(sylvan.locator("#registry-list")).to_be_hidden()
    sylvan.locator(".segment[data-world=nations]").click()
    expect(sylvan.locator("#registry-list .nation-card")).to_have_count(6)
    tab(sylvan, "Realm")
    api(admin, "/api/admin/news/broadcast", {"headline": "HEAR YE", "detail": "Something happened"})
    expect(sylvan.locator("#nav-news-badge")).to_be_visible(timeout=5000)
    tab(sylvan, "World")
    expect(sylvan.locator("#nav-news-badge")).to_be_hidden(timeout=5000)
    assert errors == []
    admin.close()


def test_a_vote_is_hard_to_miss_and_in_plain_words(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    sylvan, errors = join(browser, server, "Sylvan Concordat", "1001")
    res = api(sylvan, "/api/proposal/create", {"proposer_id": "sylvan", "title": "Plain words", "description": "Terms", "effect_type": "aid"})
    api(admin, f"/api/proposal/{res['proposal_id']}/support", {"supporter_id": "umbra"})

    tab(sylvan, "Wiki")                                      # busy reading when the Assembly opens
    expect(sylvan.locator("#wiki-body")).to_be_visible()
    expect(sylvan.locator("#wk-timer")).not_to_be_empty()    # the clock stays in sight in the wiki
    api(admin, "/api/admin/plenary/start")
    expect(sylvan.locator("#plenary-session-callout")).to_be_visible(timeout=5000)
    expect(sylvan.locator(".nation-ribbon")).to_be_visible()
    expect(sylvan.locator("#plenary-callout-title")).to_have_text("The Assembly votes")
    expect(sylvan.locator("#plenary-callout-desc")).to_contain_text("Your nation has 2 votes")
    expect(sylvan.locator("#plenary-timer-display")).to_contain_text("Voting closes in")
    expect(sylvan.locator("#motion-new-btn")).to_be_hidden()  # nothing can be tabled while the Assembly votes

    sylvan.locator(".vote-against").click()
    expect(sylvan.locator(".confirm-card")).to_contain_text("Vote against?")
    decline(sylvan)
    sylvan.locator(".vote-for").click()
    confirm(sylvan)
    expect(sylvan.locator(".vote-cast")).to_have_text("✓ You voted for with 2 votes", timeout=5000)
    expect(sylvan.locator("#plenary-callout-desc")).to_contain_text("All your votes are in")
    assert errors == []
    admin.close()


def test_the_deck_always_says_what_comes_next(server, browser):
    admin = admin_page(browser, server)
    errors = watch_errors(admin)
    full_game(admin)
    admin.reload()
    now = admin.locator("#admin-phase-display")
    actions = admin.locator("#admin-plenary-controls")

    # Nothing has begun: the checklist, with the passcodes, and one obvious button
    expect(now).to_have_text("Ready to start", timeout=5000)
    expect(admin.locator("#pregame-card")).to_be_visible()
    expect(admin.locator("#pregame-seats")).to_contain_text("1001")
    expect(admin.locator("#pregame-pins-note")).to_be_visible()     # default passcodes are easy to guess
    expect(actions.locator("button")).to_have_count(1)
    expect(admin.locator("#btn-end-turn-header")).to_have_count(0)
    expect(admin.locator("#autosave-chip")).to_have_text("Saves start with the game")

    # Running: pause is there, and it says what happens when the clock runs out
    actions.locator("#now-start").click()
    expect(now).to_have_text("Working session", timeout=5000)
    expect(admin.locator("#now-text")).to_contain_text("no motion is on the ballot")
    expect(admin.locator("#pregame-card")).to_be_hidden()
    expect(admin.locator("#seats-card")).to_be_visible()
    expect(actions.locator("button", has_text="Convene the Assembly")).to_have_count(0)
    expect(admin.locator("#admin-timer-display")).not_to_have_text("20:00", timeout=5000)
    actions.locator("button", has_text="Pause").click()
    expect(now).to_have_text("Paused", timeout=5000)
    actions.locator("button", has_text="Resume").click()
    expect(now).to_have_text("Working session", timeout=5000)

    # A motion reaches the ballot: the next step appears by itself
    res = api(admin, "/api/proposal/create", {"proposer_id": "sylvan", "title": "Next step", "description": "Terms", "effect_type": "aid"})
    api(admin, f"/api/proposal/{res['proposal_id']}/support", {"supporter_id": "umbra"})
    expect(admin.locator("#now-text")).to_contain_text("the Assembly votes on 1 motion", timeout=5000)
    actions.locator("button", has_text="Convene the Assembly").click()
    confirm(admin)

    # The vote: who is still missing
    expect(now).to_have_text("The Assembly is voting", timeout=5000)
    expect(admin.locator("#now-text")).to_contain_text("0 of 6 nations have voted")
    for realm in ("sylvan", "val_khor", "solaria", "umbra", "aquila", "aethelgard"):
        api(admin, "/api/plenary/vote", {"realm_id": realm, "proposal_id": res["proposal_id"], "choice": "support"})
    expect(admin.locator("#now-text")).to_contain_text("All nations have voted", timeout=5000)
    actions.locator("button", has_text="Settle the vote").click()
    confirm(admin)

    # Between turns, on to the next
    expect(now).to_have_text("The vote is over", timeout=5000)
    actions.locator("button", has_text="Go to Turn 2").click()
    confirm(admin)
    expect(now).to_have_text("Turn 2 is ready", timeout=5000)
    expect(actions.locator("button", has_text="Start Turn 2")).to_be_visible()
    # A question that passed shows on every tab that it is waiting
    res = api(admin, "/api/proposal/create", {"proposer_id": "aquila", "title": "A question", "description": "Well?", "effect_type": "gm_question"})
    api(admin, f"/api/proposal/{res['proposal_id']}/support", {"supporter_id": "umbra"})
    api(admin, "/api/admin/plenary/start")
    api(admin, "/api/plenary/vote", {"realm_id": "umbra", "proposal_id": res["proposal_id"], "choice": "support"})
    api(admin, "/api/admin/plenary/conclude_quick")
    alert = admin.locator(".now-alert", has_text="waiting for you")
    expect(alert).to_be_visible(timeout=5000)
    alert.click()
    expect(admin.locator("#gm-inbox textarea")).to_be_visible()
    assert "#tab-resolutions" in admin.url                          # and a reload comes back to this tab
    admin.reload()
    expect(admin.locator("#tab-resolutions")).to_be_visible()

    # The end: reflection and results
    api(admin, "/api/admin/summit/conclude")
    expect(now).to_have_text("The summit is over", timeout=5000)
    expect(actions.locator("button", has_text="Start reflection")).to_be_visible()
    expect(actions.locator("a", has_text="New summit")).to_have_attribute("href", "/admin/setup")
    assert errors == []
    full_game(admin)
    admin.close()


def test_the_setup_screen_warns_about_unsaved_settings_and_leads_on(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    admin.goto(server + "/admin/setup")
    # before a game there is nothing to start over from, only the way on
    expect(admin.locator("button", has_text="Start a new summit")).to_have_count(0)
    expect(admin.locator("#setup-dirty")).to_be_empty()
    admin.locator("input[name=scenario][value=open]").check()
    expect(admin.locator("#setup-dirty")).to_contain_text("not saved yet")
    admin.locator("#setup-actions button", has_text="Continue to the command deck").click()
    expect(admin.locator(".page-title")).to_have_text("Facilitator Command Deck", timeout=5000)
    assert state(admin)["game_settings"]["scenario"] == "open"
    expect(admin.locator("#pregame-game")).to_contain_text("Open summit")
    full_game(admin)
    admin.close()


def test_passcode_cards_and_the_players_tab(server, browser):
    admin = admin_page(browser, server)
    errors = watch_errors(admin)
    full_game(admin)
    admin.locator("[data-tab=tab-access]").click()
    # a passcode can be changed right in the table, and bad ones are refused
    pin = admin.locator('input[aria-label="Passcode of Umbral Enclave"]')
    pin.fill("x")
    pin.press("Enter")
    expect(admin.locator(".toast", has_text="3 to 8 digits")).to_be_visible(timeout=5000)
    pin = admin.locator('input[aria-label="Passcode of Umbral Enclave"]')
    pin.fill("4321")
    pin.press("Enter")
    expect(admin.locator(".toast", has_text="PIN updated")).to_be_visible(timeout=5000)

    cards = admin.context.new_page()
    cards.goto(server + "/admin/cards")
    expect(cards.locator(".pass-card")).to_have_count(6)
    umbra = cards.locator(".pass-card", has_text="Umbral Enclave")
    expect(umbra.locator(".pass-card-pin")).to_have_text("4321")
    expect(umbra.locator("svg")).to_be_visible()
    cards.close()

    phone, _ = join(browser, server, "Umbral Enclave", "4321")
    assert errors == []
    full_game(admin)
    api(admin, "/api/admin/pin/reset", {"realm_id": "umbra", "pin": "1004"})
    admin.close()


def test_every_screen_fits_a_phone(server, browser):
    admin = admin_page(browser, server)
    full_game(admin)
    context = browser.new_context(**PHONE)
    context.add_cookies(admin.context.cookies())
    deck = context.new_page()
    deck.goto(server + "/admin")
    expect(deck.locator("#now-panel")).to_be_visible()
    no_sideways_scroll(deck)
    expect(deck.locator(".nav-link", has_text="Setup")).to_be_visible()
    expect(deck.locator(".nav-link", has_text="Projector")).to_be_visible()
    for tab_id in ("tab-resolutions", "tab-events", "tab-resources", "tab-access", "tab-saves"):
        deck.locator(f"[data-tab={tab_id}]").click()
        deck.wait_for_timeout(250)
        no_sideways_scroll(deck)
    deck.goto(server + "/admin/setup")
    expect(deck.locator(".page-title")).to_have_text("Summit setup")
    no_sideways_scroll(deck)
    deck.goto(server + "/admin/cards")
    no_sideways_scroll(deck)

    sylvan, _ = join(browser, server, "Sylvan Concordat", "1001")
    no_sideways_scroll(sylvan)
    for name in ("World", "Trade", "Motions", "Quiz", "Wiki"):
        tab(sylvan, name)
        sylvan.wait_for_timeout(250)
        no_sideways_scroll(sylvan)
    admin.close()


# ---------------------------------------------------------------------------------------------------
# Saves: the real thing, with a real server being killed and started again
# ---------------------------------------------------------------------------------------------------
class GameServer:
    """A server of its own, on a fixed port and with a database that outlives it, so that it can crash and come back."""

    def __init__(self, autosave_seconds="300"):
        self.port = free_port()
        self.db = os.path.join(tempfile.mkdtemp(), "restart.db")
        self.base = f"http://127.0.0.1:{self.port}"
        self.autosave_seconds = autosave_seconds
        self.proc = None

    def start(self):
        env = dict(os.environ, PORT=str(self.port), SUMMIT_DB_PATH=self.db, ADMIN_PASSCODE=ADMIN_PASSCODE,
                   SECRET_KEY="e2e-secret", ALLOW_AUTH_PARAM="0", AUTOSAVE_SECONDS=self.autosave_seconds)
        self.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "app.py")], cwd=ROOT, env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(self.base + "/healthz", timeout=1)
                return
            except OSError:
                time.sleep(0.1)
        pytest.fail("server did not start")

    def crash(self):
        """As sudden as a dead laptop battery: no chance to clean up."""
        self.proc.kill()
        self.proc.wait(timeout=5)

    def wipe_database(self):
        """What a hosted server's restart does to a database in /tmp."""
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(self.db + suffix):
                os.remove(self.db + suffix)


@pytest.fixture
def game_server():
    server_under_test = GameServer()
    server_under_test.start()
    yield server_under_test
    server_under_test.crash()


def own_nation(page, realm_id="sylvan"):
    return next(r for r in state(page)["realms"] if r["id"] == realm_id)


def test_a_crashed_server_loses_nothing_and_the_room_gets_back_in(game_server, browser):
    base = game_server.base
    admin = admin_page(browser, base)
    sylvan, sylvan_errors = join(browser, base, "Sylvan Concordat", "1001")
    valkhor, _ = join(browser, base, "Iron Val-Khor", "1002")

    # A game is under way: the clock runs, a decree, a trade, a motion
    admin.locator("#now-start").click()
    expect(admin.locator("#admin-phase-display")).to_have_text("Working session", timeout=5000)
    sylvan.locator(".decree", has_text="Grand Gala").click()
    confirm(sylvan)
    expect(sylvan.locator("#silk-val")).to_have_text("15", timeout=5000)
    api(sylvan, "/api/trade/create", {"sender_id": "sylvan", "receiver_id": "val_khor", "offer_resource": "grain", "offer_amount": 10,
                                      "request_resource": "cores", "request_amount": 10})
    trade = next(t for t in state(sylvan)["trades"] if t["status"] == "pending")
    api(valkhor, f"/api/trade/{trade['id']}/respond", {"action": "accept", "realm_id": "val_khor"})
    motion = api(valkhor, "/api/proposal/create", {"proposer_id": "val_khor", "title": "Survives a crash", "description": "Terms", "effect_type": "aid"})
    expect(sylvan.locator("#grain-val")).to_have_text("90", timeout=5000)
    sylvan.wait_for_timeout(1200)
    before = state(admin)
    assert before["meta"]["is_timer_running"]

    # The server dies without warning: the screens say so instead of freezing
    game_server.crash()
    expect(sylvan.locator("#connection-bar")).to_be_visible(timeout=8000)
    expect(admin.locator("#connection-bar")).to_be_visible(timeout=8000)

    # It starts again. As always that means a fresh game, so the phones are asked for the passcode again...
    game_server.start()
    expect(sylvan.locator("#login-pin-modal")).to_be_visible(timeout=10000)
    expect(sylvan.locator("#login-note")).to_contain_text("A new game has started")
    expect(sylvan.locator("#connection-bar")).to_have_count(0)

    # ...but the facilitator is offered the game back first thing, on the deck and on the setup screen
    banner = admin.locator("#resume-banner")
    expect(banner).to_contain_text("A game was interrupted", timeout=10000)
    expect(banner).to_contain_text("Turn 1")
    setup = admin.context.new_page()
    setup.goto(base + "/admin/setup")
    expect(setup.locator("#setup-resume")).to_contain_text("A game was interrupted")
    setup.close()
    # (nothing has been decided yet: the fresh game has no reason to save anything over it)
    admin.reload()
    expect(banner).to_be_visible(timeout=5000)
    expect(admin.locator("#autosave-chip")).to_have_text("Saves start with the game")

    # Bring it back
    banner.locator("#resume-btn").click()
    confirm(admin)
    expect(banner).to_be_hidden(timeout=8000)

    # Everything is there, and the clock waits for the facilitator
    after = state(admin)
    for field in ("alchemical_grain", "aether_cores", "echo_silk", "diplomatic_standing"):
        assert [r[field] for r in after["realms"]] == [r[field] for r in before["realms"]], field
    assert after["meta"]["game_id"] == before["meta"]["game_id"]
    assert not after["meta"]["is_timer_running"]
    assert abs(after["meta"]["turn_timer_remaining"] - before["meta"]["turn_timer_remaining"]) <= 3
    assert [t["status"] for t in after["trades"]] == ["accepted"]
    assert any(p["id"] == motion["proposal_id"] for p in after["proposals"])
    expect(admin.locator("#admin-phase-display")).to_have_text("Paused", timeout=5000)

    # The phone that was waiting at the passcode screen goes back into the game by itself, logged in
    expect(sylvan.locator(".ribbon-name strong")).to_have_text("Sylvan Concordat", timeout=10000)
    expect(sylvan.locator("#grain-val")).to_have_text("90", timeout=5000)
    expect(sylvan.locator("#phase-title")).to_have_text("The clock is paused", timeout=5000)
    expect(valkhor.locator(".ribbon-name strong")).to_have_text("Iron Val-Khor", timeout=10000)
    tab(valkhor, "Motions")
    expect(valkhor.locator("#pending-motions-list")).to_contain_text("Survives a crash", timeout=5000)

    # And play goes on
    admin.locator("#admin-plenary-controls button", has_text="Resume").click()
    expect(sylvan.locator("#phase-title")).to_have_text("Working session", timeout=5000)
    sylvan.locator(".decree", has_text="Civil Guard").click()
    confirm(sylvan)
    expect(sylvan.locator("#cores-val")).to_have_text("25", timeout=5000)     # 25 + 10 from the trade − 10 for the guard
    assert sylvan_errors == []
    admin.close()


def test_a_wiped_hosted_server_can_be_restored_from_the_browser(game_server, browser):
    base = game_server.base
    admin = admin_page(browser, base)
    errors = watch_errors(admin)
    sylvan, _ = join(browser, base, "Sylvan Concordat", "1001")
    admin.locator("#now-start").click()
    sylvan.locator(".decree", has_text="Grand Gala").click()
    confirm(sylvan)
    expect(sylvan.locator("#silk-val")).to_have_text("15", timeout=5000)
    # A copy reaches this browser at once when the game starts, and at least every minute after that
    admin.wait_for_function("adminApp._browserSaves().length > 0", timeout=8000)
    admin.evaluate("adminApp.keepBrowserCopy()")
    admin.wait_for_function("adminApp._browserSaves()[0].snapshot.realms.find(r => r.id === 'sylvan').echo_silk === 15", timeout=8000)
    expect(admin.locator("#autosave-chip")).to_contain_text("Saved", timeout=5000)
    copies_before = admin.evaluate("adminApp._browserSaves().length")

    # Like a Render restart: the process and the database in /tmp are gone
    game_server.crash()
    game_server.wipe_database()
    game_server.start()

    # The server knows nothing about the old game, but the browser does. And a fresh game must not push that copy out.
    banner = admin.locator("#resume-banner")
    expect(banner).to_contain_text("this browser still has a copy", timeout=10000)
    admin.reload()
    expect(banner).to_contain_text("this browser still has a copy", timeout=8000)
    admin.evaluate("adminApp.keepBrowserCopy()")
    admin.wait_for_timeout(500)
    assert admin.evaluate("adminApp._browserSaves().length") == copies_before

    banner.locator("#resume-btn").click()
    confirm(admin)
    expect(banner).to_be_hidden(timeout=8000)
    assert own_nation(admin)["echo_silk"] == 15
    expect(sylvan.locator("#silk-val")).to_have_text("15", timeout=10000)
    assert errors == []
    admin.close()


def test_declining_the_interrupted_game_is_remembered(game_server, browser):
    admin = admin_page(browser, game_server.base)
    admin.locator("#now-start").click()
    expect(admin.locator("#admin-phase-display")).to_have_text("Working session", timeout=5000)
    admin.wait_for_timeout(1200)
    game_server.crash()
    game_server.start()
    banner = admin.locator("#resume-banner")
    expect(banner).to_contain_text("A game was interrupted", timeout=10000)
    banner.locator("button", has_text="Start fresh").click()
    expect(banner).to_be_hidden(timeout=5000)
    admin.reload()
    expect(admin.locator("#admin-phase-display")).to_have_text("Ready to start", timeout=5000)
    expect(banner).to_be_hidden()
    # it is still on the Saves tab if the facilitator changes their mind
    admin.locator("[data-tab=tab-saves]").click()
    expect(admin.locator("#server-saves")).to_contain_text("Before server restart", timeout=5000)
    admin.close()


def test_autosave_really_runs_during_a_game(browser):
    fast = GameServer(autosave_seconds="2")
    fast.start()
    try:
        admin = admin_page(browser, fast.base)
        errors = watch_errors(admin)
        # Nothing to save while nobody has started
        admin.wait_for_timeout(3000)
        admin.locator("[data-tab=tab-saves]").click()
        expect(admin.locator("#server-saves")).to_contain_text("No saves yet", timeout=5000)
        expect(admin.locator("#save-status")).to_contain_text("has not started")

        # The clock runs: saves appear by themselves, and the deck says so
        admin.locator("#now-start").click()
        expect(admin.locator("#autosave-chip")).to_contain_text("Saved", timeout=8000)
        admin.wait_for_timeout(3000)
        admin.evaluate("adminApp.refreshSaves()")
        expect(admin.locator("#server-saves .inset").first).to_contain_text("Autosave", timeout=8000)
        expect(admin.locator("#browser-saves .inset").first).to_contain_text("Turn 1", timeout=8000)

        # A save can be put back, and asks first
        grain = own_nation(admin)["alchemical_grain"]
        api(admin, "/api/admin/resources/bulk", {"realm_ids": ["sylvan"], "changes": [{"resource": "grain", "mode": "set", "amount": 1}]})
        admin.locator("#server-saves .inset").first.locator("button", has_text="Restore").click()
        expect(admin.locator(".confirm-card")).to_contain_text("Restore this save?")
        confirm(admin)
        expect(admin.locator(".toast", has_text="Game restored")).to_be_visible(timeout=5000)
        assert own_nation(admin)["alchemical_grain"] == grain
        # The game it replaced is kept too
        admin.evaluate("adminApp.refreshSaves()")
        expect(admin.locator("#server-saves")).to_contain_text("Before restore", timeout=5000)
        assert errors == []
        admin.close()
    finally:
        fast.crash()


# --------------------------------------------------------------------------------------------- languages and the map
def test_czech_chosen_on_the_setup_screen_and_one_phone_in_english(server, browser):
    """The facilitator picks the game's language on the setup screen; a phone can still choose its own."""
    admin = admin_page(browser, server)
    errors = watch_errors(admin)
    try:
        full_game(admin)
        admin.goto(server + "/admin/setup")
        admin.locator("input[name=language][value=cs]").check()
        admin.locator("#setup-actions .btn-secondary").click()                    # Save settings
        expect(admin.locator("html")).to_have_attribute("lang", "cs", timeout=6000)
        expect(admin.locator(".page-title")).to_have_text("Nastavení summitu")
        expect(admin.locator("input[name=language][value=cs]")).to_be_checked()

        phone = browser.new_context(**PHONE).new_page()
        phone_errors = watch_errors(phone)
        phone.goto(server + "/")
        expect(phone.locator(".join-lede")).to_contain_text("Klepněte na svůj stát")
        expect(phone.locator(".lang-switch a.active")).to_have_text("Čeština")
        # This phone would rather read English: only this phone changes
        phone.locator(".lang-switch a", has_text="English").click()
        expect(phone.locator(".join-lede")).to_contain_text("Tap your nation")
        phone.locator(".lobby-realm-card", has_text="Sylvan Concordat").click()
        phone.fill("#login-realm-pin", "1001")
        phone.locator("#pin-login-form button[type=submit]").click()
        expect(phone.locator(".ribbon-name strong")).to_have_text("Sylvan Concordat")
        expect(phone.locator(".bottom-nav-item").first).to_contain_text("Realm")
        # ...and back to Czech from its help sheet, on the same screen
        phone.locator(".ribbon-help").click()
        phone.locator(".sheet-actions .lang-switch a", has_text="Čeština").click()
        expect(phone.locator(".bottom-nav-item").first).to_contain_text("Stát")
        expect(phone).to_have_url(re.compile(r"/realm/sylvan$"))

        projector = browser.new_page(viewport={"width": 1280, "height": 720})
        projector_errors = watch_errors(projector)
        projector.goto(server + "/projector")
        expect(projector.locator("html")).to_have_attribute("lang", "cs")
        # Back to English: the projector, which follows the game, reloads in English by itself
        api(admin, "/api/admin/settings", {"language": "en"})
        expect(projector.locator("html")).to_have_attribute("lang", "en", timeout=8000)
        assert errors == [] and phone_errors == [] and projector_errors == []
        projector.close()                   # an open projector keeps animating and slows the tests after this one
        phone.context.close()
    finally:
        api(admin, "/api/admin/settings", {"language": "en"})
        admin.context.close()


def test_the_map_shows_traffic_only_for_real_trades(server, browser):
    """No caravans or ships at the start; each accepted trade sends one, a few per pair at most; a new game clears the roads."""
    admin = admin_page(browser, server)
    reset_game(admin)
    projector = browser.new_page(viewport={"width": 1280, "height": 720})
    errors = watch_errors(projector)
    projector.goto(server + "/projector")
    projector.wait_for_function("window.projApp && window.projApp.map && window.projApp.map.routeNet")
    projector.wait_for_timeout(1200)
    assert projector.evaluate("projApp.map.caravans.length") == 0
    assert projector.evaluate("projApp.map.shipsAtSea") == 0

    def trade(sender, receiver):
        api(admin, "/api/trade/create", {"sender_id": sender, "receiver_id": receiver, "offer_resource": "silk", "offer_amount": 1,
                                         "request_resource": "silk", "request_amount": 1})
        pending = next(t for t in state(admin)["trades"] if t["status"] == "pending")
        api(admin, f"/api/trade/{pending['id']}/respond", {"action": "accept", "realm_id": receiver})

    trade("sylvan", "val_khor")
    projector.wait_for_function("projApp.map.caravans.length === 1", timeout=6000)
    for _ in range(4):
        trade("sylvan", "val_khor")
    projector.wait_for_timeout(1500)
    assert projector.evaluate("projApp.map.caravans.filter(c => [c.a, c.b].sort().join() === 'sylvan,val_khor').length") == 3
    reset_game(admin)
    projector.wait_for_function("projApp.map.caravans.length === 0", timeout=6000)
    assert errors == []
    projector.close()
    admin.context.close()
