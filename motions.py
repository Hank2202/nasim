"""
Motions with automatic effects.

A motion carries a short list of structured effect "lines". The nations read the same sentences that the game
applies when the motion passes, so the facilitator never has to carry out a motion by hand.

Lines (all amounts are whole numbers):
  transfer     payers give `amount` each of `resource`; the pool is shared equally by the receivers
  levy         targets lose `amount` of `resource` (a penalty or fine)
  boost        targets gain `amount` of `resource` (only fixed templates in scenario_config.json can create value)

Nothing a player writes can take more than a nation has, and receivers only get what was actually taken.
  redistribute nations above `above` pay up to `give`; the pool goes to nations below `below` (at most `receive` each)
  flag         marks targets (the Frontier Cordon)

Targets are lists of nation ids or tokens: @me (the proposer), @target (the nation chosen in the form), @all,
@others, and, resolved when the motion passes, @richest, @poorest, @strongest, @weakest.
"""

from typing import Any, Dict, List, Optional, Tuple

FIELDS = {"grain": "alchemical_grain", "cores": "aether_cores", "silk": "echo_silk", "military": "military_power",
          "vitality": "public_vitality", "standing": "diplomatic_standing", "stability": "civil_stability"}
LABELS = {"grain": "Grain", "cores": "Cores", "silk": "Silk", "military": "Military",
          "vitality": "Vitality", "standing": "Standing", "stability": "Stability"}
CAPPED = {"vitality", "standing", "stability"}                     # kept between 0 and 100
TRANSFER_RESOURCES = ("grain", "cores", "silk", "military", "standing")
REDISTRIBUTE_RESOURCES = ("grain", "cores", "silk")
LEVY_RESOURCES = tuple(FIELDS)
MAX_AMOUNT = {res: 999 for res in FIELDS}                          # only a sanity limit: the real limit is what the nation has
DYNAMIC = {"@richest": "the richest nation", "@poorest": "the poorest nation",
           "@strongest": "the strongest army", "@weakest": "the weakest army"}
GROUPS = {"@all": "all nations", "@others": "all other nations"}
MAX_PACT_LINES = 3


def _int(value: Any, lo: int, hi: int, what: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a whole number.")
    if not lo <= n <= hi:
        raise ValueError(f"{what} must be between {lo} and {hi}.")
    return n


def _tokens(value: Any, what: str) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"Choose at least one nation for {what}.")
    return [str(v) for v in value][:12]


def _check_tokens(tokens: List[str], ids: set, what: str, allow_dynamic: bool) -> None:
    for t in tokens:
        if t in ids or t in ("@me", "@target") or t in GROUPS:
            continue
        if allow_dynamic and t in DYNAMIC:
            continue
        raise ValueError(f"{what}: '{t}' is not a nation at this summit.")


def _wealth(r: Dict[str, Any]) -> int:
    return r.get("alchemical_grain", 0) + r.get("aether_cores", 0) + r.get("echo_silk", 0)


def resolve(tokens: List[str], active: List[Dict[str, Any]], proposer_id: Optional[str]) -> List[str]:
    """Nation ids a list of tokens points at right now (active nations only, no duplicates, in table order)."""
    ids = [r["id"] for r in active]
    out: List[str] = []
    for t in tokens:
        if t == "@me":
            found = [proposer_id]
        elif t == "@all":
            found = ids
        elif t == "@others":
            found = [i for i in ids if i != proposer_id]
        elif t == "@richest" and active:
            found = [max(active, key=_wealth)["id"]]
        elif t == "@poorest" and active:
            found = [min(active, key=_wealth)["id"]]
        elif t == "@strongest" and active:
            found = [max(active, key=lambda r: r.get("military_power", 0))["id"]]
        elif t == "@weakest" and active:
            found = [min(active, key=lambda r: r.get("military_power", 0))["id"]]
        else:
            found = [t]
        for f in found:
            if f in ids and f not in out:
                out.append(f)
    return out


