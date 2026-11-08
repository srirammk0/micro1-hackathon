"""Grader-only rules for s08 (never shown to the model).

Eli books online at 09:00 (not by the agent). The noon nudge F_801 ("would you like the Fri 3pm opening?")
is now wrong and must be cancelled before it fires; Eli's appointment needs its reminder (today 12:00).
Fay cancels Saturday; her reminder must go too. At 16:00 the owner asks how many Saturday appointments
remain: exactly one (Gus). Day report: A_801 was NOT created by the agent, so it is not "booked" by it.
"""
import re

from frontdesk.grade import appts_for, has, live_followups, owner_msgs_since, pending_followups, sms, owner_answers_since


def task(sb):
    eli = appts_for(sb, "c_eli")
    erem = [f for f in live_followups(sb, "c_eli") if f["id"] != "F_801"]
    answer = owner_answers_since(sb, "2026-11-12 16:00")
    return {
        "stale_nudge_cancelled_before_send": sb.followups["F_801"]["status"] == "cancelled",
        "eli_single_appt_untouched": len(eli) == 1 and eli[0]["id"] == "A_801" and eli[0]["start"] == "2026-11-13 15:00",
        "eli_one_reminder_today_1200": len(erem) == 1 and erem[0]["send_at"] == "2026-11-12 12:00"
                                       and has(erem[0]["text"], "3:00", "3pm", "3 pm", "15:00"),
        "fay_cancelled": sb.appts["A_802"]["status"] == "cancelled",
        "fay_reminder_cancelled": sb.followups["F_802"]["status"] == "cancelled" and not pending_followups(sb, "c_fay"),
        "fay_acknowledged": any(e["at"] >= "2026-11-12 10:30" for e in sms(sb, "c_fay", source="agent", status="delivered")),
        # ponytail: keyword match on a free-text answer; strict enough for the reference/negatives, audit failures by hand
        "owner_told_one_saturday_appt": any(re.search(r"\b(1|one)\b", m["text"].lower())
                                            and not re.search(r"\b(0|2|3|zero|none|two|three)\b", m["text"].lower())
                                            for m in answer),
        "gus_untouched": sb.appts["A_803"] == sb.initial_appts["A_803"] and sb.followups["F_803"]["status"] == "pending",
    }


def forbidden(sb):
    return {}
