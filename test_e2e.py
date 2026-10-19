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
    expect(page.locator(".setup-banner")).to_contain_text("Set up this summit before you start")
    page.close()


def test_lobby_says_which_nations_are_easy_and_which_are_hard(server, browser):
    page = browser.new_page()
    page.goto(server + "/")
    expect(page.locator("#card-solaria .diff-badge")).to_contain_text("Easy")
    expect(page.locator("#card-val_khor .diff-badge")).to_contain_text("Hard")
    expect(page.locator("#card-val_khor .diff-note")).to_contain_text("30 Grain")
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
    tab(sylvan, "Motions")
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

    admin.locator("button", has_text="Convene Between-Rounds Plenary").click()
    confirm(admin)
    for phone in (sylvan, valkhor):
        vote = phone.locator("#plenary-voting-actions-container button", has_text="SUPPORT")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
        confirm(phone)
    admin.locator("button", has_text="Settle Plenary").click()
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

    tab(sylvan, "Motions")
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

    admin.locator("button", has_text="Convene Between-Rounds Plenary").click()
    confirm(admin)
    for phone in (sylvan, umbra):
        vote = phone.locator("#plenary-voting-actions-container button", has_text="SUPPORT")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
        confirm(phone)
    admin.locator("button", has_text="Settle Plenary").click()
    confirm(admin)

    tab(sylvan, "Realm")
    expect(sylvan.locator("#grain-val")).to_have_text("88", timeout=5000)
    tab(umbra, "Realm")
    expect(umbra.locator("#grain-val")).to_have_text("52", timeout=5000)
    # and the facilitator sees what the motion does and what it did, without doing anything by hand
    admin.locator(".admin-tab-btn", has_text="Resolutions").click()
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
    assert aethelgard.locator("#war-attack-btn").is_disabled()
    aethelgard.locator(".war-chip", has_text="Sylvan Concordat").click()
    expect(aethelgard.locator(".scout-odds")).to_be_visible(timeout=5000)
    expect(aethelgard.locator("#war-scout")).to_contain_text("Their Military:")
    expect(aethelgard.locator("#war-scout")).to_contain_text("What your scouts could find out")
    assert "luck" not in aethelgard.locator("#war-scout").inner_text().lower()
    assert not aethelgard.locator("#war-attack-btn").is_disabled()
    aethelgard.locator("#war-attack-btn").click()
    expect(aethelgard.locator(".confirm-card")).to_contain_text("Attack Sylvan Concordat?")
    confirm(aethelgard)

    # the attacker's phone, the defender's phone and the projector all show the battle
    expect(aethelgard.locator(".bs-modal .bs")).to_be_visible(timeout=5000)
    expect(aethelgard.locator(".bs-modal .bs.bs-done")).to_be_visible(timeout=14000)
    expect(aethelgard.locator(".bs-modal-extra")).to_contain_text("How it went for you (attacking)")
    expect(sylvan.locator(".bs-modal-extra")).to_contain_text("How it went for you (defending)", timeout=6000)
    expect(projector.locator("#battle-pop.show .bs")).to_be_visible(timeout=6000)
    expect(projector.locator("#battle-pop")).to_contain_text("Aethelgard Dominion")
    expect(projector.locator("#battle-pop .bs-done")).to_be_visible(timeout=14000)
    expect(projector.locator("#battle-pop .bs-spoils")).to_be_visible()

    # one march per turn; the facilitator sees both sides' numbers
    aethelgard.locator(".bs-modal #bs-close").click()
    expect(aethelgard.locator("#war-status")).to_contain_text("0 more times", timeout=8000)
    admin.locator(".admin-tab-btn", has_text="Events").click()
    expect(admin.locator("#admin-war-log")).to_contain_text("Aethelgard Dominion")
    expect(admin.locator("#admin-war-log")).to_contain_text("readiness")
    expect(admin.locator("#admin-war-log")).to_contain_text("luck")                 # only the facilitator sees the luck
    assert errors == [] and sylvan_errors == [] and projector_errors == []
    admin.close()


def test_clock_console_works_in_every_phase(server, browser):
    admin = admin_page(browser, server)
    reset_game(admin)
    admin.locator(".admin-tab-btn", has_text="Pacing").click()
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
    admin.locator(".admin-tab-btn", has_text="Resource Overrides").click()
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
    admin.locator(".admin-tab-btn", has_text="Resource Overrides").click()
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
    admin.locator(".admin-tab-btn", has_text="Resource Overrides").click()
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
    tab(sylvan, "Motions")
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

    admin.locator("button", has_text="Convene Between-Rounds Plenary").click()
    confirm(admin)
    for phone in (sylvan, umbra):
        vote = phone.locator("#plenary-voting-actions-container button", has_text="SUPPORT")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
        confirm(phone)
    admin.locator("button", has_text="Settle Plenary").click()
    confirm(admin)

    admin.locator(".admin-tab-btn", has_text="Resolutions").click()
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
    tab(sylvan, "Motions")
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

    admin.locator(".admin-tab-btn", has_text="Resolutions").click()
    question = admin.locator("#gm-inbox .inset", has_text="Can grain be traded in Turn 3?")
    expect(question).to_contain_text("waiting for the Assembly vote", timeout=5000)
    admin.locator(".admin-tab-btn", has_text="Pacing").click()
    admin.locator("button", has_text="Convene Between-Rounds Plenary").click()
    confirm(admin)
    for phone in (aquila, valkhor):
        vote = phone.locator("#plenary-voting-actions-container button", has_text="SUPPORT")
        expect(vote).to_be_visible(timeout=5000)
        vote.click()
        confirm(phone)
    admin.locator("button", has_text="Settle Plenary").click()
    confirm(admin)

    admin.locator(".admin-tab-btn", has_text="Resolutions").click()
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
    admin.fill("#quiz_seconds", "12")
    admin.locator("#attacks_from_turn").fill("3")
    admin.locator("input[name=scenario][value=armageddon]").check()     # fills in its suggested event numbers
    expect(admin.locator("#large_per_turn")).to_have_value("3")
    admin.fill("#event_max", "7.5")
    admin.locator("button", has_text="Start a new summit").click()
    confirm(admin)
    expect(admin.locator(".page-title")).to_have_text("Facilitator Command Deck", timeout=5000)
    settings = state(admin)["game_settings"]
    assert settings["difficulty"] == "gentle" and settings["working_session_seconds"] == 720
    assert settings["scenario"] == "armageddon" and settings["large_events_per_turn"] == 3
    assert settings["minor_event_max"] == 7.5 and settings["minor_events_per_turn"] == 10
    assert settings["quiz_seconds"] == 12 and settings["attacks_from_turn"] == 3
    admin.close()
