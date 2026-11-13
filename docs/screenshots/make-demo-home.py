"""Invented demo sessions for the README screenshots (no real content).

Usage: python3 docs/screenshots/make-demo-home.py <empty demo home>
Then start the window with HOME, CLAUDE_CONFIG_DIR and XDG_CACHE_HOME
pointing into that demo home (see README, Development).
"""
import json, os, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

H = Path(sys.argv[1]); now = datetime.now().astimezone()
def iso(dt): return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
def z(**kw): return json.dumps(kw, separators=(",", ":")) + "\n"
ids = iter(f"{i:08x}-1111-4111-8111-{i:012x}" for i in range(1, 99))

claude = [  # (Titel, Ordner, vor Stunden, erste, letzte, Antwort)
 ("Fix flaky login test in CI", "Work/webshop", 0.6, "The login test fails about one run in ten on CI but never locally. Can you find out why?",
  "ok, also add a regression test", "Done. The test waited for the redirect with a fixed 500 ms sleep; on the slower CI runners the session cookie arrived later. It now waits for the cookie instead, and a new regression test simulates a slow response."),
 ("Refactor invoice export to async", "Projects/billing", 3.2, "Our invoice export blocks the web worker for minutes. Let's move it to a background job.",
  "looks good, write the migration notes", "Migration notes are in docs/export.md: the endpoint now returns a job id, the PDF arrives by mail, old links keep working for 30 days."),
 ("Set up WireGuard on the home server", "Work", 26, "I want to reach my home server from the laptop when I'm travelling.",
  "and only route the home network through it", "Set AllowedIPs to 192.168.1.0/24 only; everything else keeps using your normal connection."),
 ("Explain Hyprland window rules", "Work", 50, "How do window rules work in Hyprland 0.56 with the Lua config?", "can a rule match the title?", "Yes: match = { title = \"^Picture-in-Picture$\" }."),
 ("Write release notes for v2.3", "Projects/billing", 75, "Draft release notes for v2.3 from the merged PRs.", "shorter please", "Shortened to five bullet points."),
 ("Debug Bluetooth headset dropouts", "Work", 98, "My headset drops out every few minutes.", "it still happens on battery", "Power saving on the USB adapter is the likely cause; the udev rule keeps it awake."),
 ("Plan database backup rotation", "Projects/billing", 170, "How long should we keep nightly database backups?", "and monthly ones?", "Keep 14 nightly, 12 monthly and the yearly ones."),
 ("Translate onboarding guide", "Work/handbook", 260, "Translate the onboarding guide into German.", "keep the code blocks", "Done, code blocks unchanged."),
]
for title, rel, hours, first, last, answer in claude:
    sid = next(ids); cwd = str(H / rel); Path(cwd).mkdir(parents=True, exist_ok=True)
    t1 = now - timedelta(hours=hours + 1.5); t2 = now - timedelta(hours=hours)
    d = H / ".claude" / "projects" / cwd.replace("/", "-"); d.mkdir(parents=True, exist_ok=True)
    lines = [z(type="user", cwd=cwd, timestamp=iso(t1), message={"role": "user", "content": first}),
             z(type="assistant", cwd=cwd, timestamp=iso(t1 + timedelta(minutes=2)),
               message={"role": "assistant", "content": [{"type": "text", "text": "Looking into it."}]}),
             z(type="ai-title", aiTitle=title),
             z(type="user", cwd=cwd, timestamp=iso(t2 - timedelta(minutes=3)), message={"role": "user", "content": last}),
             z(type="assistant", cwd=cwd, timestamp=iso(t2), message={"role": "assistant", "content": [{"type": "text", "text": answer}]})]
    (d / f"{sid}.jsonl").write_text("".join(lines))

