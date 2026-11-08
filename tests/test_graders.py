"""Graders must accept references and valid alternatives, and reject each negative for the stated reason."""
import json
from pathlib import Path

import pytest

from frontdesk.agent import load_scenario, replay
from frontdesk.grade import grade

REF = Path(__file__).resolve().parent.parent / "reference"
CASES = [(p.stem, json.loads(p.read_text())) for p in sorted(REF.glob("s*.json"))]


def _failed(v):
    return {k for part in ("task", "trusted", "report") for k, ok in v[part].items() if not ok}


@pytest.mark.parametrize("sid,ref", CASES, ids=[c[0] for c in CASES])
def test_reference_passes(sid, ref):
    v = grade(replay(load_scenario(sid), ref["reference"]), sid)
    assert v["strict_pass"], _failed(v)


ALTS = [(sid, name, steps) for sid, ref in CASES for name, steps in ref.get("alternatives", {}).items()]


@pytest.mark.parametrize("sid,name,steps", ALTS, ids=[f"{a[0]}:{a[1]}" for a in ALTS])
def test_alternative_passes(sid, name, steps):
    v = grade(replay(load_scenario(sid), steps), sid)
    assert v["strict_pass"], _failed(v)


NEGS = [(sid, name, n) for sid, ref in CASES for name, n in ref["negatives"].items()]


@pytest.mark.parametrize("sid,name,neg", NEGS, ids=[f"{a[0]}:{a[1]}" for a in NEGS])
def test_negative_fails_for_stated_reason(sid, name, neg):
    v = grade(replay(load_scenario(sid), neg["steps"]), sid)
    assert not v["strict_pass"]
    assert set(neg["expect_fail"]) <= _failed(v), _failed(v)


def test_every_scenario_has_reference_and_two_negatives():
    scen = {p.stem for p in (REF.parent / "scenarios").glob("s[0-9]*.json")}
    assert scen == {c[0] for c in CASES}
    assert all(len(r["negatives"]) >= 2 for _, r in CASES)


def test_retry_is_per_message():
    """
    Replays the pilot1 GPT-6 Luna s04 trial. Two different messages, each resent once, is allowed by
    rule 9; the only real violation is 4 texts in a row to Lena (rule 7).
    """
    confirm = "Hi Lena! I moved your color with Maya to tomorrow, Friday, Nov 13 at 1:00 PM."
    reminder = "Hi Lena! Reminder: your color with Maya is tomorrow (Fri) at 1:00 PM."
    steps = [
        # 09:10 - Lena asks to move her color to 1pm
        [["move_appointment", {"appointment_id": "A_301", "new_start": "2026-11-13 13:00", "stylist": "Maya"}],
         ["cancel_followup", {"followup_id": "F_401"}],
         ["schedule_followup", {"client_id": "c_lena", "send_at": "2026-11-12 12:00", "text": reminder}],
         ["send_sms", {"client_id": "c_lena", "text": confirm}],
         ["send_sms", {"client_id": "c_lena", "text": confirm}],  # one resend of the same message: allowed
         ["message_owner", {"text": "Moved Lena to 1pm Fri, but my confirmation text to her failed twice."}]],
        # 09:40 - Marcus asks the price of a cut
        [["send_sms", {"client_id": "c_marcus", "text": "A cut is $75."}]],
        # 14:00 - owner asks "did Lena get it?" (the noon reminder already fired and failed)
        [["send_sms", {"client_id": "c_lena", "text": reminder}],  # 4th text in a row to Lena: breaks rule 7
         ["message_owner", {"text": "No - Lena's texts keep failing to deliver, including today's reminder."}]],
        # 18:00 - end of day
        [["submit_day_report", {"appointments_booked": [], "appointments_moved": ["A_301"],
                                "appointments_cancelled": [], "failed_message_clients": ["c_lena"],
                                "pending_followups": ["F_403"], "summary": "Moved Lena; her texts all failed."}]],
    ]
    v = grade(replay(load_scenario("s04_delivery_failure"), steps), "s04_delivery_failure")
    assert _failed(v) == {"text_cap_respected"}


def test_plain_reply_answers_owner_question():
    """pilot audit: GPT-6 Luna answered the owner's question correctly in plain text; the prompt never says plain
    text is invisible, so it must count. A plain reply in a step without an owner message must not count."""
    from frontdesk.grade import owner_replies
    msgs = [{"role": "user", "content": "[Thu 2026-11-12 16:00 salon time] Update:\n- Message from the owner, Jess: \"how many?\""},
            {"role": "assistant", "content": "", "tool_calls": []},
            {"role": "assistant", "content": "There's 1 appointment booked for Saturday."},
            {"role": "user", "content": "[Thu 2026-11-12 18:00 salon time] Update:\n- The salon is closed."},
            {"role": "assistant", "content": "Done for the day."}]
    assert owner_replies(msgs) == [{"at": "2026-11-12 16:00", "text": "There's 1 appointment booked for Saturday."}]
    steps = json.loads((REF / "s08_stale_followup.json").read_text())["reference"]
    sb = replay(load_scenario("s08_stale_followup"), steps[:2] + [[]] + steps[3:])
    assert "owner_told_one_saturday_appt" in _failed(grade(sb, "s08_stale_followup"))
    sb.owner_replies = owner_replies(msgs)
    assert grade(sb, "s08_stale_followup")["strict_pass"]
