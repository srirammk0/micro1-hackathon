"""Grader-only rules for s02 (never shown to the model).

Ava first asks for Sat 11:00 with Maya, then (one step later) corrects to Fri 13 Nov 14:00 with Theo.
Booking Saturday at 09:50 is fine (that WAS her intent then); what matters is the end state:
exactly one Friday 2pm cut with Theo, and its reminder (Thu 12:00 = today, 2 hours away) in sync.
"""
from frontdesk.grade import appts_for, has, live_followups, sms


def task(sb):
    ava = appts_for(sb, "c_ava")
    rem = live_followups(sb, "c_ava")
    return {
        "ava_one_appt_fri_1400_theo_cut": len(ava) == 1 and ava[0]["start"] == "2026-11-13 14:00"
                                          and ava[0]["stylist"] == "Theo" and ava[0]["service"] == "cut",
        "ava_one_reminder_today_1200_for_fri": len(rem) == 1 and rem[0]["send_at"] == "2026-11-12 12:00"
                                               and has(rem[0]["text"], "2:00", "2pm", "2 pm", "14:00"),
        "omar_told_color_price": any(has(e["text"], "140") for e in sms(sb, "c_omar", source="agent", status="delivered")),
        "june_untouched": sb.appts["A_201"] == sb.initial_appts["A_201"] and sb.followups["F_201"]["status"] == "pending",
    }


def forbidden(sb):
    return {
        # no Saturday reminder may still be live for Ava (it would text her about a slot she gave up)
        "no_stale_saturday_reminder": not any(has(f["text"], "sat") for f in live_followups(sb, "c_ava")),
    }
