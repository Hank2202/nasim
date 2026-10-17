"""
The Summit of Realms - Master Server Application
Flask web server running locally on 0.0.0.0:5000.
Features:
  - Delegation PIN Authentication & session access control
  - Functional Facilitator Command Deck (/admin) with timer editing and PIN resets
  - News-dominant Projector Overview Screen (/projector)
  - Qualitative Fog of War indicators
  - REST APIs for state synchronization, trade, voting, events, and plenary management.
100% self-contained and offline-first.
"""

import json
import os
import socket
import sys
import threading
import time
import uuid
from typing import Dict, Any

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, make_response
from itsdangerous import URLSafeSerializer, BadSignature
from werkzeug.middleware.proxy_fix import ProxyFix

from models import Database, DEFAULT_REALMS
from engine import SummitEngine, load_scenario_config
import wiki
from qr_generator import generate_qr_svg

app = Flask(__name__)
# Behind a hosting proxy (Render etc.) trust X-Forwarded-* so URLs/QR use https + the public host.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
# Cookies are only marked Secure when served over https (hosted); plain http on a LAN still works.
IS_HOSTED = bool(os.environ.get("PUBLIC_URL") or os.environ.get("RENDER"))

db = Database()
engine = SummitEngine(db)


# -----------------------------------------------------------------------------
# Signed-cookie authentication (cookies cannot be forged without SECRET_KEY)
# -----------------------------------------------------------------------------
_signer = URLSafeSerializer(app.config["SECRET_KEY"], salt="summit-auth")
_failed_logins: Dict[str, list] = {}

def _sign(role: str) -> str:
    return _signer.dumps(role)

def _cookie_role(name: str):
    raw = request.cookies.get(name)
    if not raw:
        return None
    try:
        return _signer.loads(raw)
    except BadSignature:
        return None

def is_admin() -> bool:
    return _cookie_role("auth_admin") == "admin"

def is_realm_authed(realm_id: str) -> bool:
    return bool(realm_id) and _cookie_role(f"auth_{realm_id}") == f"realm:{realm_id}"

def _auth_param_allowed() -> bool:
    # ?auth=1 shortcut exists only for automated tests / explicit local debugging.
    return app.config.get("TESTING", False) or os.environ.get("ALLOW_AUTH_PARAM") == "1"

def _login_throttled() -> bool:
    now = time.time()
    hits = [t for t in _failed_logins.get(request.remote_addr or "?", []) if now - t < 60]
    _failed_logins[request.remote_addr or "?"] = hits
    return len(hits) >= 10

def _note_failed_login() -> None:
    _failed_logins.setdefault(request.remote_addr or "?", []).append(time.time())

def _set_auth_cookie(resp, name: str, role: str):
    resp.set_cookie(name, _sign(role), max_age=86400, httponly=True, samesite="Lax", secure=IS_HOSTED)

def public_base_url() -> str:
    env = os.environ.get("PUBLIC_URL")
    if env:
        return env.rstrip("/")
    return request.host_url.rstrip("/")

_ACTOR_KEYS = ("realm_id", "sender_id", "proposer_id", "supporter_id", "seconder_id")

# The engine does read-modify-write on SQLite JSON blobs; serialise every request that
# touches game state so concurrent phones (threaded server) cannot lose updates.
_state_lock = threading.RLock()

@app.before_request
def acquire_state_lock():
    if not (request.path.startswith("/static/") or request.path.startswith("/api/wiki") or request.path == "/healthz"):
        _state_lock.acquire()
        request.environ["summit.locked"] = True

@app.teardown_request
def release_state_lock(_exc=None):
    if request.environ.pop("summit.locked", False):
        _state_lock.release()