def _who(tokens: List[str], names: Dict[str, str], proposer_id: Optional[str]) -> str:
    parts = []
    for t in tokens:
        if t in GROUPS:
            parts.append(GROUPS[t])
        elif t in DYNAMIC:
            parts.append(DYNAMIC[t])
        elif t == "@me":
            parts.append(names.get(proposer_id, "the proposer"))
        else:
            parts.append(names.get(t, t))
    if len(parts) <= 1:
        return parts[0] if parts else "nobody"
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def describe(line: Dict[str, Any], names: Dict[str, str], proposer_id: Optional[str] = None) -> str:
    """One plain sentence: exactly what the game does for this line."""
    kind, res = line["kind"], line.get("resource")
    label = LABELS.get(res, res)
    if kind == "transfer":
        payers, receivers = _who(line["payers"], names, proposer_id), _who(line["receivers"], names, proposer_id)
        each = "each give" if len(line["payers"]) > 1 or line["payers"][0] in GROUPS else "gives"
        return (f"{payers} {each} {line['amount']} {label} (or everything it has, if that is less); only what is really taken is shared equally by {receivers}.")
    if kind == "levy":
        who = _who(line["targets"], names, proposer_id)
        verb = "lose" if len(line["targets"]) > 1 or line["targets"][0] in GROUPS else "loses"
        return f"{who} {verb} {line['amount']} {label} (or everything it has, if that is less)."
    if kind == "boost":
        who = _who(line["targets"], names, proposer_id)
        verb = "gain" if len(line["targets"]) > 1 or line["targets"][0] in GROUPS else "gains"
        return f"{who} {verb} {line['amount']} {label}."
    if kind == "redistribute":
        return (f"Every nation with more than {line['above']} {label} gives {line['give']} (never more than it has above the limit's worth of stock); "
                f"what is collected goes to nations with less than {line['below']}, at most {line['receive']} each. Nothing is created: only what is "
                f"collected is handed out.")
    if kind == "flag":
        who = _who(line["targets"], names, proposer_id)
        return f"{who} is cordoned off: plague, border surges and tsunamis hit it far less hard, and its defence in battle is stronger."
    return ""


