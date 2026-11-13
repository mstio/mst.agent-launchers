"""Tests fuer bin/agent-sessions (urspruenglich von bernhard2804) (ohne Netz, ohne fzf; erfundene Sitzungen in einem Temp-Home).

Aufruf: python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import json
import os
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


def lade(home):
    """Skript als Modul laden; Pfade werden beim Import aus HOME/Umgebung gelesen."""
    env = {"HOME": home, "CLAUDE_CONFIG_DIR": os.path.join(home, ".claude"),
           "XDG_CACHE_HOME": os.path.join(home, ".cache")}
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
        (cx / f"rollout-2026-11-01T10-00-00-{ID_X}.jsonl").write_text(zeile(
            type="session_meta", payload={"id": ID_X, "cwd": a, "thread_source": "user"}))
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
        z = self.m.zeilen(self.m.index())
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
        self.assertEqual([x["id"] for x in e], [ID_A])

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
        self.assertEqual(len(alle), 2)
        codex = [z for z in alle if z.startswith("codex:")]
        self.assertEqual(len(codex), 1)
        self.assertTrue(codex[0].startswith(f"codex:{ID_X}\t"))
        self.assertIn("Codex-Frage", codex[0])
        self.assertEqual([z.split("\t")[0] for z in self.m.liste("claude")], [ID_A])
        self.assertEqual(self.m.liste("agy"), [])

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
        z = [x for x in self.m.zeilen(self.m.index()) if x.startswith(ID_E)][0]
        self.assertEqual(z.count("\t"), 1)
        self.assertNotIn("\n", z)

    def test_kaputte_datensaetze_leeren_die_liste_nicht(self):
        sitzung(self.home, ID_E, self.arbeit, [
            "[1, 2]\n", zeile(type="ai-title", aiTitle={"x": 1}),
            zeile(type="user", cwd=self.arbeit, timestamp="2026-11-03T10:00:00Z", message="kein dict"),
            user("Echte Frage", self.arbeit)])
        ids = {e["id"] for e in self.m.index()}
        self.assertEqual(ids, {ID_A, ID_E})
        self.assertTrue(self.m.zeilen(self.m.index()))

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


if __name__ == "__main__":
    unittest.main()