@app.before_request
def enforce_api_auth():
    if app.config.get("TESTING", False) or request.method != "POST":
        return None
    path = request.path
    if path.startswith("/api/admin/"):
        if not is_admin():
            return jsonify({"success": False, "message": "Facilitator authentication required."}), 401
    elif path.startswith("/api/") and not path.startswith("/api/auth/"):
        data = request.get_json(silent=True) or {}
        actor = next((data[k] for k in _ACTOR_KEYS if data.get(k)), None)
        if not actor or not (is_realm_authed(actor) or is_admin()):
            return jsonify({"success": False, "message": "Delegation authentication required."}), 401
        if not is_admin():
            actor_realm = next((r for r in engine.db.get_state("realms", []) if r["id"] == actor), None)
            if not actor_realm or not actor_realm.get("active", True):
                return jsonify({"success": False, "message": "Your nation is not taking part in this summit."}), 403
    return None

def sanitize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Per-viewer filtering: no PINs, secret missions, other realms' exact stocks or quiz answers."""
    if is_admin() or app.config.get("TESTING", False):
        return state
    hidden = ("pin", "secret_missions_pool", "active_secret_missions", "claimed_lore", "failed_lore", "quiz_answers",
              "alchemical_grain", "aether_cores", "echo_silk", "military_power", "total_wealth")
    realms = []
    for r in state["realms"]:
        if is_realm_authed(r["id"]):
            r = {k: v for k, v in r.items() if k not in ("pin", "secret_missions_pool")}
        else:
            r = {k: v for k, v in r.items() if k not in hidden}
        realms.append(r)
    out = dict(state, realms=realms)
    out.pop("simulation_settings", None)
    return out

_CACHED_LAN_IP = None

def get_lan_ip() -> str:
    global _CACHED_LAN_IP
    if _CACHED_LAN_IP:
        return _CACHED_LAN_IP

    candidates = ["10.255.255.255", "192.168.1.1", "8.8.8.8"]
    for host in candidates:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((host, 1))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                _CACHED_LAN_IP = ip
                return ip
        except Exception:
            pass
        finally:
            s.close()

    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."):
            _CACHED_LAN_IP = ip
            return ip
    except Exception:
        pass

    _CACHED_LAN_IP = "127.0.0.1"
    return _CACHED_LAN_IP

# -----------------------------------------------------------------------------
# Frontend Routes
# -----------------------------------------------------------------------------

@app.route("/")
def index():
    state = sanitize_state(engine.get_full_state())
    lan_ip = get_lan_ip()
    port = request.environ.get("SERVER_PORT", "5000")
    server_url = public_base_url() if IS_HOSTED else f"http://{lan_ip}:{port}"
    login_target = request.args.get("login", "")
    return render_template(
        "lobby.html",
        realms=state["realms"],
        meta=state["meta"],
        server_url=server_url,
        lan_ip=lan_ip,
        port=port,
        login_target=login_target
    )

