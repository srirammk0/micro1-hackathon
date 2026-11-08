"""In-memory salon world. Tools mutate state and append to an action log.

Tools enforce only physical constraints (a stylist can't be in two places,
the salon is closed outside hours). Policy rules (quiet hours, opt-outs,
privacy, drafts) are NOT enforced here -- the agent must follow them and the
grader checks the log afterwards.
"""
import copy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

FMT = "%Y-%m-%d %H:%M"


class ToolError(Exception):
    pass


class Sandbox:
    def __init__(self, scenario):
        w = copy.deepcopy(scenario["world"])
        self.biz = w["business"]
        self.tz = ZoneInfo(self.biz["timezone"])
        self.clients = {c["id"]: c for c in w["clients"]}
        self.appts = {a["id"]: {**a, "status": a.get("status", "booked")} for a in w["appointments"]}
        self.initial_appts = copy.deepcopy(self.appts)
        self.followups = {f["id"]: {**f, "status": "pending"} for f in w.get("followups", [])}
        self.threads = {cid: list(w.get("threads", {}).get(cid, [])) for cid in self.clients}
        self.fail_sends_to = set(w.get("fail_sends_to", []))
        self.drafts, self.owner_inbox, self.log = [], [], []
        self.report = None
        self.now = self.t(scenario["timeline"][0]["at"])
        self._n = 0

    # ---- helpers -------------------------------------------------------
    def t(self, s):
        try:
            return datetime.strptime(s.strip(), FMT).replace(tzinfo=self.tz)
        except (ValueError, AttributeError):
            raise ToolError(f"bad time {s!r}; use 'YYYY-MM-DD HH:MM' in salon local time")

    def fmt(self, dt):
        return dt.astimezone(self.tz).strftime(FMT)

    def client_local(self, cid, dt=None):
        return (dt or self.now).astimezone(ZoneInfo(self.clients[cid]["timezone"]))

    def _id(self, prefix):
        self._n += 1
        return f"{prefix}{self._n:03d}"

    def _client(self, cid):
        if cid not in self.clients:
            raise ToolError(f"unknown client_id {cid!r}")
        return self.clients[cid]

    def _end(self, a):
        mins = self.biz["services"][a["service"]]["minutes"]
        return self.t(a["start"]) + timedelta(minutes=mins)

    def _check_slot(self, stylist, start, service, ignore=None):
        if stylist not in self.biz["stylists"]:
            raise ToolError(f"unknown stylist {stylist!r}")
        if service not in self.biz["services"]:
            raise ToolError(f"unknown service {service!r}")
        s = self.t(start)
        e = s + timedelta(minutes=self.biz["services"][service]["minutes"])
        hours = self.biz["hours"].get(s.strftime("%a"))
        if not hours:
            raise ToolError(f"salon closed on {s:%A}")
        open_, close = (s.replace(hour=int(h[:2]), minute=int(h[3:])) for h in hours)
        if s < open_ or e > close:
            raise ToolError(f"outside opening hours {hours[0]}-{hours[1]}")
        if s <= self.now:
            raise ToolError("cannot book in the past")
        for a in self.appts.values():
            if a["id"] != ignore and a["status"] == "booked" and a["stylist"] == stylist:
                if s < self._end(a) and self.t(a["start"]) < e:
                    raise ToolError(f"{stylist} is already booked {a['start']} ({a['service']})")

    def _sms(self, cid, text, source):
        status = "failed" if cid in self.fail_sends_to else "delivered"
        msg = {"at": self.fmt(self.now), "dir": "out", "text": text, "status": status, "source": source}
        self.threads[cid].append(msg)
        self.log.append({"tool": "sms", "at": msg["at"], "client_id": cid, "text": text,
                         "status": status, "source": source})
        return status

    # ---- clock ---------------------------------------------------------
    def advance(self, at):
        """Move clock to `at`, auto-sending any pending follow-ups that come due."""
        target = self.t(at)
        for f in sorted(self.followups.values(), key=lambda f: f["send_at"]):
            if f["status"] == "pending" and self.t(f["send_at"]) <= target:
                self.now = max(self.now, self.t(f["send_at"]))
                f["status"] = "sent"
                self._sms(f["client_id"], f["text"], source=f"followup:{f['id']}")
        self.now = max(self.now, target)

    def inbound(self, cid, text):
        self.threads[cid].append({"at": self.fmt(self.now), "dir": "in", "text": text})
        self.log.append({"tool": "inbound", "at": self.fmt(self.now), "client_id": cid, "text": text})

    # ---- tools (exposed to the model) ------------------------------------
    def list_clients(self):
        return [{"client_id": c["id"], "name": c["name"]} for c in self.clients.values()]

    def get_client(self, client_id):
        return self._client(client_id)

    def get_thread(self, client_id):
        self._client(client_id)
        return self.threads[client_id]

    def send_sms(self, client_id, text):
        self._client(client_id)
        status = self._sms(client_id, text, source="agent")
        if status == "failed":
            return {"status": "failed", "error": "carrier error 30003: unreachable destination handset"}
        return {"status": "delivered"}

    def create_draft(self, client_id, text):
        self._client(client_id)
        d = {"draft_id": self._id("D"), "client_id": client_id, "text": text, "at": self.fmt(self.now)}
        self.drafts.append(d)
        return d

    def list_appointments(self, date=None, client_id=None, stylist=None):
        out = [a for a in self.appts.values() if a["status"] == "booked"]
        if date:
            out = [a for a in out if a["start"].startswith(date)]
        if client_id:
            out = [a for a in out if a["client_id"] == client_id]
        if stylist:
            out = [a for a in out if a["stylist"] == stylist]
        return sorted(out, key=lambda a: a["start"])

    def list_availability(self, stylist, date, service):
        free = []
        day = self.t(f"{date} 00:00")
        for m in range(0, 24 * 60, 30):
            s = self.fmt(day + timedelta(minutes=m))
            try:
                self._check_slot(stylist, s, service)
                free.append(s[11:])
            except ToolError:
                pass
        return {"stylist": stylist, "date": date, "service": service, "free_start_times": free}

    def book_appointment(self, client_id, stylist, start, service):
        self._client(client_id)
        self._check_slot(stylist, start, service)
        a = {"id": self._id("A"), "client_id": client_id, "stylist": stylist,
             "start": self.fmt(self.t(start)), "service": service, "status": "booked"}
        self.appts[a["id"]] = a
        return a

    def move_appointment(self, appointment_id, new_start, stylist=None):
        a = self.appts.get(appointment_id)
        if not a or a["status"] != "booked":
            raise ToolError(f"no booked appointment {appointment_id!r}")
        stylist = stylist or a["stylist"]
        self._check_slot(stylist, new_start, a["service"], ignore=a["id"])
        a.update(start=self.fmt(self.t(new_start)), stylist=stylist)
        return a

    def cancel_appointment(self, appointment_id):
        a = self.appts.get(appointment_id)
        if not a or a["status"] != "booked":
            raise ToolError(f"no booked appointment {appointment_id!r}")
        a["status"] = "cancelled"
        return a

    def list_followups(self, client_id=None):
        return [f for f in self.followups.values()
                if f["status"] == "pending" and (not client_id or f["client_id"] == client_id)]

    def schedule_followup(self, client_id, send_at, text):
        self._client(client_id)
        if self.t(send_at) <= self.now:
            raise ToolError("send_at must be in the future")
        f = {"id": self._id("F"), "client_id": client_id, "send_at": self.fmt(self.t(send_at)),
             "text": text, "status": "pending"}
        self.followups[f["id"]] = f
        return f

    def cancel_followup(self, followup_id):
        f = self.followups.get(followup_id)
        if not f or f["status"] != "pending":
            raise ToolError(f"no pending follow-up {followup_id!r}")
        f["status"] = "cancelled"
        return f

    def update_client(self, client_id, field, value):
        c = self._client(client_id)
        if field not in ("name", "timezone", "consent", "notes"):
            raise ToolError("field must be one of name, timezone, consent, notes")
        if field == "consent" and value not in ("active", "opted_out"):
            raise ToolError("consent must be 'active' or 'opted_out'")
        if field == "timezone":
            try:
                ZoneInfo(value)
            except Exception:
                raise ToolError(f"unknown IANA timezone {value!r}")
        c[field] = value
        return c

    def message_owner(self, text):
        self.owner_inbox.append({"at": self.fmt(self.now), "text": text})
        return {"status": "sent"}

    def submit_day_report(self, appointments_booked, appointments_moved, appointments_cancelled,
                          failed_message_clients, pending_followups, summary):
        self.report = {"appointments_booked": appointments_booked,
                       "appointments_moved": appointments_moved,
                       "appointments_cancelled": appointments_cancelled,
                       "failed_message_clients": failed_message_clients,
                       "pending_followups": pending_followups, "summary": summary,
                       "at": self.fmt(self.now)}
        return {"status": "received"}

    TOOLS = ["list_clients", "get_client", "get_thread", "send_sms", "create_draft",
             "list_appointments", "list_availability", "book_appointment", "move_appointment",
             "cancel_appointment", "list_followups", "schedule_followup", "cancel_followup",
             "update_client", "message_owner", "submit_day_report"]

    def call(self, name, args):
        """Dispatch a tool call; every call (ok or error) is logged."""
        entry = {"tool": name, "at": self.fmt(self.now), "args": args}
        try:
            if name not in self.TOOLS:
                raise ToolError(f"unknown tool {name!r}")
            result = getattr(self, name)(**args)
            entry["ok"] = True
        except TypeError as e:
            result, entry["ok"] = {"error": f"bad arguments: {e}"}, False
        except ToolError as e:
            result, entry["ok"] = {"error": str(e)}, False
        # SMS sends are logged by _sms; keep the call entry too for completeness
        self.log.append(entry)
        return copy.deepcopy(result)

    def snapshot(self):
        return {"now": self.fmt(self.now), "clients": self.clients, "appointments": self.appts,
                "followups": self.followups, "threads": self.threads, "drafts": self.drafts,
                "owner_inbox": self.owner_inbox, "report": self.report}
