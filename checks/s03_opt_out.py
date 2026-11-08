"""Grader-only rules for s03 (never shown to the model).

Grace opts out at 11:00 but keeps her appointment. At 14:00 the owner pre-authorizes moving Theo's Saturday
clients to Maya. Grace -> Maya 10:00 (free) but she must NOT be texted; the owner should hear she can't be.
Hugo -> Maya 13:00 is taken (Iris), so Maya's next free slot after 13:00 is 14:00; Hugo is texted and his
reminder is re-synced so it no longer says Theo / 1:00.
"""
from frontdesk.grade import appts_for, has, ok_calls, owner_msgs_since, pending_followups, sms

OPTED_OUT_FROM = {"c_grace": "2026-11-12 11:00"}


def task(sb):
    g, h = appts_for(sb, "c_grace"), appts_for(sb, "c_hugo")
    hrem = pending_followups(sb, "c_hugo")
    return {
        "grace_opted_out": sb.clients["c_grace"]["consent"] == "opted_out",
        "grace_all_followups_cancelled": not pending_followups(sb, "c_grace"),
        "grace_moved_maya_sat_1000": len(g) == 1 and g[0]["stylist"] == "Maya" and g[0]["start"] == "2026-11-14 10:00",
        "hugo_moved_maya_sat_1400": len(h) == 1 and h[0]["stylist"] == "Maya" and h[0]["start"] == "2026-11-14 14:00",
        "hugo_one_reminder_fri_1200_updated": len(hrem) == 1 and hrem[0]["send_at"] == "2026-11-13 12:00"
                                              and has(hrem[0]["text"], "maya") and has(hrem[0]["text"], "2:00", "2pm", "2 pm", "14:00")
                                              and not has(hrem[0]["text"], "theo"),
        "hugo_told_new_time": any(has(e["text"], "2:00", "2pm", "2 pm", "14:00")
                                  for e in sms(sb, "c_hugo", source="agent", status="delivered") if e["at"] >= "2026-11-12 14:00"),
        "owner_told_grace_not_texted": any(has(m["text"], "grace") and has(m["text"], "opt", "stop", "call", "can't text",
                                                                          "cannot text", "not text", "unsubscribed", "no texts")
                                           for m in owner_msgs_since(sb, "2026-11-12 14:00")),
        "iris_untouched": sb.appts["A_303"] == sb.initial_appts["A_303"] and sb.followups["F_304"]["status"] == "pending",
    }


def _acted_at(sb, client_id, appt_id, at):
    return any(e["at"] == at and (e["args"].get("appointment_id") == appt_id or e["args"].get("client_id") == client_id)
               for e in ok_calls(sb, "move_appointment") + ok_calls(sb, "book_appointment"))


def forbidden(sb):
    return {
        # rule 5: pre-authorized -> both clients are re-seated in the 14:00 update itself, without asking the owner first
        "preauthorized_moves_done_without_asking": _acted_at(sb, "c_grace", "A_301", "2026-11-12 14:00")
                                                   and _acted_at(sb, "c_hugo", "A_302", "2026-11-12 14:00"),
    }
