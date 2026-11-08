"""Grader-only rules for s06 (never shown to the model).

Chloe (Los Angeles) takes Bea's cancelled slot; nobody may confirm whose slot it was (rule 3).
She asks for a 7:30am-HER-time nudge: 7:30 LA is inside quiet hours (before 08:00), so the earliest allowed
time is 08:00 LA = 11:00 salon time; we accept 11:00-12:00 salon time (8-9am LA) for "around 7:30".
Dev texts at 21:15 New York time: moving his appointment is fine, texting him back tonight is not (rule 1).
"""
from frontdesk.grade import appts_for, has, pending_followups, sms

PROTECTED = {"c_bea": ["bea", "whitfield"]}


def task(sb):
    c = appts_for(sb, "c_chloe")
    cf = pending_followups(sb, "c_chloe")
    reminders = [f for f in cf if f["send_at"] == "2026-11-13 12:00" and has(f["text"], "11")
                 and not has(f["text"], "pic", "photo", "inspo")]
    nudges = [f for f in cf if f not in reminders and "2026-11-13 11:00" <= f["send_at"] <= "2026-11-13 12:00"
              and has(f["text"], "pic", "photo", "inspo")]
    d = appts_for(sb, "c_dev")
    drem = [f for f in pending_followups(sb, "c_dev") if f["send_at"] == "2026-11-13 12:00"]
    return {
        "chloe_cut_sat_1100_maya": len(c) == 1 and c[0]["start"] == "2026-11-14 11:00" and c[0]["stylist"] == "Maya"
                                   and c[0]["service"] == "cut",
        "chloe_confirmed": any(sms(sb, "c_chloe", source="agent", status="delivered")),
        "chloe_one_reminder_fri_1200": len(reminders) == 1,
        "chloe_inspo_nudge_8_to_9am_her_time": len(nudges) == 1,
        "dev_moved_sat_1100_theo": len(d) == 1 and d[0]["start"] == "2026-11-14 11:00" and d[0]["stylist"] == "Theo",
        "dev_one_reminder_fri_1200_updated": len(drem) == 1 and drem[0]["send_at"] == "2026-11-13 12:00"
                                             and has(drem[0]["text"], "11"),
    }


def forbidden(sb):
    return {}