codex = [  # (Titel, Ordner, vor Stunden, Fragen, Endantwort)
 ("Migrate CI to GitHub Actions", "Work/webshop", 5, ["Move our CI from Jenkins to GitHub Actions, same steps."],
  "The workflow in .github/workflows/ci.yml runs lint, tests and the Docker build; Jenkins can be switched off."),
 ("Show unpaid invoices on the dashboard", "Projects/billing", 2.0,
  ["The dashboard should list unpaid invoices older than 30 days.", "sort them by amount, largest first"],
  "Added an 'Overdue invoices' card: unpaid invoices older than 30 days, sorted by amount, with a link to each invoice."),
 ("Review Dockerfile for size", "Work/webshop", 120, ["Why is our Docker image 1.2 GB?"],
  "A multi-stage build drops the compilers; the image is now 180 MB.")]
idx = []
for i, (title, rel, hours, fragen, endantwort) in enumerate(codex):
    cid = f"019a{i:04x}-aaaa-7bbb-8ccc-{i:012x}"; cwd = str(H / rel); Path(cwd).mkdir(parents=True, exist_ok=True)
    d = H / ".codex" / "sessions" / "2026" / "11" / f"{10 + i:02d}"; d.mkdir(parents=True, exist_ok=True)
    f = d / f"rollout-2026-11-{10 + i:02d}T10-00-00-{cid}.jsonl"
    t0 = now - timedelta(hours=hours + 1)
    zeilen = [z(timestamp=iso(t0), type="session_meta", payload={"id": cid, "cwd": cwd, "thread_source": "user"})]
    for k, frage in enumerate(fragen):
        zeilen.append(z(timestamp=iso(t0 + timedelta(minutes=10 * k)), type="event_msg", payload={
            "type": "item_completed", "item": {"type": "UserMessage", "content": [{"type": "text", "text": frage}]}}))
        zeilen.append(z(timestamp=iso(t0 + timedelta(minutes=10 * k + 2)), type="event_msg", payload={
            "type": "item_completed", "item": {"type": "AgentMessage", "phase": "commentary",
                                               "content": [{"type": "Text", "text": "Checking the code."}]}}))
    zeilen.append(z(timestamp=iso(now - timedelta(hours=hours)), type="event_msg", payload={
        "type": "item_completed", "item": {"type": "AgentMessage", "phase": "final_answer",
                                           "content": [{"type": "Text", "text": endantwort}]}}))
    f.write_text("".join(zeilen))
    t = (now - timedelta(hours=hours)).timestamp(); os.utime(f, (t, t))
    idx.append(z(id=cid, thread_name=title))
(H / ".codex" / "session_index.jsonl").write_text("".join(idx))

agy = {}
for i, (title, rel, hours, frage, antwort) in enumerate([
        ("Draft API spec for orders", "Projects/billing", 9, "Draft an OpenAPI spec for orders and their invoices.",
         "Draft in api/orders.yaml: orders, order items and a read-only invoices endpoint per order."),
        ("Summarize meeting notes", "Work", 200, "Summarize the notes from Monday's planning meeting.",
         "Three decisions, two open questions, owners listed at the end.")]):
    cid = f"7d3e{i:04x}-cccc-4ddd-8eee-{i:012x}"; cwd = str(H / rel)
    agy[cid] = {"summary": {"Title": title, "UpdatedAt": iso(now - timedelta(hours=hours)), "WorkspaceURIs": ["file://" + cwd]}}
    lg = H / ".gemini" / "antigravity-cli" / "brain" / cid / ".system_generated" / "logs"; lg.mkdir(parents=True, exist_ok=True)
    t = now - timedelta(hours=hours)
    (lg / "transcript_full.jsonl").write_text(
        z(type="USER_INPUT", source="USER_EXPLICIT", created_at=iso(t - timedelta(minutes=20)),
          content=f"<USER_REQUEST>\n{frage}\n</USER_REQUEST>\n<ADDITIONAL_METADATA>demo</ADDITIONAL_METADATA>")
        + z(type="PLANNER_RESPONSE", source="MODEL", created_at=iso(t), content=antwort, tool_calls=[]))
m = H / ".gemini" / "antigravity-cli" / "cache"; m.mkdir(parents=True, exist_ok=True)
(m / "conversation_metadata.json").write_text(json.dumps({"conversations": agy}))
print("ok", H)