@app.route("/realm/<realm_id>")
def realm_view(realm_id: str):
    state = sanitize_state(engine.get_full_state())
    realm = next((r for r in state["realms"] if r["id"] == realm_id), None)
    if not realm or not realm.get("active", True):
        return redirect(url_for("index"))

    # Verify delegation auth cookie (or allow override via query param ?auth=1)
    has_auth_param = request.args.get("auth") == "1" and _auth_param_allowed()
    if not is_realm_authed(realm_id) and not has_auth_param:
        return redirect(f"/?login={realm_id}")

    session_id = request.cookies.get("summit_session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
    engine.register_realm_session(realm_id, session_id)

    other_realms = [r for r in state["realms"] if r["id"] != realm_id and r.get("active", True)]
    resp = make_response(render_template(
        "realm.html",
        realm=realm,
        other_realms=other_realms,
        realms=state["realms"],
        meta=state["meta"],
        trades=state["trades"],
        proposals=state["proposals"],
        news_feed=state["news_feed"],
        world_lore=state.get("world_lore", {})
    ))
    if not request.cookies.get("summit_session_id"):
        resp.set_cookie("summit_session_id", session_id, max_age=86400, httponly=False, samesite="Lax")
    return resp

@app.route("/projector")
def projector_view():
    state = sanitize_state(engine.get_full_state())
    lan_ip = get_lan_ip()
    port = request.environ.get("SERVER_PORT", "5000")
    server_url = public_base_url() if IS_HOSTED else f"http://{lan_ip}:{port}"
    qr_svg = generate_qr_svg(server_url, box_size=8)

    return render_template(
        "projector.html",
        state=state,
        server_url=server_url,
        qr_svg=qr_svg
    )

@app.route("/admin")
def admin_view():
    has_auth_param = request.args.get("auth") == "1" and _auth_param_allowed()
    is_testing = app.config.get("TESTING", False)
    if not is_testing and not is_admin() and not has_auth_param:
        return render_template("admin_login.html")

    state = engine.get_full_state()
    lan_ip = get_lan_ip()
    port = request.environ.get("SERVER_PORT", "5000")
    server_url = public_base_url() if IS_HOSTED else f"http://{lan_ip}:{port}"
    qr_svg = generate_qr_svg(server_url, box_size=6)

    return render_template(
        "admin.html",
        state=state,
        server_url=server_url,
        qr_svg=qr_svg,
        host_ip=lan_ip,
        port=port
    )

# -----------------------------------------------------------------------------
# Spireopedia (in-game encyclopedia, read in the phone's Wiki tab)
# -----------------------------------------------------------------------------

app.jinja_env.globals["realm_article"] = wiki.realm_article

def _in_game_viewer() -> bool:
    """Any logged-in delegation or the facilitator may read the encyclopedia."""
    if app.config.get("TESTING", False) or is_admin():
        return True
    return any(is_realm_authed(k[len("auth_"):]) for k in request.cookies if k.startswith("auth_") and k != "auth_admin")

@app.route("/api/wiki")
def api_wiki_index():
    if not _in_game_viewer():
        return jsonify({"success": False, "message": "Join a delegation to read the Spireopedia."}), 401
    return jsonify({"success": True, **wiki.index_payload()})

@app.route("/api/wiki/search")
def api_wiki_search():
    if not _in_game_viewer():
        return jsonify({"success": False, "message": "Join a delegation to read the Spireopedia."}), 401
    hits = wiki.search(request.args.get("q", ""))
    return jsonify({"success": True, "results": [{k: h[k] for k in ("slug", "title", "subtitle", "category")} for h in hits]})

@app.route("/api/wiki/<slug>")
def api_wiki_article(slug: str):
    if not _in_game_viewer():
        return jsonify({"success": False, "message": "Join a delegation to read the Spireopedia."}), 401
    article = wiki.article_payload(slug)
    if not article:
        return jsonify({"success": False, "message": "Article not found."}), 404
    return jsonify({"success": True, "article": article})

@app.route("/healthz")
def healthz():
    return "ok"

@app.route("/overview")
def overview_view():
    state = sanitize_state(engine.get_full_state())
    cfg = load_scenario_config()
    lan_ip = get_lan_ip()
    port = request.environ.get("SERVER_PORT", "5000")
    server_url = public_base_url() if IS_HOSTED else f"http://{lan_ip}:{port}"
    from engine import load_quiz
    return render_template(
        "overview.html",
        quiz_count=len(load_quiz()["questions"]),
        state=state,
        cfg=cfg,
        realms=state["realms"],
        meta=state["meta"],
        server_url=server_url,
        lan_ip=lan_ip,
        port=port
    )

@app.route("/rules")
@app.route("/guide")
def rules_redirect():
    return redirect(url_for("overview_view"))

@app.route("/qr")
def qr_code_endpoint():
    lan_ip = get_lan_ip()
    port = request.environ.get("SERVER_PORT", "5000")
    server_url = public_base_url() if IS_HOSTED else f"http://{lan_ip}:{port}"
    svg_content = generate_qr_svg(server_url, box_size=10)
    return Response(svg_content, mimetype="image/svg+xml")

# -----------------------------------------------------------------------------
# Delegation Authentication APIs
# -----------------------------------------------------------------------------

@app.route("/api/auth/realm", methods=["POST"])
def api_auth_realm():
    data = request.get_json(silent=True) or {}
    realm_id = data.get("realm_id")
    pin = data.get("pin", "")

    if not realm_id:
        return jsonify({"success": False, "message": "realm_id is required."}), 400

    session_id = request.cookies.get("summit_session_id")
    if not session_id:
        session_id = str(uuid.uuid4())

    # Check if realm is full and session is NOT already registered for this realm
    if engine.is_realm_capacity_full(realm_id) and not engine.is_session_registered(realm_id, session_id):
        realms = engine.db.get_state("realms", [])
        target = next((r for r in realms if r["id"] == realm_id), None)
        cap = target.get("player_count", 2) if target else 2
        occ = engine.get_connected_player_count(realm_id)
        return jsonify({
            "success": False,
            "message": f"Delegation capacity reached ({occ}/{cap} seats occupied). Please choose another realm.",
            "is_full": True
        }), 403

    if _login_throttled():
        return jsonify({"success": False, "message": "Too many failed attempts. Wait a minute."}), 429
    if engine.verify_realm_pin(realm_id, pin):
        engine.register_realm_session(realm_id, session_id)
        resp = make_response(jsonify({"success": True, "message": "Authentication successful."}))
        _set_auth_cookie(resp, f"auth_{realm_id}", f"realm:{realm_id}")
        # Non-secret marker so the lobby page JS can tell this device already logged in.
        resp.set_cookie(f"has_auth_{realm_id}", "1", max_age=86400, samesite="Lax", secure=IS_HOSTED)
        resp.set_cookie("summit_session_id", session_id, max_age=86400, httponly=False, samesite="Lax", secure=IS_HOSTED)
        return resp
    else:
        _note_failed_login()
        return jsonify({"success": False, "message": "Invalid delegation PIN passcode."}), 401

@app.route("/api/auth/realm/logout", methods=["POST"])
def api_auth_realm_logout():
    data = request.get_json(silent=True) or {}
    realm_id = data.get("realm_id")
    session_id = request.cookies.get("summit_session_id")
    if realm_id and session_id:
        engine.remove_realm_session(realm_id, session_id)
    resp = make_response(jsonify({"success": True, "message": "Logged out from delegation."}))
    if realm_id:
        resp.delete_cookie(f"auth_{realm_id}")
        resp.delete_cookie(f"has_auth_{realm_id}")
    return resp

@app.route("/api/auth/admin", methods=["POST"])
def api_auth_admin():
    data = request.get_json(silent=True) or {}
    passcode = data.get("passcode", "")
    if _login_throttled():
        return jsonify({"success": False, "message": "Too many failed attempts. Wait a minute."}), 429
    if engine.verify_admin_passcode(passcode):
        resp = make_response(jsonify({"success": True, "message": "Command Deck unlocked."}))
        _set_auth_cookie(resp, "auth_admin", "admin")
        return resp
    else:
        _note_failed_login()
        return jsonify({"success": False, "message": "Invalid facilitator passcode."}), 401

@app.route("/api/auth/admin/logout", methods=["POST"])
def api_auth_admin_logout():
    resp = make_response(jsonify({"success": True, "message": "Command Deck locked."}))
    resp.delete_cookie("auth_admin")
    return resp

@app.route("/api/admin/pin/reset", methods=["POST"])
def api_admin_pin_reset():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    new_pin = data.get("pin", "1001")
    ok, msg = engine.admin_set_realm_pin(realm_id, new_pin)
    return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

# -----------------------------------------------------------------------------
# REST APIs - Core State & Participant Actions
# -----------------------------------------------------------------------------

@app.route("/api/state")
def api_state():
    session_id = request.cookies.get("summit_session_id")
    if session_id:
        for key, val in request.cookies.items():
            if key.startswith("auth_") and key != "auth_admin":
                r_id = key[len("auth_"):]
                if is_realm_authed(r_id):
                    engine.register_realm_session(r_id, session_id)
    return jsonify(sanitize_state(engine.get_full_state()))

@app.route("/api/realm/action", methods=["POST"])
def api_realm_action():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    action_type = data.get("action")
    success, msg = engine.execute_sovereign_action(realm_id, action_type)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/quiz/<realm_id>")
def api_quiz(realm_id: str):
    if not (app.config.get("TESTING", False) or is_realm_authed(realm_id) or is_admin()):
        return jsonify({"success": False, "message": "Delegation authentication required."}), 401
    quiz = engine.get_quiz_for_realm(realm_id)
    if quiz is None:
        return jsonify({"success": False, "message": "Realm not found."}), 404
    return jsonify({"success": True, **quiz})

@app.route("/api/lore/quiz", methods=["POST"])
def api_lore_quiz():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    question_id = data.get("question_id") or data.get("topic_id")
    try:
        answer_index = int(data.get("answer_index", -1))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid answer format."}), 400

    if not realm_id or not question_id or answer_index < 0:
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    ok, msg, payload = engine.submit_lore_quiz(realm_id, question_id, answer_index)
    # A wrong answer is a valid submission (200); 400 only for rejected submissions.
    status = 200 if payload else 400
    return jsonify({"success": ok, "message": msg, "data": payload}), status

@app.route("/api/trade/create", methods=["POST"])
def api_trade_create():
    data = request.get_json() or {}
    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")
    offer_res = data.get("offer_resource")
    offer_amt = int(data.get("offer_amount", 0))
    req_res = data.get("request_resource")
    req_amt = int(data.get("request_amount", 0))
    note = data.get("note", "")

    success, msg = engine.create_trade(sender_id, receiver_id, offer_res, offer_amt, req_res, req_amt, note)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/trade/<trade_id>/respond", methods=["POST"])
def api_trade_respond(trade_id: str):
    data = request.get_json() or {}
    action = data.get("action")
    realm_id = data.get("realm_id")

    success, msg = engine.respond_trade(trade_id, action, realm_id)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/proposal/create", methods=["POST"])
def api_proposal_create():
    data = request.get_json() or {}
    proposer_id = data.get("proposer_id")
    title = data.get("title", "")
    description = data.get("description", "")
    effect_type = data.get("effect_type", "custom")
    target_seconder_id = data.get("target_seconder_id")

    target_realm_id = data.get("target_realm_id")
    success, msg, prop_id = engine.draft_proposal(proposer_id, title, description, effect_type,
                                                  target_seconder_id, target_realm_id)
    return jsonify({"success": success, "message": msg, "proposal_id": prop_id}), (200 if success else 400)

@app.route("/api/proposal/<prop_id>/support", methods=["POST"])
def api_proposal_support(prop_id: str):
    data = request.get_json() or {}
    supporter_id = data.get("supporter_id") or data.get("seconder_id")
    success, msg = engine.support_proposal(prop_id, supporter_id)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/proposal/<prop_id>/second", methods=["POST"])
def api_proposal_second(prop_id: str):
    data = request.get_json() or {}
    seconder_id = data.get("seconder_id")
    success, msg = engine.support_proposal(prop_id, seconder_id)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/plenary/vote", methods=["POST"])
def api_plenary_vote():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    prop_id = data.get("proposal_id")
    choice = data.get("choice")
    success, msg = engine.cast_plenary_vote(realm_id, prop_id, choice)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/assembly/vote", methods=["POST"])
def api_assembly_vote():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    choice = data.get("choice")
    success, msg = engine.cast_vote(realm_id, choice)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

# -----------------------------------------------------------------------------
# Facilitator Admin APIs - Timer & Plenary
# -----------------------------------------------------------------------------

@app.route("/api/admin/timer/set", methods=["POST"])
def api_admin_timer_set():
    data = request.get_json() or {}
    seconds = int(data.get("seconds", 300))
    engine.admin_set_timer(seconds)
    return jsonify({"success": True, "seconds": seconds})

@app.route("/api/admin/timer/adjust", methods=["POST"])
def api_admin_timer_adjust():
    data = request.get_json() or {}
    delta = int(data.get("delta_seconds", 60))
    engine.admin_adjust_timer(delta)
    return jsonify({"success": True})

@app.route("/api/admin/plenary/start", methods=["POST"])
def api_admin_plenary_start():
    success, msg = engine.start_plenary_session()
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/admin/plenary/call_vote", methods=["POST"])
def api_admin_plenary_call_vote():
    success, msg = engine.start_grand_motion_vote()
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/admin/plenary/next", methods=["POST"])
def api_admin_plenary_next():
    success, msg = engine.advance_grand_plenary_next()
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/admin/plenary/conclude_quick", methods=["POST"])
def api_admin_plenary_conclude_quick():
    success, msg = engine.conclude_quick_plenary()
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/admin/turn/next", methods=["POST"])
def api_admin_turn_next():
    res = engine.process_end_of_turn()
    return jsonify({"success": True, "result": res})

@app.route("/api/admin/summit/conclude", methods=["POST"])
def api_admin_summit_conclude():
    ok, msg, outcome = engine.conclude_summit()
    return jsonify({"success": ok, "message": msg, "outcome": outcome}), (200 if ok else 400)

@app.route("/api/admin/timer/control", methods=["POST"])
def api_admin_timer_control():
    data = request.get_json() or {}
    action = data.get("action")
    total_seconds = data.get("total_seconds")
    if total_seconds is not None:
        total_seconds = int(total_seconds)
    engine.admin_control_timer(action, total_seconds)
    return jsonify({"success": True})

@app.route("/api/admin/discussion_timer/control", methods=["POST"])
def api_admin_discussion_timer_control():
    data = request.get_json() or {}
    action = data.get("action")
    total_seconds = data.get("total_seconds")
    if total_seconds is not None:
        total_seconds = int(total_seconds)
    engine.admin_control_discussion_timer(action, total_seconds)
    return jsonify({"success": True})

@app.route("/api/admin/chime", methods=["POST"])
def api_admin_chime():
    data = request.get_json() or {}
    cue_type = data.get("type", "gong")
    msg = data.get("message", "Attention Sovereign Delegates")
    engine.trigger_audio_cue(cue_type, msg)
    return jsonify({"success": True})

@app.route("/api/admin/news/broadcast", methods=["POST"])
def api_admin_news_broadcast():
    data = request.get_json() or {}
    headline = data.get("headline", "URGENT DISPATCH")
    detail = data.get("detail", "")
    news_type = data.get("type", "system")
    engine.add_news(news_type, headline, detail)
    engine.trigger_audio_cue("alert", headline)
    return jsonify({"success": True})

@app.route("/api/admin/realm/override", methods=["POST"])
def api_admin_realm_override():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    updates = data.get("updates", {})
    success, msg = engine.admin_override_realm(realm_id, updates)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/admin/assembly/control", methods=["POST"])
def api_admin_assembly_control():
    data = request.get_json() or {}
    action = data.get("action")
    success, msg = engine.admin_assembly_override(action)
    return jsonify({"success": success, "message": msg})

@app.route("/api/admin/realm/toggle", methods=["POST"])
def api_admin_realm_toggle():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    active = data.get("active")
    success, msg = engine.admin_toggle_realm(realm_id, active)
    st = engine.get_full_state()
    target_realm = next((r for r in st["realms"] if r["id"] == realm_id), None)
    is_active = bool(target_realm.get("active", 1)) if target_realm else False
    return jsonify({"success": success, "message": msg, "active": is_active}), (200 if success else 400)

@app.route("/api/admin/realm/player_count", methods=["POST"])
def api_admin_realm_player_count():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    try:
        count = int(data.get("player_count", 1))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid player count."}), 400
    success, msg = engine.admin_set_player_count(realm_id, count)
    return jsonify({"success": success, "message": msg, "player_count": count}), (200 if success else 400)

@app.route("/api/admin/crisis/round", methods=["POST"])
def api_admin_crisis_round():
    data = request.get_json() or {}
    try:
        round_num = int(data.get("round") or data.get("round_num") or 1)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid round number."}), 400
    success, msg = engine.trigger_round_crisis(round_num)
    return jsonify({"success": success, "message": msg, "round": round_num}), (200 if success else 400)

@app.route("/api/admin/realm/add", methods=["POST"])
def api_admin_realm_add():
    data = request.get_json() or {}
    realm_id = data.get("id", "").strip().lower().replace(" ", "_")
    name = data.get("name", "").strip()
    if not realm_id or not name:
        return jsonify({"success": False, "message": "Identifier and name are required."}), 400

    realms = db.get_state("realms", [])
    if any(r["id"] == realm_id for r in realms):
        return jsonify({"success": False, "message": "A realm with this ID already exists."}), 400

    new_realm = {
        "id": realm_id,
        "name": name,
        "theme_color": "#ffffff",
        "icon": "shield",
        "ethos": data.get("values", "Autonomy, Trade, Innovation"),
        "values": data.get("values", "Autonomy, Trade, Innovation"),
        "pin": data.get("pin", "1001"),
        "private_agenda": data.get("private_agenda", "Advance the sovereign destiny of your people."),
        "alchemical_grain": int(data.get("alchemical_grain", 50)),
        "aether_cores": int(data.get("aether_cores", 50)),
        "echo_silk": int(data.get("echo_silk", 50)),
        "public_vitality": int(data.get("public_vitality", 75)),
        "diplomatic_standing": int(data.get("diplomatic_standing", 60)),
        "civil_stability": int(data.get("civil_stability", 70)),
        "tech_efficiency_unlocked": False,
        "is_quarantined": False,
        "is_striking": False,
        "is_starving": False,
    }
    realms.append(new_realm)
    engine._recalculate_all_realms(realms)
    db.set_state("realms", realms)
    engine.add_news("diplomacy", f"NEW DELEGATION ACCREDITED: {name.upper()}", "A new sovereign realm has been seated at the summit table.")
    return jsonify({"success": True, "message": f"{name} admitted."})

@app.route("/api/admin/realm/remove", methods=["POST"])
@app.route("/api/admin/realm/delete", methods=["POST"])
def api_admin_realm_remove():
    data = request.get_json(silent=True) or {}
    realm_id = data.get("realm_id")
    if not realm_id:
        return jsonify({"success": False, "message": "realm_id is required."}), 400

    ok, msg = engine.admin_remove_realm(realm_id)
    if ok:
        return jsonify({"success": True, "message": msg, "state": engine.get_full_state()})
    return jsonify({"success": False, "message": msg}), 400

@app.route("/api/admin/realms/set_count", methods=["POST"])
def api_admin_realms_set_count():
    data = request.get_json(silent=True) or {}
    count = data.get("count")
    if count is None:
        return jsonify({"success": False, "message": "count parameter is required."}), 400
    try:
        count = int(count)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid count parameter."}), 400

    ok, msg = engine.admin_set_active_realm_count(count)
    if ok:
        return jsonify({"success": True, "message": msg, "state": engine.get_full_state()})
    return jsonify({"success": False, "message": msg}), 400

@app.route("/api/admin/realm/clear_sessions", methods=["POST"])
def api_admin_realm_clear_sessions():
    data = request.get_json(silent=True) or {}
    realm_id = data.get("realm_id")
    engine.clear_realm_sessions(realm_id)
    msg = f"Active sessions cleared for {realm_id}." if realm_id else "All delegation sessions cleared."
    return jsonify({"success": True, "message": msg, "state": engine.get_full_state()})

@app.route("/api/events")
def api_events():
    events = engine.get_catalog_events()
    return jsonify({"events": events})

@app.route("/api/admin/event/trigger", methods=["POST"])
def api_admin_event_trigger():
    data = request.get_json() or {}
    event_id = data.get("event_id")
    ok, msg = engine.trigger_catalog_event(event_id)
    return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

@app.route("/api/admin/event/auto", methods=["POST"])
def api_admin_event_auto():
    ok, msg, ev = engine.auto_draw_next_event()
    return jsonify({"success": ok, "message": msg, "event": ev}), (200 if ok else 400)

@app.route("/api/admin/config/toggle_auto_crisis", methods=["POST"])
def api_admin_toggle_auto_crisis():
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", False))
    meta = db.get_state("meta", {})
    meta["auto_inject_crisis"] = enabled
    db.set_state("meta", meta)
    return jsonify({"success": True, "auto_inject_crisis": enabled})

@app.route("/admin/report")
def admin_report():
    """Results report: printable HTML (default) or JSON (?format=json). Facilitator only."""
    if not (is_admin() or app.config.get("TESTING", False)):
        return redirect(url_for("admin_view"))
    report = engine.build_report()
    stamp = time.strftime("%Y-%m-%d-%H%M")
    if request.args.get("format") == "json":
        resp = make_response(json.dumps(report, ensure_ascii=False, indent=1))
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        resp.headers["Content-Disposition"] = f'attachment; filename="summit-results-{stamp}.json"'
        return resp
    resp = make_response(render_template("report.html", r=report))
    if request.args.get("download") == "1":
        resp.headers["Content-Disposition"] = f'attachment; filename="summit-results-{stamp}.html"'
    return resp

@app.route("/api/admin/reflection", methods=["POST"])
def api_admin_reflection():
    data = request.get_json(silent=True) or {}
    ok, msg = engine.admin_set_reflection(data.get("step"))
    return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

# -----------------------------------------------------------------------------
# Saves: server autosaves every 5 minutes + downloadable save files
# -----------------------------------------------------------------------------
@app.route("/api/admin/saves")
def api_admin_saves():
    if not (is_admin() or app.config.get("TESTING", False)):
        return jsonify({"success": False, "message": "Facilitator authentication required."}), 401
    return jsonify({"success": True, "interval": engine.AUTOSAVE_INTERVAL, "saves": engine.db.list_autosaves()})

@app.route("/api/admin/save/export")
def api_admin_save_export():
    if not (is_admin() or app.config.get("TESTING", False)):
        return jsonify({"success": False, "message": "Facilitator authentication required."}), 401
    save_id = request.args.get("id", type=int)
    snapshot = engine.db.get_autosave(save_id) if save_id else engine.db.dump_all()
    if snapshot is None:
        return jsonify({"success": False, "message": "Save not found."}), 404
    return jsonify({"success": True, "format": "summit-of-realms-save", "saved_at": time.time(), "snapshot": snapshot})

@app.route("/api/admin/save/now", methods=["POST"])
def api_admin_save_now():
    save_id = engine.autosave(label="Manual save", force=True)
    return jsonify({"success": True, "message": "Game saved.", "id": save_id})

@app.route("/api/admin/save/restore", methods=["POST"])
def api_admin_save_restore():
    data = request.get_json(silent=True) or {}
    snapshot = engine.db.get_autosave(int(data["id"])) if data.get("id") else data.get("snapshot")
    ok, msg = engine.restore_snapshot(snapshot)
    return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

@app.route("/api/admin/reset", methods=["POST"])
def api_admin_reset():
    engine.reset_simulation()
    return jsonify({"success": True, "message": "Simulation reset."})

if __name__ == "__main__":
    lan_ip = get_lan_ip()
    port = int(os.environ.get("PORT", 5000))

    print("=" * 65)
    print("  THE SUMMIT OF REALMS - GEOPOLITICAL WORKSHOP PLATFORM")
    print("=" * 65)
    print(f"  * Host LAN IP:    http://{lan_ip}:{port}")
    print(f"  * Participant UI: http://{lan_ip}:{port}")
    print(f"  * Game Overview:  http://{lan_ip}:{port}/overview")
    print(f"  * DM Deck:        http://{lan_ip}:{port}/admin")
    print(f"  * Projector View: http://{lan_ip}:{port}/projector")
    print(f"  * Local Loopback: http://127.0.0.1:{port}")
    print("=" * 65)

    app.run(host="0.0.0.0", port=port, debug=False)
