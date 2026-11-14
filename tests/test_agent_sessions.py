"""Tests fuer bin/agent-sessions (urspruenglich von bernhard2804) (ohne Netz, ohne fzf; erfundene Sitzungen in einem Temp-Home).

Aufruf: python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "agent-sessions"
ID_A = "11111111-1111-4111-8111-111111111111"
ID_B = "22222222-2222-4222-8222-222222222222"
ID_C = "33333333-3333-4333-8333-333333333333"
ID_D = "44444444-4444-4444-8444-444444444444"
ID_E = "55555555-5555-4555-8555-555555555555"
ID_X = "01a1aaaa-bbbb-7ccc-8ddd-eeeeeeeeeeee"  # Codex
ID_Y = "66666666-6666-4666-8666-666666666666"  # Agy


def lade(home):
    """Skript als Modul laden; Pfade werden beim Import aus HOME/Umgebung gelesen."""
    env = {"HOME": home, "CLAUDE_CONFIG_DIR": os.path.join(home, ".claude"),
           "XDG_CACHE_HOME": os.path.join(home, ".cache")}
    sys.dont_write_bytecode = True  # kein __pycache__ im Plugin-Ordner
    with mock.patch.dict(os.environ, env):
        loader = importlib.machinery.SourceFileLoader("agent_sessions", str(SCRIPT))
        spec = importlib.util.spec_from_loader("agent_sessions", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    return mod


def zeile(**kw):
    return json.dumps(kw, separators=(",", ":")) + "\n"  # kompakt wie Claude Code


def sitzung(home, sid, cwd, eintraege):
    ordner = Path(home, ".claude", "projects", cwd.replace("/", "-"))
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{sid}.jsonl").write_text("".join(eintraege))


def user(text, cwd, ts="2026-11-01T10:00:00Z", **kw):
    return zeile(type="user", cwd=cwd, timestamp=ts, message={"role": "user", "content": text}, **kw)


def antwort(text, cwd, ts="2026-11-01T10:01:00Z"):
    return zeile(type="assistant", cwd=cwd, timestamp=ts,
                 message={"role": "assistant", "content": [{"type": "text", "text": text}]})


class ClaudeSitzungenTest(unittest.TestCase):
    def setUp(self):
        # Nicht unter /tmp: Dort liegende Sitzungen blendet die Codex-Liste
        # bewusst aus (Curator-Laeufe).
        basis = os.environ.get("XDG_RUNTIME_DIR")
        self.tmp = tempfile.TemporaryDirectory(dir=basis if basis and os.path.isdir(basis)
                                               else Path(__file__).resolve().parent)
        self.home = self.tmp.name
        self.arbeit = os.path.join(self.home, "Arbeit")
        os.makedirs(self.arbeit)
        a = self.arbeit
        sitzung(self.home, ID_A, a, [
            user("<system-reminder>Gedaechtnis mit Kunde-A</system-reminder>Wie richte ich den Drucker ein?", a),
            antwort("So geht das mit dem Drucker.", a),
            zeile(type="ai-title", aiTitle="Drucker\x1b]0;boese\x07 einrichten"),
            user("Und der Scanner?", a, ts="2026-11-02T09:00:00Z"),
        ])
        # Ordner existiert nicht mehr -> nicht fortsetzbar, nicht gelistet
        sitzung(self.home, ID_B, os.path.join(self.home, "weg"), [
            user("Alte Frage", os.path.join(self.home, "weg"))])
        # nur Slash-Befehl, keine echte Eingabe -> nicht gelistet
        sitzung(self.home, ID_C, a, [user("<command-name>/login</command-name>", a)])
        # Ordner ausserhalb des Home -> nicht gelistet, nicht oeffenbar
        sitzung(self.home, ID_D, "/tmp", [user("Frage in /tmp", "/tmp")])
        # Codex: Kopfzeile der rollout-Datei plus Titel aus session_index.jsonl
        cx = Path(self.home, ".codex", "sessions", "2026", "11", "01")
        cx.mkdir(parents=True)
        # zeile() maskiert Umlaute als \\uXXXX (ensure_ascii), wie Codex teils auch
        (cx / f"rollout-2026-11-01T10-00-00-{ID_X}.jsonl").write_text(
            zeile(timestamp="2026-11-01T10:00:00Z", type="session_meta",
                  payload={"id": ID_X, "cwd": a, "thread_source": "user"})
            + zeile(timestamp="2026-11-01T10:00:01Z", type="response_item",
                    payload={"type": "message", "role": "user",
                             "content": [{"type": "input_text", "text": "<environment_context>Kunde-B"}]})
            + zeile(timestamp="2026-11-01T10:00:02Z", type="event_msg",
                    payload={"type": "item_completed", "item": {"type": "UserMessage", "content": [
                        {"type": "text", "text": "Grüße an den Router?"}]}})
            + zeile(timestamp="2026-11-01T10:00:03Z", type="event_msg",
                    payload={"type": "item_completed", "item": {"type": "CommandExecution", "output": "router"}})
            + zeile(timestamp="2026-11-01T10:05:00Z", type="event_msg",
                    payload={"type": "item_completed", "item": {"type": "AgentMessage", "phase": "final_answer",
                             "content": [{"type": "Text", "text": "Der Router grüßt zurück.\x1b]0;x\x07"}]}})
            + zeile(timestamp="2026-11-01T10:06:00Z", type="event_msg",
                    payload={"type": "item_completed", "item": {"type": "AgentMessage", "phase": "commentary",
                             "content": [{"type": "Text", "text": "Ich prüfe noch den Router."}]}}))
        # Agy: Metadaten plus Verlauf; nur <USER_REQUEST> und Antworten zaehlen
        ag = Path(self.home, ".gemini", "antigravity-cli")
        (ag / "cache").mkdir(parents=True)
        (ag / "cache" / "conversation_metadata.json").write_text(json.dumps({"conversations": {ID_Y: {"summary": {
            "Title": "Agy-Frage", "UpdatedAt": "2026-11-01T12:00:00Z", "WorkspaceURIs": ["file://" + a]}}}}))
        lg = ag / "brain" / ID_Y / ".system_generated" / "logs"
        lg.mkdir(parents=True)
        (lg / "transcript_full.jsonl").write_text(
            zeile(type="USER_INPUT", source="USER_EXPLICIT", created_at="2026-11-01T11:00:00Z",
                  content="<USER_REQUEST>\nWo ist der Router?\n</USER_REQUEST>\n"
                          "<ADDITIONAL_METADATA>Kunde-C</ADDITIONAL_METADATA>")
            + zeile(type="GENERIC", source="MODEL", created_at="2026-11-01T11:00:05Z", content="router.log")
            + zeile(type="PLANNER_RESPONSE", source="MODEL", created_at="2026-11-01T11:01:00Z",
                    content="Im Keller.", tool_calls=[]))
        Path(self.home, ".codex", "session_index.jsonl").write_text(zeile(id=ID_X, thread_name="Codex-Frage"))
        self.m = lade(self.home)
        # Tests sollen nicht davon abhaengen, ob claude/codex/Terminal installiert sind.
        w = mock.patch.object(self.m.shutil, "which", return_value="/usr/bin/x")
        w.start()
        self.addCleanup(w.stop)
        if self.m.STATUS is not None:  # kein hyprctl in Tests
            self.m.STATUS.window_pids = lambda: set()

    def tearDown(self):
        self.tmp.cleanup()

    def test_index_filtert_und_wertet_aus(self):
        e = {x["id"]: x for x in self.m.index()}
        self.assertEqual(set(e), {ID_A})
        a = e[ID_A]
        self.assertEqual(a["fragen"], 2)
        self.assertEqual(a["erste"], "Wie richte ich den Drucker ein?")  # system-reminder entfernt
        self.assertEqual(a["letzte"], "Und der Scanner?")
        self.assertEqual(a["cwd"], self.arbeit)

    def test_steuerzeichen_im_titel_werden_entfernt(self):
        z = self.m.liste("claude")
        self.assertEqual(len(z), 1)
        self.assertNotIn("\x1b]", z[0])
        self.assertNotIn("\x07", z[0])
        self.assertIn("Drucker]0;boese einrichten", z[0])
        self.assertTrue(z[0].startswith(ID_A + "\t"))

    def test_cache_wird_wiederverwendet(self):
        self.m.index()
        with mock.patch.object(self.m, "auswerten", side_effect=AssertionError("neu ausgewertet")):
            self.assertEqual(len(self.m.index()), 1)

    def test_inhaltssuche_ignoriert_system_reminder(self):
        _, t = self.m.inhaltssuche("Kunde-A")
        self.assertEqual(t, {})
        e, t = self.m.inhaltssuche("drucker")
        self.assertEqual(t, {ID_A: 2})  # Frage + Antwort, Titel zaehlt nicht
        self.assertEqual([x["key"] for x in e], [ID_A])

    def test_cache_nur_fuer_den_nutzer_lesbar(self):
        self.m.index()
        self.assertEqual(os.stat(self.m.CACHE).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(os.path.dirname(self.m.CACHE)).st_mode & 0o777, 0o700)

    def test_inhaltssuche_mit_anfuehrungszeichen_und_backslash(self):
        a = self.arbeit
        sitzung(self.home, ID_E, a, [user('Was macht "rm -rf" in C:\\Temp?', a)])
        _, t = self.m.inhaltssuche('"rm -rf"')
        self.assertEqual(t, {ID_E: 1})
        _, t = self.m.inhaltssuche("C:\\Temp")
        self.assertEqual(t, {ID_E: 1})

    def test_bidi_und_richtungszeichen_werden_entfernt(self):
        self.assertEqual(self.m.sauber("a\u202eb\u200fc\u2066d\u061ce"), "abcde")

    def test_oeffnen_nur_mit_gueltiger_id_und_ordner(self):
        with mock.patch.object(self.m.subprocess, "Popen") as popen, \
                mock.patch.object(self.m, "melden") as melden, \
                mock.patch.object(self.m, "offene", return_value={}):
            self.m.oeffnen("../../etc/passwd")
            self.m.oeffnen(ID_D)
            self.m.oeffnen(ID_B)
            popen.assert_not_called()
            self.assertEqual(melden.call_count, 3)
            self.m.oeffnen(ID_A, abzweig=True)
            popen.assert_called_once()
            args, kw = popen.call_args
            self.assertEqual(args[0][-4:], ["claude", "--resume", ID_A, "--fork-session"])
            self.assertEqual(kw["cwd"], self.arbeit)
            self.assertFalse(set(kw["env"]) & self.m.LAUFZEIT_VARS)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_CHILD_SESSION": "1"}), \
                mock.patch.object(self.m.subprocess, "Popen") as popen:
            self.m.oeffnen(ID_A)
            env = popen.call_args[1]["env"]
            self.assertEqual(env.get("CLAUDE_CODE_USE_BEDROCK"), "1")  # Nutzereinstellung bleibt
            self.assertNotIn("CLAUDE_CODE_CHILD_SESSION", env)

    def test_agentenwahl_listet_codex_mit_agent_und_schluessel(self):
        alle = self.m.liste("alle")
        self.assertEqual(len(alle), 3)
        codex = [z for z in alle if z.startswith("codex:")]
        self.assertEqual(len(codex), 1)
        self.assertTrue(codex[0].startswith(f"codex:{ID_X}\t"))
        self.assertIn("Codex-Frage", codex[0])
        self.assertEqual([z.split("\t")[0] for z in self.m.liste("claude")], [ID_A])
        self.assertEqual([z.split("\t")[0] for z in self.m.liste("agy")], ["agy:" + ID_Y])

    def test_vorschau_codex_und_agy_aus_dem_verlauf(self):
        for schluessel, erwartet, fehlt in (
                ("codex:" + ID_X, ["Grüße an den Router?", "Der Router grüßt zurück.", "\x1b[0m 1\n"],
                 ["Kunde-B", "\x1b]", "\x07", "Ich prüfe"]),
                ("agy:" + ID_Y, ["Wo ist der Router?", "Im Keller.", "Agy-Frage"], ["Kunde-C", "USER_REQUEST"])):
            with self.subTest(schluessel=schluessel), mock.patch("builtins.print") as p:
                self.m.vorschau(schluessel)
                aus = "\n".join(str(c[0][0]) if c[0] else "" for c in p.call_args_list)
                for t in erwartet:
                    self.assertIn(t, aus)
                for t in fehlt:
                    self.assertNotIn(t, aus)

    def test_inhaltssuche_ueber_alle_agenten_und_maskierte_umlaute(self):
        for rg in (True, False):  # mit und ohne ripgrep
            with self.subTest(rg=rg), mock.patch.object(
                    self.m.shutil, "which", side_effect=lambda b: None if b == "rg" and not rg else "/usr/bin/x"):
                _, t = self.m.inhaltssuche("router")
                self.assertEqual(t, {"codex:" + ID_X: 3, "agy:" + ID_Y: 1})  # Werkzeugausgaben zaehlen nicht
                _, t = self.m.inhaltssuche("grü")
                self.assertEqual(t, {"codex:" + ID_X: 2})
                _, t = self.m.inhaltssuche("prüfe")  # Zwischenmeldung
                self.assertEqual(t, {"codex:" + ID_X: 1})
                _, t = self.m.inhaltssuche("Kunde")  # eingeschobener Kontext, Agy-Metadaten
                self.assertEqual(t, {})
                _, t = self.m.inhaltssuche("router", "agy")
                self.assertEqual(t, {"agy:" + ID_Y: 1})
                _, t = self.m.inhaltssuche("drucker", "codex")
                self.assertEqual(t, {})

    def test_codex_unerwartete_und_gemischte_datensaetze(self):
        d = os.path.join(self.home, ".codex", "sessions", "2026", "11", "01", f"rollout-2026-11-01T10-00-00-{ID_X}.jsonl")
        with open(d, "a") as f:
            f.write(zeile(type="event_msg", payload={"type": "item_completed", "item": {"type": ["UserMessage"]}}))
            # alte Form (fortgesetzte Sitzung): neue Frage zaehlt, Doppel nicht
            f.write(zeile(type="event_msg", payload={"type": "user_message", "message": "Grüße an den Router?"}))
            f.write(zeile(type="event_msg", payload={"type": "user_message", "message": "Alter Router-Teil"}))
        _, t = self.m.inhaltssuche("router", "codex")
        self.assertEqual(t, {"codex:" + ID_X: 4})
        with mock.patch("builtins.print") as p:
            self.m.vorschau("codex:" + ID_X)
        aus = "\n".join(str(c[0][0]) if c[0] else "" for c in p.call_args_list)
        self.assertIn("\x1b[0m 2\n", aus)  # zwei Eingaben
        self.assertIn("Alter Router-Teil", aus)

    def test_ohne_endantwort_gilt_letzte_zwischenmeldung(self):
        z = self.m.zusammenfassen([("user", "F", None), ("zwischen", "Z1", None), ("zwischen", "Z2", None)])
        self.assertEqual(z["antwort"], "Z2")
        z = self.m.zusammenfassen([("assistant", "A", None), ("zwischen", "Z", None)])
        self.assertEqual(z["antwort"], "A")

    def test_inhaltssuche_umlaut_gross_klein_in_maskierter_datei(self):
        sitzung(self.home, ID_E, self.arbeit, [user("Über den Drucker", self.arbeit)])  # als \u00dc
        for q in ("über", "ÜBER", "Über"):
            with self.subTest(q=q):
                _, t = self.m.inhaltssuche(q, "claude")
                self.assertEqual(t, {ID_E: 1})

    def test_inhaltssuche_im_gewaehlten_agenten(self):
        with mock.patch.dict(os.environ, {"FZF_BORDER_LABEL": self.m.rahmen("codex")}), \
                mock.patch("builtins.print") as p:
            self.m.main(["--liste", "--inhalt", "router"])
        aus = p.call_args[0][0]
        self.assertTrue(aus.startswith(f"codex:{ID_X}\t"))
        self.assertIn("[3×]", aus)
        self.assertNotIn("agy:", aus)

    def test_wechsel_springt_reihum_und_setzt_rahmen(self):
        with mock.patch.dict(os.environ, {"FZF_BORDER_LABEL": self.m.rahmen("agy")}), \
                mock.patch("builtins.print") as p:
            self.m.wechsel(1)
        aus = p.call_args[0][0]
        self.assertIn("--liste --agent alle)", aus)
        self.assertTrue(aus.endswith("change-border-label:" + self.m.rahmen("alle")))
        self.assertNotIn("(", aus.split("change-border-label:")[1])  # Rahmen ohne Klammern

    def test_codex_oeffnen_mit_argumentliste_im_eigenen_ordner(self):
        with mock.patch.object(self.m.subprocess, "Popen") as popen, \
                mock.patch.object(self.m, "melden") as melden:
            self.m.oeffnen("codex:" + ID_X, abzweig=True)
            popen.assert_not_called()
            melden.assert_called_once()
            self.m.oeffnen("codex:../../etc")
            popen.assert_not_called()
            self.m.oeffnen("codex:" + ID_X)
            args, kw = popen.call_args
            self.assertEqual(args[0][-3:], ["codex", "resume", ID_X])
            self.assertEqual(kw["cwd"], self.arbeit)

    def test_titel_mit_tab_und_zeilenumbruch_bleibt_eine_spalte(self):
        sitzung(self.home, ID_E, self.arbeit, [user("Frage", self.arbeit),
                                              zeile(type="ai-title", aiTitle="A\tB\nC")])
        z = [x for x in self.m.liste("claude") if x.startswith(ID_E)][0]
        self.assertEqual(z.count("\t"), 1)
        self.assertNotIn("\n", z)

    def test_kaputte_datensaetze_leeren_die_liste_nicht(self):
        sitzung(self.home, ID_E, self.arbeit, [
            "[1, 2]\n", zeile(type="ai-title", aiTitle={"x": 1}),
            zeile(type="user", cwd=self.arbeit, timestamp="2026-11-03T10:00:00Z", message="kein dict"),
            user("Echte Frage", self.arbeit)])
        ids = {e["id"] for e in self.m.index()}
        self.assertEqual(ids, {ID_A, ID_E})
        self.assertTrue(self.m.liste("claude"))

    def test_sprache_einstellung_vor_system_englisch_als_rueckfall(self):
        for env, erwartet in (({"AGENT_LAUNCHERS_LANG": "de", "LANG": "en_US.UTF-8"}, "de"),
                              ({"AGENT_LAUNCHERS_LANG": "", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "de_DE.UTF-8"}, "de"),
                              ({"AGENT_LAUNCHERS_LANG": "", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "fr_FR.UTF-8"}, "en"),
                              ({"AGENT_LAUNCHERS_LANG": "xx", "LC_ALL": "", "LC_MESSAGES": "", "LANG": ""}, "en")):
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                self.assertEqual(self.m.sprache(), erwartet)
                if self.m.STATUS is not None:
                    self.assertEqual(self.m.STATUS.lang(), erwartet)
        with mock.patch.dict(os.environ, {"AGENT_LAUNCHERS_LANG": "en"}):
            self.assertIn("All", self.m.rahmen("alle"))
        with mock.patch.dict(os.environ, {"AGENT_LAUNCHERS_LANG": "de"}):
            self.assertIn("Alle", self.m.rahmen("alle"))
            # Wechsel liest den Rahmen in derselben Sprache zurueck
            with mock.patch.dict(os.environ, {"FZF_BORDER_LABEL": self.m.rahmen("codex")}), \
                    mock.patch("builtins.print") as p:
                self.m.wechsel(1)
            self.assertIn("--agent agy)", p.call_args[0][0])

    def test_offene_sitzung_wird_fokussiert_statt_doppelt_geoeffnet(self):
        with mock.patch.object(self.m.subprocess, "Popen") as popen, \
                mock.patch.object(self.m, "offene", return_value={ID_A: 4242}), \
                mock.patch.object(self.m, "fenster_zu_pid", return_value="0xabc"), \
                mock.patch.object(self.m.subprocess, "run") as run:
            self.m.oeffnen(ID_A)
            popen.assert_not_called()
            self.assertIn("address:0xabc", run.call_args[0][0][-1])



class WeitereAgentenTest(unittest.TestCase):
    """opencode (Struktur wie echte Datenbank) und experimentelle Agenten
    (Formate nach Sudhanshugtm/omarchy-session-browser, MIT)."""

    def setUp(self):
        basis = os.environ.get("XDG_RUNTIME_DIR")
        self.tmp = tempfile.TemporaryDirectory(dir=basis if basis and os.path.isdir(basis)
                                               else Path(__file__).resolve().parent)
        h = self.home = self.tmp.name
        self.arbeit = a = os.path.join(h, "Arbeit")
        os.makedirs(a)
        # opencode: Tabellen session/message/part, Daten als JSON-Text, Zeit in ms
        db = Path(h, ".local", "share", "opencode")
        db.mkdir(parents=True)
        con = sqlite3.connect(db / "opencode.db")
        con.executescript(
            "create table session (id text, title text, directory text, parent_id text, time_updated integer,"
            " time_archived integer);"
            "create table message (id text, session_id text, data text);"
            "create table part (id text, message_id text, session_id text, time_created integer, data text);")
        con.execute("insert into session values ('ses_abcdefgh12', 'Router einrichten', ?, null, 1793000000000, null)", (a,))
        con.execute("insert into session values ('ses_kindkind12', 'Unteraufgabe', ?, 'ses_abcdefgh12', 1793000000000, null)", (a,))
        con.execute("insert into session values ('-rf', 'Boese ID', ?, null, 1793000000000, null)", (a,))
        con.execute("insert into session values ('ses_archiv1234', 'Archiviert', ?, null, 1793000000000, 1793000000001)", (a,))
        for i, (rolle, teil) in enumerate([
                ("user", {"type": "text", "text": "Wie richte ich den Router ein?"}),
                ("user", {"type": "text", "text": "Zweiter Teil derselben Frage."}),
                ("user", {"type": "text", "text": "Datei router.conf", "synthetic": True}),
                ("assistant", {"type": "tool", "state": {"output": "router router"}}),
                ("assistant", {"type": "text", "text": "Der Router ist eingerichtet.\x1b]0;x\x07"})]):
            mid = "m0" if i in (0, 1, 2) else f"m{i}"  # Teile 0-2: eine Nutzernachricht
            if i not in (1, 2):
                con.execute("insert into message values (?, 'ses_abcdefgh12', ?)", (mid, json.dumps({"role": rolle})))
            con.execute("insert into part values (?, ?, 'ses_abcdefgh12', ?, ?)",
                        (f"p{i}", mid, 1793000000000 + i * 60000, json.dumps(teil)))
        con.commit()
        con.close()
        # Copilot: Hauptsitzung und Unteragent
        for sid, start in (("44444444-4444-4444-8444-444444444444", {"sessionId": "44444444-4444-4444-8444-444444444444", "context": {"cwd": a}}),
                           ("55555555-5555-4555-8555-555555555555", {"sessionId": "55555555-5555-4555-8555-555555555555", "kind": "subagent", "context": {"cwd": a}})):
            d = Path(h, ".copilot", "session-state", sid)
            d.mkdir(parents=True)
            (d / "events.jsonl").write_text(zeile(type="session.start", data=start)
                                            + zeile(type="user.message", data={"content": "Copilot-Aufgabe"}))
        # Pi: Kopfzeile mit id, Unteragent wird ausgelassen
        pi = Path(h, ".pi", "agent", "sessions", "--arbeit--")
        pi.mkdir(parents=True)
        (pi / "a.jsonl").write_text(zeile(type="session", id="pi-sitzung-1", cwd=a)
                                    + zeile(type="message", message={"role": "user", "content": "Pi-Aufgabe"}))
        (pi / "b.jsonl").write_text(zeile(type="session", id="pi-kind-0001", cwd=a, kind="subagent"))
        # Gemini CLI: Projektordner aus .project_root
        g = Path(h, ".gemini", "tmp", "projekt")
        (g / "chats").mkdir(parents=True)
        (g / ".project_root").write_text(a)
        (g / "chats" / "session-1.jsonl").write_text(
            zeile(sessionId="66666666-6666-4666-8666-666666666666", projectHash="x")
            + zeile(id="m1", type="user", content="Gemini-Aufgabe"))
        # Grok: Unteragent ueber das Register des Elternteils
        gs = Path(h, ".grok", "sessions", "%2Farbeit")
        for sid, titel in (("99999999-9999-4999-8999-999999999999", "Grok-Aufgabe"),
                           ("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "Delegiert")):
            (gs / sid).mkdir(parents=True)
            (gs / sid / "summary.json").write_text(json.dumps(
                {"info": {"id": sid, "cwd": a}, "generated_title": titel, "updated_at": "2026-11-01T10:00:00Z"}))
        kind = gs / "99999999-9999-4999-8999-999999999999" / "subagents" / "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        kind.mkdir(parents=True)
        (kind / "meta.json").write_text(json.dumps({"child_session_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}))
        with mock.patch.dict(os.environ, {"GROK_HOME": ""}):
            self.m = lade(h)
        w = mock.patch.object(self.m.shutil, "which", return_value="/usr/bin/x")
        w.start()
        self.addCleanup(w.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reiter_nur_fuer_vorhandene_agenten(self):
        self.assertEqual(self.m.AGENTEN, ["alle", "claude", "codex", "agy", "opencode", "copilot", "pi", "gemini", "grok"])
        leer = tempfile.TemporaryDirectory(dir=os.environ.get("XDG_RUNTIME_DIR") or None)
        self.addCleanup(leer.cleanup)
        Path(leer.name, ".gemini", "tmp", "x", "chats").mkdir(parents=True)  # leerer Ordner zaehlt nicht
        with mock.patch.dict(os.environ, {"GROK_HOME": ""}):
            self.assertEqual(lade(leer.name).AGENTEN, ["alle", "claude", "codex", "agy"])

    def test_listen_ohne_unteragenten_und_unzulaessige_ids(self):
        erwartet = {"opencode": ["opencode:ses_abcdefgh12"],
                    "copilot": ["copilot:44444444-4444-4444-8444-444444444444"],
                    "pi": ["pi:pi-sitzung-1"],
                    "gemini": ["gemini:66666666-6666-4666-8666-666666666666"],
                    "grok": ["grok:99999999-9999-4999-8999-999999999999"]}
        for a, schluessel in erwartet.items():
            with self.subTest(agent=a):
                self.assertEqual([z.split("\t")[0] for z in self.m.liste(a)], schluessel)
        self.assertEqual(len(self.m.liste("alle")), 5)

    def test_opencode_vorschau_und_suche(self):
        with mock.patch("builtins.print") as p:
            self.m.vorschau("opencode:ses_abcdefgh12")
        aus = "\n".join(str(c[0][0]) if c[0] else "" for c in p.call_args_list)
        for t in ("Wie richte ich den Router ein?\nZweiter Teil", "Der Router ist eingerichtet.", "\x1b[0m 1\n"):
            self.assertIn(t, aus)
        for t in ("router.conf", "\x1b]", "\x07"):
            self.assertNotIn(t, aus)
        _, t = self.m.inhaltssuche("router", "opencode")
        self.assertEqual(t, {"opencode:ses_abcdefgh12": 2})  # Werkzeug und eingefuegte Dateien zaehlen nicht
        _, t = self.m.inhaltssuche("aufgabe", "alle")  # experimentelle Agenten werden nicht durchsucht
        self.assertEqual(t, {})

    def test_experimentelle_vorschau_ohne_verlauf(self):
        with mock.patch("builtins.print") as p:
            self.m.vorschau("pi:pi-sitzung-1")
        aus = "\n".join(str(c[0][0]) if c[0] else "" for c in p.call_args_list)
        self.assertIn("Pi-Aufgabe", aus)
        self.assertIn("experiment", aus)
        self.assertNotIn("Prompts", aus)
        self.assertNotIn("Eingaben", aus)

    def test_fortsetzen_mit_argumentliste(self):
        for schluessel, befehl in (
                ("opencode:ses_abcdefgh12", ["opencode", "--session", "ses_abcdefgh12"]),
                ("copilot:44444444-4444-4444-8444-444444444444", ["copilot", "--resume", "44444444-4444-4444-8444-444444444444"]),
                ("pi:pi-sitzung-1", ["pi", "--session", "pi-sitzung-1"]),
                ("gemini:66666666-6666-4666-8666-666666666666", ["gemini", "--resume", "66666666-6666-4666-8666-666666666666"]),
                ("grok:99999999-9999-4999-8999-999999999999", ["grok", "--resume", "99999999-9999-4999-8999-999999999999"])):
            with self.subTest(schluessel=schluessel), mock.patch.object(self.m.subprocess, "Popen") as popen:
                self.m.oeffnen(schluessel)
                args, kw = popen.call_args
                self.assertEqual(args[0][-3:], befehl)
                self.assertEqual(kw["cwd"], self.arbeit)
        with mock.patch.object(self.m.subprocess, "Popen") as popen, mock.patch.object(self.m, "melden"):
            self.m.oeffnen("opencode:-rf")
            self.m.oeffnen("pi:../../etc")
            self.m.oeffnen("copilot:55555555-5555-4555-8555-555555555555")  # Unteragent
            popen.assert_not_called()

    def test_kaputte_einzeldatei_leert_die_liste_nicht(self):
        h = Path(self.home)
        kaputt = [h / ".copilot" / "history-session-state" / "kaputt.json",
                  h / ".gemini" / "tmp" / "projekt" / "chats" / "session-0.json",
                  h / ".grok" / "sessions" / "%2Farbeit" / "00000000-0000-4000-8000-000000000000" / "summary.json",
                  h / ".pi" / "agent" / "sessions" / "--arbeit--" / "0.jsonl"]
        for f in kaputt:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('{"halb geschrieben')
        kaputt[-1].chmod(0)  # unlesbar (das Temp-Home loescht sie trotzdem)
        self.assertEqual(len(self.m.liste("alle")), 5)

    def test_alte_formen_abzweige_und_duplikate(self):
        h, a = Path(self.home), self.arbeit
        alt = h / ".copilot" / "history-session-state"
        alt.mkdir(parents=True)
        (alt / "copilot-alt-0001.json").write_text(json.dumps({"summary": "Alte Copilot-Aufgabe", "cwd": a}))
        (alt / "copilot-alt-kind.json").write_text(json.dumps({"summary": "Kind", "kind": "subagent", "cwd": a}))
        g = h / ".gemini" / "tmp" / "projekt" / "chats"
        (g / "session-alt.json").write_text(json.dumps({"sessionId": "77777777-7777-4777-8777-777777777777",
                                                        "messages": [{"role": "user", "content": [{"text": "Alte Gemini-Aufgabe"}]}]}))
        # gleiche ID noch einmal, aelter: die neuere Datei gilt
        (g / "session-2.jsonl").write_text(zeile(sessionId="66666666-6666-4666-8666-666666666666", projectHash="x")
                                           + zeile(id="m1", type="user", content="Veraltet"))
        os.utime(g / "session-2.jsonl", (1, 1))
        gs = h / ".grok" / "sessions" / "%2Farbeit" / "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        gs.mkdir(parents=True)
        (gs / "summary.json").write_text(json.dumps({"info": {"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "cwd": a},
                                                     "generated_title": "Abzweig", "session_kind": "fork",
                                                     "parent_session_id": "99999999-9999-4999-8999-999999999999"}))
        cop = {z.split("\t")[0] for z in self.m.liste("copilot")}
        self.assertEqual(cop, {"copilot:44444444-4444-4444-8444-444444444444", "copilot:copilot-alt-0001"})
        gem = {z.split("\t")[0]: z for z in self.m.liste("gemini")}
        self.assertEqual(set(gem), {"gemini:66666666-6666-4666-8666-666666666666", "gemini:77777777-7777-4777-8777-777777777777"})
        self.assertIn("Gemini-Aufgabe", gem["gemini:66666666-6666-4666-8666-666666666666"])
        self.assertIn("Alte Gemini-Aufgabe", gem["gemini:77777777-7777-4777-8777-777777777777"])
        self.assertEqual(len(self.m.liste("grok")), 2)  # Abzweig des Nutzers bleibt sichtbar

    def test_opencode_im_wal_modus_nur_lesend(self):
        db = Path(self.home, ".local", "share", "opencode", "opencode.db")
        con = sqlite3.connect(db)
        con.execute("pragma journal_mode=wal")
        con.execute("insert into session values ('ses_neu12345', 'Neu im WAL', ?, null, 1793000009000, null)", (self.arbeit,))
        con.commit()  # Schreiber bleibt offen wie ein laufendes opencode
        self.addCleanup(con.close)
        vorher = db.read_bytes()
        self.assertIn("opencode:ses_neu12345", [z.split("\t")[0] for z in self.m.liste("opencode")])
        self.assertEqual(db.read_bytes(), vorher)  # Inhalt unveraendert

    def test_kaputte_datenbank_leert_die_anderen_nicht(self):
        Path(self.home, ".local", "share", "opencode", "opencode.db").write_bytes(b"kein sqlite")
        self.assertEqual(self.m.liste("opencode"), [])
        self.assertEqual(len(self.m.liste("alle")), 4)


class KennzahlenTest(unittest.TestCase):
    """Tokens, Kontext, Agentenzeit und Remote-Markierung (erfundene Datensaetze)."""

    def setUp(self):
        basis = os.environ.get("XDG_RUNTIME_DIR")
        self.tmp = tempfile.TemporaryDirectory(dir=basis if basis and os.path.isdir(basis)
                                               else Path(__file__).resolve().parent)
        self.home = self.tmp.name
        self.m = lade(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def test_claude_tokens_je_nachricht_einmal_kontext_der_letzten_anfrage(self):
        a = self.home
        u1 = {"input_tokens": 10, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 5, "output_tokens": 7}
        u2 = {"input_tokens": 20, "cache_read_input_tokens": 2000, "cache_creation_input_tokens": 0, "output_tokens": 30}
        sitzung(self.home, ID_A, a, [
            user("Frage eins", a),
            # zwei Zeilen derselben Nachricht (je Inhaltsblock) -> nur einmal zaehlen
            zeile(type="assistant", cwd=a, timestamp="2026-11-01T10:01:00Z",
                  message={"id": "m1", "model": "claude-x", "usage": u1, "content": [{"type": "thinking"}]}),
            zeile(type="assistant", cwd=a, timestamp="2026-11-01T10:01:01Z",
                  message={"id": "m1", "model": "claude-x", "usage": u1, "content": [{"type": "text", "text": "a"}]}),
            zeile(type="system", subtype="turn_duration", durationMs=90_000, isSidechain=False),
            zeile(type="assistant", cwd=a, timestamp="2026-11-01T10:02:00Z", isSidechain=True,
                  message={"id": "s1", "model": "claude-y", "usage": u2, "content": []}),
            zeile(type="system", subtype="turn_duration", durationMs=True),  # Unsinn ignorieren
        ])
        e = self.m.auswerten(next(Path(self.home, ".claude", "projects").glob("*/*.jsonl")))
        self.assertEqual(e["tok"], {"ein": 1015 + 2020, "cache": 3000, "aus": 37})
        self.assertEqual(e["ctx"], 1015)  # Nebenkette (Unteragent) zaehlt nicht zum Kontext
        self.assertEqual(e["modell"], "claude-x")
        self.assertEqual(e["arbeit_s"], 90)

    def _codex(self, zeilen):
        d = Path(self.home, "rollout.jsonl")
        d.write_text("".join(zeilen))
        return str(d)

    def test_codex_kontext_fenster_tokens_und_arbeitszeit(self):
        tc = lambda total, ctx: zeile(timestamp="2026-11-01T10:00:05Z", type="event_msg", payload={
            "type": "token_count", "info": {"total_token_usage": {"input_tokens": total, "cached_input_tokens": total // 2,
                                                                   "output_tokens": 9},
                                            "last_token_usage": {"total_tokens": ctx}, "model_context_window": 1000}})
        d = self._codex([
            zeile(timestamp="2026-11-01T10:00:00Z", type="turn_context", payload={"model": "gpt-z"}),
            zeile(timestamp="2026-11-01T10:00:00Z", type="event_msg", payload={"type": "task_started"}),
            tc(100, 50),
            zeile(timestamp="2026-11-01T10:01:00Z", type="event_msg", payload={"type": "task_complete"}),
            zeile(timestamp="2026-11-01T10:05:00Z", type="event_msg", payload={"type": "task_started"}),
            tc(400, 250),
            zeile(timestamp="2026-11-01T10:05:30Z", type="event_msg", payload={"type": "turn_aborted"}),
            zeile(type="event_msg", payload={"type": "token_count", "info": None}),  # ohne Angaben
        ])
        m = self.m.metrik_codex(d, voll=True)
        self.assertEqual((m["ctx"], m["fenster"], m["modell"], m["arbeit_s"]), (250, 1000, "gpt-z", 90))
        self.assertEqual(m["tok"], {"ein": 400, "cache": 200, "aus": 9})
        self.assertIsNone(self.m.metrik_codex(d)["arbeit_s"])  # Liste: nur Dateiende, keine Zeit

    def test_agy_tokens_und_kontext(self):
        d = self._codex([zeile(type="PLANNER_RESPONSE", input_tokens=100, cache_read_tokens=0, output_tokens=5),
                         zeile(type="PLANNER_RESPONSE", input_tokens=10, cache_read_tokens=200, output_tokens=6)])
        m = self.m.metrik_agy(d)
        self.assertEqual((m["ctx"], m["tok"]), (210, {"ein": 310, "cache": 200, "aus": 11}))

    def test_remote_markierung_und_kontext_in_der_zeile(self):
        z = self.m._formatieren([
            {"key": "a", "agent": "claude", "ende": 2.0, "titel": "Fern", "cwd": "/x", "aktiv": True,
             "remote": True, "ctx": 182_000},
            {"key": "b", "agent": "claude", "ende": 1.0, "titel": "Lokal", "cwd": "/x", "aktiv": True, "ctx": 0}])
        self.assertIn(" \U000f0121 Fern  \x1b[2m182k", z[0])
        self.assertIn(" ● Lokal", z[1])
        self.assertNotIn("\x1b[2m0", z[1])

    def test_kurzformen(self):
        with mock.patch.dict(os.environ, {"AGENT_LAUNCHERS_LANG": "de"}):
            self.assertEqual([self.m.kzahl(n) for n in (850, 182_400, 4_120_000)], ["850", "182k", "4,1 M"])
            self.assertEqual([self.m.dauer(s) for s in (30, 600, 7500, 90000)],
                             ["< 1 min", "10 min", "2 h 05 min", "1 T 1 h"])


if __name__ == "__main__":
    unittest.main()