def build_lines(template: Dict[str, Any], params: Dict[str, Any], proposer_id: str,
                active: List[Dict[str, Any]], target_realm_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Turn a template and the player's choices into validated lines. Raises ValueError with a message for the player."""
    params = params or {}
    ids = {r["id"] for r in active}
    builder = template.get("builder", "fixed")
    defaults = template.get("defaults", {})
    lines: List[Dict[str, Any]] = []

    if builder == "fixed" or builder == "cordon":
        target = target_realm_id if builder == "cordon" else None
        if builder == "cordon" and target not in ids:
            raise ValueError("Choose the nation for this motion.")
        for raw in template.get("lines", []):
            line = dict(raw)
            for key in ("targets", "payers", "receivers"):
                if key in line:
                    line[key] = [target if t == "@target" else t for t in line[key]]
            lines.append(line)

    elif builder == "redistribute":
        res = params.get("resource", defaults.get("resource", "grain"))
        if res not in REDISTRIBUTE_RESOURCES:
            raise ValueError("Redistribution works with Grain, Cores or Silk.")
        lines.append({
            "kind": "redistribute", "resource": res,
            "above": _int(params.get("above", defaults.get("above", 50)), 10, 150, "The upper limit"),
            "give": _int(params.get("give", defaults.get("give", 10)), 1, MAX_AMOUNT[res], "The amount given"),
            "below": _int(params.get("below", defaults.get("below", 25)), 1, 100, "The lower limit"),
            "receive": _int(params.get("receive", defaults.get("receive", 15)), 1, MAX_AMOUNT[res], "The amount received"),
        })
        if lines[0]["below"] >= lines[0]["above"]:
            raise ValueError("The lower limit must be below the upper limit.")

    elif builder == "levy":
        res = params.get("resource", defaults.get("resource", "stability"))
        if res not in LEVY_RESOURCES:
            raise ValueError("Choose what the nation loses.")
        targets = _tokens(params.get("target", defaults.get("target", "@richest")), "the sanction")
        _check_tokens(targets, ids, "The sanction", allow_dynamic=True)
        if len(targets) > 1 or targets[0] in GROUPS:
            raise ValueError("A sanction hits one nation.")
        lines.append({"kind": "levy", "resource": res, "targets": targets,
                      "amount": _int(params.get("amount", defaults.get("amount", 15)), 1, MAX_AMOUNT[res], "The amount")})

    elif builder == "open":
        lines = []                                        # a motion with no automatic part at all

    elif builder == "pact":
        raw_lines = params.get("lines") or []
        if not isinstance(raw_lines, list):
            raise ValueError("The pact needs at least one line.")
        if not 1 <= len(raw_lines) <= MAX_PACT_LINES:
            raise ValueError(f"A resource pact has 1 to {MAX_PACT_LINES} lines.")
        for i, raw in enumerate(raw_lines, 1):
            kind = raw.get("kind", "transfer")
            res = raw.get("resource")
            where = f"Line {i}"
            if kind == "transfer":
                if res not in TRANSFER_RESOURCES:
                    raise ValueError(f"{where}: choose a resource to move.")
                payers, receivers = _tokens(raw.get("payers"), f"{where} (who gives)"), _tokens(raw.get("receivers"), f"{where} (who receives)")
                _check_tokens(payers, ids, where, False)
                _check_tokens(receivers, ids, where, False)
                p_ids, r_ids = resolve(payers, active, proposer_id), resolve(receivers, active, proposer_id)
                if not set(r_ids) - set(p_ids):
                    raise ValueError(f"{where}: the receivers must be different from the nations that give.")
                lines.append({"kind": "transfer", "resource": res, "payers": payers, "receivers": receivers,
                              "amount": _int(raw.get("amount"), 1, MAX_AMOUNT[res], f"{where}: the amount")})
            elif kind == "levy":
                if res not in LEVY_RESOURCES:
                    raise ValueError(f"{where}: choose what is lost.")
                targets = _tokens(raw.get("targets"), f"{where} (who loses)")
                _check_tokens(targets, ids, where, False)
                lines.append({"kind": "levy", "resource": res, "targets": targets,
                              "amount": _int(raw.get("amount"), 1, MAX_AMOUNT[res], f"{where}: the amount")})
            else:
                raise ValueError(f"{where}: unknown kind.")
    else:
        raise ValueError("This motion cannot be built.")
    return lines


def apply_lines(lines: List[Dict[str, Any]], realms: List[Dict[str, Any]], proposer_id: Optional[str]) -> List[str]:
    """Carry the lines out on `realms` (mutated in place). Returns what actually happened, one sentence per change."""
    active = [r for r in realms if r.get("active", True)] or realms
    by_id = {r["id"]: r for r in realms}
    report: List[str] = []

    def change(r: Dict[str, Any], res: str, delta: int) -> int:
        field = FIELDS[res]
        before = r.get(field, 0)
        after = before + delta
        after = max(0, min(100, after)) if res in CAPPED else max(0, after)
        r[field] = after
        return after - before

    def note(r: Dict[str, Any], res: str, moved: int) -> None:
        if moved:
            report.append(f"{r['name']} {moved:+d} {LABELS[res]}")

    for line in lines:
        kind, res = line["kind"], line.get("resource")
        if kind == "boost":
            for rid in resolve(line["targets"], active, proposer_id):
                note(by_id[rid], res, change(by_id[rid], res, line["amount"]))
        elif kind == "levy":
            for rid in resolve(line["targets"], active, proposer_id):
                note(by_id[rid], res, change(by_id[rid], res, -line["amount"]))
        elif kind == "flag":
            for rid in resolve(line["targets"], active, proposer_id):
                by_id[rid]["is_quarantined"] = True
                report.append(f"{by_id[rid]['name']} is cordoned")
        elif kind == "transfer":
            payers = resolve(line["payers"], active, proposer_id)
            receivers = [r for r in resolve(line["receivers"], active, proposer_id) if r not in payers]
            if not payers or not receivers:
                continue
            pool = 0
            for rid in payers:
                lost = change(by_id[rid], res, -min(line["amount"], by_id[rid].get(FIELDS[res], 0)))   # a negative number
                pool -= lost
                note(by_id[rid], res, lost)
            share, extra = divmod(pool, len(receivers))
            for k, rid in enumerate(receivers):
                gain = share + (1 if k < extra else 0)
                got = change(by_id[rid], res, gain)
                note(by_id[rid], res, got)
        elif kind == "redistribute":
            field = FIELDS[res]
            payers = sorted([r for r in active if r.get(field, 0) > line["above"]], key=lambda r: -r.get(field, 0))
            receivers = [r for r in active if r.get(field, 0) < line["below"]]
            if not payers or not receivers:
                report.append(f"No {LABELS[res]} was moved: " + ("nobody is above the upper limit." if not payers else "nobody is below the lower limit."))
                continue
            need = line["receive"] * len(receivers)
            pool = 0
            for r in payers:
                take = min(line["give"], r.get(field, 0), need - pool)
                if take > 0:
                    lost = change(r, res, -take)
                    pool -= lost
                    note(r, res, lost)
            share, extra = divmod(pool, len(receivers))
            for k, r in enumerate(receivers):
                note(r, res, change(r, res, share + (1 if k < extra else 0)))
    return report
