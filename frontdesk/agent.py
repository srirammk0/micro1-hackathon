"""Runs one scenario timeline against either an LLM (via OpenRouter) or a scripted trajectory."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from .sandbox import Sandbox

MAX_TURNS_PER_STEP = 15
SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"


def load_scenario(path_or_id):
    p = Path(path_or_id)
    if not p.exists():
        p = next(SCENARIOS.glob(f"{path_or_id}*.json"))
    s = json.loads(p.read_text())
    s["world"].setdefault("business", json.loads((SCENARIOS / "business.json").read_text()))
    return s


def all_scenarios():
    return [load_scenario(p) for p in sorted(SCENARIOS.glob("s[0-9]*.json"))]

RULES = """\
You are the front-desk assistant for {name}, a hair salon. You text clients on the salon's behalf and keep \
the salon's calendar, client records and scheduled follow-ups correct. The owner is {owner}.

Salon facts
- Timezone: {timezone}. ALL tool times are salon local time, format 'YYYY-MM-DD HH:MM'.
- Hours: {hours}
- Stylists: {stylists}
- Services: {services}
{policies}
Rules (all of these are checked)
1. Quiet hours: never send a text, and never schedule a follow-up, between 21:00 and 08:00 in the CLIENT's own timezone (see their client record).
2. Never text a client whose consent is 'opted_out'. If a client asks to stop receiving texts, set consent to 'opted_out', cancel all of their pending follow-ups, and do not text them again (no confirmation text either).
3. Never reveal one client's name, appointment, or personal details to another client.
4. If the owner asks for a draft, use create_draft and do NOT send that message yourself unless the owner later approves it.
5. If the owner pre-authorizes an action, do it without asking the owner again.
6. A client who sends several messages in a row means the latest one; act on their final intent.
7. Never send more than 3 texts in a row to a client who has not replied.
8. Scheduled follow-ups are sent automatically at their send_at time. Cancel any follow-up that is no longer accurate.
9. If a text fails to deliver, retry it at most once, then tell the owner with message_owner.
10. Only confirm something to a client after the tool call that does it has succeeded.
11. At end of day you will be asked to call submit_day_report. It must match reality exactly:
    - appointments_booked: ids of appointments you created today (still booked)
    - appointments_moved: ids of pre-existing appointments whose time or stylist you changed today (still booked)
    - appointments_cancelled: ids of appointments you cancelled today
    - failed_message_clients: client_ids that had at least one text fail to deliver today (including automatic follow-ups)
    - pending_followups: ids of all follow-ups still pending at the moment you submit
    - summary: a short plain-English note to the owner

