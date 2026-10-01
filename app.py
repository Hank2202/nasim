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
from typing import Dict, Any

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, make_response

from models import Database, DEFAULT_REALMS
from engine import SummitEngine, load_scenario_config
from qr_generator import generate_qr_svg

app = Flask(__name__)
app.config["SECRET_KEY"] = "summit-of-realms-secret-key"

db = Database()
engine = SummitEngine(db)

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
    state = engine.get_full_state()
    lan_ip = get_lan_ip()
    port = request.environ.get("SERVER_PORT", "5000")
    server_url = f"http://{lan_ip}:{port}"
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
    state = engine.get_full_state()
    realm = next((r for r in state["realms"] if r["id"] == realm_id), None)
    if not realm:
        return redirect(url_for("index"))

    # Verify delegation auth cookie (or allow override via query param ?auth=1)
    auth_cookie = request.cookies.get(f"auth_{realm_id}")
    has_auth_param = request.args.get("auth") == "1"
    if not auth_cookie and not has_auth_param:
        return redirect(f"/?login={realm_id}")

    other_realms = [r for r in state["realms"] if r["id"] != realm_id]
    return render_template(
        "realm.html",
        realm=realm,
        other_realms=other_realms,
        realms=state["realms"],
        meta=state["meta"],
        trades=state["trades"],
        proposals=state["proposals"],
        news_feed=state["news_feed"],
        world_lore=state.get("world_lore", {})
    )

@app.route("/projector")
def projector_view():
    state = engine.get_full_state()
    lan_ip = get_lan_ip()
    port = request.environ.get("SERVER_PORT", "5000")
    server_url = f"http://{lan_ip}:{port}"
    qr_svg = generate_qr_svg(server_url, box_size=8)

    return render_template(
        "projector.html",
        state=state,
        server_url=server_url,
        qr_svg=qr_svg
    )

@app.route("/admin")
def admin_view():
    state = engine.get_full_state()
    lan_ip = get_lan_ip()
    port = request.environ.get("SERVER_PORT", "5000")
    server_url = f"http://{lan_ip}:{port}"
    qr_svg = generate_qr_svg(server_url, box_size=6)

    return render_template(
        "admin.html",
        state=state,
        server_url=server_url,
        qr_svg=qr_svg,
        host_ip=lan_ip,
        port=port
    )

@app.route("/overview")
def overview_view():
    state = engine.get_full_state()
    cfg = load_scenario_config()
    lan_ip = get_lan_ip()
    port = request.environ.get("SERVER_PORT", "5000")
    server_url = f"http://{lan_ip}:{port}"
    return render_template(
        "overview.html",
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
    server_url = f"http://{lan_ip}:{port}"
    svg_content = generate_qr_svg(server_url, box_size=10)
    return Response(svg_content, mimetype="image/svg+xml")

# -----------------------------------------------------------------------------
# Delegation Authentication APIs
# -----------------------------------------------------------------------------

@app.route("/api/auth/realm", methods=["POST"])
def api_auth_realm():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    pin = data.get("pin", "")

    if engine.verify_realm_pin(realm_id, pin):
        resp = make_response(jsonify({"success": True, "message": "Authentication successful."}))
        resp.set_cookie(f"auth_{realm_id}", "authenticated", max_age=86400, httponly=False, samesite="Lax")
        return resp
    else:
        return jsonify({"success": False, "message": "Invalid delegation PIN passcode."}), 401

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
    return jsonify(engine.get_full_state())

@app.route("/api/realm/action", methods=["POST"])
def api_realm_action():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    action_type = data.get("action")
    success, msg = engine.execute_sovereign_action(realm_id, action_type)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)

@app.route("/api/lore/quiz", methods=["POST"])
def api_lore_quiz():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    topic_id = data.get("topic_id")
    try:
        answer_index = int(data.get("answer_index", -1))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid answer format."}), 400

    if not realm_id or not topic_id or answer_index < 0:
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    ok, msg, payload = engine.submit_lore_quiz(realm_id, topic_id, answer_index)
    return jsonify({"success": ok, "message": msg, "data": payload}), (200 if ok else 400)

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

    success, msg, prop_id = engine.draft_proposal(proposer_id, title, description, effect_type, target_seconder_id)
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

@app.route("/api/admin/realm/delete", methods=["POST"])
def api_admin_realm_delete():
    data = request.get_json() or {}
    realm_id = data.get("realm_id")
    realms = db.get_state("realms", [])
    filtered = [r for r in realms if r["id"] != realm_id]
    if len(filtered) == len(realms):
        return jsonify({"success": False, "message": "Realm not found."}), 404

    db.set_state("realms", filtered)
    return jsonify({"success": True, "message": "Realm deleted."})

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
