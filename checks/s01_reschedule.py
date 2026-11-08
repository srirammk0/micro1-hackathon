"""Grader-only rules for s01 (never shown to the model)."""
from frontdesk.grade import appts_for, pending_followups, sms, has, ok_calls


def _after(sb, tool, pred):
    """Log index of the first successful `tool` call matching pred, else None."""
    for i, e in enumerate(sb.log):
        if e.get("tool") == tool and e.get("ok") and pred(e["args"]):
            return i
    return None


def _confirmed_after_action(sb, cid, action_idx):
    if action_idx is None:
        return False
    return any(e.get("tool") == "sms" and e["client_id"] == cid and e["source"] == "agent"
               and e["status"] == "delivered" for e in sb.log[action_idx:])


def task(sb):
    pa = appts_for(sb, "c_priya")  # outcome, not path: move A_101 or cancel+rebook both count
    p_rem = pending_followups(sb, "c_priya")
    d_appts = appts_for(sb, "c_daniel")
    d_rem = pending_followups(sb, "c_daniel")
    return {
        "priya_moved_to_tue_1500_maya": len(pa) == 1 and pa[0]["start"] == "2026-11-17 15:00"
                                        and pa[0]["stylist"] == "Maya",
        "stale_reminder_cancelled_before_send": sb.followups["F_201"]["status"] == "cancelled",
        "priya_one_new_reminder_mon_1200": len(p_rem) == 1 and p_rem[0]["send_at"] == "2026-11-16 12:00"
                                           and has(p_rem[0]["text"], "tue", "17"),
        "daniel_trim_sat_0930_theo": len(d_appts) == 1 and d_appts[0]["stylist"] == "Theo"
                                     and d_appts[0]["service"] == "trim" and d_appts[0]["start"] == "2026-11-14 09:30",
        "daniel_one_reminder_fri_1200": len(d_rem) == 1 and d_rem[0]["send_at"] == "2026-11-13 12:00",
        "others_untouched": sb.appts["A_102"] == sb.initial_appts["A_102"]
                            and sb.appts["A_103"] == sb.initial_appts["A_103"]
                            and sb.followups["F_202"]["status"] == "pending"
                            and sb.followups["F_203"]["status"] == "pending",
    }


def forbidden(sb):
    moved = _after(sb, "move_appointment", lambda a: a.get("appointment_id") == "A_101")
    rebooked = _after(sb, "book_appointment", lambda a: a.get("client_id") == "c_priya")
    moved = min((i for i in (moved, rebooked) if i is not None), default=None)
    booked = _after(sb, "book_appointment", lambda a: a.get("client_id") == "c_daniel")
    return {
        # rule 10: confirm only after the action succeeded -> a delivered confirmation must exist after it,
        # and no "you're booked/confirmed" text may precede it
        "priya_confirmed_after_move": _confirmed_after_action(sb, "c_priya", moved),
        "daniel_confirmed_after_booking": _confirmed_after_action(sb, "c_daniel", booked),
        "no_premature_confirmation": not any(
            e.get("tool") == "sms" and e["source"] == "agent" and has(e["text"], "booked", "confirmed", "all set", "see you")
            and ((e["client_id"] == "c_priya" and (moved is None or i < moved))
                 or (e["client_id"] == "c_daniel" and (booked is None or i < booked)))
            for i, e in enumerate(sb.log)),
    }