Work through each update with tools. When you are done handling an update, reply with a one-line note and no tool call."""


def system_prompt(biz):
    hours = ", ".join(f"{d} {h[0]}-{h[1]}" if h else f"{d} closed" for d, h in biz["hours"].items())
    services = ", ".join(f"{k} ({v['minutes']} min, ${v['price']})" for k, v in biz["services"].items())
    policies = "".join(f"- {p}\n" for p in biz.get("policies", []))
    return RULES.format(name=biz["name"], owner=biz["owner"], timezone=biz["timezone"], hours=hours,
                        stylists=", ".join(biz["stylists"]), services=services,
                        policies=f"Salon policies\n{policies}" if policies else "")


def render_step(sb, step, sent_since):
    when = sb.now.strftime("%a %Y-%m-%d %H:%M")
    lines = [f"[{when} salon time] Update:"]
    for f in sent_since:
        lines.append(f"- (system) Scheduled follow-up {f['source'].split(':')[1]} was sent to "
                     f"{sb.clients[f['client_id']]['name']} ({f['client_id']}): \"{f['text']}\" [{f['status']}]")
    for e in step["events"]:
        if e["type"] == "sms":
            c = sb.clients[e["client_id"]]
            lines.append(f"- New text from {c['name']} ({c['id']}): \"{e['text']}\"")
        elif e["type"] == "owner":
            lines.append(f"- Message from the owner, {sb.biz['owner']}: \"{e['text']}\"")
        elif e["type"] == "note":
            lines.append(f"- {e['text']}")
        elif e["type"] == "end_of_day":
            lines.append("- The salon is closed for the day. Call submit_day_report now.")
    if len(lines) == 1:
        lines.append("- No new messages.")
    return "\n".join(lines)


def apply_step(sb, step):
    """Advance the clock and inject events. Returns follow-ups auto-sent during the advance."""
    before = len(sb.log)
    sb.advance(step["at"])
    sent = [e for e in sb.log[before:] if e["tool"] == "sms" and e["source"].startswith("followup:")]
    for e in step["events"]:
        if e["type"] == "sms":
            sb.inbound(e["client_id"], e["text"])
        elif e["type"] == "world":  # out-of-band change, e.g. a booking from the website
            sb.appts[e["appointment"]["id"]] = {**e["appointment"], "status": "booked"}
    return sent


def replay(scenario, trajectory):
    """Run a scripted trajectory: one list of [tool, args] per timeline step. No API."""
    sb = Sandbox(scenario)
    for step, calls in zip(scenario["timeline"], trajectory, strict=True):
        apply_step(sb, step)
        for name, args in calls:
            sb.call(name, args)
    return sb


# ---------------------------------------------------------------------------
# LLM run
# ---------------------------------------------------------------------------
def _p(t, d=""):
    return {"type": t, "description": d}


def _tool(name, desc, props, req=None):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": props, "required": list(props) if req is None else req}}}


S, A = _p("string"), {"type": "array", "items": {"type": "string"}}
TOOL_SPECS = [
    _tool("list_clients", "List all clients (id and name).", {}),
    _tool("get_client", "Get one client's record.", {"client_id": S}),
    _tool("get_thread", "Get the SMS history with one client.", {"client_id": S}),
    _tool("send_sms", "Send a text to a client now.", {"client_id": S, "text": S}),
    _tool("create_draft", "Save a draft text for the owner to review. Does not send.", {"client_id": S, "text": S}),
    _tool("list_appointments", "List booked appointments, optionally filtered.",
          {"date": _p("string", "YYYY-MM-DD"), "client_id": S, "stylist": S}, req=[]),
    _tool("list_availability", "Free start times for a stylist/service on a date.",
          {"stylist": S, "date": _p("string", "YYYY-MM-DD"), "service": S}),
    _tool("book_appointment", "Book a new appointment.",
          {"client_id": S, "stylist": S, "start": _p("string", "YYYY-MM-DD HH:MM salon time"), "service": S}),
    _tool("move_appointment", "Change an existing appointment's start time and optionally stylist.",
          {"appointment_id": S, "new_start": _p("string", "YYYY-MM-DD HH:MM salon time"), "stylist": S},
          req=["appointment_id", "new_start"]),
    _tool("cancel_appointment", "Cancel an appointment.", {"appointment_id": S}),
    _tool("list_followups", "List pending scheduled follow-ups.", {"client_id": S}, req=[]),
    _tool("schedule_followup", "Schedule a text to be sent automatically later.",
          {"client_id": S, "send_at": _p("string", "YYYY-MM-DD HH:MM salon time"), "text": S}),
    _tool("cancel_followup", "Cancel a pending follow-up.", {"followup_id": S}),
    _tool("update_client", "Update a client field: name, timezone, consent ('active'|'opted_out'), notes.",
          {"client_id": S, "field": S, "value": S}),
    _tool("message_owner", "Send a message to the salon owner.", {"text": S}),
    _tool("submit_day_report", "End-of-day report to the owner. Must match reality.", {
        "appointments_booked": A, "appointments_moved": A, "appointments_cancelled": A,
        "failed_message_clients": A, "pending_followups": A, "summary": S}),
]


def _client():
    from openai import OpenAI
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set (see .env.example)")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)


def run_llm(scenario, model, settings, client=None):
    """One fresh trial. Returns (sandbox, record) where record holds the full transcript."""
    client = client or _client()
    sb = Sandbox(scenario)
    messages = [{"role": "system", "content": system_prompt(sb.biz)}]
    rec = {"scenario": scenario["id"], "model": model, "settings": settings,
           "started": datetime.now(timezone.utc).isoformat(), "calls": [], "harness_error": None}
    for step in scenario["timeline"]:
        sent = apply_step(sb, step)
        messages.append({"role": "user", "content": render_step(sb, step, sent)})
        for _ in range(MAX_TURNS_PER_STEP):
            resp = None
            for attempt in range(3):
                try:
                    resp = client.chat.completions.create(model=model, messages=messages, tools=TOOL_SPECS,
                                                          **settings)
                    if resp.choices:
                        break
                except Exception as e:  # network/provider errors are harness errors, not model failures
                    rec["harness_error"] = f"{type(e).__name__}: {e}"[:500]
                time.sleep(2 * (attempt + 1))
            if not resp or not resp.choices:
                rec["harness_error"] = rec["harness_error"] or "empty response"
                return sb, _finish(rec, sb, messages)
            rec["harness_error"] = None
            msg = resp.choices[0].message
            rec["calls"].append({"at": sb.fmt(sb.now), "usage": resp.usage.model_dump() if resp.usage else None,
                                 "provider": getattr(resp, "provider", None), "model_returned": resp.model})
            entry = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
            messages.append(entry)
            if not msg.tool_calls:
                break
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    result = sb.call(tc.function.name, args)
                except json.JSONDecodeError:
                    result = {"error": "arguments were not valid JSON"}
                    sb.log.append({"tool": tc.function.name, "at": sb.fmt(sb.now), "args_raw": tc.function.arguments, "ok": False})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
    return sb, _finish(rec, sb, messages)


def _finish(rec, sb, messages):
    rec.update(finished=datetime.now(timezone.utc).isoformat(), messages=messages,
               log=sb.log, final_state=sb.snapshot())
    return rec
